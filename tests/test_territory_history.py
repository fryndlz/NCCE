"""Confirmed conversions remain distinct from captures and invented dates."""
import json,sys,tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src')]
from store import Store
import territory_history as th
from story_engine import regenerate
from world_streams import places_with_aliases,locate_place,read_stream
import exchange_automation as exchange


def setup(directory):
    s=Store(Path(directory)/'test.db')
    for b in th.manifest()['bindings']:
        gid=b['gang_id'];name='Ethernetans' if b.get('conversion') else 'Slag Eaters'
        s.db.execute('INSERT INTO gangs(gang_id,name,active) VALUES(?,?,1)',(gid,name))
        # Reproduce the stale MAIN name join: both settlements had the default ID.
        for default in (True,False):
            s.db.execute("INSERT INTO territories(gang_id,gang_name,territory,is_default,active,mechanics_json) VALUES(?,?,'Settlement',?,1,?)",
                         (gid,name,int(default),json.dumps({'territory_id':'default-'+gid})))
    s.db.commit();return s


def test_confirmed_history_has_one_identity_event_and_explicit_origin_exception():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s=setup(directory)
        try:
            originals=[tuple(r) for r in s.db.execute('SELECT * FROM territories')]
            assert len(th.apply(s))==1 and not th.apply(s)
            assert [tuple(r) for r in s.db.execute('SELECT * FROM territories')]==originals
            event=dict(s.db.execute('SELECT * FROM campaign_events').fetchone())
            assert event['occurred_at'] is None and event['provenance_class']=='player_authored'
            assert len(th.records(s))==1 # No fake Orlock conversion.
            timeline=s.history_timeline();change=timeline['events'][0]
            assert change['timestamp_basis']=='first_observed' and change['phase']=='unavailable'
            assert change['battle_id'] is None and change['preceding_battle_id'] is None
            assert change['recorded_at']==th.manifest()['confirmed_at']
            assert change['local_territory_id'] is not None
            place=dict(s.db.execute('SELECT * FROM territories WHERE id=?',(change['local_territory_id'],)).fetchone())
            assert not place['is_default']
            places=places_with_aliases(s)
            assert locate_place({},places,'Gambling Den')['id']==place['id']
            assert locate_place({'territory_id':th.manifest()['bindings'][1]['source_territory_id']},places)['gang_name']=='Slag Eaters'
            with patch('urllib.request.urlopen',side_effect=AssertionError('No network/model work')):
                regenerate(s,writer_enabled=False)
            stream=read_stream(s,'territory',place['id'])
            assert len([e for e in stream if e['entry_key']==event['event_id']])==1
            candidates=exchange.candidates(s)
            c=next(c for c in candidates if c['form']=='territory_origin' and c['entity_key']==str(place['id']))
            assert 'Gambling Den' in c['context']['origin_history_exception']
            assert c['facts']['confirmed_territory_history'][0]['occurred_at'] is None
            assert all('origin_history_exception' not in c['context'] for c in candidates
                       if c['form']=='territory_origin' and c['entity_key']!=str(place['id']))
            assert len(th.records(s))==1
        finally:s.close()


def test_ambiguous_or_missing_binding_never_chooses_an_arbitrary_settlement():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s=setup(directory)
        try:
            b=th.manifest()['bindings'][0]
            s.db.execute("INSERT INTO territories(gang_id,gang_name,territory,is_default,active) VALUES(?,'Ethernetans','Settlement',0,1)",(b['gang_id'],));s.db.commit()
            assert not th.apply(s)
            assert all(not th.history_for(s,r[0]) for r in s.db.execute('SELECT id FROM territories'))
        finally:s.close()


def test_paused_origin_amendment_preserves_id_original_brief_and_prose():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
        s=setup(directory)
        try:
            regenerate(s,writer_enabled=False)
            cs=exchange.candidates(s)
            c=next(c for c in cs if c['form']=='territory_origin' and c['facts'].get('confirmed_territory_history'))
            old=deepcopy(c);old['facts'].pop('confirmed_territory_history');old['context'].pop('origin_history_exception')
            rid=c['facts']['confirmed_territory_history'][0]['paused_origin_request_id']
            packet=exchange._packet(s,old,rid);revision=exchange.revision(old,[],s)
            packet['request']['source_revision']=revision
            s.db.execute("INSERT INTO writing_exchange_requests(request_id,target_key,packet_json,target_json,source_revision,state,created_at,client_state,policy_version) VALUES(?,?,?,?,?,'PENDING','2026-11-05','WRITING',2)",
                (rid,exchange.target_key(c),exchange.packed(packet),exchange.packed({'target':old,'original':exchange.projection(s,c)}),revision));s.db.commit()
            with s.db:th.amend_paused_origin(s,cs)
            row=dict(s.db.execute('SELECT * FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone())
            assert row['state']=='PENDING' and row['client_state']=='WRITING'
            assert row['source_revision']!=revision and exchange.source_matches(s,c,row)
            audit=json.loads(row['target_json'])
            assert audit['brief_history'][0]['packet']==packet
            assert th.amendments(s)[0]['packet']['context'][-1]['section']=='history_amendment'
            with s.db:th.amend_paused_origin(s,cs)
            assert s.db.execute('SELECT target_json FROM writing_exchange_requests WHERE request_id=?',(rid,)).fetchone()[0]==row['target_json']
            text='Existing draft, adjusted once to acknowledge the Gambling Den.'
            result=exchange.deliver(s,dict(request_id=rid,status='READY',source_revision=row['source_revision'],writer_text_md=text))
            assert result['status']=='imported',result
            assert not th.amendments(s)
        finally:s.close()


if __name__=='__main__':
    test_confirmed_history_has_one_identity_event_and_explicit_origin_exception()
    test_ambiguous_or_missing_binding_never_chooses_an_arbitrary_settlement()
    test_paused_origin_amendment_preserves_id_original_brief_and_prose()
    print('PASS confirmed territory history: dates, identity, capture exclusion, timeline, stream, origin context, no source edits')
