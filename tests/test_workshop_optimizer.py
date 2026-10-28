"""Optimization improves future production prompts; no paid calls during tests."""
import copy
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
import llm_writer as writer
import writer_workshop as ws
import workshop_optimizer as opt
from test_writer_pipeline import with_store as base_with_store, draft
import os
import hashlib
import codex_review_queue as cq
from test_writer_workshop import seed
from test_story_engine import mechanical_records


def with_store(check):
    def wrapped(store):
        with patch.dict(os.environ, {'NCCE_REVIEW_BRIDGE_TOKEN_SHA256':hashlib.sha256(('test-bridge-token-'*4).encode()).hexdigest()}):
            ready_bridge(store)
            check(store)
    base_with_store(wrapped)


def ready_bridge(store):
    identity = {'thread_id':cq.thread_id(),'worker_id':'test-worker-0001'}
    cq.self_test(store,{})
    claim = cq.claim(store,identity)
    lease = {**identity,'job_id':claim['job']['job_id'],'lease':claim['lease'],'turn_id':'test-diagnostic-turn'}
    cq.started(store,lease)
    cq.complete(store,{**lease,'review':assessment()})
    cq.heartbeat(store,identity)


def body(store, rounds=3):
    return {'sample_key': seed(store)['key'], 'request_key': 'optimizer-request-000000001', 'max_rounds': rounds, 'allow_paid': True}


def assessment(score=8, category=None):
    return {'summary': 'The actions are concrete and maintain the fighter viewpoint.',
            'proposed_form_instructions': 'First person, 40–100 words. Show one physically intelligible action and this fighter’s concrete consequence. Preserve event boundaries.',
            'candidates': [{'index': i, 'overall': score, 'scores': {c: score for c in opt.CRITERIA},
                            'issues': [{'category': category, 'evidence': 'Missing historical identity', 'explanation': 'The source context needs repair', 'blocking': False}] if category else []}
                           for i in range(2)]}


def rejects(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('Invalid operation accepted')


def fake_call(form, packet, **kwargs):
    writer._calls += 1
    writer._last_prompt.update(instructions=kwargs['contract_override'], input=json.dumps(packet))
    writer._last_response.update(input_tokens=100, output_tokens=30)
    return draft('I put the handle down. My hand still hurt when I opened it.')


def test_live_activity_is_persisted_before_each_provider_role_runs():
    def check(store):
        request = body(store, 3)
        with patch.object(writer, 'API_KEY', 'mock'):
            state, _ = opt.queue(store, request)
            def generator(store, state, prepared, instructions, token):
                live = opt.get(store, state['run_id'])['activity']
                assert live['actor'] == 'JuniorWriter' and live['phase'] == 'draft'
                assert live['draft'] in (1, 2) and live['sample'] in (1, 2)
                return {'status':'ready','document':{},'usage':{},'error':''}
            def reviewer(store, state, pair, preceding):
                live = opt.get(store, state['run_id'])['activity']
                assert live['actor'] == 'StoryTechMan' and live['phase'] == 'awaiting_reviewer'
                return assessment(7 if len(state['rounds']) == 1 else 9)
            result = opt.execute(store, state['run_id'], generator=generator, reviewer=reviewer)
            assert result['activity']['phase'] == 'approval' and result['activity']['actor'] == 'human'
            assert set(result['visited_steps']) == {'context','draft','awaiting_reviewer','evaluate','revise','validation','approval'}
    with_store(check)


def test_loop_revises_real_prompt_and_explicit_approval_changes_future_ncce_generation():
    def check(store):
        request = body(store); before = mechanical_records(store)
        memories = [tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
        with patch.object(writer, 'API_KEY', 'mock'), patch.object(writer, '_call', side_effect=fake_call) as provider:
            state, fresh = opt.queue(store, request)
            assert fresh and len(state['samples']) == 2 and provider.call_count == 0
            reviewer = lambda store, state, pair, preceding: assessment(7 if len(state['rounds']) == 1 else 9)
            result = opt.execute(store, state['run_id'], reviewer=reviewer)
            assert result['status'] == 'awaiting_approval' and len(result['rounds']) == 3
            assert result['writer_reserved'] == 12 and result['reviewer_reserved'] == 6 and provider.call_count == 12
            assert ws.active_contract(store, 'fighter_memory') is None
            assert 'physically intelligible' in provider.call_args.kwargs['contract_override']
            assert mechanical_records(store) == before
            assert memories == [tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
            assert opt.execute(store, state['run_id'], reviewer=reviewer)['status'] == 'awaiting_approval'
            assert provider.call_count == 12
            opt.decide(store, {'run_id': state['run_id'], 'approve': True})
            assert 'physically intelligible' in ws.active_contract(store, 'fighter_memory')
            writer.reset_budget(1)
            writer.write(store, 'fighter_memory', {'subject': 'A new production context'})
            assert provider.call_count == 13
            assert 'physically intelligible' in provider.call_args.kwargs['contract_override']
        assert mechanical_records(store) == before
    with_store(check)


def test_technical_issue_stops_entire_loop_before_second_sample_or_revision():
    for category in ('context', 'technical', 'permission'):
        def check(store):
            request = body(store, 3)
            with patch.object(writer, 'API_KEY', 'mock'), patch.object(writer, '_call', side_effect=fake_call) as provider:
                state, _ = opt.queue(store, request)
                result = opt.execute(store, state['run_id'], reviewer=lambda *args: assessment(9, category))
                assert result['status'] == 'escalated' and provider.call_count == 2
                assert result['reviewer_reserved'] == 1 and len(result['rounds'][0]['pairs']) == 1
                assert ws.active_contract(store, 'fighter_memory') is None
                rejects(lambda: opt.decide(store, {'run_id': state['run_id'], 'approve': True}))
        with_store(check)


def test_budget_cancel_and_failed_writer_never_trigger_automatic_retries():
    for kind in ('budget', 'cancel', 'failure'):
        def check(store):
            request = body(store, 1)
            with patch.object(writer, 'API_KEY', 'mock'):
                state, _ = opt.queue(store, request)
                calls = []
                def generator(*args):
                    calls.append(1)
                    return {'status': 'error' if kind == 'failure' else 'ready', 'document': {}, 'usage': {}, 'error': 'quota exhausted' if kind == 'failure' else ''}
                cancel = lambda: kind == 'cancel' and opt.get(store, state['run_id'])['writer_reserved'] >= 1
                result = opt.execute(store, state['run_id'], generator=generator, reviewer=lambda *a: assessment(7), cancelled=cancel)
                assert result['status'] == {'budget': 'awaiting_next_round', 'cancel': 'stopped', 'failure': 'escalated'}[kind]
                if kind == 'budget':
                    assert result['message'].startswith('This test batch is complete.')
                    assert 'Drafts and reviews are saved' in result['message']
                    assert 'credit' not in result['message'] and 'failure' not in result['message']
                assert len(calls) == (4 if kind == 'budget' else 1)
                assert result['reviewer_reserved'] == (2 if kind == 'budget' else 0)
                assert ws.active_contract(store, 'fighter_memory') is None
        with_store(check)


def test_idempotency_authorization_restart_and_stale_promotion():
    def check(store):
        request = body(store)
        with patch.object(writer, 'API_KEY', 'mock'), patch.object(writer, '_call', side_effect=fake_call):
            rejects(lambda: opt.queue(store, {**request, 'allow_paid': False}))
            state, _ = opt.queue(store, request)
            assert opt.queue(store, request)[1] is False
            rejects(lambda: opt.queue(store, {**request, 'max_rounds': 2}))
            result = opt.execute(store, state['run_id'], reviewer=lambda *a: assessment())
            changed = ws.save_revision(store, {**ws.defaults('shared'), 'instructions': 'New owner shared instructions'})
            ws.activate(store, {'scope': 'shared', 'revision_id': changed['revision_id'], 'expected_active': None})
            rejects(lambda: opt.decide(store, {'run_id': state['run_id'], 'approve': True}))
            assert ws.active(store, 'shared')['revision_id'] == changed['revision_id']
            assert ws.active(store, 'fighter_memory') is None
            result['status'] = 'running'; opt.save(store, result); opt.recover(store)
            assert opt.get(store, state['run_id'])['status'] == 'escalated'
            assert opt.execute(store, state['run_id'])['status'] == 'escalated'
    with_store(check)


def test_duplicate_context_cannot_be_used_as_two_independent_samples():
    def check(store):
        selected = seed(store)
        with patch.object(writer, 'API_KEY', 'mock'), patch.object(ws, 'catalog', return_value=[selected]):
            rejects(lambda: opt.queue(store, {'sample_key': selected['key'], 'request_key': 'one-context-0000000', 'allow_paid': True}))
        assert store.db.execute('SELECT count(*) FROM workshop_optimization_runs').fetchone()[0] == 0
    with_store(check)


def test_codex_wait_has_no_external_api_fallback():
    def check(store):
        with patch.object(writer, 'API_KEY', 'mock'):
            state, _ = opt.queue(store, body(store))
            pair={'instructions':'protected','packet':{},'candidates':[]}
            with patch('urllib.request.urlopen') as network:
                try:opt.review_pair(store,state,pair,[],cancelled=lambda:True)
                except opt.ReviewCancelled:pass
                else:raise AssertionError('Cancelled Codex wait continued')
                assert network.call_count==0
            assert store.db.execute("SELECT status FROM codex_review_jobs WHERE run_id != 'connection-check'").fetchone()[0]=='cancelled'
    with_store(check)


def test_invalid_reviewer_scores_and_shapes_fail_closed():
    for value in (True, float('nan'), float('inf'), -1, 11, '8'):
        bad = assessment(); bad['candidates'][0]['overall'] = value
        rejects(lambda: opt.assess(bad))
    for change in ({'candidates': []}, {'proposed_form_instructions': ''}, {'summary': ''}):
        rejects(lambda: opt.assess({**assessment(), **change}))


def test_server_upgrade_backup_includes_committed_wal_without_changing_source():
    import sqlite3
    from contextlib import closing
    from migrations import backup_before_upgrade
    def check(store):
        with store.db:
            store.db.execute("INSERT INTO system_state VALUES('backup-test','preserved')")
            store.db.execute('PRAGMA user_version=12')
        target = backup_before_upgrade(store.path)
        assert target and target.exists()
        with closing(sqlite3.connect(target)) as db:
            assert db.execute('PRAGMA user_version').fetchone()[0] == 12
            assert db.execute("SELECT value FROM system_state WHERE key='backup-test'").fetchone()[0] == 'preserved'
            assert db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        assert store.db.execute('PRAGMA user_version').fetchone()[0] == 12
        with store.db: store.db.execute('PRAGMA user_version=14')
        assert backup_before_upgrade(store.path) is None
    with_store(check)


if __name__ == '__main__':
    for name, test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test): test(); print('PASS', name)
