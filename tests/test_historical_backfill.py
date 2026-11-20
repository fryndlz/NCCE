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
import bulk_qa as qa
from writing_exchange import digest

TEXT="**HARD LESSON**\n\nThe sump taught me to hold my ground. We still have a job to finish."


def fixture():
    tmp=tempfile.TemporaryDirectory(dir=ROOT/'data')
    store,bundle,fid,memory=setup(tmp.name)
    row=store.db.execute("SELECT gang_id FROM fighters WHERE id=?",(fid,)).fetchone()
    return tmp,store,str(row['gang_id'])


def create_job(store, gangs, **kwargs):
    return bulk.create(store, gangs, start_date="2026-01-01", end_date="2026-12-31", **kwargs)


def checkpoint_args(job_id, packet, text):
    return dict(job_id=job_id, request_id=packet["request"]["request_id"],
                source_revision=packet["request"]["source_revision"], version=0,
                state=dict(phase="review", draft=text, original="", issues=[],
                           draft_attempts=1, review_attempts=1,
                           context_hash=packet["context_hash"], guidance_hash="a"*64))


def approve(store, job_id, packet, text):
    payload = checkpoint_args(job_id, packet, text)
    assert qa.save(store, payload)["status"] == "saved"
    payload["version"] = 1
    payload["state"].update(phase="approved", draft_hash=qa.draft_hash(text),
                            checks={key:"Grounded in synthetic fixture" for key in qa.CHECKS})
    assert qa.save(store, payload)["status"] == "saved"


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



def test_memory_title_must_not_contain_fighter_name_or_alias():
    tmp,store,gang=fixture()
    try:
        candidate=next(c for c in exchange.candidates(store)
                       if c['form']=='fighter_memory')
        fid=candidate['entity_key']
        store.db.execute("UPDATE fighters SET name='Mara Kel' WHERE id=?",(fid,))
        assert exchange.fighter_memory_title_error(store,candidate,
            "**MARA KEL // STILL STANDING**\n\nAn observation.")
        assert exchange.fighter_memory_title_error(store,candidate,
            "**WHAT MARA SAW**\n\nAn observation.")
        assert exchange.fighter_memory_title_error(store,candidate,
            "**THE KEL REPORT**\n\nAn observation.")
        assert not exchange.fighter_memory_title_error(store,candidate,
            "**STILL STANDING**\n\nAn observation.")
        store.db.execute("UPDATE fighters SET name='Severus „Bezlitosny”' WHERE id=?",(fid,))
        assert exchange.fighter_memory_title_error(store,candidate,
            "**BEZLITOSNY // THE ORDER**\n\nAn observation.")
        assert exchange.fighter_memory_title_error(store,candidate,
            "**SEVERUS / THE ORDER**\n\nAn observation.")
        assert not exchange.fighter_memory_title_error(store,candidate,
            "**THE ORDER**\n\nAn observation.")
        assert not exchange.fighter_memory_title_error(store,
            {**candidate,'form':'fighter_reflection'},
            "**SEVERUS // THE ORDER**\n\nA reflection.")
    finally:store.close();tmp.cleanup()


def test_owner_authorization_scoped_and_schema_present():
    tmp,s,gang=fixture()
    try:
        assert s.schema_version>=21
        with raises(ValueError,match='owner authorization'):
            create_job(s,[gang])
        assert s.db.execute("SELECT count(*) FROM historical_backfill_jobs").fetchone()[0]==0
        job=create_job(s,[gang],owner_authorized=True)
        assert job['scope']==[gang]
        assert job['queued']>=1,job
        assert job['discovered']>=job['queued']
        assert set(bulk.reserved_targets(s))
        with raises(ValueError,match='already has an active'):
            create_job(s,[gang],owner_authorized=True)
        with raises(ValueError,match='must exist'):
            create_job(s,['fake-gang-id'],owner_authorized=True)
        assert bulk.summary(s,job['job_id'])['count']>=1
    finally:s.close();tmp.cleanup()


def test_normal_exchange_skips_bulk_reservations_without_changing_legacy_queue():
    tmp,s,gang=fixture()
    try:
        job=create_job(s,[gang],owner_authorized=True)
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
        job=create_job(s,[gang],owner_authorized=True)
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
        approve(s, job['job_id'], packet, TEXT)
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
        job=create_job(s,[gang],owner_authorized=True)
        selected=next(x for x in bulk._items(s,job['job_id']) if x['form']=='fighter_memory')
        c=next(c for c in exchange.candidates(s) if exchange.target_key(c)==selected['target_key'])
        with patch.object(bulk,'plan',return_value=([c],{},{})):
            packet=bulk.poll(s,job['job_id'],1)['packets'][0]
        approve(s, job['job_id'], packet, TEXT)
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
        job=create_job(s,[gang],owner_authorized=True)
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
        job=create_job(s,[gang],owner_authorized=True)
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


def test_requires_exact_passing_checklist_before_import():
    tmp, store, gang = fixture()
    try:
        job = create_job(store, [gang], owner_authorized=True)["job_id"]
        candidate = next(c for c in exchange.candidates(store) if c["form"] == "fighter_memory")
        with patch.object(bulk, "plan", return_value=([candidate], {}, {})):
            packet = bulk.poll(store, job, 1)["packets"][0]
        delivery = {**packet["request"], "status":"READY", "writer_text_md":TEXT}
        with raises(ValueError, match="requires the current independent QA"):
            bulk.deliver(store, job, delivery)
        delivery["qa_protocol"] = qa.PROTOCOL
        assert bulk.deliver(store, job, delivery)["status"] == "needs_review"
        args = checkpoint_args(job, packet, TEXT)
        assert qa.save(store, args)["version"] == 1
        assert qa.save(store, args)["status"] == "stale"
        args["version"] = 1
        checks = {key:"Cited evidence" for key in qa.CHECKS}
        args["state"].update(phase="approved", draft_hash=qa.draft_hash(TEXT), checks=checks)
        del checks["chronology"]
        with raises(ValueError, match="all seven"):
            qa.save(store, args)
        checks["chronology"] = "Correct fixture order"
        assert qa.save(store, args)["version"] == 2
        assert bulk.deliver(store, job, {**delivery, "writer_text_md":TEXT + " Changed."})["status"] == "needs_review"
        assert bulk.deliver(store, job, delivery)["status"] == "imported"
    finally:
        store.close()
        tmp.cleanup()


def test_inclusive_utc_dates_manifest_and_admission_cap():
    tmp, store, gang = fixture()
    try:
        for dates in ({}, {"start_date":"2026-02-30", "end_date":"2026-03-01"},
                      {"start_date":"2026-03-02", "end_date":"2026-03-01"}):
            with raises(ValueError):
                bulk.create(store, [gang], owner_authorized=True, **dates)
        selected = [c for c in exchange.candidates(store) if c["form"] == "fighter_memory"]
        at = next(c["event_at_utc"] for c in selected if c["event_at_utc"])
        day = bulk.instant(at).date().isoformat()
        with raises(ValueError, match="explicit max_items"):
            bulk.create(store, [gang], start_date=day, end_date=day,
                        owner_authorized=True, autonomous_writer_authorized=True)
        result = bulk.create(store, [gang], start_date=day, end_date=day, owner_authorized=True)
        assert result["discovered"]
        report = bulk.summary(store, result["job_id"], include_items=True)
        assert report["manifest"]["start_date"] == report["manifest"]["end_date"] == day
        assert all(bulk.instant(item["event_at_utc"]).date().isoformat() == day for item in report["items"])
        assert bulk._within({"event_at_utc":day + "T23:59:59Z"}, bulk.date.fromisoformat(day), bulk.date.fromisoformat(day))
        assert not bulk._within({"event_at_utc":day + "T23:59:59-01:00"}, bulk.date.fromisoformat(day), bulk.date.fromisoformat(day))
        assert not bulk._within({}, bulk.date.fromisoformat(day), bulk.date.fromisoformat(day))
    finally:
        store.close()
        tmp.cleanup()


def test_terminal_prerequisites_keep_exact_ids_and_reasons():
    tmp, store, gang = fixture()
    try:
        job_id = create_job(store, [gang], owner_authorized=True)["job_id"]
        original = bulk._items(store, job_id)
        blockers = {r["target_key"]:["Unapproved baseline"] for r in original}
        with patch.object(bulk, "plan", return_value=([], {}, blockers)):
            assert bulk.poll(store, job_id)["blocked"] == len(original)
            assert bulk.poll(store, job_id, resolve_blocked=True)["job"]["statuses"]["HOLD"] == len(original)
        assert [r["request_id"] for r in original] == [r["request_id"] for r in bulk._items(store, job_id)]
        assert all("Unapproved baseline" in r["error"] for r in bulk._items(store, job_id))
        assert bulk.close(store, job_id)["state"] == "COMPLETED_WITH_ERRORS"
    finally:
        store.close()
        tmp.cleanup()


if __name__=='__main__':
    for name,check in list(globals().items()):
        if name.startswith('test_') and callable(check):
            check();print('PASS',name)
