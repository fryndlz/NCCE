"""Deterministic replacement policy and prose dependencies; no model work."""
import json
from datetime import datetime, timezone

VERSION=2
PHASES=('Baselines','Recorded events','Reflections','Current thoughts','Histories and downtime','Regional chronicle')
FORM_PHASE={
    'fighter_biography':0,'territory_origin':0,
    'fighter_memory':1,'gang_event':1,'place_event':1,'place_ambient':1,'battle_report':1,
    'fighter_reflection':2,'fighter_mind':3,
    'gang_history':4,'territory_history':4,'relationship':4,'downtime':4,'region_history':5}


def classify(store,items):
    from exchange_automation import target_key,semantic_seal,load
    imported={}
    for row in store.db.execute("SELECT * FROM writing_exchange_requests WHERE state='IMPORTED' ORDER BY imported_at"):
        imported[row['target_key']]=dict(row)
    for c in items:
        saved=imported.get(target_key(c))
        # Static accepted entries are never rewritten for guidance changes.
        # Rolling histories can get another entry when their factual input changes.
        from exchange_automation import ROLLING_FORMS
        same=bool(saved and semantic_seal(store,load(saved['target_json'])['target'])==semantic_seal(store,c))
        c['approved']=bool(saved and (c['form'] not in ROLLING_FORMS or same))
        c['legacy']=not c['approved'] and c.get('has_prose',c['ready'])
        c['phase']=FORM_PHASE[c['form']]
    return items


def order(c):
    from narrative_context import instant
    # Ordering prose by event time does not alter the cognitive event clock.
    at=instant(c.get('event_at_utc')) or datetime.min.replace(tzinfo=timezone.utc)
    return (c['phase'],at,c['entity_type'],c['entity_key'],str(c['key']))


def dependencies(store,items):
    from exchange_automation import target_key,load
    bykey={target_key(c):c for c in items};deps={k:set() for k in bykey};missing={k:[] for k in bykey}
    fighters={str(r['id']):dict(r) for r in store.db.execute('SELECT * FROM fighters')}
    places={str(r['id']):dict(r) for r in store.db.execute('SELECT * FROM territories WHERE active=1')}
    memids={r['memory_id']:json.dumps(['memory',[r['fighter_id'],r['memory_key']]],separators=(',',':'))
            for r in store.db.execute('SELECT memory_id,fighter_id,memory_key FROM story_memories')}
    def artifact(form,key):return json.dumps(['artifact',[form,str(key)]],ensure_ascii=False,separators=(',',':'))
    def gang(c):
        if c['entity_type']=='fighter':return str(fighters.get(c['entity_key'],{}).get('gang_id',''))
        if c['entity_type']=='gang':return c['entity_key']
        return ''
    gang_names={str(r['gang_id']):r['name'] for r in store.db.execute('SELECT gang_id,name FROM gangs')}
    def battle_parties(c):
        s=c['facts'].get('subject',{})
        return {s.get('attacker'),s.get('defender')}-{None,''}
    def battle_place(c):
        s=c['facts'].get('subject',{})
        exact=[p for p in places.values() if p.get('territory')==s.get('territory') and p.get('gang_name') in battle_parties(c)]
        return str(exact[0]['id']) if len(exact)==1 else None
    def baseline(c,kind,key):
        k=target_key(c);dep=artifact('fighter_biography' if kind=='fighter' else 'territory_origin',key)
        if dep in bykey:deps[k].add(dep)
        elif kind=='fighter':
            from narrative_context import authored
            f=fighters.get(str(key),{})
            if not (authored(f) or load(f.get('mechanics_json')).get('Backstory')):
                missing[k].append('Fighter baseline slot is missing')
        else:missing[k].append('Territory baseline slot is missing')
    for c in items:
        key=target_key(c);form=c['form']
        if c['entity_type']=='fighter' and form!='fighter_biography':baseline(c,'fighter',c['entity_key'])
        if c['entity_type']=='territory' and form!='territory_origin':baseline(c,'territory',c['entity_key'])
        if form=='battle_report':
            place=battle_place(c)
            if place:baseline(c,'territory',place)
        if form=='fighter_reflection':
            refs=c['facts'].get('source_observation_ids_json',[])
            for ref in refs:
                if memids.get(ref) in bykey:deps[key].add(memids[ref])
                else:
                    # The reviewed Mara pilot is deliberately absent from candidates.
                    row=store.db.execute('SELECT fighter_id,memory_key FROM story_memories WHERE memory_id=? AND active=1',(ref,)).fetchone()
                    if not row or not store.db.execute("SELECT 1 FROM external_prose_deliveries WHERE fighter_id=? AND memory_key=? AND disposition='imported'",tuple(row)).fetchone():
                        missing[key].append('Cited observation unavailable: '+str(ref))
        if form=='fighter_mind':
            cause=c['facts'].get('memory_key')
            target=json.dumps(['memory',[int(c['entity_key']),cause]],separators=(',',':'))
            if target in bykey:deps[key].add(target)
            elif not store.db.execute("SELECT 1 FROM external_prose_deliveries WHERE fighter_id=? AND memory_key=? AND disposition='imported'",(c['entity_key'],cause)).fetchone():
                missing[key].append('Current thought cause is unavailable')
        if form in ('gang_history','downtime','relationship','territory_history','region_history'):
            names=set(c['entity_key'].split('|')) if form=='relationship' else {gang_names.get(gang(c))}
            for other in items:
                if other is c:continue
                include=False
                if form=='region_history':include=other['phase']==4
                elif form=='territory_history':
                    include=other['entity_type']=='territory' and other['entity_key']==c['entity_key'] and other['phase']==1
                    include|=other['form']=='battle_report' and battle_place(other)==c['entity_key']
                elif other['phase'] in (1,2,3):
                    include=bool(gang_names.get(gang(other)) in names and gang(other))
                    include|=other['form']=='battle_report' and bool(battle_parties(other)&names)
                if include:deps[key].add(target_key(other))
    # Each fighter/scope's event stream is written in chronological sequence.
    groups={}
    for c in items:
        if c['form'] in ('fighter_memory','gang_event','place_event','place_ambient'):
            groups.setdefault((c['entity_type'],c['entity_key']),[]).append(c)
    for stream in groups.values():
        previous=None
        for c in sorted(stream,key=order):
            if previous:deps[target_key(c)].add(target_key(previous))
            previous=c
    return deps,missing


def plan(store,items):
    from exchange_automation import target_key
    deps,missing=dependencies(store,items);lookup={target_key(c):c for c in items}
    ready=[];blocked={}
    held={r[0] for r in store.db.execute("SELECT target_key FROM writing_exchange_requests WHERE state='HOLD'")}
    for c in items:
        if c['approved']:continue
        k=target_key(c);reasons=list(missing[k])
        if k in held:reasons.append('Request is on HOLD; reconciliation required')
        reasons.extend('Awaiting '+lookup[d]['form']+': '+lookup[d]['title'] for d in sorted(deps[k]) if not lookup[d]['approved'])
        if reasons:blocked[k]=reasons
        else:ready.append(c)
    return sorted(ready,key=order),deps,blocked


def context(store,c,deps,items):
    """Accepted prerequisites only; legacy wording never becomes a style seed."""
    from exchange_automation import target_key,projection,load,body,digest
    lookup={target_key(x):x for x in items};result=[]
    for key in sorted(deps.get(target_key(c),())):
        if key not in lookup:continue
        other=lookup[key]
        if not other['approved']:continue
        raw=projection(store,other)
        doc=load(raw.get('document_json'))
        text=raw.get('content') if other['kind'] in ('memory','thought') else doc.get('external_markdown') or body(doc)
        result.append({'target_key':key,'form':other['form'],'title':other['title'],
                       'event_at_utc':other['event_at_utc'],'provenance':'accepted_generated_fiction',
                       'text':text,'text_hash':digest(text)})
    return result


def scrub(value):
    if isinstance(value,list):return [scrub(x) for x in value]
    if not isinstance(value,dict):return value
    excluded={'generated_background','baseline','earlier_stories','related_observations','prior_entry','prior_entries','continuity_reference'}
    return {k:scrub(v) for k,v in value.items() if k not in excluded}


def retire_legacy(store,items):
    """Preserve every old projection, and stop labelling old generated prose ready."""
    from exchange_automation import target_key,projection,packed,seal,now
    count=0
    for c in items:
        if not c['legacy']:continue
        raw=projection(store,c);key=target_key(c)
        store.db.execute('INSERT OR IGNORE INTO writing_legacy_inventory(target_key,source_revision,projection_json,recorded_at) VALUES(?,?,?,?)',
                         (key,seal(c),packed(raw),now()))
        if raw.get('writer_status')=='stale' or (c['kind'] not in ('memory','thought') and json.loads(raw['document_json']).get('writer_status')=='stale'):
            continue
        if c['kind']=='memory':store.db.execute("UPDATE story_memories SET writer_status='stale' WHERE fighter_id=? AND memory_key=? AND active=1",c['key'])
        elif c['kind']=='thought':store.db.execute("UPDATE fighter_thoughts SET writer_status='stale' WHERE thought_id=? AND lifecycle='active'",c['key'])
        else:
            table,fields=('story_artifacts',['scope_type','scope_key']) if c['kind']=='artifact' else ('narrative_entries',['scope_type','scope_key','entry_key'])
            doc=json.loads(raw['document_json']);doc.update(writer_status='stale',writer_message='Legacy generated draft awaiting one replacement through the writing exchange.')
            store.db.execute('UPDATE '+table+' SET document_json=? WHERE '+' AND '.join(f+'=?' for f in fields)+' AND active=1',(packed(doc),*c['key']))
        c['ready']=False;count+=1
    return count


def summary(store,items):
    from exchange_automation import target_key
    runnable,deps,blocked=plan(store,items);rows=[]
    for index,name in enumerate(PHASES):
        subset=[c for c in items if c['phase']==index]
        rows.append(dict(phase=index,name=name,total=len(subset),complete=sum(c['approved'] for c in subset),
                         needs_writing=sum(not c['approved'] for c in subset),blocked=sum(target_key(c) in blocked for c in subset)))
    return dict(policy_version=VERSION,phases=rows,runnable=len(runnable),
                legacy_saved=store.db.execute('SELECT count(*) FROM writing_legacy_inventory').fetchone()[0],
                deferred=store.db.execute("SELECT count(*) FROM writing_exchange_requests WHERE state='DEFERRED'").fetchone()[0])
