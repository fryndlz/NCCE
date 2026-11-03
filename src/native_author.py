"""Bounded direct Codex authorship. No provider calls, queue jobs or policy activation."""
import copy
import json
import uuid
import writer_workshop as ws
import writer_contract as contract
import writing_rag as rag
import category_population as pop

PREFIX = 'native-author:'
ORDER = ['fighter_biography', 'gang_origin', 'territory_origin', 'fighter_memory',
         'gang_event', 'place_event', 'battle_report', 'place_ambient', 'fighter_reflection',
         'relationship', 'gang_history', 'territory_history', 'region_history', 'fighter_mind', 'downtime']


def get(store, key):
    if not isinstance(key, str) or not key.startswith(('batch-', 'draft-')) or len(key)>100:
        raise ValueError('Use a native batch or draft identity')
    raw = store.get_state(PREFIX + key)
    if not raw:
        raise ValueError('Native writing record not found')
    return json.loads(raw)


def put(store, key, value):
    store.db.execute('INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                     (PREFIX + key, ws.packed(value)))


def request_id(body):
    key = body.get('request_key')
    if not isinstance(key, str) or not 16 <= len(key) <= 100:
        raise ValueError('Use a stable request key of 16–100 characters')
    return key


def source_record(store, key):
    if isinstance(key, str) and key.startswith('gang-origin:'):
        gid = key.partition(':')[2]
        row = store.db.execute('SELECT * FROM gangs WHERE gang_id=? AND active=1', (gid,)).fetchone()
        if not row:
            raise ValueError('Gang no longer exists')
        gang = dict(row)
        if gang.get('backstory_source') == 'player-authored / campaign Sheet' and gang.get('backstory'):
            raise ValueError('Authored gang background is protected')
        if store.db.execute("SELECT 1 FROM story_artifacts WHERE scope_type='gang_origin' AND scope_key=? AND active=1", (gid,)).fetchone():
            raise ValueError('A gang origin now exists; select its real record')
        return {'gang': gang, 'active': 1, 'writer_status': 'pending', 'provenance_class': 'inference'}
    return pop.record(store, key)


def gang_origin_sample(store, key):
    import narrative_context as context
    import writing_director as director
    gang = source_record(store, key)['gang']
    gid = gang['gang_id']
    document = director.direct_document('gang_origin', key, {'title': gang['name'], 'provenance_class': 'inference',
        'source_event_ids': [], 'evidence': ['Faction: ' + str(gang.get('gang_type') or 'unknown')]}, {'baseline': True})
    packet = context.document_packet(store, 'gang_origin', gid, document)
    packet['roster_context'] = [{'name': r['name'], 'type': r['type'], 'class': r['class']} for r in
                               store.db.execute('SELECT name,type,class FROM fighters WHERE gang_id=? AND listed_in_source=1', (gid,))]
    return {'key': key, 'form': 'gang_origin', 'label': gang['name'] + ' · origin', 'packet': packet, 'document': document, 'at': None}


def scene_sample(store, key):
    import narrative_context as context
    import writing_director as director
    row = pop.record(store, key)['territory']
    if store.db.execute("SELECT 1 FROM narrative_entries WHERE scope_type='territory' AND scope_key=? AND active=1 AND provenance_class='connective_fiction'", (str(row['id']),)).fetchone():
        raise ValueError('A scene already exists; inspect the real scene record')
    entity = context.entity_context(store, 'territory', str(row['id']))
    document = director.direct_document('place_ambient', key, {'title': row['territory'] + ' · local scene',
        'provenance_class': 'connective_fiction', 'evidence': ['Invented scene; no mechanical campaign effects.']}, {})
    packet = {'subject': row['territory'], 'subject_context': entity,
              'fiction_boundary': 'Invent one local scene, not a campaign fact. No tabletop consequences.', 'source_event_ids': []}
    return {'key': key, 'form': 'place_ambient', 'label': document['title'], 'packet': packet, 'document': document, 'at': None}


def sample(store, key):
    if not isinstance(key, str) or len(key) > 160 or key.startswith('comparison:'):
        raise ValueError('Select an actual campaign record, not a comparison')
    if key.startswith('gang-origin:'):
        return gang_origin_sample(store, key)
    return scene_sample(store, key) if key.startswith('scene:') else ws.sample(store, key)


def catalog(store):
    items = []
    for source in ws.catalog(store):
        if source['key'].startswith('comparison:'):
            continue
        before = pop.record(store, source['key'])
        state = pop.eligibility(before)
        doc = json.loads(before.get('document_json') or '{}')
        items.append({**source, 'state': state, 'at': before.get('occurred_at') or before.get('observed_at') or doc.get('occurred_at'), 'subject_scope':
                      str(before.get('scope_key') or before.get('fighter_id') or '')})
    for row in store.db.execute("SELECT id,territory FROM territories t WHERE active=1 AND NOT EXISTS(SELECT 1 FROM narrative_entries n WHERE n.scope_type='territory' AND n.scope_key=cast(t.id AS TEXT) AND n.active=1 AND n.provenance_class='connective_fiction') ORDER BY id"):
        items.append({'key': 'scene:' + str(row['id']), 'form': 'place_ambient', 'label': row['territory'] + ' · local scene',
                      'state': 'pending', 'at': None, 'subject_scope': str(row['id'])})
    for row in store.db.execute("SELECT * FROM gangs g WHERE active=1 AND NOT EXISTS(SELECT 1 FROM story_artifacts a WHERE a.scope_type='gang_origin' AND a.scope_key=g.gang_id AND a.active=1)"):
        if row['backstory_source']=='player-authored / campaign Sheet' and row['backstory']:
            continue
        items.append({'key':'gang-origin:'+row['gang_id'], 'form':'gang_origin', 'label':row['name']+' · origin',
                      'state':'pending', 'at':None, 'subject_scope':row['gang_id']})
    items.sort(key=lambda x: (ORDER.index(x['form']), x.get('at') or '', x['key']))
    return {'forms': [{'form': f, 'brief': contract.BRIEFS[f]} for f in ORDER], 'subjects': items,
            'notice': 'Dependency tiers then recorded time (unknown times remain unknown). Drafts do not become campaign facts.'}


def context(store, key):
    selected = sample(store, key)
    before = source_record(store, key)
    if pop.eligibility(before) == 'protected':
        raise ValueError('Authored, inactive or canonical records are protected')
    form = selected['form']
    shared, specific = ws.active(store, 'shared') or ws.defaults('shared'), ws.active(store, form) or ws.defaults(form)
    from editorial_sync import standards
    import territory_reference
    import writer_planning as planning
    packet = dict(selected['packet'])
    reference = territory_reference.for_packet(form, packet)
    if reference:
        packet['rulebook_context'] = reference
    packet['editorial_pattern_warnings'] = {
        'boundary': 'Other-subject editorial avoidance hints only, never world history or details to copy.',
        'patterns': planning.recent(store, packet.get('subject') or key, planning.family_of(form))}
    packet['retrieval'] = rag.retrieve(store, form, packet)
    value = {'key': key, 'form': form, 'label': selected['label'], 'packet': packet,
             'document': selected['document'], 'source_hash': pop.hashed(before),
             'instructions': ws.compose(form, shared, specific), 'retrieval_revision': rag.corpus(store)[3],
             'active_revisions': {'shared': shared['revision_id'], form: specific['revision_id']},
             'reviewer_standards': standards(store, form), 'before': before}
    value['context_hash'] = pop.hashed(value)
    return value


def public_context(value):
    return {k: v for k, v in value.items() if k != 'before'}


def start(store, body):
    rid = request_id(body)
    batch_id = 'batch-' + pop.hashed(rid)[:32]
    fingerprint = pop.hashed({k: v for k, v in body.items() if k not in ('worker_id', 'thread_id')})
    old = store.get_state(PREFIX + batch_id)
    if old:
        value = json.loads(old)
        if value['request_hash'] != fingerprint:
            raise ValueError('Request key belongs to another batch')
        return value
    forms = body.get('forms', ORDER)
    if not isinstance(forms, list) or not forms or any(f not in ORDER for f in forms):
        raise ValueError('Choose actual NCCE prose categories')
    limit = body.get('max_drafts')
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('Choose a nonrenewing maximum of 1–200 native drafts, including revisions')
    mode = body.get('mode', 'missing')
    if mode not in ('missing', 'replace_generated'):
        raise ValueError('Choose missing or explicitly authorized replace_generated')
    keys = body.get('keys')
    if keys is not None and (not isinstance(keys, list) or len(keys) > 1000 or any(not isinstance(k, str) for k in keys)):
        raise ValueError('Invalid selected record keys')
    rows = [r for r in catalog(store)['subjects'] if r['form'] in forms and
            r['state'] in (('pending',) if mode == 'missing' else ('pending', 'existing')) and (keys is None or r['key'] in keys)]
    if keys is not None and set(keys) != {r['key'] for r in rows}:
        raise ValueError('A selected record is protected, unavailable or outside this batch mode')
    value = {'batch_id': batch_id, 'request_hash': fingerprint, 'created_at': ws.now(), 'forms': forms,
             'mode': mode, 'max_drafts': limit, 'targets': rows, 'attempts': [], 'status': 'open', 'writer': 'native-codex'}
    with store.db:
        put(store, batch_id, value)
    return value


def prepare(store, body):
    batch = get(store, body.get('batch_id', ''))
    if batch['status'] != 'open':
        raise ValueError('This native batch is stopped')
    rid = request_id(body)
    for attempt in batch['attempts']:
        if attempt['request_key'] == rid:
            if body.get('key') and body['key'] != attempt['key']:
                raise ValueError('Request key belongs to a different target')
            return get(store, attempt['draft_id'])
    unfinished = next((a for a in batch['attempts'] if a['status'] == 'reserved'), None)
    if unfinished:
        raise ValueError('An attempt is already reserved. Inspect its saved packet; do not silently regenerate after uncertainty.')
    if len(batch['attempts']) >= batch['max_drafts']:
        raise ValueError('Native batch draft allowance exhausted; saved work is retained')
    key = body.get('key')
    if not key:
        done = {a['key'] for a in batch['attempts']}
        key = next((r['key'] for r in batch['targets'] if r['key'] not in done), None)
    if key not in {r['key'] for r in batch['targets']}:
        raise ValueError('No selected unfinished target; choose a new bounded batch')
    count = sum(a['key'] == key for a in batch['attempts'])
    if count >= 5:
        raise ValueError('Five total attempts already reserved for this entry; retain the best valid candidate')
    prepared = context(store, key)
    state = pop.eligibility(prepared['before'])
    if state not in (('pending',) if batch['mode'] == 'missing' else ('pending', 'existing')):
        raise ValueError('Target is no longer eligible for this batch')
    draft_id = 'draft-' + uuid.uuid4().hex
    value = {'draft_id': draft_id, 'batch_id': batch['batch_id'], 'key': key, 'form': prepared['form'],
             'request_key': rid, 'status': 'reserved', 'attempt': count + 1, 'reserved_at': ws.now(), 'context': prepared}
    batch['attempts'].append({k: value[k] for k in ('draft_id', 'key', 'request_key', 'status', 'attempt')})
    with store.db:
        put(store, draft_id, value)
        put(store, batch['batch_id'], batch)
    return value


def save_draft(store, body):
    value = get(store, body.get('draft_id', ''))
    output = body.get('output')
    checks = body.get('checks')
    if not isinstance(checks, dict) or set(checks) != {'source_fidelity', 'chronology', 'viewpoint', 'repetition', 'uncertainty'} or any(not isinstance(v, str) or len(v) > 1500 for v in checks.values()):
        raise ValueError('Supply concise source_fidelity, chronology, viewpoint, repetition and uncertainty check notes')
    fingerprint = pop.hashed({'output': output, 'checks': checks})
    if value['status'] != 'reserved':
        if value.get('output_hash') != fingerprint:
            raise ValueError('Draft already saved; reserve a new attempt to revise it')
        return value
    import llm_writer as writer
    try:
        paragraphs, composition = writer.normalize_result(output)
        writer.validate_diegetic_prose(value['form'], paragraphs)
        if composition.get('closing'):
            writer.validate_diegetic_prose(value['form'], [composition['closing']])
    except RuntimeError as exc:
        raise ValueError(str(exc)) from None
    if value['form'] in contract.PERSONAL and composition:
        raise ValueError('Personal prose does not use a documentary composition')
    # Apply only to the server-supplied shell: clients cannot inject evidence or provenance.
    document = writer.apply(copy.deepcopy(value['context']['document']), paragraphs,
                            {'status': 'ready', 'revision': 'native-codex-v1', 'composition': composition})
    document['writer_model'] = 'native-codex'
    document['native_author'] = {'draft_id': value['draft_id'], 'batch_id': value['batch_id'],
                                 'context_hash': value['context']['context_hash'], 'independently_reviewed': False}
    value.update(status='draft', output=output, paragraphs=paragraphs, document=document, checks=checks,
                 output_hash=fingerprint, saved_at=ws.now())
    value['publish_hash'] = pop.hashed({'draft_id': value['draft_id'], 'output_hash': fingerprint,
                                      'context_hash': value['context']['context_hash']})
    batch = get(store, value['batch_id'])
    next(a for a in batch['attempts'] if a['draft_id'] == value['draft_id'])['status'] = 'draft'
    with store.db:
        put(store, value['draft_id'], value)
        put(store, batch['batch_id'], batch)
    return value


def publish(store, body):
    value = get(store, body.get('draft_id', ''))
    if body.get('confirm_publish') != value.get('publish_hash') or not value.get('publish_hash'):
        raise ValueError('Confirm the exact saved draft publish_hash after owner approval')
    if value['status'] == 'published':
        return value
    if value['status'] != 'draft':
        raise ValueError('Save a checked draft before publishing')
    if context(store, value['key'])['context_hash'] != value['context']['context_hash']:
        raise ValueError('Sources, continuity or guidelines changed; draft retained. Prepare a fresh attempt before publication.')
    batch = get(store, value['batch_id'])
    before = value['context']['before']
    document = copy.deepcopy(value['document'])
    with store.db:
        key = value['key']
        if key.startswith('gang-origin:'):
            from story_engine import GENERATION
            gid = before['gang']['gang_id']
            aid = uuid.uuid4().hex
            document.update(generated_at=ws.now(), generation_version=GENERATION)
            store.db.execute('INSERT INTO story_artifacts VALUES(?,?,?,?,?,?,?,1)',
                             (aid, 'gang_origin', gid, ws.packed(document), pop.hashed(document), GENERATION, ws.now()))
            key = 'artifact:' + aid
        if key.startswith('scene:'):
            from world_streams import scene_record
            key = 'entry:' + scene_record(store, int(key.split(':')[1]), token='native-' + value['draft_id'])
            before = pop.record(store, key)
            # Keep the real server-created provenance/evidence shell.
            shell = ws.sample(store, key)['document']
            import llm_writer as writer
            document = writer.apply(shell, value['paragraphs'], {'status': 'ready', 'revision': 'native-codex-v1',
                                    'composition': value['document'].get('composition', {})})
            document['writer_model'] = 'native-codex'
            document['native_author'] = value['document']['native_author']
        if not value['key'].startswith('gang-origin:'):
            pop.publish(store, key, before, document, value['paragraphs'], allow_existing=batch['mode'] == 'replace_generated')
        value.update(status='published', published_at=ws.now(), published_key=key, published_document=document)
        next(a for a in batch['attempts'] if a['draft_id'] == value['draft_id'])['status'] = 'published'
        put(store, value['draft_id'], value)
        put(store, batch['batch_id'], batch)
    return value


def dispatch(store, action, body):
    from codex_review_queue import thread_id
    if body.get('thread_id') != thread_id():
        raise ValueError('Native author access is scoped to the configured JKSimmons chat')
    if action == 'catalog':
        return catalog(store)
    if action == 'context':
        return public_context(context(store, body.get('key')))
    if action == 'start':
        return start(store, body)
    if action == 'prepare':
        return prepare(store, body)
    if action == 'save':
        return save_draft(store, body)
    if action == 'publish':
        return publish(store, body)
    if action == 'abandon':
        value = get(store, body.get('draft_id', ''))
        reason = body.get('reason')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 600:
            raise ValueError('Give a concise reason for closing this attempt; its allowance is not refunded')
        if value.get('status') != 'reserved':
            raise ValueError('Only an unresolved reservation may be abandoned; saved drafts remain immutable')
        value.update(status='abandoned', reason=reason.strip(), finished_at=ws.now())
        batch = get(store, value['batch_id'])
        next(a for a in batch['attempts'] if a['draft_id'] == value['draft_id'])['status'] = 'abandoned'
        with store.db:
            put(store, value['draft_id'], value)
            put(store, batch['batch_id'], batch)
        return value
    if action == 'status':
        return get(store, body.get('id', ''))
    if action == 'batches':
        return {'batches': [json.loads(r[0]) for r in store.db.execute("SELECT value FROM system_state WHERE substr(key,1,?)=? ORDER BY rowid DESC LIMIT 30", (len(PREFIX + 'batch-'), PREFIX + 'batch-'))]}
    if action == 'stop':
        batch = get(store, body.get('batch_id', ''))
        if 'attempts' not in batch or batch.get('batch_id') != body.get('batch_id'):
            raise ValueError('Select a native batch to stop')
        batch.update(status='stopped', stopped_at=ws.now())
        with store.db:
            put(store, batch['batch_id'], batch)
        return batch
    raise ValueError('Unknown native author operation')
