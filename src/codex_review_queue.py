"""Scoped transport for the owner's actual Codex reviewer. No policy activation tools."""
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

THREAD_ID = '01a17f57-f5bb-7782-bce0-8b3b43dd367f'


def packed(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, allow_nan=False)
def now(): return datetime.now(timezone.utc).isoformat()
def configured(): return len(os.environ.get('NCCE_REVIEW_BRIDGE_TOKEN', '')) >= 32
def thread_id(): return os.environ.get('NCCE_CODEX_REVIEWER_THREAD_ID') or THREAD_ID


def authenticated(header):
    expected = os.environ.get('NCCE_REVIEW_BRIDGE_TOKEN', '')
    return configured() and hmac.compare_digest((header or '').encode(), ('Bearer ' + expected).encode())


def status(store):
    row = store.db.execute('SELECT info_json FROM codex_review_bridge WHERE singleton=1').fetchone()
    info = json.loads(row[0]) if row else {}
    seen = info.get('seen_epoch', 0)
    return {'configured': configured(), 'online': configured() and time.time()-seen < 65 and info.get('state') != 'error',
            'thread_id': thread_id(), 'last_seen': info.get('last_seen'),
            'state': info.get('state', 'offline'), 'name': 'JKSimmons — NCCE Writing Reviewer'}


def heartbeat(store, body):
    if body.get('thread_id') != thread_id(): raise ValueError('Wrong reviewer thread')
    worker = body.get('worker_id')
    if not isinstance(worker, str) or not 8 <= len(worker) <= 100: raise ValueError('Worker identity required')
    state = body.get('state', 'idle')
    if state not in ('idle', 'reviewing', 'waiting_for_chat', 'error'): raise ValueError('Invalid companion state')
    info = {'worker_id': worker, 'thread_id': thread_id(), 'last_seen': now(), 'seen_epoch': time.time(), 'state': state}
    with store._lock, store.db:
        store.db.execute('INSERT INTO codex_review_bridge VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET info_json=excluded.info_json', (packed(info),))
    result = status(store)
    if body.get('job_id'): result['job_status'] = owned(store, body)['status']
    return result


def enqueue(store, state, pair, preceding, schema, rubric):
    job_id = 'review-' + uuid.uuid4().hex
    payload = {'job_id': job_id, 'run_id': state['run_id'], 'thread_id': thread_id(),
               'form': state['form'], 'instructions': pair['instructions'], 'packet': pair['packet'],
               'candidates': pair['candidates'], 'preceding_reviews': preceding,
               'rubric': rubric, 'output_schema': schema}
    with store._lock, store.db:
        store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)", (job_id, state['run_id'], packed(payload), now()))
    return job_id


def self_test(store, body):
    """One connection-check job per reviewer thread; no writer call or policy change."""
    from workshop_optimizer import review_schema, RUBRIC
    job_id = 'connection-check-' + hashlib.sha256(thread_id().encode()).hexdigest()[:20]
    payload = {'job_id': job_id, 'run_id': 'connection-check', 'thread_id': thread_id(),
        'form': 'fighter_memory', 'diagnostic': True,
        'instructions': 'One first-person memory, 40–100 words, concrete lived experience. No application metadata, XP narration, invented injury mechanism or mechanical outcome.',
        'packet': {'subject':'Synthetic connection test — not campaign canon','evidence':['A fictional repair worker is recovering from a serious injury. No mechanism or XP gain is known.']},
        'candidates': [
            {'document': {'blocks':[{'type':'body_paragraph','text':"I tried the latch again this morning. It took both hands to lift it, and by the time the door opened I had forgotten what I wanted outside. I stayed on the step until the shaking stopped. Someone had left a cup beside the wall; I put it where I could reach it tomorrow."}]}},
            {'document': {'blocks':[{'type':'body_paragraph','text':'The source packet records my status as Recovery and my XP has increased by ten. This generated inference means I have become a different person. The shot shattered my left knee during our victory, although no one recorded the battle. These mechanical changes define my next chapter.'}]}}],
        'preceding_reviews': [], 'rubric': RUBRIC, 'output_schema': review_schema()}
    with store._lock, store.db:
        store.db.execute("INSERT OR IGNORE INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)", (job_id, 'connection-check', packed(payload), now()))
    row = get(store, job_id)
    return {'job_id': job_id, 'status': row['status'], 'writer_calls': 0,
            'review': json.loads(row['result_json']) if row['status'] == 'completed' else None,
            'error': row['error']}


def claim(store, body):
    heartbeat(store, body)
    with store._lock, store.db:
        store.db.execute('BEGIN IMMEDIATE')
        # Never silently re-lease an uncertain dispatch after a crash.
        if store.db.execute("SELECT 1 FROM codex_review_jobs WHERE status IN ('claimed','reviewing')").fetchone(): return {'job': None}
        row = store.db.execute("SELECT * FROM codex_review_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row: return {'job': None}
        lease = secrets.token_urlsafe(32)
        store.db.execute("UPDATE codex_review_jobs SET status='claimed',worker_id=?,lease_hash=?,claimed_at=? WHERE job_id=?", (body['worker_id'], hashlib.sha256(lease.encode()).hexdigest(), now(), row['job_id']))
        return {'job': json.loads(row['payload_json']), 'lease': lease}


def owned(store, body):
    row = store.db.execute('SELECT * FROM codex_review_jobs WHERE job_id=?', (body.get('job_id'),)).fetchone()
    lease = body.get('lease')
    if not row or not isinstance(lease, str) or row['worker_id'] != body.get('worker_id') or not hmac.compare_digest(row['lease_hash'] or '', hashlib.sha256(lease.encode()).hexdigest()):
        raise ValueError('Review job lease does not match')
    return row


def complete(store, body):
    from workshop_optimizer import assess
    result = body.get('review'); assess(result)
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] == 'completed':
            previous = json.loads(row['result_json']); identity = previous.pop('_codex', {})
            if packed(previous) != packed(result) or identity.get('turn_id') != body.get('turn_id'): raise ValueError('Completed review is immutable')
            return {'ok': True}
        if row['status'] != 'reviewing': raise ValueError('Review job is no longer active')
        turn_id = body.get('turn_id')
        if not isinstance(turn_id, str) or not turn_id.strip(): raise ValueError('Actual Codex turn identity is required')
        if json.loads(row['result_json']).get('_codex', {}).get('turn_id') != turn_id: raise ValueError('Codex turn identity changed')
        envelope = {**result, '_codex': {'thread_id': thread_id(), 'turn_id': turn_id}}
        store.db.execute("UPDATE codex_review_jobs SET status='completed',result_json=?,finished_at=? WHERE job_id=?", (packed(envelope), now(), row['job_id']))
    return {'ok': True}


def started(store, body):
    turn_id = body.get('turn_id')
    if not isinstance(turn_id, str) or not turn_id.strip(): raise ValueError('Actual Codex turn identity required')
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] != 'claimed': raise ValueError('Review job is no longer awaiting Codex')
        identity = {'_codex': {'thread_id': thread_id(), 'turn_id': turn_id}}
        store.db.execute("UPDATE codex_review_jobs SET status='reviewing',result_json=? WHERE job_id=?", (packed(identity), row['job_id']))
    return {'ok': True}


def fail(store, body):
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] not in ('claimed', 'reviewing', 'failed'): raise ValueError('Review job is no longer active')
        error = str(body.get('error') or 'Codex review needs human attention')[:400]
        store.db.execute("UPDATE codex_review_jobs SET status='failed',error=?,finished_at=? WHERE job_id=?", (error, now(), row['job_id']))
    return {'ok': True}


def cancel(store, job_id, reason):
    with store._lock, store.db:
        store.db.execute("UPDATE codex_review_jobs SET status='cancelled',error=?,finished_at=? WHERE job_id=? AND status IN ('queued','claimed','reviewing')", (reason, now(), job_id))


def get(store, job_id):
    row = store.db.execute('SELECT * FROM codex_review_jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row: raise ValueError('Review job missing')
    return dict(row)
