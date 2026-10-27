"""Queue ownership, cancellation, real-state handoff and companion dispatch without models."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import codex_review_queue as cq
import workshop_optimizer as opt
import llm_writer as writer
from test_writer_pipeline import with_store as base_store
from test_workshop_optimizer import assessment,body,rejects
spec=importlib.util.spec_from_file_location('companion',ROOT/'scripts'/'codex_review_bridge.py')
companion=importlib.util.module_from_spec(spec);spec.loader.exec_module(companion)
TOKEN='bridge-test-only-'*4


def with_store(check):
    def run(store):
        with patch.dict(os.environ,{'NCCE_REVIEW_BRIDGE_TOKEN_SHA256':hashlib.sha256(TOKEN.encode()).hexdigest()}):check(store)
    base_store(run)


def identity():return {'thread_id':cq.thread_id(),'worker_id':'worker-test-001'}


def test_scoped_auth_offline_and_claim_result_ownership():
    def check(store):
        assert not cq.authenticated('Bearer wrong') and cq.authenticated('Bearer '+TOKEN)
        assert not cq.authenticated('Bearer '+hashlib.sha256(TOKEN.encode()).hexdigest()), 'Verifier hash must not be usable as a credential'
        assert not cq.status(store)['online']
        request=body(store)
        with patch.object(writer,'API_KEY','mock'):rejects(lambda:opt.queue(store,request))
        cq.heartbeat(store,identity());assert cq.status(store)['online']
        with patch('codex_review_queue.time.time',return_value=time.time()+100):assert not cq.status(store)['online']
        rejects(lambda:cq.heartbeat(store,{**identity(),'thread_id':'wrong'}))
        check_job=cq.self_test(store,{})
        assert cq.self_test(store,{})['job_id']==check_job['job_id']
        claimed=cq.claim(store,identity());assert claimed['job']['job_id']==check_job['job_id']
        lease={**identity(),'job_id':check_job['job_id'],'lease':claimed['lease']}
        assert cq.claim(store,identity())['job'] is None
        rejects(lambda:cq.complete(store,{**lease,'lease':'wrong','review':assessment(),'turn_id':'turn-real'}))
        rejects(lambda:cq.complete(store,{**lease,'review':assessment(),'turn_id':'turn-real'}))
        cq.started(store,{**lease,'turn_id':'turn-real'})
        assert cq.heartbeat(store,{**lease,'state':'reviewing'})['job_status']=='reviewing'
        value={**lease,'review':assessment(),'turn_id':'turn-real'}
        assert cq.complete(store,value)['ok'];assert cq.complete(store,value)['ok']
        changed=assessment(7);rejects(lambda:cq.complete(store,{**value,'review':changed}))
        result=json.loads(cq.get(store,check_job['job_id'])['result_json'])
        assert result['_codex']['thread_id']==cq.thread_id() and result['_codex']['turn_id']=='turn-real'
        assert store.db.execute('SELECT count(*) FROM workshop_active').fetchone()[0]==0
        assert store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0
    with_store(check)


def test_waiter_lights_only_after_actual_codex_turn_start_and_returns_review():
    def check(store):
        cq.heartbeat(store,identity());request=body(store)
        with patch.object(writer,'API_KEY','mock'):state,_=opt.queue(store,request)
        pair={'instructions':'protected','packet':{},'candidates':[]}
        observations=[]
        def poll_delay(_seconds):
            # Execute on the same store to avoid concurrent connection use.
            observations.append(opt.get(store,state['run_id'])['activity']['phase'])
            if len(observations)==1:
                claim=cq.claim(store,identity());pair['_lease']=claim['lease']
                assert observations[-1]=='awaiting_reviewer'
                cq.started(store,{**identity(),'job_id':claim['job']['job_id'],'lease':claim['lease'],'turn_id':'actual-turn'})
            else:
                assert observations[-1]=='review'
                cq.complete(store,{**identity(),'job_id':pair['codex_job_id'],'lease':pair['_lease'],'turn_id':'actual-turn','review':assessment()})
        with patch.object(opt.time,'sleep',side_effect=poll_delay):result=opt.review_pair(store,state,pair,[])
        assert result['_codex']['turn_id']=='actual-turn'
        assert observations==['awaiting_reviewer','review']
    with_store(check)


def test_cancelled_job_never_accepts_result_and_restart_never_replays():
    def check(store):
        job=cq.self_test(store,{})['job_id'];claim=cq.claim(store,identity())
        lease={**identity(),'job_id':job,'lease':claim['lease']}
        cq.started(store,{**lease,'turn_id':'turn'})
        cq.cancel(store,job,'owner stopped')
        assert cq.heartbeat(store,{**lease,'state':'reviewing'})['job_status']=='cancelled'
        rejects(lambda:cq.complete(store,{**lease,'turn_id':'turn','review':assessment()}))
        assert cq.claim(store,identity())['job'] is None
        opt.recover(store);assert cq.get(store,job)['status']=='cancelled'
    with_store(check)


def test_companion_uses_actual_thread_no_model_override_and_durable_no_replay():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        folder=Path(directory);notes=folder/'notes';notes.mkdir();(notes/'feedback.jsonl').write_text('Owner prefers concrete consequences.')
        config={'base_url':'http://127.0.0.1:9999','worker_id':'worker-test-001','thread_id':cq.THREAD_ID,'token':TOKEN,'context_dir':str(notes),'codex_executable':'codex'}
        path=folder/'config.json';path.write_text(json.dumps(config))
        worker=companion.Companion(path);sent=[]
        def post(action,body=None):
            sent.append((action,body));return {'job_status':'reviewing'}
        worker.post=post
        class FakeRpc:
            def __init__(self):self.events=queue.Queue();self.calls=[]
            def call(self,method,params):
                self.calls.append((method,params))
                if method=='turn/start':
                    self.events.put({'method':'item/completed','params':{'threadId':cq.THREAD_ID,'item':{'type':'agentMessage','phase':'final_answer','text':json.dumps(assessment())}}})
                    self.events.put({'method':'turn/completed','params':{'threadId':cq.THREAD_ID,'turn':{'id':'actual-turn','status':'completed'}}})
                    return {'turn':{'id':'actual-turn'}}
                return {}
        rpc=FakeRpc();job={'job_id':'review-test','output_schema':opt.review_schema(),'packet':{'subject':'fixture'}}
        worker.perform(rpc,job,'lease')
        assert [m for m,_ in rpc.calls]==['thread/resume','turn/start']
        params=rpc.calls[1][1];assert params['threadId']==cq.THREAD_ID and 'model' not in params
        assert 'Owner prefers concrete consequences.' in params['input'][0]['text']
        assert sent[-1][0]=='complete' and sent[-1][1]['turn_id']=='actual-turn'
        try:worker.perform(rpc,job,'lease')
        except RuntimeError:pass
        else:raise AssertionError('Completed/uncertain job replayed')


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
