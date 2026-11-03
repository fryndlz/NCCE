"""Read/format compatibility for stored prose. The old writing system is removed.

This module cannot call a provider or be enabled by configuration. Its small
compatibility surface lets the event/memory engine preserve existing records.
"""
import writer_contract
MODEL=None
API_KEY=''
WRITER_ENABLED=False
FORMATTING_REVISION=writer_contract.REVISION
ALLOWED_MARKS={'critical_status','error_or_missing','machine_error'}
PAUSED={'status':'paused','message':'Writing is paused while a replacement is prepared.'}
_run_stats={}

def availability():
 return {'configured':False,'provider':None,'model':None,'status':'removed','calls_used':0,'call_budget':0}

def reset_budget(limit=None,run_id=None):
 global _run_stats
 _run_stats={'run_id':run_id,'call_limit':0,'drafts_requested':0,'requests_attempted':0,'requests_succeeded':0,'requests_failed':0,'cache_hits':0,'blocked_by_budget':0,'input_tokens':0,'output_tokens':0,'cached_input_tokens':0,'reasoning_tokens':0}

def run_summary():
 return dict(_run_stats)

def set_enabled(value):
 # Deliberately inert even if a legacy caller or old environment requests True.
 pass

def write(store,form,packet,trace=None,contract_override=None):
 return [],dict(PAUSED)

def normalize_paragraphs(paragraphs):
 if not isinstance(paragraphs,list) or not 1<=len(paragraphs)<=6:
  raise RuntimeError('Writing provider returned invalid prose')
 normalized=[]
 for paragraph in paragraphs:
  if isinstance(paragraph,str):
   runs=[{'text':paragraph.strip(),'marks':[]}]
  elif isinstance(paragraph,dict) and isinstance(paragraph.get('runs'),list):
   runs=[]
   for run in paragraph['runs']:
    if not isinstance(run,dict) or not isinstance(run.get('text'),str) or not isinstance(run.get('marks',[]),list):
     raise RuntimeError('Writing provider returned invalid prose formatting')
    raw_marks=run.get('marks',[])
    if any(not isinstance(mark,str) or mark not in ALLOWED_MARKS for mark in raw_marks):
     raise RuntimeError('Writing provider returned unsupported prose formatting')
    marks=list(dict.fromkeys(raw_marks))
    text=run['text']
    if text:runs.append({'text':text,'marks':marks})
  else:
   raise RuntimeError('Writing provider returned invalid prose formatting')
  plain=''.join(run['text'] for run in runs).strip()
  if not plain or len(plain)>1800: raise RuntimeError('Writing provider returned invalid prose')
  if runs:
   runs[0]['text']=runs[0]['text'].lstrip()
   runs[-1]['text']=runs[-1]['text'].rstrip()
   runs=[run for run in runs if run['text']]
  normalized.append({'runs':runs})
 return normalized

def normalize_result(value):
 paragraphs=normalize_paragraphs(value.get('paragraphs',[]) if isinstance(value,dict) else value)
 composition=value.get('composition',{}) if isinstance(value,dict) else {}
 allowed={'heading','subject','body_heading','closing_label','closing','signoff'}
 if not isinstance(composition,dict) or any(key not in allowed or not isinstance(text,str) or len(text)>800 for key,text in composition.items()):
  raise RuntimeError('Writing provider returned invalid document composition')
 return paragraphs,{key:text.strip() for key,text in composition.items()}

def paragraph_text(paragraph):
 if isinstance(paragraph,str): return paragraph
 return ''.join(run.get('text','') for run in paragraph.get('runs',[]))

def paragraph_runs(paragraph):
 if isinstance(paragraph,str): return [{'text':paragraph,'marks':[]}]
 return [{'text':run['text'],'marks':list(run.get('marks',[]))} for run in paragraph.get('runs',[]) if run.get('text')]

def reflection_observations(memories):
 return [{'id':m.get('id') or m.get('memory_id'),'title':m['title'],'tags':m['tags'],'importance':m['importance'],
          'occurred_at':m.get('occurred_at'),'observed_at':m.get('observed_at'),
          'experience':m['content'] if m.get('writer_status')=='ready' else None,
          'evidence':m['evidence'],'source_event_ids':m['source_event_ids']} for m in memories]

def memory_packet(store,fighter,gang,title,evidence,identity,prior=(),form='fighter_memory',event=None):
 import narrative_context
 import fighter_event_clock
 identity=identity if isinstance(identity,dict) else {}
 facets=identity.get('inferred_identity',[])
 # Only a few elevated stimulus topics enter the model packet. Their weights
 # guide attention and are not the event's mechanical importance or salience.
 weights=sorted((x for x in identity.get('stim_weights',[]) if x.get('weight',1)>1),key=lambda x:(-x.get('weight',1),x.get('topic','')))[:5]
 packet={'subject':fighter.get('name'),'event_title':title,'mechanical_evidence':list(evidence or [])[:12],
         'identity':identity.get('identity',{}),'inferred_identity':facets[:8],
         'stimulus_attention':weights,
         'event_boundary':'This packet concerns one recorded event only. Treat all other context as a limited perspective lens, not as additional events or proof.',
         'narrative_task':'Connect this event to one supported, concrete concern in the fighter’s life. Do not narrate unrelated backstory or merge separate mechanical changes.',
         'related_observations':list(prior)[-4:] if form=='fighter_reflection' else [],
         'knowledge_boundary':identity.get('knowledge_boundary')}
 packet['authored_background']=narrative_context.authored(fighter)
 packet['background_instruction']='Background establishes voice and prior life only; none of its incidents are happening again in this event.'
 packet['cognitive_design']=fighter_event_clock.policy()
 if form=='fighter_reflection':
  packet['event_boundary']='Interpret connections among the cited observations. They remain separate past experiences; do not invent another incident.'
  packet['narrative_task']='Reflect on how the cited experiences connect, change an expectation, or shape an intention. Use only their supported relationships, not an unrelated life lesson.'
  packet['source_observation_ids']=[item.get('id') for item in prior if isinstance(item,dict) and item.get('id')]
 if store:
  packet['generated_background']=narrative_context.origin(store,'fighter_biography',fighter.get('id'),(event or {}).get('occurred_at') or (event or {}).get('observed_at')) if event else None
 if event and form!='fighter_reflection':
  packet['event']={k:event.get(k) for k in ('event_id','event_type','occurred_at','observed_at','payload')}
 if gang.get('name'):
  packet['gang_context']={'name':gang.get('name'),'affiliation':gang.get('gang_type')}
 return packet

def write_memory(store,fighter,gang,title,evidence,identity,prior=(),form='fighter_memory',event=None):
 packet=memory_packet(store,fighter,gang,title,evidence,identity,prior,form,event)
 return write(store,form,packet,{'subject_type':'fighter','subject_key':fighter.get('id'),'subject_name':fighter.get('name')})

def write_document(store,scope,key,document):
 import narrative_context
 if document.get('provenance_class') in {'player_authored','canon_authored'}:
  return [],{'status':'ready','authored':True}
 form={'gang_origin':'gang_origin','territory_origin':'territory_origin'}.get(scope,scope)
 packet=narrative_context.document_packet(store,form,key,document)
 return write(store,form,packet,{'subject_type':scope,'subject_key':key,'subject_name':document.get('title')})

def apply(document,paragraphs,status):
 if status.get('authored') or document.get('provenance_class') in {'player_authored','canon_authored'}:
  return dict(document)
 result=dict(document); result['blocks']=[{'type':'body_paragraph','text':paragraph_text(p),'content':paragraph_runs(p)} for p in paragraphs]
 composition=status.get('composition') or {}
 if composition:
  result['composition']=composition
  if composition.get('body_heading'): result['blocks'].insert(0,{'type':'section_label','text':composition['body_heading']})
  if composition.get('closing'): result['blocks'].append({'type':'internal_note','text':composition.get('closing_label',''),'blocks':[{'type':'body_paragraph','text':composition['closing']}]})
  result['termination']={'type':'record_termination','text':composition.get('signoff','')}
 if status.get('status')=='ready': result['writer_revision']=status.get('revision',FORMATTING_REVISION)
 result['writer_status']=status.get('status','pending')
 if status.get('contract_hash'):result['writer_contract_hash']=status['contract_hash']
 if status.get('message'): result['writer_message']=status['message']
 else: result.pop('writer_message',None)
 result['writer_model']=MODEL if status.get('status')=='ready' else None
 return result

def retain_previous(document,previous,status):
 """Keep a usable old draft visible when a new draft is unavailable/rejected."""
 if not previous or previous.get('writer_status') not in ('ready','stale') or status.get('status')=='ready':
  return document
 result=dict(document)
 result['blocks']=previous.get('blocks',[])
 for key in ('composition','termination','writer_revision','native_author'):
  if key in previous: result[key]=previous[key]
 if previous.get('native_author'):result['writer_model']=previous.get('writer_model','native-codex')
 result['writer_status']=previous.get('writer_status','ready')
 result['writer_model']=previous.get('writer_model')
 if 'writer_contract_hash' in previous:result['writer_contract_hash']=previous['writer_contract_hash']
 if status.get('status')=='paused':
  result.pop('writer_message',None)
  return result
 if status.get('status')=='error':
  result['writer_message']='Earlier draft retained; the replacement failed validation or the writing provider failed.'
 else:
  result['writer_message']='Earlier draft retained; no replacement was produced in this run.'
 return result


reset_budget()
