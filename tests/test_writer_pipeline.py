"""Shared writer regressions: composition, facts, continuity, usage, previews. No paid calls."""
import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import llm_writer as writer
import writer_contract as contract
import narrative_context as context
import writer_preview
from store import Store
from test_story_engine import campaign,latest_game,apply,mechanical_records
from world_streams import save_entry


def draft(text='The reliquary wall now supports a cookhouse.'):
    return {'paragraphs':[{'runs':[{'text':text,'marks':[]}]}],
            'composition':{'heading':'ADEPTUS ADMINISTRATUM','subject':'The adjoining chambers','body_heading':'ASSESSMENT',
                           'closing_label':'REMARK','closing':'Residential tithes applicable.','signoff':'+++ END RECORD +++'}}


def with_store(check):
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=Store(Path(folder)/'test.db')
        try:
            writer.reset_budget(4)
            with patch.object(writer,'API_KEY',''),patch.object(writer,'WRITER_ENABLED',True):
                check(store)
        finally: store.close()


def test_all_forms_share_policy_with_relevant_positive_examples():
    for form in contract.BRIEFS:
        policy=writer._contract_for(form)
        assert contract.RUNTIME_PATH.read_text(encoding='utf-8').strip() in policy
        assert 'STYLE DEMONSTRATION' in policy and 'REQUESTED FORM: '+form in policy
        assert 'Never create an action' not in policy
        assert len(policy)<15000  # full design/renderer manuals cannot creep back in
    assert 'Ossuary' not in writer._contract_for('fighter_memory')
    assert 'Ossuary' not in writer._contract_for('gang_event')


def test_composition_survives_cache_and_authored_content_is_untouched():
    def check(store):
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',return_value=draft()) as call:
            first,status=writer.write(store,'gang_history',{'subject':'A gang'})
            document=writer.apply({'title':'A gang'},first,status)
            cached,cached_status=writer.write(store,'gang_history',{'subject':'A gang'})
            assert writer.apply({'title':'A gang'},cached,cached_status)==document
            assert document['composition']['subject']=='The adjoining chambers'
            assert document['blocks'][-1]['type']=='internal_note' and call.call_count==1
            authored={'provenance_class':'player_authored','blocks':[{'text':'Exact author text\n\n+++ END +++'}]}
            before=deepcopy(authored)
            prose,status=writer.write_document(store,'fighter_biography',1,authored)
            assert writer.apply(authored,prose,status)==before and call.call_count==1
    with_store(check)


def test_failed_output_is_retained_and_charged_usage_is_counted_once():
    def check(store):
        bad=draft('The source packet says the settlement has changed.')
        def fake(form,packet):
            writer._calls+=1
            writer._last_response.update(raw_response={'id':'resp_test','output':bad},input_tokens=120,output_tokens=30,cached_input_tokens=100,reasoning_tokens=10)
            return bad
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake) as call:
            assert writer.write(store,'place_event',{'subject':'Place'})[1]['status']=='error'
            assert writer.write(store,'place_event',{'subject':'Place'})[1]['status']=='error'
            assert call.call_count==1 and writer.run_summary()['input_tokens']==120
            assert writer.run_summary()['cached_input_tokens']==100
            row=store.db.execute('SELECT * FROM writer_request_details').fetchone()
            assert json.loads(row['draft_json'])==bad and 'resp_test' in row['response_json']
            assert store.db.execute('SELECT count(*) FROM writer_result_cache').fetchone()[0]==0
    with_store(check)


def test_fictional_continuity_is_ordered_and_excludes_legacy_and_future():
    def check(store):
        before=campaign(); apply(store,before)
        tid=store.dashboard()['territories'][0]['id']
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',return_value=draft()):
            for name,at in [('past','2026-10-24T20:00:00Z'),('future','2026-10-28T20:00:00Z')]:
                save_entry(store,'territory',tid,name,'ambient_report',name,[],[],provenance='connective_fiction',created_at=at)
            entries=context.preceding(store,'territory',tid,'2026-10-26T20:00:00Z')
            assert len(entries)==1 and entries[0]['text'].startswith('ASSESSMENT')
            row=store.db.execute("SELECT entry_id,document_json FROM narrative_entries WHERE entry_key='past'").fetchone()
            doc=json.loads(row['document_json']); doc['writer_revision']='old-guardrails'
            store.db.execute('UPDATE narrative_entries SET document_json=? WHERE entry_id=?',(json.dumps(doc),row['entry_id']))
            assert context.preceding(store,'territory',tid,'2026-10-26T20:00:00Z')==[]
    with_store(check)


def test_historical_owner_uses_historical_snapshot_and_unknown_stays_unknown():
    def check(store):
        before=campaign(); apply(store,before)
        changed=latest_game(before); changed['territories'][0].update({'Gang':'Ethernetans 2.0','Gang ID':'g2'})
        apply(store,changed)
        place=store.dashboard()['territories'][0]
        earlier=context.territory_state_at(store,place,'2026-10-24T20:00:00Z')
        assert earlier['holder']==before['territories'][0]['Gang']
        assert 'holder' not in context.territory_state_at(store,place,'2026-10-20')
        current=context.territory_state_at(store,place,'2026-10-26')
        assert current['holder']=='Ethernetans 2.0'
    with_store(check)


def test_event_packets_have_baseline_not_boilerplate_or_future_stories():
    def check(store):
        before=campaign(); apply(store,before); apply(store,latest_game(before))
        tid=store.dashboard()['territories'][0]['id']
        packets=[]
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=lambda form,p:(packets.append(p) or draft())):
            save_entry(store,'territory',tid,'check','territory_state_changed','Old template',[],['Recorded change'],
                       event={'event_type':'territory_state_changed','observed_at':'2026-10-25T11:00:00Z','payload':{'territory':'Promethium Cache'}},details=['The traders chalk routes beside their prices.'])
        assert packets and 'chalk' not in json.dumps(packets[0]) and 'invented_details' not in json.dumps(packets[0])
        assert packets[0]['writer_context']['state_at_event']['name']=='Promethium Cache'
    with_store(check)


def test_preview_resolves_legacy_snapshot_without_fabricating_event_ids():
    def check(store):
        before=campaign(); apply(store,before); apply(store,latest_game(before))
        tid=store.dashboard()['territories'][0]['id']
        store.db.execute("UPDATE narrative_entries SET source_event_ids_json='[]' WHERE scope_type='territory'")
        sample=writer_preview.territory_samples(store,tid)[1]
        assert sample['packet']['source_event_ids']==[]
        assert sample['packet']['source_records'][0]['snapshot_id']
        assert sample['packet']['evidence'][0]['scenario']=='Takeover'
        store.db.execute("UPDATE narrative_entries SET document_json='{}' WHERE scope_type='territory'")
        try: writer_preview.territory_samples(store,tid)
        except ValueError: pass
        else: raise AssertionError('Unverified projection must not become factual evidence')
    with_store(check)


def test_preview_uses_shared_writer_and_never_publishes_synthetic_events():
    def check(store):
        before=campaign(); apply(store,before); apply(store,latest_game(before))
        tid=store.dashboard()['territories'][0]['id']
        immutable=mechanical_records(store)
        active=[tuple(row) for row in store.db.execute('SELECT entry_id,document_json FROM narrative_entries WHERE active=1')]
        samples=writer_preview.territory_samples(store,tid)
        calls=[]
        def fake(form,packet):
            writer._calls+=1; calls.append((form,deepcopy(packet))); return draft()
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake):
            result=writer_preview.run_preview(store,samples,'offline-preview')
        assert result['status']=='complete' and len(calls)==4
        assert calls[0][0]=='territory_origin' and calls[-1][0]=='place_event'
        assert len(calls[-1][1]['preview_continuity']['earlier_entries'])==3
        assert immutable==mechanical_records(store)
        assert active==[tuple(row) for row in store.db.execute('SELECT entry_id,document_json FROM narrative_entries WHERE active=1')]
        assert store.db.execute('SELECT count(*) FROM writer_request_details').fetchone()[0]==4
    with_store(check)


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):
            test(); print('PASS',name)
