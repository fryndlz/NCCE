"""Workshop integrity, one-call execution, durable edits and production policy activation."""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import llm_writer as writer
import writer_workshop as ws
from test_writer_pipeline import with_store,draft
from test_story_engine import campaign,latest_game,apply,mechanical_records

def seed(store):
    before=campaign();apply(store,before);apply(store,latest_game(before))
    return next(item for item in ws.catalog(store) if item['form']=='fighter_memory')

def test_revisions_activate_only_explicitly_and_preserve_source():
    def check(store):
        seed(store); immutable=mechanical_records(store)
        r=ws.save_revision(store,{**ws.defaults('shared'),'instructions':'Use a precise narrator and meaningful detail.'})
        assert ws.active_contract(store,'fighter_memory') is None
        ws.activate(store,{'scope':'shared','revision_id':r['revision_id'],'expected_active':None})
        first=ws.active_contract(store,'fighter_memory')
        assert r['instructions'] in first and 'Mechanical evidence fixes' in first
        second=ws.save_revision(store,{**r,'instructions':'Use ordinary language and a coherent action.'})
        assert ws.active_contract(store,'fighter_memory')==first
        try:store.db.execute('UPDATE workshop_revisions SET instructions=?',( 'overwrite',))
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('Saved revision changed in place')
        ws.activate(store,{'scope':'shared','revision_id':None,'expected_active':r['revision_id']})
        assert ws.active_contract(store,'fighter_memory') is None
        assert len(ws.editor(store,'shared')['history'])==2 and immutable==mechanical_records(store)
    with_store(check)

def test_one_generation_is_idempotent_audited_and_uses_selected_prompt():
    def check(store):
        source=seed(store); before=mechanical_records(store)
        memories=[tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
        r=ws.save_revision(store,{**ws.defaults('fighter_memory'),'instructions':'First person, one meaningful personal experience.'})
        body={'sample_key':source['key'],'form_revision_id':r['revision_id'],'request_key':'once-000000000000000'}
        with patch.object(writer,'API_KEY','mock'):
            try:ws.queue(store,{**body,'packet_hash':'stale-context'})
            except ValueError:pass
            else:raise AssertionError('Changed evidence was not detected before spending')
            item,fresh=ws.queue(store,body)
            again,fresh2=ws.queue(store,body)
            assert fresh and not fresh2 and item['trial_id']==again['trial_id']
            def fake(form,packet,**kwargs):
                writer._calls+=1;writer._last_prompt.update(instructions=kwargs['contract_override'],input=json.dumps(packet))
                writer._last_response.update(input_tokens=100,output_tokens=20)
                return draft('I left the tools where they were.')
            with patch.object(writer,'_call',side_effect=fake) as provider:
                result=ws.execute(store,item['trial_id']); ws.execute(store,item['trial_id'])
                assert provider.call_count==1
        assert result['status']=='ready' and result['usage']['requests_attempted']==1
        audit=store.db.execute('SELECT prompt_json FROM writer_request_details WHERE request_row_id=(SELECT request_row_id FROM writer_requests WHERE run_id=?)',(item['trial_id'],)).fetchone()
        assert r['instructions'] in json.loads(audit[0])['instructions']
        assert ws.active_contract(store,'fighter_memory') is None
        assert memories==[tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
        assert before==mechanical_records(store)
        edit=ws.save_edit(store,{'trial_id':item['trial_id'],'body':'I asked for my tools.','composition':{}})
        assert [b['text'] for b in edit['document']['blocks'] if b['type']=='body_paragraph']==['I left the tools where they were.']
        assert edit['edits'][0]['document']['blocks'][0]['text']=='I asked for my tools.'
    with_store(check)

def test_approved_policy_changes_actual_production_prompt_and_cache():
    def check(store):
        seed(store)
        calls=[]
        def fake(form,packet,**kwargs):
            writer._calls+=1;calls.append(kwargs.get('contract_override'));return draft('I shut the locker.')
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake):
            writer.reset_budget(3)
            writer.write(store,'fighter_memory',{'subject':'Test'})
            r=ws.save_revision(store,{**ws.defaults('fighter_memory'),'instructions':'My approved narrative rules.'})
            ws.activate(store,{'scope':'fighter_memory','revision_id':r['revision_id'],'expected_active':None})
            writer.write(store,'fighter_memory',{'subject':'Test'})
            assert len(calls)==2 and calls[0] is None and r['instructions'] in calls[1]
            writer.write(store,'fighter_memory',{'subject':'Test'})
            assert len(calls)==2 and writer.run_summary()['cache_hits']==1
    with_store(check)

def test_failed_paid_draft_remains_audited_without_retry():
    def check(store):
        source=seed(store)
        with patch.object(writer,'API_KEY','mock'):
            item,_=ws.queue(store,{'sample_key':source['key'],'request_key':'failed-0000000000000'})
            def bad(*args,**kwargs):
                writer._calls+=1;writer._last_response.update(input_tokens=12,output_tokens=3,raw_response={'output':[{'content':[{'type':'output_text','text':'bad draft retained'}]}]})
                return draft('The source packet says that I am injured.')
            with patch.object(writer,'_call',side_effect=bad) as provider:
                result=ws.execute(store,item['trial_id']);ws.execute(store,item['trial_id'])
                assert provider.call_count==1
        assert result['status']=='error' and result['raw_output']=='bad draft retained'
        assert result['usage']['input_tokens']==12 and result['usage']['requests_failed']==1
    with_store(check)

def test_import_preserves_exact_available_prompt_without_spending():
    def check(store):
        selected={'key':'comparison:1:0','form':'fighter_memory','label':'Mara A','packet':{'subject':'Mara'},'document':{'blocks':[]},'instructions_used':'Exact audited comparison instructions'}
        with patch.object(ws,'sample',return_value=selected),patch.object(writer,'_call') as provider:
            imported=ws.import_sample(store,{'sample_key':selected['key']})
            assert imported['instructions']==selected['instructions_used']
            assert imported['usage']['requests_attempted']==0 and provider.call_count==0
    with_store(check)

if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
