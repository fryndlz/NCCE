"""Executable event-clock specification. No model/network calls or real campaign writes."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from fighter_event_clock import build,measure,HALF_LIFE_EVENTS
from story_engine import select_mind
from test_writer_pipeline import with_store
from test_fighter_mind import fighter,memory,AT
import fighter_mind as mind

def obs(index,event=None,**overrides):
    return {**memory(str(index),['skill'],f'2026-10-{index+1:02d}T12:00:00+00:00'),
            'source_event_ids':[event or f'e{index}'],'fighter_id':1,**overrides}

def test_ten_subsequent_relevant_changes_halve_recency():
    records=[obs(i) for i in range(11)];clock=build(records,fighter_id=1)
    assert clock['head']==11 and HALF_LIFE_EVENTS==10
    assert measure(records[0],clock)=={'event_position':1,'subsequent_relevant_events':10,'recency':0.5}
    assert measure(records[-1],clock)['recency']==1
    # Importance/relevance/bias stay independent of the recency clock.
    selected=select_mind(fighter(),records,at='1900-01-01',limit=100)
    assert selected==select_mind(fighter(),records,at='2099-01-01',limit=100)

def test_reimports_rewrites_derived_thoughts_and_foreign_events_do_not_tick():
    a=obs(0);clock=build([a],fighter_id=1)
    duplicate={**a,'id':'new-prose-version','content':'Rewritten prose, same factual cause.'}
    reflection={**obs(1),'memory_type':'reflection','source_event_ids':['e0'],'source_observation_ids':[a['id']]}
    thought={**obs(2),'memory_type':'thought'}
    foreign=obs(3,fighter_id=2)
    baseline=obs(4,baseline=True)
    extended=build([a,duplicate,reflection,thought,foreign,baseline],fighter_id=1)
    assert extended['head']==clock['head']==1
    assert measure(a,extended)['recency']==1
    assert measure(reflection,extended)['event_position']==1
    # Resolving a concern does not erase that experience from the logical clock.
    historical=obs(5,tags=['history_only'])
    assert build([a,historical],fighter_id=1)['head']==2

def test_individual_changes_count_even_when_imported_together():
    records=[obs(i,occurred_at=AT,observed_at=AT) for i in range(3)]
    # An injury, XP change and gang result are three distinct causes, not one sync.
    records[0]['tags']=['injury'];records[1]['tags']=['growth'];records[2]['tags']=['battle']
    clock=build(records,fighter_id=1)
    assert clock['head']==3
    assert sorted(clock['positions'].values())==[1,2,3]
    assert build(list(reversed(records)),fighter_id=1)==clock

def test_reflection_formation_is_latest_cited_cause_not_generation_time():
    records=[obs(i) for i in range(5)]
    reflection={**obs(10),'memory_type':'reflection','memory_key':'reflection:batch',
                'source_event_ids':[], 'source_observation_ids':[records[0]['id'],records[2]['id']]}
    clock=build(records+[reflection],fighter_id=1)
    assert clock['head']==5
    assert measure(reflection,clock)['event_position']==3
    assert measure(reflection,clock)['subsequent_relevant_events']==2
    rewritten={**reflection,'created_at':'2099-01-01','observed_at':'2099-01-01','content':'New wording.'}
    assert measure(rewritten,build(records+[rewritten],fighter_id=1))==measure(reflection,clock)

def test_corrections_are_one_underlying_event_and_unrelated_ledger_rows_do_not_tick():
    def check(store):
        def event(eid,stamp,parent=None):
            store.db.execute('''INSERT INTO campaign_events(event_id,event_key,event_type,occurred_at,observed_at,created_at,provenance_class,payload_json,supersedes_event_id)
                VALUES(?,?,'battle_result',?,?,?,'mechanical_fact','{}',?)''',(eid,eid,stamp,stamp,stamp,parent))
        event('original','2026-10-01');event('other','2026-10-03');event('correction','2026-10-08','original')
        a=obs(0,event='original',occurred_at='2026-10-01');b=obs(2,event='other',occurred_at='2026-10-03')
        clock=build([a,b],store,1)
        corrected={**a,'id':'corrected','source_event_ids':['correction']}
        assert build([corrected,b],store,1)['ordered_event_ids']==clock['ordered_event_ids']
        assert measure(corrected,build([corrected,b],store,1))['subsequent_relevant_events']==1
        event('foreign','2026-10-09')
        assert build([corrected,b],store,1)['head']==2
    with_store(check)

def test_no_fixed_expiry_and_clock_advances_only_with_another_relevant_fact():
    a=obs(0,tags=['grief','belonging']);f=fighter()
    assert mind.candidates(f,[a],'2026-10-01')==mind.candidates(f,[a],'2099-12-31')
    before=mind.candidates(f,[a])[0]
    after=mind.candidates(f,[a,obs(1)])[0]
    grief=next(c for c in mind.candidates(f,[a,obs(1)]) if c['family']=='grief')
    assert grief['event_clock']['subsequent_relevant_events']==1 and before['expires_at'] is None
    assert grief['id']==before['id']  # waiting/new facts do not force a prose rewrite

def test_malformed_correction_cycle_is_order_independent():
    from types import SimpleNamespace
    graph={'a':{'supersedes_event_id':'b'},'b':{'supersedes_event_id':'c'},'c':{'supersedes_event_id':'b'}}
    fake=SimpleNamespace(db=SimpleNamespace(execute=lambda query,args:SimpleNamespace(fetchone=lambda:graph.get(args[0]))))
    records=[obs(0,event='a'),obs(1,event='b'),obs(2,event='c')]
    assert build(records,fake,1)['ordered_event_ids']==['b']
    assert build(list(reversed(records)),fake,1)['ordered_event_ids']==['b']

def test_three_roles_receive_the_same_versioned_cognitive_policy():
    import llm_writer, codex_review_queue as queue
    from fighter_event_clock import policy
    packet=llm_writer.memory_packet(None,fighter(),{'name':'Gang'},'A thought',['A recorded cause.'],{},form='fighter_mind')
    assert packet['cognitive_design']==policy()
    def check(store):
        job_id=queue.enqueue(store,{'run_id':'test','form':'fighter_mind','rounds':[]},
                             {'instructions':'One current thought.','packet':packet,'candidates':[]},[],{},'Test rubric')
        payload=json.loads(store.db.execute('SELECT payload_json FROM codex_review_jobs WHERE job_id=?',(job_id,)).fetchone()[0])
        assert payload['cognitive_design']==policy() and payload['packet']['cognitive_design']==policy()
        import workshop_interventions as tech
        from unittest.mock import patch
        state={'run_id':'test','form':'fighter_mind','status':'escalated','message':'Test only',
               'configuration':{},'shared':{},'specific':{},'rounds':[]}
        with patch.object(tech,'save'):
            tech.submit(store,state,'technical_investigation')
        job=json.loads(store.db.execute('SELECT payload_json FROM codex_review_jobs WHERE job_id=?',(state['tech']['job_id'],)).fetchone()[0])
        assert job['packet']['cognitive_design']==policy()
    with_store(check)

if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):fn();print('PASS '+name)
