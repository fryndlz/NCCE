"""Guideline history, exact changes and honest attribution; no paid calls."""
from test_workshop_optimizer import with_store, body, assessment, writer, opt, ws, patch
import workshop_guidelines as guides


def test_saved_update_and_read_only_history():
    def check(store):
        with patch.object(writer, 'API_KEY', 'mock'):
            state, _ = opt.queue(store, body(store, 1))
            before = state['specific']['instructions']
            reviews = iter([{**assessment(6),'proposed_form_instructions':'Earlier distinct proposal.'},assessment(6)])
            result = opt.execute(store, state['run_id'], generator=lambda *a: {'status':'ready','document':{},'usage':{},'error':''}, reviewer=lambda *a: next(reviews))
        assert result['status']=='awaiting_next_round'
        update = result['prompt_history'][0]
        assert update['change']['edits']
        assert any('I updated the fighter memory guidelines' in d['text'] and 'Added:' in d['text'] for d in result['dialogue'])
        assert any('I proposed changes to' in d['text'] for d in result['dialogue'])
        count = store.db.total_changes
        library = guides.library(store, 'fighter_memory')
        assert store.db.total_changes == count
        assert library['latest']['revision_id']==result['specific']['revision_id']
        assert library['active']['revision_id'] is None
        assert library['latest']['source']['author']=='JKSimmons'
        assert library['latest']['source']['reason']==assessment(6)['summary']
        assert library['latest']['change']==guides.changes(before, result['specific']['instructions'])
        assert all(e['event_id'] and e['time_basis'] for e in library['timeline'])
        times = [e['created_at'] for e in library['timeline'] if e['created_at']]
        assert times == sorted(times, reverse=True)
        assert library['proposals'][0]['entry_number']==1
        assert 'exact review time unavailable' in library['proposals'][0]['time_basis']
        assert len(library['proposals'])==1, 'The first pair proposal remains distinct from the adopted second proposal'
        # Existing audits without new change metadata still reconstruct exact changes.
        del result['prompt_history'][0]['change'];opt.save(store,result)
        assert guides.library(store, 'fighter_memory')['latest']['change']==library['latest']['change']
        spoof = ws.save_revision(store, {'scope':'fighter_memory','instructions':'Different manual guidance','label':'JKSimmons'})
        assert guides.library(store, 'fighter_memory')['latest']['source'] is None, 'Labels cannot prove authorship'
        assert guides.library(store, 'shared')['proposals']==[]
    with_store(check)


def test_proposal_does_not_replace_saved_or_active_instructions():
    def check(store):
        with patch.object(writer, 'API_KEY', 'mock'), patch.object(ws,'now',return_value='2026-10-28T11:00:00+00:00'):
            state, _ = opt.queue(store, body(store, 1))
            result = opt.execute(store, state['run_id'], generator=lambda *a: {'status':'ready','document':{},'usage':{},'error':''}, reviewer=lambda *a: assessment(7,'context'))
        assert result['status']=='escalated' and not result['prompt_history']
        # Use a real recorded review completion time, not the older study start.
        pair = result['rounds'][0]['pairs'][0]
        pair['codex_job_id']='dated-review'
        with store.db:
            store.db.execute("INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,created_at,finished_at) VALUES(?,?,'completed','{}',?,?)",('dated-review',result['run_id'],'2026-10-28T12:00:00+00:00','2026-10-29T12:30:00+00:00'))
        opt.save(store,result)
        count = store.db.total_changes
        library = guides.library(store, 'fighter_memory')
        assert library['timeline'][0]['kind']=='proposal'
        assert library['timeline'][0]['created_at']=='2026-10-29T12:30:00+00:00'
        assert library['timeline'][0]['time_basis']=='Review completed'
        assert library['proposals'][0]['instructions']==assessment()['proposed_form_instructions']
        assert library['latest']['revision_id']==state['specific']['revision_id']
        assert library['active']['revision_id'] is None and store.db.total_changes==count
        try: guides.library(store, 'invalid')
        except ValueError: pass
        else: raise AssertionError('Invalid scope accepted')
    with_store(check)


def test_owner_activation_exact_proposal_idempotency_and_stale_rejection():
    def check(store):
        with patch.object(writer,'API_KEY','mock'):
            state,_=opt.queue(store,body(store,1))
            opt.execute(store,state['run_id'],generator=lambda *a:{'status':'ready','document':{},'usage':{},'error':''},reviewer=lambda *a:assessment(7,'context'))
        before=guides.library(store,'fighter_memory'); proposal=next(e for e in before['timeline'] if e['kind']=='proposal')
        request={'scope':'fighter_memory','event_id':proposal['event_id'],'content_hash':proposal['content_hash'],'expected_active':before['active']['revision_id'],'request_key':'activation-request-0001'}
        count=store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]
        bad={**request,'content_hash':'wrong'}
        try:guides.activate(store,bad)
        except ValueError:pass
        else:raise AssertionError('Stale content accepted')
        assert store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]==count
        after=guides.activate(store,request)
        assert after['active']['instructions']==proposal['instructions']
        assert after['active']['examples']==proposal['examples']
        assert sum(e['is_active'] for e in after['timeline'])==1
        assert next(e for e in after['timeline'] if e['event_id']==proposal['event_id'])['is_active']
        assert proposal['instructions'] in ws.active_contract(store,'fighter_memory')
        assert store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]==count+1
        assert guides.activate(store,request)['active']['revision_id']==after['active']['revision_id']
        assert store.db.execute('SELECT count(*) FROM workshop_revisions').fetchone()[0]==count+1
        saved=next(e for e in after['timeline'] if e['kind']=='saved')
        switch={'scope':'fighter_memory','event_id':saved['event_id'],'content_hash':saved['content_hash'],'expected_active':after['active']['revision_id'],'request_key':'activation-request-0002'}
        final=guides.activate(store,switch)
        assert final['active']['revision_id']==saved['revision_id']
        assert not next(e for e in final['timeline'] if e['event_id']==proposal['event_id'])['is_active']
        stale={**switch,'request_key':'activation-request-0003'}
        try:guides.activate(store,stale)
        except ValueError:pass
        else:raise AssertionError('Stale active pointer accepted')
        assert ws.active(store,'fighter_memory')['revision_id']==saved['revision_id']
    with_store(check)


if __name__=='__main__':
    assert guides.changes('Same\r\ntext','Same\ntext')['edits']==[]
    assert 'reviewed' in guides.announcement('fighter_memory',guides.changes('same','same'))
    assert 'specific NEW ending' in guides.announcement('fighter_memory',guides.changes('Repeated prefix '*80+'old ending','Repeated prefix '*80+'specific NEW ending'))
    for test in [test_saved_update_and_read_only_history,test_proposal_does_not_replace_saved_or_active_instructions,test_owner_activation_exact_proposal_idempotency_and_stale_rejection]:
        test();print('PASS',test.__name__)
