"""Offline contract tests for model writing and provider caching."""
from pathlib import Path
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
import llm_writer
from store import Store
from test_story_engine import apply,campaign,fighter,latest_game
from story_engine import document_for,read_memories


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
    llm_writer._call=lambda form,packet:(calls.append((form,packet)) or ['A clear sentence grounded in the recorded event.'])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-cache.db')
            try:
                packet={'title':'Recovery','facts':['Status: Active → Recovery'],'identity':{'being':'human','work':'prospect miner'}}
                first=llm_writer.write(store,'fighter_memory',packet)
                second=llm_writer.write(store,'fighter_memory',packet)
                assert first[0]==second[0]==['A clear sentence grounded in the recorded event.']
                assert first[1]['status']==second[1]['status']=='ready' and second[1]['cached']
                assert len(calls)==1 and calls[0][1]['identity']['work']=='prospect miner'
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._call=old_call


def test_openai_request_uses_server_key_and_structured_prose_schema():
    old_key,old_urlopen=llm_writer.API_KEY,llm_writer.urlopen
    llm_writer.API_KEY='mock-secret'
    captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self):
            return json.dumps({'output':[{'content':[{'type':'output_text','text':json.dumps({'paragraphs':['She remembers the repair shift.']})}]}]}).encode()
    def fake(request,timeout):
        captured['url']=request.full_url; captured['authorization']=request.get_header('Authorization')
        captured['body']=json.loads(request.data); captured['timeout']=timeout
        return Response()
    llm_writer.urlopen=fake
    try:
        paragraphs=llm_writer._call('fighter_memory',{'identity':{'species':'human'},'mechanical_evidence':['Status: Recovery']})
        assert paragraphs==['She remembers the repair shift.']
        assert captured['url']=='https://api.openai.com/v1/responses'
        assert captured['authorization']=='Bearer mock-secret'
        assert captured['body']['text']['format']['type']=='json_schema'
        assert 'identity' in captured['body']['input'] and 'mechanical_evidence' in captured['body']['input']
    finally: llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_story_engine_uses_model_output_across_memories_artifacts_and_streams():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget()
    llm_writer._call=lambda form,packet:[f'Model-written {form} prose grounded in its supplied account.']
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


if __name__=='__main__':
    tests=[value for name,value in sorted(globals().items()) if name.startswith('test_')]
    for test in tests: test(); print('PASS',test.__name__)
