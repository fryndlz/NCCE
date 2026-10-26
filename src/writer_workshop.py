"""Private editorial workbench. Revisions and samples never edit campaign source/canon."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
import writer_contract as contract
import writing_director as director
import narrative_context as context

REVIEW=[
    {'case':0,'verdict':'neither','lean':'A','note':'Territory: almost A, but neither reaches the required quality.'},
    {'case':1,'verdict':'A','lean':'A','note':'Mara: A preferred. B made the note-taking action nonsensical to the reader.'},
    {'case':2,'verdict':'neither','lean':'B','note':'Gang seizure: B would be preferred, but a self-authored Ethernetans report cannot refer to its authors as external third parties.'},
]

def now(): return datetime.now(timezone.utc).isoformat()
def packed(value): return json.dumps(value,ensure_ascii=False,sort_keys=True)
def scope_name(scope):
    if scope!='shared' and scope not in contract.BRIEFS: raise ValueError('Unknown writing form')
    return scope

def defaults(scope,preset='current'):
    scope_name(scope)
    if preset not in ('current','candidate'): raise ValueError('Unknown preset')
    raw=contract.RUNTIME_PATH.read_text(encoding='utf-8-sig')
    if scope=='shared':
        instructions=raw.split('## Voice and craft',1)[1].split('## Context and presentation',1)[0].strip()
        if preset=='candidate':
            import writer_candidate
            instructions=writer_candidate.PATH.read_text(encoding='utf-8-sig')
        return {'scope':scope,'instructions':instructions,'examples':'','label':preset+' shared craft','revision_id':None}
    examples=contract.example_for(scope)
    if preset=='candidate':
        import writer_candidate
        if scope in contract.PERSONAL: examples=writer_candidate.PERSONAL
        elif not (scope=='fighter_biography' or scope.startswith('territory') or scope.startswith('place_')): examples=writer_candidate.COLLECTIVE
    return {'scope':scope,'instructions':contract.BRIEFS[scope],'examples':examples,'label':preset+' '+scope,'revision_id':None}

def revision(store,revision_id,scope=None):
    row=store.db.execute('SELECT * FROM workshop_revisions WHERE revision_id=?',(revision_id,)).fetchone()
    if not row or (scope and row['scope']!=scope): raise ValueError('Saved revision does not match this form')
    return dict(row)

def active(store,scope):
    row=store.db.execute('SELECT revision_id FROM workshop_active WHERE scope=?',(scope,)).fetchone()
    return revision(store,row[0],scope) if row else None

def editor(store,scope):
    scope_name(scope)
    revisions=[dict(r) for r in store.db.execute('SELECT * FROM workshop_revisions WHERE scope=? ORDER BY created_at DESC,revision_id DESC LIMIT 40',(scope,))]
    current=active(store,scope)
    return {'draft':revisions[0] if revisions else current or defaults(scope),'active':current,
            'history':revisions,'builtin':defaults(scope),'candidate':defaults(scope,'candidate')}

def compose(form,shared,specific):
    raw=contract.RUNTIME_PATH.read_text(encoding='utf-8-sig')
    authority=raw.split('## Voice and craft',1)[0]
    presentation='## Context and presentation'+raw.split('## Context and presentation',1)[1]
    return (authority+'\n## Voice and craft\n'+shared['instructions']+'\n'+shared['examples']+
            '\n'+presentation+'\n## Style examples — illustrative guidance, never campaign evidence\n'+specific['examples']+
            '\nREQUESTED FORM: '+form+'\n'+specific['instructions'])

def active_contract(store,form):
    shared=active(store,'shared'); specific=active(store,form)
    if not shared and not specific: return None
    return compose(form,shared or defaults('shared'),specific or defaults(form))

def save_revision(store,body):
    scope=scope_name(body.get('scope'))
    instructions=body.get('instructions'); examples=body.get('examples',''); label=body.get('label','Editorial draft')
    if not isinstance(instructions,str) or not 1<=len(instructions.strip())<=(12000 if scope=='shared' else 4000): raise ValueError('Instructions are empty or too long')
    if not isinstance(examples,str) or len(examples)>8000: raise ValueError('Examples must be at most 8,000 characters')
    if not isinstance(label,str) or len(label)>120: raise ValueError('Revision label is too long')
    item={'revision_id':uuid.uuid4().hex,'scope':scope,'instructions':instructions.strip(),'examples':examples.strip(),'label':label.strip() or 'Editorial draft','created_at':now()}
    with store._lock,store.db:
        store.db.execute('INSERT INTO workshop_revisions VALUES(?,?,?,?,?,?)',tuple(item[k] for k in ('revision_id','scope','label','instructions','examples','created_at')))
    return item

def activate(store,body):
    scope=scope_name(body.get('scope')); rid=body.get('revision_id')
    with store._lock,store.db:
        current=active(store,scope)
        if body.get('expected_active')!=(current or {}).get('revision_id'): raise ValueError('Active instructions changed in another session. Reload before activating.')
        if rid:
            revision(store,rid,scope)
            store.db.execute('INSERT INTO workshop_active VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET revision_id=excluded.revision_id',(scope,rid))
        else: store.db.execute('DELETE FROM workshop_active WHERE scope=?',(scope,))
    return editor(store,scope)

def comparison_review(store):
    import writer_comparison
    value=store.get_state(writer_comparison.STATE_KEY)
    if not value:return []
    saved=json.loads(value); result=[]
    for note in REVIEW:
        item={**note,'label':saved['cases'][note['case']]['label'],'versions':{}}
        for position in range(2):
            row=store.db.execute('''SELECT contract_revision FROM writer_requests JOIN writer_request_details USING(request_row_id)
                WHERE run_id=? AND subject_key=?''',(saved['run_id'],f"{note['case']}:{position}")).fetchone()
            item['versions']['A' if position==0 else 'B']='candidate' if row and row[0]=='editorial-selection-v1' else 'current' if row else 'unknown'
        result.append(item)
    return result

def catalog(store):
    samples=[]
    import writer_comparison
    saved=store.get_state(writer_comparison.STATE_KEY)
    if saved:
        for index,case in enumerate(json.loads(saved)['cases']):
            for pos,entry in enumerate(case['entries']):
                samples.append({'key':f'comparison:{index}:{pos}','form':case['form'],'label':case['label']+' · '+entry['label']+' · comparison'})
    for row in store.db.execute('SELECT artifact_id,scope_type,scope_key,document_json FROM story_artifacts WHERE active=1 ORDER BY scope_type,scope_key'):
        doc=json.loads(row['document_json'])
        if row['scope_type'] in contract.BRIEFS and doc.get('provenance_class') not in ('player_authored','canon_authored'):
            samples.append({'key':'artifact:'+row['artifact_id'],'form':row['scope_type'],'label':row['scope_type'].replace('_',' ')+' · '+str(doc.get('title') or row['scope_key'])})
    for row in store.db.execute('SELECT entry_id,scope_type,event_type,title,provenance_class FROM narrative_entries WHERE active=1 ORDER BY created_at DESC'):
        form='place_ambient' if row['provenance_class']=='connective_fiction' else 'place_event' if row['scope_type']=='territory' else 'gang_event'
        samples.append({'key':'entry:'+row['entry_id'],'form':form,'label':row['scope_type']+' event · '+row['title']})
    for row in store.db.execute('SELECT m.memory_id,m.memory_type,m.title,f.name FROM story_memories m JOIN fighters f ON f.id=m.fighter_id WHERE m.active=1 ORDER BY f.name,m.observed_at DESC'):
        form='fighter_reflection' if row['memory_type']=='reflection' else 'fighter_memory'
        samples.append({'key':'memory:'+row['memory_id'],'form':form,'label':row['name']+' · '+row['title']})
    return samples

def sample(store,key):
    if not isinstance(key,str) or len(key)>160: raise ValueError('Invalid sample')
    kind,_,ident=key.partition(':')
    if kind=='comparison':
        import writer_comparison
        saved=json.loads(store.get_state(writer_comparison.STATE_KEY,'{}'))
        try:
            case_index,pos=map(int,ident.split(':'))
            if case_index not in range(3) or pos not in range(2):raise ValueError()
            case=saved['cases'][case_index]; entry=case['entries'][pos]
            row=store.db.execute('SELECT prompt_json FROM writer_requests JOIN writer_request_details USING(request_row_id) WHERE run_id=? AND subject_key=?',(saved['run_id'],ident)).fetchone()
            saved_request=json.loads(row[0])
            packet=json.loads(saved_request['input'].split('\n',1)[1]); packet.pop('editorial_evaluation_run',None)
            return {'key':key,'form':case['form'],'label':case['label']+' · '+entry['label'],'packet':packet,'document':entry['document'],
                    'instructions_used':saved_request['instructions'],'at':entry['document'].get('occurred_at')}
        except (KeyError,ValueError,TypeError,IndexError): raise ValueError('Comparison sample not found') from None
    if kind=='artifact':
        row=store.db.execute('SELECT * FROM story_artifacts WHERE artifact_id=? AND active=1',(ident,)).fetchone()
        if not row or row['scope_type'] not in contract.BRIEFS: raise ValueError('Document not found')
        doc=json.loads(row['document_json'])
        if doc.get('provenance_class') in ('player_authored','canon_authored'): raise ValueError('Authored source is read-only')
        return {'key':key,'form':row['scope_type'],'label':doc.get('title'),'packet':context.document_packet(store,row['scope_type'],row['scope_key'],doc),'document':doc,'at':doc.get('occurred_at')}
    if kind=='entry':
        row=store.db.execute('SELECT * FROM narrative_entries WHERE entry_id=? AND active=1',(ident,)).fetchone()
        if not row: raise ValueError('Event entry not found')
        form='place_ambient' if row['provenance_class']=='connective_fiction' else 'place_event' if row['scope_type']=='territory' else 'gang_event'
        doc=json.loads(row['document_json'])
        return {'key':key,'form':form,'label':row['title'],'packet':context.document_packet(store,form,row['scope_key'],doc),'document':doc,'at':row['occurred_at'] or row['observed_at']}
    if kind=='memory':
        row=store.db.execute('SELECT * FROM story_memories WHERE memory_id=? AND active=1',(ident,)).fetchone()
        if not row: raise ValueError('Memory not found')
        fighter=dict(store.db.execute('SELECT * FROM fighters WHERE id=?',(row['fighter_id'],)).fetchone())
        gang=dict(store.db.execute('SELECT * FROM gangs WHERE gang_id=?',(fighter['gang_id'],)).fetchone())
        ids=json.loads(row['source_event_ids_json']); event=None
        if ids:
            source=store.db.execute('SELECT * FROM campaign_events WHERE event_id=?',(ids[0],)).fetchone()
            if source: event=dict(source); event['payload']=json.loads(event.pop('payload_json'))
        historical,historical_gang=context.fighter_at_event(store,fighter,gang,event or {},bool(row['baseline']))
        prior=[]
        for mid in json.loads(row['source_observation_ids_json']):
            cited=store.db.execute('SELECT title,content,occurred_at,observed_at FROM story_memories WHERE memory_id=?',(mid,)).fetchone()
            if cited:prior.append(dict(cited))
        form='fighter_reflection' if row['memory_type']=='reflection' else 'fighter_memory'
        import llm_writer as writer
        packet=writer.memory_packet(store,historical,historical_gang,row['title'],json.loads(row['evidence_json']),json.loads(row['writer_context_json']),prior,form,event)
        document=director.direct_document(form,'WORKSHOP-SOURCE',{'title':row['title'],'provenance_class':'inference'},dict(row))
        document['blocks']=[{'type':'body_paragraph','text':row['content']}]
        return {'key':key,'form':form,'label':fighter['name']+' · '+row['title'],'packet':packet,'document':document,'at':row['occurred_at'] or row['observed_at']}
    raise ValueError('Unknown sample')

def trial(store,tid):
    row=store.db.execute('SELECT * FROM workshop_trials WHERE trial_id=?',(tid,)).fetchone()
    if not row:raise ValueError('Workshop trial not found')
    item=dict(row)
    if item['status']=='imported' and item['instructions']=='Imported existing sample; no generation':
        try:item['instructions']=sample(store,item['sample_key']).get('instructions_used','Original generation instructions are unavailable for this legacy sample. The source packet and prose remain preserved.')
        except ValueError:item['instructions']='Original generation instructions are unavailable for this legacy sample. The source packet and prose remain preserved.'
    for key in ('packet','document','usage'):item[key]=json.loads(item.pop(key+'_json'))
    edits=[dict(r) for r in store.db.execute('SELECT * FROM workshop_edits WHERE trial_id=? ORDER BY created_at DESC,edit_id DESC',(tid,))]
    for edit in edits:edit['document']=json.loads(edit.pop('document_json'))
    item['edits']=edits
    item['raw_output']=''
    if item['status']=='error':
        audit=store.db.execute('SELECT response_json FROM writer_requests JOIN writer_request_details USING(request_row_id) WHERE run_id=?',(tid,)).fetchone()
        if audit:
            response=json.loads(audit[0]) or {}
            item['raw_output']='\n'.join(c.get('text','') for part in response.get('output',[]) for c in part.get('content',[]) if c.get('type')=='output_text')
    return item

def home(store):
    import llm_writer as writer
    return {'forms':list(contract.BRIEFS),'samples':catalog(store),'review':comparison_review(store),
            'model':writer.MODEL,'effort':writer.DEFAULT_REASONING_EFFORT,'configured':bool(writer.API_KEY),
            'trials':[dict(r) for r in store.db.execute('SELECT trial_id,label,form,status,created_at FROM workshop_trials ORDER BY created_at DESC LIMIT 40')]}

def preview(store,body):
    selected=sample(store,body.get('sample_key'))
    shared=revision(store,body['shared_revision_id'],'shared') if body.get('shared_revision_id') else defaults('shared')
    specific=revision(store,body['form_revision_id'],selected['form']) if body.get('form_revision_id') else defaults(selected['form'])
    packet_hash=hashlib.sha256(packed(selected['packet']).encode()).hexdigest()
    if body.get('packet_hash') and body['packet_hash']!=packet_hash:raise ValueError('This entry context changed. Select it again to inspect the updated facts before generating.')
    return {**selected,'packet_hash':packet_hash,'instructions':compose(selected['form'],shared,specific),
            'shared_revision_id':shared['revision_id'],'form_revision_id':specific['revision_id']}

def queue(store,body):
    request_key=body.get('request_key')
    if not isinstance(request_key,str) or not 16<=len(request_key)<=100:raise ValueError('A valid request key is required')
    prepared=preview(store,body)
    with store._lock,store.db:
        old=store.db.execute('SELECT trial_id,sample_key,instructions FROM workshop_trials WHERE request_key=?',(request_key,)).fetchone()
        if old:
            if old['sample_key']!=prepared['key'] or old['instructions']!=prepared['instructions']:raise ValueError('Request key already belongs to another draft')
            return trial(store,old['trial_id']),False
        if store.db.execute("SELECT 1 FROM workshop_trials WHERE status IN ('queued','running')").fetchone():raise ValueError('A workshop generation is already running')
        import llm_writer as writer
        if not writer.API_KEY:raise ValueError('Writing provider is not configured; no request was made')
        tid='workshop-'+uuid.uuid4().hex
        store.db.execute('''INSERT INTO workshop_trials(trial_id,request_key,sample_key,form,label,packet_json,instructions,model,effort,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,'queued',?)''',(tid,request_key,prepared['key'],prepared['form'],prepared['label'],packed(prepared['packet']),prepared['instructions'],writer.MODEL,writer.DEFAULT_REASONING_EFFORT,now()))
    return trial(store,tid),True

def execute(store,tid):
    import llm_writer as writer
    item=trial(store,tid)
    if item['status']!='queued':return item
    old_enabled=writer.WRITER_ENABLED
    writer.reset_budget(1,tid); writer.set_enabled(True)
    with store._lock,store.db:store.db.execute("UPDATE workshop_trials SET status='running' WHERE trial_id=?",(tid,))
    document={}; error=''
    try:
        output,status=writer.write(store,item['form'],item['packet'],{'subject_type':'writer_workshop','subject_key':tid,
            'subject_name':item['label'],'contract_revision':'workshop:'+hashlib.sha256(item['instructions'].encode()).hexdigest()[:16]},contract_override=item['instructions'])
        document=director.direct_document(item['form'],tid,{'title':item['packet'].get('subject'),'provenance_class':'inference'},item['packet'].get('event') or item['packet'].get('writer_context') or {})
        document=writer.apply(document,output,status)
        final='ready' if status['status']=='ready' else 'error'; error=status.get('message','')
    except Exception as exc:final='error'; error=str(exc)[:300]
    finally:
        writer.set_enabled(old_enabled)
        with store._lock,store.db:
            store.db.execute('UPDATE workshop_trials SET status=?,document_json=?,usage_json=?,error=?,finished_at=? WHERE trial_id=?',
                (final,packed(document),packed(writer.run_summary()),error,now(),tid))
    return trial(store,tid)

def save_edit(store,body):
    original=trial(store,body.get('trial_id'))
    content=body.get('body')
    if not isinstance(content,str) or not content.strip() or len(content)>16000:raise ValueError('Edited prose must contain 1–16,000 characters')
    fields=body.get('composition') or {}
    allowed=('heading','subject','body_heading','closing_label','closing','signoff')
    if not isinstance(fields,dict) or any(k not in allowed or not isinstance(v,str) or len(v)>800 for k,v in fields.items()):raise ValueError('Invalid document heading or closing')
    document=dict(original['document']); document['blocks']=[{'type':'body_paragraph','text':p.strip()} for p in content.split('\n\n') if p.strip()]
    document['composition']=fields; document['writer_status']='ready'; document['workshop_provenance']='owner_edited_style_sample'
    document.pop('writer_message',None); document['writer_model']=None
    if fields.get('body_heading'):document['blocks'].insert(0,{'type':'section_label','text':fields['body_heading']})
    if fields.get('closing'):document['blocks'].append({'type':'internal_note','text':fields.get('closing_label',''),'blocks':[{'type':'body_paragraph','text':fields['closing']}]})
    document['termination']={'type':'record_termination','text':fields.get('signoff','')}
    with store._lock,store.db:store.db.execute('INSERT INTO workshop_edits VALUES(?,?,?,?)',(uuid.uuid4().hex,original['trial_id'],packed(document),now()))
    return trial(store,original['trial_id'])

def import_sample(store,body):
    selected=sample(store,body.get('sample_key'))
    tid='workshop-'+uuid.uuid4().hex
    import llm_writer as writer
    with store._lock,store.db:
        store.db.execute('''INSERT INTO workshop_trials(trial_id,request_key,sample_key,form,label,packet_json,instructions,model,effort,status,document_json,usage_json,created_at,finished_at)
            VALUES(?,?,?,?,?,?,?,?,?,'imported',?,?,?,?)''',(tid,'import-'+uuid.uuid4().hex,selected['key'],selected['form'],selected['label'],packed(selected['packet']),
                selected.get('instructions_used','Original generation instructions are unavailable for this legacy sample. The source packet and prose remain preserved.'),
                writer.MODEL,writer.DEFAULT_REASONING_EFFORT,packed(selected['document']),packed({'requests_attempted':0}),now(),now()))
    return trial(store,tid)
