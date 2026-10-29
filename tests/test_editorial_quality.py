"""Prospective owner calibration and controlled comparisons. No paid calls."""
import copy
import hashlib
import os
import sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
import editorial_quality as q
import workshop_experiments as exp
import workshop_optimizer as opt
import writer_workshop as ws
import llm_writer as writer
import codex_review_queue as cq
from test_writer_pipeline import with_store
from test_writer_workshop import seed
from test_workshop_optimizer import ready_bridge, assessment, rejects
from test_workshop_optimizer import fake_call
from test_story_engine import mechanical_records


def request(store, rounds=3, key='controlled-study-00000001'):
    source = seed(store)
    candidate = ws.save_revision(store, {**ws.defaults(source['form']),
        'instructions': q.seed_brief(source['form']), 'examples': '', 'label': 'Controlled candidate'})
    return {'sample_key': source['key'], 'request_key': key, 'max_rounds': rounds,
            'allow_paid': True, 'form_revision_id': candidate['revision_id'],
            'hypothesis': 'Test clearer subject focus and direct language against current writing.'}


def review(pair, neither=False):
    r = assessment(9)
    r['preference'] = 'neither' if neither else 'AB'[pair['candidate_index']]
    r['experiment'] = {'changed': 'Direct subject guidance.', 'addresses': 'Subject drift.',
                       'observed_effect': 'Clearer subject.' if not neither else 'Neither works.', 'regressions': 'None observed.'}
    for c in r['candidates']:
        c['acceptable'] = not neither
        c['owner_checks'] = {k: not neither for k in q.CHECKS}
    return r


def fake_generator(store, state, prepared, instructions, token):
    return {'status': 'ready', 'document': {'blocks': [{'type': 'body_paragraph', 'text': 'A fresh draft.'}]}, 'usage': {}, 'error': ''}


def setup(store, fn):
    with patch.dict(os.environ, {'NCCE_REVIEW_BRIDGE_TOKEN_SHA256': hashlib.sha256(('test-bridge-token-'*4).encode()).hexdigest()}), patch.object(writer, 'API_KEY', 'mock'):
        ready_bridge(store)
        # These regressions isolate prospective judging. Consolidation has its
        # own end-to-end suite with a native claim/complete and durable memory.
        with patch('editorial_sync.maybe_queue',side_effect=lambda s,r:opt.get(s,r)):
            fn(store)


def vote(store, state, index, preference=None, acceptable=None):
    round_ = state['rounds'][-1]; pair = round_['pairs'][index]
    return q.record_verdict(store, {'run_id': state['run_id'], 'round': round_['number'], 'pair': index,
        'preference': preference or pair['review']['preference'],
        'acceptable': acceptable if acceptable is not None else [c['acceptable'] for c in pair['review']['candidates']]})


def test_calibration_is_cold_and_historical_feedback_has_no_credit():
    def check(store):
        assert len(q.contract()['historical_examples']) == 3
        assert all(not e['calibration_credit'] for e in q.contract()['historical_examples'])
        assert not q.calibration(store, 'territory_origin')['calibrated']
        assert q.calibration(store, 'territory_origin')['fresh_pairs'] == 0
        rejects(lambda: q.require_calibrated(store, 'territory_origin'))
    with_store(check)


def test_actual_controlled_pairs_calibration_validation_and_exact_activation():
    def check(store):
        state, _ = opt.queue(store, request(store))
        before = mechanical_records(store)
        calls = []
        def generator(store, state, prepared, instructions, token):
            calls.append((copy.deepcopy(prepared['packet']), instructions))
            return fake_generator(store,state,prepared,instructions,token)
        def reviewer(store,state,pair,preceding):
            return review(pair, neither=len(state['rounds']) == 1 and len(state['rounds'][-1]['pairs']) == 1)
        first = opt.execute(store,state['run_id'],generator=generator,reviewer=reviewer)
        assert first['status'] == 'awaiting_owner'
        assert len(calls) == 4 and first['reviewer_reserved'] == 2
        for i in (0,2):
            assert calls[i][0] == calls[i+1][0]
            assert calls[i][1] != calls[i+1][1]
        blind = exp.public_run(store,first)
        assert all(p['review'] is None and 'candidate_index' not in p for p in blind['rounds'][0]['pairs'])
        assert not blind['prompt_history']
        rejects(lambda: exp.checkpoint(store,{'run_id':first['run_id']}))
        vote(store,first,0); vote(store,first,1)
        assert exp.public_run(store,first)['rounds'][0]['pairs'][0]['review']
        second,_ = exp.checkpoint(store,{'run_id':first['run_id']})
        assert second['status'] == 'queued' and second['writer_limit'] == 12
        second = opt.execute(store,first['run_id'],generator=generator,reviewer=reviewer)
        assert second['status'] == 'awaiting_owner'
        vote(store,second,0);vote(store,second,1)
        assert q.calibration(store,second['form'])['calibrated']
        assert not q.calibration(store,'territory_origin')['calibrated']
        exp.checkpoint(store,{'run_id':first['run_id']})
        final = opt.execute(store,first['run_id'],generator=generator,reviewer=reviewer)
        assert final['status'] == 'awaiting_approval'
        assert final['rounds'][-1]['kind'] == 'validation'
        assert final['rounds'][-1]['revision_id'] == final['rounds'][-2]['revision_id']
        assert len({p['sample_key'] for r in final['rounds'] for p in r['pairs']}) == 6
        assert len(calls) == 12 and final['reviewer_reserved'] == 6
        assert ws.active(store,final['form']) is None
        rejects(lambda: opt.decide(store,{'run_id':final['run_id'],'approve':True}))
        vote(store,final,0);vote(store,final,1)
        opt.decide(store,{'run_id':final['run_id'],'approve':True})
        assert ws.active(store,final['form'])['revision_id'] == final['specific']['revision_id']
        assert mechanical_records(store) == before
    with_store(lambda store: setup(store,check))


def test_strong_rejection_revokes_agreement_and_owner_verdict_cannot_be_rewritten():
    def check(store):
        state,_ = opt.queue(store,request(store,1))
        state = opt.execute(store,state['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p))
        saved = vote(store,state,0,'neither',[False,False])
        assert saved['critical_miss'] and not saved['agrees']
        rejects(lambda: vote(store,state,0,'A',[True,False]))
        assert q.calibration(store,state['form'])['critical_misses'] == 1
        assert q.calibration(store,state['form'])['fresh_pairs'] == 0
        vote(store,state,1)
        exp.checkpoint(store,{'run_id':state['run_id']})
        state = opt.get(store,state['run_id'])
        assert state['status'] == 'awaiting_next_round' and not state['validation_pending']
        assert not state.get('tech')
        assert state['writer_reserved'] == 4
    with_store(lambda store: setup(store,check))


def test_same_source_cannot_manufacture_calibration_and_changed_standards_invalidate():
    def check(store):
        for i in range(2):
            state,_=opt.queue(store,request(store,1,'controlled-study-repeat-'+str(i)))
            state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p,True))
            a=vote(store,state,0);vote(store,state,1)
            assert a.get('duplicate_source',False) == bool(i)
        assert q.calibration(store,state['form'])['fresh_pairs'] == 2
        with patch.object(q,'fingerprint',return_value='new-owner-contract'):
            assert q.calibration(store,state['form'])['fresh_pairs'] == 0
            rejects(lambda: exp.checkpoint(store,{'run_id':state['run_id']}))
    with_store(lambda store: setup(store,check))


def test_no_identical_arm_spending_and_invalid_review_fails_closed():
    def check(store):
        b=request(store)
        rejects(lambda: opt.queue(store,{**b,'hypothesis':''}))
        rejects(lambda: opt.queue(store,{**b,'form_revision_id':None}))
        state,_=opt.queue(store,b)
        for field in ('acceptable','owner_checks'):
            p={'candidate_index':0};r=review(p);r['candidates'][0].pop(field)
            rejects(lambda: exp.validate_review(r))
        state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=lambda *a:assessment(10))
        assert state['status']=='escalated' and state['writer_reserved']==2
        assert ws.active(store,state['form']) is None
    with_store(lambda store: setup(store,check))


def test_native_review_payload_blinds_arm_identity_and_includes_owner_contract():
    def check(store):
        state,_=opt.queue(store,request(store))
        pair={'instructions':'candidate','comparison_instructions':['brief A','brief B'],'packet':{},'candidates':[],'candidate_index':1}
        job_id=cq.enqueue(store,state,pair,[],exp.schema(),opt.RUBRIC)
        import json
        payload=json.loads(cq.get(store,job_id)['payload_json'])
        assert payload['workflow_version']==3 and payload['editorial_contract']==q.contract()
        assert 'candidate_index' not in payload and 'instructions' not in payload
        assert payload['comparison_instructions']==['brief A','brief B']
    with_store(lambda store: setup(store,check))


def test_actual_provider_audit_contains_identical_inputs_and_different_instructions():
    def check(store):
        import json
        state,_=opt.queue(store,request(store,1))
        with patch.object(writer,'_call',side_effect=fake_call) as provider:
            state=opt.execute(store,state['run_id'],reviewer=lambda s,t,p,h:review(p))
            assert state['status']=='awaiting_owner' and provider.call_count==4
        for pair in state['rounds'][0]['pairs']:
            prompts=[]
            for c in pair['candidates']:
                row=store.db.execute('SELECT prompt_json FROM writer_request_details d JOIN writer_requests r USING(request_row_id) WHERE r.run_id=?',(c['trial_id'],)).fetchone()
                prompts.append(json.loads(row[0]))
            assert prompts[0]['input']==prompts[1]['input']
            assert prompts[0]['instructions']!=prompts[1]['instructions']
        assert not ws.active(store,state['form'])
    with_store(lambda store:setup(store,check))


def test_high_scores_cannot_hide_a_losing_candidate_and_critical_miss_revokes_existing_trust():
    def check(store):
        import json
        state,_=opt.queue(store,request(store,1))
        for i in range(3):
            record={'form':state['form'],'fingerprint':q.fingerprint(),'at':str(i),'agrees':True,
                    'critical_miss':False,'preference':'neither' if i==0 else 'A'}
            store.set_state('editorial-verdict:prior-fixture-'+str(i),json.dumps(record))
        assert q.calibration(store,state['form'])['calibrated']
        def prefers_current(s,t,p,h):
            r=review(p);r['preference']='AB'[1-p['candidate_index']]
            return r
        state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=prefers_current)
        assert state['status']=='awaiting_next_round' and not state['validation_pending']
        assert not state['rounds'][0]['candidate_non_regression']
        # Every score is 9, yet neither entry qualifies the candidate.
        assert all(c['overall']==9 for p in state['rounds'][0]['pairs'] for c in p['review']['candidates'])
        vote(store,state,0,'neither',[False,False])
        assert not q.calibration(store,state['form'])['calibrated']
        assert q.calibration(store,state['form'])['fresh_pairs']==0
        rejects(lambda:q.require_calibrated(store,state['form']))
    with_store(lambda store:setup(store,check))


def test_relative_preference_and_ties_do_not_require_publication_acceptance():
    pair={'candidate_index':0}
    for preference in ('A','B','tie','neither'):
        r=review(pair,True);r['preference']=preference
        exp.validate_review(r)
        assert not exp.candidate_passes({'candidate_index':0,'review':r})
        q.validate_verdict(preference,[False,False])
    bad=review(pair);bad['preference']='neither'
    rejects(lambda:exp.validate_review(bad))


def test_both_rejected_agrees_on_acceptance_despite_relative_ranking():
    def check(store):
        state,_=opt.queue(store,request(store,1))
        def ranked_rejection(s,t,p,h):
            r=review(p,True);r['preference']='A';return r
        state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=ranked_rejection)
        a=vote(store,state,0,'neither',[False,False])
        b=vote(store,state,1,'B',[False,False])
        assert a['agrees'] and a['acceptance_agrees'] and not a['ranking_agrees']
        assert b['agrees'] and not b['critical_miss']
        assert q.calibration(store,state['form'])['has_rejection_check']
    with_store(lambda store:setup(store,check))


def test_restore_original_native_verdict_and_resume_without_replaying_any_completed_call():
    def check(store):
        import json
        state,_=opt.queue(store,request(store,1))
        generated=[]
        def generator(*args):
            generated.append(args[-1]);return fake_generator(*args)
        def interrupted(s,t,p,h):
            job=cq.enqueue(s,t,p,h,exp.schema(),opt.RUBRIC);p['codex_job_id']=job;opt.save(s,t)
            identity={'thread_id':cq.thread_id(),'worker_id':'retained-review-worker','job_id':job}
            claim=cq.claim(s,identity)
            cq.started(s,{**identity,'lease':claim['lease'],'turn_id':'original-native-review-turn'})
            raise ValueError('Original submission rejected by the former ranking validator')
        broken=opt.execute(store,state['run_id'],generator=generator,reviewer=interrupted)
        assert broken['status']=='escalated' and len(generated)==2
        original=copy.deepcopy(broken['rounds'][0]['pairs'][0])
        # Old 0.18.0 runs did not retain per-round prepared_samples.
        broken['rounds'][0].pop('prepared_samples',None)
        broken['quality_fingerprint']='previous-protocol';broken['environment_hash']='previous-validator-source'
        opt.save(store,broken);opt.recover(store)
        verdict=review(original,True);verdict['preference']='A'
        job=original['codex_job_id']
        rejects(lambda:exp.restore_saved_review(store,job,verdict,'wrong-native-turn'))
        restored=exp.restore_saved_review(store,job,verdict,'original-native-review-turn')
        assert restored['status']=='awaiting_resume' and restored['writer_reserved']==2 and restored['reviewer_reserved']==1
        assert restored['rounds'][0]['pairs'][0]['candidates']==original['candidates']
        assert cq.get(store,job)['status']=='completed'
        assert exp.restore_saved_review(store,job,verdict,'original-native-review-turn')['status']=='awaiting_resume'
        altered={**verdict,'summary':'A different assessment.'}
        rejects(lambda:exp.restore_saved_review(store,job,altered,'original-native-review-turn'))
        rejects(lambda:exp.resume_saved_round(store,{'run_id':state['run_id']}))
        exp.resume_saved_round(store,{'run_id':state['run_id'],'allow_remaining':True})
        resumed=opt.execute(store,state['run_id'],generator=generator,reviewer=lambda s,t,p,h:review(p,True))
        assert resumed['status']=='awaiting_owner' and len(resumed['rounds'])==1
        assert len(resumed['rounds'][0]['pairs'])==2 and len(generated)==4 and len(set(generated))==4
        assert resumed['writer_reserved']==4 and resumed['reviewer_reserved']==2
        assert resumed['writer_limit']==4 and resumed['reviewer_limit']==2
        assert resumed['rounds'][0]['pairs'][0]['candidates']==original['candidates']
        assert not ws.active(store,resumed['form'])
    with_store(lambda store:setup(store,check))


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
