"""Category calibration and owner technical decisions: all models mocked."""
import sys,json,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import workshop_optimizer as opt
import workshop_interventions as tech
import codex_review_queue as cq
import writer_workshop as ws
import llm_writer as writer
from test_workshop_optimizer import with_store,body,assessment,rejects,fake_call


def proposal(questions=None):
 return {'headline':'Supply the missing verified context','summary':'Investigate reusable input preparation, not individual prose.',
  'findings':[{'problem':'The packet lacks a required reference','evidence':'Exact saved field is empty','uncertainty':'The canonical source must be verified'}],
  'proposed_changes':['Supply a verified reference with provenance'],'validation_plan':['Assert the actual provider packet includes it'],
  'risks':['Do not turn generated prose into canon'],'questions':questions or []}


def report(ready=True):
 return {'headline':'Tested development repair','summary':'Reusable context preparation repaired.','changes':['Added verified context'],
  'tests':['Relevant context boundary test passed'],'files':['src/narrative_context.py'],'limitations':['No paid generation performed'],
  'proposed_shared_instructions':'','proposed_form_instructions':'','commit_id':'1'*40,'ready':ready}


def identity():return {'thread_id':tech.TECH_THREAD_ID,'worker_id':'storytech-test-worker'}
def claim_tech(store,job_id):
 claimed=cq.claim(store,{**identity(),'job_id':job_id});assert claimed['job']
 lease={**identity(),'job_id':job_id,'lease':claimed['lease'],'turn_id':'real-native-tech-turn'}
 cq.started(store,lease)
 return claimed['job'],lease


def test_whole_round_grants_candidate_saved_and_fresh_validation_before_activation():
 def check(store):
  request=body(store,1)
  with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake_call) as provider:
   state,_=opt.queue(store,request);rid=state['run_id']
   first=opt.execute(store,rid,reviewer=lambda *a:assessment(7))
   frozen=copy.deepcopy(first['rounds'][0]['pairs'])
   assert first['status']=='awaiting_next_round' and provider.call_count==4
   assert first['specific']['instructions']==assessment(7)['proposed_form_instructions'] and len(first['prompt_history'])==1
   assert not store.db.execute("SELECT 1 FROM codex_review_jobs WHERE json_extract(payload_json,'$.kind')='technical_investigation'").fetchone()
   decision={'run_id':rid,'request_key':'grant-one-000000001','additional_rounds':1,'allow_paid':True}
   rejects(lambda:opt.continue_run(store,{**decision,'allow_paid':False}))
   _,fresh=opt.continue_run(store,decision);assert fresh
   second=opt.execute(store,rid,reviewer=lambda *a:assessment(9))
   assert second['status']=='awaiting_next_round' and second['validation_pending'] and provider.call_count==8
   assert second['rounds'][0]['pairs']==frozen
   assert opt.continue_run(store,decision)[1] is False
   rejects(lambda:opt.continue_run(store,{**decision,'additional_rounds':2}))
   rejects(lambda:opt.decide(store,{'run_id':rid,'approve':True}))
   opt.continue_run(store,{**decision,'request_key':'grant-two-000000002'})
   final=opt.execute(store,rid,reviewer=lambda *a:assessment(9))
   assert final['status']=='awaiting_approval' and provider.call_count==12
   pairs=[p for r in final['rounds'] for p in r['pairs']]
   assert len({p['sample_key'] for p in pairs})==6 and len({p['packet_hash'] for p in pairs})==6
   assert final['rounds'][2]['kind']=='validation'
   assert final['rounds'][1]['revision_id']==final['rounds'][2]['revision_id']
   assert final['writer_reserved']==12 and final['reviewer_reserved']==6
   assert ws.active(store,'fighter_memory') is None
   with patch.object(opt,'environment_fingerprint',return_value='changed'):rejects(lambda:opt.decide(store,{'run_id':rid,'approve':True}))
   rejects(lambda:opt.decide(store,{'run_id':rid,'approve':True}));assert ws.active(store,'fighter_memory') is None
 with_store(check)


def test_no_fresh_validation_sources_pauses_without_more_calls():
 def check(store):
  request=body(store,2)
  with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake_call) as provider:
   state,_=opt.queue(store,request)
   allowed={s['key'] for s in state['samples']};catalog=[x for x in ws.catalog(store) if x['key'] in allowed]
   with patch.object(ws,'catalog',return_value=catalog):result=opt.execute(store,state['run_id'],reviewer=lambda *a:assessment(9))
   assert result['status']=='awaiting_samples' and provider.call_count==4
   assert not result.get('validated') and ws.active(store,'fighter_memory') is None
 with_store(check)


def test_context_handoff_real_proposal_and_separate_repair_release_approvals():
 def check(store):
  request=body(store,3)
  with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake_call) as provider:
   state,_=opt.queue(store,request);rid=state['run_id']
   state=opt.execute(store,rid,reviewer=lambda *a:assessment(9,'context'))
   assert state['status']=='escalated' and state['tech']['status']=='queued' and provider.call_count==2
   job_id=state['tech']['job_id']
   assert cq.claim(store,{'thread_id':cq.thread_id(),'worker_id':'reviewer-test-worker','job_id':job_id})['job'] is None
   job,lease=claim_tech(store,job_id)
   assert job['kind']=='technical_investigation' and job['packet']['rounds'][0]['pairs'][0]['instructions']
   rejects(lambda:cq.complete(store,{**lease,'thread_id':cq.thread_id(),'review':proposal()}))
   cq.complete(store,{**lease,'review':proposal()})
   state=opt.get(store,rid);assert state['tech']['status']=='proposal_ready'
   assert ws.active(store,'fighter_memory') is None and provider.call_count==2
   rejects(lambda:tech.decision(store,{'run_id':rid,'action':'approve_repair','proposal_hash':'wrong'}))
   approved={'run_id':rid,'action':'approve_repair','proposal_hash':state['tech']['proposal_hash']}
   state=tech.decision(store,approved);repair_id=state['tech']['job_id']
   assert tech.decision(store,approved)['tech']['job_id']==repair_id
   job,lease=claim_tech(store,repair_id)
   assert job['approval']['kind']=='development_repair' and job['approval']['proposal_hash']==approved['proposal_hash']
   rejects(lambda:tech.decision(store,{'run_id':rid,'action':'approve_release','report_hash':'wrong'}))
   repair=report();repair['proposed_shared_instructions']='A repaired reusable shared draft.'
   cq.complete(store,{**lease,'review':repair});state=opt.get(store,rid)
   assert ws.revision(store,state['tech']['repair_candidates']['shared'])['instructions']=='A repaired reusable shared draft.'
   assert ws.active(store,'shared') is None
   assert state['tech']['status']=='repair_ready' and provider.call_count==2
   release={'run_id':rid,'action':'approve_release','report_hash':state['tech']['report_hash']}
   state=tech.decision(store,release);job,lease=claim_tech(store,state['tech']['job_id'])
   assert job['approval']['commit_id']=='1'*40
   opt.recover(store);assert cq.get(store,job['job_id'])['status']=='reviewing','Approved release must retain its lease across its own restart'
   cq.complete(store,{**lease,'review':report()});assert opt.get(store,rid)['tech']['status']=='released'
   assert ws.active(store,'fighter_memory') is None and provider.call_count==2
   closed=opt.get(store,rid);closed['status']='awaiting_next_round';opt.save(store,closed)
   rejects(lambda:opt.continue_run(store,{'run_id':rid,'request_key':'must-start-new-study-0001','allow_paid':True,'additional_rounds':1}))
 with_store(check)


def test_questions_need_answers_and_more_rounds_do_not_bypass_investigation():
 def check(store):
  request=body(store,1)
  with patch.object(writer,'API_KEY','mock'):
   state,_=opt.queue(store,request);rid=state['run_id'];state['status']='awaiting_next_round';opt.save(store,state)
   state=tech.investigate(store,{'run_id':rid,'request_key':'manual-investigation-0001','note':'Why does the category repeat?'})
   rejects(lambda:opt.continue_run(store,{'run_id':rid,'request_key':'grant-blocked-00001','additional_rounds':1,'allow_paid':True}))
   _,lease=claim_tech(store,state['tech']['job_id']);cq.complete(store,{**lease,'review':proposal(['Which verified source is authoritative?'])})
   state=opt.get(store,rid)
   rejects(lambda:tech.decision(store,{'run_id':rid,'action':'approve_repair','proposal_hash':state['tech']['proposal_hash']}))
   next_state=tech.investigate(store,{'run_id':rid,'request_key':'manual-investigation-0002','note':'Use the approved canonical source.'})
   packet=json.loads(cq.get(store,next_state['tech']['job_id'])['payload_json'])['packet']
   assert packet['proposal']['questions'] and packet['note']=='Use the approved canonical source.'
 with_store(check)


if __name__=='__main__':
 for name,test in sorted(list(globals().items())):
  if name.startswith('test_') and callable(test):test();print('PASS',name)
