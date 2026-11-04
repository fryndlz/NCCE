"""Exact external prose import; all data is confined to disposable databases."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from store import Store
from story_engine import read_memories,regenerate
from fighter_event_clock import build
from writing_exchange import import_delivery,packet_revision
from test_story_engine import campaign,apply,C9


def setup(directory):
    store=Store(Path(directory)/'test.db')
    bundle=json.loads((ROOT/'data/writing-exchange/accepted/17e7fee1-bc2b-491c-825d-a07f1f014b96.json').read_text(encoding='utf-8'))
    source=bundle['packet']['binding'];snap=campaign()
    snap['gangs'][C9]['gang_id']=source['gang_source_id']
    snap['gangs'][C9]['fighters']['Mara Kel']['Backstory']=next(b['text'] for b in bundle['packet']['context'] if b['section']=='authored_canon')
    apply(store,snap)
    later=deepcopy(snap);later['captured_at']='2026-10-25T16:23:15+00:00'
    later['gangs'][C9]['fighters']['Mara Kel'].update(Effects='Injuries: Critical Injury',Status='Recovery')
    apply(store,later)
    fid=store.db.execute("SELECT id FROM fighters WHERE name='Mara Kel'").fetchone()[0]
    memory=next(m for m in read_memories(store,fid) if m['title']=='Critical injury recorded')
    bundle['target_binding']['memory_key']=memory['memory_key']
    bundle['target_binding']['evidence_json']=json.dumps(memory['evidence'],ensure_ascii=False,separators=(',',':'))
    facts=json.loads(next(b['text'] for b in bundle['packet']['context'] if b['section']=='mechanics'))
    archived={**facts,'fighter_id':source['fighter_source_id'],'gang_id':source['gang_source_id'],
              'fighter_name_hint':source['fighter_name'],'created_at_utc':bundle['packet']['request']['event_at_utc']}
    store.db.execute('''INSERT INTO campaign_archive_records(source_table,record_id,version_hash,payload_hash,
        imported_at_utc,source_tab,source_row_json,raw_record_json,normalized_json)
        VALUES(?,?,'append-only','test','2026-11-04','MUNDA_ACTIVITY_RAW','{}','{}',?)''',
        (source['source_table'],source['source_event_id'],json.dumps(archived)))
    store.db.commit()
    return store,bundle,fid,memory


def facts(store):
    return {t:[tuple(r) for r in store.db.execute('SELECT * FROM '+t)] for t in ('campaign_events','snapshots','fighters','fighter_thoughts')}


def test_import_keeps_exact_text_authority_history_and_clock_across_refresh_and_restart():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            before=facts(store);clock=build(read_memories(store,fid),store,fid)
            with patch('llm_writer.write',side_effect=AssertionError('No model work during import')):
                result=import_delivery(store,bundle)
            assert result['status']=='imported',result
            assert facts(store)==before
            current=read_memories(store,fid)
            same=[m for m in current if m['memory_key']==old['memory_key']]
            assert len(same)==1 and same[0]['content']==bundle['writer_text_md'] and same[0]['writer_status']=='ready'
            assert same[0]['importance']==old['importance'] and same[0]['source_event_ids']==old['source_event_ids']
            assert (same[0]['occurred_at'],same[0]['observed_at'])==(old['occurred_at'],old['observed_at'])
            assert build(current,store,fid)==clock
            assert store.db.execute('SELECT active FROM story_memories WHERE memory_id=?',(old['id'],)).fetchone()[0]==0
            assert import_delivery(store,bundle)['receipt']==result['receipt']
            assert store.db.execute('SELECT count(*) FROM external_prose_deliveries').fetchone()[0]==1
            regenerate(store,force=True,writer_enabled=False)
            same=[m for m in read_memories(store,fid) if m['memory_key']==old['memory_key']]
            assert len(same)==1 and same[0]['content']==bundle['writer_text_md'] and same[0]['writer_status']=='ready'
            assert build(read_memories(store,fid),store,fid)==clock
            assert list(Path(directory).glob('pre-exchange-*.db'))
            path=store.path;store.close();store=Store(path)
            assert import_delivery(store,bundle)['reused']
            assert next(m for m in read_memories(store,fid) if m['memory_key']==old['memory_key'])['content']==bundle['writer_text_md']
        finally:store.close()


def test_invalid_or_conflicting_deliveries_are_retained_without_changing_target():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            bad=deepcopy(bundle);bad['packet']['request']['source_revision']='sha256:wrong'
            result=import_delivery(store,bad)
            assert result['status']=='held'
            assert store.db.execute('SELECT raw_markdown FROM external_prose_deliveries').fetchone()[0]==bundle['writer_text_md']
            assert next(m for m in read_memories(store,fid) if m['memory_key']==old['memory_key'])['id']==old['id']
            good=import_delivery(store,bundle);assert good['status']=='imported',good
            bad=deepcopy(bundle);bad['writer_text_md']='An explicitly different saved draft.'
            assert import_delivery(store,bad)['status']=='held'
            assert next(m for m in read_memories(store,fid) if m['memory_key']==old['memory_key'])['content']==bundle['writer_text_md']
            assert store.db.execute("SELECT count(*) FROM external_prose_deliveries WHERE disposition='imported'").fetchone()[0]==1
            assert store.db.execute("SELECT count(*) FROM external_prose_deliveries WHERE disposition='held'").fetchone()[0]==2
        finally:store.close()


def test_wrong_target_changed_source_or_authored_memory_never_gets_overwritten():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            wrong=deepcopy(bundle);wrong['target_binding']['memory_key']='not-the-injury'
            assert import_delivery(store,wrong)['status']=='held'
            store.db.execute("UPDATE story_memories SET provenance_class='player_authored' WHERE memory_id=?",(old['id'],));store.db.commit()
            assert import_delivery(store,bundle)['status']=='held'
            store.db.execute("UPDATE story_memories SET provenance_class='inference' WHERE memory_id=?",(old['id'],))
            store.db.execute("UPDATE campaign_archive_records SET normalized_json='{}'");store.db.commit()
            assert import_delivery(store,bundle)['status']=='held'
            assert store.db.execute('SELECT active FROM story_memories WHERE memory_id=?',(old['id'],)).fetchone()[0]==1
        finally:store.close()


def test_existing_canonical_biography_is_preserved_when_sheet_context_matches():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            store.db.execute("UPDATE fighters SET backstory='Preserved authored canon',backstory_source='canon: C-NINE Story' WHERE id=?",(fid,));store.db.commit()
            assert import_delivery(store,bundle)['status']=='imported'
            assert store.db.execute('SELECT backstory FROM fighters WHERE id=?',(fid,)).fetchone()[0]=='Preserved authored canon'
        finally:store.close()


def test_no_existing_memory_means_hold_not_a_second_invented_experience():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            store.db.execute('UPDATE story_memories SET active=0 WHERE memory_id=?',(old['id'],));store.db.commit()
            count=store.db.execute('SELECT count(*) FROM story_memories').fetchone()[0]
            assert import_delivery(store,bundle)['status']=='held'
            assert store.db.execute('SELECT count(*) FROM story_memories').fetchone()[0]==count
        finally:store.close()


def test_failed_database_write_rolls_back_prose_and_preserves_rejected_delivery():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        store,bundle,fid,old=setup(directory)
        try:
            store.db.execute("CREATE TRIGGER fail_import BEFORE INSERT ON story_memories BEGIN SELECT RAISE(ABORT,'test write failure'); END")
            store.db.commit()
            result=import_delivery(store,bundle)
            assert result['status']=='held' and 'test write failure' in result['error']
            assert next(m for m in read_memories(store,fid) if m['memory_key']==old['memory_key'])['id']==old['id']
            assert store.db.execute('SELECT raw_markdown FROM external_prose_deliveries').fetchone()[0]==bundle['writer_text_md']
        finally:store.close()


if __name__=='__main__':
    for name,check in list(globals().items()):
        if name.startswith('test_') and callable(check):check();print('PASS',name)
