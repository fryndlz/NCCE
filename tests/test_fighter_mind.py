"""Current thoughts: independent prose, source traceability and lifecycle. No model calls."""
import sys,json
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writer_pipeline import with_store
from test_story_engine import campaign,latest_game,apply
import fighter_mind as mind, llm_writer as writer, writer_workshop as ws
from story_engine import read_memories,document_for

AT='2026-10-28T12:00:00+00:00'
def fighter():return {'id':1,'name':'Test fighter','gang_id':'g1','class':'Ganger','type':'Gunner','status':'Recovery','effects':None}
def memory(key='injury',tags=None,at=AT):
    return {'id':key,'memory_key':key,'memory_type':'observation','content':'This is the full historical memory paragraph.',
            'writer_status':'stale','importance':7,'occurred_at':at,'observed_at':AT,'baseline':False,
            'tags':tags or ['recovery'],'source_event_ids':['event-'+key],'evidence':['Recovery recorded.'],'title':'Status changed'}

def test_pending_is_not_a_thought_and_ready_is_independent_persistent_prose():
    def check(store):
        f=fighter();m=memory();g={'name':'Test gang','gang_type':'Orlock'}
        with patch.object(writer,'WRITER_ENABLED',False):mind.refresh(store,f,g,[m],AT)
        thoughts,status=mind.read(store,f,[m],AT)
        assert not thoughts and status['pending']==1
        text='I need my hands steady before they put that cutter back in them.'
        with patch.object(writer,'write',return_value=([{'runs':[{'text':text}]}],{'status':'ready'})) as call:
            mind.refresh(store,f,g,[m],AT)
            assert call.call_count==1
            mind.refresh(store,f,g,[m],AT)
            assert call.call_count==1
        thoughts,status=mind.read(store,f,[m],AT)
        assert thoughts[0]['content']==text and thoughts[0]['content']!=m['content']
        assert thoughts[0]['memory_id']==m['id'] and thoughts[0]['source_event_ids']==m['source_event_ids']
        assert status['pending']==0 and m['content'].startswith('This is the full')
        store.db.commit()
        # Read-only API snapshots see the persisted thought too.
        with store.reader() as reader:assert mind.read(reader,f,[m],AT)[0][0]['content']==text
    with_store(check)

def test_condition_resolves_death_clears_and_calendar_never_expires_thoughts():
    def check(store):
        f=fighter();m=memory();g={'name':'Test gang'}
        with patch.object(writer,'write',return_value=([{'runs':[{'text':'I need rest.'}]}],{'status':'ready'})):
            mind.refresh(store,f,g,[m],AT)
        assert mind.read(store,{**f,'status':'Active'},[m],AT)[0]==[]
        mind.refresh(store,{**f,'status':'Active'},g,[m],AT)
        assert store.db.execute('SELECT lifecycle FROM fighter_thoughts').fetchone()[0]!='active'
        assert not mind.candidates({**f,'status':'Killed'},[m],AT)
        old=memory('old',['victory','battle'],'2026-10-01T12:00:00+00:00')
        new=memory('new',['defeat','battle'],'2026-10-27T12:00:00+00:00')
        assert len(mind.candidates({**f,'status':'Active'},[old,new],AT))==1
        assert mind.candidates({**f,'status':'Active'},[old,new],AT)[0]['source_memory_id']=='new'
        assert mind.candidates({**f,'status':'Active'},[new],'2099-11-10T12:00:00+00:00') == mind.candidates({**f,'status':'Active'},[new],AT)
    with_store(check)

def test_workshop_reflection_matches_production_packet_and_mind_is_selectable():
    def check(store):
        before=campaign();apply(store,before);apply(store,latest_game(before))
        source=next(s for s in ws.catalog(store) if s['form']=='fighter_reflection')
        selected=ws.sample(store,source['key']);ident=source['key'].split(':')[1]
        row=dict(store.db.execute('SELECT * FROM story_memories WHERE memory_id=?',(ident,)).fetchone())
        f=dict(store.db.execute('SELECT * FROM fighters WHERE id=?',(row['fighter_id'],)).fetchone())
        g=dict(store.db.execute('SELECT * FROM gangs WHERE gang_id=?',(f['gang_id'],)).fetchone())
        refs=[dict(store.db.execute('SELECT * FROM story_memories WHERE memory_id=?',(mid,)).fetchone()) for mid in json.loads(row['source_observation_ids_json'])]
        for m in refs:
            for field in ('tags','evidence','source_event_ids'):m[field]=json.loads(m[field+'_json'])
        expected=writer.memory_packet(store,f,g,row['title'],json.loads(row['evidence_json']),json.loads(row['writer_context_json']),writer.reflection_observations(refs),form='fighter_reflection')
        assert selected['packet']==expected
        assert 'event' not in expected and expected['source_observation_ids']
        assert 'one recorded event only' not in expected['event_boundary']
        thought=next(s for s in ws.catalog(store) if s['form']=='fighter_mind')
        sample=ws.sample(store,thought['key'])
        saved=store.db.execute('SELECT packet_json FROM fighter_thoughts WHERE thought_id=?',(thought['key'].split(':')[1],)).fetchone()
        assert sample['packet']==json.loads(saved[0]) and sample['packet']['source_memory_ids']
        assert 'fighter_mind' in ws.home(store)['forms']
    with_store(check)

def test_ready_biography_remains_stable_and_battle_dates_are_not_import_dates():
    def check(store):
        before=campaign();apply(store,before)
        fid=store.db.execute("SELECT id FROM fighters WHERE name='Maex'").fetchone()[0]
        doc=document_for(store,'fighter_biography',fid);doc.update(writer_status='ready',blocks=[{'type':'body_paragraph','text':'A stable formative life.'}])
        store.db.execute("UPDATE story_artifacts SET document_json=? WHERE scope_type='fighter_biography' AND scope_key=? AND active=1",(json.dumps(doc),str(fid)))
        store.db.execute("UPDATE fighters SET backstory='A stable formative life.' WHERE id=?",(fid,));store.db.commit()
        apply(store,latest_game(before))
        assert document_for(store,'fighter_biography',fid)['blocks']==doc['blocks']
        assert store.db.execute('SELECT backstory FROM fighters WHERE id=?',(fid,)).fetchone()[0]=='A stable formative life.'
        mara=store.db.execute("SELECT id FROM fighters WHERE name='Mara Kel'").fetchone()[0]
        battles=[m for m in read_memories(store,mara) if 'battle' in m['tags'] and m['memory_type']=='observation']
        assert battles and all(m['occurred_at'] for m in battles)
    with_store(check)

if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):fn();print('PASS '+name)
