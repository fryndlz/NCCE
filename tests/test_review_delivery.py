"""Delayed native dispatch and selective review recovery, using fake providers."""
import copy
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
import codex_review_queue as cq
import workshop_optimizer as opt
import workshop_experiments as exp
import workshop_review_recovery as recovery
import workshop_interventions as interventions
from test_editorial_quality import setup, request, fake_generator, review
from test_writer_pipeline import with_store
from test_workshop_optimizer import rejects
from test_codex_review_bridge import identity


def interrupted(store):
    state, _ = opt.queue(store, request(store, 1))
    def reviewer(s, t, p, h):
        job = cq.enqueue(s, t, p, h, exp.schema(), opt.RUBRIC)
        p['codex_job_id'] = job
        if h:
            cq.cancel(s, job, 'Codex review timed out; no automatic replay')
            raise ValueError('Codex reviewer did not finish within 30 minutes')
        claim = cq.claim(s, {**identity(), 'job_id': job})
        body = {**identity(), 'job_id': job, 'lease': claim['lease'], 'turn_id': 'original-first-turn'}
        cq.started(s, body)
        cq.complete(s, {**body, 'review': review(p, True)})
        return json.loads(cq.get(s, job)['result_json'])
    return opt.execute(store, state['run_id'], generator=fake_generator, reviewer=reviewer)


def recovery_body(state):
    return {'run_id': state['run_id'], 'job_id': state['rounds'][-1]['pairs'][-1]['codex_job_id'],
            'request_key': 'exact-recovery-request-0001', 'allow_review_recovery': True}


def test_delayed_queue_and_offline_listener_do_not_expire_unclaimed_work():
    def check(store):
        state, _ = opt.queue(store, request(store, 1))
        pair = {'instructions': 'protected', 'packet': {}, 'candidates': []}
        state['workflow_version'] = 2
        clock = [0]; polls = []; lease = {}
        def delay(_):
            polls.append(opt.get(store, state['run_id'])['activity']['phase'])
            clock[0] += 8000
            if len(polls) == 1:
                assert cq.get(store, pair['codex_job_id'])['status'] == 'queued'
            elif len(polls) == 2:
                claim = cq.claim(store, {**identity(), 'job_id': pair['codex_job_id']})
                lease.update({**identity(), 'job_id': pair['codex_job_id'], 'lease': claim['lease'], 'turn_id': 'delayed-turn'})
                cq.started(store, lease)
            else:
                cq.complete(store, {**lease, 'review': __import__('test_workshop_optimizer').assessment()})
        with patch.object(opt.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(opt.time, 'sleep', side_effect=delay), patch.object(cq, 'status', return_value={'online': False}):
            result = opt.review_pair(store, state, pair, [])
        assert result['_codex']['turn_id'] == 'delayed-turn'
        assert polls == ['awaiting_reviewer', 'awaiting_reviewer', 'review']
        assert len(store.db.execute("SELECT * FROM codex_review_jobs WHERE run_id=?", (state['run_id'],)).fetchall()) == 1
    with_store(lambda s: setup(s, check))


def test_active_timeout_owner_cancel_and_sanitized_transport():
    def check(store):
        state, _ = opt.queue(store, request(store, 1)); state['workflow_version'] = 2
        pair = {'instructions': 'protected', 'packet': {}, 'candidates': []}
        clock = [0]; polls = [0]
        def delay(_):
            polls[0] += 1
            if polls[0] == 1:
                job = pair['codex_job_id']
                cq.notified(store, {**identity(), 'job_id': job})
                stamp = cq.transport(store, job)['notification_accepted_at']
                cq.notified(store, {**identity(), 'job_id': job})
                assert cq.transport(store, job)['notification_accepted_at'] == stamp
                rejects(lambda: cq.notified(store, {**identity(), 'job_id': job, 'thread_id': 'wrong'}))
                claim = cq.claim(store, {**identity(), 'job_id': job})
                cq.started(store, {**identity(), 'job_id': job, 'lease': claim['lease'], 'turn_id': 'slow-turn'})
            else:
                clock[0] = 1801
        with patch.object(opt.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(opt.time, 'sleep', side_effect=delay):
            rejects(lambda: opt.review_pair(store, state, pair, []))
        t = cq.transport(store, pair['codex_job_id'])
        assert t['status'] == 'cancelled' and t['started_at'] and 'Active Codex' in t['terminal_cause']
        assert set(t) == {'job_id','status','enqueued_at','notification_accepted_at','claimed_at','started_at','finished_at','terminal_cause'}
        assert not recovery.available(store, state)
        pair2 = {'instructions': 'protected', 'packet': {}, 'candidates': []}
        try: opt.review_pair(store, state, pair2, [], cancelled=lambda: True)
        except opt.ReviewCancelled: pass
        else: raise AssertionError('Owner stop ignored')
        assert cq.get(store, pair2['codex_job_id'])['error'] == 'Owner stopped the run'
    with_store(lambda s: setup(s, check))


def test_recovery_reuses_exact_drafts_mapping_and_original_allowance():
    def check(store):
        state = interrupted(store); original = copy.deepcopy(state)
        requests_before = store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]
        active_before = list(store.db.execute('SELECT * FROM workshop_active').fetchall())
        assert state['status'] == 'escalated' and len(state['rounds'][0]['pairs']) == 2
        assert recovery.available(store, state)
        body = recovery_body(state)
        recovered, fresh = recovery.recover(store, body)
        assert fresh
        assert recovery.recover(store, body)[1] is False
        rejects(lambda: recovery.recover(store, {**body, 'request_key': 'different-recovery-identity'}))
        audit = recovered['review_delivery_recovery']
        old = cq.get(store, audit['original_job_id']); new = cq.get(store, audit['replacement_job_id'])
        assert old['status'] == 'cancelled' and new['status'] == 'queued'
        old_payload = json.loads(old['payload_json']); new_payload = json.loads(new['payload_json'])
        for key in ('candidates','packet','comparison_instructions','preceding_reviews','editorial_contract','output_schema','prior_owner_corrections'):
            assert old_payload[key] == new_payload[key]
        assert new_payload['replacement_of'] == old['job_id']
        def reviewer(s, t, pair, preceding):
            claim = cq.claim(s, {**identity(), 'job_id': new['job_id']})
            native = {**identity(), 'job_id': new['job_id'], 'lease': claim['lease'], 'turn_id': 'replacement-real-turn'}
            cq.started(s, native);cq.complete(s, {**native, 'review': review(pair, True)})
            return json.loads(cq.get(s, new['job_id'])['result_json'])
        done = opt.execute(store, state['run_id'], generator=lambda *a: (_ for _ in ()).throw(AssertionError('Repeated writer request')), reviewer=reviewer)
        assert done['status'] == 'awaiting_owner'
        assert done['rounds'][0]['pairs'][0] == original['rounds'][0]['pairs'][0]
        for p, before in zip(done['rounds'][0]['pairs'], original['rounds'][0]['pairs']):
            for k in ('candidates','comparison_instructions','candidate_index','instructions','packet','packet_hash'):
                assert p[k] == before[k]
        for k in ('writer_reserved','reviewer_reserved','writer_limit','reviewer_limit'):
            assert done[k] == original[k]
        public = exp.public_run(store, done)
        assert all(p['review'] is None and 'candidate_index' not in p for p in public['rounds'][0]['pairs'])
        assert store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0] == requests_before
        assert list(store.db.execute('SELECT * FROM workshop_active').fetchall()) == active_before
    with_store(lambda s: setup(s, check))


def test_recovery_refuses_changes_uncertain_history_and_wrong_job():
    def check(store):
        state = interrupted(store); body = recovery_body(state)
        for field, value in [('environment_hash','different-source'),('quality_fingerprint','other-reviewer'),('writer_reserved',0)]:
            changed = copy.deepcopy(state);changed[field] = value
            rejects(lambda: recovery.inspect(store, changed))
        for mutate in [lambda s: s['configuration'].update(writer_model='other'),
                       lambda s: s['expected_active'].update(shared='changed'),
                       lambda s: s['rounds'][0]['pairs'][1]['packet'].update(subject='changed'),
                       lambda s: s['rounds'][0]['pairs'][1]['comparison_instructions'].__setitem__(0,'changed'),
                       lambda s: s['rounds'][0]['pairs'][1]['candidates'][0].update(status='error')]:
            changed = copy.deepcopy(state);mutate(changed);rejects(lambda: recovery.inspect(store, changed))
        rejects(lambda: recovery.recover(store, {**body,'allow_review_recovery':False}))
        rejects(lambda: recovery.recover(store, {**body,'job_id':'wrong'}))
        for column,value in [('claimed_at','previous-claim'),('worker_id','previous-worker'),('lease_hash','private'),('result_json','{"_codex":{"turn_id":"previous-native-turn"}}'),('status','completed'),('error','Owner stopped the run')]:
            saved = cq.get(store, body['job_id'])[column]
            with store.db: store.db.execute('UPDATE codex_review_jobs SET '+column+'=? WHERE job_id=?',(value,body['job_id']))
            assert recovery.available(store,state) is None
            rejects(lambda: recovery.recover(store, body))
            with store.db: store.db.execute('UPDATE codex_review_jobs SET '+column+'=? WHERE job_id=?',(saved,body['job_id']))
        # Frozen technical packets contain allowlisted status, never credentials.
        interventions.submit(store,state,'technical_investigation')
        payload = json.loads(cq.get(store,state['tech']['job_id'])['payload_json'])
        assert len(payload['packet']['review_transport']) == 2
        assert all('lease' not in k and 'worker' not in k for t in payload['packet']['review_transport'] for k in t)
    with_store(lambda s: setup(s, check))


def test_notification_acknowledgement_retry_never_redispatches_cli():
    sys.path.insert(0, str(ROOT/'scripts'))
    from codex_event_listener import EventListener
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        path = Path(folder)/'config.json'
        path.write_text(json.dumps({'base_url':'http://localhost','worker_id':'event-test-worker','thread_id':cq.THREAD_ID,'token':'disposable-test-only','codex_executable':'codex'}))
        listener = EventListener(path); attempts = []
        def post(action, body=None):
            if action == 'events': return {'job_id':'delayed-review'}
            attempts.append(action)
            if len(attempts) == 1: raise TimeoutError('metadata response lost')
            return {'ok':True}
        listener.post = post
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0)) as cli, patch('codex_event_listener.time.sleep'):
            try: listener.tick()
            except TimeoutError: pass
            else: raise AssertionError('Lost acknowledgement hidden')
            assert listener.tick() is False
            assert listener.tick() is False
            assert cli.call_count == 1 and attempts == ['notified','notified']


def test_only_exact_transport_source_upgrade_can_rebind_environment():
    def check(store):
        state = interrupted(store)
        current = opt.environment_fingerprint()
        assert current in recovery.REPAIRED_ENVIRONMENTS, 'Update exact compatibility hashes only after verifying transport-only edits'
        state['environment_hash'] = next(iter(recovery.PREVIOUS_ENVIRONMENTS))
        opt.save(store,state)
        assert recovery.available(store,state)
        upgraded,_ = recovery.recover(store,recovery_body(state))
        assert upgraded['environment_hash'] == current
        assert upgraded['review_delivery_recovery']['previous_environment_hash'] in recovery.PREVIOUS_ENVIRONMENTS
    with_store(lambda s: setup(s, check))


if __name__ == '__main__':
    for name, test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):
            test();print('PASS', name)
