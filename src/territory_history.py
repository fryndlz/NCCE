"""Owner-confirmed history supplements; never edits authoritative Sheet state.

Resolve only unique, non-default current holdings. Source IDs here bridge the
stale raw dump and current visible Sheet; they do not overwrite either source.
"""
import json
from pathlib import Path

PATH=Path(__file__).resolve().parents[1]/'data/lore/territory-history-confirmations.json'


def manifest():
    return json.loads(PATH.read_text(encoding='utf-8'))


def bindings(store):
    rows=[dict(r) for r in store.db.execute('SELECT * FROM territories WHERE active=1')]
    result=[]
    for binding in manifest()['bindings']:
        matches=[r for r in rows if str(r['gang_id'])==binding['gang_id']
                 and r['territory']==binding['current_type'] and bool(r['is_default'])==binding['is_default']]
        if len(matches)==1:result.append((binding,matches[0]))
    return result


def source_identity(store, territory):
    return next((b['source_territory_id'] for b,t in bindings(store) if t['id']==territory['id']),None)


def history_for(store, territory_id):
    data=manifest()
    return [dict(b['conversion'],former_type=b['former_type'],current_type=b['current_type'],
                 source_territory_id=b['source_territory_id'],source_id=data['source_id'],
                 provenance_class='player_authored',confirmed_at=data['confirmed_at'])
            for b,t in bindings(store) if t['id']==int(territory_id) and b.get('conversion')]


def apply(store):
    """Persist each explicit confirmation once, with unknown occurrence preserved."""
    data=manifest();created=[]
    matches=[(b,t) for b,t in bindings(store) if b.get('conversion')]
    if not matches:return created
    store.record_source(data['source_id'],'owner_confirmed_territory_history','player_authored',
                        'Owner-confirmed territory history',source_locator=PATH.name)
    from sync import SHEET_SOURCE_ID,SHEET_URI
    store.record_source(SHEET_SOURCE_ID,'campaign_sheet','mechanical_fact',
                        'Authoritative campaign Google Sheet',source_uri=SHEET_URI)
    for binding,place in matches:
        conversion=binding['conversion'];source=binding['source_territory_id']
        if store.event_by_key('owner-confirmed:'+conversion['key']):continue
        state={'Territory':binding['current_type'],
               'territory_id':source,'source_territory_key':source}
        payload={'territory':binding['current_type'],'territory_key':source,'previous_name':binding['former_type'],
                 'before_state':{**state,'Territory':binding['former_type']},'after_state':state,
                 'recorded_holder_id':place['gang_id'],'recorded_holder':place['gang_name'],'owner_at_conversion_unknown':True,
                 'cause':conversion['cause'],'occurrence_date_unknown':conversion['occurred_at'] is None,
                 'confirmation':conversion['confirmation'],'evidence':conversion['evidence']}
        subjects=[]
        for kind,key,name,role in [('territory',source,place['territory'],'location'),
                                  ('gang',place['gang_id'],place['gang_name'],'current_holder')]:
            existing=store.db.execute('SELECT entity_id FROM entities WHERE entity_type=? AND entity_key=?',(kind,key)).fetchone()
            entity=existing['entity_id'] if existing else store.register_entity(kind,key,name,'mechanical_fact',SHEET_SOURCE_ID)
            subjects.append({'entity_id':entity,'role':role})
        event_id,is_new=store.record_event('owner-confirmed:'+conversion['key'],'territory_type_changed',payload,
            'player_authored',source_id=data['source_id'],source_locator=PATH.name+'#'+conversion['key'],
            occurred_at=conversion['occurred_at'],observed_at=data['confirmed_at'],confidence=1.0,subjects=subjects)
        if is_new:created.append(event_id)
    return created


def records(store):
    """Timeline dots use confirmation time, never a fabricated conversion date."""
    result=[]
    for row in store.db.execute("SELECT * FROM campaign_events WHERE source_id=? ORDER BY event_id",(manifest()['source_id'],)):
        row=dict(row);p=json.loads(row['payload_json'])
        at=row['occurred_at'] or row['observed_at']
        description=f"{p['previous_name']} → {p['territory']} · {p['cause']}. Conversion date unknown; owner-confirmed history." if not row['occurred_at'] else f"{p['previous_name']} → {p['territory']} · {p['cause']}"
        result.append({'record_id':'territory-ledger:'+row['event_id'],'source_table':'territory_ledger',
            'source_event_id':row['event_id'],'gang_id':p['recorded_holder_id'],'fighter_id':None,
            'created_at_raw':at,'created_at_utc':at,'timestamp_basis':'occurred_at' if row['occurred_at'] else 'first_observed',
            'action_type':'territory_type_changed','description':description,'version_hash':row['event_id'],
            'source_tab':'Owner-confirmed territory history','source_id':row['source_id'],
            'source_locator':row['source_locator'],'errors':[],
            'record':{'campaign_territory_id':p['territory_key'],'territory_label':p['previous_name']+' → '+p['territory'],
                      'payload':p,'provenance_class':row['provenance_class'],
                      'occurred_at':row['occurred_at'],'observed_at':row['observed_at']}})
    return result


ORIGIN_EXCEPTION=(
    'ORIGIN EXCEPTION — confirmed transformation. Establish this place as the former Gambling Den, '
    'then briefly acknowledge its conversion into the present Settlement with an isotropic fuel rod. '
    'It was not always a Settlement. Preserve one continuous place and identity. '
    'The conversion also has a separate event-stream entry; do not invent its date, battle, owner at conversion, '
    'casualties or an exact sequence around other events. Territory creation and battle dates are not conversion dates. '
    'Do not expose confirmation, source tracing or application language inside diegetic prose. '
    'This exception applies only to the explicitly confirmed holding; other origins retain the usual baseline boundary.'
)


def amend_paused_origin(store, candidates):
    """One owner-authorized paused brief correction, never READY/imported work.

    Original packet/target/revision are retained under target_json.brief_history.
    No text or status is changed. The relay applies the new revision only after
    appending the correction to Context; an old-revision delivery fails closed.
    """
    from copy import deepcopy
    from exchange_automation import load,packed,revision,target_key,semantic_seal
    for c in candidates:
        if c['form']!='territory_origin':continue
        confirmations=c['facts'].get('confirmed_territory_history',[])
        for h in confirmations:
            rid=h.get('paused_origin_request_id')
            if not rid:continue
            r=store.db.execute('SELECT * FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone()
            if not r or r['target_key']!=target_key(c) or r['state']!='PENDING' or r['client_state'] not in ('WRITING','PENDING'):continue
            old=load(r['target_json'])
            if old['target']['facts'].get('confirmed_territory_history'):continue
            comparison=deepcopy(c)
            comparison['facts'].pop('confirmed_territory_history',None)
            comparison['context'].pop('origin_history_exception',None)
            if semantic_seal(store,comparison)!=semantic_seal(store,old['target']):continue
            block=dict(section='history_amendment',provenance='player_authored',
                source_ref='Owner-authorized paused-origin correction · '+h['key'],event_at_utc='',source_event_ids='',
                text='UPDATED BRIEF — read before resuming this paused request. This correction supersedes any earlier assumption that the place was always a Settlement. '
                     +ORIGIN_EXCEPTION+'\nConfirmed history: '+packed(confirmations)+'\nPreserve and edit any saved draft; do not create variants or restart the other entries.')
            packet=load(r['packet_json']);new_revision=revision(c,load(r['dependencies_json']),store)
            old.setdefault('brief_history',[]).append({'packet':deepcopy(packet),'target':old['target'],
                'source_revision':r['source_revision'],'reason':'Owner paused this request to add confirmed conversion history',
                'amended_at':manifest()['confirmed_at']})
            old['target']=c;packet['context'].append(block);packet['request']['source_revision']=new_revision
            relay_packet=deepcopy(packet);relay_packet['context']+=load(r['supplement_json'])
            old['relay_amendment']={'request_id':rid,'previous_revision':r['source_revision'],
                                    'source_revision':new_revision,'packet':relay_packet}
            store.db.execute('UPDATE writing_exchange_requests SET packet_json=?,target_json=?,source_revision=? WHERE request_id=?',
                             (packed(packet),packed(old),new_revision,rid))


def amendments(store):
    result=[]
    for r in store.db.execute("SELECT target_json FROM writing_exchange_requests WHERE state='PENDING'"):
        amendment=json.loads(r['target_json']).get('relay_amendment')
        if amendment:result.append(amendment)
    return result
