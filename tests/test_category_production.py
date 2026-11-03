"""Real store/queue transitions, fake provider: no paid calls or native model turns."""
import json,sys,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from store import Store
from test_story_engine import campaign,latest_game,apply
from story_engine import regenerate
import category_production as prod
import category_population as pop
import codex_review_queue as bridge
import llm_writer as writer
import writer_workshop as ws


def main():
 with tempfile.TemporaryDirectory(dir=ROOT/'data',ignore_cleanup_errors=True) as folder:
  store=Store(Path(folder)/'test.db');first=campaign();apply(store,first);apply(store,latest_game(first));regenerate(store,writer_enabled=False)
  form='territory_origin'
  template=dict(store.db.execute("SELECT * FROM story_artifacts WHERE scope_type=? AND active=1 LIMIT 1",(form,)).fetchone())
  territory=dict(store.db.execute('SELECT * FROM territories WHERE id=?',(template['scope_key'],)).fetchone())
  def new_record():
   row={k:v for k,v in territory.items() if k!='id'};row['source_territory_id']='test-'+uuid.uuid4().hex
   cursor=store.db.execute('INSERT INTO territories('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
   key=cursor.lastrowid;aid=uuid.uuid4().hex;doc=json.loads(template['document_json']);doc['writer_status']='pending'
   store.db.execute('INSERT INTO story_artifacts VALUES(?,?,?,?,?,?,?,1)',(aid,form,str(key),ws.packed(doc),uuid.uuid4().hex,template['generation_version'],ws.now()));store.db.commit()
   return 'artifact:'+aid
  def configure(enabled,grant=0,key=None):
   body={'form':form,'enabled':enabled,'additional_calls':grant,'expected_revision':prod.policy(store,form)['revision'],'request_key':key or uuid.uuid4().hex}
   result=prod.configure(store,body)
   assert prod.configure(store,body)==result,'Duplicate decision changed authorization'
   return result
  def task(key):return prod.read(store,prod.ITEM+prod.identity(store,key))
  def review(item,score,valid=True,category='writing'):
   jid=item['review_job'];worker='disposable-native-test';turn='native-'+uuid.uuid4().hex
   claim=bridge.claim(store,{'thread_id':bridge.thread_id(),'worker_id':worker,'job_id':jid})
   assert claim['job']['kind']==prod.KIND
   body={'thread_id':bridge.thread_id(),'worker_id':worker,'job_id':jid,'lease':claim['lease'],'turn_id':turn}
   bridge.started(store,body)
   body['review']={'overall':score,'valid':valid,'category':category,'summary':'Review evidence.','feedback':'Make the consequences clearer.'}
   bridge.complete(store,body);before=ws.packed(task(item['key']));bridge.complete(store,body);assert ws.packed(task(item['key']))==before
  count=0
  def fake_write(*args,**kwargs):
   nonlocal count
   count+=1
   assert 'Production draft attempt' in kwargs['contract_override']
   return [{'runs':[{'text':'Distinct valid draft '+str(count),'marks':[]}]}],{'status':'ready','revision':'test'}
  with patch.object(writer,'API_KEY','fake-key'),patch.object(bridge,'status',return_value={'online':True}),patch.object(writer,'write',side_effect=fake_write):
   baseline=len(pop.plan(store,form)['items']);assert baseline
   configure(True,30)
   prod.discover(store);assert not prod.all_items(store),'Enablement incorrectly populated the backlog'
   key=new_record();prod.discover(store);prod.discover(store);assert len(prod.all_items(store))==1
   ident=prod.identity(store,key)
   for score in [6.2,7.4,7.0,7.8,7.3]:
    prod.advance(store);item=task(key);assert item['status']=='awaiting_review'
    review(item,score)
   prod.advance(store);item=prod.read(store,prod.ITEM+ident)
   assert item['status']=='published' and item['below_target'] and item['best']==3 and len(item['attempts'])==5
   assert 'draft 4' in item['attempts'][item['best']]['document']['blocks'][0]['text']
   prod.discover(store);prod.advance(store);assert count==5,'Five-attempt ceiling was exceeded'
   # Off does not add backlog or reset attempts; cancelling an unstarted review retains the draft.
   key=new_record();prod.discover(store);prod.advance(store);assert count==6
   configure(False);assert task(key)['status']=='paused_review'
   prod.advance(store);assert count==6
   configure(True);assert len(task(key)['attempts'])==1
   review(task(key),8.3);prod.advance(store);assert task(key)['status']=='published' and count==6
   # A context defect is an escalation, not another rewrite.
   key=new_record();prod.discover(store);prod.advance(store);review(task(key),3,False,'context')
   prod.advance(store);assert task(key)['status']=='needs_attention' and count==7
   # All invalid drafts: no fallback publication, regardless of numerical score.
   key=new_record();prod.discover(store)
   for n in range(5):prod.advance(store);review(task(key),9,False)
   prod.advance(store);assert task(key)['status']=='needs_attention' and pop.eligibility(pop.record(store,key))=='pending'
   assert count==12
   # Restart never silently repeats a pending native review or an uncertain paid call.
   key=new_record();prod.discover(store);prod.advance(store);assert task(key)['status']=='awaiting_review'
   prod.recover(store);prod.advance(store);assert task(key)['status']=='needs_attention' and count==13
   bridge.cancel(store,task(key)['review_job'],'Disposable restart test')
   # Explicit allowance is separate from the per-entry cap and survives toggle cycles.
   p=prod.policy(store,form);p['remaining']=0;prod.put(store,prod.POLICY+form,p);store.db.commit()
   key=new_record();prod.discover(store);prod.advance(store);assert not task(key)['attempts']
   configure(True,1);prod.advance(store);assert len(task(key)['attempts'])==1
   review(task(key),6);prod.advance(store);assert len(task(key)['attempts'])==1 and prod.policy(store,form)['remaining']==0
   configure(False);configure(True,1);prod.advance(store);assert len(task(key)['attempts'])==2
   review(task(key),8.5);prod.advance(store);assert task(key)['status']=='published'
   assert not prod.policy(store,form)['remaining']
   # Scene listening creates pending fiction from NEW recorded territory entries,
   # independently of the general writer flag and without a model call during discovery.
   from world_streams import save_entry,scene_triggers
   form='place_ambient'
   configure(True,3)
   baseline_scenes=store.db.execute("SELECT count(*) FROM narrative_entries WHERE provenance_class='connective_fiction'").fetchone()[0]
   ledger_count=store.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]
   prod.discover(store);assert store.db.execute("SELECT count(*) FROM narrative_entries WHERE provenance_class='connective_fiction'").fetchone()[0]==baseline_scenes
   prior_count=count
   save_entry(store,'territory',territory['id'],'new-recorded-change','territory_owner_changed','Recorded change',[],['Test source evidence'],generate=False)
   store.db.commit();prod.discover(store);prod.discover(store)
   assert count==prior_count,'Scene discovery called the writer'
   scene_tasks=[i for i in prod.all_items(store) if i['form']=='place_ambient']
   assert len(scene_tasks)==1 and pop.record(store,scene_tasks[0]['key'])['provenance_class']=='connective_fiction'
   assert store.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]==ledger_count
   prod.advance(store);review(prod.read(store,prod.ITEM+scene_tasks[0]['item_id']),8.4);prod.advance(store)
   assert prod.read(store,prod.ITEM+scene_tasks[0]['item_id'])['status']=='published'
   save_entry(store,'territory',territory['id'],'new-recorded-change','territory_owner_changed','Corrected change',[],['Corrected source evidence'],event={'payload':{'correction':True}},generate=False)
   store.db.commit();prod.discover(store)
   assert len([i for i in prod.all_items(store) if i['form']=='place_ambient'])==1,'A correction duplicated its scene'
   configure(False)
   save_entry(store,'territory',territory['id'],'another-recorded-change','territory_owner_changed','Recorded change',[],['Test source evidence'],generate=False)
   store.db.commit();prod.discover(store)
   assert len([i for i in prod.all_items(store) if i['form']=='place_ambient'])==1
   configure(True);prod.discover(store)
   assert len([i for i in prod.all_items(store) if i['form']=='place_ambient'])==1,'Enabling scenes backfilled historical events'
   p=prod.policy(store,form);p.pop('scene_seen');prod.put(store,prod.POLICY+form,p);store.db.commit()
   prod.recover(store);prod.discover(store)
   assert len([i for i in prod.all_items(store) if i['form']=='place_ambient'])==1,'Upgrade backfilled historical scene triggers'
  store.close()
 print('Category production passed: event discovery, independent controls, five-attempt cap, best-valid selection, native identity, pause, restart and spending bounds')


if __name__=='__main__':main()
