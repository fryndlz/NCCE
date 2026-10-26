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
    llm_writer._call=lambda form,packet:(calls.append((form,packet)) or [{'runs':[{'text':'I feel the change in the work my hands can do.','marks':[]}]}])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-cache.db')
            try:
                packet={'title':'Recovery','facts':['Status: Active → Recovery'],'identity':{'being':'human','work':'prospect miner'}}
                first=llm_writer.write(store,'fighter_memory',packet)
                second=llm_writer.write(store,'fighter_memory',packet)
                expected=[{'runs':[{'text':'I feel the change in the work my hands can do.','marks':[]}]}]
                assert first[0]==second[0]==expected
                assert first[1]['status']==second[1]['status']=='ready' and second[1]['cached']
                assert len(calls)==1 and calls[0][1]['identity']['work']=='prospect miner'
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._call=old_call


def test_disabled_writer_reuses_cached_prose_without_a_provider_call():
    old_key,old_call,old_enabled=llm_writer.API_KEY,llm_writer._call,llm_writer.WRITER_ENABLED
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget(); llm_writer.set_enabled(True); calls=[]
    llm_writer._call=lambda form,packet:(calls.append(form) or [{'runs':[{'text':'I keep the earlier draft close.','marks':[]}]}])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-cache-gated.db')
            try:
                packet={'event_title':'A recorded change'}
                first=llm_writer.write(store,'fighter_memory',packet)
                llm_writer.set_enabled(False)
                second=llm_writer.write(store,'fighter_memory',packet)
                assert first[0]==second[0] and second[1]['status']=='ready' and second[1]['cached']
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
        assert llm_writer._last_response['request_id']=='req_test_001'
        assert llm_writer._last_response['response_id']=='resp_test_001'
        assert llm_writer._last_response['input_tokens']==123 and llm_writer._last_response['output_tokens']==7
        assert llm_writer._last_response['status'] is None
        assert captured['body']['text']['format']['type']=='json_schema'
        assert 'critical_status' in str(captured['body']['text']['format']['schema'])
        assert 'error_or_missing' in str(captured['body']['text']['format']['schema'])
        assert 'uniqueItems' not in str(captured['body']['text']['format']['schema'])
        assert 'identity' in captured['body']['input'] and 'mechanical_evidence' in captured['body']['input']
    finally: llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_memory_prompt_loads_guardrails_and_caps_short_output():
    old_key,old_urlopen=llm_writer.API_KEY,llm_writer.urlopen
    llm_writer.API_KEY='mock-secret'; captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        headers={'x-request-id':'req_guardrails'}
        def read(self):
            return json.dumps({'id':'resp_guardrails','usage':{'input_tokens':20,'output_tokens':5},'output':[{'content':[{'type':'output_text','text':json.dumps({'paragraphs':[{'runs':[{'text':'The hurt makes the next shift uncertain.','marks':[]}]}]})}]}]}).encode()
    def fake(request,timeout):
        captured['body']=json.loads(request.data)
        return Response()
    llm_writer.urlopen=fake
    try:
        llm_writer._call('fighter_memory',{'event_title':'Critical injury','mechanical_evidence':['Critical Injury']})
        instructions=captured['body']['instructions']
        assert 'NCCE shared writing contract' in instructions
        assert 'Generated fiction MAY' in instructions
        assert 'First-person memories' in instructions
        assert 'STYLE DEMONSTRATION' in instructions
        assert llm_writer._read_contract(llm_writer.FORMAT_PATH) not in instructions
        assert llm_writer._read_contract(llm_writer.DATE_PATH) not in instructions
        assert 'Never create an action' not in instructions
        assert captured['body']['max_output_tokens']==650
        assert captured['body']['reasoning']=={'effort':'medium'}
    finally: llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_diegetic_gate_rejects_mechanical_meta_prose_without_caching_or_blocking_next_entry():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget(limit=5); calls=[]
    def mock_call(form,packet):
        calls.append((form,packet))
        text='My condition is now recorded as critical injury. My concern is the next shift.' if len(calls)==1 else 'My hands shake when I reach for the spanner; the next shift will have to wait.'
        return [{'runs':[{'text':text,'marks':[]}]}]
    llm_writer._call=mock_call
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-diegetic-gate.db')
            try:
                rejected,status=llm_writer.write(store,'fighter_memory',{'event_title':'Critical injury'})
                assert rejected==[] and status['status']=='error'
                assert 'diegetic voice check' in status['message']
                assert store.db.execute('SELECT count(*) FROM writer_result_cache').fetchone()[0]==0
                accepted,ok=llm_writer.write(store,'fighter_memory',{'event_title':'Recovery'})
                assert ok['status']=='ready' and accepted[0]['runs'][0]['text'].startswith('My hands shake')
                assert len(calls)==2 and llm_writer.run_summary()['requests_failed']==1
            finally: store.close()
    finally: llm_writer.API_KEY=old_key; llm_writer._call=old_call


def test_c_nine_context_does_not_force_archive_voice_on_fighter_memory():
    instructions=llm_writer._contract_for('fighter_memory')
    assert 'C-NINE conventions apply only where C-NINE context supplies them' in instructions
    assert 'Imperial administrative/industrial record voice' not in instructions


def test_territory_writer_receives_shared_runtime_contract_and_form_brief():
    instructions=llm_writer._contract_for('territory_history')
    assert 'NCCE shared writing contract' in instructions
    assert 'territory_history' in instructions
    assert 'Preserve its baseline' in instructions


def test_rejected_replacement_keeps_prior_artifact_visible_as_stale():
    previous={'writer_status':'ready','blocks':[{'type':'body_paragraph','text':'Prior saved prose.'}]}
    current={'writer_status':'error','blocks':[],'writer_message':'rejected'}
    retained=llm_writer.retain_previous(current,previous,{'status':'error'})
    assert retained['blocks']==previous['blocks']
    assert retained['writer_status']=='stale'
    assert 'retained' in retained['writer_message']


def test_changing_contract_content_invalidates_cached_draft():
    old_key,old_call,old_contract=llm_writer.API_KEY,llm_writer._call,llm_writer._contract_for
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget(limit=5); calls=[]; contract=['guardrail version one']
    llm_writer._contract_for=lambda form:contract[0]
    llm_writer._call=lambda form,packet:(calls.append(form) or [{'runs':[{'text':'I carry this change into the next shift.','marks':[]}]}])
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-contract-hash.db')
            try:
                packet={'event_title':'A new injury'}
                first=llm_writer.write(store,'fighter_memory',packet)
                contract[0]='guardrail version two'
                second=llm_writer.write(store,'fighter_memory',packet)
                assert first[1]['status']==second[1]['status']=='ready'
                assert not second[1]['cached'] and calls==['fighter_memory','fighter_memory']
            finally: store.close()
    finally: llm_writer.API_KEY=old_key; llm_writer._call=old_call; llm_writer._contract_for=old_contract


def test_incomplete_response_exposes_output_limit_diagnostics():
    old_key,old_urlopen=llm_writer.API_KEY,llm_writer.urlopen
    llm_writer.API_KEY='mock-secret'; captured={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        headers={'x-request-id':'req_incomplete'}
        def read(self):
            return json.dumps({'id':'resp_incomplete','status':'incomplete','incomplete_details':{'reason':'max_output_tokens'},
                'usage':{'input_tokens':1551,'output_tokens':180,'output_tokens_details':{'reasoning_tokens':180}},'output':[]}).encode()
    def fake(request,timeout): captured['body']=json.loads(request.data); return Response()
    llm_writer.urlopen=fake
    try:
        try: llm_writer._call('fighter_memory',{'event_title':'Critical injury'},output_token_limit=650,reasoning_effort='low')
        except RuntimeError as exc: assert str(exc)=='Writing provider response incomplete: max_output_tokens'
        else: raise AssertionError('incomplete response should not be treated as a missing prose field')
        assert captured['body']['max_output_tokens']==650
        assert captured['body']['reasoning']=={'effort':'low'}
        assert llm_writer._last_response['incomplete_reason']=='max_output_tokens'
        assert llm_writer._last_response['reasoning_tokens']==180
    finally: llm_writer.API_KEY=old_key; llm_writer.urlopen=old_urlopen


def test_memory_packet_does_not_replay_unrelated_biography_or_old_prose():
    old_write=llm_writer.write; captured={}
    llm_writer.write=lambda store,form,packet,trace:(captured.update(form=form,packet=packet,trace=trace) or ([],{'status':'pending'}))
    try:
        authored='A long authored biography of an unrelated battle.'
        identity={'authored_context':authored,'identity':{},'inferred_identity':[{'label':'Recorded role','value':'Specialist','source':'mechanical_fact'}],
                  'stim_weights':[{'topic':'injury','weight':1.3,'basis':['voice tendency: enduring']}]}
        llm_writer.write_memory(None,{'id':3,'name':'Mara Kel'},{'name':'C-NINE','gang_type':'GSC'},
            'Critical injury',['Status: Active to Recovery'],identity,prior=['Unrelated old memory prose'])
        packet=captured['packet']
        assert packet['event_title']=='Critical injury'
        assert packet['inferred_identity']==identity['inferred_identity']
        assert packet['stimulus_attention']==identity['stim_weights']
        assert packet['related_observations']==[]
        assert 'authored_context' not in packet and 'prior_entries' not in packet
        assert 'Unrelated old memory prose' not in json.dumps(packet)
        assert 'C-NINE' in packet['gang_context']['name']
    finally: llm_writer.write=old_write


def test_document_packet_does_not_replay_prior_generated_paragraphs():
    old_write=llm_writer.write; captured={}
    llm_writer.write=lambda store,form,packet,trace:(captured.update(form=form,packet=packet) or ([],{'status':'pending'}))
    try:
        document={'title':'District account','blocks':[{'text':'Current narrative'}],
                  'writer_context':{'prior_entry':'An earlier generated report full of unrelated detail.',
                                    'prior_entries':['Old gang story','Older battle story'],
                                    'continuity_reference':{'earlier_entry_ids':['abc']},
                                    'current_event':'Territory holder changed'},
                  'mechanical_evidence':['Holder: A → B']}
        llm_writer.write_document(None,'gang_history','g1',document)
        packet=captured['packet']
        assert 'blocks' not in packet
        assert packet['evidence']==['Holder: A → B']
        assert packet['writer_context']['current_event']=='Territory holder changed'
        assert 'continuity_reference' not in packet['writer_context']
        assert 'prior_entry' not in packet['writer_context'] and 'prior_entries' not in packet['writer_context']
        assert 'unrelated detail' not in json.dumps(packet)
    finally: llm_writer.write=old_write


def test_disabled_writer_keeps_prior_drafts_visible_as_stale():
    old_key,old_call,old_enabled,old_revision=llm_writer.API_KEY,llm_writer._call,llm_writer.WRITER_ENABLED,llm_writer.FORMATTING_REVISION
    llm_writer.API_KEY='mock-token'
    llm_writer._call=lambda form,packet:[{'runs':[{'text':'I remember the event in my own words.' if form in {'fighter_memory','fighter_reflection'} else f'Existing {form} prose from the prior approved draft.','marks':[]}]}]
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-stale-preserved.db')
            try:
                before=campaign(); apply(store,before); apply(store,latest_game(before))
                regenerate(store,force=True,writer_enabled=True,writer_run_id='approved-mock-draft')
                assert llm_writer.run_summary()['requests_succeeded']+llm_writer.run_summary()['cache_hits']>0
                previous=store.db.execute("SELECT memory_key,content FROM story_memories WHERE active=1 AND writer_status='ready' AND content!='' LIMIT 1").fetchone()
                assert previous
                old_artifacts=store.db.execute("SELECT scope_type,scope_key,document_json FROM story_artifacts WHERE active=1 AND scope_type='fighter_biography'").fetchall()
                previous_artifact=next(({**dict(row),'document':json.loads(row['document_json'])} for row in old_artifacts
                                        if json.loads(row['document_json']).get('writer_status')=='ready'),None)
                llm_writer.FORMATTING_REVISION=old_revision+'-changed'
                second=regenerate(store,force=True,writer_enabled=False,writer_run_id='no-spend-revision')
                retained=store.db.execute("SELECT content,writer_status FROM story_memories WHERE active=1 AND memory_key=? ORDER BY created_at DESC LIMIT 1",(previous['memory_key'],)).fetchone()
                assert retained['content']==previous['content'] and retained['writer_status']=='stale'
                requests=store.db.execute("SELECT count(*) FROM writer_requests WHERE run_id='no-spend-revision'").fetchone()[0]
                assert requests==0 and llm_writer.run_summary()['requests_attempted']==0
                if previous_artifact:
                    artifact=store.db.execute("SELECT document_json FROM story_artifacts WHERE active=1 AND scope_type=? AND scope_key=? ORDER BY generated_at DESC LIMIT 1",(previous_artifact['scope_type'],previous_artifact['scope_key'])).fetchone()
                    assert artifact
                    doc=json.loads(artifact[0])
                    assert doc.get('writer_status')=='stale'
                    assert doc.get('blocks')==previous_artifact['document'].get('blocks')
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._call=old_call; llm_writer.set_enabled(old_enabled); llm_writer.FORMATTING_REVISION=old_revision


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
                assert 'not been attempted' in status['message'] and not llm_writer._failure
            finally: store.close()
    finally:
        llm_writer.API_KEY=old_key; llm_writer._calls=old_calls; llm_writer._failure=old_failure; llm_writer._call=old_call


def test_story_engine_uses_model_output_across_memories_artifacts_and_streams():
    old_key,old_call=llm_writer.API_KEY,llm_writer._call
    llm_writer.API_KEY='mock-token'; llm_writer.reset_budget()
    llm_writer._call=lambda form,packet:[{'runs':[{'text':'I remember the event and how it changed my work.' if form in {'fighter_memory','fighter_reflection'} else f'Model-written {form} prose grounded in its supplied account.','marks':[]}]}]
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
            store=Store(Path(folder)/'writer-integration.db')
            try:
                before=campaign(); apply(store,before); apply(store,latest_game(before))
                maex=fighter(store,'Maex')
                memories=read_memories(store,maex['id'])
                assert any(m['writer_status']=='ready' and m['content'].startswith('I remember the event') for m in memories)
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
    llm_writer._call=lambda form,packet:(calls.append((form,packet)) or [{'runs':[{'text':'I remember this event through my own work.' if form in {'fighter_memory','fighter_reflection'} else f'Mara-only draft for {form}, grounded in this record.','marks':[]}]}])
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
