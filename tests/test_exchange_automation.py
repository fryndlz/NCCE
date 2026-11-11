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
            assert frozen[0]['request']['form']=='gang_origin'
            assert all(c['phase']==0 for c in exchange.candidates(s) if c['form']=='gang_origin')
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


def test_versioned_revision_reuses_original_slot_and_preserves_audit_across_rebuild():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            first=queue_one(s,c)
            accepted=exchange.deliver(s,first)
            assert accepted['status']=='imported'
            revision=exchange.request_revision(s,first['request_id'],accepted['receipt'])
            assert revision['status']=='PENDING'
            again=exchange.request_revision(s,first['request_id'],accepted['receipt'])
            assert again['request_id']==revision['request_id'] and again['reused']
            packet=next(p for p in exchange.outbox(s) if p['request']['request_id']==revision['request_id'])
            assert packet['request']['source_revision']!=first['source_revision']
            assert any(x['section']=='revision_baseline' and x['text']==TEXT for x in packet['context'])
            replacement='**Revised memory**\\n\\nSame event, clearer wording.'
            deliver=dict(request_id=revision['request_id'],
                         source_revision=packet['request']['source_revision'],
                         status='READY',writer_text_md=replacement)
            result=exchange.deliver(s,deliver)
            assert result['status']=='imported',result
            assert exchange.projection(s,c)['content']==replacement
            assert exchange.deliver(s,deliver)['receipt']==result['receipt']
            assert exchange.deliver(s,first)['receipt']==accepted['receipt']
            assert s.db.execute("""SELECT count(*) FROM writing_exchange_requests
                WHERE target_key=? AND state='IMPORTED'""",(exchange.target_key(c),)).fetchone()[0]==2
            assert s.db.execute("""SELECT raw_markdown FROM writing_exchange_requests
                WHERE request_id=?""",(first['request_id'],)).fetchone()[0]==TEXT
            assert s.db.execute("""SELECT revision_of FROM writing_exchange_requests
                WHERE request_id=?""",(revision['request_id'],)).fetchone()[0]==first['request_id']
            assert len(s.db.execute("""SELECT * FROM story_memories
                WHERE fighter_id=? AND memory_key=? AND active=1""",c['key']).fetchall())==1
            regenerate(s,force=True,writer_enabled=False)
            exchange.restore(s)
            assert exchange.projection(s,c)['content']==replacement
            path=s.path;s.close()
            from store import Store
            s=Store(path);exchange.restore(s)
            assert exchange.projection(s,c)['content']==replacement
            # New corrections must chain from the latest successful receipt.
            try:
                exchange.request_revision(s,first['request_id'],accepted['receipt'])
                raise AssertionError('Old parent should be rejected')
            except ValueError as exc:
                assert 'newer revision' in str(exc)
        finally:s.close()


def test_revision_of_imported_biography_keeps_one_document_and_survives_rebuild():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['form']=='fighter_biography' and not c['approved'])
            original=queue_one(s,c)
            first=exchange.deliver(s,original)
            assert first['status']=='imported'
            child=exchange.request_revision(s,original['request_id'],first['receipt'])
            packet=next(x for x in exchange.outbox(s) if x['request']['request_id']==child['request_id'])
            replacement='**Edited fighter dossier**\\n\\nPreserved facts; amended interpretation.'
            result=exchange.deliver(s,dict(request_id=child['request_id'],status='READY',
                source_revision=packet['request']['source_revision'],writer_text_md=replacement))
            assert result['status']=='imported',result
            doc=json.loads(exchange.projection(s,c)['document_json'])
            assert doc['external_markdown']==replacement
            assert doc['external_request_id']==child['request_id']
            assert s.db.execute("""SELECT count(*) FROM story_artifacts
                WHERE scope_type=? AND scope_key=? AND active=1""",c['key']).fetchone()[0]==1
            regenerate(s,force=True,writer_enabled=False);exchange.restore(s)
            doc=json.loads(exchange.projection(s,c)['document_json'])
            assert doc['external_markdown']==replacement
            assert doc['external_request_id']==child['request_id']
            old=s.db.execute('SELECT raw_markdown,receipt FROM writing_exchange_requests WHERE request_id=?',
                             (original['request_id'],)).fetchone()
            assert old['raw_markdown']==TEXT and old['receipt']==first['receipt']
        finally:s.close()


def test_multiple_successive_revisions_use_only_latest_accepted_baseline():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            original=queue_one(s,c);first=exchange.deliver(s,original)
            one=exchange.request_revision(s,original['request_id'],first['receipt'])
            packet=next(x for x in exchange.outbox(s) if x['request']['request_id']==one['request_id'])
            t1='First corrected reading of the event.'
            a=exchange.deliver(s,dict(request_id=one['request_id'],status='READY',
                source_revision=packet['request']['source_revision'],writer_text_md=t1))
            assert a['status']=='imported',a
            two=exchange.request_revision(s,one['request_id'],a['receipt'])
            packet2=next(x for x in exchange.outbox(s) if x['request']['request_id']==two['request_id'])
            bases=[v['text'] for v in packet2['context'] if v['section']=='revision_baseline']
            assert bases==[t1],bases
            assert len([v for v in packet2['context']
                        if v.get('source_ref')=='Explicit imported-prose correction'])==1
            t2='Second corrected reading of the same event.'
            b=exchange.deliver(s,dict(request_id=two['request_id'],status='READY',
                source_revision=packet2['request']['source_revision'],writer_text_md=t2))
            assert b['status']=='imported',b
            regenerate(s,force=True,writer_enabled=False);exchange.restore(s)
            assert exchange.projection(s,c)['content']==t2
            revisions=s.db.execute("""SELECT revision_of,raw_markdown,receipt
                FROM writing_exchange_requests WHERE target_key=? AND state='IMPORTED'
                ORDER BY rowid""",(exchange.target_key(c),)).fetchall()
            assert len(revisions)==3
            assert [r['raw_markdown'] for r in revisions]==[TEXT,t1,t2]
            assert [r['revision_of'] for r in revisions]==[None,original['request_id'],one['request_id']]
            assert len({r['receipt'] for r in revisions})==3
        finally:s.close()


def test_revision_refuses_stale_receipt_source_edits_and_unapproved_overwrite():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            original=queue_one(s,c);accepted=exchange.deliver(s,original)
            for receipt in ('wrong', ''):
                try:
                    exchange.request_revision(s,original['request_id'],receipt)
                    raise AssertionError('Unverified receipt accepted')
                except ValueError:pass
            child=exchange.request_revision(s,original['request_id'],accepted['receipt'])
            row=s.db.execute('SELECT source_revision FROM writing_exchange_requests WHERE request_id=?',
                             (child['request_id'],)).fetchone()
            forged=dict(request_id=child['request_id'],source_revision=row[0],status='READY',
                        writer_text_md='Changed by revision')
            s.db.execute('UPDATE story_memories SET content=? WHERE fighter_id=? AND memory_key=?',
                         ('concurrent edit',*c['key']));s.db.commit()
            assert exchange.deliver(s,forged)['status']=='held'
            assert exchange.projection(s,c)['content']=='concurrent edit'
            assert s.db.execute('SELECT raw_markdown FROM writing_exchange_requests WHERE request_id=?',
                                (original['request_id'],)).fetchone()[0]==TEXT
        finally:s.close()


def test_revision_is_never_automatically_drafted_or_mutates_authored_work():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            original=queue_one(s,c);accepted=exchange.deliver(s,original)
            s.db.execute('UPDATE story_memories SET provenance_class=? WHERE fighter_id=? AND memory_key=?',
                         ('player_authored',*c['key']));s.db.commit()
            try:
                exchange.request_revision(s,original['request_id'],accepted['receipt'])
                raise AssertionError('An authored memory was revised')
            except ValueError:pass
            s.db.execute('UPDATE story_memories SET provenance_class=? WHERE fighter_id=? AND memory_key=?',
                         ('inference',*c['key']));s.db.commit()
            child=exchange.request_revision(s,original['request_id'],accepted['receipt'])
            with patch.object(exchange,'candidates',return_value=[c]):
                with patch('writing_waterfall.plan',return_value=([],{},{})):
                    exchange.prepare(s,client_states=[])
            assert s.db.execute('SELECT state FROM writing_exchange_requests WHERE request_id=?',
                                (child['request_id'],)).fetchone()[0]=='PENDING'
            assert any(p['request']['request_id']==child['request_id'] for p in exchange.outbox(s))
        finally:s.close()


def test_owner_reapproval_of_writer_hold_is_importable_but_other_holds_stay_sealed():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            first=queue_one(s,c)
            exchange.prepare(s,client_states=[dict(request_id=first['request_id'],
                status='HOLD',has_text=True,note='Earlier editorial objection')])
            held=s.db.execute('SELECT state,error FROM writing_exchange_requests WHERE request_id=?',
                              (first['request_id'],)).fetchone()
            assert held['state']=='HOLD' and held['error'].startswith('Writer placed this request on HOLD;')
            result=exchange.deliver(s,first)
            assert result['status']=='imported',result
            assert exchange.projection(s,c)['content']==TEXT
            assert exchange.deliver(s,first)['receipt']==result['receipt']
        finally:s.close()
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s,b,f,m=setup(directory)
        try:
            c=next(c for c in exchange.candidates(s) if c['kind']=='memory')
            first=queue_one(s,c)
            s.db.execute("UPDATE writing_exchange_requests SET state='HOLD',error=? WHERE request_id=?",
                         ('Source changed; do not write or regenerate this request',first['request_id']))
            s.db.commit()
            assert exchange.deliver(s,first)['status']=='held'
            assert exchange.projection(s,c)['content']!=TEXT
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
