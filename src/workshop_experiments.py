"""Controlled current-vs-candidate studies; isolated from production writing."""
import secrets
import editorial_quality as quality
import writer_workshop as ws


def schema():
    import workshop_optimizer as opt
    result = opt.review_schema()
    props = result['properties']
    props['preference'] = {'type': 'string', 'enum': ['A', 'B', 'tie', 'neither']}
    props['experiment'] = {'type': 'object', 'properties': {
        key: {'type': 'string'} for key in ('changed', 'addresses', 'observed_effect', 'regressions')},
        'required': ['changed', 'addresses', 'observed_effect', 'regressions'], 'additionalProperties': False}
    candidate = props['candidates']['items']
    candidate['properties']['acceptable'] = {'type': 'boolean'}
    candidate['properties']['owner_checks'] = {'type': 'object', 'properties': {
        key: {'type': 'boolean'} for key in quality.CHECKS}, 'required': list(quality.CHECKS), 'additionalProperties': False}
    candidate['required'] += ['acceptable', 'owner_checks']
    result['required'] += ['preference', 'experiment']
    return result


def validate_review(value):
    import workshop_optimizer as opt
    opt.assess(value)  # Retain factual/issue validation; scores are advisory.
    if value.get('preference') not in ('A', 'B', 'tie', 'neither'):
        raise ValueError('Controlled comparison needs an A/B/tie/neither preference')
    experiment = value.get('experiment')
    if not isinstance(experiment, dict) or set(experiment) != {'changed', 'addresses', 'observed_effect', 'regressions'} or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 2000 for v in experiment.values()):
        raise ValueError('Explain the tested change, target problem, observed effect and regressions')
    for c in value['candidates']:
        checks = c.get('owner_checks')
        if type(c.get('acceptable')) is not bool or not isinstance(checks, dict) or set(checks) != set(quality.CHECKS) or any(type(v) is not bool for v in checks.values()):
            raise ValueError('Reviewer must explicitly check subject, clarity, register and closing')
        if c['acceptable'] and (not all(checks.values()) or any(i['blocking'] for i in c['issues'])):
            raise ValueError('A failed owner check or blocking issue cannot be accepted')
    accept = [c['acceptable'] for c in value['candidates']]
    if value['preference'] == 'neither' and any(accept) or value['preference'] == 'tie' and not all(accept) or value['preference'] in ('A', 'B') and not accept[0 if value['preference'] == 'A' else 1]:
        raise ValueError('Reviewer preference conflicts with acceptance decisions')


def candidate_passes(pair):
    review = pair['review']
    index = pair['candidate_index']
    # Improvement or non-regression is necessary, not a higher self-score.
    return review['candidates'][index]['acceptable'] and review['preference'] in ('tie', 'AB'[index])


def start_fields(store, state, body):
    hypothesis = body.get('hypothesis')
    if not isinstance(hypothesis, str) or not 10 <= len(hypothesis.strip()) <= 1000:
        raise ValueError('Describe the specific category improvement this experiment will test (10–1,000 characters)')
    baseline = {scope: ws.active(store, scope) or ws.defaults(scope) for scope in ('shared', state['form'])}
    baseline = {scope: r if r.get('revision_id') else ws.save_revision(store, r) for scope, r in baseline.items()}
    if ws.compose(state['form'], baseline['shared'], baseline[state['form']]) == ws.compose(state['form'], state['shared'], state['specific']):
        raise ValueError('Current and candidate instructions are identical. Choose a concrete candidate change before spending calls.')
    state.update(workflow_version=3, baseline=baseline, hypothesis=hypothesis.strip(),
                 quality_fingerprint=quality.fingerprint(), editorial_contract=quality.contract(),
                 reviewer_calibration=quality.calibration(store, state['form']))


def ensure_current(store, state):
    if state.get('quality_fingerprint') != quality.fingerprint():
        raise ValueError('Owner contract or reviewer changed. Start a fresh comparison; previous qualification is stale.')
    import workshop_optimizer as opt
    if state.get('environment_hash') != opt.environment_fingerprint():
        raise ValueError('Generation environment changed. Start a fresh comparison.')
    for scope, expected in state['expected_active'].items():
        if (ws.active(store, scope) or {}).get('revision_id') != expected:
            raise ValueError('Current production instructions changed. Start a fresh comparison.')


def checkpoint(store, body):
    import workshop_optimizer as opt
    state = opt.get(store, body.get('run_id'))
    if state.get('workflow_version', 1) < 3 or state['status'] != 'awaiting_owner':
        raise ValueError('No controlled comparison is waiting for your verdicts')
    ensure_current(store, state)
    round_ = state['rounds'][-1]
    votes = [quality.verdict_for(store, state['run_id'], round_['number'], i) for i in range(len(round_['pairs']))]
    if not votes or not all(votes):
        raise ValueError('Record your blind verdict on each entry before continuing')
    state['reviewer_calibration'] = quality.calibration(store, state['form'])
    candidate_accepted = all(v['acceptable'][p['candidate_index']] and v['preference'] in ('tie','AB'[p['candidate_index']]) for p,v in zip(round_['pairs'],votes))
    if not candidate_accepted:
        state['validation_pending'] = False
    elif round_.get('candidate_non_regression') and state['reviewer_calibration']['calibrated']:
        state['validation_pending'] = True
    if len(state['rounds']) >= state['max_rounds']:
        opt.pause(store, state, 'awaiting_next_round', 'Your verdicts are saved. This authorized batch is complete. Continue with a new bounded round, inspect findings, or finish.')
    else:
        state['status'] = 'queued'
        opt.activity(store, state, 'queued', 'human', 'Blind verdicts saved. Resuming only the rounds already authorized; no spending limit increased.')
    return state, state['status'] == 'queued'


def execute(store, state, cancelled, generator, reviewer):
    import workshop_optimizer as opt
    from workshop_guidelines import changes, announcement
    import llm_writer as writer
    state['status'] = 'running'
    opt.activity(store, state, 'context', 'StoryTechMan', 'Checking the frozen baseline, candidate and owner standards.')
    try:
        ensure_current(store, state)
        if opt.configuration() != state['configuration'] or not writer.API_KEY:
            raise ValueError('Writer/reviewer configuration changed or credentials unavailable')
        for round_index in range(len(state['rounds']), state['max_rounds']):
            ensure_current(store, state)
            validation = state.get('validation_pending', False)
            samples = opt.round_samples(store, state)
            if len(samples) < 2:
                opt.pause(store, state, 'awaiting_samples', 'Two unused source entries are needed. No calls were made for this round; ask StoryTechMan to inspect source coverage.')
                return state
            round_ = {'number': round_index + 1, 'kind': 'validation' if validation else 'learning',
                      'revision_id': state['specific']['revision_id'], 'hypothesis': state['hypothesis'], 'pairs': []}
            state['rounds'].append(round_)
            for si, prepared in enumerate(samples):
                if cancelled():
                    opt.stop(store, state, 'Stopped by the owner before the next request.', 'stopped'); return state
                if opt.hashed(ws.sample(store, prepared['key'])['packet']) != prepared['packet_hash']:
                    raise ValueError('Source context changed. Start a fresh comparison.')
                baseline = ws.compose(state['form'], state['baseline']['shared'], state['baseline'][state['form']])
                candidate = ws.compose(state['form'], state['shared'], state['specific'])
                ci = secrets.randbelow(2)
                instructions = [baseline, baseline]; instructions[ci] = candidate
                pair = {'sample_key': prepared['key'], 'label': prepared['label'], 'packet': prepared['packet'],
                        'packet_hash': prepared['packet_hash'], 'instructions': candidate, 'comparison_instructions': instructions,
                        'candidate_index': ci, 'candidates': [], 'review': None, 'experiment': True}
                round_['pairs'].append(pair); opt.save(store, state)
                for di in range(2):
                    if cancelled():
                        opt.stop(store, state, 'Stopped before the next draft.', 'stopped'); return state
                    if state['writer_reserved'] >= state['writer_limit']:
                        raise ValueError('Authorized writer-call limit reached')
                    state['writer_reserved'] += 1
                    opt.activity(store, state, 'draft', 'JuniorWriter', f'Writing blind draft {"AB"[di]}, entry {si+1} of 2. One uses current instructions; one tests the candidate.', round=round_index+1, sample=si+1, draft=di+1)
                    result = (generator or opt.generate)(store, state, prepared, instructions[di], f'{state["run_id"]}-{round_index}-{si}-{di}')
                    pair['candidates'].append(result); opt.save(store, state)
                    if result['status'] != 'ready':
                        raise ValueError(result.get('error') or 'Draft failed. No retry.')
                if cancelled():
                    opt.stop(store, state, 'Stopped before review.', 'stopped'); return state
                if state['reviewer_reserved'] >= state['reviewer_limit']:
                    raise ValueError('Authorized reviewer-call limit reached')
                state['reviewer_reserved'] += 1
                opt.activity(store, state, 'awaiting_reviewer', 'StoryTechMan', 'Requesting an independent blind current-versus-candidate review.', round=round_index+1, sample=si+1)
                preceding = [p['review'] for r in state['rounds'] for p in r['pairs'] if p.get('review')]
                result = reviewer(store, state, pair, preceding) if reviewer else opt.review_pair(store, state, pair, preceding, cancelled)
                validate_review(result)
                pair['review'] = result; pair['review_sealed_at'] = ws.now()
                opt.activity(store, state, 'evaluate', 'JKSimmons', 'Independent verdict sealed. Your blind judgement will be recorded before the assessment and setup identities are revealed.', round=round_index+1, sample=si+1)
                if opt.assess(result)[1]:
                    opt.stop(store, state, 'Context, technical or permission evidence needs investigation. StoryTechMan will return an actionable proposal; writing is paused.')
                    import workshop_interventions as interventions
                    interventions.investigate(store, {'run_id': state['run_id'], 'request_key': 'auto-tech-'+state['run_id'], 'note': result['summary']})
                    return opt.get(store, state['run_id'])
            qualified = all(candidate_passes(p) for p in round_['pairs'])
            state['reviewer_calibration'] = quality.calibration(store, state['form'])
            calibrated = state['reviewer_calibration']['calibrated']
            round_['candidate_non_regression'] = qualified
            round_['calibrated_at_review'] = calibrated
            if qualified and validation and calibrated:
                state['validated'] = {'round': round_index+1, 'entries': [p['sample_key'] for p in round_['pairs']],
                                      'quality_fingerprint': state['quality_fingerprint'], 'revision_id': state['specific']['revision_id']}
                state['status'] = 'awaiting_approval'
                opt.activity(store, state, 'approval', 'human', 'Candidate passed fresh comparisons under a calibrated reviewer. Record your blind verdicts, then approve or reject the exact tested setup.')
                return state
            if qualified and calibrated:
                state['validation_pending'] = True
                opt.save(store, state, 'Candidate met the owner checks without losing to current instructions. Freeze it for fresh validation.')
            else:
                state['validation_pending'] = False
                # Validation failures are diagnostic evidence. Consolidated guidance
                # comes from review two, which receives the first review as context.
                if not qualified:
                    previous = state['specific']['revision_id']
                    proposal = round_['pairs'][-1]['review']['proposed_form_instructions']
                    change = changes(state['specific']['instructions'], proposal)
                    state['specific'] = ws.save_revision(store, {**state['specific'], 'instructions': proposal,
                        'label': 'Experimental candidate '+state['run_id'][-8:]+' after round '+str(round_index+1)})
                    state['prompt_history'].append({'after_round': round_index+1, 'from_revision': previous,
                        'to_revision': state['specific']['revision_id'], 'instructions': proposal, 'change': change, 'at': ws.now()})
                    opt.activity(store, state, 'revise', 'JKSimmons', announcement(state['form'], change), round=round_index+1)
                if not calibrated:
                    opt.pause(store, state, 'awaiting_owner', 'Reviewer scores remain advisory. This comparison is saved; record your blind verdicts before more writing. No instructions have been activated.')
                    return state
        opt.pause(store, state, 'awaiting_next_round', 'This test batch is complete. Current-versus-candidate comparisons and findings are saved. Continue within a new bounded grant, investigate, or finish.')
    except opt.ReviewCancelled as exc:
        opt.stop(store, state, str(exc), 'stopped')
    except Exception as exc:
        message = str(exc).replace(writer.API_KEY, '[redacted]') if writer.API_KEY else str(exc)
        opt.stop(store, state, message[:400])
    return state


def public_run(store, state):
    """Do not reveal assessor verdicts or A/B identities before owner judgement."""
    import copy
    result = copy.deepcopy(state)
    if result.get('workflow_version', 1) < 3:
        return result
    result['reviewer_calibration'] = quality.calibration(store, result['form'])
    for r in result['rounds']:
        for i, pair in enumerate(r['pairs']):
            verdict = quality.verdict_for(store, result['run_id'], r['number'], i)
            pair['owner_verdict'] = verdict
            pair.pop('comparison_instructions', None)
            pair.pop('instructions', None)
            if not verdict:
                pair.pop('candidate_index', None)
                pair['review_pending_reveal'] = bool(pair.get('review'))
                pair['review'] = None
                # Trial IDs permit a full instruction lookup; the blind view has
                # the prose and state it needs, without a direct audit link.
                for candidate in pair['candidates']:
                    candidate.pop('trial_id', None)
    # Hypotheses/revision text and hashes are useful for audit but bias a blind
    # judgement. Keep them hidden until every completed pair has an owner vote.
    pending = any(p.get('review_pending_reveal') for r in result['rounds'] for p in r['pairs'])
    if pending:
        result['prompt_history'] = []
        result.pop('baseline', None)
        result['specific'] = {'instructions': 'Hidden until blind verdicts are sealed.'}
        result['shared'] = {'instructions': 'Hidden until blind verdicts are sealed.'}
        for r in result['rounds']:
            r.pop('candidate_non_regression', None)
        result['dialogue'] = [e for e in result.get('dialogue',[]) if e.get('phase') not in ('revise',)]
        result['events'] = []
    return result
