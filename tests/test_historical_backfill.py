"""Historical backfill: finite scope, normal Queue exclusion, canonical imports.

These use disposable NCCE databases. No live Sheet, model or Render writes.
"""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from contextlib import contextmanager

@contextmanager
def raises(error_type, match=None):
    try:
        yield
    except error_type as exc:
        if match and match not in str(exc):
            raise AssertionError('Unexpected error: '+str(exc)) from exc
    else:
        raise AssertionError('Expected '+error_type.__name__)

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writing_exchange import setup
import exchange_automation as exchange
import historical_backfill as bulk
from writing_exchange import digest

TEXT="**HARD LESSON**\n\nThe sump taught me to hold my ground. We still have a job to finish."


def fixture():
    tmp=tempfile.TemporaryDirectory(dir=ROOT/'data')
    store,bundle,fid,memory=setup(tmp.name)
    row=store.db.execute("SELECT gang_id FROM fighters WHERE id=?",(fid,)).fetchone()
    return tmp,store,str(row['gang_id'])


def test_bulk_text_validation_is_form_specific():
    reflection = "**WHAT REMAINS**\n\n" + ("I remember what the work cost, and reckon it mattered. " * 10)
    assert len(reflection) > 350
    bulk._validate_bulk_text("fighter_reflection", reflection)
    with raises(ValueError, match="350 characters"):
        bulk._validate_bulk_text("fighter_memory", reflection)
    with raises(ValueError, match="nonempty"):
        bulk._validate_bulk_text("fighter_reflection", "   ")
    with raises(ValueError, match="30000"):
        bulk._validate_bulk_text("fighter_reflection", "A" * 30000)
    bulk._validate_bulk_text("fighter_memory", TEXT)


def test_owner_authorization_scoped_and_schema_present():
    tmp,s,gang=fixture()
    try:
        assert s.schema_version>=21
        with raises(ValueError,match='owner authorization'):
            bulk.create(s,[gang])
        assert s.db.execute("SELECT count(*) FROM historical_backfill_jobs").fetchone()[0]==0
        job=bulk.create(s,[gang],owner_authorized=True)
        assert job['scope']==[gang]
        assert job['queued']>=1,job
        assert job['discovered']>=job['queued']
        assert set(bulk.reserved_targets(s))
        with raises(ValueError,match='already has an active'):
            bulk.create(s,[gang],owner_authorized=True)
        with raises(ValueError,match='must exist'):
            bulk.create(s,['fake-gang-id'],owner_authorized=True)
        assert bulk.summary(s,job['job_id'])['count']>=1
    finally:s.close();tmp.cleanup()


def test_normal_exchange_skips_bulk_reservations_without_changing_legacy_queue():
    tmp,s,gang=fixture()
    try:
        job=bulk.create(s,[gang],owner_authorized=True)
        reserved=bulk.reserved_targets(s)
        assert reserved
        exchange.prepare(s,client_states=[])
        normal={r['target_key'] for r in s.db.execute(
            "SELECT target_key FROM writing_exchange_requests WHERE state='PENDING'")}
        assert not reserved.intersection(normal)
        assert all(packet['request']['request_id'] not in
                   {x['request_id'] for x in bulk._items(s,job['job_id'])}
                   for packet in exchange.outbox(s))
    finally:s.close();tmp.cleanup()


def test_bulk_delivery_reuses_same_import_validator_and_manual_revision_is_normal():
    tmp,s,gang=fixture()
    try:
        exchange.prepare(s,client_states=[])
        origin=next(p['request'] for p in exchange.outbox(s)
                    if p['request']['form']=='gang_origin' and p['request']['entity_key']==gang)
        assert exchange.deliver(s,{**origin,'status':'READY','writer_text_md':TEXT})['status']=='imported'
        job=bulk.create(s,[gang],owner_authorized=True)
        packets=bulk.poll(s,job['job_id'],1)['packets']
        assert len(packets)==1
        packet=packets[0]
        selected=next(x for x in bulk._items(s,job['job_id']) if x['request_id']==packet['request']['request_id'])
        c=next(c for c in exchange.candidates(s) if exchange.target_key(c)==selected['target_key'])
        assert packet['request']['request_id']==selected['request_id']
        assert packet['request']['source_revision']
        assert bulk.poll(s,job['job_id'],1)['packets'][0]==packet
        payload=dict(job_id=job['job_id'],request_id=selected['request_id'],
                     source_revision=packet['request']['source_revision'],
                     status='READY',writer_text_md=TEXT)
        canonical_deliver=exchange.deliver
        def interrupt_after_commit(store, draft):
            assert canonical_deliver(store,draft)['status']=='imported'
            raise RuntimeError('Relay interrupted after canonical commit')
        with patch.object(exchange,'deliver',side_effect=interrupt_after_commit):
            with raises(RuntimeError,match='interrupted after canonical commit'):
                bulk.deliver(s,job['job_id'],payload)
        with patch('llm_writer.write',side_effect=AssertionError('No model execution in NCCE')):
            imported=bulk.deliver(s,job['job_id'],payload)
        assert imported['status']=='imported',imported
        assert imported['reused'] and imported['imported_at_utc']
        assert imported['receipt'].startswith('exchange:')
        with raises(ValueError,match='revision does not match'):
            bulk.deliver(s,job['job_id'],{**payload,'source_revision':'stale'})
        assert bulk.deliver(s,job['job_id'],payload)['receipt']==imported['receipt']
        with raises(ValueError,match='immutable'):
            bulk.deliver(s,job['job_id'],{**payload,'writer_text_md':'**Different**'})
        assert not any(p['request']['request_id']==selected['request_id']
                       for p in exchange.outbox(s))
        assert s.db.execute(
            "SELECT state FROM writing_exchange_requests WHERE request_id=?",
            (selected['request_id'],)).fetchone()[0]=='IMPORTED'
        assert s.db.execute(
            "SELECT content FROM story_memories WHERE fighter_id=? AND memory_key=? AND active=1",
            c['key']).fetchone()[0]==TEXT
        reviewed=bulk.request_manual_revision(s,job['job_id'],selected['request_id'],imported['receipt'])
        assert reviewed['request_id']!=selected['request_id']
        assert reviewed['status']=='PENDING'
        assert any(p['request']['request_id']==reviewed['request_id']
                   for p in exchange.outbox(s))
        assert s.db.execute(
            "SELECT revision_of FROM writing_exchange_requests WHERE request_id=?",
            (reviewed['request_id'],)).fetchone()[0]==selected['request_id']
    finally:s.close();tmp.cleanup()


def test_stale_source_holds_without_an_import_or_fact_mutation():
    tmp,s,gang=fixture()
    try:
        job=bulk.create(s,[gang],owner_authorized=True)
        selected=next(x for x in bulk._items(s,job['job_id']) if x['form']=='fighter_memory')
        c=next(c for c in exchange.candidates(s) if exchange.target_key(c)==selected['target_key'])
        with patch.object(bulk,'plan',return_value=([c],{},{})):
            packet=bulk.poll(s,job['job_id'],1)['packets'][0]
        s.db.execute(
            "UPDATE story_memories SET evidence_json=? WHERE fighter_id=? AND memory_key=? AND active=1",
            ('["changed mechanical evidence"]',*c['key']))
        s.db.commit()
        result=bulk.deliver(s,job['job_id'],{
            'request_id':selected['request_id'],'source_revision':packet['request']['source_revision'],
            'status':'READY','writer_text_md':TEXT
        })
        assert result['status']=='held'
        assert 'changed' in result['error']
        assert s.db.execute(
            "SELECT content FROM story_memories WHERE fighter_id=? AND memory_key=? AND active=1",
            c['key']).fetchone()[0]!=TEXT
        item=s.db.execute(
            "SELECT state,writer_text_md FROM historical_backfill_items WHERE request_id=?",
            (selected['request_id'],)).fetchone()
        assert item['state']=='HOLD' and item['writer_text_md']==TEXT
    finally:s.close();tmp.cleanup()


def test_cancel_releases_reservations_and_never_unimports_successful_items():
    tmp,s,gang=fixture()
    try:
        job=bulk.create(s,[gang],owner_authorized=True)
        assert bulk.reserved_targets(s)
        after=bulk.cancel(s,job['job_id'])
        assert after['state']=='CANCELLED'
        assert not bulk.reserved_targets(s)
        with raises(ValueError,match='Only open jobs'):
            bulk.cancel(s,job['job_id'])
    finally:s.close();tmp.cleanup()


def test_unresolved_job_can_only_close_with_explicit_held_item_audit():
    tmp,s,gang=fixture()
    try:
        job=bulk.create(s,[gang],owner_authorized=True)
        assert bulk.summary(s,job['job_id'])['state']=='ACTIVE'
        items=bulk._items(s,job['job_id'])
        assert items and all(item['state']=='PENDING' for item in items)
        for item in items:
            assert item['context_seal']==digest(
                json.loads(item['packet_json'])['context'])
        with raises(ValueError,match='Unresolved'):
            bulk.close(s,job['job_id'])
        done=bulk.close(s,job['job_id'],finalize_unresolved=True)
        assert done['state']=='COMPLETED_WITH_ERRORS'
        assert done['statuses']['HOLD']==len(items)
        assert not bulk.reserved_targets(s)
        assert all(item['error'] for item in bulk._items(s,job['job_id']))
    finally:s.close();tmp.cleanup()


if __name__=='__main__':
    for name,check in list(globals().items()):
        if name.startswith('test_') and callable(check):
            check();print('PASS',name)
