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








def test_fictional_continuity_is_ordered_and_excludes_legacy_and_future():
    def check(store):
        before=campaign(); apply(store,before)
        tid=store.dashboard()['territories'][0]['id']
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'write',return_value=(draft()['paragraphs'],{'status':'ready','revision':writer.FORMATTING_REVISION,'composition':draft()['composition']})):
            for name,at in [('past','2026-10-24T20:00:00Z'),('future','2026-10-28T20:00:00Z')]:
                save_entry(store,'territory',tid,name,'ambient_report',name,[],[],provenance='connective_fiction',created_at=at)
                row=store.db.execute('SELECT entry_id,document_json FROM narrative_entries WHERE entry_key=?',(name,)).fetchone()
                doc=json.loads(row['document_json']);doc['external_request_id']='accepted-fixture:'+name
                store.db.execute('UPDATE narrative_entries SET document_json=? WHERE entry_id=?',(json.dumps(doc),row['entry_id']))
            entries=context.preceding(store,'territory',tid,'2026-10-26T20:00:00Z')
            assert len(entries)==1 and entries[0]['text'].startswith('ASSESSMENT')
            row=store.db.execute("SELECT entry_id,document_json FROM narrative_entries WHERE entry_key='past'").fetchone()
            doc=json.loads(row['document_json']);doc.pop('external_request_id');doc['writer_revision']=writer.FORMATTING_REVISION
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
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'write',side_effect=lambda store,form,p,trace=None:(packets.append(p) or (draft()['paragraphs'],{'status':'ready'}))):
            save_entry(store,'territory',tid,'check','territory_state_changed','Old template',[],['Recorded change'],
                       event={'event_type':'territory_state_changed','observed_at':'2026-10-25T11:00:00Z','payload':{'territory':'Promethium Cache'}},details=['The traders chalk routes beside their prices.'])
        assert packets and 'chalk' not in json.dumps(packets[0]) and 'invented_details' not in json.dumps(packets[0])
        assert packets[0]['writer_context']['state_at_event']['name']=='Promethium Cache'
    with_store(check)






if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):
            test(); print('PASS',name)
