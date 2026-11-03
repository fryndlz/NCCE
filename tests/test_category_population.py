"""Population spending, publication, recovery and preservation; fake writer only."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from store import Store
from test_story_engine import campaign,latest_game,apply
from story_engine import regenerate
import category_population as pop
import llm_writer as writer
import writer_workshop as ws


def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as folder:
        store=Store(Path(folder)/'test.db')
        first=campaign();apply(store,first);apply(store,latest_game(first))
        regenerate(store,writer_enabled=False)
        baseline=pop.preview(store,{'form':'territory_origin'})
        assert baseline['items'], 'Fixture must contain genuine pending territory records'
        def body(preview,key):return {'form':preview['form'],'fingerprint':preview['fingerprint'],'call_limit':1,'request_key':key}
        fake=([{'runs':[{'text':'Workers mend the broken gate before the shift arrives.','marks':[]}]}],{'status':'ready','revision':'fake'})
        with patch.object(writer,'API_KEY','fake-key'),patch.object(writer,'write',return_value=fake) as call:
            readonly_before=store.db.total_changes
            pop.preview(store,{'form':'territory_origin'});pop.home(store)
            assert store.db.total_changes==readonly_before
            b=body(baseline,'population-request-1');run,fresh=pop.queue(store,b);assert fresh
            same,fresh=pop.queue(store,b);assert not fresh and same['run_id']==run['run_id']
            result=pop.execute(store,run['run_id'])
            assert result['status']=='completed' and result['results'][0]['status']=='ready'
            assert call.call_count==1
            assert result['remaining_count']==len(baseline['items'])-1
            original=run['plan']['items'][0]['key'];old=pop.record(store,original)
            assert old['active']==0
            published=store.db.execute('SELECT * FROM story_artifacts WHERE scope_type=? AND scope_key=? AND active=1',('territory_origin',old['scope_key'])).fetchone()
            assert json.loads(published['document_json'])['writer_status']=='ready'
            assert json.loads(published['document_json'])['provenance_class']=='inference'
            assert pop.execute(store,run['run_id'])==result and call.call_count==1
            assert original not in [i['key'] for i in pop.preview(store,{'form':'territory_origin'})['items']]
            assert not store.db.execute('SELECT * FROM workshop_active').fetchone(), 'Population activated a policy'
            # Preview identity changes with active policy/source changes.
            try:pop.queue(store,body(baseline,'population-stale-plan'));raise AssertionError('Stale plan accepted')
            except ValueError:pass
            p=pop.preview(store,{'form':'territory_origin'})
            if p['items']:
                run,_=pop.queue(store,body(p,'population-stopped-1'));pop.stop(store,run['run_id'])
                assert pop.execute(store,run['run_id'])['status']=='stopped' and call.call_count==1
                # Server restarts never automatically replay unfinished spending.
                run,_=pop.queue(store,body(p,'population-restart-1'));pop.recover(store)
                assert pop.get(store,run['run_id'])['status']=='interrupted'
                pop.execute(store,run['run_id']);assert call.call_count==1
                # Errors halt after one attempt and do not publish an empty draft.
                run,_=pop.queue(store,body(p,'population-failure-1'))
                with patch.object(writer,'write',return_value=([],{'status':'error','message':'Provider timeout; no retry'})) as fail:
                    failed=pop.execute(store,run['run_id'])
                assert failed['status']=='needs_attention' and failed['results'][0]['status']=='error' and fail.call_count==1
                assert pop.record(store,p['items'][0]['key'])['active']==1
                assert failed['results'][0]['key'] not in [i['key'] for i in pop.preview(store,{'form':'territory_origin'})['items']], 'Failed spending silently became eligible for retry'
                # A paid result cannot replace a target modified while the request was in flight.
                p=pop.preview(store,{'form':'territory_history'});run,_=pop.queue(store,body(p,'population-conflict-1'))
                def race(*args,**kwargs):
                    row=pop.record(store,p['items'][0]['key']);doc=json.loads(row['document_json']);doc['writer_status']='ready'
                    store.db.execute('UPDATE story_artifacts SET document_json=? WHERE artifact_id=?',(ws.packed(doc),row['artifact_id']));store.db.commit()
                    return fake
                with patch.object(writer,'write',side_effect=race):conflict=pop.execute(store,run['run_id'])
                assert conflict['status']=='needs_attention' and conflict['results'][0]['document']['writer_status']=='ready'
                assert conflict['results'][0]['status']=='generated', 'Unpublished output falsely marked saved'
        # Authored records and uncertain failures must never be considered missing prose.
        for state in ('ready','stale','error','running'):
            assert pop.eligibility({'writer_status':state})!='pending'
        assert pop.eligibility({'writer_status':'pending','provenance_class':'player_authored'})=='protected'
        store.close()
    print('Category population tests passed')


if __name__=='__main__':main()
