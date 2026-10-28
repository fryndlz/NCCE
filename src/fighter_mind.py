"""Persistent present-tense thoughts, separate from the historical memory ledger."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json

VERSION='mind-v1'
def packed(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def candidates(fighter, memories, at=None, store=None, clock=None):
    from story_engine import select_mind
    import fighter_event_clock
    clock=clock or fighter_event_clock.build(memories,store,fighter.get('id'))
    ranked=select_mind(fighter,memories,limit=100,clock=clock)
    result=[]; families=set()
    for memory in ranked:
        tags=set(memory.get('tags',[]))
        if memory.get('baseline') or not memory.get('source_event_ids'):continue
        bodily=bool(tags & {'critical','recovery','injury','captivity','scars','grudge','humiliation'}) and 'return' not in tags
        family='condition' if bodily else 'battle' if tags & {'victory','defeat','battle'} else 'grief' if 'grief' in tags else 'equipment' if tags & {'equipment','weapon'} else 'progress' if tags & {'advancement','growth','skill','promotion'} else 'return' if 'return' in tags else 'social'
        # One reaction per family, anchored to the latest experience rather than
        # keeping an old victory and defeat side by side indefinitely.
        newer=[m for m in ranked if m.get('source_event_ids') and set(m.get('tags',[])) & ({'battle','victory','defeat'} if family=='battle' else {'equipment','weapon'} if family=='equipment' else set())]
        if newer and memory is not max(newer,key=lambda m:(m['score_details']['event_position'],m['memory_key'])):continue
        if family in families:continue
        families.add(family)
        label=memory['label']
        if family=='condition' and 'recovery' in str(fighter.get('status','')).lower() and not fighter.get('effects'):label='Recovering'
        source={k:memory.get(k) for k in ('memory_key','title','occurred_at','observed_at','evidence','source_event_ids')}
        basis={'version':VERSION,'fighter_id':fighter['id'],'family':family,'source':source,
               'condition':{'status':fighter.get('status'),'effects':fighter.get('effects')},
               'identity_corrections':fighter.get('writer_identity_json') or '{}',
               'authored_background':fighter.get('backstory') if 'authored' in str(fighter.get('backstory_source','')) else None}
        key=hashlib.sha256(packed(basis).encode()).hexdigest()[:32]
        result.append({'id':key,'family':family,'label':label,'source_memory_id':memory['id'],
                       'source':source,'score':memory['selection_score'],'score_details':memory['score_details'],
                       'expires_at':None,'condition_bound':bodily,'event_clock':{
                           'basis':'fighter_relevant_events','head':clock['head'],
                           'formation_event_position':memory['score_details']['event_position'],
                           'subsequent_relevant_events':memory['score_details']['subsequent_relevant_events'],
                           'half_life_events':fighter_event_clock.HALF_LIFE_EVENTS,'fixed_expiry':False}})
        if len(result)==4:break
    return result

def packet(store,fighter,gang,candidate):
    import llm_writer, story_prose, writing_director, narrative_context
    identity=writing_director.identity_context(fighter,gang,story_prose.voice_profile(fighter,gang))
    result=llm_writer.memory_packet(store,fighter,gang,candidate['label'],candidate['source']['evidence'],identity,form='fighter_mind')
    result.update(current_state={k:fighter.get(k) for k in ('status','effects','class','type')},
                  causes=[candidate['source']],source_memory_ids=[candidate['source_memory_id']],
                  event_boundary='A present reaction to the cited causes. They are past experiences, not incidents happening again.',
                  narrative_task='Write one short current thought in this fighter’s voice. Express what affects them now; do not retell the event or announce its recording.',
                  lifecycle={'family':candidate['family'],'fixed_expiry':False,'condition_bound':candidate['condition_bound']},
                  event_clock=candidate['event_clock'])
    result.pop('event',None)
    result['generated_background']=narrative_context.origin(store,'fighter_biography',fighter['id'])
    return result

def refresh(store,fighter,gang,memories,at=None):
    import llm_writer, fighter_event_clock
    at=at or datetime.now(timezone.utc).isoformat()
    selected=candidates(fighter,memories,store=store); ids={c['id'] for c in selected}
    for row in store.db.execute("SELECT thought_id,family,packet_json FROM fighter_thoughts WHERE fighter_id=? AND lifecycle='active'",(fighter['id'],)).fetchall():
        if row['thought_id'] not in ids:
            old_state=json.loads(row['packet_json']).get('current_state',{})
            changed=any(old_state.get(field)!=fighter.get(field) for field in ('status','effects'))
            state='resolved' if (row['family']=='condition' and changed) or str(fighter.get('status','')).lower() in ('dead','killed') else 'superseded'
            store.db.execute('UPDATE fighter_thoughts SET lifecycle=?,ended_at=? WHERE thought_id=?',(state,at,row['thought_id']))
    for candidate in selected:
        saved=store.db.execute('SELECT * FROM fighter_thoughts WHERE thought_id=?',(candidate['id'],)).fetchone()
        context=json.loads(saved['packet_json']) if saved else packet(store,fighter,gang,candidate)
        context['cognitive_design']=fighter_event_clock.policy()
        context['lifecycle']={'family':candidate['family'],'fixed_expiry':False,'condition_bound':candidate['condition_bound']}
        context['event_clock']=candidate['event_clock']
        # Accepted wording survives guidance updates. A change to the causes
        # creates another entry; reading a page never requests model work.
        if saved and saved['writer_status']=='ready':
            store.db.execute("UPDATE fighter_thoughts SET lifecycle='active',ended_at=NULL,expires_at=NULL,packet_json=?,source_memory_id=? WHERE thought_id=?",(packed(context),candidate['source_memory_id'],candidate['id']))
            continue
        output,status=llm_writer.write(store,'fighter_mind',context,{'subject_type':'fighter','subject_key':fighter['id'],'subject_name':fighter['name']})
        content='\n\n'.join(llm_writer.paragraph_text(p) for p in output)
        store.db.execute('''INSERT INTO fighter_thoughts(thought_id,fighter_id,family,label,source_memory_id,source_json,packet_json,content,writer_status,lifecycle,expires_at,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,'active',?,?) ON CONFLICT(thought_id) DO UPDATE SET source_memory_id=excluded.source_memory_id,packet_json=excluded.packet_json,content=excluded.content,writer_status=excluded.writer_status,lifecycle='active',expires_at=NULL,ended_at=NULL''',
            (candidate['id'],fighter['id'],candidate['family'],candidate['label'],candidate['source_memory_id'],packed(candidate['source']),packed(context),content,status['status'],candidate['expires_at'],at))

def read(store,fighter,memories,at=None,clock=None):
    import fighter_event_clock
    clock=clock or fighter_event_clock.build(memories,store,fighter.get('id'))
    selected=candidates(fighter,memories,store=store,clock=clock); result=[]; pending=0; errors=0
    for cause in selected:
        row=store.db.execute("SELECT * FROM fighter_thoughts WHERE thought_id=? AND lifecycle='active'",(cause['id'],)).fetchone()
        if not row or row['writer_status']!='ready' or not row['content'].strip():
            pending+=1
            errors+=int(bool(row and row['writer_status']=='error'))
            continue
        source=json.loads(row['source_json'])
        result.append({'id':row['thought_id'],'memory_id':cause['source_memory_id'],'label':row['label'],
                       'content':row['content'],'writer_status':'ready','provenance_class':'inference',
                       'evidence':source['evidence'],'source_event_ids':source['source_event_ids'],
                       'expires_at':None,'event_clock':cause['event_clock'],'selection_score':cause['score'],'score_details':cause['score_details']})
    return result,{'pending':pending,'errors':errors,'candidate_count':len(selected),'max_thoughts':4,'separate_prose':True,'event_clock_head':clock['head']}
