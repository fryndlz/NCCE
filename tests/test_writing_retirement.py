"""Retirement is permanent in code, preserves prose, and closes every old API.

Run normally for offline checks; add --http for disposable authenticated HTTP.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from contextlib import closing
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from store import Store
from writing_retirement import retire,public_state,MARKER
import llm_writer as writer
from test_story_engine import campaign,apply,latest_game
from story_engine import document_for,regenerate,read_memories


def test_retirement_cancels_work_preserves_audit_and_verified_backup():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=Store(Path(folder)/'test.db')
        try:
            apply(store,campaign())
            store.set_state('category-policy:fighter_memory',json.dumps({'enabled':True,'remaining':42}))
            store.set_state('category-item:item',json.dumps({'status':'awaiting_review','draft':'DO NOT LOSE'}))
            store.set_state('native-author:batch-a',json.dumps({'status':'open','attempts':[{'draft_id':'draft-a'}]}))
            store.set_state('native-author:draft-a',json.dumps({'status':'draft','output':'Private draft'}))
            store.db.execute("INSERT INTO workshop_optimization_runs VALUES('run','key','hash',?)",(json.dumps({'status':'running','rounds':[{'draft':'saved'}]}),))
            store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES('job','run','claimed','{}','2026-11-03')")
            store.db.execute("INSERT INTO workshop_review_requests(call_id,run_id,status,prompt_json,error) VALUES('successful','run','succeeded','{}','original note')")
            store.db.commit()
            before={t:[tuple(r) for r in store.db.execute('SELECT * FROM '+t)] for t in ('fighters','snapshots','campaign_events','story_memories','story_artifacts','narrative_entries','fighter_thoughts')}
            result=retire(store)
            with closing(sqlite3.connect(result['backup'])) as backup:
                assert backup.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert backup.execute("SELECT status FROM codex_review_jobs WHERE job_id='job'").fetchone()[0]=='claimed'
                assert backup.execute('SELECT value FROM system_state WHERE key=?',(MARKER,)).fetchone() is None
            assert store.db.execute('SELECT status FROM codex_review_jobs').fetchone()[0]=='cancelled'
            assert json.loads(store.get_state('category-item:item'))['draft']=='DO NOT LOSE'
            assert json.loads(store.get_state('category-item:item'))['status']=='cancelled'
            assert not json.loads(store.get_state('category-policy:fighter_memory'))['enabled']
            assert json.loads(store.get_state('category-policy:fighter_memory'))['remaining']==42
            assert json.loads(store.get_state('native-author:batch-a'))['status']=='cancelled'
            assert json.loads(store.get_state('native-author:draft-a'))['output']=='Private draft'
            for t,rows in before.items():assert rows==[tuple(r) for r in store.db.execute('SELECT * FROM '+t)],t
            assert retire(store)==result
            assert store.db.execute("SELECT status FROM workshop_review_requests WHERE call_id='successful'").fetchone()[0]=='succeeded'
            # Simulate the earlier rollout audit-label bug. Repair restores the
            # terminal preimage only, never the genuinely unfinished job.
            result.pop('audit_revision')
            store.set_state(MARKER,json.dumps(result))
            store.db.execute("UPDATE workshop_review_requests SET status='cancelled',error='Writing system removed by owner' WHERE call_id='successful'")
            store.db.commit()
            repaired=retire(store)
            assert repaired['restored_terminal_audits']==1 and repaired['audit_revision']==2
            assert tuple(store.db.execute("SELECT status,error FROM workshop_review_requests WHERE call_id='successful'").fetchone())==('succeeded','original note')
            assert store.db.execute("SELECT status FROM codex_review_jobs WHERE job_id='job'").fetchone()[0]=='cancelled'
            assert len(list(Path(folder).glob('*pre-writing-retirement*.db')))==1
            state=public_state({r['key']:r['value'] for r in store.db.execute('SELECT * FROM system_state')})
            assert not any(k.startswith(('native-author:','category-')) for k in state)
        finally:store.close()


def test_backup_failure_does_not_cancel_or_mark_retired():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=Store(Path(folder)/'test.db')
        try:
            store.set_state('category-policy:test','{"enabled":true}')
            with patch('writing_retirement.sqlite3.connect',side_effect=OSError('Backup unavailable')):
                try:retire(store);raise AssertionError('Must fail closed')
                except OSError:pass
            assert store.get_state(MARKER) is None
            assert json.loads(store.get_state('category-policy:test'))['enabled']
        finally:store.close()


def test_refresh_preserves_written_memories_documents_and_authored_prose():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=Store(Path(folder)/'test.db')
        try:
            original=campaign();apply(store,original);apply(store,latest_game(original))
            row=store.db.execute("SELECT * FROM story_memories WHERE active=1 ORDER BY memory_type LIMIT 1").fetchone()
            text='My lamp is still down there. Someone had better fetch it.'
            runs=json.dumps([[{'text':text,'marks':[]}]] )
            store.db.execute("UPDATE story_memories SET content=?,content_runs_json=?,writer_status='ready' WHERE memory_id=?",(text,runs,row['memory_id']))
            artifact=store.db.execute("SELECT * FROM story_artifacts WHERE active=1 AND scope_type='territory_origin' LIMIT 1").fetchone()
            doc=json.loads(artifact['document_json']);doc.update(writer_status='ready',writer_model='historical-model',native_author={'source':'historical-audit'},blocks=[{'type':'body_paragraph','text':'The old shrine remains.'}])
            store.db.execute('UPDATE story_artifacts SET document_json=? WHERE artifact_id=?',(json.dumps(doc),artifact['artifact_id']))
            authored=[tuple(r) for r in store.db.execute("SELECT id,backstory,backstory_source FROM fighters WHERE backstory_source IS NOT NULL AND backstory_source!=''")]
            store.db.commit();retire(store)
            # A leftover environment/key/enable flag cannot restore generation.
            with patch.object(writer,'API_KEY','legacy-key'),patch.object(writer,'WRITER_ENABLED',True):
                writer.set_enabled(True)
                assert writer.write(store,'fighter_memory',{})[1]['status']=='paused'
                regenerate(store,force=True,writer_enabled=True)
            saved=next(m for m in read_memories(store,row['fighter_id']) if m['memory_key']==row['memory_key'])
            assert saved['content']==text and saved['writer_status']=='ready'
            current=document_for(store,artifact['scope_type'],artifact['scope_key'])
            for key in ('blocks','writer_status','writer_model','native_author'):assert current[key]==doc[key],key
            assert authored==[tuple(r) for r in store.db.execute("SELECT id,backstory,backstory_source FROM fighters WHERE backstory_source IS NOT NULL AND backstory_source!=''")]
            assert writer.availability()['configured'] is False and writer.run_summary()['requests_attempted']==0
        finally:store.close()


def http_check():
    import threading
    from http.cookiejar import CookieJar
    from urllib.request import build_opener,ProxyHandler,HTTPCookieProcessor,Request
    from urllib.error import HTTPError
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        path=Path(folder)/'http.db';seed=Store(path);apply(seed,campaign());seed.close()
        env={'NCCE_DB_PATH':str(path),'NCCE_OPENAI_API_KEY':'must-not-be-used','NCCE_AUTO_WRITE_ENABLED':'1',
             'NCCE_REQUIRE_AUTH':'1','NCCE_ACCESS_PASSWORD':'disposable-test-passphrase','NCCE_SESSION_SECRET':'disposable-test-signing-secret-000000000000'}
        with patch.dict(os.environ,env):
            import server
        service=server.ThreadingHTTPServer(('127.0.0.1',0),server.H)
        worker=threading.Thread(target=service.serve_forever,daemon=True);worker.start()
        client=build_opener(ProxyHandler({}),HTTPCookieProcessor(CookieJar()))
        base='http://127.0.0.1:'+str(service.server_port)
        def request(path,body=None):
            return client.open(Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer old-bridge-token'}),timeout=10)
        try:
            assert json.load(request('/healthz'))['version']=='0.23.2'
            try:request('/api/prose-progress');raise AssertionError('Coverage must require campaign authentication')
            except HTTPError as error:assert error.code==401
            retired=['/api/workshop','/api/workshop/generate','/api/workshop/rag/sync','/api/native-author/publish','/api/reviewer-bridge/claim','/api/writer-diagnostic','/api/writer-runs/mara-latest','/api/territory-writer-runs','/api/fighters/1/write-check']
            for authenticated in (False,True):
                if authenticated:request('/api/login',{'password':env['NCCE_ACCESS_PASSWORD']}).close()
                for path in retired:
                    for body in (None,{}):
                        try:request(path,body);raise AssertionError(path)
                        except HTTPError as error:assert error.code==410,(path,error.code)
            dashboard=json.load(request('/api/dashboard'));assert dashboard['gangs'] and dashboard['writer']['status']=='removed'
            progress=json.load(request('/api/prose-progress'));assert len(progress['categories'])==15 and progress['generation_enabled'] is False
            assert json.load(request('/api/history'))
            assert b'data-view="workshop"' not in request('/').read()
            for asset in ('workshop.js','retrieval.js','writing_activity.js'):
                try:request('/'+asset);raise AssertionError(asset)
                except HTTPError as error:assert error.code==404
            assert json.load(request('/api/health'))['writer']['calls_used']==0
            print('PASS HTTP: authenticated campaign app, old routes 410, removed bundles 404, no writer')
        finally:
            service.shutdown();service.server_close();worker.join();server.store.close()


if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_'):fn();print('PASS '+name)
    if '--http' in sys.argv:http_check()
