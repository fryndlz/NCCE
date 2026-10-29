"""Real HTTP boundary tests with a mocked worker: no external or paid requests."""
import json,os,sys,tempfile,threading
import hashlib
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from store import Store
from test_story_engine import campaign,latest_game,apply
from access import make_session_token,effective_session_key

def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        db=Path(folder)/'test.db';seed=Store(db);before=campaign();apply(seed,before);apply(seed,latest_game(before));seed.close()
        bridge_token='disposable-bridge-token-for-http-tests-000000'
        os.environ.update(NCCE_DB_PATH=str(db),NCCE_REQUIRE_AUTH='0',NCCE_OPENAI_API_KEY='',NCCE_REVIEW_BRIDGE_TOKEN_SHA256=hashlib.sha256(bridge_token.encode()).hexdigest())
        import server,writer_workshop as ws
        import codex_review_queue as bridge
        bridge.heartbeat(server.store,{'thread_id':bridge.thread_id(),'worker_id':'http-test-worker'})
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.H)
        host='127.0.0.1:'+str(http.server_address[1]);base='http://'+host
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        client=build_opener(ProxyHandler({}))
        def call(path,body=None,cookie=None,origin=base,authorization=None):
            headers={'Content-Type':'application/json','Origin':origin}
            if cookie:headers['Cookie']='ncce_session='+cookie
            if authorization:headers['Authorization']=authorization
            req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with client.open(req,timeout=5) as response:return response.status,json.load(response)
            except HTTPError as error:return error.code,json.load(error)
        try:
            with patch.object(server.llm_writer,'API_KEY','mock-provider-key'):
                assert call('/api/workshop')[0]==403
                assert call('/api/workshop/generate',{})[0]==403
                assert call('/api/workshop/optimize',{})[0]==403
                assert call('/api/reviewer-bridge/claim',{})[0]==401
                assert call('/api/reviewer-bridge/events',{})[0]==401
                bridge_body={'thread_id':bridge.thread_id(),'worker_id':'http-test-worker'}
                assert call('/api/workshop/quality?scope=territory_origin')[0]==403
                assert call('/api/workshop/owner-verdict',{})[0]==403
                assert call('/api/workshop/optimization-resume',{})[0]==403
                assert call('/api/workshop/optimization-recover-review',{})[0]==403
                assert call('/api/reviewer-bridge/notified',{})[0]==401
                bearer='Bearer '+bridge_token
                assert call('/api/reviewer-bridge/claim',bridge_body,authorization=bearer)[0]==200
                assert call('/api/reviewer-bridge/events',{**bridge_body,'wait_seconds':0},authorization=bearer)[1]=={'job_id':None}
                assert call('/api/workshop/activate',{},authorization=bearer)[0]==403
                assert server.store.db.execute('SELECT count(*) FROM workshop_trials').fetchone()[0]==0
                server.AUTH_REQUIRED=True;server.SESSION_KEY=effective_session_key('disposable-password','disposable-test-secret')
                cookie=make_session_token(server.SESSION_KEY)
                # An idle event wait must not block owner reads or review callbacks.
                entered=threading.Event(); event_result=[]; original_sleep=bridge.time.sleep
                def waiting(delay):
                    entered.set();original_sleep(delay)
                with patch.object(bridge.time,'sleep',side_effect=waiting):
                    waiter=threading.Thread(target=lambda:event_result.append(call('/api/reviewer-bridge/events',{**bridge_body,'wait_seconds':2},authorization=bearer)))
                    waiter.start();assert entered.wait(2)
                    assert call('/api/workshop/optimizations',cookie=cookie)[0]==200
                    assert waiter.is_alive(), 'Idle listener held the shared database lock'
                    waiter.join(4);assert event_result[0][0]==200

                assert call('/api/workshop/guidelines?scope=fighter_memory')[0]==401
                assert call('/api/workshop')[0]==401
                assert call('/api/workshop/generate',{})[0]==401
                assert call('/api/workshop/optimize',{})[0]==401
                assert call('/api/workshop/optimization-decide',{},cookie,'https://foreign.invalid')[0]==403
                assert call('/api/workshop/generate',{},cookie,'https://foreign.invalid')[0]==403
                assert call('/api/workshop/generate',{},cookie,'')[0]==403
                status,home=call('/api/workshop',cookie=cookie);assert status==200 and home['samples']
                assert call('/api/workshop/guidelines?scope=unknown',cookie=cookie)[0]==400
                status,library=call('/api/workshop/guidelines?scope=fighter_memory',cookie=cookie)
                assert status==200 and library['scope']=='fighter_memory' and library['active']['instructions']
                source=next(s for s in home['samples'] if s['form']=='fighter_memory')
                body={'sample_key':source['key'],'request_key':'http-once-000000000000'}
                server._writer_pipeline_guard.acquire()
                assert call('/api/workshop/generate',body,cookie)[0]==409
                server._writer_pipeline_guard.release()
                launches=[]; launched=threading.Event()
                def fake_worker(tid):
                    launches.append(tid);server._writer_pipeline_guard.release();launched.set()
                with patch.object(server,'_run_workshop',side_effect=fake_worker):
                    code,first=call('/api/workshop/generate',body,cookie)
                    assert code==202 and launched.wait(2)
                    code,second=call('/api/workshop/generate',body,cookie)
                    assert code==200 and first['trial_id']==second['trial_id'] and len(launches)==1
                assert server.store.db.execute('SELECT count(*) FROM workshop_trials').fetchone()[0]==1
                assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0
                import editorial_quality
                candidate=ws.save_revision(server.store,{**ws.defaults(source['form']),'instructions':editorial_quality.seed_brief(source['form'])})
                optimization={'sample_key':source['key'],'request_key':'http-optimizer-00000000','max_rounds':1,'allow_paid':True,
                              'form_revision_id':candidate['revision_id'],'hypothesis':'Test clearer subject focus against current instructions.'}
                assert call('/api/workshop/optimize',{**optimization,'allow_paid':False},cookie)[0]==400
                server._writer_pipeline_guard.acquire()
                assert call('/api/workshop/optimize',optimization,cookie)[0]==409
                server._writer_pipeline_guard.release()
                assert call('/api/workshop/optimize',optimization,cookie)[0]==400, 'Heartbeat without actual review must block spending'
                from test_workshop_optimizer import ready_bridge
                ready_bridge(server.store)
                assert call('/api/workshop/optimization-resume',{'run_id':'missing','allow_remaining':True},cookie,'https://foreign.invalid')[0]==403
                launched.clear(); optimizer_launches=[]
                def optimizer_worker(run_id):
                    optimizer_launches.append(run_id);server._writer_pipeline_guard.release();launched.set()
                with patch.object(server,'_run_optimization',side_effect=optimizer_worker):
                    code,first=call('/api/workshop/optimize',optimization,cookie)
                    assert code==202 and launched.wait(2)
                    code,second=call('/api/workshop/optimize',optimization,cookie)
                    assert code==200 and first['run_id']==second['run_id'] and len(optimizer_launches)==1
                assert call('/api/workshop/optimization?run_id='+first['run_id'],cookie=cookie)[0]==200
                assert call('/api/workshop/optimization-decide',{'run_id':first['run_id'],'approve':True},cookie)[0]==400
                assert call('/api/workshop/optimization-stop',{'run_id':first['run_id']},cookie)[1]['stop_requested']
                assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0
                assert server.store.db.execute('SELECT count(*) FROM workshop_review_requests').fetchone()[0]==0
                assert call('/api/workshop/optimizations',cookie=cookie)[0]==200
                from test_workshop_decisions import proposal
                import workshop_interventions as interventions
                state=server.workshop_optimizer.get(server.store,first['run_id']);state['status']='awaiting_next_round';server.workshop_optimizer.save(server.store,state)
                grant={'run_id':state['run_id'],'request_key':'http-round-grant-000001','additional_rounds':1,'allow_paid':True}
                assert call('/api/workshop/optimization-continue',{**grant,'allow_paid':False},cookie)[0]==400
                optimizer_launches.clear();launched.clear()
                with patch.object(server,'_run_optimization',side_effect=optimizer_worker):
                    code,next_run=call('/api/workshop/optimization-continue',grant,cookie);assert code==202 and launched.wait(2)
                    assert call('/api/workshop/optimization-continue',grant,cookie)[0]==200 and len(optimizer_launches)==1
                next_run['status']='awaiting_next_round';server.workshop_optimizer.save(server.store,next_run)
                # A real v3 execution with fake providers: owner sees blind prose
                # before reviews, then a durable reveal. No model invocation.
                from test_editorial_quality import fake_generator,review
                next_run['status']='queued';next_run['max_rounds']=1;server.workshop_optimizer.save(server.store,next_run)
                compared=server.workshop_optimizer.execute(server.store,next_run['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p))
                assert compared['status']=='awaiting_owner'
                visible=call('/api/workshop/optimization?run_id='+compared['run_id'],cookie=cookie)[1]
                assert visible['rounds'][0]['pairs'][0]['review'] is None
                assert 'candidate_index' not in visible['rounds'][0]['pairs'][0]
                assert call('/api/workshop/quality?scope=fighter_memory',cookie=cookie)[1]['calibration']['fresh_pairs']==0
                for i,pair in enumerate(compared['rounds'][0]['pairs']):
                    ballot={'run_id':compared['run_id'],'round':1,'pair':i,'preference':pair['review']['preference'],'acceptable':[True,True]}
                    assert call('/api/workshop/owner-verdict',ballot)[0]==401
                    assert call('/api/workshop/owner-verdict',ballot,cookie,'https://foreign.invalid')[0]==403
                    assert call('/api/workshop/owner-verdict',ballot,cookie)[0]==200
                    assert call('/api/workshop/owner-verdict',ballot,cookie)[0]==200
                visible=call('/api/workshop/optimization?run_id='+compared['run_id'],cookie=cookie)[1]
                assert visible['rounds'][0]['pairs'][0]['review']['preference']
                assert call('/api/workshop/optimization-checkpoint',{'run_id':compared['run_id']},cookie)[1]['status']=='awaiting_next_round'
                investigation={'run_id':state['run_id'],'request_key':'http-tech-investigation-0001','note':'Investigate the reusable input setup'}
                assert call('/api/workshop/optimization-investigate',investigation,authorization=bearer)[0]==401
                assert call('/api/workshop/optimization-investigate',investigation,cookie,'https://foreign.invalid')[0]==403
                code,case=call('/api/workshop/optimization-investigate',investigation,cookie);assert code==200
                assert call('/api/workshop/optimization-investigate',investigation,cookie)[1]['tech']['job_id']==case['tech']['job_id']
                tech_body={'thread_id':interventions.TECH_THREAD_ID,'worker_id':'http-storytech-worker','job_id':case['tech']['job_id']}
                claimed=call('/api/reviewer-bridge/claim',tech_body,authorization=bearer)[1]
                leased={**tech_body,'lease':claimed['lease'],'turn_id':'real-http-native-turn'}
                assert call('/api/reviewer-bridge/started',leased,authorization=bearer)[0]==200
                assert call('/api/reviewer-bridge/complete',{**leased,'review':proposal()},authorization=bearer)[0]==200
                case=call('/api/workshop/optimization?run_id='+state['run_id'],cookie=cookie)[1]
                approve={'run_id':state['run_id'],'action':'approve_repair','proposal_hash':case['tech']['proposal_hash']}
                assert call('/api/workshop/optimization-technical-decision',{**approve,'proposal_hash':'wrong'},cookie)[0]==400
                assert call('/api/workshop/optimization-technical-decision',approve,cookie)[1]['tech']['status']=='repair_queued'
                assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0

                # Manual library activation is owner-authenticated and excluded from in-flight writing.
                import workshop_guidelines as guidelines
                library=guidelines.library(server.store,'fighter_memory')
                event=next(e for e in library['timeline'] if e['kind']=='saved')
                selection={'scope':'fighter_memory','event_id':event['event_id'],'content_hash':event['content_hash'],'expected_active':library['active']['revision_id'],'request_key':'http-manual-activation-0001'}
                assert call('/api/workshop/guidelines-activate',selection)[0]==401
                assert call('/api/workshop/guidelines-activate',selection,cookie,'https://foreign.invalid')[0]==403
                server._writer_pipeline_guard.acquire()
                assert call('/api/workshop/guidelines-activate',selection,cookie)[0]==409
                server._writer_pipeline_guard.release()
                code,updated=call('/api/workshop/guidelines-activate',selection,cookie)
                assert code==200 and updated['active']['revision_id']==event['revision_id']
                assert call('/api/workshop/guidelines-activate',selection,cookie)[0]==200
                assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0

                # Explicit saved-draft recovery: auth/origin, pipeline guard and
                # duplicate HTTP delivery cannot enqueue a second native job.
                from test_review_delivery import interrupted,recovery_body
                paused=interrupted(server.store); recover_body=recovery_body(paused)
                requests_before=server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]
                assert call('/api/workshop/optimization-recover-review',recover_body)[0]==401
                assert call('/api/workshop/optimization-recover-review',recover_body,cookie,'https://foreign.invalid')[0]==403
                assert call('/api/workshop/optimization-recover-review',{'run_id':paused['run_id']},cookie)[0]==400
                server._writer_pipeline_guard.acquire()
                assert call('/api/workshop/optimization-recover-review',recover_body,cookie)[0]==409
                server._writer_pipeline_guard.release()
                launched.clear();optimizer_launches.clear()
                with patch.object(server,'_run_optimization',side_effect=optimizer_worker):
                    code,recovered=call('/api/workshop/optimization-recover-review',recover_body,cookie)
                    assert code==202 and launched.wait(2)
                    assert call('/api/workshop/optimization-recover-review',recover_body,cookie)[0]==200
                    assert len(optimizer_launches)==1
                assert recovered['review_delivery_recovery']['original_job_id']==recover_body['job_id']
                assert server.store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==requests_before

            print('HTTP workshop passed: auth mandatory, cross-origin denied, busy rejected, duplicate key queued once, no paid calls')
        finally:http.shutdown();http.server_close();thread.join();server.store.close()

if __name__=='__main__':main()
