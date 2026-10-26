"""Bounded editorial previews using the production writer; never publish to campaign state."""
import json
from datetime import datetime, timezone
import llm_writer
import narrative_context as context
import writing_director as director
import writer_contract

STATE_KEY = 'writer_preview:' + writer_contract.REVISION


def recorded_event(store, entries):
    """Resolve ledger evidence or an exact battle in an immutable snapshot."""
    for entry in entries:
        for event_id in json.loads(entry['source_event_ids_json']):
            event=store.db.execute('SELECT * FROM campaign_events WHERE event_id=?',(event_id,)).fetchone()
            if event:
                return json.loads(event['payload_json']),event['occurred_at'],event['observed_at'],[event_id],[]
    from snapshot import battle_records
    fields=('date','scenario','attacker','defender','winner','territory','territory_claimer','notes')
    for entry in entries:
        expected=json.loads(entry['document_json']).get('writer_context',{}).get('event',{})
        if not expected.get('date') or not expected.get('territory'): continue
        for snapshot in store.db.execute('SELECT id,captured_at,payload_json FROM snapshots ORDER BY id DESC'):
            raw=json.loads(snapshot['payload_json']).get('battles')
            if not isinstance(raw,list): continue
            matches=[battle for battle in battle_records(raw) if all(battle.get(key)==expected.get(key) for key in fields)]
            if len(matches)==1:
                battle=matches[0]
                source={'snapshot_id':snapshot['id'],'source_row':battle.get('source_row'),'basis':'exact immutable snapshot battle'}
                return battle,battle['date'],snapshot['captured_at'],[],[source]
    raise ValueError('The preview event needs an immutable source record')


def territory_samples(store, territory_id):
    """Territories are the first fixture for the shared writing pipeline, not a special writer."""
    row=store.db.execute('SELECT * FROM territories WHERE id=? AND active=1',(territory_id,)).fetchone()
    if not row: raise ValueError('Active territory not found')
    territory=dict(row)
    entries=store.db.execute("SELECT * FROM narrative_entries WHERE scope_type='territory' AND scope_key=? AND active=1 AND event_type IN ('battle_result','battle_record_corrected','territory_holder_changed') ORDER BY coalesce(occurred_at,observed_at),entry_id",(str(territory_id),)).fetchall()
    if not entries: raise ValueError('Choose a territory with a recorded contest or ownership change for this preview')
    payload,occurred_at,observed_at,event_ids,source_records=recorded_event(store,entries)
    at=occurred_at or observed_at
    state=context.territory_state_at(store,territory,at)
    name=payload.get('territory') or state.get('name') or territory['territory']
    common={'subject':name,'writer_context':{'state_at_event':state}}
    return [
        {'label':'Baseline — generated background', 'form':'territory_origin','packet':{'subject':name,'evidence':['Territory type: '+name], 'writer_context':{'task':'Foundational local history, before the campaign event. No current campaign outcome belongs in the background.'}},'at':None},
        {'label':'Recorded event — real campaign evidence', 'form':'place_event','packet':{**common,'evidence':[payload], 'source_event_ids':event_ids,'source_records':source_records,'writer_context':{**common['writer_context'],'event':payload,'occurred_at':occurred_at,'observed_at':observed_at}},'at':at},
        {'label':'Ambient incident — fictional preview, not added to campaign', 'form':'place_ambient','packet':{**common,'evidence':[], 'writer_context':{**common['writer_context'],'task':'A hypothetical later local incident; no mechanical effects. This test is outside the real timeline.'}},'at':None},
        {'label':'Transformation — hypothetical test, not a recorded change', 'form':'place_event','packet':{'subject':name,'evidence':[{'test_fixture':True,'before_type':name,'after_type':'Settlement' if name!='Settlement' else 'Old Ruins','cause':None}], 'writer_context':{'task':'Hypothetical subsequent physical transformation. Neither this change nor its cause is asserted in the real campaign.'}},'at':None},
    ]


def run_preview(store, samples, run_id):
    """One request per supplied entry; 1–4 entries; all outputs remain auditable."""
    if not 1<=len(samples)<=4: raise ValueError('A writing preview must contain one to four entries')
    if any(sample['form'] not in writer_contract.BRIEFS for sample in samples): raise ValueError('Unknown writing form')
    old_enabled=llm_writer.WRITER_ENABLED
    llm_writer.reset_budget(limit=len(samples),run_id=run_id)
    llm_writer.set_enabled(True)
    result={'run_id':run_id,'status':'running','revision':writer_contract.REVISION,'model':llm_writer.MODEL,
            'effort':llm_writer.DEFAULT_REASONING_EFFORT,'created_at':datetime.now(timezone.utc).isoformat(),'entries':[]}
    store.set_state(STATE_KEY,json.dumps(result))
    earlier=[]
    try:
        for index,sample in enumerate(samples):
            packet=json.loads(json.dumps(sample['packet']))
            packet['preview_continuity']={'provenance':'generated_fiction','earlier_entries':earlier}
            paragraphs,status=llm_writer.write(store,sample['form'],packet,{'subject_type':'editorial_preview','subject_key':str(index),'subject_name':packet.get('subject')})
            document=director.direct_document(sample['form'],'PREVIEW-'+str(index+1),{'title':packet.get('subject'),'provenance_class':'inference'},{'occurred_at':sample.get('at')})
            document=llm_writer.apply(document,paragraphs,status)
            result['entries'].append({'label':sample['label'],'form':sample['form'],'document':document})
            if status['status']=='ready':
                earlier.append({'label':sample['label'],'text':context.prose(document),'subject':document.get('composition',{}).get('subject')})
            result['usage']=llm_writer.run_summary()
            store.set_state(STATE_KEY,json.dumps(result,ensure_ascii=False))
            if status['status']!='ready':
                result['status']='needs_review'
                result['message']='Stopped after the unsuccessful entry. Its response is retained; no dependent calls were made.'
                break
        else:
            result['status']='complete'
    finally:
        llm_writer.set_enabled(old_enabled)
        result['usage']=llm_writer.run_summary()
        store.set_state(STATE_KEY,json.dumps(result,ensure_ascii=False))
    return result


def main():
    import argparse,os,uuid
    from pathlib import Path
    from store import Store
    parser=argparse.ArgumentParser(description='Four-entry editorial preview. Does not publish campaign prose.')
    parser.add_argument('--territory-id',required=True,type=int)
    parser.add_argument('--execute',action='store_true',help='Explicitly authorize at most four provider requests; otherwise print the plan only')
    args=parser.parse_args()
    path=Path(os.environ.get('NCCE_DB_PATH',str(Path(__file__).resolve().parents[1]/'data/chronicle.db')))
    if not path.exists(): parser.error('Existing campaign database required')
    store=Store(path)
    try:
        samples=territory_samples(store,args.territory_id)
        if not args.execute:
            print(json.dumps({'maximum_calls':len(samples),'model':llm_writer.MODEL,'effort':llm_writer.DEFAULT_REASONING_EFFORT,
                              'entries':[{'label':s['label'],'form':s['form']} for s in samples]},indent=2))
            return
        if not llm_writer.API_KEY: parser.error('Server-side writing provider key is not configured')
        if store.get_state(STATE_KEY): parser.error('This revision already has a saved preview. Inspect it; no repeat calls were made.')
        claim=store.db.execute('INSERT OR IGNORE INTO system_state(key,value) VALUES(?,?)',(STATE_KEY+':claimed','1'))
        store.db.commit()
        if claim.rowcount!=1: parser.error('This preview was already claimed by another process; no calls were made.')
        result=run_preview(store,samples,'editorial-preview-'+uuid.uuid4().hex)
        print(json.dumps({'status':result['status'],'usage':result['usage']},indent=2))
    finally:
        store.close()


if __name__=='__main__': main()
