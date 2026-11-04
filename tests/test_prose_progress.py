"""Read-only coverage counts published current slots, never workshop/audit rows."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from prose_progress import summary
from test_writer_pipeline import with_store
from test_story_engine import campaign,apply


def test_counts_authored_ready_stale_missing_and_is_read_only():
    def check(store):
        apply(store,campaign())
        store.db.execute("UPDATE fighters SET backstory='An authored life.',backstory_source='player-authored / campaign Sheet' WHERE name='Mara Kel'")
        store.db.commit()
        # Archive/missing prose checks require no model and use real source slots.
        report=summary(store);assert len(report['categories'])==16
        by={r['key']:r for r in report['categories']}
        assert by['fighter_biography']['counts']['authored']>=1
        assert by['gang_origin']['written']==0
        assert by['place_ambient']['total']==0 and by['place_ambient']['completed_percent'] is None
        row=store.db.execute("SELECT * FROM story_artifacts WHERE scope_type='territory_origin' AND active=1 LIMIT 1").fetchone()
        doc=json.loads(row['document_json']);doc.update(writer_status='stale',blocks=[{'type':'body_paragraph','text':'An earlier published account.'}])
        store.db.execute('UPDATE story_artifacts SET document_json=? WHERE artifact_id=?',(json.dumps(doc),row['artifact_id']))
        memory=store.db.execute("SELECT memory_id FROM story_memories WHERE active=1 AND memory_type='observation' LIMIT 1").fetchone()[0]
        store.db.execute("UPDATE story_memories SET content='An accepted memory.',writer_status='ready' WHERE memory_id=?",(memory,))
        store.db.commit()
        before=store.db.total_changes
        with store.reader() as reader:report=summary(reader)
        assert store.db.total_changes==before
        by={r['key']:r for r in report['categories']}
        assert by['territory_origin']['written']==1 and by['territory_origin']['completed']==0
        assert by['fighter_memory']['written']==by['fighter_memory']['completed']==1
        doc.update(writer_status='ready',blocks=[{'type':'section_label','text':'HEADER ONLY'}])
        store.db.execute('UPDATE story_artifacts SET document_json=? WHERE artifact_id=?',(json.dumps(doc),row['artifact_id']))
        assert next(r for r in summary(store)['categories'] if r['key']=='territory_origin')['written']==0
        # No old memory versions/current thoughts or removed subjects inflate totals.
        store.db.execute('UPDATE story_memories SET active=0 WHERE memory_id=?',(memory,))
        assert next(r for r in summary(store)['categories'] if r['key']=='fighter_memory')['written']==0
        for r in report['categories']:
            assert 0<=r['completed']<=r['written']<=r['total']
            assert sum(r['counts'].values())==r['total']
        assert report['generation_enabled'] is False
    with_store(check)


if __name__=='__main__':
    test_counts_authored_ready_stale_missing_and_is_read_only();print('PASS prose progress: authored/current/earlier/missing, header-only exclusion, active versions and read-only reads')
