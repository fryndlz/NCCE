"""Player battle reports supersede inference in storage, APIs and coverage."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writer_pipeline import with_store
from test_story_engine import campaign,apply,mechanical_records
from story_engine import regenerate,document_for
from prose_progress import summary

TEXT='// JOINT PRECINCT INCIDENT REVIEW //\nOrigin: TAP\n\nThe report remains mine.\nFANGS: Leave it open.\nTAP: On what basis?\nFANGS: Previous contact.\nTAP:\n// RECORD ENDS //'


def test_current_source_is_primary_authored_report_and_counts_without_generation():
    def check(store):
        source=campaign();apply(store,source)
        battle=store.db.execute('SELECT id FROM battles WHERE active=1 LIMIT 1').fetchone()[0]
        # Read and coverage must fix old projections immediately, before refresh.
        store.db.execute('UPDATE battles SET notes=? WHERE id=?',(TEXT,battle));store.db.commit()
        before=mechanical_records(store)
        doc=document_for(store,'battle_report',battle)
        assert doc['authored_text']==TEXT and doc['provenance_class']=='player_authored'
        assert doc['writer_status']=='ready' and 'recorded_notes' not in doc
        coverage=next(r for r in summary(store)['categories'] if r['key']=='battle_report')
        assert coverage['completed']==coverage['written']==coverage['counts']['authored']==1
        assert next(b for b in store.dashboard()['battles'] if b['id']==battle)['report_document']['authored_text']==TEXT
        regenerate(store,force=True,writer_enabled=False)
        stored=json.loads(store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type='battle_report' AND scope_key=? AND active=1",(str(battle),)).fetchone()[0])
        assert stored['provenance_class']=='player_authored' and stored['authored_text']==TEXT
        assert TEXT==stored['blocks'][0]['text']
        assert before==mechanical_records(store)
        # Source correction replaces the authored account; clearing it does not
        # revive a previous source report through generated-draft retention.
        store.db.execute('UPDATE battles SET notes=? WHERE id=?',('Replacement authored report.',battle));store.db.commit()
        assert document_for(store,'battle_report',battle)['authored_text']=='Replacement authored report.'
        store.db.execute('UPDATE battles SET notes=NULL WHERE id=?',(battle,));store.db.commit()
        assert document_for(store,'battle_report',battle) is None
        assert next(r for r in summary(store)['categories'] if r['key']=='battle_report')['written']==0
        regenerate(store,force=True,writer_enabled=False)
        assert document_for(store,'battle_report',battle)['provenance_class']=='inference'
        assert TEXT not in json.dumps(document_for(store,'battle_report',battle))
        assert store.db.execute("SELECT count(*) FROM story_artifacts WHERE scope_type='battle_report' AND active=0").fetchone()[0]>0
    with_store(check)


if __name__=='__main__':
    test_current_source_is_primary_authored_report_and_counts_without_generation();print('PASS authored battles: source precedence, exact text, API, coverage, no source mutation and correction/removal history')
