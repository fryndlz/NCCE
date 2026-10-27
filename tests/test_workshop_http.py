"""Real HTTP boundary tests with a mocked worker: no external or paid requests."""
import json,os,sys,tempfile,threading
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
        os.environ.update(NCCE_DB_PATH=str(db),NCCE_REQUIRE_AUTH='0',NCCE_OPENAI_API_KEY='',NCCE_REVIEW_BRIDGE_TOKEN='disposable-bridge-token-for-http-tests-000000')
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
                bridge_body={'thread_id':bridge.thread_id(),'worker_id':'http-test-worker'}
                bearer='Bearer '+os.environ['NCCE_REVIEW_BRIDGE_TOKEN']
                assert call('/api/reviewer-bridge/claim',bridge_body,authorization=bearer)[0]==200
                assert call('/api/workshop/activate',{},authorization=bearer)[0]==403
                assert server.store.db.execute('SELECT count(*) FROM workshop_trials').fetchone()[0]==0
                server.AUTH_REQUIRED=True;server.SESSION_KEY=effective_session_key('disposable-password','disposable-test-secret')
                cookie=make_session_token(server.SESSION_KEY)
                assert call('/api/workshop')[0]==401
                assert call('/api/workshop/generate',{})[0]==401
                assert call('/api/workshop/optimize',{})[0]==401
                assert call('/api/workshop/optimization-decide',{},cookie,'https://foreign.invalid')[0]==403
                assert call('/api/workshop/generate',{},cookie,'https://foreign.invalid')[0]==403
                assert call('/api/workshop/generate',{},cookie,'')[0]==403
                status,home=call('/api/workshop',cookie=cookie);assert status==200 and home['samples']
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
                optimization={'sample_key':source['key'],'request_key':'http-optimizer-00000000','max_rounds':1,'allow_paid':True}
                assert call('/api/workshop/optimize',{**optimization,'allow_paid':False},cookie)[0]==400
                server._writer_pipeline_guard.acquire()
                assert call('/api/workshop/optimize',optimization,cookie)[0]==409
                server._writer_pipeline_guard.release()
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
            print('HTTP workshop passed: auth mandatory, cross-origin denied, busy rejected, duplicate key queued once, no paid calls')
        finally:http.shutdown();http.server_close();thread.join();server.store.close()

if __name__=='__main__':main()
