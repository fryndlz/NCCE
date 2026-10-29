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
def configured():
    value = os.environ.get('NCCE_REVIEW_BRIDGE_TOKEN_SHA256', '')
    return len(value) == 64 and all(c in '0123456789abcdef' for c in value)
def thread_id(): return os.environ.get('NCCE_CODEX_REVIEWER_THREAD_ID') or THREAD_ID

def valid_thread(value):
    from workshop_interventions import TECH_THREAD_ID
    return value in (thread_id(),TECH_THREAD_ID)


def authenticated(header):
    if not configured() or not isinstance(header, str) or not header.startswith('Bearer '): return False
    token = header[7:]
    if not 32 <= len(token) <= 300: return False
    expected = os.environ['NCCE_REVIEW_BRIDGE_TOKEN_SHA256']
    return hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected)


def status(store):
    row = store.db.execute('SELECT info_json FROM codex_review_bridge WHERE singleton=1').fetchone()
    info = json.loads(row[0]) if row else {}
    seen = info.get('seen_epoch', 0)
    diagnostic = latest_check(store)
    verified = bool(diagnostic and diagnostic['status'] == 'completed')
    ttl = max(65, info.get('poll_interval', 0) + 60)
    return {'configured': configured(), 'online': configured() and verified and time.time()-seen < ttl and info.get('state') != 'error',
            'transport': info.get('transport', 'stdio'), 'poll_interval': info.get('poll_interval', 0),
            'verified': verified, 'connection_error': diagnostic['error'] if diagnostic and diagnostic['error'] else ('' if verified else 'The actual Codex reviewer connection has not passed its test.'),
            'thread_id': thread_id(), 'last_seen': info.get('last_seen'),
            'state': info.get('state', 'offline'), 'name': 'JKSimmons — NCCE Writing Reviewer'}


def heartbeat(store, body):
    if not valid_thread(body.get('thread_id')): raise ValueError('Wrong agent thread')
    if body['thread_id']!=thread_id():
        result={'thread_id':body['thread_id'],'state':body.get('state','idle')}
        if body.get('job_id'):result['job_status']=owned(store,body)['status']
        return result
    worker = body.get('worker_id')
    if not isinstance(worker, str) or not 8 <= len(worker) <= 100: raise ValueError('Worker identity required')
    state = body.get('state', 'idle')
    if state not in ('idle', 'reviewing', 'waiting_for_chat', 'error'): raise ValueError('Invalid companion state')
    interval = body.get('poll_interval', 0)
    if type(interval) is not int or not 0 <= interval <= 300: raise ValueError('Invalid polling interval')
    info = {'worker_id': worker, 'thread_id': thread_id(), 'last_seen': now(), 'seen_epoch': time.time(), 'state': state,
            'poll_interval': interval, 'transport': body.get('transport') if body.get('transport') in ('codex_chat','queue_listener') else 'stdio'}
    with store._lock, store.db:
        store.db.execute('INSERT INTO codex_review_bridge VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET info_json=excluded.info_json', (packed(info),))
    result = status(store)
    if body.get('job_id'): result['job_status'] = owned(store, body)['status']
    return result


def enqueue(store, state, pair, preceding, schema, rubric):
    from fighter_event_clock import policy as cognitive_policy
    job_id = 'review-' + uuid.uuid4().hex
    payload = {'job_id': job_id, 'run_id': state['run_id'], 'thread_id': thread_id(),
               'form': state['form'], 'instructions': pair['instructions'], 'packet': pair['packet'],
               'candidates': pair['candidates'], 'preceding_reviews': preceding,
               'rubric': rubric, 'output_schema': schema, 'cognitive_design':cognitive_policy(),
               'objective':'Improve the reusable category setup, never rewrite the candidate texts. Propose complete general form instructions; flag context/system defects for StoryTechMan. In your summary name the prose category and explain concretely what you propose changing in its reusable guidelines and why. A proposal does not activate instructions; the application records saved candidates separately.',
               'round_kind':state.get('rounds',[{}])[-1].get('kind','learning') if state.get('rounds') else 'learning'}
    if state.get('workflow_version',1)>=3:
        import editorial_quality
        payload.update(workflow_version=3, editorial_contract=state['editorial_contract'],
            hypothesis=state['hypothesis'], comparison_instructions=pair['comparison_instructions'],
            prior_owner_corrections=editorial_quality.training_feedback(store,state['form']))
        from editorial_sync import standards
        payload['reviewer_standards']=standards(store,state['form'])
        payload.pop('instructions',None)
        payload['objective'] = ('Blindly compare A and B. Both use the same model, source context and response limits; only the instructions differ. '
            'Do not infer which is current or candidate. Apply the explicit owner editorial contract before scoring: subject, first-read clarity, direct register and useful-or-empty closing. '
            'Scores are advisory, never proof of qualification. Explain changed/addresses/observed_effect/regressions. '
            'On entry two, consolidate reusable proposed_form_instructions across BOTH entries and preceding reviews. '
            'Never rewrite a candidate text or activate anything. Historical owner examples are training data, not fresh calibration evidence. '
            'Prior sealed feedback is coaching. Do not inspect owner verdicts for THIS draft pair or infer them from this chat. If already exposed to this pair’s owner verdict, fail the job instead of claiming independence.')
    with store._lock, store.db:
        store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)", (job_id, state['run_id'], packed(payload), now()))
    return job_id


def events(store, body):
    """Long-poll for work identifiers only. Never claims a job or starts a model."""
    heartbeat(store, body)
    wait = body.get('wait_seconds', 25)
    if type(wait) is not int or not 0 <= wait <= 25: raise ValueError('Invalid event wait')
    deadline = time.monotonic() + wait
    while True:
        with store._lock:
            row = store.db.execute("SELECT job_id FROM codex_review_jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if row:
            payload=json.loads(store.db.execute('SELECT payload_json FROM codex_review_jobs WHERE job_id=?',(row['job_id'],)).fetchone()[0])
            return {'job_id':row['job_id'], 'kind':payload.get('kind','review'), 'thread_id':payload.get('thread_id',thread_id())}
        if time.monotonic() >= deadline: return {'job_id': None}
        time.sleep(min(.5, max(0, deadline-time.monotonic())))


def connection_check_id():
    return 'connection-check-' + hashlib.sha256(thread_id().encode()).hexdigest()[:20]


def latest_check(store):
    return store.db.execute("SELECT * FROM codex_review_jobs WHERE run_id='connection-check' AND json_extract(payload_json,'$.thread_id')=? ORDER BY created_at DESC LIMIT 1", (thread_id(),)).fetchone()


def self_test(store, body):
    """One connection-check job per reviewer thread; no writer call or policy change."""
    from workshop_optimizer import review_schema, RUBRIC
    previous = latest_check(store)
    job_id = previous['job_id'] if previous else connection_check_id()
    if body.get('new_attempt'):
        if previous and previous['status'] not in ('failed', 'cancelled', 'completed'): raise ValueError('Existing connection check must finish; no replay')
        job_id = connection_check_id() + '-' + uuid.uuid4().hex[:12]
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
    heartbeat(store, {k:v for k,v in body.items() if k not in ('job_id','lease')})
    with store._lock, store.db:
        store.db.execute('BEGIN IMMEDIATE')
        # Never silently re-lease an uncertain dispatch after a crash.
        if store.db.execute("SELECT 1 FROM codex_review_jobs WHERE status IN ('claimed','reviewing') AND json_extract(payload_json,'$.thread_id')=?",(body['thread_id'],)).fetchone(): return {'job': None}
        if body.get('job_id'):
            row = store.db.execute("SELECT * FROM codex_review_jobs WHERE status='queued' AND job_id=? AND json_extract(payload_json,'$.thread_id')=?", (body['job_id'],body['thread_id'])).fetchone()
        else:
            row = store.db.execute("SELECT * FROM codex_review_jobs WHERE status='queued' AND json_extract(payload_json,'$.thread_id')=? ORDER BY created_at LIMIT 1",(body['thread_id'],)).fetchone()
        if not row: return {'job': None}
        payload=json.loads(row['payload_json'])
        if payload.get('kind')=='editorial_consolidation':
            from editorial_sync import prepare_claim
            payload=prepare_claim(store,payload)
        lease = secrets.token_urlsafe(32)
        store.db.execute("UPDATE codex_review_jobs SET status='claimed',worker_id=?,lease_hash=?,claimed_at=? WHERE job_id=?", (body['worker_id'], hashlib.sha256(lease.encode()).hexdigest(), now(), row['job_id']))
        return {'job': payload, 'lease': lease}


def owned(store, body):
    row = store.db.execute('SELECT * FROM codex_review_jobs WHERE job_id=?', (body.get('job_id'),)).fetchone()
    lease = body.get('lease')
    if not row or json.loads(row['payload_json']).get('thread_id')!=body.get('thread_id') or not isinstance(lease, str) or row['worker_id'] != body.get('worker_id') or not hmac.compare_digest(row['lease_hash'] or '', hashlib.sha256(lease.encode()).hexdigest()):
        raise ValueError('Review job lease does not match')
    return row


def complete(store, body):
    from workshop_optimizer import assess
    result = body.get('review')
    row=owned(store,body);payload=json.loads(row['payload_json'])
    if payload.get('kind')=='editorial_consolidation':
        from editorial_sync import validate
        validate(result)
    elif payload.get('kind','review')=='review':
        if payload.get('workflow_version',1)>=3:
            from workshop_experiments import validate_review
            validate_review(result)
        else:assess(result)
    else:
        from workshop_interventions import validate
        validate(payload['kind'],result,payload.get('report_version',1))
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] == 'completed':
            previous = json.loads(row['result_json']); identity = previous.pop('_codex', {})
            if packed(previous) != packed(result) or identity.get('turn_id') != body.get('turn_id'): raise ValueError('Completed review is immutable')
            if payload.get('kind')=='editorial_consolidation':
                from editorial_sync import export
                return {'ok':True,'standards_export':export(store,payload)}
            return {'ok': True}
        if row['status'] != 'reviewing': raise ValueError('Review job is no longer active')
        turn_id = body.get('turn_id')
        if not isinstance(turn_id, str) or not turn_id.strip(): raise ValueError('Actual Codex turn identity is required')
        if json.loads(row['result_json']).get('_codex', {}).get('turn_id') != turn_id: raise ValueError('Codex turn identity changed')
        identity={'thread_id':payload['thread_id'],'turn_id':turn_id}
        envelope = {**result, '_codex': identity}
        if payload.get('kind')=='editorial_consolidation':
            from editorial_sync import complete as finish_learning
            finish_learning(store,payload,result,identity)
        elif payload.get('kind','review')!='review' and not payload.get('diagnostic'):
            from workshop_interventions import complete as finish_technical
            finish_technical(store,payload,result,identity)
        store.db.execute("UPDATE codex_review_jobs SET status='completed',result_json=?,finished_at=? WHERE job_id=?", (packed(envelope), now(), row['job_id']))
    if payload.get('kind')=='editorial_consolidation':
        from editorial_sync import export
        return {'ok':True,'standards_export':export(store,payload)}
    return {'ok': True}


def started(store, body):
    turn_id = body.get('turn_id')
    if not isinstance(turn_id, str) or not turn_id.strip(): raise ValueError('Actual Codex turn identity required')
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] != 'claimed': raise ValueError('Review job is no longer awaiting Codex')
        payload=json.loads(row['payload_json'])
        payload.setdefault('transport_audit', {})['started_at'] = now()
        identity = {'_codex': {'thread_id': payload['thread_id'], 'turn_id': turn_id}}
        if payload.get('kind')=='editorial_consolidation':
            from editorial_sync import set_status
            set_status(store,payload,'reviewing','JKSimmons is incorporating your sealed feedback into his standards and candidate guidance.')
        elif payload.get('kind','review')!='review' and not payload.get('diagnostic'):
            from workshop_interventions import started as technical_started
            technical_started(store,payload)
        store.db.execute("UPDATE codex_review_jobs SET status='reviewing',result_json=?,payload_json=? WHERE job_id=?", (packed(identity), packed(payload), row['job_id']))
    return {'ok': True}


def fail(store, body):
    with store._lock, store.db:
        row = owned(store, body)
        if row['status'] not in ('claimed', 'reviewing', 'failed'): raise ValueError('Review job is no longer active')
        error = str(body.get('error') or 'Codex review needs human attention')[:400]
        payload=json.loads(row['payload_json'])
        if payload.get('kind')=='editorial_consolidation':
            from editorial_sync import set_status
            set_status(store,payload,'failed',error)
        elif payload.get('kind','review')!='review' and not payload.get('diagnostic'):
            from workshop_interventions import failed
            failed(store,payload,error)
        store.db.execute("UPDATE codex_review_jobs SET status='failed',error=?,finished_at=? WHERE job_id=?", (error, now(), row['job_id']))
    return {'ok': True}


def cancel(store, job_id, reason):
    with store._lock, store.db:
        store.db.execute("UPDATE codex_review_jobs SET status='cancelled',error=?,finished_at=? WHERE job_id=? AND status IN ('queued','claimed','reviewing')", (reason, now(), job_id))


def get(store, job_id):
    row = store.db.execute('SELECT * FROM codex_review_jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row: raise ValueError('Review job missing')
    return dict(row)


def transport(store, job_id):
    """Allowlisted transport evidence, never leases, workers or hidden verdicts."""
    row = get(store, job_id)
    audit = json.loads(row['payload_json']).get('transport_audit', {})
    return {'job_id': job_id, 'status': row['status'], 'enqueued_at': row['created_at'],
            'notification_accepted_at': audit.get('notification_accepted_at'),
            'claimed_at': row['claimed_at'], 'started_at': audit.get('started_at'),
            'finished_at': row['finished_at'], 'terminal_cause': row['error'] or ''}


def notified(store, body):
    """A queue CLI acknowledgement is not a native claim or review start."""
    row = get(store, body.get('job_id'))
    payload = json.loads(row['payload_json'])
    if not valid_thread(body.get('thread_id')) or payload.get('thread_id') != body['thread_id']:
        raise ValueError('Wrong notification thread')
    audit = payload.setdefault('transport_audit', {})
    if not audit.get('notification_accepted_at'):
        audit['notification_accepted_at'] = now()
        with store._lock, store.db:
            store.db.execute('UPDATE codex_review_jobs SET payload_json=? WHERE job_id=?', (packed(payload), row['job_id']))
    return {'ok': True}
