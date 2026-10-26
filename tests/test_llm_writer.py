"""Offline contract tests for model writing and provider caching."""
from pathlib import Path
import json
import sys
import tempfile
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
import llm_writer
from store import Store
from test_story_engine import apply,campaign,fighter,latest_game
from story_engine import document_for,read_memories,regenerate


def test_unconfigured_writer_returns_pending_without_template_fallback():
    old=llm_writer.API_KEY
    llm_writer.API_KEY=''
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-pending.db')
            try:
                paragraphs,status=llm_writer.write(store,'fighter_memory',{'event_title':'Critical injury','mechanical_evidence':['Critical Injury']})
                assert paragraphs==[] and status['status']=='unconfigured'
                assert store.db.execute('SELECT count(*) FROM writer_result_cache').fetchone()[0]==0
            finally: store.close()
    finally: llm_writer.API_KEY=old


def test_successful_draft_is_cached_by_fact_packet():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY='mock-token'; calls=[]
    llm_writer._call=lambda form,packet:(calls.append((form,packet)) or [{'runs':[{'text':'A clear sentence grounded in the recorded event.','marks':[]}]}])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-cache.db')
            try:
                packet={'title':'Recovery','facts':['Status: Active → Recovery'],'identity':{'being':'human','work':'prospect miner'}}
                first=llm_writer.write(store,'fighter_memory',packet)
                second=llm_writer.write(store,'fighter_memory',packet)
                expected=[{'runs':[{'text':'A clear sentence grounded in the recorded event.','marks':[]}]}]
                assert first[0]==second[0]==expected
                assert first[1]['status']==second[1]['status']=='ready' and second[1]['cached']
                assert len(calls)==1 and calls[0][1]['identity']['work']=='prospect miner'
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._call=old_call


def test_disabled_writer_reuses_cached_prose_without_a_provider_call():
    old_key,old_call,old_enabled=llm_writer.API_KEY,llm_writer._call,llm_writer.WRITER_ENABLED
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget(); llm_writer.set_enabled(True); calls=[]
    llm_writer._call=lambda form,packet:(calls.append(form) or [{'runs':[{'text':'Previously approved prose remains available.','marks':[]}]}])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-cache-gated.db')
            try:
                packet={'event_title':'A recorded change'}
                first=llm_writer.write(store,'fighter_memory',packet)
                llm_writer.set_enabled(False)
                second=llm_writer.write(store,'fighter_memory',packet)
                assert first[0]==second[0] and second[1]=={'status':'ready','cached':True}
                assert calls==['fighter_memory']
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._call=old_call; llm_writer.set_enabled(old_enabled)


def test_openai_request_uses_server_key_and_structured_prose_schema():
    old_key,old_urlopen=llm_writer.API_KEY,llm_writer.urlopen
    llm_writer.API_KEY='mock-secret'
    captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        headers={'x-request-id':'req_test_001'}
        def read(self):
            return json.dumps({'id':'resp_test_001','usage':{'input_tokens':123,'output_tokens':7},'output':[{'content':[{'type':'output_text','text':json.dumps({'paragraphs':[{'runs':[{'text':'She remembers the repair shift.','marks':[]}]}]})}]}]}).encode()
    def fake(request,timeout):
        captured['url']=request.full_url; captured['authorization']=request.get_header('Authorization')
        captured['body']=json.loads(request.data); captured['timeout']=timeout
        return Response()
    llm_writer.urlopen=fake
    try:
        paragraphs=llm_writer._call('fighter_memory',{'identity':{'species':'human'},'mechanical_evidence':['Status: Recovery']})
        assert paragraphs==[{'runs':[{'text':'She remembers the repair shift.','marks':[]}]}]
        assert captured['url']=='https://api.openai.com/v1/responses'
        assert captured['authorization']=='Bearer mock-secret'
        assert llm_writer._last_response=={'request_id':'req_test_001','response_id':'resp_test_001','input_tokens':123,'output_tokens':7}
        assert captured['body']['text']['format']['type']=='json_schema'
        assert 'critical_status' in str(captured['body']['text']['format']['schema'])
        assert 'error_or_missing' in str(captured['body']['text']['format']['schema'])
        assert 'uniqueItems' not in str(captured['body']['text']['format']['schema'])
        assert 'identity' in captured['body']['input'] and 'mechanical_evidence' in captured['body']['input']
    finally: llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_provider_http_error_surfaces_safe_actionable_reason():
    old_key,old_urlopen=llm_writer.API_KEY,llm_writer.urlopen
    llm_writer.API_KEY='mock-secret'
    body=json.dumps({'error':{'type':'invalid_request_error','param':'text.format.schema','message':'Rejected mock-secret schema'}}).encode()
    llm_writer.urlopen=lambda *args,**kwargs: (_ for _ in ()).throw(HTTPError('https://api.openai.com/v1/responses',400,'Bad Request',{},__import__('io').BytesIO(body)))
    try:
        try:
            llm_writer._call('fighter_memory',{'event_title':'Recovery'})
        except RuntimeError as exc:
            message=str(exc)
        else:
            raise AssertionError('expected provider rejection')
        assert message.startswith('Writing provider returned HTTP 400:')
        assert 'invalid_request_error' in message and 'text.format.schema' in message
        assert 'Rejected [redacted] schema' in message and 'mock-secret' not in message
    finally:
        llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_writer_budget_exhaustion_is_pending_and_does_not_call_provider():
    old_key,old_calls,old_failure,old_call=llm_writer.API_KEY,llm_writer._calls,llm_writer._failure,llm_writer._call
    llm_writer.API_KEY='mock-token'; llm_writer._calls=llm_writer.MAX_CALLS; llm_writer._failure=''
    llm_writer._call=lambda *args: (_ for _ in ()).throw(AssertionError('provider must not be called'))
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-budget.db')
            try:
                paragraphs,status=llm_writer.write(store,'fighter_memory',{'event_title':'Critical injury'})
                assert paragraphs==[] and status['status']=='pending'
                assert 'next refresh' in status['message'] and not llm_writer._failure
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._calls=old_calls; llm_writer._failure=old_failure; llm_writer._call=old_call


def test_story_engine_uses_model_output_across_memories_artifacts_and_streams():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget()
    llm_writer._call=lambda form,packet:[{'runs':[{'text':f'Model-written {form} prose grounded in its supplied account.','marks':[]}]}]
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-integration.db')
            try:
                before=campaign(); apply(store,before); apply(store,latest_game(before))
                maex=fighter(store,'Maex')
                memories=read_memories(store,maex['id'])
                assert any(m['writer_status']=='ready' and m['content'].startswith('Model-written fighter_memory') for m in memories)
                biography=document_for(store,'fighter_biography',maex['id'])
                assert biography['writer_status']=='ready' and biography['blocks'][0]['text'].startswith('Model-written fighter_biography')
                territory=store.dashboard()['territories'][0]
                entries=store.territory(territory['id'])['narrative_stream']
                assert entries and any(e['document']['writer_status']=='ready' for e in entries)
                assert store.db.execute('SELECT count(*) FROM writer_result_cache').fetchone()[0]>0
            finally: store.close()
    finally: llm_writer.API_KEY=old_key; llm_writer._call=old_call


def test_mara_writer_check_is_scoped_and_preserves_authored_biography():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY=''; calls=[]
    llm_writer._call=lambda form,packet:(calls.append((form,packet)) or [{'runs':[{'text':f'Mara-only draft for {form}, grounded in this record.','marks':[]}]}])
    authored="KEL, Mara\nDesignation: Maintenance Fitter\nWorkshop Audit — 781.M41\n‘It is one workshop.’"
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'mara-only.db')
            try:
                before=campaign(); apply(store,before)
                calls.clear()
                mara=fighter(store,'Mara Kel'); other=fighter(store,'Maex')
                store.db.execute("UPDATE fighters SET backstory=?,backstory_source='player-authored / C-NINE story',provenance_class='player_authored' WHERE id=?",(authored,mara['id']))
                store.db.commit()
                other_before=[tuple(row) for row in store.db.execute('SELECT memory_id,content,writer_status,active FROM story_memories WHERE fighter_id=? ORDER BY memory_id',(other['id'],))]
                artifact_count=store.db.execute('SELECT count(*) FROM story_artifacts').fetchone()[0]
                llm_writer.API_KEY='mock-token'
                result=regenerate(store,force=True,fighter_ids=[mara['id']],call_budget=13,writer_run_id='mara-test-run')
                assert result['fighters']==1 and result['writer']['requests_attempted']<=13
                assert result['writer']['requests_succeeded']==result['writer']['requests_attempted']>0
                assert all(item['writer_status']=='ready' for item in result['memory_results'])
                assert all(packet.get('subject')=='Mara Kel' for _,packet in calls)
                assert store.db.execute('SELECT backstory FROM fighters WHERE id=?',(mara['id'],)).fetchone()[0]==authored
                assert [tuple(row) for row in store.db.execute('SELECT memory_id,content,writer_status,active FROM story_memories WHERE fighter_id=? ORDER BY memory_id',(other['id'],))]==other_before
                assert store.db.execute('SELECT count(*) FROM story_artifacts').fetchone()[0]==artifact_count
                requests=store.db.execute('SELECT count(*),sum(status="succeeded"),count(DISTINCT subject_name) FROM writer_requests WHERE run_id="mara-test-run"').fetchone()
                assert requests[0]==requests[1]==len(calls) and requests[2]==1
            finally: store.close()
    finally: llm_writer.API_KEY=old_key; llm_writer._call=old_call


if __name__=='__main__':
    tests=[value for name,value in sorted(globals().items()) if name.startswith('test_')]
    for test in tests: test(); print('PASS',test.__name__)
