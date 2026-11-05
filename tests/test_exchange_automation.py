"""Private exchange: exact slots, source seals, replay, no model/source writes."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writing_exchange import setup
import exchange_automation as exchange
from story_engine import regenerate

TEXT='+++ RECORD +++\n\n**The lamp cells**\n\nThey were still good.\n\n+++ END RECORD +++'


def queue_one(store,c):
    with patch.object(exchange,'candidates',return_value=[c]):
        # These adapter checks isolate publication; waterfall gates are covered
        # separately with the complete candidate graph.
        with patch('writing_waterfall.plan',return_value=([c],{},{})):
            exchange.prepare(store,1)
    row=store.db.execute('SELECT * FROM writing_exchange_requests WHERE target_key=? ORDER BY created_at DESC',(exchange.target_key(c),)).fetchone()
    request=json.loads(row['packet_json'])['request']
    return dict(request_id=request['request_id'],source_revision=request['source_revision'],status='READY',writer_text_md=TEXT)


def test_bounded_idempotent_preparation_and_authored_exclusion():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            first=exchange.prepare(s);assert 0<len(first)<=5
            frozen=exchange.outbox(s)
            assert exchange.prepare(s)==[]
            assert exchange.outbox(s)==frozen
            assert len(exchange.outbox(s))==len(first)
            assert not any(c['form']=='fighter_biography' and c['entity_key']==str(f) for c in exchange.candidates(s))
            assert not any(c['form']=='gang_origin' for c in exchange.candidates(s))
            assert not s.db.in_transaction
        finally:s.close()


def test_all_existing_target_kinds_import_exact_text_without_facts_or_clock_changes():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            before={t:[tuple(r) for r in s.db.execute('SELECT * FROM '+t)] for t in ('fighters','campaign_events','snapshots')}
            chosen={}
            for c in exchange.candidates(s):
                if not c['ready']:chosen.setdefault(c['kind'],c)
            assert {'artifact','memory','thought','entry'}<=set(chosen),set(chosen)
            for c in chosen.values():
                delivery=queue_one(s,c)
                with patch('llm_writer.write',side_effect=AssertionError('No model call')):
                    result=exchange.deliver(s,delivery)
                assert result['status']=='imported',result
                assert exchange.deliver(s,delivery)['receipt']==result['receipt']
                raw=exchange.projection(s,c)
                assert raw.get('content',json.loads(raw.get('document_json','{}')).get('external_markdown'))==TEXT
                original=json.loads(s.db.execute('SELECT target_json FROM writing_exchange_requests WHERE request_id=?',(delivery['request_id'],)).fetchone()[0])['original']
                assert original!=raw and original.get('evidence_json')==raw.get('evidence_json')
            assert {t:[tuple(r) for r in s.db.execute('SELECT * FROM '+t)] for t in before}==before
            assert len(list(Path(directory).glob('pre-exchange-automation.db')))==1
            regenerate(s,force=True,writer_enabled=False);exchange.restore(s)
            for c in chosen.values():
                raw=exchange.projection(s,c)
                assert raw.get('content',json.loads(raw.get('document_json','{}')).get('external_markdown'))==TEXT,c['kind']
        finally:s.close()


def test_changed_source_conflicts_unknown_ids_and_drafts_remain_audited():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            delivery=queue_one(s,c);prior=exchange.projection(s,c)
            s.db.execute("UPDATE story_memories SET evidence_json='[\"changed source\"]' WHERE fighter_id=? AND memory_key=?",c['key']);s.db.commit()
            result=exchange.deliver(s,delivery);assert result['status']=='held'
            assert exchange.projection(s,c)['content']==prior['content']
            assert s.db.execute('SELECT payload_json FROM writing_exchange_attempts').fetchone()[0].find('lamp cells')>=0
            assert exchange.deliver(s,delivery)['reused']
            delivery['request_id']='unknown'
            assert exchange.deliver(s,delivery)['status']=='held'
            assert s.db.execute('SELECT count(*) FROM writing_exchange_attempts').fetchone()[0]==2
        finally:s.close()


def test_committed_output_survives_refresh_restart_and_different_delivery_cannot_replace_it():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            delivery=queue_one(s,c);assert exchange.deliver(s,delivery)['status']=='imported'
            bad={**delivery,'writer_text_md':'A second version'}
            assert exchange.deliver(s,bad)['status']=='held'
            regenerate(s,force=True,writer_enabled=False);exchange.restore(s)
            assert exchange.projection(s,c)['content']==TEXT
            path=s.path;s.close()
            from store import Store
            s=Store(path);exchange.restore(s)
            assert exchange.projection(s,c)['content']==TEXT
            assert exchange.deliver(s,delivery)['status']=='imported'
        finally:s.close()


def test_atomic_write_failure_leaves_output_available_for_same_payload_retry():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            delivery=queue_one(s,c);before=exchange.projection(s,c)
            with patch.object(exchange,'_write',side_effect=RuntimeError('disk unavailable')):
                try:exchange.deliver(s,delivery);raise AssertionError('failure expected')
                except RuntimeError:pass
            assert exchange.projection(s,c)==before
            assert s.db.execute('SELECT state FROM writing_exchange_requests').fetchone()[0]=='PENDING'
            assert exchange.deliver(s,delivery)['status']=='imported'
        finally:s.close()


def test_auth_is_dedicated_and_default_closed():
    with patch.dict(os.environ,{'NCCE_EXCHANGE_TOKEN':''}):
        assert not exchange.enabled() and not exchange.authenticated('Bearer ')
    with patch.dict(os.environ,{'NCCE_EXCHANGE_TOKEN':'disposable-test-only-00000000000000'}):
        assert exchange.enabled()
        assert not exchange.authenticated('Bearer incorrect')
        assert exchange.authenticated('Bearer disposable-test-only-00000000000000')


if __name__=='__main__':
    for name,check in list(globals().items()):
        if name.startswith('test_') and callable(check):check();print('PASS',name)
