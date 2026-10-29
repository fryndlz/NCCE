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
from test_workshop_optimizer import assessment,body,rejects,ready_bridge
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
        cq.heartbeat(store,identity());assert not cq.status(store)['online'], 'Heartbeat is not proof the actual chat can review'
        with patch.object(writer,'API_KEY','mock'):rejects(lambda:opt.queue(store,request))
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
        assert cq.status(store)['online']
        changed=assessment(7);rejects(lambda:cq.complete(store,{**value,'review':changed}))
        result=json.loads(cq.get(store,check_job['job_id'])['result_json'])
        assert result['_codex']['thread_id']==cq.thread_id() and result['_codex']['turn_id']=='turn-real'
        assert store.db.execute('SELECT count(*) FROM workshop_active').fetchone()[0]==0
        assert store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0
    with_store(check)


def test_failed_diagnostic_stays_offline_despite_fresh_heartbeat():
    def check(store):
        job=cq.self_test(store,{})['job_id'];claimed=cq.claim(store,identity())
        cq.fail(store,{**identity(),'job_id':job,'lease':claimed['lease'],'error':'Codex chat already has an active writer'})
        cq.heartbeat(store,identity())
        current=cq.status(store)
        assert not current['online'] and not current['verified']
        assert 'active writer' in current['connection_error']
        request=body(store)
        before=store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]
        with patch.object(writer,'API_KEY','mock'):rejects(lambda:opt.queue(store,request))
        assert store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==before
    with_store(check)


def test_native_chat_retry_preserves_failed_attempt_and_poll_expiry():
    def check(store):
        first=cq.self_test(store,{})['job_id'];claimed=cq.claim(store,identity())
        cq.fail(store,{**identity(),'job_id':first,'lease':claimed['lease'],'error':'Old transport failed'})
        second=cq.self_test(store,{'new_attempt':True})['job_id']
        assert second!=first and cq.get(store,first)['status']=='failed'
        rejects(lambda:cq.self_test(store,{'new_attempt':True}))
        claimed=cq.claim(store,identity());lease={**identity(),'job_id':second,'lease':claimed['lease'],'turn_id':'native-turn'}
        cq.started(store,lease);cq.complete(store,{**lease,'review':assessment()})
        cq.heartbeat(store,{**identity(),'transport':'codex_chat','poll_interval':300})
        assert cq.status(store)['online'] and cq.status(store)['transport']=='codex_chat'
        with patch('codex_review_queue.time.time',return_value=time.time()+301):assert cq.status(store)['online']
        with patch('codex_review_queue.time.time',return_value=time.time()+361):assert not cq.status(store)['online']
    with_store(check)


def test_waiter_lights_only_after_actual_codex_turn_start_and_returns_review():
    def check(store):
        ready_bridge(store);request=body(store)
        with patch.object(writer,'API_KEY','mock'):state,_=opt.queue(store,request)
        state['workflow_version']=2  # Historical transport-only fixture; v3 payloads have dedicated tests.
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


def test_native_helper_never_starts_model_or_discloses_lease_and_no_replay():
    sys.path.insert(0,str(ROOT/'scripts'))
    from codex_chat_worker import ChatWorker
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        path=Path(folder)/'config.json'
        path.write_text(json.dumps({'base_url':'http://localhost','worker_id':'native-test-worker','thread_id':cq.THREAD_ID,'token':TOKEN,'codex_executable':'codex'}))
        worker=ChatWorker(path);sent=[]
        def post(action,body=None):
            sent.append((action,body))
            return {'job':{'job_id':'native-job','output_schema':opt.review_schema()},'lease':'private-lease'} if action=='claim' else {'ok':True}
        worker.post=post
        with patch('subprocess.Popen',side_effect=AssertionError('Native chat must not spawn a model')):
            reply=worker.claim('actual-native-turn')
            assert 'private-lease' not in json.dumps(reply) and TOKEN not in json.dumps(reply)
            try:worker.claim('another-turn')
            except RuntimeError:pass
            else:raise AssertionError('Unfinished native review replayed')
            worker.finish(review=assessment())
        complete=next(b for a,b in sent if a=='complete')
        assert complete['turn_id']=='actual-native-turn' and complete['lease']=='private-lease'


def test_event_wait_never_claims_and_exact_job_claim_ignores_cancelled():
    def check(store):
        assert cq.events(store,{**identity(),'wait_seconds':0})=={'job_id':None}
        job=cq.self_test(store,{})['job_id']
        assert cq.events(store,{**identity(),'wait_seconds':0})=={'job_id':job,'kind':'review','thread_id':cq.thread_id()}
        assert cq.get(store,job)['status']=='queued'
        assert cq.claim(store,{**identity(),'job_id':'unknown'})['job'] is None
        cq.cancel(store,job,'Owner cancelled before wake')
        assert cq.claim(store,{**identity(),'job_id':job})['job'] is None
    with_store(check)


def test_event_listener_idle_is_free_and_restart_never_duplicates_model_wake():
    sys.path.insert(0,str(ROOT/'scripts'))
    from codex_event_listener import EventListener
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        path=Path(folder)/'config.json'
        path.write_text(json.dumps({'base_url':'http://localhost','worker_id':'event-test-worker','thread_id':cq.THREAD_ID,'token':TOKEN,'codex_executable':'codex'}))
        listener=EventListener(path);listener.post=lambda *a,**k:{'job_id':None}
        with patch('subprocess.run') as run:
            for _ in range(5):assert listener.tick() is False
            run.assert_not_called()
        listener.post=lambda *a,**k:{'job_id':'review-event-test'}
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as run,patch('codex_event_listener.time.sleep'):
            assert listener.tick() is True
            assert listener.tick() is False
            restarted=EventListener(path);restarted.post=listener.post;assert restarted.tick() is False
            assert run.call_count==1
            argv=run.call_args[0][0]
            assert argv[1:4]==['queue','--thread',cq.THREAD_ID]
            assert TOKEN not in ' '.join(argv) and '--job-id review-event-test' in argv[-1]
        # Uncertain command output never causes a second automatic wake.
        listener.post=lambda *a,**k:{'job_id':'review-uncertain'}
        with patch('subprocess.run',side_effect=TimeoutError('uncertain')) as run:
            for _ in range(2):
                try:listener.tick()
                except (RuntimeError,TimeoutError):pass
                else:raise AssertionError('Uncertain wake replayed')
            assert run.call_count==1


def test_listener_routes_only_known_technical_thread_without_idle_model_calls():
    sys.path.insert(0,str(ROOT/'scripts'))
    from codex_event_listener import EventListener
    from workshop_interventions import TECH_THREAD_ID
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        path=Path(folder)/'config.json'
        path.write_text(json.dumps({'base_url':'http://localhost','worker_id':'event-test-worker','thread_id':cq.THREAD_ID,'storytech_thread_id':TECH_THREAD_ID,'token':TOKEN,'codex_executable':'codex'}))
        listener=EventListener(path)
        listener.post=lambda *a,**k:{'job_id':'tech-test','kind':'technical_investigation','thread_id':TECH_THREAD_ID}
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
            assert listener.tick();args=run.call_args[0][0]
            assert args[3]==TECH_THREAD_ID and 'Investigations are READ ONLY' in args[-1]
        listener.post=lambda *a,**k:{'job_id':'tech-wrong','kind':'technical_investigation','thread_id':'wrong-thread'}
        with patch('subprocess.run') as run:
            try:listener.tick()
            except ValueError:pass
            else:raise AssertionError('Unknown technical target accepted')
            run.assert_not_called()


def test_rejected_completion_stops_waiter_but_network_uncertainty_does_not_retry():
    sys.path.insert(0,str(ROOT/'scripts'))
    import codex_chat_worker as worker_module
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        worker=object.__new__(worker_module.ChatWorker)
        worker.active=Path(folder)/'active.json'
        initial={'job_id':'retained-review','lease':'private-test-lease','turn_id':'native-turn','status':'reviewing'}
        for status in (400,503):
            worker.save(initial);calls=[]
            def post(action,body):
                calls.append(action)
                if action=='complete':raise worker_module.BridgeRequestError(action,status,'Rejected assessment')
                return {'ok':True}
            worker.post=post
            try:worker.finish(review={'saved':'review'})
            except worker_module.BridgeRequestError:pass
            else:raise AssertionError('Submission rejection was hidden')
            assert calls==(['complete','fail','heartbeat'] if status==400 else ['complete'])
            assert json.loads(worker.active.read_text())['status']==('failed' if status==400 else 'reviewing')


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
