"""Editorial memory refreshes new studies, never inspected/validation requests."""
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
import writer_planning as planning
import writer_workshop as ws
import llm_writer as writer
import workshop_optimizer as opt
import codex_review_queue as cq
from test_workshop_optimizer import with_store, body, assessment, fake_call
from test_story_engine import mechanical_records


def add_trial(store, tid, form='territory_origin', subject='Palanite Precinct', text=None):
    text = text or 'Sella keeps a cup aside for her sister, the desk clerk. She directs witnesses to the right window.'
    doc = {'blocks':[{'type':'body_paragraph','text':text}],
           'composition':{'body_heading':tid,'closing':'Queue volume is excluded from official returns.'}}
    store.db.execute('''INSERT INTO workshop_trials(trial_id,request_key,sample_key,form,label,packet_json,
        instructions,model,effort,status,document_json,created_at)
        VALUES(?,?,?,?,?,?,'Saved owner brief','mock','medium','ready',?,'2026-10-28T00:00:00Z')''',
        (tid,tid,'source:'+tid,form,subject,json.dumps({'subject':subject}),json.dumps(doc)))
    return doc


def add_review(store, jid, form='territory_origin', run='older-study'):
    value = {'candidates':[{'issues':[
        {'category':'writing','title':'Vary the unofficial-favor ending','evidence':'A cup is not in the inventory.'},
        {'category':'context','title':'Unverified diagnosis must not become advice','evidence':'Unknown'}]}],
        'proposed_form_instructions':'DO NOT PROMOTE THIS BRIEF'}
    store.db.execute('''INSERT INTO codex_review_jobs(job_id,run_id,status,payload_json,result_json,created_at,finished_at)
        VALUES(?,?,'completed',?,?,'2026-10-28','2026-10-28')''',
        (jid,run,json.dumps({'form':form}),json.dumps(value)))


def test_fresh_snapshot_sees_same_subject_trials_and_reviews_but_pinned_plan_stays_frozen():
    def check(store):
        before = mechanical_records(store)
        packet = {'subject':'Palanite Precinct','subject_context':{'authored_context':'Accepted identity','earlier_stories':['Accepted history']}}
        empty = planning.editorial_snapshot(store,'territory_origin')
        original = planning.prepare(store,'territory_origin',packet,'same-source',editorial=empty)
        add_trial(store,'earlier'); add_review(store,'review-earlier')
        add_review(store,'broken-review');store.db.execute("UPDATE codex_review_jobs SET result_json='{' WHERE job_id='broken-review'")
        add_review(store,'current-review',run='excluded-study')
        add_trial(store,'wrong-form',form='fighter_memory'); add_review(store,'review-wrong',form='fighter_memory')
        snapshot = planning.editorial_snapshot(store,'territory_origin','excluded-study')
        assert len(snapshot['attempts']) == 1
        assert snapshot['attempts'][0]['subject'] == packet['subject']
        assert 'refreshment_based_favor' in snapshot['attempts'][0]['devices']
        assert 'queue_assistance' in snapshot['attempts'][0]['devices']
        assert 'official_exclusion' in snapshot['attempts'][0]['ending_devices']
        assert len(snapshot['lessons']) == 1 and snapshot['lessons'][0]['source']=='review:review-earlier'
        assert 'DO NOT PROMOTE' not in json.dumps(snapshot) and 'Unverified diagnosis' not in json.dumps(snapshot)
        assert 'Sella keeps' not in json.dumps(snapshot)
        current = planning.prepare(store,'territory_origin',packet,'same-source',editorial=snapshot)
        assert current['creative_plan']['plan_key'] != original['creative_plan']['plan_key']
        assert current['subject_context'] == packet['subject_context']
        assert 'NOT accepted history' in current['creative_plan']['editorial_memory_boundary']
        assert planning.prepare(store,'territory_origin',packet,'same-source',plan_key=original['creative_plan']['plan_key'],editorial=snapshot)==original
        assert planning.prepare(store,'territory_origin',packet,'same-source',editorial=empty)==original
        assert ws.active_contract(store,'territory_origin') is None and mechanical_records(store)==before
    with_store(check)


def test_exact_category_selection_precedes_limits_and_snapshot_is_bounded_and_tolerates_legacy_rows():
    def check(store):
        add_trial(store,'relevant'); add_review(store,'relevant-review')
        # More unrelated history than either old global SQL cap.
        for n in range(90):
            add_trial(store,'unrelated-'+str(n),form='fighter_memory')
            planning.remember(store,'unrelated-'+str(n),'fighter_memory',{'subject':'Elsewhere'},['Unrelated'],{})
        store.db.execute('''INSERT INTO writer_creative_footprints VALUES('broken','territory_origin','x','{','2026-10-29')''')
        store.db.execute('''INSERT INTO writer_creative_footprints VALUES('legacy','territory_origin','x',?,'2026-10-29')''',
                         (json.dumps({'names':None,'devices':42}),))
        for n in range(20):
            planning.remember(store,'large-'+str(n),'territory_origin',{'subject':'X'*300},['Trade and weighing.'],{'body_heading':'H'*100})
        snapshot=planning.editorial_snapshot(store,'territory_origin')
        assert len(snapshot['attempts']) <= planning.WINDOW
        assert len(planning.packed(snapshot)) < 6150
        assert snapshot['lessons'][0]['source']=='review:relevant-review'
        assert 'unrelated-' not in json.dumps(snapshot)
        # A separate snapshot with no crowded same-form history must see the trial.
        store.db.execute("DELETE FROM writer_creative_footprints WHERE fingerprint LIKE 'large-%'")
        assert any(x['source']=='trial:relevant' for x in planning.editorial_snapshot(store,'territory_origin')['attempts'])
    with_store(check)


def test_one_response_footprint_and_trial_count_once_with_saved_request_provenance():
    def check(store):
        doc=add_trial(store,'same-response')
        planning.remember(store,'signature','territory_origin',{'subject':'Palanite Precinct'},['Old extractor output'],{})
        cursor=store.db.execute('''INSERT INTO writer_requests(run_id,form,subject_type,subject_key,model,
            requested_at,finished_at,status) VALUES('same-response','territory_origin','writer_workshop','same-response','mock','2026-10-28','2026-10-28','succeeded')''')
        store.db.execute('''INSERT INTO writer_request_details(request_row_id,prompt_hash,contract_revision,reasoning_effort,prompt_json,response_json,draft_json)
            VALUES(?,'signature','old','medium','{}','{}','{}')''',(cursor.lastrowid,))
        snapshot=planning.editorial_snapshot(store,'territory_origin')
        assert len(snapshot['attempts'])==1
        assert snapshot['attempts'][0]['source']=='trial:same-response'
        assert 'refreshment_based_favor' in snapshot['attempts'][0]['devices']
    with_store(check)


def test_mechanisms_warn_about_relationships_not_incidental_objects():
    assert 'refreshment_based_favor' in planning.mechanisms('The clerk keeps a cup aside for her sister.')
    assert 'refreshment_based_favor' not in planning.mechanisms('Tea is stored in a warehouse. A cup is cracked.')
    assert 'official_exclusion' in planning.mechanisms('Broth sales are not included in the published provision.')
    assert 'official_exclusion' not in planning.mechanisms('The official counted the cups and signed the inventory.')
    assert planning.mechanisms('Vendors sell tea. People walk through the square.')==[]


def test_new_studies_refresh_learning_and_freeze_validation_in_actual_writer_and_reviewer_packets():
    def check(store):
        original_request=body(store,1)
        shared=ws.save_revision(store,{**ws.defaults('shared'),'instructions':'Owner selected craft.', 'examples':'Owner selected shared example.'})
        specific=ws.save_revision(store,{**ws.defaults('fighter_memory'),'instructions':'EVENT. First person, 40–100 words. No institutional heading.', 'examples':'Owner selected personal example.'})
        original_request.update(shared_revision_id=shared['revision_id'],form_revision_id=specific['revision_id'])
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=fake_call) as provider:
            state,_=opt.queue(store,original_request)
            rid=state['run_id']; initial=copy.deepcopy(state['editorial_snapshot'])
            first=opt.execute(store,rid,reviewer=lambda *args:assessment(7))
            frozen=copy.deepcopy(first['rounds'][0]['pairs'])
            assert all('EVENT. First person, 40–100 words.' in p['instructions'] for p in frozen)
            add_trial(store,'new-learning-history',form='fighter_memory',subject='Mara')
            add_review(store,'new-learning-review',form='fighter_memory')
            decision={'run_id':rid,'request_key':'new-learning-grant-0001','additional_rounds':1,'allow_paid':True}
            opt.continue_run(store,decision)
            second=opt.execute(store,rid,reviewer=lambda *args:assessment(9))
            learning=copy.deepcopy(second['editorial_snapshot'])
            assert learning != initial and second['validation_pending']
            assert second['rounds'][0]['pairs']==frozen
            add_trial(store,'heldout-must-not-teach',form='fighter_memory')
            add_review(store,'heldout-review',form='fighter_memory')
            opt.continue_run(store,{**decision,'request_key':'validation-grant-0001'})
            with patch.object(planning,'editorial_snapshot',side_effect=AssertionError('Validation refreshed lessons')), \
                 patch.object(planning,'recent',side_effect=AssertionError('Validation read live repetition history')):
                final=opt.execute(store,rid,reviewer=lambda *args:assessment(9))
            assert final['status']=='awaiting_approval' and final['editorial_snapshot']==learning
            assert provider.call_count==12, (provider.call_count,final['writer_reserved'])
            assert ws.active_contract(store,'fighter_memory') is None
            for r in final['rounds'][1:]:
                for pair in r['pairs']:
                    memory=pair['packet']['creative_plan']['editorial_memory']
                    assert memory==learning and 'heldout-review' not in json.dumps(memory)
                    audits=store.db.execute('''SELECT d.prompt_json FROM writer_requests r JOIN writer_request_details d USING(request_row_id)
                        WHERE r.run_id IN (?,?)''',tuple(c['trial_id'] for c in pair['candidates'])).fetchall()
                    assert len(audits)==2
                    for a in audits:
                        sent=json.loads(a[0]); delivered=json.loads(sent['input'])
                        assert delivered['creative_plan']['editorial_memory']==learning
                        assert sent['instructions']==pair['instructions']
                        assert 'Owner selected craft.' in sent['instructions'] and 'Owner selected shared example.' in sent['instructions']
                        assert sent['instructions']==ws.compose('fighter_memory',shared,ws.revision(store,r['revision_id']))
                        assert 'First person, 40–100 words.' in sent['instructions'] and 'Owner selected personal example.' in sent['instructions']
                    # Both writer outputs and the exact saved packet go to Codex.
                    jid=cq.enqueue(store,final,pair,[],opt.review_schema(),'rubric')
                    queued=json.loads(cq.get(store,jid)['payload_json'])
                    assert queued['packet']['creative_plan']['editorial_memory']==learning
            # A new request sees the latest records; duplicate launch reuses its saved snapshot.
            request={**original_request,'request_key':'fresh-study-request-0001'}
            new,_=opt.queue(store,request)
            assert new['editorial_snapshot']!=learning
            before=copy.deepcopy(new)
            add_review(store,'even-newer-review',form='fighter_memory')
            assert opt.queue(store,request)==(before,False)
            assert provider.call_count==12
    with_store(check)


def test_territory_brief_examples_and_authority_are_unchanged_by_editorial_context():
    def check(store):
        shared=ws.save_revision(store,ws.defaults('shared'))
        specific=ws.save_revision(store,{**ws.defaults('territory_origin'),
            'instructions':'BASELINE. Imperial clerk. One paragraph, 70–100 words. Return all seven fields.',
            'examples':'Style only. Never transplant the example facts.'})
        expected=ws.compose('territory_origin',shared,specific)
        sample={'key':'territory-fixture','form':'territory_origin','packet':{'subject':'Palanite Precinct','evidence':['Recorded type: Palanite Precinct']}}
        with patch.object(ws,'sample',return_value=copy.deepcopy(sample)):
            prepared=ws.preview(store,{'sample_key':sample['key'],'shared_revision_id':shared['revision_id'],
                'form_revision_id':specific['revision_id']},editorial=planning.editorial_snapshot(store,'territory_origin'))
        assert prepared['instructions']==expected
        assert '70–100 words' in expected and 'seven fields' in expected and 'Imperial clerk' in expected
        assert 'Style only. Never transplant' in expected and 'Player-authored and canon-authored' in expected
        assert prepared['packet']['rulebook_context']['status']=='unverified'
        assert ws.revision(store,specific['revision_id'])['instructions']==specific['instructions']
    with_store(check)


def test_starting_with_an_inspected_legacy_plan_preserves_it_and_freezes_future_validation():
    def check(store):
        request=body(store,1)
        inspected=ws.preview(store,request)
        add_trial(store,'new-after-inspection',form='fighter_memory')
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',side_effect=AssertionError('Queue spent calls')):
            state,_=opt.queue(store,{**request,'plan_key':inspected['plan_key']})
        assert state['samples'][0]['packet']==inspected['packet']
        assert state['editorial_snapshot']['attempts']
        # Even a legacy inspected plan must not trigger live history reads in validation.
        state['rounds']=[{'pairs':[{'sample_key':p['key'],'packet_hash':p['packet_hash']} for p in state['samples']]}]
        state['validation_pending']=True
        with patch.object(planning,'editorial_snapshot',side_effect=AssertionError('Refreshed validation')), \
             patch.object(planning,'recent',side_effect=AssertionError('Read live history')):
            opt.round_samples(store,state)
    with_store(check)


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
