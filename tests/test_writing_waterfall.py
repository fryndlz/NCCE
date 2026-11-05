"""Meaningful replacement/DAG/claim tests against disposable campaign state."""
from copy import deepcopy
import json
from pathlib import Path
import sys,tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writing_exchange import setup
from writing_exchange import import_delivery as pilot_import,packed
from story_engine import regenerate,read_memories
import exchange_automation as e
import writing_waterfall as w


def deliver_outbox(s):
    results=[]
    for p in e.outbox(s):
        q=p['request'];text='Accepted '+q['form']+' for '+q['title']+'.'
        result=e.deliver(s,dict(request_id=q['request_id'],status='READY',source_revision=q['source_revision'],writer_text_md=text))
        assert result['status']=='imported',result
        results.append(q['request_id'])
    return results


def test_legacy_ready_baselines_are_archived_and_queued_once_authored_and_accepted_protected():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            pilot_import(s,b)
            row=s.db.execute("SELECT * FROM story_artifacts WHERE scope_type='territory_origin' AND active=1").fetchone()
            doc=json.loads(row['document_json']);doc.update(writer_status='ready',blocks=[{'type':'body_paragraph','text':'Old machine placeholder prose.'}])
            s.db.execute('UPDATE story_artifacts SET document_json=? WHERE artifact_id=?',(packed(doc),row['artifact_id']));s.db.commit()
            e.prepare(s)
            packets=e.outbox(s);assert packets and all(p['request']['form'] in ('territory_origin','fighter_biography') for p in packets)
            old=json.loads(s.db.execute('SELECT projection_json FROM writing_legacy_inventory').fetchone()[0])
            assert 'Old machine placeholder prose.' in old['document_json']
            assert not any(p['request']['form']=='fighter_biography' and p['request']['entity_key']==str(f) for p in packets)
            assert all(m['content']==b['writer_text_md'] for m in read_memories(s,f) if m['memory_key']==b['target_binding']['memory_key'])
            deliver_outbox(s);e.prepare(s)
            assert not any(p['request']['form'] in ('territory_origin','fighter_biography') for p in e.outbox(s))
        finally:s.close()


def test_event_waits_for_baseline_and_receives_accepted_text_not_legacy_seed():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            e.prepare(s);origins={p['request']['entry_key'] for p in e.outbox(s)}
            assert origins
            deliver_outbox(s);e.prepare(s)
            cs=e.candidates(s);lookup={e.target_key(c):c for c in cs}
            for p in e.outbox(s):
                assert w.FORM_PHASE[p['request']['form']]==1
                for block in p['context']:
                    if block['section']=='existing_fiction':
                        refs=json.loads(block['text'])
                        assert all(lookup[r['target_key']]['approved'] for r in refs)
                        assert all(r['text'].startswith('Accepted ') for r in refs)
            assert len(e.outbox(s))<=5
        finally:s.close()


def test_unclaimed_old_battles_deferred_same_ids_while_started_drafts_can_finish():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            cs=e.candidates(s);battle=next(c for c in cs if c['form']=='battle_report');key=e.target_key(battle)
            rid='e0ae33da-4a96-48de-ad09-ff03a2bb6176';packet=e._packet(s,battle,rid)
            s.db.execute("INSERT INTO writing_exchange_requests(request_id,target_key,packet_json,target_json,source_revision,state,created_at) VALUES(?,?,?,?,?,'PENDING','before')",
                         (rid,key,packed(packet),packed({'target':battle,'original':e.projection(s,battle)}),e.seal(battle)))
            s.db.commit()
            e.prepare(s,client_states=[dict(request_id=rid,status='PENDING',has_text=False)])
            assert s.db.execute('SELECT state FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone()[0]=='DEFERRED'
            assert any(d['request_id']==rid for d in e.deferred(s))
            assert all(p['request']['form']!='battle_report' for p in e.outbox(s))
            # A writer that claimed at the exact deferral boundary can still
            # publish the one saved draft against its unchanged original facts.
            result=e.deliver(s,dict(request_id=rid,source_revision=e.seal(battle),status='READY',writer_text_md='Saved once; never discarded.'))
            assert result['status']=='imported',result
            assert e.projection(s,battle)['document_json'].find('Saved once; never discarded.')>=0
        finally:s.close()


def test_claims_and_partial_output_are_never_withdrawn():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            c=next(c for c in e.candidates(s) if c['form']=='battle_report')
            from test_exchange_automation import queue_one
            delivery=queue_one(s,c);rid=delivery['request_id']
            e.prepare(s,client_states=[dict(request_id=rid,status='WRITING',has_text=False)])
            assert s.db.execute('SELECT state FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone()[0]=='PENDING'
            assert any(p['request']['request_id']==rid for p in e.outbox(s))
            assert len(e.outbox(s))<=5
        finally:s.close()


def test_reflection_and_mind_have_explicit_cause_dependencies_and_legacy_context_is_scrubbed():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            cs=e.candidates(s);ready,deps,blocked=w.plan(s,cs)
            for c in cs:
                if c['form'] in ('fighter_reflection','fighter_mind'):
                    assert deps[e.target_key(c)] or e.target_key(c) in blocked
                    assert c not in ready
            assert w.scrub({'baseline':'old wording','identity':{'lineage':'human'},'nested':{'related_observations':['machine babble']}})=={'identity':{'lineage':'human'},'nested':{}}
            assert not __import__('narrative_context').usable({'writer_status':'ready','writer_revision':__import__('writer_contract').REVISION})
        finally:s.close()


def test_waterfall_drains_without_rewriting_accepted_entries_or_changing_event_clock():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
        s,b,f,m=setup(temp)
        try:
            from fighter_event_clock import build
            before=build(read_memories(s,f),s,f);seen=set();phases=[]
            for turn in range(100):
                e.prepare(s);packets=e.outbox(s)
                if not packets:break
                phases.extend(w.FORM_PHASE[p['request']['form']] for p in packets)
                ids=deliver_outbox(s);assert not seen.intersection(ids);seen.update(ids)
            else:raise AssertionError('Waterfall failed to drain')
            assert len(seen)>10 and phases==sorted(phases),phases
            assert build(read_memories(s,f),s,f)==before
            count=len(seen)
            regenerate(s,force=True,writer_enabled=False);e.restore(s);e.prepare(s)
            assert not e.outbox(s),[(p['request']['form'],p['request']['title']) for p in e.outbox(s)]
            assert s.db.execute("SELECT count(*) FROM writing_exchange_requests WHERE state='IMPORTED'").fetchone()[0]==count
        finally:s.close()


if __name__=='__main__':
    for name,check in list(globals().items()):
        if name.startswith('test_') and callable(check):check();print('PASS',name)
