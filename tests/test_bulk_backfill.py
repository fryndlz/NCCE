"""Historical backfill isolation, sequencing, import safety and correction tests."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]

from test_writing_exchange import setup
import bulk_backfill as bulk
import exchange_automation as exchange

GOOD = "**THE OLD ROAD**\n\nThe load got home. I remember the iron more than the shouting."


def scenario():
    temporary = tempfile.TemporaryDirectory(dir=ROOT / 'data')
    store, bundle, fighter_id, memory = setup(temporary.name)
    gang_id = store.db.execute(
        "SELECT gang_id FROM fighters WHERE id=?", (fighter_id,)
    ).fetchone()[0]
    return temporary, store, fighter_id, gang_id


def first(store, job_id):
    claimed = bulk.claim(store, job_id, 50)
    assert claimed
    return claimed[0]


def test_snapshot_never_publishes_to_normal_queue_before_authorization():
    temp, s, fid, gid = scenario()
    try:
        normal_before = exchange.outbox(s)
        job = bulk.create_job(s, gid)
        assert job['state'] == 'PREPARED'
        assert job['approval_policy'] == 'MANUAL'
        assert job['snapshot_count'] >= 1
        assert exchange.outbox(s) == normal_before
        assert all(item['status'] if 'status' in item else item['state']
                   for item in bulk.list_items(s, job['job_id']))
        assert all(
            r['bulk_job_id'] == job['job_id']
            for r in s.db.execute(
                "SELECT bulk_job_id FROM writing_exchange_requests WHERE bulk_job_id=?",
                (job['job_id'],)
            )
        )
        try:
            bulk.claim(s, job['job_id'])
            assert False, "No writing before owner authorization"
        except ValueError:
            pass
        try:
            bulk.authorize_job(s, job['job_id'], job['snapshot_count'] + 1)
            assert False, "A stale snapshot cannot be authorized"
        except ValueError:
            pass
        try:
            bulk.create_job(s, gid)
            assert False, "Only one active job per gang"
        except Exception:
            pass
        authorized = bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        assert authorized['approval_policy'] == 'AUTO'
        assert authorized['state'] == 'AUTHORIZED'
        assert exchange.outbox(s) == normal_before
    finally:
        s.close(); temp.cleanup()


def test_bulk_import_reuses_normal_validation_receipt_and_no_facts_are_changed():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        item = first(s, job['job_id'])
        rid = item['request_id']
        assert all(p['request']['request_id'] != rid for p in exchange.outbox(s))
        assert not bulk.claim(s, job['job_id'])  # One per fighter until prior imported
        before = {
            t: [tuple(r) for r in s.db.execute('SELECT * FROM ' + t)]
            for t in ('fighters', 'campaign_events', 'snapshots', 'event_subjects')
        }
        try:
            exchange.deliver(s, {
                'request_id': rid, 'status': 'READY',
                'source_revision': item['packet']['request']['source_revision'],
                'writer_text_md': GOOD,
            })
            assert False, "Ordinary delivery route must reject a bulk request"
        except ValueError:
            pass
        result = bulk.submit(
            s, job['job_id'], rid,
            item['packet']['request']['source_revision'], GOOD
        )
        assert result['status'] == 'imported', result
        repeated = bulk.submit(
            s, job['job_id'], rid,
            item['packet']['request']['source_revision'], GOOD
        )
        assert repeated['status'] == 'imported' and repeated['reused']
        assert repeated['receipt'] == result['receipt']
        assert {t: [tuple(r) for r in s.db.execute('SELECT * FROM ' + t)]
                for t in before} == before
        assert s.db.execute(
            'SELECT raw_markdown FROM writing_exchange_requests WHERE request_id=?',
            (rid,)
        ).fetchone()[0] == GOOD
        assert exchange.outbox(s) == []
    finally:
        s.close(); temp.cleanup()


def test_bad_draft_held_then_retried_without_changing_ids():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        item = first(s, job['job_id'])
        rid = item['request_id']
        invalid = "**NO**\n\n" + 'A' * 400
        result = bulk.submit(
            s, job['job_id'], rid,
            item['packet']['request']['source_revision'], invalid
        )
        assert result['status'] == 'held'
        assert bulk._item(s, job['job_id'], rid)['writer_text_md'] == invalid
        assert s.db.execute(
            'SELECT state FROM writing_exchange_requests WHERE request_id=?',
            (rid,)
        ).fetchone()[0] == 'DEFERRED'
        bulk.retry_held(s, job['job_id'], rid)
        assert bulk._item(s, job['job_id'], rid)['state'] == 'PENDING'
        recovered = first(s, job['job_id'])
        assert recovered['request_id'] == rid
        assert bulk.submit(
            s, job['job_id'], rid,
            recovered['packet']['request']['source_revision'], GOOD
        )['status'] == 'imported'
    finally:
        s.close(); temp.cleanup()


def test_hold_escalation_returns_to_normal_approval_without_forging_new_id():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        item = first(s, job['job_id'])
        rid = item['request_id']
        bulk.submit(s, job['job_id'], rid,
                    'sha256:outdated', GOOD)
        escalated = bulk.escalate(s, job['job_id'], rid)
        assert escalated['state'] == 'ESCALATED'
        row = s.db.execute(
            'SELECT state,bulk_job_id,source_revision FROM writing_exchange_requests WHERE request_id=?',
            (rid,)
        ).fetchone()
        assert row['bulk_job_id'] is None and row['state'] == 'DEFERRED'
        # The normal producer owns its own five-item window again.
        assert not bulk.is_reserved(s, item['packet']['request']['entry_key'])
        assert exchange.outbox(s) == []
        assert s.db.execute(
            'SELECT count(*) FROM writing_bulk_audit WHERE request_id=?', (rid,)
        ).fetchone()[0] >= 2
    finally:
        s.close(); temp.cleanup()


def test_versioned_manual_correction_of_imported_bulk_memory():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        item = first(s, job['job_id'])
        rid = item['request_id']
        result = bulk.submit(
            s, job['job_id'], rid,
            item['packet']['request']['source_revision'], GOOD
        )
        revision = bulk.correct_import(
            s, job['job_id'], rid, result['receipt']
        )
        assert revision['status'] == 'PENDING'
        assert revision['request_id'] != rid
        old = s.db.execute(
            'SELECT state,raw_markdown,receipt FROM writing_exchange_requests WHERE request_id=?',
            (rid,)
        ).fetchone()
        assert old['state'] == 'IMPORTED'
        assert old['raw_markdown'] == GOOD
        assert old['receipt'] == result['receipt']
        newer = s.db.execute(
            'SELECT revision_of,bulk_job_id FROM writing_exchange_requests WHERE request_id=?',
            (revision['request_id'],)
        ).fetchone()
        assert newer['revision_of'] == rid
        assert newer['bulk_job_id'] is None  # Manual approval is restored.
    finally:
        s.close(); temp.cleanup()


def test_job_can_finish_only_after_every_item_imported_or_escalated():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        try:
            bulk.finish(s, job['job_id'])
            assert False, "Cannot silently close unfinished memories"
        except ValueError:
            pass
        items = bulk.list_items(s, job['job_id'], limit=50)
        for item in items:
            bulk.escalate(s, job['job_id'], item['request_id'])
        closed = bulk.finish(s, job['job_id'])
        assert closed['state'] == 'COMPLETED_WITH_ERRORS'
        assert all(item['state'] == 'ESCALATED'
                   for item in bulk.list_items(s, job['job_id'], limit=50))
    finally:
        s.close(); temp.cleanup()


def test_cancel_releases_to_normal_lifecycle_but_preserves_imported_text():
    temp, s, fid, gid = scenario()
    try:
        job = bulk.create_job(s, gid)
        bulk.authorize_job(s, job['job_id'], job['snapshot_count'])
        item = first(s, job['job_id'])
        accepted = bulk.submit(
            s, job['job_id'], item['request_id'],
            item['packet']['request']['source_revision'], GOOD
        )
        assert accepted['status'] == 'imported'
        cancelled = bulk.cancel(s, job['job_id'])
        assert cancelled['state'] == 'CANCELLED'
        assert s.db.execute(
            'SELECT state FROM writing_exchange_requests WHERE request_id=?',
            (item['request_id'],)
        ).fetchone()[0] == 'IMPORTED'
        assert s.db.execute(
            'SELECT raw_markdown FROM writing_exchange_requests WHERE request_id=?',
            (item['request_id'],)
        ).fetchone()[0] == GOOD
    finally:
        s.close(); temp.cleanup()


if __name__ == '__main__':
    for name, check in list(globals().items()):
        if name.startswith('test_') and callable(check):
            check()
            print('PASS', name)
