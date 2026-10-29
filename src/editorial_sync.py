"""One event-driven reviewer learning job per sealed feedback snapshot.

No writer calls, policy activation, timers, or rewriting of historical verdicts.
"""
import json
import uuid
import writer_workshop as ws
import codex_review_queue as cq
import editorial_quality as quality

KIND='editorial_consolidation'
BUSY=('queued','claimed','reviewing')


def standards(store,form):
    value=store.get_state('reviewer-standards:'+form)
    return json.loads(value) if value else None


def schema():
    strings={'type':'array','maxItems':8,'items':{'type':'string','minLength':1,'maxLength':400}}
    props={'summary':{'type':'string','minLength':1,'maxLength':600},'changes':strings,
           'owner_corrections':strings,'reviewer_inferences':strings,
           'reviewer_standards':{'type':'string','minLength':1,'maxLength':6000},
           'proposed_form_instructions':{'type':'string','minLength':1,'maxLength':4000}}
    return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}


def validate(result):
    if not isinstance(result,dict) or set(result)!=set(schema()['properties']):raise ValueError('Feedback update must match its schema')
    for key,spec in schema()['properties'].items():
        v=result[key]
        if spec['type']=='string':
            if not isinstance(v,str) or not v.strip() or len(v)>spec['maxLength']:raise ValueError('Feedback update text is missing or too long')
        elif not isinstance(v,list) or len(v)>8 or any(not isinstance(x,str) or not x.strip() or len(x)>400 for x in v):raise ValueError('Keep feedback changes short and bounded')


def maybe_queue(store,run_id):
    import workshop_optimizer as opt
    with store._lock,store.db:
        state=opt.get(store,run_id)
        if state.get('workflow_version',1)<3 or state['status'] in ('queued','running'):return state
        inputs=[]
        for r in state['rounds']:
            for i,p in enumerate(r['pairs']):
                if not p.get('review'):continue
                vote=quality.verdict_for(store,run_id,r['number'],i)
                if not vote:return state
                inputs.append({'round':r['number'],'pair':i,'label':p['label'],'drafts':p['candidates'],
                    'review':p['review'],'owner_verdict':vote})
        if not inputs:return state
        fingerprint=quality.digest({'run':run_id,'feedback':inputs})
        previous=state.get('feedback_sync',{})
        if previous.get('input_hash')==fingerprint or previous.get('status') in BUSY:return state
        job='learn-'+uuid.uuid4().hex
        payload={'kind':KIND,'job_id':job,'run_id':run_id,'thread_id':cq.thread_id(),'form':state['form'],
            'input_hash':fingerprint,'feedback':inputs,'editorial_contract':quality.contract(),
            'candidate':state['specific'],'base_standards':standards(store,state['form']),
            'objective':'Consolidate the owner feedback AFTER independent reviews and owner verdicts were sealed. '
                'Update reusable reviewer standards and propose a complete reusable category writing brief. '
                'Explicit owner corrections outrank your preferences; distinguish them from your tentative inferences. '
                'Explain what changed and why in short human language. Never alter scores, verdicts, source/canon, '
                'the protected owner contract, spending or active writing policies. Do not rewrite drafts, start writing, '
                'inspect unjudged comparisons, or message other chats. Return the exact schema; the application saves '
                'inactive candidate guidance and the local helper mirrors the confirmed standards to reviewer memory.',
            'output_schema':schema()}
        state['feedback_sync']={'job_id':job,'input_hash':fingerprint,'status':'queued','at':ws.now(),
            'message':'Your verdicts are saved. JKSimmons will update his standards and candidate guidance once.'}
        store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)",(job,run_id,cq.packed(payload),ws.now()))
        store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?',(opt.packed(state),run_id))
    return state


def prepare_claim(store,payload):
    # Same native thread is leased serially. Refresh the base at claim time so
    # consecutive studies do not overwrite a newer completed consolidation.
    payload['base_standards']=standards(store,payload['form'])
    store.db.execute('UPDATE codex_review_jobs SET payload_json=? WHERE job_id=?',(cq.packed(payload),payload['job_id']))
    return payload


def set_status(store,payload,status,message):
    import workshop_optimizer as opt
    state=opt.get(store,payload['run_id']);sync=state.get('feedback_sync',{})
    if sync.get('job_id')!=payload['job_id']:raise ValueError('Feedback update was replaced')
    sync.update(status=status,message=message,at=ws.now())
    store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?',(opt.packed(state),state['run_id']))


def complete(store,payload,result,identity):
    import workshop_optimizer as opt
    state=opt.get(store,payload['run_id']);sync=state.get('feedback_sync',{})
    if sync.get('job_id')!=payload['job_id'] or sync['input_hash']!=payload['input_hash']:raise ValueError('Feedback snapshot changed')
    current=standards(store,payload['form'])
    if (current or {}).get('revision_id')!=(payload.get('base_standards') or {}).get('revision_id'):raise ValueError('Reviewer standards changed during this update; retain the result for inspection')
    revision=uuid.uuid4().hex;at=ws.now();base=payload['candidate']
    # Plain inserts share complete()'s transaction: candidate, memory and audit
    # either all commit or all roll back. No active policy pointers are touched.
    store.db.execute('INSERT INTO workshop_revisions VALUES(?,?,?,?,?,?)',(revision,payload['form'],
        'JKSimmons feedback consolidation',result['proposed_form_instructions'].strip(),base.get('examples',''),at))
    saved={**result,'examples':base.get('examples',''),'revision_id':payload['job_id'],'candidate_revision_id':revision,'form':payload['form'],
        'run_id':state['run_id'],'at':at,'identity':identity}
    for key in ('reviewer-standards-version:'+payload['job_id'],'reviewer-standards:'+payload['form']):
        store.db.execute('INSERT INTO system_state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,cq.packed(saved)))
    sync.update(status='completed',message=result['summary'],changes=result['changes'],standards=result['reviewer_standards'],
        owner_corrections=result['owner_corrections'],reviewer_inferences=result['reviewer_inferences'],
        candidate_revision_id=revision,previous_candidate_revision_id=base['revision_id'],at=at,identity=identity)
    store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?',(opt.packed(state),state['run_id']))


def export(store,payload):
    saved=standards(store,payload['form'])
    if not saved or saved['revision_id']!=payload['job_id']:
        raw=store.get_state('reviewer-standards-version:'+payload['job_id'])
        saved=json.loads(raw) if raw else None
    return {k:saved[k] for k in ('form','revision_id','reviewer_standards','summary','at','owner_corrections','reviewer_inferences')} if saved else None


def before_more_writing(store,state):
    """Consume a completed inactive candidate once, before a fresh learning round."""
    sync=state.get('feedback_sync',{})
    if sync.get('status') in BUSY:raise ValueError('JKSimmons is incorporating your feedback. Wait for his update before another writing round.')
    if sync.get('status') in ('failed','cancelled'):raise ValueError('The reviewer feedback update needs attention in his Codex chat before more writing.')
    rid=sync.get('candidate_revision_id')
    if sync.get('status')=='completed' and rid and sync.get('consumed_revision_id')!=rid:
        candidate=ws.revision(store,rid,state['form'])
        if candidate['instructions']!=state['specific']['instructions'] or candidate['examples']!=state['specific'].get('examples',''):
            state['specific']=candidate;state['validation_pending']=False
        sync['consumed_revision_id']=rid
