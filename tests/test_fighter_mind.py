"""Current thoughts: independent prose, source traceability and lifecycle. No model calls."""
import sys,json
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_writer_pipeline import with_store
from test_story_engine import campaign,latest_game,apply
import fighter_mind as mind, llm_writer as writer
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
            # Upgrade a stored pre-policy packet without buying replacement prose.
            saved=store.db.execute('SELECT thought_id,packet_json FROM fighter_thoughts').fetchone()
            legacy=json.loads(saved['packet_json']);legacy.pop('cognitive_design',None)
            store.db.execute('UPDATE fighter_thoughts SET packet_json=? WHERE thought_id=?',(json.dumps(legacy),saved['thought_id']))
            mind.refresh(store,f,g,[m],AT)
            assert call.call_count==1
            updated=json.loads(store.db.execute('SELECT packet_json FROM fighter_thoughts').fetchone()[0])
            import fighter_event_clock
            assert updated['cognitive_design']==fighter_event_clock.policy()
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

def test_four_existing_thoughts_reduce_to_three_without_losing_saved_prose():
    def check(store):
        f=fighter()
        memories=[memory(tag,[tag]) for tag in ('recovery','battle','equipment','advancement')]
        gang={'name':'Test gang'}
        with patch.object(mind,'MAX_THOUGHTS',4), patch.object(writer,'write',return_value=([{'runs':[{'text':'Saved thought.'}]}],{'status':'ready'})):
            mind.refresh(store,f,gang,memories,AT)
        assert store.db.execute("SELECT count(*) FROM fighter_thoughts WHERE lifecycle='active'").fetchone()[0]==4
        thoughts,status=mind.read(store,f,memories,AT)
        assert len(thoughts)==status['candidate_count']==status['max_thoughts']==3
        with patch.object(writer,'write') as write:
            mind.refresh(store,f,gang,memories,AT)
            write.assert_not_called()
        assert store.db.execute("SELECT count(*) FROM fighter_thoughts WHERE lifecycle='active'").fetchone()[0]==3
        assert store.db.execute("SELECT content FROM fighter_thoughts WHERE lifecycle='superseded'").fetchone()[0]=='Saved thought.'
    with_store(check)


if __name__=='__main__':
    for name,fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):fn();print('PASS '+name)
