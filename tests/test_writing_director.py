"""Director and world-stream integration checks using disposable databases."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from writing_director import format_date, record_date, public_policy
from world_streams import read_stream, maybe_ambient
from story_engine import document_for, regenerate
from test_story_engine import campaign, latest_game, apply, _with_store, fighter, C9, KLY, mechanical_records


def test_dates_follow_warsaw_calendar_and_fixed_anchor():
    result=format_date('2026-10-25T09:46:31.046883+00:00')
    assert result['imperialDisplay']=='9.814.998.M41'
    assert result['realDisplay']=='25 October 2026 · 10:46'
    assert format_date('2026-01-01')['imperialDisplay']=='9.001.998.M41'
    assert format_date('2027-01-01')['imperialDisplay']=='9.001.998.M41'
    assert format_date('2024-12-31')['fraction']==998
    assert format_date('2026-10-25')['realDisplay']=='25 October 2026'
    assert '00:00' not in format_date('2026-10-25T00:00:00')['realDisplay']
    assert format_date('2026-03-29T00:30:00Z')['realDisplay'].endswith('01:30')
    assert format_date('2026-03-29T01:30:00Z')['realDisplay'].endswith('03:30')
    assert record_date({'baseline':True,'observed_at':'2026-10-25'})['imperialDisplay']=='Undated archive'
    assert 'occurrence date unknown' in record_date({'observed_at':'2026-10-25'})['realDisplay']


def test_place_transformation_owner_and_mechanics_stay_one_history():
    def check(store):
        original=campaign(); apply(store,original)
        tid=store.dashboard()['territories'][0]['id']
        origin=document_for(store,'territory_origin',tid)
        changed=latest_game(original)
        apply(store,changed)
        changed=deepcopy(changed); changed['captured_at']='2026-10-26T10:00:00Z'
        changed['territories'][0].update({'Territory':'Smelting Works','Gang ID':'g3','Gang':KLY,'Ruined':True,'Income':20})
        apply(store,changed)
        current=store.dashboard()['territories'][0]
        assert current['id']==tid and current['territory']=='Smelting Works'
        stream=store.territory(tid)['narrative_stream']
        assert {'battle_result','territory_holder_changed','territory_type_changed'} <= {x['event_type'] for x in stream}
        assert document_for(store,'territory_origin',tid)==origin
        assert all(x['document']['author'] and x['document']['metadata'] and x['document']['date_display'] for x in stream)
        battle=next(x for x in stream if x['event_type']=='battle_result')
        assert 'fuel gantries' in json.dumps(battle['document']) and 'furnace doors' not in json.dumps(battle['document'])
        assert any(x['continuity']['previous_entry_ids'] for x in stream)
        records=mechanical_records(store)
        counts=[store.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('narrative_entries','story_memories','story_artifacts')]
        assert not regenerate(store)['changed']
        regenerate(store,force=True)
        assert counts==[store.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('narrative_entries','story_memories','story_artifacts')]
        assert records==mechanical_records(store)
    _with_store(check)


def test_battle_correction_and_removal_do_not_leave_active_place_outcomes():
    def check(store):
        before=campaign(); apply(store,before); after=latest_game(before); apply(store,after)
        tid=store.dashboard()['territories'][0]['id']
        old=[x for x in read_stream(store,'territory',tid) if x['event_type']=='battle_result'][0]
        correction=deepcopy(after); correction['captured_at']='2026-10-25T11:00:00Z'; correction['battles'][0]['winner']=KLY
        apply(store,correction)
        active=read_stream(store,'territory',tid)
        assert old['entry_id'] not in {x['entry_id'] for x in active}
        assert any(KLY in json.dumps(x['document'],ensure_ascii=False) for x in active)
        correction['captured_at']='2026-10-25T12:00:00Z'; correction['battles']=correction['battles'][1:]
        apply(store,correction)
        assert not read_stream(store,'territory',tid)
        assert store.db.execute('SELECT active FROM narrative_entries WHERE entry_id=?',(old['entry_id'],)).fetchone()[0]==0
    _with_store(check)


def test_ambient_is_bounded_persistent_fiction_with_historical_owner():
    def check(store):
        before=campaign(); apply(store,before)
        tid=store.dashboard()['territories'][0]['id']; records=mechanical_records(store)
        gangs=store.dashboard()['gangs']; territories=store.dashboard()['territories']
        import llm_writer
        old_key,old_call=llm_writer.API_KEY,llm_writer._call
        llm_writer.API_KEY='mock-token'; llm_writer._call=lambda form,packet:['Residents keep the old notice beside the new one.']
        try:
            with store.db:
                assert maybe_ambient(store,gangs,territories,at='2026-10-25T12:00:00+00:00',chance=1,limit=2)==1
                assert maybe_ambient(store,gangs,territories,at='2026-10-25T13:00:00+00:00',chance=1,limit=2)==0
        finally: llm_writer.API_KEY=old_key; llm_writer._call=old_call
        ambient=read_stream(store,'territory',tid)[0]
        assert ambient['provenance_class']=='connective_fiction' and not ambient['source_event_ids']
        assert 'fiction composed' in ambient['date_display']['realDisplay']
        after=deepcopy(before); after['captured_at']='2026-10-26T12:00:00Z'; after['territories'][0].update({'Gang ID':'g3','Gang':KLY}); apply(store,after)
        retained=next(x for x in read_stream(store,'territory',tid) if x['entry_id']==ambient['entry_id'])
        assert C9 in str(retained['document']['evidence']) and KLY not in str(retained['document']['evidence'])
        # Ambient never creates a factual event or source snapshot.
        assert len(records[0])+1==len(mechanical_records(store)[0])
        with store.db:
            assert maybe_ambient(store,store.dashboard()['gangs'],store.dashboard()['territories'],at='2026-10-26T12:00:00+00:00',chance=1)==0
    _with_store(check)


def test_identity_is_authored_persistent_and_changes_only_derived_voice():
    def check(store):
        before=campaign(); apply(store,before)
        subject=fighter(store,'Maex'); records=mechanical_records(store)
        store.set_writer_identity(subject['id'],{'being':['animal'],'work':['scout'],'narration_mode':'sensory'})
        result=store.fighter(subject['id'])
        assert result['writer_identity']['work']==['scout']
        assert result['voice_profile']['writer_context']['narration_mode']=='sensory'
        assert all(x['writer_context']['identity'].get('work')==['scout'] for x in result['memories'])
        assert all('player:writer-identities' in x['source_ids'] for x in result['memories'])
        assert all('XP' not in x['content'] for x in result['memories'])
        assert result['memories'] and all(x['writer_status']=='unconfigured' and x['content']=='' for x in result['memories'])
        assert store.db.execute('SELECT count(*) FROM writer_identity_revisions').fetchone()[0]==1
        assert records==mechanical_records(store)
    _with_store(check)


def test_authored_backstory_informs_identity_without_becoming_event_prompt_text():
    from writing_director import identity_context
    packet=identity_context({'name':'Mara Kel','backstory':'Canon instruction: preserve the broken archive record.','backstory_source':'C-NINE Story'},
                            {'name':C9,'gang_type':'Genestealer Cults'})
    assert packet['authored_context'] is None
    assert any(item['label']=='Authored history' and item['source']=='canon_authored' for item in packet['inferred_identity'])
    assert 'gender' not in packet['identity'] and 'pronouns' not in packet['identity']


def test_identity_and_stim_weights_are_inferred_with_provenance():
    from writing_director import identity_context
    fighter={'name':'Mara Kel','class':'Specialist','type':'Maintenance Fitter','backstory':'KEL, Mara — Maintenance Fitter; the workshop is home.','backstory_source':'player-authored / C-NINE story','status':'Recovery','effects':'Critical Injury','mechanics':{'T':4,'S':3,'W':1}}
    packet=identity_context(fighter,{'name':C9,'gang_type':'Genestealer Cults'},{'register':'crew','traits':['practical','enduring']})
    facets={item['label']:item for item in packet['inferred_identity']}
    weights={item['topic']:item for item in packet['stim_weights']}
    assert facets['Recorded role']['value']=='Specialist'
    assert facets['Authored work or craft']['value']=='maintenance fitter'
    assert facets['Authored work or craft']['source']=='player_authored'
    assert facets['Physical endurance']['source']=='inference'
    assert 'Physical strength' not in facets
    assert weights['injury']['weight']>1 and weights['recovery']['weight']>1
    assert weights['equipment']['weight']>1
    assert all('basis' in item for item in weights.values())


def test_ambiguous_place_names_do_not_invent_a_location_link():
    def check(store):
        before=campaign(); before['territories'].append({'Territory ID':'t2','Territory':'Promethium Cache','Gang ID':'g3','Gang':KLY,'Card':'5D'})
        apply(store,before); apply(store,latest_game(before))
        assert not any(read_stream(store,'territory',t['id']) for t in store.dashboard()['territories'])
        assert any(x['event_type']=='battle_result' for x in store.gang('g1')['narrative_stream'])
    _with_store(check)


if __name__=='__main__':
    checks=[value for name,value in list(globals().items()) if name.startswith('test_') and callable(value)]
    for check in checks:
        check(); print('PASS',check.__name__)
    print(f'ok ({len(checks)} writing director checks)')
