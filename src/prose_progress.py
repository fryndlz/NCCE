"""Read-only coverage of current prose slots, independent of any writing system."""
import json

CATEGORIES = (
    ('fighter_biography','Fighters','Biography','Static background and identity.'),
    ('fighter_memory','Fighters','Memory / observation','One experience, including baseline observations.'),
    ('fighter_reflection','Fighters','Reflection','Connections between earlier memories.'),
    ('fighter_mind','Fighters','Current thought','Current active thoughts; resolved thoughts are excluded.'),
    ('gang_origin','Gangs','Backstory','Sheet-authored background or an existing published native origin.'),
    ('gang_history','Gangs','History','An evolving account of the gang.'),
    ('gang_event','Gangs','Event entry','One recorded gang change.'),
    ('territory_origin','Places','Backstory','The territory’s baseline description.'),
    ('territory_history','Places','History','The territory’s evolving history.'),
    ('place_event','Places','Event entry','A recorded territorial change.'),
    ('place_ambient','Places','Local scene','Existing fictional incidents with no mechanical impact.'),
    ('battle_report','Campaign','Battle report','One recorded engagement.'),
    ('downtime','Campaign','Downtime report','The current inter-battle account for each gang.'),
    ('region_history','Campaign','Regional chronicle','The campaign-wide account.'),
    ('relationship','Relationships','Relationship history','Current recorded gang-pair histories.'),
)
OPEN_ENDED={'fighter_memory','fighter_reflection','fighter_mind','gang_event','place_event','place_ambient','relationship'}


def _load(raw):
    try:return json.loads(raw or '{}')
    except (ValueError,TypeError):return {}


def _body(document):
    if not isinstance(document,dict):return ''
    pieces=[]
    for block in document.get('blocks',[]):
        if not isinstance(block,dict):continue
        if block.get('type') in ('body_paragraph','paragraph','dialogue'):
            pieces.append(str(block.get('text') or ''.join(str(r.get('text','')) for r in block.get('content',[]) if isinstance(r,dict))))
        pieces.append(_body(block))
    return ' '.join(pieces).strip()


def _state(content='',status=None,authored=False):
    if not str(content or '').strip():return 'unwritten'
    if authored:return 'authored'
    if status=='ready':return 'ready'
    if status=='stale':return 'earlier'
    # Errors/placeholders and unaccepted drafts are not completed writing.
    return 'unwritten'


def _row(key,group,label,description,slots,open_ended=False):
    counts={state:sum(value==state for value in slots.values()) for state in ('authored','ready','earlier','unwritten')}
    total=len(slots);completed=counts['authored']+counts['ready'];written=completed+counts['earlier']
    return dict(key=key,group=group,label=label,description=description,total=total,completed=completed,written=written,
                completed_percent=round(100*completed/total,1) if total else None,
                written_percent=round(100*written/total,1) if total else None,
                counts=counts,open_ended=open_ended)


def summary(store):
    """Count current logical records once; never load trials or call a writer."""
    rows=lambda query:[dict(r) for r in store.db.execute(query)]
    gangs=rows('SELECT * FROM gangs WHERE active=1');gids={g['gang_id'] for g in gangs}
    fighters=rows('SELECT * FROM fighters');fighters=[f for f in fighters if f['gang_id'] in gids]
    fids={str(f['id']) for f in fighters}
    places=rows('SELECT * FROM territories WHERE active=1');tids={str(t['id']) for t in places}
    battles=rows('SELECT id,notes FROM battles WHERE active=1')
    slots={key:{} for key,*_ in CATEGORIES}
    artifacts={}
    for a in rows('SELECT scope_type,scope_key,document_json FROM story_artifacts WHERE active=1 ORDER BY generated_at,artifact_id'):
        artifacts[(a['scope_type'],a['scope_key'])]=_load(a['document_json'])
    def document(form,key):
        doc=artifacts.get((form,str(key)),{})
        return _state(_body(doc),doc.get('writer_status'),doc.get('provenance_class') in ('player_authored','canon_authored'))
    for f in fighters:
        source=str(f.get('backstory_source') or '').lower()
        authored=any(s in source for s in ('authored','c-nine story','canon')) and 'mechanic' not in source
        slots['fighter_biography'][str(f['id'])]=_state(f.get('backstory'),authored=True) if authored and str(f.get('backstory') or '').strip() else document('fighter_biography',f['id'])
    for g in gangs:
        slots['gang_history'][g['gang_id']]=document('gang_history',g['gang_id'])
        slots['downtime'][g['gang_id']]=document('downtime',g['gang_id'])
        origin=artifacts.get(('gang_origin',g['gang_id']),{})
        slots['gang_origin'][g['gang_id']]=_state(g.get('backstory'),authored=True) if g.get('backstory_source')=='player-authored / campaign Sheet' and str(g.get('backstory') or '').strip() else document('gang_origin',g['gang_id']) if origin.get('native_author') else 'unwritten'
    for t in places:
        for form in ('territory_origin','territory_history'):slots[form][str(t['id'])]=document(form,t['id'])
    from authored_battles import has_report
    for b in battles:
        stored=artifacts.get(('battle_report',str(b['id'])),{})
        slots['battle_report'][str(b['id'])]='authored' if has_report(b) else 'unwritten' if stored.get('authored_report_revision') else document('battle_report',b['id'])
    if gangs or rows('SELECT id FROM regions'):
        slots['region_history']['campaign']=document('region_history','campaign')
    for m in rows('SELECT fighter_id,memory_key,memory_type,content,writer_status FROM story_memories WHERE active=1 ORDER BY created_at,memory_id'):
        if str(m['fighter_id']) in fids:
            form='fighter_reflection' if m['memory_type']=='reflection' else 'fighter_memory'
            slots[form][(m['fighter_id'],m['memory_key'])]=_state(m['content'],m['writer_status'])
    for t in rows("SELECT thought_id,fighter_id,content,writer_status FROM fighter_thoughts WHERE lifecycle='active'"):
        if str(t['fighter_id']) in fids:slots['fighter_mind'][t['thought_id']]=_state(t['content'],t['writer_status'])
    for e in rows('SELECT * FROM narrative_entries WHERE active=1 ORDER BY created_at,entry_id'):
        if e['scope_type']=='gang' and e['scope_key'] in gids:form='gang_event'
        elif e['scope_type']=='territory' and e['scope_key'] in tids:form='place_ambient' if e['provenance_class']=='connective_fiction' else 'place_event'
        else:continue
        doc=_load(e['document_json']);slots[form][(e['scope_key'],e['entry_key'])]=_state(_body(doc),doc.get('writer_status'))
    # Relationship artifacts are keyed by the gang names, rather than IDs.
    for (form,key),doc in artifacts.items():
        if form=='relationship' and len(set(key.split('|')))==2 and set(key.split('|')).issubset({g['name'] for g in gangs}):
            slots[form][key]=document(form,key)
    categories=[_row(key,group,label,description,slots[key],key in OPEN_ENDED) for key,group,label,description in CATEGORIES]
    from authored_archive import stories
    archive={name:'unwritten' for name in ('The Prospect','The Deep Answers')}
    for story in stories(store):archive[story['title']]=_state(story.get('content'),authored=True)
    return {'categories':categories,'archive':_row('archive','Archive','Authored stories','The two source-bounded archive stories.',archive),
            'generation_enabled':False,'definition':'Completed = non-empty ready prose or authored content. Written also includes retained earlier drafts; it is not a literary quality score. Totals use current records and existing event/scene/thought slots, not future campaign events.'}
