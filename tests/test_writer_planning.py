"""Reference grounding, repetition, stable plans and one-call provenance. Offline."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
import writer_planning as planning
import territory_reference as reference
import writer_workshop as workshop
import writer_contract
import llm_writer as writer
from test_writer_pipeline import with_store,draft
from test_writer_workshop import seed
from test_story_engine import mechanical_records


def test_verified_reference_cards_and_unknown_types():
    assert len(reference.CARDS)==26
    for card in reference.CARDS.values():
        assert 173<=card['source']['printed_page']<=181
        assert card['source']['pdf_page']==card['source']['printed_page']+1
        assert card['source']['edition']=='2023' and card['function'] and card['rule_significance']
    needle=reference.lookup('Needle Ways')
    assert 'concealed' in needle['function'] and needle['enhanced_boon_house']=='Delaque'
    assert 'captives' in reference.lookup('Mine Workings')['rule_significance']
    assert reference.lookup('Mine Works')==reference.lookup('Mine Workings')
    assert reference.lookup('Archaeotech')==reference.lookup('Archaeotech Device')
    assert reference.lookup('The Needle Works') is None
    assert reference.for_packet('territory_origin',{'subject':'Something unknown'})['status']=='unverified'
    assert reference.for_packet('fighter_memory',{'subject':'Needle Ways'}) is None


def test_historical_type_beats_subject_and_incidental_prose():
    packet={'subject':'Settlement','writer_context':{'state_at_event':{'name':'Bone Shrine'}}}
    card=reference.for_packet('place_event',packet)
    assert card['type']=='Bone Shrine' and 'not recorded campaign occurrences' in card['boundary']
    assert reference.for_packet('territory_origin',{'subject':'A shrine','evidence':['Recorded type at first description: Bone Shrine']})['type']=='Bone Shrine'
    assert reference.for_packet('territory_origin',{'subject':'Unknown','evidence':['A report mentions Bone Shrine']})['status']=='unverified'
    packet['writer_context']['territory_type']='Needle Ways'
    assert reference.for_packet('place_event',packet)['status']=='unverified'


def test_legacy_trial_repetition_is_avoidance_not_continuity_or_policy():
    def check(store):
        source=seed(store); before=mechanical_records(store)
        doc={'blocks':[{'type':'body_paragraph','text':'One family keeps weights across generations. Crews settle disputes at the tally board.'}],
             'composition':{'body_heading':'The Grey Mirror','closing':'Custom is admissible; title is outside this office’s remit.'}}
        with store.db:
            store.db.execute('''INSERT INTO workshop_trials(trial_id,request_key,sample_key,form,label,packet_json,instructions,model,effort,status,document_json,created_at)
                VALUES('old','old-request-key','old-source','territory_origin','Old draft',?,'Owner instructions','mock','medium','ready',?,'2026-10-26T00:00:00Z')''',
                (json.dumps({'subject':'Sludge Sea'}),json.dumps(doc)))
        planned=planning.prepare(store,'territory_origin',{'subject':'Mine Workings'})
        hints=planned['creative_plan']['recent_patterns']
        assert hints['devices']['customary_accounting']==1 and hints['ending_devices']['legal_recognition']==1
        assert hints['names']==['The Grey Mirror']
        assert 'One family' not in json.dumps(planned)
        assert 'NOT world history' in planned['creative_plan']['recent_patterns_boundary']
        assert planned['rulebook_context']['type']=='Mine Workings'
        assert len(json.dumps(hints))<3000
        assert mechanical_records(store)==before and workshop.active_contract(store,'territory_origin') is None
    with_store(check)


def test_frozen_plan_survives_history_changes_and_database_reopen():
    def check(store):
        packet={'subject':'Needle Ways','subject_context':{'baseline':'Authored continuity'}}
        original=planning.prepare(store,'territory_origin',packet,'source')
        key=original['creative_plan']['plan_key']
        planning.remember(store,'different','territory_origin',{'subject':'Elsewhere','creative_plan':{'focus':'economic'}},['Trade and weighing fees.'],{})
        assert planning.prepare(store,'territory_origin',packet,'source')==original
        assert planning.prepare(store,'territory_origin',packet,'source',plan_key=key)==original
        store.db.commit()
        with store.reader() as reader:
            assert planning.prepare(reader,'territory_origin',packet,'source',plan_key=key)==original
        try: planning.prepare(store,'territory_origin',{'subject':'Changed'},'source',plan_key=key)
        except ValueError: pass
        else: raise AssertionError('A saved plan accepted different source evidence')
        pinned=planning.prepare(store,'territory_origin',packet,'source',focus='religious')
        assert pinned['creative_plan']['focus']=='religious' and pinned['creative_plan']['selection']=='owner pinned'
        assert pinned['subject_context']==packet['subject_context']
    with_store(check)


def test_least_used_selection_and_event_boundaries_across_every_form():
    def check(store):
        with store.db:
            for focus in planning.FOCUSES:
                if focus!='historical':
                    planning.remember(store,focus,'territory_origin',{'subject':focus,'creative_plan':{'focus':focus}},['A place.'],{})
        plan=planning.prepare(store,'territory_origin',{'subject':'Mine Workings'})['creative_plan']
        assert plan['focus']=='historical'
        for form in writer_contract.BRIEFS:
            p=planning.prepare(store,form,{'subject':'Test','event':{'event_id':'a','payload':{'after':'Recovery'}}})
            assert p['event']['payload']['after']=='Recovery'
            if form not in ('fighter_biography','gang_origin','territory_origin','place_ambient'):
                assert p['creative_plan']['focus'] in ('recorded_event','recorded_sequence')
                try: planning.prepare(store,form,{'subject':'Test'},focus='religious')
                except ValueError: pass
                else: raise AssertionError('Creative theme displaced a recorded event')
    with_store(check)


def test_same_subject_excluded_and_memory_window_bounded():
    def check(store):
        with store.db:
            for i in range(22):
                planning.remember(store,str(i),'territory_origin',{'subject':str(i),'creative_plan':{'focus':'economic'}},['Trade and weighing fees.'],{'body_heading':str(i)})
        recent=planning.recent(store,'21','place')
        assert len(recent)==planning.WINDOW and all(p['subject_key']!='21' for p in recent)
        assert planning.recent(store,'other','fighter')==[]
    with_store(check)


def test_workshop_preview_pinning_paid_call_and_unchanged_authored_sources():
    def check(store):
        source=seed(store); before=mechanical_records(store)
        policy=workshop.save_revision(store,{**workshop.defaults('fighter_memory'),'instructions':'My saved instructions.'})
        body={'sample_key':source['key'],'form_revision_id':policy['revision_id'],'request_key':'planned-once-00000000'}
        with patch.object(writer,'API_KEY','mock'),patch.object(writer,'_call',return_value=draft('I kept my tools.')) as provider:
            prepared=workshop.preview(store,body)
            assert provider.call_count==0
            item,_=workshop.queue(store,{**body,'plan_key':prepared['plan_key']})
            result=workshop.execute(store,item['trial_id'])
            assert provider.call_count==1 and result['status']=='ready'
            sent=provider.call_args.args[1]
            assert sent==prepared['packet'] and 'My saved instructions.' in provider.call_args.kwargs['contract_override']
            assert workshop.queue(store,{**body,'plan_key':prepared['plan_key']})[1] is False
            assert provider.call_count==1
        assert mechanical_records(store)==before
        assert workshop.revision(store,policy['revision_id'])['instructions']=='My saved instructions.'
    with_store(check)


def test_planning_does_not_commit_surrounding_campaign_transaction():
    def check(store):
        store.db.execute("INSERT INTO system_state VALUES('transaction-test','uncommitted')")
        planning.prepare(store,'gang_origin',{'subject':'A new gang'})
        assert store.db.in_transaction
        store.db.rollback()
        assert store.get_state('transaction-test') is None
        assert store.db.execute('SELECT count(*) FROM writer_creative_plans').fetchone()[0]==0
    with_store(check)


def test_schema_11_upgrade_preserves_owner_workshop_revisions_and_edits():
    def check(store):
        source=seed(store)
        policy=workshop.save_revision(store,{**workshop.defaults('fighter_memory'),'instructions':'Owner original.'})
        imported=workshop.import_sample(store,{'sample_key':source['key']})
        workshop.save_edit(store,{'trial_id':imported['trial_id'],'body':'My edited memory.'})
        with store.db:
            store.db.execute('DROP TABLE writer_creative_plans')
            store.db.execute('DROP TABLE writer_creative_footprints')
            store.db.execute('DELETE FROM schema_migrations WHERE version>=12')
            store.db.execute('PRAGMA user_version=11')
        from migrations import migrate
        assert migrate(store.db)==14
        assert workshop.revision(store,policy['revision_id'])['instructions']=='Owner original.'
        assert workshop.trial(store,imported['trial_id'])['edits'][0]['document']['blocks'][0]['text']=='My edited memory.'
    with_store(check)


if __name__=='__main__':
    for name,test in sorted(list(globals().items())):
        if name.startswith('test_') and callable(test):test();print('PASS',name)
