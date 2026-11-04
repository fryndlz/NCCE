"""Read-only bridge from tracked fighter facts into per-gang chronology."""
import json
import re
import unicodedata
from campaign_history import parse_instant


def key(value):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value or '')).strip().casefold())


def records(store):
    identities={}
    for f in store.db.execute('SELECT id,gang_id,name FROM fighters'):
        identities.setdefault((str(f['gang_id']),key(f['name'])),[]).append(dict(f))
    fighters={k:v[0] for k,v in identities.items() if len(v)==1}
    result=[];seen=set()
    query="""SELECT ce.*,e.entity_key,e.display_name FROM campaign_events ce
        JOIN event_subjects es ON es.event_id=ce.event_id JOIN entities e ON e.entity_id=es.entity_id
        WHERE e.entity_type='fighter' AND ce.provenance_class='mechanical_fact'
        AND substr(ce.event_type,1,8)='fighter_'
        AND ce.event_id NOT IN (SELECT supersedes_event_id FROM campaign_events WHERE supersedes_event_id IS NOT NULL)
        ORDER BY coalesce(ce.occurred_at,ce.observed_at),ce.event_id"""
    for row in store.db.execute(query):
        row=dict(row);identity=str(row['entity_key']).split('/',1)
        if len(identity)!=2:continue
        gang_id,name_key=identity;fighter=fighters.get((gang_id,key(name_key)))
        if not fighter:continue
        unique=(row['event_id'],fighter['id'])
        if unique in seen:continue
        seen.add(unique)
        raw_time=row.get('occurred_at') or row['observed_at']
        raw,at,error=parse_instant(raw_time)
        if not at:continue
        payload=json.loads(row['payload_json']);label=row['event_type'].replace('fighter_','').replace('_',' ')
        detail=''
        if 'before' in payload or 'after' in payload:
            value=lambda v: 'not recorded' if v is None else str(v) if isinstance(v,(str,int,float)) else json.dumps(v,ensure_ascii=False)
            detail=f" · {payload.get('field') or label}: {value(payload.get('before'))} → {value(payload.get('after'))}"
        description=f"{fighter['name']} · {label}{detail}"
        result.append({'record_id':'ledger:'+row['event_id']+':'+str(fighter['id']),'source_table':'fighter_ledger',
                       'gang_id':gang_id,'fighter_id':'local:'+str(fighter['id']),'fighter_name_hint':fighter['name'],
                       'created_at_raw':raw,'created_at_utc':at,'updated_at_utc':at,'version_hash':row['event_id'],
                       'action_type':row['event_type'],'description':description,'errors':[error] if error else [],
                       'source_tab':'NCCE tracked fighter changes','source_row':None,
                       'timestamp_basis':'occurred_at' if row.get('occurred_at') else 'first_observed',
                       'source_event_id':row['event_id'],'source_id':row['source_id'],'source_locator':row.get('source_locator'),
                       'record':{'id':row['event_id'],'gang_id':gang_id,'fighter_id':'local:'+str(fighter['id']),
                                 'description':description,'payload':payload,'source_event_id':row['event_id'],
                                 'from_snapshot_id':row.get('from_snapshot_id'),'to_snapshot_id':row.get('to_snapshot_id')}})
    return result
