"""Every gang's tracked fighter facts appear in its chronological lane."""
from pathlib import Path
import sys
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writer_pipeline import with_store
from test_story_engine import campaign,apply,latest_game
from fighter_timeline import records


def test_all_gangs_tracked_changes_are_linked_once_without_advancing_state():
    def check(store):
        before=campaign();apply(store,before)
        after=latest_game(before)
        after['gangs']['Ethernetans 2.0']['fighters']['Maex']['XP']=6
        after['gangs']['Kły Sprawiedliwości']['fighters']['Rook']['XP']=2
        apply(store,after)
        changes=store.db.total_changes
        timeline=store.history_timeline();events=[e for e in timeline['events'] if e['source_table']=='fighter_ledger']
        assert {'g1','g2','g3'}.issubset({e['gang_id'] for e in events}),[(e['gang_id'],e['description']) for e in events]
        assert len({e['event_id'] for e in events})==len(events)
        maex=next(e for e in events if e['fighter_name']=='Maex' and e['action_type']=='fighter_xp_changed')
        assert maex['gang_id']=='g2' and maex['local_fighter_id']
        assert maex['timestamp_basis']=='first_observed' and maex['source_event_id']
        assert maex['participation']['status']=='unknown'
        assert maex['source_event_id'] in maex['event_id']
        assert timeline['stats']['tracked_fighter_records']==len(events)
        assert any(e['event_id']==maex['event_id'] for e in store.gang_history('g2')['events'])
        assert any(e['event_id']==maex['event_id'] for e in store.fighter_history(maex['local_fighter_id'])['events'])
        assert store.db.total_changes==changes
        assert store.history_timeline()['events']==timeline['events']
        # Duplicate subject roles do not create another timeline tick.
        entity=store.db.execute("SELECT entity_id FROM event_subjects WHERE event_id=? LIMIT 1",(maex['source_event_id'],)).fetchone()[0]
        store.db.execute('INSERT OR IGNORE INTO event_subjects(event_id,entity_id,role) VALUES(?,?,?)',(maex['source_event_id'],entity,'additional_test_role'));store.db.commit()
        assert len([e for e in store.history_timeline()['events'] if e.get('source_event_id')==maex['source_event_id']])==1
    with_store(check)


if __name__=='__main__':
    test_all_gangs_tracked_changes_are_linked_once_without_advancing_state();print('PASS fighter timeline: all gangs, stable identities, observation-time honesty, linked fighters, shared views and read-only replay')
