"""Controlled current-vs-candidate studies; isolated from production writing."""
import secrets
import editorial_quality as quality
import writer_workshop as ws


def schema():
    import workshop_optimizer as opt
    result = opt.review_schema()
    props = result['properties']
    props['preference'] = {'type': 'string', 'enum': ['A', 'B', 'tie', 'neither'],
        'description':'Relative ranking, independent of publication acceptance. A/B may be preferred even when both drafts are unacceptable; tie may also mean both fail.'}
    props['experiment'] = {'type': 'object', 'properties': {
        key: {'type': 'string'} for key in ('changed', 'addresses', 'observed_effect', 'regressions')},
        'required': ['changed', 'addresses', 'observed_effect', 'regressions'], 'additionalProperties': False}
    candidate = props['candidates']['items']
    candidate['properties']['acceptable'] = {'type': 'boolean', 'description':'Publication judgement for this draft, independent of relative preference.'}
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
    quality.validate_verdict(value['preference'],accept)


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


def resume_saved_round(store, body):
    """Owner action resumes only untouched work inside the existing allowance."""
    import workshop_optimizer as opt
    state=opt.get(store,body.get('run_id'))
    if state['status']!='awaiting_resume' or not state.get('review_recovery') or body.get('allow_remaining') is not True:
        raise ValueError('Explicit resume of a recovered saved round is required')
    ensure_current(store,state)
    state['resume_round']=True;state['status']='queued'
    opt.activity(store,state,'queued','human','Resuming the saved round. Completed drafts and reviews will be reused; the authorized allowance is unchanged.')
    return state,True


def restore_saved_review(store, job_id, review, expected_turn_id):
    """Operator-only repair, deliberately NOT exposed on the bridge or web API.

    Restore an existing native verdict after the submission-validator repair.
    No lease is reissued, no review regenerated and no writing starts here.
    """
    import json
    import workshop_optimizer as opt
    import codex_review_queue as cq
    validate_review(review)
    if '_codex' in review:
        raise ValueError('Supply the original review, not an identity override')
    with store._lock,store.db:
        store.db.execute('BEGIN IMMEDIATE')
        job=cq.get(store,job_id);payload=json.loads(job['payload_json'])
        identity=json.loads(job['result_json']).get('_codex',{})
        if identity!={'thread_id':cq.thread_id(),'turn_id':expected_turn_id} or payload.get('workflow_version')!=3 or payload.get('kind','review')!='review':
            raise ValueError('Saved verdict must match the original native reviewer turn and job')
        state=opt.get(store,job['run_id'])
        previous=state.get('review_recovery',{})
        if previous.get('job_id')==job_id:
            if previous.get('review_hash')!=quality.digest(review):raise ValueError('Recovered review is immutable')
            return state
        recoverable=(job['status']=='cancelled' and job['error']=='Server restarted; uncertain reviews are not replayed') or (job['status']=='failed' and job['error'].startswith('Reviewer submission rejected:'))
        if not recoverable or state['status']!='escalated':
            raise ValueError('Only a restart-interrupted native review may be recovered by this repair')
        if store.db.execute("SELECT 1 FROM workshop_optimization_runs WHERE run_id!=? AND json_extract(state_json,'$.status') IN ('queued','running')",(state['run_id'],)).fetchone():
            raise ValueError('Wait for other active writing before repairing a saved study')
        if any(v.get('run_id')==state['run_id'] for v in quality.records(store)):
            raise ValueError('Do not rebind a study with sealed owner verdicts')
        round_=state['rounds'][-1]
        pair=next((p for p in round_['pairs'] if p.get('codex_job_id')==job_id),None)
        if not pair or pair.get('review') or payload['candidates']!=pair['candidates'] or len(pair['candidates'])!=2 or any(c['status']!='ready' for c in pair['candidates']):
            raise ValueError('Both original ready drafts and the pending pair must be intact')
        samples=round_.get('prepared_samples') or (state['samples'] if round_['number']==1 else [])
        if len(samples)!=2:raise ValueError('Both frozen source plans are required for recovery')
        for sample in samples:
            if opt.hashed(ws.sample(store,sample['key'])['packet'])!=sample['packet_hash']:
                raise ValueError('A frozen source changed; no recovery or new calls performed')
        for scope,expected in state['expected_active'].items():
            if (ws.active(store,scope) or {}).get('revision_id')!=expected:
                raise ValueError('Active writing instructions changed; do not resume')
        if opt.configuration()!=state['configuration'] or state['editorial_contract']!=quality.contract():
            raise ValueError('Writer configuration or owner standards changed; do not resume')
        candidate=ws.compose(state['form'],state['shared'],state['specific'])
        baseline=ws.compose(state['form'],state['baseline']['shared'],state['baseline'][state['form']])
        if pair['instructions']!=candidate or pair['comparison_instructions'][pair['candidate_index']]!=candidate or pair['comparison_instructions'][1-pair['candidate_index']]!=baseline:
            raise ValueError('Exact frozen instructions changed; do not resume')
        state['review_recovery']={'job_id':job_id,'turn_id':expected_turn_id,'review_hash':quality.digest(review),
            'at':ws.now(),'old_quality_fingerprint':state['quality_fingerprint'],
            'old_environment_hash':state['environment_hash'],
            'reason':'Owner-requested repair of ranking/acceptance validation; original review and ready drafts retained. No replay or increased allowance.'}
        pair['review']={**review,'_codex':identity};pair['review_sealed_at']=ws.now()
        round_['prepared_samples']=samples
        state['quality_fingerprint']=quality.fingerprint();state['environment_hash']=opt.environment_fingerprint()
        state['status']='awaiting_resume'
        state['message']='The saved JKSimmons review has been recovered. Existing drafts and verdict are retained. Resume only the unfinished portion of this authorized round, or finish with the saved findings.'
        state['activity']={'phase':'decision','actor':'human','message':state['message'],'at':ws.now()}
        state['events'].append({'at':ws.now(),'message':state['review_recovery']['reason']})
        store.db.execute("UPDATE codex_review_jobs SET status='completed',result_json=?,error='',finished_at=? WHERE job_id=?",(cq.packed(pair['review']),ws.now(),job_id))
        store.db.execute('UPDATE workshop_optimization_runs SET state_json=? WHERE run_id=?',(opt.packed(state),state['run_id']))
    return state


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
        start=len(state['rounds'])-1 if state.get('resume_round') else len(state['rounds'])
        for round_index in range(start, state['max_rounds']):
            ensure_current(store, state)
            resuming=bool(state.get('resume_round') and round_index==start)
            if resuming:
                round_=state['rounds'][round_index]
                validation=round_['kind']=='validation'
                samples=round_.get('prepared_samples') or (state['samples'] if round_index==0 else [])
                if round_['revision_id']!=state['specific']['revision_id']:
                    raise ValueError('Saved candidate changed; the interrupted round cannot resume')
            else:
                validation = state.get('validation_pending', False)
                samples = opt.round_samples(store, state)
            if len(samples) < 2:
                opt.pause(store, state, 'awaiting_samples', 'Two unused source entries are needed. No calls were made for this round; ask StoryTechMan to inspect source coverage.')
                return state
            if not resuming:
                round_ = {'number': round_index + 1, 'kind': 'validation' if validation else 'learning',
                          'revision_id': state['specific']['revision_id'], 'hypothesis': state['hypothesis'], 'pairs': [], 'prepared_samples':samples}
                state['rounds'].append(round_)
            for si, prepared in enumerate(samples):
                if cancelled():
                    opt.stop(store, state, 'Stopped by the owner before the next request.', 'stopped'); return state
                if opt.hashed(ws.sample(store, prepared['key'])['packet']) != prepared['packet_hash']:
                    raise ValueError('Source context changed. Start a fresh comparison.')
                if si<len(round_['pairs']):
                    retained=round_['pairs'][si]
                    if not resuming or retained['sample_key']!=prepared['key'] or len(retained['candidates'])!=2 or any(c['status']!='ready' for c in retained['candidates']) or not retained.get('review'):
                        raise ValueError('Interrupted request outcome is uncertain. No automatic retry is allowed.')
                    validate_review(retained['review'])
                    if opt.assess(retained['review'])[1]:
                        raise ValueError('The retained review requires technical investigation before more writing')
                    continue
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
            state.pop('resume_round',None)
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
