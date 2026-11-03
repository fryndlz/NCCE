"""Owner-authorized, bounded filling of existing pending narrative records."""
import hashlib
import json
import uuid
import llm_writer as writer
import writer_workshop as ws
import writing_rag

PREFIX = 'category-population:'
TABLES = {'artifact': ('story_artifacts', 'artifact_id'), 'entry': ('narrative_entries', 'entry_id'),
          'memory': ('story_memories', 'memory_id'), 'mind': ('fighter_thoughts', 'thought_id')}


def hashed(value):
    return hashlib.sha256(ws.packed(value).encode()).hexdigest()


def record(store, key):
    kind, _, ident = key.partition(':')
    if kind=='scene':
        row=store.db.execute('SELECT * FROM territories WHERE id=? AND active=1',(ident,)).fetchone()
        if not row:raise ValueError('Scene territory no longer exists')
        return {'territory':dict(row),'active':1,'writer_status':'pending','provenance_class':'connective_fiction'}
    if kind not in TABLES:
        raise ValueError('This is not a campaign writing record')
    table, column = TABLES[kind]
    row = store.db.execute(f'SELECT * FROM {table} WHERE {column}=?', (ident,)).fetchone()
    if not row:
        raise ValueError('The source record no longer exists')
    return dict(row)


def eligibility(row):
    doc = json.loads(row['document_json']) if 'document_json' in row else row
    if doc.get('provenance_class') in ('player_authored', 'canon_authored') or row.get('provenance_class') in ('player_authored', 'canon_authored'):
        return 'protected'
    if row.get('active', 1) != 1 or row.get('lifecycle', 'active') != 'active':
        return 'protected'
    status = doc.get('writer_status', 'pending')
    if status in ('ready', 'stale'):
        return 'existing'
    if status not in ('pending', 'unconfigured'):
        return 'attention'
    return 'pending'


def setup(store, form):
    return {'shared': ws.active(store, 'shared') or ws.defaults('shared'),
            'specific': ws.active(store, form) or ws.defaults(form),
            'retrieval_revision': writing_rag.corpus(store)[3], 'model': writer.MODEL,
            'effort': writer.DEFAULT_REASONING_EFFORT, 'contract_revision': writer.FORMATTING_REVISION}


def plan(store, form):
    ws.scope_name(form)
    if form == 'shared':
        raise ValueError('Choose a prose category')
    items, counts = [], {'existing': 0, 'protected': 0, 'attention': 0}
    uncertain = {e['key'] for r in home_all(store) for e in r['results'] if e['status'] in ('generating', 'generated', 'error')}
    import category_production
    uncertain.update(i['key'] for i in category_production.all_items(store) if i['status']!='published')
    for source in ws.catalog(store):
        if source['form'] != form or source['key'].startswith('comparison:'):
            continue
        row = record(store, source['key'])
        state = eligibility(row)
        if state == 'pending' and source['key'] in uncertain:
            state = 'attention'
        if state != 'pending':
            counts[state] += 1
            continue
        sample = ws.sample(store, source['key'])
        items.append({'key': source['key'], 'label': source['label'], 'source_hash': hashed(row),
                      'packet_hash': hashed(sample['packet'])})
    if form=='place_ambient':
        for row in store.db.execute("SELECT * FROM territories t WHERE active=1 AND NOT EXISTS(SELECT 1 FROM narrative_entries n WHERE n.scope_type='territory' AND n.scope_key=cast(t.id AS TEXT) AND n.active=1 AND n.provenance_class='connective_fiction') ORDER BY id"):
            key='scene:'+str(row['id']);seed=record(store,key)
            items.append({'key':key,'label':row['territory']+' · '+str(row['gang_name'] or 'Unknown holder')+' · local scene',
                          'source_hash':hashed(seed),'packet_hash':hashed(seed['territory'])})
    return {'form': form, 'items': items, 'counts': counts, 'setup': setup(store, form)}


def get(store, run_id):
    value = store.get_state(PREFIX + str(run_id))
    if not value:
        raise ValueError('Population run not found')
    return json.loads(value)


def save(store, run):
    prior = store.get_state(PREFIX + run['run_id'])
    if prior and json.loads(prior).get('stop_requested'):
        run['stop_requested'] = True
    run['updated_at'] = ws.now()
    # Preserve a concurrent owner stop atomically across worker connections.
    store.db.execute('''INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=
        CASE WHEN json_extract(system_state.value,'$.stop_requested')=1
        THEN json_set(excluded.value,'$.stop_requested',json('true')) ELSE excluded.value END''',
        (PREFIX+run['run_id'],ws.packed(run)))
    store.db.commit()


def public(run):
    result = {k: v for k, v in run.items() if k not in ('plan', 'request_hash')}
    result['results'] = [{k: v for k, v in entry.items() if k != 'before'} for entry in run['results']]
    return result


def home(store):
    runs = [json.loads(r[0]) for r in store.db.execute("SELECT value FROM system_state WHERE key LIKE 'category-population:%'")]
    return {'runs': [public(r) for r in sorted(runs, key=lambda r: r['created_at'], reverse=True)[:20]],
            'max_calls': writer.MAX_CALLS}


def preview(store, body):
    planned = plan(store, body.get('form'))
    return {**planned, 'fingerprint': hashed(planned), 'max_calls': writer.MAX_CALLS,
            'configured': bool(writer.API_KEY)}


def existing(store, body):
    key = body.get('request_key')
    if not isinstance(key, str) or not 8 <= len(key) <= 100:
        raise ValueError('A population request key is required')
    for run in home_all(store):
        if run.get('request_key') == key:
            if run['request_hash'] != hashed(body):
                raise ValueError('This request key belongs to different population settings')
            return run


def home_all(store):
    return [json.loads(r[0]) for r in store.db.execute("SELECT value FROM system_state WHERE key LIKE 'category-population:%'")]


def queue(store, body):
    previous = existing(store, body)
    if previous:
        return previous, False
    if any(r['status'] in ('queued', 'running') for r in home_all(store)):
        raise ValueError('A category population run is already active')
    limit = body.get('call_limit')
    if type(limit) is not int or not 1 <= limit <= writer.MAX_CALLS:
        raise ValueError('Choose a valid maximum number of writing calls')
    planned = plan(store, body.get('form'))
    if body.get('fingerprint') != hashed(planned):
        raise ValueError('The category, context or guidelines changed. Preview the category again before spending.')
    if not planned['items']:
        raise ValueError('There are no pending records in this category')
    if not writer.API_KEY:
        raise ValueError('JuniorWriter is not configured; no calls were made')
    # A review or technical operation must finish before production uses its setup.
    if store.db.execute("SELECT 1 FROM codex_review_jobs WHERE status IN ('queued','claimed','reviewing')").fetchone():
        raise ValueError('Finish the current review or investigation before populating a category')
    run = {'run_id': 'populate-' + uuid.uuid4().hex, 'request_key': body['request_key'],
           'request_hash': hashed(body), 'form': planned['form'], 'status': 'queued',
           'call_limit': limit, 'plan': planned, 'created_at': ws.now(), 'results': [],
           'target_count': min(limit, len(planned['items'])), 'remaining_count': max(0, len(planned['items']) - limit),
           'message': 'Population authorized. Existing writing will be preserved.', 'usage': {}}
    # Virtual scene slots are preview-only until this explicit one-off authorization.
    with store.db:
        for item in planned['items'][:run['target_count']]:
            if item['key'].startswith('scene:'):
                from world_streams import scene_record
                entry_id=scene_record(store,int(item['key'].partition(':')[2]))
                item['key']='entry:'+entry_id
                item['source_hash']=hashed(record(store,item['key']))
                item['packet_hash']=hashed(ws.sample(store,item['key'])['packet'])
    save(store, run)
    return run, True


def stop(store, run_id):
    run = get(store, run_id)
    if run['status'] in ('queued', 'running'):
        run['stop_requested'] = True
        save(store, run)
    return public(run)


def recover(store):
    for run in home_all(store):
        if run['status'] in ('queued', 'running'):
            run.update(status='interrupted', message='The server restarted. Saved results are retained; an uncertain request is never replayed.')
            save(store, run)


def publish(store, key, before, document, paragraphs):
    """Replace only an unchanged pending derived record; retain the old document in the run audit."""
    if record(store, key) != before or eligibility(before) != 'pending':
        raise ValueError('The target changed during generation. The paid output is retained in the run; it was not published.')
    kind, _, ident = key.partition(':')
    text = '\n\n'.join(writer.paragraph_text(p) for p in paragraphs)
    if kind == 'artifact':
        aid = uuid.uuid4().hex
        store.db.execute('UPDATE story_artifacts SET active=0 WHERE artifact_id=?', (ident,))
        store.db.execute('INSERT INTO story_artifacts VALUES(?,?,?,?,?,?,?,1)',
                         (aid, before['scope_type'], before['scope_key'], ws.packed(document), hashed(document), before['generation_version'], ws.now()))
        from story_engine import _link
        for evidence in store.db.execute('SELECT event_id,source_id FROM narrative_evidence WHERE artifact_type=? AND artifact_key=?', (before['scope_type'], ident)).fetchall():
            _link(store, before['scope_type'], aid, event_id=evidence['event_id'], source_id=evidence['source_id'])
    elif kind == 'entry':
        store.db.execute('UPDATE narrative_entries SET document_json=? WHERE entry_id=?', (ws.packed(document), ident))
    elif kind == 'memory':
        store.db.execute("UPDATE story_memories SET content=?,writer_status='ready' WHERE memory_id=?", (text, ident))
    else:
        store.db.execute("UPDATE fighter_thoughts SET content=?,writer_status='ready' WHERE thought_id=?", (text, ident))


def execute(store, run_id):
    run = get(store, run_id)
    if run['status'] != 'queued':
        return public(run)
    old_enabled = writer.WRITER_ENABLED
    writer.reset_budget(run['call_limit'], run_id)
    writer.set_enabled(True)
    run['status'] = 'running'
    save(store, run)
    try:
        for item in run['plan']['items'][:run['target_count']]:
            # Read the owner stop decision from a fresh committed connection between calls.
            with store.reader() as view:
                stopped = get(view, run_id).get('stop_requested')
            if stopped:
                run.update(status='stopped', message='Stopped. Completed entries are saved; no further requests will start.')
                break
            if setup(store, run['form']) != run['plan']['setup']:
                raise ValueError('Guidelines or retrieval context changed. Preview a new run before continuing.')
            before = record(store, item['key'])
            if hashed(before) != item['source_hash'] or eligibility(before) != 'pending':
                raise ValueError('A planned source record changed. No further calls will start; preview again.')
            selected = ws.sample(store, item['key'])
            entry = {'key': item['key'], 'label': item['label'], 'status': 'generating', 'started_at': ws.now(), 'before': before}
            run['results'].append(entry)
            run['message'] = 'Writing ' + item['label']
            save(store, run)  # Durable reservation before any provider request.
            contract = ws.compose(run['form'], run['plan']['setup']['shared'], run['plan']['setup']['specific'])
            paragraphs, status = writer.write(store, run['form'], selected['packet'],
                {'subject_type': 'category_population', 'subject_key': item['key'], 'subject_name': item['label']}, contract_override=contract)
            document = writer.apply(selected['document'], paragraphs, status)
            store.db.commit()  # Provider audit survives a later publication conflict.
            entry.update(document=document, finished_at=ws.now(), status='generated' if status['status'] == 'ready' else 'error')
            run['usage'] = writer.run_summary()
            save(store, run)  # Retain paid output even if the target changed.
            if entry['status'] != 'generated':
                raise RuntimeError(status.get('message', 'Generation did not produce valid prose. No automatic retry.'))
            with store._lock, store.db:
                publish(store, item['key'], before, document, paragraphs)
            entry['status'] = 'ready'
            save(store, run)
        else:
            run.update(status='completed', message='Population complete. Existing prose and authored sources were preserved.')
    except Exception as exc:
        store.db.commit()  # Preserve provider audit/cache even if publication failed.
        run.update(status='needs_attention', message=str(exc)[:600])
    finally:
        writer.set_enabled(old_enabled)
        run['usage'] = writer.run_summary()
        run['finished_at'] = ws.now()
        # Do not erase a stop flag received during the final in-flight request.
        with store.reader() as view:
            if get(view, run_id).get('stop_requested'):
                run['stop_requested'] = True
        save(store, run)
    return public(run)
