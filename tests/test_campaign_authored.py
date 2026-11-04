"""Reviewed Google Doc imports bind only to their exact guarded battles."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writer_pipeline import with_store
from campaign_authored import catalog,document,attach
from story_engine import document_for
from prose_progress import summary


def test_five_guarded_reports_and_addenda_are_authored_and_read_only():
    def check(store):
        entries=catalog()['engagements'];assert len(entries)==5
        assert [e['attachment_count'] for e in entries]==[2,3,4,4,2]
        for entry in entries:
            g=entry['guards']
            store.db.execute('INSERT INTO battles(scenario,attacker,defender,territory,source_battle_key,active) VALUES(?,?,?,?,?,1)',
                             (g['scenario'],g['attacker'],g['defender'],g['territory'],entry['battle_key']))
        store.db.commit();changes=store.db.total_changes
        for row,entry in zip(store.db.execute('SELECT * FROM battles ORDER BY id'),entries):
            battle=dict(row);doc=document_for(store,'battle_report',battle['id'])
            assert doc['provenance_class']=='canon_authored' and doc['authored_text']==entry['report']
            assert '[■] Post-Engagement Record' not in doc['authored_text']
            attach(battle);add=battle['post_battle_addendum']
            assert add['authored_text']==entry['addenda'] and add['provenance_class']=='canon_authored'
            assert 'PERSONNEL FILES' not in add['authored_text'] and 'THE DEEP ANSWERS' not in add['authored_text']
            assert add['source_revision']==catalog()['source']['export_sha256'] and add['source_url'].startswith('https://docs.google.com/')
            assert document({**battle,'territory':'Unrelated place'}) is None
            assert document({**battle,'source_battle_key':'other'}) is None
        coverage={r['key']:r for r in summary(store)['categories']}
        assert len(coverage)==16
        assert coverage['battle_report']['counts']['authored']==5
        assert coverage['post_battle_addendum']['counts']['authored']==5
        assert coverage['post_battle_addendum']['total']==5
        assert store.db.total_changes==changes
        first=store.db.execute('SELECT id FROM battles ORDER BY id LIMIT 1').fetchone()[0]
        store.db.execute('UPDATE battles SET notes=? WHERE id=?',('Player report takes priority.',first));store.db.commit()
        assert document_for(store,'battle_report',first)['authored_text']=='Player report takes priority.'
        battle=dict(store.db.execute('SELECT * FROM battles WHERE id=?',(first,)).fetchone());attach(battle)
        assert battle['alternate_report_document']['authored_text']==entries[0]['report']
    with_store(check)


if __name__=='__main__':
    test_five_guarded_reports_and_addenda_are_authored_and_read_only();print('PASS campaign authored: exact source sections/hashes, guarded links, Notes priority, addenda category and read-only coverage')
