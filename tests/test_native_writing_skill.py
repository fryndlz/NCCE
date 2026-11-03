"""Native-author helper checks against disposable data; no hosted or model calls."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_writer_pipeline import with_store


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'skills/ncce-backlog-writer/scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_journal():
    journal = load('journal')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / 'private'
        assert journal.read(root) == [] and not root.exists()
        first = {'id': 'draft-1', 'kind': 'draft', 'form': 'place_event', 'text': 'A readable first draft.'}
        assert journal.append(root, first)['created']
        assert not journal.append(root, first)['created']
        try:
            journal.append(root, {**first, 'text': 'Overwritten!'})
        except ValueError:
            pass
        else:
            raise AssertionError('Existing immutable draft was replaced')
        journal.append(root, {'id': 'feedback-1', 'kind': 'feedback', 'text': 'Keep the precinct central.', 'draft_ids': ['draft-1']})
        journal.append(root, {'id': 'standard-1', 'kind': 'standard', 'text': 'Keep the actual institution central.', 'feedback_id': 'feedback-1'})
        rows = journal.read(root)
        assert [r['id'] for r in rows] == ['standard-1', 'feedback-1', 'draft-1']
        assert all(r['stored_at'].endswith('+00:00') and len(r['sha256']) == 64 for r in rows)
        assert 'A readable first draft.' in journal.markdown(rows)
        assert rows[-1]['text'] == first['text']
        journal.append(root, {'id': 'standard-2', 'kind': 'standard', 'form': 'place_event',
                              'text': 'A more specific updated rule.', 'supersedes': 'standard-1'})
        assert [r['id'] for r in journal.standards(root, 'place_event')] == ['standard-2']
        assert journal.standards(root, 'fighter_memory') == []


def test_context():
    context = load('context')
    import writer_workshop as ws
    import writing_rag as rag
    import llm_writer as writer

    def check(store):
        from test_story_engine import campaign, latest_game, apply
        from story_engine import regenerate
        first = campaign()
        apply(store, first)
        apply(store, latest_game(first))
        regenerate(store, writer_enabled=False)
        rag.sync_sources(store)
        source = next(s for s in ws.catalog(store) if s['form'] == 'territory_origin' and not s['key'].startswith('comparison:'))
        before = '\n'.join(store.db.iterdump())
        with patch.object(writer, '_call', side_effect=AssertionError('No provider calls allowed')):
            catalog = context.inspect(ROOT, store.path)
            result = context.inspect(ROOT, store.path, source['key'])
        assert source in catalog['subjects']
        assert result['sample']['key'] == source['key']
        assert result['context']['instructions'] and result['context']['subject_packet']
        assert '\n'.join(store.db.iterdump()) == before
        try:
            context.inspect(ROOT, store.path, 'comparison:0:0')
        except ValueError:
            pass
        else:
            raise AssertionError('Blind comparison exposed')
    with_store(check)
    with tempfile.TemporaryDirectory() as folder:
        missing = Path(folder) / 'absent.db'
        try:
            context.inspect(ROOT, missing)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Missing source accepted')
        assert not missing.exists()


def test_native_client():
    client = load('client')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        cfg = root / 'config.json'
        cfg.write_text(json.dumps({'base_url': 'https://ncce-private-preview.onrender.com',
                                  'thread_id': 'configured-jks-thread', 'token': 'private-token-never-output'}))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps({'subjects': [{'key': 'artifact:real', 'label': 'Source subject'}]}).encode()
        class Opener:
            def open(self, request, timeout):
                assert request.full_url.endswith('/api/native-author/catalog')
                assert json.loads(request.data)['thread_id'] == 'configured-jks-thread'
                return Response()
        with patch.object(client, 'build_opener', return_value=Opener()):
            manifest = client.call(cfg, 'catalog', {}, root / 'responses')
        assert 'private-token-never-output' not in json.dumps(manifest)
        page = client.read(manifest['path'], manifest['sha256'], '/subjects/0')
        assert page['complete'] and json.loads(page['text'])['key'] == 'artifact:real'
        try:
            client.read(manifest['path'], '0' * 64)
        except ValueError:
            pass
        else:
            raise AssertionError('Altered response accepted')
        cfg.write_text(json.dumps({'base_url': 'https://unrelated.example', 'token': 'private', 'thread_id': 'x'}))
        with patch.object(client, 'build_opener', side_effect=AssertionError('Credential sent to another host')):
            try:
                client.call(cfg, 'catalog', {}, root / 'responses')
            except ValueError:
                pass
            else:
                raise AssertionError('Unexpected host accepted')


if __name__ == '__main__':
    test_journal()
    test_context()
    test_native_client()
    print('Native writing skill checks passed: immutable journal, idempotency, read-only real-context export, no model calls.')
