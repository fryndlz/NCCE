"""Six-call blinded editorial experiment. Does not change production stories or policy."""
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime,timezone
from pathlib import Path
import llm_writer as writer
import narrative_context as context
import writer_candidate as candidate
import writer_contract
import writer_preview
import writing_director as director

STATE_KEY='writer_comparison:'+candidate.REVISION

def cases(store,territory_id,fighter_name):
    territory=writer_preview.territory_samples(store,territory_id)[1]
    payload=territory['packet']['writer_context']['event']
    # All cases use sourced facts and authored context, never the earlier generated pilot.
    territory['label']='Territory event — '+territory['packet']['subject']
    target=payload.get('territory_claimer') or payload.get('winner') or payload.get('defender')
    gangs=store.db.execute('SELECT * FROM gangs WHERE active=1 AND name=?',(target,)).fetchall()
    if len(gangs)!=1: raise ValueError('A unique recorded gang is required')
    gang=dict(gangs[0])
    gang_packet={'subject':gang['name'],'evidence':[payload],
                 'source_event_ids':territory['packet']['source_event_ids'],
                 'source_records':territory['packet']['source_records'],
                 'gang_context':{'name':gang['name'],'affiliation':gang.get('gang_type'),'authored_background':context.authored(gang)},
                 'writer_context':{'event':payload,'occurred_at':territory['at'],
                    'task':'One gang account of this recorded outcome. No individual attendance or battlefield actions are established.'}}
    fighters=store.db.execute('SELECT * FROM fighters WHERE name=?',(fighter_name,)).fetchall()
    if len(fighters)!=1: raise ValueError('A unique fighter is required')
    fighter=dict(fighters[0])
    event=None
    for memory in store.db.execute('SELECT * FROM story_memories WHERE fighter_id=? AND active=1 ORDER BY coalesce(occurred_at,observed_at),memory_id',(fighter['id'],)):
        for event_id in json.loads(memory['source_event_ids_json']):
            row=store.db.execute("SELECT * FROM campaign_events WHERE event_id=? AND event_type='fighter_effects_changed'",(event_id,)).fetchone()
            if row and 'critical injury' in str(json.loads(row['payload_json']).get('after','')).lower():
                event=dict(row); event['payload']=json.loads(event.pop('payload_json')); break
        if event: break
    if not event: raise ValueError('No sourced critical-injury event for this fighter')
    fighter_gang=dict(store.db.execute('SELECT * FROM gangs WHERE gang_id=?',(fighter['gang_id'],)).fetchone())
    import story_prose,story_engine
    historical,historical_gang=context.fighter_at_event(store,fighter,fighter_gang,event)
    identity=director.identity_context(historical,historical_gang,story_prose.voice_profile(historical,historical_gang))
    packet=writer.memory_packet(store,historical,historical_gang,'Critical injury',story_engine.event_evidence(event),identity,event=event)
    packet.pop('generated_background',None)
    return [territory,{'label':'Fighter memory — '+fighter_name,'form':'fighter_memory','packet':packet,'at':event.get('occurred_at') or event.get('observed_at')},
            {'label':'Gang event — '+gang['name'],'form':'gang_event','packet':gang_packet,'at':territory['at']}]

def run(store,samples,run_id):
    if len(samples)!=3: raise ValueError('Exactly three paired cases required')
    old_enabled=writer.WRITER_ENABLED
    writer.reset_budget(6,run_id); writer.set_enabled(True)
    result={'run_id':run_id,'status':'running','model':writer.MODEL,'effort':writer.DEFAULT_REASONING_EFFORT,
            'created_at':datetime.now(timezone.utc).isoformat(),'cases':[]}
    # Assignment stays server-side. Client receives blind labels only.
    assignments=[]
    for index,sample in enumerate(samples):
        order=['current','candidate']; secrets.SystemRandom().shuffle(order)
        assignments.append(order)
        result['cases'].append({'label':sample['label'],'form':sample['form'],
            'evidence':sample['packet'].get('evidence',sample['packet'].get('mechanical_evidence',[])),
            'input_hash':hashlib.sha256(writer._json(sample['packet']).encode()).hexdigest(),'entries':[]})
    store.set_state(STATE_KEY,json.dumps(result))
    try:
        for index,sample in enumerate(samples):
            packet=json.loads(json.dumps(sample['packet']))
            packet['editorial_evaluation_run']=run_id  # same packet for both; prevents old result-cache reuse
            for position,variant in enumerate(assignments[index]):
                policy=writer_contract.contract(sample['form']) if variant=='current' else candidate.contract(sample['form'])
                trace={'subject_type':'editorial_comparison','subject_key':f'{index}:{position}',
                       'subject_name':sample['packet'].get('subject'),
                       'contract_revision':writer_contract.REVISION if variant=='current' else candidate.REVISION}
                paragraphs,status=writer.write(store,sample['form'],packet,trace,contract_override=policy)
                document=director.direct_document(sample['form'],f'COMPARE-{index+1}-{position+1}',
                    {'title':sample['packet'].get('subject'),'provenance_class':'inference'},{'occurred_at':sample['at']})
                document=writer.apply(document,paragraphs,status)
                result['cases'][index]['entries'].append({'label':'Version '+('A' if position==0 else 'B'),'document':document})
                result['usage']=writer.run_summary()
                store.set_state(STATE_KEY,json.dumps(result,ensure_ascii=False))
        result['status']='complete' if writer.run_summary()['requests_succeeded']==6 else 'needs_review'
    finally:
        writer.set_enabled(old_enabled)
        result['usage']=writer.run_summary()
        store.set_state(STATE_KEY,json.dumps(result,ensure_ascii=False))
    return result

def main():
    import argparse
    from store import Store
    parser=argparse.ArgumentParser(description='One six-call writing comparison; default is a free plan')
    parser.add_argument('--territory-id',type=int,required=True)
    parser.add_argument('--fighter-name',default='Mara Kel')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    path=Path(os.environ.get('NCCE_DB_PATH',str(Path(__file__).resolve().parents[1]/'data/chronicle.db')))
    if not path.exists(): parser.error('Existing database required')
    store=Store(path)
    try:
        samples=cases(store,args.territory_id,args.fighter_name)
        if not args.execute:
            print(json.dumps({'maximum_calls':6,'model':writer.MODEL,'effort':writer.DEFAULT_REASONING_EFFORT,
                'cases':[{'label':s['label'],'form':s['form']} for s in samples]},indent=2)); return
        if not writer.API_KEY: parser.error('Provider key unavailable')
        if writer.MAX_CALLS<6: parser.error('Configured budget is below six; no calls made')
        if store.get_state(STATE_KEY): parser.error('Comparison already saved; no repeat calls made')
        claim=store.db.execute('INSERT OR IGNORE INTO system_state(key,value) VALUES(?,?)',(STATE_KEY+':claimed','1'))
        store.db.commit()
        if claim.rowcount!=1: parser.error('Comparison already claimed; no repeat calls made')
        result=run(store,samples,'comparison-'+uuid.uuid4().hex)
        print(json.dumps({'status':result['status'],'usage':result['usage']},indent=2))
    finally: store.close()

if __name__=='__main__': main()
