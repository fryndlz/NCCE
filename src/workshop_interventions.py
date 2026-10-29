"""Owner decisions and scoped StoryTechMan proposals. Never calls a model directly."""
import hashlib
import json
import re
import uuid
import codex_review_queue as cq
import writer_workshop as ws

TECH_THREAD_ID='01a17ff0-9029-7a13-935f-d0a86dcdc2b2'
KINDS=('technical_investigation','technical_repair','technical_release')


def digest(value):return hashlib.sha256(cq.packed(value).encode()).hexdigest()
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def strings():return {'type':'array','items':{'type':'string'}}


def schema(kind,report_version=2):
    if kind=='technical_investigation':
        result=obj({'headline':{'type':'string','maxLength':180},'summary':{'type':'string'},
            'findings':{'type':'array','items':obj({'problem':{'type':'string','maxLength':240},'evidence':{'type':'string'},'uncertainty':{'type':'string'}})},
            'proposed_changes':strings(),'validation_plan':strings(),'risks':strings(),'questions':strings()})
    else:
        result=obj({'headline':{'type':'string','maxLength':180},'summary':{'type':'string'},'changes':strings(),'tests':strings(),
            'files':strings(),'limitations':strings(),'proposed_shared_instructions':{'type':'string'},'proposed_form_instructions':{'type':'string'},'commit_id':{'type':'string'},'ready':{'type':'boolean'}})
    if report_version>=2:
        result['properties']['decision_brief']=obj({key:{'type':'string','minLength':1,'maxLength':limit}
            for key,limit in [('problem',300),('solution',400),('risk',300)]})
        result['required'].append('decision_brief')
    return result


def validate(kind,result,report_version=1):
    if not isinstance(result,dict):raise ValueError('StoryTechMan must return a structured report')
    expected=schema(kind,2 if report_version>=2 or 'decision_brief' in result else 1)['properties']
    if set(result)!=set(expected):raise ValueError('StoryTechMan report fields do not match the job')
    for key,spec in expected.items():
        value=result[key]
        if key=='decision_brief':
            if not isinstance(value,dict) or set(value)!={'problem','solution','risk'}:raise ValueError('Report needs Problem, Solution and Risk')
            for field,limit in [('problem',300),('solution',400),('risk',300)]:
                if not isinstance(value[field],str) or not value[field].strip() or len(value[field])>limit:raise ValueError('Keep '+field+' short and human readable')
        if spec['type']=='string' and (not isinstance(value,str) or len(value)>12000):raise ValueError('Invalid report text')
        if spec['type']=='boolean' and type(value) is not bool:raise ValueError('Invalid repair readiness')
        if spec['type']=='array':
            if not isinstance(value,list) or len(value)>30:raise ValueError('Report list too long')
            for item in value:
                if key=='findings':
                    if not isinstance(item,dict) or set(item)!={'problem','evidence','uncertainty'} or any(not isinstance(v,str) or len(v)>6000 for v in item.values()):raise ValueError('Findings need bounded evidence and uncertainty')
                elif not isinstance(item,str) or len(item)>6000:raise ValueError('Invalid report list item')
    if len(result['headline'])>180:raise ValueError('Report headline must be concise')
    if not result['headline'].strip() or not result['summary'].strip():raise ValueError('Report summary required')
    if kind!='technical_investigation':
        if len(result['proposed_shared_instructions'])>12000 or len(result['proposed_form_instructions'])>4000:raise ValueError('Proposed prompt changes are too long')
    if kind!='technical_investigation' and result['ready']:
        if not re.fullmatch('[0-9a-f]{40}',result['commit_id']) or not result['tests']:raise ValueError('A ready repair needs a commit and validation evidence')


def self_test(store,body):
    job_id='tech-connection-check-'+digest(TECH_THREAD_ID)[:16]
    payload={'job_id':job_id,'run_id':'technical-connection-check','thread_id':TECH_THREAD_ID,'kind':'technical_investigation','diagnostic':True,'report_version':2,
        'packet':{'note':'Connection diagnostic only. Inspect current reusable generation/context and Workshop intervention code read-only. Propose one bounded infrastructure improvement with actual file evidence. Do not infer missing live data from this synthetic packet, edit files, generate prose, activate policies or deploy.'},'approval':None,'output_schema':schema('technical_investigation')}
    with store._lock,store.db:
        store.db.execute("INSERT OR IGNORE INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)",(job_id,payload['run_id'],cq.packed(payload),ws.now()))
    row=cq.get(store,job_id)
    return {'job_id':job_id,'status':row['status'],'result':json.loads(row['result_json']) if row['status']=='completed' else None,'error':row['error']}


def load(store,run_id):
    from workshop_optimizer import get
    return get(store,run_id)


def save(store,state,message):
    from workshop_optimizer import save
    save(store,state,message)


def submit(store,state,kind,note='',approval=None):
    from fighter_event_clock import policy as cognitive_policy
    job_id='tech-'+uuid.uuid4().hex
    packet={'run_id':state['run_id'],'form':state['form'],'status':state['status'],'message':state['message'],
        'environment_hash':state.get('environment_hash'),'configuration':state['configuration'],'shared':state['shared'],'specific':state['specific'],'rounds':state['rounds'],'prompt_history':state.get('prompt_history',[]),
        'note':note,'proposal':state.get('tech',{}).get('proposal'),'rejected_proposals':state.get('tech',{}).get('rejections',[])[-5:],
        'repair_report':state.get('tech',{}).get('report'),'cognitive_design':cognitive_policy()}
    payload={'job_id':job_id,'run_id':state['run_id'],'thread_id':TECH_THREAD_ID,'kind':kind,'report_version':2,
        'objective':'Improve reusable category prompts, guardrails and NCCE context; do not rewrite one draft. '
            'Lead with decision_brief: Problem, Solution, Risk. Use plain human language, one or two short sentences each, no file paths, hashes, raw status codes or Mechanicus banter. '
            'State the user-visible problem, your concrete recommendation and its main downside or uncertainty; never promise no risk without evidence. Keep detailed evidence in the other fields. '
            'If the owner rejected a proposal, investigate their objection and propose a revised approach. Do not repeat the rejected solution without explaining what changed or why alternatives are unavailable.',
        'packet':packet,'approval':approval,'output_schema':schema(kind)}
    packet['review_transport'] = [cq.transport(store,p['codex_job_id'])
        for r in state['rounds'] for p in r['pairs'] if p.get('codex_job_id')]
    with store._lock,store.db:
        store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)",(job_id,state['run_id'],cq.packed(payload),ws.now()))
        tech=state.setdefault('tech',{})
        tech.update(job_id=job_id,status={'technical_investigation':'queued','technical_repair':'repair_queued','technical_release':'release_queued'}[kind],thread_id=TECH_THREAD_ID,error='')
        save(store,state,'StoryTechMan job queued: '+kind)
    return state


def investigate(store,body):
    state=load(store,body.get('run_id'));key=body.get('request_key')
    if not isinstance(key,str) or not 12<=len(key)<=100:raise ValueError('Investigation identity required')
    old=state.get('tech',{})
    if old.get('request_key')==key:return state
    if state['status'] in ('queued','running'):raise ValueError('Stop the writing run before an investigation')
    if old.get('status') in ('queued','investigating','repair_queued','repairing','release_queued','releasing'):return state
    note=body.get('note','')
    if not isinstance(note,str) or len(note)>6000:raise ValueError('Investigation note too long')
    state['tech']={**old,'request_key':key,'thread_id':TECH_THREAD_ID,'error':''}
    return submit(store,state,'technical_investigation',note)


def decision(store,body):
    state=load(store,body.get('run_id'));tech=state.get('tech',{});action=body.get('action')
    if action=='reject':
        key=body.get('request_key')
        if not isinstance(key,str) or not 12<=len(key)<=100:raise ValueError('A unique rejection identity is required')
        request_hash=digest(body)
        previous=next((r for r in tech.get('rejections',[]) if r['request_key']==key),None)
        if previous:
            if previous['request_hash']!=request_hash:raise ValueError('Rejection identity belongs to different feedback')
            return state
        if tech.get('status')!='proposal_ready':raise ValueError('No proposal is awaiting your decision')
        if not tech.get('proposal_hash') or body.get('proposal_hash')!=tech['proposal_hash']:raise ValueError('Reject the exact saved proposal; refresh if it changed')
        note=body.get('note','')
        if not isinstance(note,str) or len(note)>2000:raise ValueError('Keep rejection feedback within 2,000 characters')
        tech.setdefault('rejections',[]).append({'request_key':key,'request_hash':request_hash,'at':ws.now(),
            'proposal_hash':tech['proposal_hash'],'proposal':tech['proposal'],'reason':note.strip()})
        # Keep immutable evidence in history; remove stale approval targets.
        for field in ('proposal','proposal_hash','report','report_hash','release_report','repair_candidates','identity'):
            tech.pop(field,None)
        state['tech']=tech
        return submit(store,state,'technical_investigation',
            'The owner rejected the previous solution. Re-investigate and return a revised Problem / Solution / Risk recommendation. '+
            ('Owner objection: '+note.strip() if note.strip() else 'No further reason was supplied; reconsider the assumptions and alternatives.' ))
    if action=='approve_repair':
        if body.get('proposal_hash')!=tech.get('proposal_hash') or not tech.get('proposal_hash'):raise ValueError('Approve the exact saved proposal')
        if tech.get('status') in ('repair_queued','repairing','repair_ready'):return state
        if tech.get('status')!='proposal_ready':raise ValueError('Proposal is not ready for approval')
        if tech['proposal'].get('questions'):raise ValueError('Answer the proposal questions and request an updated proposal before approving a repair')
        approval={'kind':'development_repair','proposal_hash':tech['proposal_hash'],'at':ws.now(),
            'scope':'Implement and test this proposal on the development branch. No deployment, writer calls, policy activation or campaign edits.'}
        return submit(store,state,'technical_repair',approval=approval)
    if action=='approve_release':
        if body.get('report_hash')!=tech.get('report_hash') or not tech.get('report_hash'):raise ValueError('Approve the exact tested repair report')
        if tech.get('status') in ('release_queued','releasing','released'):return state
        if tech.get('status')!='repair_ready' or not tech.get('report',{}).get('ready'):raise ValueError('A tested repair must be ready before release')
        approval={'kind':'release','report_hash':tech['report_hash'],'commit_id':tech['report']['commit_id'],'at':ws.now(),
            'scope':'Publish only the tested repair to the existing NCCE preview and verify it. No writer calls, policy activation or campaign edits.'}
        return submit(store,state,'technical_release',approval=approval)
    raise ValueError('Unknown technical decision')


def started(store,payload):
    state=load(store,payload['run_id']);tech=state.get('tech',{})
    if tech.get('job_id')!=payload['job_id']:raise ValueError('Technical job was replaced')
    tech['status']={'technical_investigation':'investigating','technical_repair':'repairing','technical_release':'releasing'}[payload['kind']]
    save(store,state,'StoryTechMan started '+payload['kind'])


def complete(store,payload,result,identity):
    state=load(store,payload['run_id']);tech=state.get('tech',{})
    if tech.get('job_id')!=payload['job_id']:raise ValueError('Technical job was replaced')
    kind=payload['kind'];tech['identity']=identity
    if kind=='technical_investigation':tech.update(status='proposal_ready',proposal=result,proposal_hash=digest(result))
    elif kind=='technical_repair':
        tech.update(status='repair_ready' if result['ready'] else 'needs_input',report=result,report_hash=digest(result))
        if result['ready']:
            candidates={}
            for scope,field,original in [('shared','proposed_shared_instructions',state['shared']),(state['form'],'proposed_form_instructions',state['specific'])]:
                if result[field].strip():candidates[scope]=ws.save_revision(store,{**original,'instructions':result[field],'label':'StoryTechMan proposed '+scope+' repair'})['revision_id']
            tech['repair_candidates']=candidates
    else:tech.update(status='released' if result['ready'] else 'needs_input',release_report=result)
    from workshop_optimizer import activity
    activity(store,state,'decision','StoryTechMan',result['headline'])


def failed(store,payload,error):
    state=load(store,payload['run_id']);tech=state.get('tech',{})
    if tech.get('job_id')==payload['job_id']:
        tech.update(status='needs_input',error=error);save(store,state,'StoryTechMan needs human attention: '+error)
