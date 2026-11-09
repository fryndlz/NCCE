"""Private, bounded exchange with an external writing chat. Never calls a model.

Requests are server-sealed logical slots. The Sheet is a delivery surface, not
authority over routing, facts, memory salience or event-clock progression.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
from uuid import uuid4

from writing_exchange import digest, packed, _backup
from narrative_context import document_packet

ROOT=Path(__file__).resolve().parents[1]
HEADERS=('request_id,status,form,entity_type,entity_key,entry_key,title,context_id,'
         'source_revision,event_at_utc,imperial_date,writer_text_md,writer_note,'
         'completed_at_utc,imported_at_utc,import_receipt').split(',')
ARTIFACT_FORMS={'fighter_biography','gang_history','territory_origin','territory_history',
                'battle_report','downtime','region_history','relationship'}
ROLLING_FORMS={'gang_history','territory_history','downtime','region_history','relationship'}


def now():return datetime.now(timezone.utc).isoformat()


def enabled():return len(os.environ.get('NCCE_EXCHANGE_TOKEN',''))>=32


def authenticated(header):
    token=os.environ.get('NCCE_EXCHANGE_TOKEN','')
    return enabled() and hmac.compare_digest(header or '', 'Bearer '+token)


def load(value):return json.loads(value or '{}')


def body(doc):
    from prose_progress import _body
    return _body(doc)


def authored(doc):return doc.get('provenance_class') in ('player_authored','canon_authored')


def clean_context(value):
    """Drop volatile presentation and generated wording from the source seal."""
    if isinstance(value,list):return [clean_context(v) for v in value]
    if not isinstance(value,dict):return value
    skip={'generated_at','generation_version','date_display','writer_status','writer_message',
          'writer_model','event_clock','selection_score','score_details','previous_entry_ids',
          'earlier_stories','baseline','generated_background','source_memory_id'}
    return {k:clean_context(v) for k,v in value.items() if k not in skip}


def candidates(store):
    """Existing slots only. Authored material is never eligible for replacement."""
    result=[]
    def add(kind,key,form,entity,subject,title,facts,context,at,ready,**extra):
        if entity=='territory':
            from territory_history import history_for, ORIGIN_EXCEPTION
            confirmed=history_for(store,subject)
            if confirmed:
                facts={**facts,'confirmed_territory_history':confirmed}
                if form=='territory_origin':context={**context,'origin_history_exception':ORIGIN_EXCEPTION}
        if entity=='fighter':
            from narrative_context import authored as background
            f=store.db.execute('SELECT * FROM fighters WHERE id=?',(subject,)).fetchone()
            if not f:return
            fighter=dict(f)
            canon=load(fighter.get('mechanics_json')).get('Backstory') or background(fighter)
            context={**context,'authored_background':canon,'subject_name':fighter['name']}
        result.append(dict(kind=kind,key=key,form=form,entity_type=entity,entity_key=str(subject),
                           title=title,facts=facts,context=context,event_at_utc=at or '',
                           ready=ready,**extra))
    for row in store.db.execute('SELECT * FROM story_artifacts WHERE active=1 ORDER BY scope_type,scope_key'):
        r=dict(row); form=r['scope_type'];doc=load(r['document_json'])
        if form not in ARTIFACT_FORMS or authored(doc):continue
        key=r['scope_key'];entity='fighter' if form=='fighter_biography' else 'territory' if form.startswith('territory_') else 'battle' if form=='battle_report' else 'gang' if form in ('gang_history','downtime') else 'campaign'
        subject={}
        if entity in ('fighter','territory','battle','gang'):
            table,field={'fighter':('fighters','id'),'territory':('territories','id'),'battle':('battles','id'),'gang':('gangs','gang_id')}[entity]
            found=store.db.execute(f'SELECT * FROM {table} WHERE {field}=?',(key,)).fetchone()
            if not found:continue
            subject=dict(found)
            if subject.get('active')==0:continue
            if form=='fighter_biography':
                from narrative_context import authored as background
                if background(subject) or load(subject.get('mechanics_json')).get('Backstory'):continue
            if form=='battle_report':
                from authored_battles import has_report
                from campaign_authored import document
                if has_report(subject) or document(subject):continue
            # Source projections only; generated summaries/timestamps are not facts.
            subject={k:v for k,v in subject.items() if k not in ('id','chronicle','backstory','backstory_source','updated_at','created_at','snapshot_id')}
        add('artifact',[form,key],form,entity,key,doc.get('title',form),
            {'evidence':doc.get('evidence',[]),'source_event_ids':doc.get('source_event_ids',[]),'subject':subject},
            document_packet(store,form,key,doc),doc.get('date_display',{}).get('sourceTimestamp'),
            doc.get('writer_status')=='ready' and bool(body(doc)),has_prose=bool(body(doc)))
    for row in store.db.execute('SELECT * FROM story_memories WHERE active=1 ORDER BY fighter_id,coalesce(occurred_at,observed_at),memory_key'):
        r=dict(row)
        if r['provenance_class'] in ('player_authored','canon_authored'):continue
        form='fighter_reflection' if r['memory_type']=='reflection' else 'fighter_memory'
        add('memory',[r['fighter_id'],r['memory_key']],form,'fighter',r['fighter_id'],r['title'],
            {k:load(r[k]) for k in ('evidence_json','source_event_ids_json','source_observation_ids_json','tags_json')},
            load(r['writer_context_json']),r['occurred_at'] or r['observed_at'],r['writer_status']=='ready' and bool(r['content'].strip()),has_prose=bool(r['content'].strip()))
    for row in store.db.execute("SELECT * FROM fighter_thoughts WHERE lifecycle='active' ORDER BY fighter_id,thought_id"):
        r=dict(row)
        add('thought',[r['thought_id']],'fighter_mind','fighter',r['fighter_id'],r['label'],load(r['source_json']),
            load(r['packet_json']),'',r['writer_status']=='ready' and bool(r['content'].strip()),has_prose=bool(r['content'].strip()))
    for row in store.db.execute('SELECT * FROM narrative_entries WHERE active=1 ORDER BY scope_type,scope_key,coalesce(occurred_at,observed_at),entry_key'):
        r=dict(row);doc=load(r['document_json'])
        if authored(doc):continue
        form='gang_event' if r['scope_type']=='gang' else 'place_ambient' if r['provenance_class']=='connective_fiction' else 'place_event'
        add('entry',[r['scope_type'],r['scope_key'],r['entry_key']],form,r['scope_type'],r['scope_key'],doc.get('title',r['title']),
            {'evidence':doc.get('evidence',[]),'source_event_ids':doc.get('source_event_ids',[]),'provenance':r['provenance_class']},
            doc.get('writer_context',{}),r['occurred_at'] or r['observed_at'],doc.get('writer_status')=='ready' and bool(body(doc)),has_prose=bool(body(doc)))
    from writing_waterfall import classify
    return classify(store,result)


def target_key(c):return packed([c['kind'],c['key']])


def seal(c):return 'sha256:'+digest(clean_context({k:v for k,v in c.items() if k not in ('ready','approved','legacy','phase','has_prose')}))


def _packet(store,c,rid):
    from writing_director import format_date
    request=dict(request_id=rid,status='PENDING',form=c['form'],entity_type=c['entity_type'],
                 entity_key=c['entity_key'],entry_key=target_key(c),title=c['title'],context_id='ctx:'+rid,
                 source_revision=seal(c),event_at_utc=c['event_at_utc'],imperial_date='')
    if c['event_at_utc']:
        request['imperial_date']=format_date(c['event_at_utc']).get('imperialDisplay','')
    context=[dict(section='mechanics',provenance='mechanical_fact',source_ref='NCCE sealed derived slot',
                  event_at_utc=c['event_at_utc'],source_event_ids='',text=packed({k:v for k,v in c['facts'].items() if k!='confirmed_territory_history'})),
             dict(section='character_context',provenance='inference',source_ref='NCCE source-separated writing context',
                  event_at_utc=c['event_at_utc'],source_event_ids='',text=packed({k:v for k,v in c['context'].items() if k!='authored_background'}))]
    # Voice is a separate, provenance-labelled writing lens, not mechanical evidence.
    # Only new sealed packets receive it; in-flight requests retain their frozen context.
    if c['entity_type']=='fighter' and c['form'] in ('fighter_biography','fighter_memory','fighter_reflection','fighter_mind'):
        from voice_layers import build_voice_layers
        # Some older/baseline writer contexts do not carry the roster's gang and
        # House names. Add identity-only fallback without copying current injury,
        # weapon, promotion or status into a past event's narrative context.
        profile_context=dict(c['context'])
        fighter_row=store.db.execute(
            'SELECT f.name AS fighter_name, f.gang_name AS host_name, '
            'g.name AS roster_gang, g.gang_type AS roster_faction '
            'FROM fighters f LEFT JOIN gangs g ON g.gang_id=f.gang_id '
            'WHERE f.id=?',(c['entity_key'],)).fetchone()
        if fighter_row:
            if not profile_context.get('subject_name'):
                profile_context['subject_name']=fighter_row['fighter_name']
            if not profile_context.get('gang'):
                profile_context['gang']=fighter_row['roster_gang'] or fighter_row['host_name']
            if not profile_context.get('affiliation') and not profile_context.get('faction'):
                profile_context['affiliation']=fighter_row['roster_faction']
        layers=build_voice_layers(profile_context)
        context.append(dict(section='voice_layers',provenance='style_guidance',
            source_ref='NCCE validated versioned voice registry; editorial layer, never event evidence',
            event_at_utc='',source_event_ids='',text=packed(layers)))
    # Current Sheet/canon biography is a voice lens, never a replay of old events.
    confirmed=c['facts'].get('confirmed_territory_history',[]) if isinstance(c['facts'],dict) else []
    if confirmed:
        context.append(dict(section='confirmed_territory_history',provenance='player_authored',
            source_ref='Owner-confirmed history supplement; raw Sheet untouched',event_at_utc='',
            source_event_ids='',text=packed(confirmed)))
    if c['entity_type']=='fighter':
        text=c['context'].get('authored_background')
        if text:context.append(dict(section='authored_canon',provenance='player_authored',source_ref='fighter authored background; prior life only',event_at_utc='',source_event_ids='',text=text))
    event_ids=c['facts'].get('source_event_ids',c['facts'].get('source_event_ids_json',[])) if isinstance(c['facts'],dict) else []
    events=[]
    for key in event_ids:
        row=store.db.execute('SELECT event_id,event_type,occurred_at,observed_at,payload_json FROM campaign_events WHERE event_id=?',(key,)).fetchone()
        if row:
            event=dict(row);event['facts']=load(event.pop('payload_json'));events.append(event)
    events.sort(key=lambda e:(e['occurred_at'] or e['observed_at'] or '',e['event_id']))
    if events:context.append(dict(section='chronology',provenance='mechanical_fact',source_ref='cited factual event ledger only',event_at_utc='',source_event_ids=','.join(event_ids),text=packed(events)))
    context.append(dict(section='brief',provenance='instruction',source_ref='owner-approved exchange policy',event_at_utc='',source_event_ids='',text=
        'Write this one entry once, in the established style of this chat. Preserve the chronological boundary. '
        'Authored background supplies voice, not new events. Mechanics are evidence, not language to copy. '
        'Return complete Markdown; metadata/provenance and real-world dates stay outside diegesis. '
        'Do not create variants, reviewers or rerun a completed entry. READY means publish this text unchanged.'))
    return {'request':request,'context':context}


def source_matches(store,c,row):
    if row['policy_version']==1:
        return seal(c)==row['source_revision'] or semantic_seal(store,c)==semantic_seal(store,load(row['target_json'])['target'])
    from writing_waterfall import context
    items=candidates(store);deps={target_key(c):set(x['target_key'] for x in load(row['dependencies_json']))}
    references=context(store,c,deps,items)
    return revision(c,references,store)==row['source_revision']


def semantic_seal(store,c):
    value=deepcopy(c)
    if c['form'] in ROLLING_FORMS|{'fighter_biography','territory_origin'}:
        # These records have compilation times, not new campaign events.
        value['event_at_utc']=''
    def ref(key):
        row=store.db.execute('SELECT fighter_id,memory_key FROM story_memories WHERE memory_id=?',(key,)).fetchone()
        return [row['fighter_id'],row['memory_key']] if row else key
    def visit(v):
        if isinstance(v,list):return [visit(x) for x in v]
        if not isinstance(v,dict):return v
        return {k:[ref(x) for x in item] if k in ('source_observation_ids_json','source_memory_ids') and isinstance(item,list) else visit(item) for k,item in v.items()}
    return seal(visit(value))


def revision(c,references,store):
    return 'sha256:'+digest({'source':semantic_seal(store,c),'dependencies':[(r['target_key'],r['text_hash']) for r in references]})


def supplements(c,references):
    result=[dict(section='brief',provenance='instruction',source_ref='NCCE dependency waterfall v2',
        event_at_utc='',source_event_ids='',text='Queue phase: '+str(c['phase'])+'. '+
        'This is one replacement of an unapproved legacy/placeholder draft or a missing entry. '
        'Never copy the old generated wording. Use the accepted prerequisite prose below as fictional continuity, '
        'not mechanical proof; preserve the requested event date and this chat’s established voice.')]
    if references:result.append(dict(section='existing_fiction',provenance='inference',source_ref='accepted prerequisite entries',
        event_at_utc='',source_event_ids='',text=packed(references)))
    return result


def prepare(store,limit=5,client_states=()):
    """Export the earliest runnable phase, preserving claims, drafts and all IDs."""
    from writing_waterfall import plan,context,order,retire_legacy,VERSION
    limit=max(0,min(int(limit),5));created=[]
    with store._lock:
        if store.db.in_transaction:raise RuntimeError('Exchange preparation requires its own transaction')
        with store.db:
            available=candidates(store);lookup={target_key(c):c for c in available}
            retire_legacy(store,available)
            if client_states is not None:
                if not isinstance(client_states,list) and client_states!=():raise ValueError('Invalid queue-state snapshot')
                if len(client_states)>2000:raise ValueError('Queue-state snapshot too large')
                for entry in client_states:
                    if not isinstance(entry,dict) or entry.get('status') not in ('DRAFT','PENDING','WRITING','READY','IMPORTED','HOLD'):continue
                    store.db.execute('UPDATE writing_exchange_requests SET client_state=?,client_has_text=? WHERE request_id=?',
                        (entry['status'],int(bool(entry.get('has_text'))),str(entry.get('request_id',''))))
                    if entry['status']=='HOLD':
                        store.db.execute("UPDATE writing_exchange_requests SET state='HOLD',error=? WHERE request_id=? AND state IN ('PENDING','DEFERRED')",
                            ('Writer placed this request on HOLD; saved draft remains in the Sheet. '+str(entry.get('note',''))[:1000],str(entry.get('request_id',''))))
            from territory_history import amend_paused_origin
            amend_paused_origin(store,available)
            for row in store.db.execute("SELECT request_id,target_key,source_revision FROM writing_exchange_requests WHERE state='PENDING'").fetchall():
                c=lookup.get(row['target_key'])
                request=store.db.execute('SELECT * FROM writing_exchange_requests WHERE request_id=?',(row['request_id'],)).fetchone()
                if not c or not source_matches(store,c,request):
                    store.db.execute("UPDATE writing_exchange_requests SET state='HOLD',error='Source changed; do not write or regenerate this request' WHERE request_id=?",(row['request_id'],))
            requests=[dict(r) for r in store.db.execute('SELECT * FROM writing_exchange_requests ORDER BY created_at')]
            bytarget={}
            for r in requests:bytarget.setdefault(r['target_key'],[]).append(r)
            def in_progress(r):
                return r['state']=='PENDING' and (r['client_state'] in ('WRITING','READY') or r['client_has_text'] or (client_states is None and not r['client_state']))
            protected=[r for r in requests if in_progress(r)]
            protected_keys={r['target_key'] for r in protected}
            runnable,deps,blocked=plan(store,available)
            eligible=[]
            for c in runnable:
                rows=bytarget.get(target_key(c),[])
                if target_key(c) in protected_keys or any(r['state']=='HOLD' for r in rows):continue
                eligible.append(c)
            # An in-progress lower-phase draft may finish, but new work comes
            # only from the earliest runnable frontier.
            frontier=eligible[0]['phase'] if eligible else None
            selected=[c for c in eligible if c['phase']==frontier][:max(0,limit-len(protected))]
            selected_keys={target_key(c) for c in selected}|protected_keys
            if client_states is not None:
                for r in requests:
                    if r['state']=='PENDING' and r['target_key'] not in selected_keys and not in_progress(r):
                        store.db.execute("UPDATE writing_exchange_requests SET state='DEFERRED' WHERE request_id=?",(r['request_id'],))
            elif any(r['state']=='PENDING' for r in requests):
                return [] # Older relay cannot safely report claims; upgrade it first.
            for rank,c in enumerate(selected):
                key=target_key(c);references=context(store,c,deps,available)
                waiting=[r for r in bytarget.get(key,[]) if r['state'] in ('PENDING','DEFERRED')]
                if waiting:
                    r=waiting[0]
                    if not source_matches(store,c,r):continue
                    # Original source packet/revision remain immutable. Deferred
                    # v1 requests receive separately retained accepted continuity.
                    extra=load(r['supplement_json'])
                    if r['policy_version']==1 and not extra:extra=supplements(c,references)
                    store.db.execute("UPDATE writing_exchange_requests SET state='PENDING',queue_rank=?,supplement_json=? WHERE request_id=?",(rank,packed(extra),r['request_id']))
                    continue
                rid=str(uuid4());packet=_packet(store,c,rid)
                from writing_waterfall import scrub
                for block in packet['context']:
                    if block['section']=='character_context':block['text']=packed(scrub(load(block['text'])))
                packet['request']['source_revision']=revision(c,references,store)
                packet['context']+=supplements(c,references)
                store.db.execute("INSERT INTO writing_exchange_requests(request_id,target_key,packet_json,target_json,source_revision,state,created_at,policy_version,queue_rank,dependencies_json) VALUES(?,?,?,?,?,'PENDING',?,?,?,?)",
                    (rid,key,packed(packet),packed({'target':c,'original':projection(store,c)}),packet['request']['source_revision'],now(),VERSION,rank,packed(references)))
                created.append(rid)
    return created


def outbox(store):
    result=[]
    for r in store.db.execute("SELECT packet_json,supplement_json FROM writing_exchange_requests WHERE state='PENDING' ORDER BY queue_rank,created_at,request_id LIMIT 5"):
        packet=load(r['packet_json']);packet['context']+=load(r['supplement_json']);result.append(packet)
    return result


def projection(store,c):
    table,fields={'memory':('story_memories',['fighter_id','memory_key']),
                  'thought':('fighter_thoughts',['thought_id']),
                  'artifact':('story_artifacts',['scope_type','scope_key']),
                  'entry':('narrative_entries',['scope_type','scope_key','entry_key'])}[c['kind']]
    where=' AND '.join(f+'=?' for f in fields)+(" AND lifecycle='active'" if c['kind']=='thought' else ' AND active=1')
    rows=store.db.execute('SELECT * FROM '+table+' WHERE '+where,c['key']).fetchall()
    if len(rows)!=1:raise ValueError('Exact prose slot missing or ambiguous')
    return dict(rows[0])


def _write(store,c,text,rid):
    """Update derived prose only; original rows retained in the delivery audit."""
    if c['kind']=='memory':
        store.db.execute("UPDATE story_memories SET content=?,content_runs_json='[]',writer_status='ready' WHERE fighter_id=? AND memory_key=? AND active=1",(text,*c['key']))
    elif c['kind']=='thought':
        store.db.execute("UPDATE fighter_thoughts SET content=?,writer_status='ready' WHERE thought_id=? AND lifecycle='active'",(text,*c['key']))
    else:
        table,fields=('story_artifacts',['scope_type','scope_key']) if c['kind']=='artifact' else ('narrative_entries',['scope_type','scope_key','entry_key'])
        where=' AND '.join(f+'=?' for f in fields)+' AND active=1'
        rows=store.db.execute('SELECT document_json FROM '+table+' WHERE '+where,c['key']).fetchall()
        if len(rows)!=1:raise ValueError('Current document slot is missing or ambiguous')
        doc=load(rows[0][0]);doc.update(writer_status='ready',writer_message='',external_request_id=rid,
            external_markdown=text,blocks=[{'type':'body_paragraph','text':p} for p in text.split('\n\n') if p.strip()])
        # Wrapper composition belonged to the old draft; returned Markdown owns its
        # own diegetic headings. Evidence/source/date metadata remain untouched.
        doc.pop('composition',None)
        store.db.execute('UPDATE '+table+' SET document_json=? WHERE '+where,(packed(doc),*c['key']))


def deliver(store,payload):
    """READY grants publication, not authorship. Freeze output even on rejection."""
    if not isinstance(payload,dict):raise ValueError('Expected a delivery object')
    rid=payload.get('request_id','');text=payload.get('writer_text_md','')
    if not isinstance(rid,str) or not isinstance(text,str) or not text.strip() or len(text)>30000:
        raise ValueError('Request ID and complete text (1–30000 characters) required')
    if len(packed(payload))>100000:raise ValueError('Delivery too large')
    attempt=digest(payload);received=now()
    with store._lock:
        if store.db.in_transaction:raise RuntimeError('Delivery requires its own transaction')
        old=store.db.execute('SELECT disposition,error FROM writing_exchange_attempts WHERE attempt_hash=?',(attempt,)).fetchone()
        request=store.db.execute('SELECT * FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone()
        if old:
            return dict(status=old['disposition'],request_id=rid,error=old['error'],receipt=request['receipt'] if request else None,imported_at_utc=request['imported_at'] if request else None,reused=True)
        error='';current=None
        if not request:error='Unknown request; routing is owned by NCCE'
        elif request['state'] not in ('PENDING','DEFERRED'):error='Request is already imported or held; no replacement authorized'
        elif payload.get('source_revision')!=request['source_revision']:error='Source revision does not match'
        elif payload.get('status')!='READY':error='Only READY output can publish'
        else:
            found=[c for c in candidates(store) if target_key(c)==request['target_key']]
            if len(found)!=1 or not source_matches(store,found[0],request):error='Target or source changed; draft retained for reconciliation'
            elif found[0]['approved']:error='Slot already contains accepted external prose; draft retained'
            else:current=found[0]
        if not error:_backup(store,'automation')
        receipt='exchange:'+rid+':'+attempt[:16] if not error else None
        try:
            with store.db:
                if not error:
                    _write(store,current,text,rid)
                    store.db.execute("INSERT INTO system_state(key,value) VALUES('story_revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('exchange:'+attempt[:16],))
                    store.db.execute("UPDATE writing_exchange_requests SET state='IMPORTED',raw_markdown=?,writer_note=?,completed_at=?,imported_at=?,receipt=? WHERE request_id=?",
                        (text,str(payload.get('writer_note','')),str(payload.get('completed_at_utc','')),received,receipt,rid))
                elif request and request['state']=='PENDING':
                    store.db.execute("UPDATE writing_exchange_requests SET state='HOLD',raw_markdown=?,error=? WHERE request_id=?",(text,error,rid))
                store.db.execute('INSERT INTO writing_exchange_attempts VALUES(?,?,?,?,?,?)',(attempt,rid,packed(payload),received,'held' if error else 'imported',error))
        except Exception:
            # The caller retries the same saved output after a transient DB error;
            # no acknowledgement and no request for another generation is issued.
            raise
        return dict(status='held' if error else 'imported',request_id=rid,error=error,receipt=receipt,imported_at_utc=received if not error else None,reused=False)


def restore(store):
    """Reapply accepted wording after projection rebuild, only to unchanged causes."""
    with store._lock:
        available={target_key(c):c for c in candidates(store)}
        with store.db:
            for row in store.db.execute("SELECT * FROM writing_exchange_requests WHERE state='IMPORTED'").fetchall():
                c=available.get(row['target_key'])
                same=c and semantic_seal(store,c)==semantic_seal(store,load(row['target_json'])['target'])
                if same:
                    _write(store,c,row['raw_markdown'],row['request_id'])


def diagnostics(store):
    rows=[dict(r) for r in store.db.execute('SELECT request_id,state,created_at,imported_at,receipt,error FROM writing_exchange_requests ORDER BY created_at')]
    from writing_waterfall import summary
    return dict(enabled=enabled(),max_outstanding=5,requests=rows,waterfall=summary(store,candidates(store)),relay_last_seen=store.get_state('exchange_relay_last_seen'),
                policy='One entry once. READY publishes unchanged. Held drafts are retained; no automatic regeneration.')


def holds(store):
    return [dict(r) for r in store.db.execute("SELECT request_id,source_revision,error FROM writing_exchange_requests WHERE state='HOLD'")]


def deferred(store):
    return [dict(r) for r in store.db.execute("SELECT request_id,source_revision FROM writing_exchange_requests WHERE state='DEFERRED'")]


def guidance():
    return {name:(ROOT/path).read_text(encoding='utf-8') for name,path in {
        'Writer skill':'skills/ncce-campaign-writing/SKILL.md',
        'Voice identity':'docs/WRITER_IDENTITY_TAGS.md',
        'Automation instructions':'docs/WRITER_AUTOMATION_PROMPT.md'}.items()}
