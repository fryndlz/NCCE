"""Event-driven category policies and durable five-attempt production jobs.

No model work on GET. Generation is kicked by sync, owner decisions and native
review completion. The server serializes writers with its shared pipeline lock.
"""
import json
import math
import uuid
import category_population as pop
import writer_workshop as ws
import llm_writer as writer
import codex_review_queue as bridge

POLICY='category-policy:'
ITEM='category-item:'
KIND='production_review'


def read(store,key,default=None):
    value=store.get_state(key)
    return json.loads(value) if value else default


def put(store,key,value):
    store.db.execute('INSERT INTO system_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,ws.packed(value)))


def all_items(store):
    return [json.loads(r[0]) for r in store.db.execute("SELECT value FROM system_state WHERE key LIKE 'category-item:%'")]


def policy(store,form):
    return read(store,POLICY+form,{'form':form,'enabled':False,'remaining':0,'used':0,'revision':None,'seen':[]})


def identity(store,key):
    row=pop.record(store,key);kind=key.partition(':')[0]
    if kind=='artifact':parts=[kind,row['scope_type'],row['scope_key']]
    elif kind=='memory':parts=[kind,row['fighter_id'],row['memory_key']]
    elif kind=='entry':parts=[kind,row['scope_type'],row['scope_key'],row['entry_key']]
    else:parts=[kind,row['thought_id']]
    return pop.hashed(parts)


def sources(store,form):
    return [(identity(store,s['key']),s) for s in ws.catalog(store) if s['form']==form and not s['key'].startswith('comparison:')]


def public_policy(p):
    return {k:v for k,v in p.items() if k not in ('seen','setup')}


def public_item(store,item):
    out={k:v for k,v in item.items() if k not in ('before','packet','instructions','source_hash','setup')}
    if item.get('review_job'):
        out['transport']=bridge.transport(store,item['review_job'])
    return out


def home(store):
    return {'policies':{f:public_policy(policy(store,f)) for f in ws.contract.BRIEFS},
            'items':[public_item(store,x) for x in sorted(all_items(store),key=lambda x:x['created_at'],reverse=True)[:100]],
            'reviewer':bridge.status(store),'max_grant':200}


def configure(store,body):
    form=ws.scope_name(body.get('form'))
    if form=='shared':raise ValueError('Choose a prose category')
    key=body.get('request_key')
    if not isinstance(key,str) or not 8<=len(key)<=100:raise ValueError('Decision identity required')
    command='category-decision:'+key
    old=read(store,command)
    if old:
        if old!=pop.hashed(body):raise ValueError('Decision identity belongs to different settings')
        return public_policy(policy(store,form))
    enabled=body.get('enabled');grant=body.get('additional_calls',0)
    if type(enabled) is not bool or type(grant) is not int or not 0<=grant<=200:raise ValueError('Invalid automatic-writing decision')
    p=policy(store,form)
    if body.get('expected_revision')!=p['revision']:raise ValueError('Automatic-writing settings changed. Refresh before deciding.')
    if enabled and (not writer.API_KEY or not bridge.status(store)['online']):raise ValueError('Connect JuniorWriter and the actual Codex reviewer before enabling automatic writing')
    if enabled and p['remaining']+grant<1:raise ValueError('Authorize a bounded writing allowance before enabling')
    with store._lock,store.db:
        store.db.execute('BEGIN IMMEDIATE')
        p=policy(store,form)
        if body.get('expected_revision')!=p['revision']:raise ValueError('Automatic-writing settings changed. Refresh before deciding.')
        if enabled and not p['enabled']:
            # Existing pending records belong to the one-off backlog action.
            p['seen']=list(set(p['seen'])|{ident for ident,_ in sources(store,form)})
            if 'setup' not in p:p['setup']=pop.setup(store,form)
            if form=='place_ambient':
                from world_streams import scene_triggers
                p['scene_seen']=[key for key,_ in scene_triggers(store)]
        p.update(enabled=enabled,remaining=p['remaining']+grant,revision=uuid.uuid4().hex,updated_at=ws.now())
        p['guidelines']=(p.get('setup') or {}).get('specific',{}).get('label','Active instructions at enablement')
        put(store,POLICY+form,p);put(store,command,pop.hashed(body))
        if not enabled:
            for item in all_items(store):
                if item['form']!=form or item['status']!='awaiting_review':continue
                job=bridge.get(store,item['review_job'])
                if job['status']=='queued':
                    bridge.cancel(store,item['review_job'],'Owner disabled automatic writing before review started')
                    item.update(status='paused_review',message='Automatic writing is off. Saved draft retained; review has not started.')
                    put(store,ITEM+item['item_id'],item)
        else:
            for item in all_items(store):
                if item['form']==form and item['status']=='paused_review':
                    enqueue_review(store,item);put(store,ITEM+item['item_id'],item)
    return public_policy(p)


def discover(store):
    """Called only after a successful campaign sync; stable identity is independent of regenerated row IDs."""
    with store._lock,store.db:
        for form in ws.contract.BRIEFS:
            p=policy(store,form)
            if not p['enabled']:continue
            if form=='place_ambient':
                from world_streams import scene_record,scene_triggers
                known=set(p.get('scene_seen',[]))
                for trigger,anchor in scene_triggers(store):
                    if trigger not in known:
                        scene_record(store,int(anchor['scope_key']),trigger,anchor)
                        known.add(trigger)
                p['scene_seen']=sorted(known)
            seen=set(p['seen'])
            uncertain={e['key'] for run in pop.home_all(store) for e in run['results'] if e['status'] in ('generating','generated','error')}
            for ident,source in sources(store,form):
                if ident in seen:continue
                seen.add(ident)
                if source['key'] in uncertain:continue
                if pop.eligibility(pop.record(store,source['key']))!='pending':continue
                if read(store,ITEM+ident):continue
                item={'item_id':ident,'form':form,'key':source['key'],'label':source['label'],'status':'queued',
                      'created_at':ws.now(),'attempts':[],'best':None,'message':'New campaign record queued.','setup':p['setup']}
                put(store,ITEM+ident,item)
            p['seen']=sorted(seen);put(store,POLICY+form,p)


def review_schema():
    props={'overall':{'type':'number','minimum':0,'maximum':10},'valid':{'type':'boolean'},
           'category':{'type':'string','enum':['writing','context','technical','permission']},
           'summary':{'type':'string','maxLength':600},'feedback':{'type':'string','maxLength':2000}}
    return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}


def validate(result):
    if not isinstance(result,dict) or set(result)!=set(review_schema()['properties']):raise ValueError('Invalid production-review fields')
    score=result['overall']
    if type(score) not in (float,int) or not math.isfinite(score) or not 0<=score<=10 or type(result['valid']) is not bool:raise ValueError('Invalid production score or validity')
    if result['category'] not in ('writing','context','technical','permission'):raise ValueError('Invalid issue category')
    for key,maximum in [('summary',600),('feedback',2000)]:
        if not isinstance(result[key],str) or not 1<=len(result[key].strip())<=maximum:raise ValueError('Missing or excessive production review '+key)


def enqueue_review(store,item):
    attempt=item['attempts'][-1];job='production-'+uuid.uuid4().hex
    from editorial_sync import standards
    from editorial_quality import contract
    payload={'kind':KIND,'job_id':job,'run_id':'production:'+item['item_id'],'thread_id':bridge.thread_id(),
             'item_id':item['item_id'],'attempt':len(item['attempts']),'form':item['form'],
             'instructions':item['instructions'],'packet':item['packet'],'draft':attempt['document'],
             'previous_reviews':[a['review'] for a in item['attempts'][:-1] if a.get('review')],
             'reviewer_standards':standards(store,item['form']),'editorial_contract':contract(),'output_schema':review_schema(),
             'objective':'Review ONE production draft. Do not perform an A/B study or change category guidelines. Rate literary quality honestly. valid means factual fidelity, source authority, required format and viewpoint all pass; an invalid draft can never be published as fallback. For writing-only shortcomings give concrete rewrite feedback. Context, technical or permission problems stop this entry and require human attention. No writer calls, policy changes or source edits from this reviewer chat. Return the exact schema.'}
    store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)",(job,payload['run_id'],ws.packed(payload),ws.now()))
    item.update(status='awaiting_review',review_job=job,message='Draft saved. Waiting for JKSimmons to start its review; queued is not running.')


def complete(store,payload,result,identity_info):
    item=read(store,ITEM+payload['item_id'])
    if not item or item.get('review_job')!=payload['job_id'] or payload['attempt']!=len(item['attempts']):raise ValueError('Production review identity changed')
    a=item['attempts'][-1];a['review']={**result,'native':identity_info};a['status']='reviewed'
    if result['category']!='writing':
        item.update(status='needs_attention',message=result['summary'])
    else:
        if result['valid'] and (item['best'] is None or result['overall']>item['attempts'][item['best']]['review']['overall']):item['best']=len(item['attempts'])-1
        if result['valid'] and result['overall']>=8 or len(item['attempts'])>=5:
            item.update(status='publish_pending',message='Selecting the best valid reviewed draft.')
        else:item.update(status='queued',message='JKSimmons requested a rewrite. '+result['feedback'])
    put(store,ITEM+item['item_id'],item)


def failed(store,payload,message):
    item=read(store,ITEM+payload['item_id'])
    if item and item.get('review_job')==payload['job_id']:
        item.update(status='needs_attention',message=message);put(store,ITEM+item['item_id'],item)


def recover(store):
    with store._lock,store.db:
        p=read(store,POLICY+'place_ambient')
        if p and 'scene_seen' not in p:
            from world_streams import scene_triggers
            p['scene_seen']=[key for key,_ in scene_triggers(store)]
            put(store,POLICY+'place_ambient',p)
        for item in all_items(store):
            if item['status'] in ('writing','awaiting_review'):
                item.update(status='needs_attention',message='Server restarted during a request or review. Saved attempts retained; no automatic replay.')
                put(store,ITEM+item['item_id'],item)


def runnable(store):
    online=bridge.status(store)['online']
    return any(policy(store,i['form'])['enabled'] and (i['status']=='publish_pending' or online and i['status']=='queued' and policy(store,i['form'])['remaining']>0) for i in all_items(store))


def advance(store):
    """Drain ready generation/publication stages; never wait for a reviewer or retry a request."""
    for candidate in all_items(store):
        p=policy(store,candidate['form'])
        if not p['enabled'] or candidate['status'] not in ('queued','publish_pending'):continue
        item=read(store,ITEM+candidate['item_id'])
        if item['status']=='publish_pending':
            if item['best'] is None:item.update(status='needs_attention',message='Five drafts reviewed; none passed factual and format checks. Nothing published.')
            else:
                best=item['attempts'][item['best']]
                try:
                    with store._lock,store.db:pop.publish(store,item['key'],item['before'],best['document'],best['paragraphs'])
                    item.update(status='published',below_target=best['review']['overall']<8,message='Best valid draft saved'+(' below the quality target after five attempts.' if best['review']['overall']<8 else '.'))
                except ValueError as exc:item.update(status='needs_attention',message=str(exc))
            put(store,ITEM+item['item_id'],item);store.db.commit();continue
        if p['remaining']<1:continue
        if not bridge.status(store)['online']:continue
        if len(item['attempts'])>=5:
            item.update(status='needs_attention',message='Five attempts already reserved. No further writer request is permitted.')
            put(store,ITEM+item['item_id'],item);store.db.commit();continue
        try:
            row=pop.record(store,item['key'])
            if pop.eligibility(row)!='pending':raise ValueError('The target already has prose or is no longer eligible. Existing writing preserved.')
            if item['attempts'] and pop.hashed(row)!=item['source_hash']:raise ValueError('Campaign facts changed during this entry. Inspect its saved drafts before continuing.')
            if not item['attempts']:
                sample=ws.sample(store,item['key'])
                import writer_planning,writing_rag
                item.update(before=row,source_hash=pop.hashed(row),
                    packet=writing_rag.attach(store,item['form'],writer_planning.prepare(store,item['form'],sample['packet'],persist=True),persist=True),
                    instructions=ws.compose(item['form'],item['setup']['shared'],item['setup']['specific']))
            # One durable reservation counts even if a provider response is uncertain.
            with store._lock,store.db:
                store.db.execute('BEGIN IMMEDIATE')
                p=policy(store,item['form'])
                if not p['enabled'] or p['remaining']<1:continue
                p['remaining']-=1;p['used']+=1
                item['attempts'].append({'number':len(item['attempts'])+1,'status':'writing','started_at':ws.now()})
                item.update(status='writing',message='JuniorWriter is drafting attempt '+str(len(item['attempts']))+' of 5.')
                put(store,POLICY+item['form'],p);put(store,ITEM+item['item_id'],item)
            writer.reset_budget(1,'production:'+item['item_id']+':'+str(len(item['attempts'])))
            enabled=writer.WRITER_ENABLED;writer.set_enabled(True)
            feedback=item['attempts'][-2].get('review',{}).get('feedback') if len(item['attempts'])>1 else None
            instructions=item['instructions']+'\n\nProduction draft attempt '+str(len(item['attempts']))+' of 5. Write a complete draft.'+('\n\n## Revision feedback for this entry only\n'+feedback if feedback else '')
            try:paragraphs,status=writer.write(store,item['form'],item['packet'],{'subject_type':'category_production','subject_key':item['item_id'],'subject_name':item['label']},contract_override=instructions)
            finally:writer.set_enabled(enabled)
            store.db.commit()
            attempt=item['attempts'][-1];attempt.update(usage=writer.run_summary(),finished_at=ws.now())
            if status['status']!='ready':raise RuntimeError(status.get('message','JuniorWriter did not produce valid prose'))
            # Preserve the original record presentation and evidence.
            original=json.loads(item['before']['document_json']) if 'document_json' in item['before'] else ws.sample(store,item['key'])['document']
            attempt.update(status='drafted',paragraphs=paragraphs,document=writer.apply(original,paragraphs,status))
            with store._lock,store.db:
                if policy(store,item['form'])['enabled']:enqueue_review(store,item)
                else:item.update(status='paused_review',message='Automatic writing switched off. Draft saved; no review started.')
                put(store,ITEM+item['item_id'],item)
        except Exception as exc:
            store.db.commit();item.update(status='needs_attention',message=str(exc)[:600]);put(store,ITEM+item['item_id'],item);store.db.commit()
