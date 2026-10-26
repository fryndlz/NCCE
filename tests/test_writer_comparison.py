"""Controlled comparison: identical inputs, isolated prompts, six calls, no campaign writes."""
import json
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import writer_comparison as comparison
import writer_candidate as candidate
import writer_contract
import llm_writer as writer
from test_writer_pipeline import with_store,draft
from test_story_engine import campaign,latest_game,apply,mechanical_records

def test_six_calls_are_matched_blind_and_isolated():
    def check(store):
        before=campaign(); apply(store,before); apply(store,latest_game(before))
        tid=store.dashboard()['territories'][0]['id']
        samples=comparison.cases(store,tid,'Mara Kel')
        assert [s['form'] for s in samples]==['place_event','fighter_memory','gang_event']
        assert samples[1]['packet']['event']['payload']['after']=='Injuries: Critical Injury'
        assert 'generated_background' not in samples[1]['packet']
        source_before=mechanical_records(store)
        stories_before=[tuple(r) for r in store.db.execute('SELECT * FROM narrative_entries')]
        calls=[]
        def fake(form,packet,**kwargs):
            calls.append((form,deepcopy(packet),kwargs['contract_override']))
            writer._calls+=1
            writer._last_prompt.update(instructions=kwargs['contract_override'],input=json.dumps(packet))
            writer._last_response.update(input_tokens=10,output_tokens=5)
            return draft('I left the tools where they were.' if form=='fighter_memory' else 'The reliquary doors remained open.')
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake):
            result=comparison.run(store,samples,'comparison-test')
        assert result['status']=='complete' and len(calls)==6
        for first,second in zip(calls[::2],calls[1::2]):
            assert first[:2]==second[:2] and first[2]!=second[2]
            assert {first[2],second[2]}=={writer_contract.contract(first[0]),candidate.contract(first[0])}
        assert 'editorial-selection-v1' not in json.dumps(result)
        assert source_before==mechanical_records(store)
        assert stories_before==[tuple(r) for r in store.db.execute('SELECT * FROM narrative_entries')]
        assert store.db.execute('SELECT count(*) FROM writer_request_details').fetchone()[0]==6
        revisions=[r[0] for r in store.db.execute('SELECT contract_revision FROM writer_request_details')]
        assert revisions.count(candidate.REVISION)==3
        assert revisions.count(writer_contract.REVISION)==3
        assert writer.run_summary()['input_tokens']==60
    with_store(check)

def test_candidate_preserves_authority_and_presentation_for_all_forms():
    original=writer_contract.RUNTIME_PATH.read_text(encoding='utf-8-sig')
    for form in writer_contract.BRIEFS:
        policy=candidate.contract(form)
        assert original.split('## Voice and craft')[0] in policy
        assert original.split('## Context and presentation')[1] in policy
        assert 'proportion to significance' in policy and 'Return only the finished piece' in policy
    assert 'Ossuary' not in candidate.contract('fighter_memory')
    assert 'Ossuary' not in candidate.contract('gang_event')

if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test): test(); print('PASS',name)
