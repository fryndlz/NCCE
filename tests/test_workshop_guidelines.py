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
        with patch.object(writer, 'API_KEY', 'mock'):
            state, _ = opt.queue(store, body(store, 1))
            result = opt.execute(store, state['run_id'], generator=lambda *a: {'status':'ready','document':{},'usage':{},'error':''}, reviewer=lambda *a: assessment(7,'context'))
        assert result['status']=='escalated' and not result['prompt_history']
        count = store.db.total_changes
        library = guides.library(store, 'fighter_memory')
        assert library['proposals'][0]['instructions']==assessment()['proposed_form_instructions']
        assert library['latest']['revision_id']==state['specific']['revision_id']
        assert library['active']['revision_id'] is None and store.db.total_changes==count
        try: guides.library(store, 'invalid')
        except ValueError: pass
        else: raise AssertionError('Invalid scope accepted')
    with_store(check)


if __name__=='__main__':
    assert guides.changes('Same\r\ntext','Same\ntext')['edits']==[]
    assert 'reviewed' in guides.announcement('fighter_memory',guides.changes('same','same'))
    assert 'specific NEW ending' in guides.announcement('fighter_memory',guides.changes('Repeated prefix '*80+'old ending','Repeated prefix '*80+'specific NEW ending'))
    for test in [test_saved_update_and_read_only_history,test_proposal_does_not_replace_saved_or_active_instructions]:
        test();print('PASS',test.__name__)
