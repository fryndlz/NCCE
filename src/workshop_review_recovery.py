"""Explicit owner recovery of a cancelled review that never claimed work."""
import json
import uuid

import codex_review_queue as cq
import writer_workshop as ws

# Exact pre/post source environments for this transport-only compatibility
# upgrade. Unknown source edits still invalidate the study; never waive a
# fingerprint just because draft instructions happen to match.
PREVIOUS_ENVIRONMENTS = {
    'a033f7cc2d774ee5e58e7683e61649bfd232e146bfff5b88859c60ee33ff62d3',
    '22deb0627c34d532d63f9d40aaba67720216da013059ac643b4cfdf9a8c89baf'}
REPAIRED_ENVIRONMENTS = {
    '1401e7921ba356a2c63ec96482c930fed6b8d76093dc72d7119a1e25b40502c8',
    '28131e30c1a4e85d5bf6d040ada131fd9b133fb249787c0f7a6021b5b2489936'}


def inspect(store, state):
    import workshop_optimizer as opt
    import workshop_experiments as exp
    import editorial_quality as quality
    if state.get('workflow_version') != 3 or state['status'] != 'escalated':
        raise ValueError('Only a paused controlled study can recover a review')
    current = opt.environment_fingerprint()
    if state.get('environment_hash') != current and not (
            state.get('environment_hash') in PREVIOUS_ENVIRONMENTS and current in REPAIRED_ENVIRONMENTS):
        raise ValueError('Generation environment changed beyond this transport repair')
    if state.get('quality_fingerprint') != quality.fingerprint() or state.get('editorial_contract') != quality.contract() or state['configuration'] != opt.configuration():
        raise ValueError('Reviewer, owner standards or writer configuration changed')
    for scope, expected in state['expected_active'].items():
        if (ws.active(store, scope) or {}).get('revision_id') != expected:
            raise ValueError('Active writing instructions changed')
    if any(v.get('run_id') == state['run_id'] for v in quality.records(store)):
        raise ValueError('Do not rebind a study with sealed owner verdicts')
    round_ = state['rounds'][-1]
    if round_['revision_id'] != state['specific']['revision_id']:
        raise ValueError('Saved candidate changed')
    samples = round_.get('prepared_samples') or (state['samples'] if round_['number'] == 1 else [])
    if len(samples) != 2 or len(round_['pairs']) != 2:
        raise ValueError('Recovery requires the complete saved two-entry draft round')
    baseline = ws.compose(state['form'], state['baseline']['shared'], state['baseline'][state['form']])
    candidate = ws.compose(state['form'], state['shared'], state['specific'])
    for i, (sample, pair) in enumerate(zip(samples, round_['pairs'])):
        if opt.hashed(ws.sample(store, sample['key'])['packet']) != sample['packet_hash'] or pair['sample_key'] != sample['key'] or pair['packet_hash'] != sample['packet_hash'] or pair['packet'] != sample['packet']:
            raise ValueError('Frozen source or plan changed')
        ci = pair.get('candidate_index')
        if type(ci) is not int or ci not in (0, 1) or pair['instructions'] != candidate or pair['comparison_instructions'][ci] != candidate or pair['comparison_instructions'][1-ci] != baseline:
            raise ValueError('Frozen A/B instructions or mapping changed')
        if len(pair['candidates']) != 2 or any(c['status'] != 'ready' for c in pair['candidates']):
            raise ValueError('Both original ready drafts are required')
        job = cq.get(store, pair['codex_job_id'])
        payload = json.loads(job['payload_json'])
        if job['run_id'] != state['run_id'] or payload.get('workflow_version') != 3 or payload.get('kind', 'review') != 'review' or payload['thread_id'] != cq.thread_id() or payload['packet'] != pair['packet'] or payload['candidates'] != pair['candidates'] or payload['comparison_instructions'] != pair['comparison_instructions']:
            raise ValueError('Saved review packet differs from the frozen pair')
        if i == 0:
            if job['status'] != 'completed' or json.loads(job['result_json']) != pair.get('review'):
                raise ValueError('The first original completed review must be intact')
            exp.validate_review(pair['review'])
        elif pair.get('review') or job['status'] != 'cancelled' or job['error'] != 'Codex review timed out; no automatic replay' or job['claimed_at'] or job['worker_id'] or job['lease_hash'] or json.loads(job['result_json'] or '{}'):
            raise ValueError('Only the definitively timed-out, never-claimed second review can be replaced')
        elif payload.get('form') != state['form'] or payload.get('editorial_contract') != state['editorial_contract'] or payload.get('output_schema') != exp.schema() or payload.get('rubric') != opt.RUBRIC:
            raise ValueError('Frozen review contract differs from the current protocol')
    if opt.assess(round_['pairs'][0]['review'])[1]:
        raise ValueError('The first review requires technical investigation before further work')
    count = sum(len(r['pairs']) for r in state['rounds'])
    if state['writer_reserved'] != count * 2 or state['reviewer_reserved'] != count or state['writer_reserved'] > state['writer_limit'] or state['reviewer_reserved'] > state['reviewer_limit']:
        raise ValueError('Saved reservations do not match the original allowance')
    if store.db.execute("SELECT 1 FROM workshop_optimization_runs WHERE run_id!=? AND json_extract(state_json,'$.status') IN ('queued','running')", (state['run_id'],)).fetchone():
        raise ValueError('Another writing study is active')
    return round_['pairs'][-1], job, payload


def available(store, state):
    try:
        _, job, _ = inspect(store, state)
        return {'job_id': job['job_id']}
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def recover(store, body):
    """Owner endpoint, atomic/idempotent; no provider or writer invocation."""
    import workshop_optimizer as opt
    key = body.get('request_key')
    if body.get('allow_review_recovery') is not True or not isinstance(key, str) or not 16 <= len(key) <= 100:
        raise ValueError('Explicit recovery and a request identity are required')
    with store._lock, store.db:
        store.db.execute('BEGIN IMMEDIATE')
        state = opt.get(store, body.get('run_id'))
        old = state.get('review_delivery_recovery')
        if old and old['request_key'] == key:
            if old['original_job_id'] != body.get('job_id'):
                raise ValueError('Recovery identity belongs to another job')
            return state, False
        if old:
            raise ValueError('A replacement already exists; inspect it instead of replaying')
        pair, job, payload = inspect(store, state)
        if job['job_id'] != body.get('job_id'):
            raise ValueError('Approve the exact cancelled review')
        replacement = 'review-' + uuid.uuid4().hex
        payload = {**payload, 'job_id': replacement, 'replacement_of': job['job_id']}
        payload.pop('transport_audit', None)
        store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at) VALUES(?,?,'queued',?,?)", (replacement, state['run_id'], cq.packed(payload), ws.now()))
        state['review_delivery_recovery'] = {'request_key': key, 'original_job_id': job['job_id'],
            'replacement_job_id': replacement, 'at': ws.now(), 'previous_environment_hash': state['environment_hash']}
        state['environment_hash'] = opt.environment_fingerprint()
        pair['codex_job_id'] = replacement
        state['resume_round'] = True
        state['status'] = 'queued'
        opt.activity(store, state, 'awaiting_reviewer', 'human', 'Owner recovered only the never-started review of these saved drafts. Writer calls and allowance are unchanged.')
    return state, True
