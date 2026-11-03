"""Native authorship invariants using a synthetic campaign. Never calls a model."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
from test_writer_pipeline import with_store
from test_story_engine import campaign, latest_game, apply
from story_engine import regenerate
import native_author as author
import category_population as pop
import codex_review_queue as bridge
import llm_writer as writer
import writing_rag as rag
import writer_workshop as ws

CHECKS = {k: 'Checked against the supplied packet; no independent review claimed.' for k in
          ('source_fidelity', 'chronology', 'viewpoint', 'repetition', 'uncertainty')}


def rejects(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('Unsafe operation accepted')


def main():
    def check(store):
        first=campaign(); apply(store,first); apply(store,latest_game(first)); regenerate(store,writer_enabled=False)
        rag.sync_sources(store)
        def call(action, **body):
            return author.dispatch(store,action,{'thread_id':bridge.thread_id(),**body})
        with patch.object(writer,'_call',side_effect=AssertionError('Native author called a provider')):
            before='\n'.join(store.db.iterdump())
            cat=call('catalog')
            assert set(f['form'] for f in cat['forms'])==set(ws.contract.BRIEFS)
            key=next(r['key'] for r in cat['subjects'] if r['form']=='territory_origin' and r['state']=='pending')
            ctx=call('context',key=key)
            assert ctx['context_hash']==call('context',key=key)['context_hash']
            assert ctx['instructions'] and 'retrieval' in ctx['packet']
            assert 'rulebook_context' in ctx['packet'] and 'editorial_pattern_warnings' in ctx['packet']
            assert '\n'.join(store.db.iterdump())==before
            origin=next(r['key'] for r in cat['subjects'] if r['form']=='gang_origin')
            ob=call('start',forms=['gang_origin'],keys=[origin],max_drafts=1,request_key='native-gang-origin-batch')
            od=call('prepare',batch_id=ob['batch_id'],request_key='native-gang-origin-attempt')
            assert od['context']['packet']['subject_context']
            os=call('save',draft_id=od['draft_id'],output={'paragraphs':['The gang keeps its tools beside the furnace gate.']},checks=CHECKS)
            op=call('publish',draft_id=od['draft_id'],confirm_publish=os['publish_hash'])
            assert op['status']=='published'
            gid=od['context']['before']['gang']['gang_id']
            assert store.gang(gid)['origin_document']['native_author']['draft_id']==od['draft_id']
            rejects(lambda:author.dispatch(store,'catalog',{'thread_id':'some-other-thread'}))
            rejects(lambda:call('context',key='comparison:0:0'))
            start={'forms':['territory_origin'],'keys':[key],'max_drafts':2,'request_key':'native-author-batch-1'}
            batch=call('start',**start)
            assert call('start',**start)==batch
            rejects(lambda:call('start',**{**start,'max_drafts':3}))
            reserve={'batch_id':batch['batch_id'],'key':key,'request_key':'native-author-reservation-1'}
            draft=call('prepare',**reserve)
            assert call('prepare',**reserve)==draft
            rejects(lambda:call('prepare',**{**reserve,'request_key':'native-author-reservation-2'}))
            payload={'paragraphs':['Workers pass the rusted gate on their way to the furnaces.'], 'composition':{'body_heading':'THE FURNACE GATE','closing':''}}
            saved=call('save',draft_id=draft['draft_id'],output=payload,checks=CHECKS)
            assert pop.eligibility(pop.record(store,key))=='pending','Saving published prose'
            assert call('save',draft_id=draft['draft_id'],output=payload,checks=CHECKS)==saved
            rejects(lambda:call('save',draft_id=draft['draft_id'],output={'paragraphs':['Different.']},checks=CHECKS))
            rejects(lambda:call('publish',draft_id=draft['draft_id'],confirm_publish='wrong'))
            published=call('publish',draft_id=draft['draft_id'],confirm_publish=saved['publish_hash'])
            assert published['status']=='published' and published['published_document']['writer_model']=='native-codex'
            assert pop.record(store,key)['active']==0,'Artifact predecessor was not retained'
            assert call('publish',draft_id=draft['draft_id'],confirm_publish=saved['publish_hash'])==published
            assert author.get(store,draft['draft_id'])['context']['before']==draft['context']['before']

            # Explicit generated replacement preserves previous output in its immutable source snapshot.
            replacement_key=next(r['key'] for r in call('catalog')['subjects'] if r['form']=='territory_origin' and r['state']=='existing')
            rejects(lambda:call('start',forms=['territory_origin'],keys=[replacement_key],max_drafts=1,request_key='native-missing-denial'))
            replacement=call('start',forms=['territory_origin'],keys=[replacement_key],mode='replace_generated',max_drafts=1,request_key='native-replacement-1')
            rd=call('prepare',batch_id=replacement['batch_id'],request_key='native-replacement-attempt')
            old=rd['context']['before']
            rs=call('save',draft_id=rd['draft_id'],output=payload,checks=CHECKS)
            assert call('publish',draft_id=rd['draft_id'],confirm_publish=rs['publish_hash'])['status']=='published'
            assert author.get(store,rd['draft_id'])['context']['before']==old

            # Five durable reservations maximum, even with another request key.
            pending=next(r['key'] for r in call('catalog')['subjects'] if r['form']=='fighter_memory' and r['state']=='pending')
            limits=call('start',forms=['fighter_memory'],keys=[pending],max_drafts=10,request_key='native-attempt-limits')
            for n in range(5):
                item=call('prepare',batch_id=limits['batch_id'],key=pending,request_key='native-memory-attempt-'+str(n))
                ms=call('save',draft_id=item['draft_id'],output={'paragraphs':['I left my tools beside the bed and waited for the pain to settle.']},checks=CHECKS)
            rejects(lambda:call('prepare',batch_id=limits['batch_id'],key=pending,request_key='native-memory-attempt-6'))
            call('publish',draft_id=ms['draft_id'],confirm_publish=ms['publish_hash'])
            memory=pop.record(store,pending)
            assert memory['content']=='I left my tools beside the bed and waited for the pain to settle.'
            assert json.loads(memory['content_runs_json'])[0][0]['text']==memory['content']

            # Changed guidelines refuse publication but retain the draft.
            others=next(r['key'] for r in call('catalog')['subjects'] if r['form']=='territory_history' and r['state']=='pending')
            stale=call('start',forms=['territory_history'],keys=[others],max_drafts=1,request_key='native-stale-context')
            sd=call('prepare',batch_id=stale['batch_id'],request_key='native-stale-attempt')
            ss=call('save',draft_id=sd['draft_id'],output=payload,checks=CHECKS)
            rev=ws.save_revision(store,{'scope':'territory_history','instructions':'Changed owner instructions.'})
            ws.activate(store,{'scope':'territory_history','revision_id':rev['revision_id'],'expected_active':None})
            rejects(lambda:call('publish',draft_id=sd['draft_id'],confirm_publish=ss['publish_hash']))
            assert call('status',id=sd['draft_id'])['status']=='draft'
            rejects(lambda:call('prepare',batch_id=stale['batch_id'],key=others,request_key='native-over-batch-limit'))

            # Virtual scenes remain read-only until approval, then become fictional entries only.
            scene=next(r['key'] for r in call('catalog')['subjects'] if r['key'].startswith('scene:'))
            b=call('start',forms=['place_ambient'],keys=[scene],max_drafts=1,request_key='native-scene-batch-1')
            count=store.db.execute('SELECT count(*) FROM narrative_entries').fetchone()[0]
            event_count=store.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]
            d=call('prepare',batch_id=b['batch_id'],request_key='native-scene-attempt-1')
            s=call('save',draft_id=d['draft_id'],output=payload,checks=CHECKS)
            assert store.db.execute('SELECT count(*) FROM narrative_entries').fetchone()[0]==count
            assert d['context']['context_hash']==call('context',key=scene)['context_hash']
            p=call('publish',draft_id=d['draft_id'],confirm_publish=s['publish_hash'])
            assert p['published_document']['provenance_class']=='connective_fiction'
            assert store.db.execute('SELECT count(*) FROM campaign_events').fetchone()[0]==event_count
            assert store.db.execute('SELECT count(*) FROM narrative_entries').fetchone()[0]==count+1
            assert store.db.execute('SELECT count(*) FROM writer_requests').fetchone()[0]==0
            assert store.db.execute('SELECT count(*) FROM codex_review_jobs').fetchone()[0]==0
            remaining=next(r for r in call('catalog')['subjects'] if r['state']=='pending')
            left=remaining['key']
            ab=call('start',forms=[remaining['form']],keys=[left],max_drafts=1,request_key='native-abandon-limit')
            ad=call('prepare',batch_id=ab['batch_id'],request_key='native-abandon-attempt')
            call('abandon',draft_id=ad['draft_id'],reason='Known invalid output retained locally.')
            rejects(lambda:call('prepare',batch_id=ab['batch_id'],key=left,request_key='native-abandon-retry'))
            rejects(lambda:call('abandon',draft_id=published['draft_id'],reason='Cannot erase saved work.'))
            regenerate(store,writer_enabled=False,force=True)
            active=[json.loads(r[0]) for r in store.db.execute('SELECT document_json FROM story_artifacts WHERE active=1')]
            assert any(d.get('native_author') and d.get('writer_model')=='native-codex' for d in active), 'Native provenance lost on routine refresh'
    with_store(check)
    print('Native author checks passed: source reads, all forms, bounded reservations, immutable drafts, safe publication, scenes and no model calls.')


if __name__=='__main__': main()
