"""Bounded in-app prompt optimization. Auth/same-origin/pipeline lock are server-owned.

Writes only private Workshop drafts, trials and audit until explicit promotion.
No model can activate a policy, alter sources, increase budget or execute tools.
"""
import hashlib
import json
import math
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import llm_writer as writer
import writer_workshop as ws
from writer_quality import CRITERIA, RUBRIC


def packed(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
def hashed(value): return hashlib.sha256(packed(value).encode()).hexdigest()


def configuration():
    return {'writer_model': writer.MODEL, 'writer_effort': writer.DEFAULT_REASONING_EFFORT,
            'reviewer_model': os.environ.get('NCCE_REVIEWER_MODEL') or writer.MODEL,
            'reviewer_effort': os.environ.get('NCCE_REVIEWER_REASONING_EFFORT') or writer.DEFAULT_REASONING_EFFORT,
            'max_output_tokens': writer.MAX_OUTPUT_TOKENS}


def get(store, run_id):
    row = store.db.execute('SELECT state_json FROM workshop_optimization_runs WHERE run_id=?', (run_id,)).fetchone()
    if not row: raise ValueError('Optimization run not found')
    return json.loads(row[0])


def save(store, state, action=None):
    if action: state['events'].append({'at': ws.now(), 'message': action})
    with store._lock, store.db:
        store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?', (packed(state), state['run_id']))


def activity(store, state, phase, actor, message, **position):
    """Persist observable work before it begins; the UI never invents agent activity."""
    state['activity'] = {'phase': phase, 'actor': actor, 'message': message, 'at': ws.now(), **position}
    visited = state.setdefault('visited_steps', [])
    if phase not in visited: visited.append(phase)
    save(store, state, actor + ': ' + message)


def home(store):
    return {'configuration': configuration(), 'configured': bool(writer.API_KEY),
            'runs': [json.loads(r[0]) for r in store.db.execute('SELECT state_json FROM workshop_optimization_runs ORDER BY rowid DESC LIMIT 12')]}


def existing(store, body):
    row = store.db.execute('SELECT request_hash,state_json FROM workshop_optimization_runs WHERE request_key=?', (body.get('request_key'),)).fetchone()
    if row:
        if row[0] != hashed(body): raise ValueError('Request key belongs to different optimization settings')
        return json.loads(row[1])


def queue(store, body):
    old = existing(store, body)
    if old: return old, False
    if body.get('allow_paid') is not True: raise ValueError('Explicit writer AND reviewer call authorization is required')
    rounds = body.get('max_rounds', 1)
    if type(rounds) is not int or not 1 <= rounds <= 3: raise ValueError('Choose 1–3 optimization rounds')
    key = body.get('request_key')
    if not isinstance(key, str) or not 16 <= len(key) <= 100: raise ValueError('A unique request key is required')
    if not writer.API_KEY: raise ValueError('The server writing provider is not configured; no calls made')
    selected = ws.sample(store, body.get('sample_key'))
    # Two independent real contexts: duplicate A/B comparison packets do not count.
    samples = [selected]; seen = {hashed(selected['packet'])}
    for entry in ws.catalog(store):
        if entry['form'] != selected['form'] or entry['key'] == selected['key']: continue
        other = ws.sample(store, entry['key'])
        fingerprint = hashed(other['packet'])
        if fingerprint not in seen: samples.append(other); seen.add(fingerprint)
        if len(samples) == 2: break
    if len(samples) < 2:
        raise ValueError('This form needs a second independent sourced sample to test consistency. No calls made.')
    specific = ws.revision(store, body['form_revision_id'], selected['form']) if body.get('form_revision_id') else ws.defaults(selected['form'])
    shared = ws.revision(store, body['shared_revision_id'], 'shared') if body.get('shared_revision_id') else ws.defaults('shared')
    if not specific.get('revision_id'): specific = ws.save_revision(store, specific)
    if not shared.get('revision_id'): shared = ws.save_revision(store, shared)
    prepared = []
    for sample in samples:
        options = {**body, 'sample_key': sample['key'], 'shared_revision_id': shared['revision_id'], 'form_revision_id': specific['revision_id']}
        if sample['key'] != selected['key']:
            options.pop('packet_hash', None); options.pop('plan_key', None)
        prepared.append(ws.preview(store, options))
    state = {'run_id': 'opt-' + uuid.uuid4().hex, 'status': 'queued', 'form': selected['form'],
             'created_at': ws.now(), 'configuration': configuration(), 'max_rounds': rounds,
             'writer_limit': rounds * 4, 'reviewer_limit': rounds * 2,
             'writer_reserved': 0, 'reviewer_reserved': 0, 'shared': shared, 'specific': specific,
             'expected_active': {scope: (ws.active(store, scope) or {}).get('revision_id') for scope in ('shared', selected['form'])},
             'samples': prepared, 'rounds': [], 'events': [], 'message': '', 'decision': None,
             'coverage': 'Two independent source packets for one prose form; representative checks, not a guarantee across all prose.',
             'activity': {'phase': 'queued', 'actor': 'StoryTechMan', 'message': 'Your bounded run is queued. Preparing the source checks.', 'at': ws.now()},
             'visited_steps': [],
             'reviewer_context': 'Recovered requirements and saved NCCE editorial feedback; original chat reviews/images unavailable.'}
    with store._lock, store.db:
        store.db.execute('INSERT INTO workshop_optimization_runs VALUES(?,?,?,?)', (state['run_id'], key, hashed(body), packed(state)))
    return state, True


def stop(store, state, message, status='escalated'):
    state['status'] = status; state['message'] = message
    activity(store, state, status, 'StoryTechMan', message)


def recover(store):
    for row in store.db.execute('SELECT state_json FROM workshop_optimization_runs').fetchall():
        state = json.loads(row[0])
        if state['status'] in ('queued', 'running'):
            stop(store, state, 'Server restarted. Inspect retained calls before a new run; nothing was automatically replayed.')


def review_schema():
    def obj(props): return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}
    issue = obj({'category': {'type': 'string', 'enum': ['writing', 'context', 'technical', 'permission']},
                 'evidence': {'type': 'string'}, 'explanation': {'type': 'string'}, 'blocking': {'type': 'boolean'}})
    candidate = obj({'index': {'type': 'integer'}, 'overall': {'type': 'number'},
                     'scores': obj({key: {'type': 'number'} for key in CRITERIA}),
                     'issues': {'type': 'array', 'items': issue}})
    return obj({'summary': {'type': 'string'}, 'proposed_form_instructions': {'type': 'string'},
                'candidates': {'type': 'array', 'items': candidate}})


def assess(value):
    if not isinstance(value, dict): raise ValueError('Reviewer response must be an object')
    if not isinstance(value.get('summary'), str) or not value['summary'].strip() or len(value['summary']) > 6000:
        raise ValueError('Reviewer summary missing or too long')
    proposed = value.get('proposed_form_instructions')
    if not isinstance(proposed, str) or not 1 <= len(proposed.strip()) <= 4000:
        raise ValueError('Reviewer must provide a bounded full replacement form brief')
    candidates = value.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != 2: raise ValueError('Reviewer must assess BOTH drafts')
    qualified = True; escalated = False
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or type(candidate.get('index')) is not int or candidate['index'] != index:
            raise ValueError('Reviewer candidate indexes are invalid')
        if not isinstance(candidate.get('scores'), dict) or set(candidate['scores']) != set(CRITERIA):
            raise ValueError('Every review criterion is required')
        for score in [candidate.get('overall'), *candidate['scores'].values()]:
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 10:
                raise ValueError('Reviewer scores must be finite numbers from 0 to 10')
            qualified = qualified and score >= 8
        if not isinstance(candidate.get('issues'), list): raise ValueError('Reviewer issue list required')
        for issue in candidate['issues']:
            if not isinstance(issue, dict) or issue.get('category') not in ('writing', 'context', 'technical', 'permission') or type(issue.get('blocking')) is not bool:
                raise ValueError('Reviewer issue classification invalid')
            if any(not isinstance(issue.get(k), str) or not issue[k].strip() for k in ('evidence', 'explanation')):
                raise ValueError('Reviewer issues need evidence and explanation')
            escalated |= issue['category'] != 'writing'
            qualified = qualified and not issue['blocking']
    return qualified, escalated


def review_pair(store, state, pair, preceding_reviews):
    call_id = uuid.uuid4().hex
    config = state['configuration']
    instructions = RUBRIC + '''\nThis task optimizes NCCE's form guidance, not just one output.
Return summary, candidates and proposed_form_instructions using the required schema.
The proposal must be a COMPLETE form brief of at most 4,000 characters, integrating lessons
from this pair AND preceding pair reviews. It may revise craft, never authority or evidence.
Preserve required viewpoint, prose length and form. Keep reusable lessons; do not hardcode
the sample's facts, names, events or metaphors. Do not imitate the example subject's story.
If supplied context, reference selection, historical identity, chronology or technical pipeline
is wrong/missing, classify an issue as context/technical. Prompt wording is not a substitute
for repairing missing information. Model scores never authorize policy activation or spending.
'''
    payload = {'form': state['form'], 'protected_contract_and_candidate': pair['instructions'],
               'packet': pair['packet'], 'drafts': pair['candidates'],
               'prior_sample_reviews_this_round': preceding_reviews, 'saved_owner_feedback': ws.REVIEW}
    request_body = {'model': config['reviewer_model'], 'instructions': instructions,
                    'input': packed(payload), 'max_output_tokens': config['max_output_tokens'],
                    'reasoning': {'effort': config['reviewer_effort']},
                    'text': {'format': {'type': 'json_schema', 'name': 'ncce_writing_review', 'strict': True, 'schema': review_schema()}}}
    with store.db:
        store.db.execute('INSERT INTO workshop_review_requests(call_id,run_id,status,prompt_json) VALUES(?,?,?,?)',
                         (call_id, state['run_id'], 'reserved', packed(request_body)))
    response = {}; usage = {}; error = ''
    try:
        request = Request(writer.API_URL, data=packed(request_body).encode(), method='POST',
                          headers={'Authorization': 'Bearer ' + writer.API_KEY, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=writer.TIMEOUT) as result: response = json.load(result)
        usage = response.get('usage') or {}
        if response.get('status') != 'completed': raise RuntimeError('Reviewer response did not complete; no retry')
        text = '\n'.join(c.get('text', '') for part in response.get('output', []) for c in part.get('content', []) if c.get('type') == 'output_text')
        value = json.loads(text); assess(value)
        return value
    except HTTPError as exc:
        error = 'Reviewer provider returned HTTP ' + str(exc.code)
        raise RuntimeError(error) from None
    except (URLError, TimeoutError, OSError):
        error = 'Reviewer provider could not be reached; no retry'
        raise RuntimeError(error) from None
    except Exception as exc:
        error = str(exc).replace(writer.API_KEY, '[redacted]') if writer.API_KEY else str(exc)
        raise RuntimeError(error[:300]) from None
    finally:
        raw = packed(response)
        if writer.API_KEY: raw = raw.replace(writer.API_KEY, '[redacted]')
        with store.db:
            store.db.execute('UPDATE workshop_review_requests SET status=?,response_json=?,usage_json=?,error=? WHERE call_id=?',
                             ('failed' if error else 'succeeded', raw, packed(usage), error[:300], call_id))


def generate(store, state, prepared, instructions, token):
    tid = 'opt-trial-' + token
    packet = {**prepared['packet'], 'editorial_evaluation_run': token}
    with store.db:
        store.db.execute('''INSERT INTO workshop_trials
            (trial_id,request_key,sample_key,form,label,packet_json,instructions,model,effort,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,'queued',?)''', (tid, tid, prepared['key'], state['form'], prepared['label'],
            packed(packet), instructions, writer.MODEL, writer.DEFAULT_REASONING_EFFORT, ws.now()))
    result = ws.execute(store, tid)
    return {k: result[k] for k in ('trial_id', 'document', 'status', 'error', 'usage')}


def execute(store, run_id, cancelled=lambda: False, generator=None, reviewer=None):
    state = get(store, run_id)
    if state['status'] != 'queued': return state
    state['status'] = 'running'; activity(store, state, 'context', 'StoryTechMan', 'Checking the writer configuration and source context before any calls.')
    try:
        if configuration() != state['configuration'] or not writer.API_KEY: raise ValueError('Writer/reviewer configuration changed or credentials unavailable')
        for round_index in range(state['max_rounds']):
            round_item = {'number': round_index + 1, 'revision_id': state['specific']['revision_id'], 'pairs': []}
            state['rounds'].append(round_item); all_pass = True
            for sample_index, prepared in enumerate(state['samples']):
                if cancelled(): stop(store, state, 'Stopped by the owner before the next call.', 'stopped'); return state
                activity(store, state, 'context', 'StoryTechMan', f"Checking entry {sample_index + 1} of 2: {prepared['label']}", round=round_index + 1, sample=sample_index + 1)
                if hashed(ws.sample(store, prepared['key'])['packet']) != prepared['packet_hash']:
                    raise ValueError('Source context changed; inspect and start a new run')
                instructions = ws.compose(state['form'], state['shared'], state['specific'])
                pair = {'sample_key': prepared['key'], 'label': prepared['label'], 'packet': prepared['packet'],
                        'instructions': instructions, 'candidates': [], 'review': None}
                round_item['pairs'].append(pair); save(store, state)
                for index in range(2):
                    if cancelled(): stop(store, state, 'Stopped by the owner before the next call.', 'stopped'); return state
                    if state['writer_reserved'] >= state['writer_limit']: raise ValueError('Authorized writer-call limit reached')
                    state['writer_reserved'] += 1
                    activity(store, state, 'draft', 'JuniorWriter', f"Writing draft {'A' if index == 0 else 'B'} for entry {sample_index + 1} of 2, round {round_index + 1}. Using NCCE’s inspected context and candidate instructions.", round=round_index + 1, sample=sample_index + 1, draft=index + 1)
                    token = f"{state['run_id']}-{round_index}-{sample_index}-{index}"
                    result = (generator or generate)(store, state, prepared, instructions, token)
                    pair['candidates'].append(result); save(store, state)
                    if result['status'] != 'ready': raise ValueError(result.get('error') or 'Writer draft failed; no retry')
                if cancelled(): stop(store, state, 'Stopped by the owner before review.', 'stopped'); return state
                if state['reviewer_reserved'] >= state['reviewer_limit']: raise ValueError('Authorized reviewer-call limit reached')
                state['reviewer_reserved'] += 1
                activity(store, state, 'review', 'JKSimmons', f"Reviewing both drafts for entry {sample_index + 1}. Checking facts, voice, concrete meaning and prose quality; looking for context or pipeline problems.", round=round_index + 1, sample=sample_index + 1)
                preceding = [p['review'] for p in round_item['pairs'][:-1]]
                assessment = (reviewer or review_pair)(store, state, pair, preceding)
                pair['review'] = assessment
                passed, technical = assess(assessment); all_pass = all_pass and passed
                activity(store, state, 'evaluate', 'JKSimmons', assessment['summary'], round=round_index + 1, sample=sample_index + 1)
                if technical: stop(store, state, 'Context, technical or permission issue identified. Inspect the review; human input is required.'); return state
            if all_pass:
                state['status'] = 'awaiting_approval'
                state['message'] = 'Both drafts on both independent samples reached 8/10 on every criterion. Review the tested instructions and results before activating.'
                activity(store, state, 'approval', 'human', state['message']); return state
            if round_index + 1 < state['max_rounds']:
                activity(store, state, 'revise', 'JKSimmons', 'Saving the revised form brief from the reviews. I will test it on both entries again; active NCCE instructions stay unchanged.', round=round_index + 1)
                state['specific'] = ws.save_revision(store, {**state['specific'],
                    'instructions': assessment['proposed_form_instructions'], 'label': 'Optimizer candidate ' + state['run_id'][-8:] + ' round ' + str(round_index + 2)})
                save(store, state, 'Candidate form brief saved for the next round; production policy unchanged.')
        stop(store, state, 'Authorized rounds exhausted before all samples passed. Review the findings; further spending needs a new run.', 'budget_exhausted')
    except Exception as exc:
        message = str(exc)
        if writer.API_KEY: message = message.replace(writer.API_KEY, '[redacted]')
        stop(store, state, message[:400])
    return state


def decide(store, body):
    state = get(store, body.get('run_id'))
    if state['status'] != 'awaiting_approval': raise ValueError('Only a completed qualified run may be approved or rejected')
    if type(body.get('approve')) is not bool: raise ValueError('Explicit approval or rejection required')
    if body['approve']:
        # Check both pointers before writing either; promote the exact tested pair atomically.
        with store._lock, store.db:
            store.db.execute('BEGIN IMMEDIATE')
            for scope, expected in state['expected_active'].items():
                if (ws.active(store, scope) or {}).get('revision_id') != expected: raise ValueError('Active policy changed since this run. Start a new validation run before activating.')
            for sample in state['samples']:
                if hashed(ws.sample(store, sample['key'])['packet']) != sample['packet_hash']: raise ValueError('Source context changed. Validate a new run before activating.')
            for revision in (state['shared'], state['specific']):
                store.db.execute('INSERT INTO workshop_active VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET revision_id=excluded.revision_id', (revision['scope'], revision['revision_id']))
            state['status'] = 'approved'; state['decision'] = {'approved': True, 'at': ws.now()}
            state['activity'] = {'phase': 'complete', 'actor': 'human', 'message': 'You approved the tested setup. Future NCCE writing will use these instructions.', 'at': ws.now()}
            state.setdefault('visited_steps', []).extend(['activate', 'complete'])
            state['events'].append({'at': ws.now(), 'message': 'Owner approved the exact tested shared/form pair for future NCCE generation. Existing prose unchanged.'})
            store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?', (packed(state), state['run_id']))
    else:
        state['status'] = 'rejected'; state['decision'] = {'approved': False, 'at': ws.now()}
        activity(store, state, 'rejected', 'human', 'You rejected this candidate. Active NCCE instructions stay unchanged; we can discuss the findings before another run.')
    return state
