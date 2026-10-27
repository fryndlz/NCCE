"""Offline quality gates exercised through real Workshop audits and mocked provider."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
import llm_writer as writer
import writer_quality as quality
from test_writer_pipeline import with_store, draft
from test_writer_workshop import seed
from test_story_engine import mechanical_records


def setup(store, max_rounds=3):
    source = seed(store)
    return quality.Workflow.create(store, {'fighter_memory': source['key']}, max_rounds)


def review(flow, score=8, issue=None):
    value = flow.bundle('fighter_memory')['template']
    value['summary'] = 'Both drafts use a coherent concrete action and consistent viewpoint.'
    value['next_instructions'] = 'Make the consequence specific to this fighter.'
    for candidate in value['candidates']:
        candidate['overall'] = score
        candidate['scores'] = {key: score for key in quality.CRITERIA}
        candidate['issues'] = [issue] if issue else []
    return value


def fake_candidate(pair, index):
    return {'status': 'ready', 'document': {'blocks': [{'text': 'Sample ' + str(index)}]}, 'usage': {}}


def rejects(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('Unsafe transition accepted')


def test_no_grant_no_spend_two_calls_only_and_no_source_changes():
    def check(store):
        flow = setup(store)
        before = mechanical_records(store)
        memories = [tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
        active = [tuple(r) for r in store.db.execute('SELECT * FROM workshop_active')]
        packets = []
        def fake(form, packet, **kwargs):
            packets.append(copy.deepcopy(packet))
            writer._calls += 1
            writer._last_prompt.update(instructions=kwargs['contract_override'], input=json.dumps(packet))
            writer._last_response.update(input_tokens=100, output_tokens=20)
            return draft('I left the tools where they were. The handle still hurt my hand.')
        with patch.object(writer, 'API_KEY', 'mock'), patch.object(writer, '_call', side_effect=fake) as provider:
            flow.inspect('fighter_memory')
            rejects(lambda: flow.run_pair('fighter_memory'))
            assert provider.call_count == 0
            flow.grant('fighter_memory', 'human')
            flow.run_pair('fighter_memory')
            rejects(lambda: flow.run_pair('fighter_memory'))
            assert provider.call_count == 2
        assert len(packets) == 2
        assert packets[0].pop('editorial_evaluation_run') != packets[1].pop('editorial_evaluation_run')
        assert packets[0] == packets[1]
        assert store.db.execute('SELECT COUNT(*) FROM writer_requests').fetchone()[0] == 2
        assert mechanical_records(store) == before
        assert memories == [tuple(r) for r in store.db.execute('SELECT * FROM story_memories')]
        assert active == [tuple(r) for r in store.db.execute('SELECT * FROM workshop_active')]
    with_store(check)


def test_reviews_require_both_candidates_and_finite_scores_bound_to_pair():
    def check(store):
        flow = setup(store); flow.grant('fighter_memory', 'human'); flow.run_pair('fighter_memory', fake_candidate)
        good = review(flow)
        for bad in (dict(good, candidates=good['candidates'][:1]), dict(good, bundle_hash='stale')):
            rejects(lambda: flow.review('fighter_memory', bad))
        for score in (True, float('nan'), float('inf'), -1, 11, '8'):
            bad = copy.deepcopy(good); bad['candidates'][0]['overall'] = score
            rejects(lambda: flow.review('fighter_memory', bad))
        bad = copy.deepcopy(good); bad['candidates'][1]['scores']['voice_and_viewpoint'] = 7
        flow.review('fighter_memory', bad)
        assert flow.state()['forms']['fighter_memory']['status'] == 'awaiting_grant'
        rejects(lambda: flow.decide('fighter_memory', 'human', True, 'approve'))
    with_store(check)


def test_qualified_is_human_gate_and_scope_cannot_claim_all_forms():
    def check(store):
        flow = setup(store); flow.grant('fighter_memory', 'human'); flow.run_pair('fighter_memory', fake_candidate)
        flow.review('fighter_memory', review(flow))
        report = flow.report()
        assert report['all_selected_forms_at_target'] and not report['all_fourteen_forms_selected']
        assert not report['ready_for_bulk_planning']
        rejects(lambda: flow.run_pair('fighter_memory', fake_candidate))
        flow.decide('fighter_memory', 'human', True, 'I approve these samples')
        assert flow.report()['ready_for_bulk_planning']
        assert not flow.report()['bulk_generation_enabled'] and not flow.report()['publication_enabled']
        rejects(lambda: flow.decide('fighter_memory', 'human', True, 'duplicate'))
    with_store(check)


def test_every_nonwriting_issue_escalates_even_with_high_scores():
    for category in ('context', 'technical', 'permission'):
        def check(store):
            flow = setup(store); flow.grant('fighter_memory', 'human'); flow.run_pair('fighter_memory', fake_candidate)
            issue = {'category': category, 'blocking': False, 'evidence': 'Missing source field', 'explanation': 'Needs human investigation'}
            flow.review('fighter_memory', review(flow, 9, issue))
            assert flow.state()['forms']['fighter_memory']['status'] == 'escalated'
            rejects(lambda: flow.grant('fighter_memory', 'human'))
            flow.resolve('fighter_memory', 'human', 'Investigated the missing field; use the existing bounded evidence')
            rejects(lambda: flow.run_pair('fighter_memory', fake_candidate))
        with_store(check)


def test_failure_stops_second_call_and_restart_never_replays_pair():
    def check(store):
        flow = setup(store); flow.grant('fighter_memory', 'human')
        calls = []
        def fail(pair, index):
            calls.append(index)
            return {'status': 'error', 'error': 'quota exhausted'}
        flow.run_pair('fighter_memory', fail)
        assert calls == [0]
        assert quality.Workflow(store).state()['forms']['fighter_memory']['status'] == 'escalated'
        rejects(lambda: flow.run_pair('fighter_memory', fail))
        flow.resolve('fighter_memory', 'human', 'Quota investigated')
        flow.grant('fighter_memory', 'human')
        # Simulate abrupt process death after durable reservation; reopening does not replay.
        with flow.change() as state: state['forms']['fighter_memory']['status'] = 'running'
        restarted = quality.Workflow(store)
        rejects(lambda: restarted.run_pair('fighter_memory', fail))
        restarted.resolve('fighter_memory', 'human', 'Checked provider audit after crash; abandon uncertain pair')
        rejects(lambda: restarted.run_pair('fighter_memory', fail))
    with_store(check)


def test_round_cap_requires_human_reassessment_and_no_automatic_spend():
    def check(store):
        flow = setup(store, 1); flow.grant('fighter_memory', 'human'); flow.run_pair('fighter_memory', fake_candidate)
        flow.review('fighter_memory', review(flow, 7))
        flow.grant('fighter_memory', 'human')
        assert flow.state()['forms']['fighter_memory']['status'] == 'escalated'
        assert len(flow.state()['forms']['fighter_memory']['rounds']) == 1
    with_store(check)


def test_snapshot_cli_copies_wal_and_rejects_live_databases_and_concurrent_operators():
    import importlib.util
    import sqlite3
    spec = importlib.util.spec_from_file_location('quality_cli', ROOT / 'scripts' / 'writer_quality.py')
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    def check(store):
        selected = seed(store)
        before = mechanical_records(store)
        target = store.path.parent / 'quality-run'
        cli.snapshot(store.path, target, ['fighter_memory'], {'fighter_memory': selected['key']}, 3)
        with cli.opened(target) as flow:
            assert mechanical_records(flow.store) == before
            rejects(lambda: cli.opened(target).__enter__())
            flow.grant('fighter_memory', 'human')
            flow.run_pair('fighter_memory', fake_candidate)
            flow.review('fighter_memory', review(flow))
            flow.decide('fighter_memory', 'human', False, 'The score does not match my judgment')
            rejects(lambda: flow.grant('fighter_memory', 'human'))
        assert mechanical_records(store) == before
        assert not store.db.execute("SELECT 1 FROM sqlite_master WHERE name='quality_run'").fetchone()
        assert not (target / 'operator.lock').exists()
        # Ordinary campaign databases must be rejected before Store initialization/migration.
        original_folder = store.path.parent / 'ordinary'; original_folder.mkdir()
        with closing(sqlite3.connect(original_folder / 'snapshot.db')) as db:
            db.execute('CREATE TABLE untouched (value TEXT)')
        rejects(lambda: cli.opened(original_folder).__enter__())
        with closing(sqlite3.connect(original_folder / 'snapshot.db')) as db:
            assert [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ['untouched']
    with_store(check)


def test_missing_credentials_and_changed_config_stop_before_provider():
    def check(store):
        flow = setup(store); flow.grant('fighter_memory', 'human')
        with patch.object(writer, 'API_KEY', ''), patch.object(writer, '_call') as provider:
            flow.run_pair('fighter_memory')
            assert provider.call_count == 0
        flow.resolve('fighter_memory', 'human', 'Configured credentials')
        flow.grant('fighter_memory', 'human')
        with patch.object(writer, 'MODEL', 'changed'), patch.object(writer, '_call') as provider:
            flow.run_pair('fighter_memory')
            assert provider.call_count == 0
        assert flow.state()['forms']['fighter_memory']['status'] == 'escalated'
    with_store(check)


if __name__ == '__main__':
    for name, test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):
            test(); print('PASS', name)
