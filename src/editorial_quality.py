"""Owner standards and prospective reviewer calibration. No provider calls.

Owner verdicts are append-only evidence, not model-generated labels. Fresh
judgements count only against reviews sealed before the owner voted.
"""
import hashlib
import json
from pathlib import Path
import writer_workshop as ws
import codex_review_queue as cq

PATH = Path(__file__).resolve().parents[1] / 'data/editorial/owner-contract.json'
CHECKS = ('subject', 'clarity', 'register', 'closing')


def digest(value):
    return hashlib.sha256(cq.packed(value).encode()).hexdigest()


def contract():
    return json.loads(PATH.read_text(encoding='utf-8'))


def fingerprint():
    # A new reviewer thread or a changed rubric invalidates prior calibration.
    from writer_quality import RUBRIC
    return digest({'contract': contract(), 'thread': cq.thread_id(), 'rubric': RUBRIC,
                   'protocol': 'prospective-owner-agreement-v1'})


def records(store):
    return [json.loads(r[0]) for r in store.db.execute(
        "SELECT value FROM system_state WHERE key LIKE 'editorial-verdict:%' ORDER BY key")]


def calibration(store, form):
    current = fingerprint()
    evidence = [v for v in records(store) if v['form'] == form and v['fingerprint'] == current]
    evidence.sort(key=lambda v: v['at'])
    # A false acceptance of a strong rejection revokes trust immediately. Only
    # fresh evidence after the failure can restore it; old wins cannot hide it.
    last_failure = max((i for i, v in enumerate(evidence) if v['critical_miss']), default=-1)
    window = evidence[last_failure + 1:][-10:]
    agreements = sum(v['agrees'] for v in window)
    negative = any(v['preference'] == 'neither' for v in window)
    ready = len(window) >= 3 and negative and agreements / len(window) >= .8
    return {'form': form, 'fingerprint': current, 'calibrated': ready,
            'fresh_pairs': len(window), 'agreements': agreements,
            'has_rejection_check': negative, 'critical_misses': sum(v['critical_miss'] for v in evidence),
            'message': 'Reviewer agreement gate passed for this category.' if ready else
            'Reviewer scores are advisory. Need at least 3 fresh owner-labelled pairs, 80% preference agreement, a correctly rejected neither pair, and no unresolved false acceptance of a strong rejection.'}


def require_calibrated(store, form):
    if not calibration(store, form)['calibrated']:
        raise ValueError('Reviewer is not calibrated for this category. Scores cannot qualify or activate a study. Record blind owner verdicts first.')


def home(store, form):
    ws.scope_name(form)
    data = contract()
    return {'contract': data, 'calibration': calibration(store, form),
            'suggested_instructions': seed_brief(form),
            'scope_note': 'Historical examples teach standards; they never count as fresh calibration evidence. Calibration is category-specific and is revoked by a strong-rejection false acceptance.'}


def seed_brief(form):
    anchors = '\nTone anchors only; never copy these phrases or import their subject facts: ' + '; '.join(
        '“'+r['excerpt']+'” ('+r['source']+', p. '+str(r['printed_page'])+'): '+r['lesson'] for r in contract().get('style_references',[]))
    if form == 'territory_origin':
        return '''BASELINE TERRITORY ORIGIN. Write 70–100 words of body prose about the supplied territory itself. Preserve its actual primary function, physical setting and faction. For a Palanite precinct, centre Helmawr's enforcers, their authority and what happens at their precinct; do not substitute a civilian trade or public stairway story. For a mine, retain extraction; for a shrine, retain worship.
Use direct, concrete English with a rough industrial register. Make one clear, worthwhile idea land on the first read. Compatible local invention is allowed, but do not make a disposable named stranger the main attraction. Personal details must serve the requested subject. Do not invent campaign events, benefits, ownership or authoritative lore. Separate verified context from inference. A creative focus is optional inspiration and must never displace the territory's identity.
Return the required structured fields: heading, subject, body_heading, body, closing_label, closing and signoff. These are presentation fields, not a demand for seven pieces of prose. The closing and closing_label may be empty strings. Include a closing only if it adds a clearly connected, useful observation. Do not force an Administratum flourish, legal caveat, grand implication, joke or extra causal mechanism. A bureaucratic wrapper does not require fancy language. Preserve the protected source hierarchy and all factual limits.''' + anchors
    return ws.defaults(form)['instructions'] + '\nUse direct concrete language. Keep the requested subject and event central. Meaning must be clear on the first read; complexity is not a quality bonus. Incidental people must support the subject. Optional closing remarks may be empty; never force an administrative flourish. Preserve the required viewpoint, source hierarchy and factual limits.' + anchors


def record_verdict(store, body):
    from workshop_optimizer import get
    run = get(store, body.get('run_id'))
    if run.get('workflow_version', 1) < 3 or run['status'] in ('queued', 'running'):
        raise ValueError('Blind verdicts require a paused controlled comparison')
    round_number, pair_index = body.get('round'), body.get('pair')
    if type(round_number) is not int or type(pair_index) is not int:
        raise ValueError('Choose a comparison pair')
    round_ = next((r for r in run['rounds'] if r['number'] == round_number), None)
    if not round_ or not 0 <= pair_index < len(round_['pairs']):
        raise ValueError('Comparison pair not found')
    pair = round_['pairs'][pair_index]
    review = pair.get('review')
    if not review or not pair.get('review_sealed_at'):
        raise ValueError('Independent review must finish before owner judgement')
    preference = body.get('preference')
    acceptable = body.get('acceptable')
    if preference not in ('A', 'B', 'tie', 'neither') or not isinstance(acceptable, list) or len(acceptable) != 2 or any(type(v) is not bool for v in acceptable):
        raise ValueError('Choose a preference and whether each draft is acceptable')
    if (preference == 'neither' and any(acceptable)) or (preference in ('A', 'B') and not acceptable[0 if preference == 'A' else 1]) or (preference == 'tie' and not all(acceptable)):
        raise ValueError('Preference and acceptance choices conflict')
    note = body.get('note', '')
    if not isinstance(note, str) or len(note) > 4000:
        raise ValueError('Keep the owner note within 4,000 characters')
    key = 'editorial-verdict:' + digest([run['run_id'], round_number, pair_index])
    choice = {'preference': preference, 'acceptable': acceptable, 'note': note}
    existing = store.get_state(key)
    if existing:
        saved = json.loads(existing)
        if any(saved[k] != v for k, v in choice.items()):
            raise ValueError('This blind verdict is sealed. It cannot be rewritten after the reveal.')
        return saved
    from workshop_experiments import validate_review
    validate_review(review)
    predicted = [c['acceptable'] for c in review['candidates']]
    value = {**choice, 'run_id': run['run_id'], 'round': round_number, 'pair': pair_index,
             'form': run['form'], 'fingerprint': run['quality_fingerprint'],
             'at': ws.now(), 'review_sealed_at': pair['review_sealed_at'],
             'review_hash': digest(review), 'reviewer_preference': review['preference'],
             'agrees': review['preference'] == preference,
             'critical_miss': preference == 'neither' and any(predicted),
             'candidate_index': pair['candidate_index']}
    with store._lock, store.db:
        # Duplicate source entries, even in another study, cannot manufacture
        # independent calibration evidence.
        source = digest([run['form'], pair['packet_hash'], run['quality_fingerprint']])
        if store.get_state('editorial-source:' + source):
            value['duplicate_source'] = True
            value['fingerprint'] = 'duplicate-source-not-calibration'
        store.db.execute('INSERT INTO system_state VALUES(?,?)', (key, cq.packed(value)))
        store.db.execute('INSERT OR IGNORE INTO system_state VALUES(?,?)', ('editorial-source:' + source, key))
    return value


def verdict_for(store, run_id, round_number, pair_index):
    key = 'editorial-verdict:' + digest([run_id, round_number, pair_index])
    value = store.get_state(key)
    return json.loads(value) if value else None


def training_feedback(store, form):
    """Previously sealed owner corrections; current hidden labels do not exist yet."""
    result = []
    for v in sorted(records(store), key=lambda v:v['at'], reverse=True):
        if v['form'] != form:
            continue
        row = store.db.execute('SELECT state_json FROM workshop_optimization_runs WHERE run_id=?', (v['run_id'],)).fetchone()
        if not row:
            continue
        run = json.loads(row[0])
        round_ = next((r for r in run['rounds'] if r['number'] == v['round']), None)
        if not round_ or v['pair'] >= len(round_['pairs']):
            continue
        pair = round_['pairs'][v['pair']]
        result.append({'entry': pair['label'], 'owner_preference': v['preference'],
                       'owner_acceptable': v['acceptable'], 'owner_note': v['note'],
                       'previous_reviewer_preference': v['reviewer_preference'],
                       'drafts': [c.get('document',{}) for c in pair['candidates']]})
        if len(result) == 6:
            break
    return result
