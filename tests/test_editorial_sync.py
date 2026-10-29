"""Post-study learning: event-driven, durable, bounded and automatically activates completed updates."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'scripts')]
import editorial_sync as sync
import editorial_quality as q
import workshop_optimizer as opt
import workshop_experiments as exp
import writer_workshop as ws
import llm_writer as writer
import codex_review_queue as cq
from test_writer_pipeline import with_store
from test_workshop_optimizer import ready_bridge,rejects
from test_editorial_quality import request,review,fake_generator,vote


def update(instructions='Use the subject as the centre. Keep endings useful or empty.'):
    return {'summary':'I tightened subject focus and removed forced administrative endings.',
        'changes':['Territory role now comes first.','Empty closings are permitted.'],
        'owner_corrections':['Keep the requested place central.'],
        'reviewer_inferences':['Test whether a shorter opening improves clarity.'],
        'reviewer_standards':'Owner requirement: retain the subject. Reviewer hypothesis: try a shorter opening.',
        'proposed_form_instructions':instructions}


def setup(store,fn):
    with patch.dict(os.environ,{'NCCE_REVIEW_BRIDGE_TOKEN_SHA256':hashlib.sha256(('test-bridge-token-'*4).encode()).hexdigest()}),patch.object(writer,'API_KEY','mock'):
        ready_bridge(store);fn(store)


def judged(store):
    state,_=opt.queue(store,request(store,1,key=uuid.uuid4().hex))
    state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p,True))
    vote(store,state,0)
    assert 'feedback_sync' not in opt.get(store,state['run_id'])
    vote(store,state,1)
    return opt.get(store,state['run_id'])


def finish_learning(store,state,result=None):
    identity={'thread_id':cq.thread_id(),'worker_id':'learning-native-worker','job_id':state['feedback_sync']['job_id']}
    claimed=cq.claim(store,identity);assert claimed['job']['kind']==sync.KIND
    lease={**identity,'lease':claimed['lease'],'turn_id':'real-learning-native-turn'}
    cq.started(store,lease)
    response=cq.complete(store,{**lease,'review':result or update()})
    return claimed['job'],lease,response


def test_last_verdict_queues_once_and_completion_saves_candidate_memory_and_changes():
    def check(store):
        state=judged(store);job=state['feedback_sync']['job_id'];frozen=copy.deepcopy(state['rounds'])
        assert state['feedback_sync']['status']=='queued'
        assert sync.maybe_queue(store,state['run_id'])['feedback_sync']['job_id']==job
        vote(store,state,1)
        assert store.db.execute("SELECT count(*) FROM codex_review_jobs WHERE json_extract(payload_json,'$.kind')=?",(sync.KIND,)).fetchone()[0]==1
        reservations=[state[k] for k in ('writer_reserved','writer_limit','reviewer_reserved','reviewer_limit')]
        rejects(lambda:exp.checkpoint(store,{'run_id':state['run_id']}))
        payload,lease,response=finish_learning(store,state)
        done=opt.get(store,state['run_id']);memory=sync.standards(store,state['form'])
        assert len(payload['feedback'])==2 and all(x['owner_verdict'] for x in payload['feedback'])
        assert done['feedback_sync']['status']=='completed' and done['rounds']==frozen
        assert [done[k] for k in ('writer_reserved','writer_limit','reviewer_reserved','reviewer_limit')]==reservations
        assert ws.active(store,state['form'])['revision_id']==memory['candidate_revision_id'] and ws.active(store,'shared') is None
        assert update()['proposed_form_instructions'] in ws.active_contract(store,state['form'])
        assert done['expected_active'][state['form']]==memory['candidate_revision_id']
        assert done['specific']['revision_id']==state['specific']['revision_id'],'historically tested pair is immutable'
        assert ws.revision(store,memory['candidate_revision_id'])['instructions']==update()['proposed_form_instructions']
        assert q.home(store,state['form'])['suggested_instructions']==update()['proposed_form_instructions']
        assert cq.complete(store,{**lease,'review':update()})==response
        assert response['standards_export']['reviewer_standards']==update()['reviewer_standards']
        exp.checkpoint(store,{'run_id':state['run_id']})
        assert opt.get(store,state['run_id'])['specific']['revision_id']==memory['candidate_revision_id']
        assert not opt.get(store,state['run_id'])['validation_pending']
        from workshop_guidelines import library
        assert next(x for x in library(store,state['form'])['history'] if x['revision_id']==memory['candidate_revision_id'])['source']['kind']=='feedback_consolidation'
    with_store(lambda s:setup(s,check))


def test_failure_and_restart_never_replay_a_learning_job():
    def check(store):
        state=judged(store);job=state['feedback_sync']['job_id']
        opt.recover(store)
        stopped=opt.get(store,state['run_id'])
        assert stopped['feedback_sync']['status']=='cancelled' and cq.get(store,job)['status']=='cancelled'
        assert sync.maybe_queue(store,state['run_id'])['feedback_sync']['job_id']==job
        rejects(lambda:exp.checkpoint(store,{'run_id':state['run_id']}))
        assert sync.standards(store,state['form']) is None
    with_store(lambda s:setup(s,check))


def test_latest_completed_update_activates_without_touching_other_scopes_or_replaying():
    def check(store):
        untouched=ws.save_revision(store,{'scope':'shared','instructions':'Keep shared craft.'})
        ws.activate(store,{'scope':'shared','revision_id':untouched['revision_id']})
        other=ws.save_revision(store,{'scope':'fighter_biography','instructions':'Keep biography guidance.'})
        ws.activate(store,{'scope':'fighter_biography','revision_id':other['revision_id']})
        first=judged(store);finish_learning(store,first)
        second=judged(store);frozen=copy.deepcopy(second['rounds'])
        _,lease,_=finish_learning(store,second,update('Newest completed category guidance.'))
        rid=sync.standards(store,second['form'])['candidate_revision_id']
        assert ws.active(store,second['form'])['revision_id']==rid
        assert ws.active(store,'shared')==untouched and ws.active(store,'fighter_biography')==other
        assert opt.get(store,second['run_id'])['rounds']==frozen
        # Later manual rollback must survive retries/startup.
        rollback=ws.save_revision(store,{'scope':second['form'],'instructions':'Owner rollback.'})
        ws.activate(store,{'scope':second['form'],'revision_id':rollback['revision_id'],'expected_active':rid})
        cq.complete(store,{**lease,'review':update('Newest completed category guidance.')})
        sync.reconcile_active_guidelines(store);sync.reconcile_active_guidelines(store)
        assert ws.active(store,second['form'])==rollback
    with_store(lambda s:setup(s,check))


def test_upgrade_activates_existing_latest_feedback_once_and_preserves_audit():
    def check(store):
        state=judged(store);finish_learning(store,state)
        saved=sync.standards(store,state['form']);rid=saved['candidate_revision_id']
        # Model a pre-upgrade database: completed standards exist, pointer was never advanced.
        with store.db:
            store.db.execute('DELETE FROM workshop_active WHERE scope=?',(state['form'],))
            store.db.execute('DELETE FROM system_state WHERE key=?',('guideline-auto-activation:'+saved['revision_id'],))
        frozen=copy.deepcopy(opt.get(store,state['run_id'])['rounds'])
        sync.reconcile_active_guidelines(store)
        assert ws.active(store,state['form'])['revision_id']==rid
        audit=json.loads(store.get_state('guideline-auto-activation:'+saved['revision_id']))
        assert audit['previous_active'] is None and audit['reason']=='existing_completed_feedback'
        assert opt.get(store,state['run_id'])['rounds']==frozen
        assert ws.active(store,'shared') is None
        sync.reconcile_active_guidelines(store)
        assert json.loads(store.get_state('guideline-auto-activation:'+saved['revision_id']))==audit
    with_store(lambda s:setup(s,check))


def test_activation_failure_rolls_back_candidate_memory_audit_and_job_completion():
    def check(store):
        import sqlite3
        state=judged(store)
        before=store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]
        with store.db:
            store.db.execute("CREATE TRIGGER reject_activation BEFORE INSERT ON workshop_active BEGIN SELECT RAISE(ABORT,'test activation failure'); END")
        try:finish_learning(store,state)
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('Activation failure must abort the complete transaction')
        assert sync.standards(store,state['form']) is None
        assert ws.active(store,state['form']) is None
        assert store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]==before
        assert opt.get(store,state['run_id'])['feedback_sync']['status']=='reviewing'
        assert cq.get(store,state['feedback_sync']['job_id'])['status']=='reviewing'
        assert not store.get_state('guideline-auto-activation:'+state['feedback_sync']['job_id'])
    with_store(lambda s:setup(s,check))


def test_finished_study_still_learns_once_after_its_last_rating():
    def check(store):
        state,_=opt.queue(store,request(store,1,key=uuid.uuid4().hex))
        state=opt.execute(store,state['run_id'],generator=fake_generator,reviewer=lambda s,t,p,h:review(p,True))
        opt.finish_run(store,{'run_id':state['run_id']})
        vote(store,state,0);vote(store,state,1)
        done=opt.get(store,state['run_id'])
        assert done['status']=='finished' and done['feedback_sync']['status']=='queued'
        assert opt.finish_run(store,{'run_id':state['run_id']})['feedback_sync']['job_id']==done['feedback_sync']['job_id']
    with_store(lambda s:setup(s,check))


def test_invalid_learning_result_and_changed_base_cannot_update_standards():
    def check(store):
        state=judged(store)
        identity={'thread_id':cq.thread_id(),'worker_id':'learning-native-worker','job_id':state['feedback_sync']['job_id']}
        claim=cq.claim(store,identity);lease={**identity,'lease':claim['lease'],'turn_id':'failed-learning-turn'}
        cq.started(store,lease)
        bad=update();bad['reviewer_standards']=''
        rejects(lambda:cq.complete(store,{**lease,'review':bad}))
        assert sync.standards(store,state['form']) is None
        store.set_state('reviewer-standards:'+state['form'],json.dumps({'revision_id':'changed-elsewhere'}))
        rejects(lambda:cq.complete(store,{**lease,'review':update()}))
        assert sync.standards(store,state['form'])['revision_id']=='changed-elsewhere'
        cq.fail(store,{**lease,'error':'Standards changed while this update was running.'})
        assert opt.get(store,state['run_id'])['feedback_sync']['status']=='failed'
        assert sync.maybe_queue(store,state['run_id'])['feedback_sync']['job_id']==identity['job_id']
    with_store(lambda s:setup(s,check))


def test_confirmed_standards_are_mirrored_locally_without_another_model():
    from codex_chat_worker import ChatWorker
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        worker=object.__new__(ChatWorker);worker.active=Path(folder)/'active.json'
        worker.client=SimpleNamespace(config={'context_dir':str(Path(folder)/'notes')})
        worker.save({'status':'reviewing','job_id':'learn-test','lease':'private','turn_id':'native'})
        export={'form':'territory_origin','revision_id':'learn-test','at':'2026-10-29','summary':'Updated',
            'reviewer_standards':'Concrete subject first.','owner_corrections':['Keep the territory central.'],'reviewer_inferences':['Try a shorter start.']}
        calls=[]
        worker.post=lambda action,body:(calls.append(action) or ({'ok':True,'standards_export':export} if action=='complete' else {}))
        worker.finish(review=update())
        text=(Path(folder)/'notes/workshop-standards-territory_origin.md').read_text(encoding='utf-8')
        assert 'Concrete subject first.' in text and 'Reviewer interpretations (not owner instructions)' in text
        assert calls==['complete','heartbeat']
        assert json.loads(worker.active.read_text())['status']=='completed'


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
