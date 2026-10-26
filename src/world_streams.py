"""Persistent, versioned gang/place accounts; ambient fiction never enters the ledger."""
from datetime import datetime, timezone
import hashlib
import json

import writing_director as director
import llm_writer


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def hash_of(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def read_stream(store, scope, key):
    rows = store.db.execute('SELECT * FROM narrative_entries WHERE scope_type=? AND scope_key=? AND active=1 ORDER BY coalesce(occurred_at,observed_at,created_at) DESC,entry_key', (scope,str(key)))
    result=[]
    for row in rows:
        item=dict(row)
        item['document']=json.loads(item.pop('document_json'))
        item['source_event_ids']=json.loads(item.pop('source_event_ids_json'))
        item['continuity']=json.loads(item.pop('continuity_json'))
        item['date_display']=item['document'].get('date_display')
        result.append(item)
    return result


def save_entry(store, scope, key, entry_key, kind, title, blocks, evidence, event=None,
               previous=(), provenance='inference', created_at=None, details=()):
    event=event or {}
    old_draft=store.db.execute('''SELECT document_json FROM narrative_entries WHERE scope_type=? AND scope_key=? AND entry_key=?
        ORDER BY created_at DESC LIMIT 1''',(scope,str(key),entry_key)).fetchone()
    old_document=json.loads(old_draft[0]) if old_draft else None
    created_at=created_at or datetime.now(timezone.utc).isoformat()
    source_ids=[event['event_id']] if event.get('event_id') else []
    # The citation chain is narrative continuity, never additional mechanical evidence.
    continuity={'previous_entry_ids':list(previous)[-2:], 'invented_details':list(details)}
    record={'occurred_at':event.get('occurred_at'), 'observed_at':event.get('observed_at'),
            'generated_at':created_at, 'provenance_class':provenance}
    doc=director.direct_document('place_ambient' if provenance=='connective_fiction' else 'place_event' if scope=='territory' else 'gang_event',
                                entry_key, {'title':title,'blocks':blocks,'evidence':evidence,'source_event_ids':source_ids,
                                            'source_ids':[event['source_id']] if event.get('source_id') else [],
                                            'provenance_class':provenance},record)
    doc['writer_context']={'scope':scope,'scope_key':str(key),'event_type':event.get('event_type') or 'ambient_report',
                           'event':event.get('payload',{}),'continuity':continuity}
    if previous:
        doc['writer_context']['continuity_reference']={
            'earlier_entry_ids':list(previous)[-2:],
            'instruction':'Earlier generated prose is not evidence; use only the event and facts in this packet.'}
    paragraphs,writer_status=llm_writer.write_document(store,'place_ambient' if provenance=='connective_fiction' else 'place_event' if scope=='territory' else 'gang_event',entry_key,doc)
    doc=llm_writer.apply(doc,paragraphs,writer_status)
    if old_document and old_document.get('writer_status') in ('ready','stale') and writer_status.get('status')!='ready' and not llm_writer.WRITER_ENABLED:
        doc['blocks']=old_document.get('blocks',[])
        doc['writer_status']='stale'
        doc['writer_message']='Existing draft retained; the updated writing rules have not been run for this entry.'
    if event.get('source_locator'):
        doc['source_locator']=event['source_locator']
    # Do not make a new version merely because a refresh happened later.
    semantic={k:v for k,v in doc.items() if k!='date_display'}
    entry_id=hash_of([scope,str(key),entry_key,semantic,continuity])[:32]
    old=store.db.execute('SELECT created_at,document_json FROM narrative_entries WHERE entry_id=?',(entry_id,)).fetchone()
    if old:
        created_at=old['created_at']
        doc=json.loads(old['document_json'])
    store.db.execute('UPDATE narrative_entries SET active=0 WHERE scope_type=? AND scope_key=? AND entry_key=?',(scope,str(key),entry_key))
    store.db.execute('''INSERT INTO narrative_entries(entry_id,scope_type,scope_key,entry_key,event_type,title,document_json,occurred_at,observed_at,created_at,provenance_class,source_event_ids_json,continuity_json,generation_version,active)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(entry_id) DO UPDATE SET active=1''',
                     (entry_id,scope,str(key),entry_key,kind,title,packed(doc),record['occurred_at'],record['observed_at'],created_at,provenance,packed(source_ids),packed(continuity),director.VERSION))
    for event_id in source_ids:
        store.db.execute('''INSERT INTO narrative_evidence(artifact_type,artifact_key,event_id,evidence_role,created_at)
            SELECT 'world_entry',?,?, 'generation_source',? WHERE NOT EXISTS
            (SELECT 1 FROM narrative_evidence WHERE artifact_type='world_entry' AND artifact_key=? AND event_id=?)''',
            (entry_id,event_id,created_at,entry_id,event_id))
    for source_id in doc.get('source_ids',[]):
        if store.db.execute('SELECT 1 FROM provenance_sources WHERE source_id=?',(source_id,)).fetchone():
            store.db.execute('''INSERT INTO narrative_evidence(artifact_type,artifact_key,source_id,evidence_role,created_at)
                SELECT 'world_entry',?,?,'source_context',? WHERE NOT EXISTS
                (SELECT 1 FROM narrative_evidence WHERE artifact_type='world_entry' AND artifact_key=? AND source_id=?)''',
                (entry_id,source_id,created_at,entry_id,source_id))
    return entry_id


def paragraph(text):
    return {'type':'body_paragraph','text':text}


def state_of(territory):
    try:
        return json.loads(territory.get('mechanics_json') or '{}')
    except ValueError:
        return {}


def locate_place(state, territories, name=None):
    """Only a unique identity/card/name can attach a mechanical event to a place."""
    state=state or {}
    source=state.get('source_territory_key') or state.get('Territory ID') or state.get('territory_id')
    card=state.get('Card') or state.get('card')
    if source:
        candidates=[t for t in territories if str(t.get('source_territory_id'))==str(source)]
        if len(candidates)==1:
            return candidates[0]
    if card:
        candidates=[t for t in territories if t.get('card')==card]
        if len(candidates)==1:
            return candidates[0]
    name=name or state.get('Territory') or state.get('territory')
    candidates=[t for t in territories if str(name or '').casefold() in {str(x).casefold() for x in [t.get('territory',''),*t.get('_aliases',[])]}]
    return candidates[0] if len(candidates)==1 else None


def local_focus(name):
    text=name.casefold()
    for word, values in (
        ('promethium',('fuel gantries','access to the stored fuel','fuel')),
        ('smelt',('furnace doors','the next working shift','heat')),
        ('mine',('pit entrances','the route back from the workings','ore')),
        ('toll',('crossing gates','permission to pass','passage')),
        ('settlement',('hab doors','the daily market','food')),
        ('corpse',('collection bays','the work of the reclamation crews','collection')),
        ('water',('pump housings','the supply of drinkable water','water')),
        ('ruin',('broken accessways','a usable way through the old structure','salvage')),
    ):
        if word in text:
            return values
    return ('bulkhead approaches','the routes used by workers and traders','supplies')


def place_event_text(territory, event, battle=None):
    p=event.get('payload') or {}; kind=event.get('event_type','')
    name=territory['territory']; feature,stake,_=local_focus(name)
    if battle:
        winner=battle.get('winner')
        return ('The account of the contested approaches',
                f"The surviving return places an armed contest at {name}. For those who depend on {stake}, its conclusion is a question of who can make a demand at the {feature}. " +
                (f"The return names {winner} as the successful party. It does not establish a transfer of title by itself." if winner else 'The surviving account leaves the result unsettled.'))
    if kind=='territory_holder_changed':
        return ('A different name at the gate',f"The registered claim to {name} now answers to a different holder. Whoever approaches the {feature} must reckon with a new authority over {stake}. The old claim remains in the earlier accounts; a changed title cannot remove that history.")
    if kind=='territory_type_changed':
        return ('The place entered under another name',f"The record once described this ground as {p.get('previous_name') or 'an earlier holding'}. It now calls it {p.get('territory') or name}. The earlier description remains in the archive. What that amendment means for those who use the place has not yet been independently described.")
    if kind=='territory_unlisted':
        return ('A claim absent from the return', 'The latest return leaves this place out. No account has yet established whether the omission marks abandonment, a lost claim, or a correction to the register. Its earlier history remains open.')
    if kind=='territory_listed':
        return ('A place enters the district account',f"A return now includes {name}. Its claim has become visible in the district register; the work and passage through the {feature} acquire another name to answer to.")
    changes=p.get('changes') or {}
    ruined=next((v.get('after') for k,v in changes.items() if k.lower()=='ruined'),None)
    if ruined is True:
        return ('The workings entered as ruined',f"The return now marks this ground as ruined. The {feature} belong to an interrupted use of the place; any later account of {stake} must begin with that break.")
    if ruined is False:
        return ('The ruin classification is lifted',f"The return no longer classifies the place as ruined. That amendment reopens a question over {stake}; it does not tell us which work has been completed or who carried it out.")
    return ('An amendment to the local record',f"The return for {name} has been amended. The {feature} remain the point at which a changed register meets ordinary use; the extent of any local disruption is unrecorded.")


def gang_event_text(gang, event, battle=None):
    p=event.get('payload') or {}; kind=event.get('event_type','')
    person=next((s.get('display_name') for s in event.get('subjects',[]) if s.get('entity_type')=='fighter'),'one of our own')
    if battle:
        won=battle.get('winner')==gang['name']
        return ('A claim to carry forward', ('The engagement is entered in our favour. That result gives the next demand weight, while leaving us to account for what it cost.' if won else
                'The engagement is entered against us. The next claim will be made in the shadow of this one; it is a result to reckon with, not an account of what any one fighter did.') if battle.get('winner') else 'The engagement has no settled verdict in the surviving return. The unanswered claim accompanies the gang into the next interval.')
    if kind.startswith('territory_'):
        return ('The shape of our holding', 'The ground attached to the gang’s name has an amended entry. Routes, obligations and expectations will have to be read against the new return as well as the old.')
    if kind=='fighter_status_changed':
        state=str(p.get('after') or '').lower()
        if state in ('dead','killed'):
            return ('A name retained in the roll',f'{person} is entered among the dead. The roll can close a personnel file more easily than the gang can close the place a familiar presence occupied.')
        if state=='active':
            return ('A name returned to service',f'{person} is entered as available again. The earlier absence remains in the account; the return gives the gang another person to reckon with when work is allocated.')
        return ('A place in the line',f'A personnel return changes the condition of {person}. Their place in the gang has to be read against that amendment; the earlier entry remains part of the same account.')
    if kind=='fighter_effects_changed':
        return ('The medical entry beside a familiar name',f'The medical entry beside {person} has changed. The gang’s plans now have to carry that return as well as its ambitions. No individual account has yet explained how the condition was incurred.')
    if kind=='fighter_xp_changed':
        if isinstance(p.get('before'),(int,float)) and isinstance(p.get('after'),(int,float)) and p['after']<p['before']:
            return ('A revision to the service account',f'The service account for {person} has been revised downward without a reason beside the amendment. Earlier service remains in the file; this revision supplies no account of a fresh lesson.')
        return ('What the service account retains',f'The service account for {person} has been amended. Experience is credited without a named act attached to it; the gang has a changed assessment to carry into the work that follows.')
    if kind in ('fighter_skills_changed','fighter_advancement_changed'):
        return ('A practiced habit enters the account',f'The return recognizes a change in {person}’s practiced capabilities. The gang can begin to expect something different of familiar hands, though no single action in the surviving record explains the change.')
    if kind in ('fighter_weapons_changed','fighter_wargear_changed'):
        return ('Different tools in familiar hands',f'The equipment account attached to {person} has changed. The next allocation will have to be made with the new arrangement in mind; the return does not describe a sale, gift or field trial.')
    if kind=='fighter_kills_changed':
        return ('The cost entered against a name',f'The record of deaths credited to {person} has been amended. It gives the gang a tally to carry without preserving the circumstances or identifying who witnessed them.')
    if kind=='gang_reputation_changed':
        return ('The weight carried by our name','The standing attached to the gang’s name has changed. A reputation is an expectation carried into the next meeting; the return cannot tell us how each person hearing the name will answer it.')
    if kind=='fighter_recruited':
        return ('Another name enters', 'Another name is entered among the gang. A place in the return brings expectations that a name alone cannot yet fulfill.')
    if kind=='fighter_unlisted':
        return ('An absent name', 'A name is absent from the latest roll. The omission has no settled explanation; earlier service has not been erased.')
    if kind=='gang_alignment_changed':
        return ('The permissions surrounding our name', 'The authorities have changed the column in which they place the gang. Familiar arrangements must now be judged under a different public classification.')
    if kind=='gang_credits_changed':
        return ('The common account', 'The common account has changed. What can be promised and what must wait will be measured against this return; the ledger does not record how the balance was reached.')
    return ('What the amended return asks of us', 'Another return alters what can be expected of the gang. The change joins the earlier claims and obligations; the next decision must answer to both.')


def local_reconstruction(name, kind, prior=False):
    feature,stake,resource=local_focus(name)
    if kind=='territory_holder_changed':
        text=f'The old collection notice at the {feature} has been turned to the wall. Residents stop to read the fresh directions before joining the queue. Those who arrive with yesterday’s permission are being sent back to ask again.'
    elif kind=='territory_type_changed':
        text='Delivery tickets still carry the old name. The new one has been painted over the work gate, but the stallholders keep giving directions as they always did. For now, finding the place requires knowing both.'
    elif kind=='territory_unlisted':
        text=f'The copy of the district register beside the {feature} now has a gap where this place used to be. The people who work here still need {resource}; absence from a list has not settled who will answer their requests.'
    elif kind=='territory_state_changed':
        text=f'A fresh notice has been fastened beside the {feature}. People read it on the way to work, then compare it with what they were told on the previous shift. Whoever keeps the queue moving has begun carrying both versions.'
    else:
        text=f'The traders at the {feature} have started chalking usable approaches beside their prices. The argument is over {stake}: which way to go, whose directions to trust, whether to wait for another shift. Someone has put a price on a piece of chalk.'
    if prior:
        text+=' An older notice has been kept beneath the new one rather than thrown away; residents still point to it when the accounts differ.'
    return text


def places_with_aliases(store, events=None):
    all_places=[dict(r) for r in store.db.execute('SELECT * FROM territories ORDER BY active DESC,id')]
    for place in all_places:
        origin=store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type='territory_origin' AND scope_key=? AND active=1",(str(place['id']),)).fetchone()
        place['_aliases']=[json.loads(origin[0]).get('title')] if origin else []
    if events is None:
        events=[{'event_type':'territory_type_changed','payload':json.loads(row[0])} for row in store.db.execute("SELECT payload_json FROM campaign_events WHERE event_type='territory_type_changed'")]
    for event in events:
        p=event.get('payload') or {}
        if event.get('event_type')=='territory_type_changed':
            place=locate_place(p.get('after_state'),all_places,p.get('territory'))
            if place:
                place['_aliases'].extend([p.get('previous_name'),p.get('territory')])
    return all_places


def association_notes(store, battles):
    places=places_with_aliases(store)
    return [{'battle_id':battle['id'],'territory':battle['territory'],'date':battle.get('date'),
             'text':'The source names this location without uniquely identifying one place record. The battle is retained in the battle and gang accounts.'}
            for battle in battles if battle.get('territory') and not locate_place({},places,battle['territory'])]


def rebuild(store, gangs, territories, battles, events, current_battle, evidence_for, generated_at):
    all_places=places_with_aliases(store,events)
    store.db.execute("UPDATE narrative_entries SET active=0 WHERE provenance_class='inference'")
    continuity={}
    def add(scope,key,entry_key,event,title,text,evidence):
        prior=continuity.setdefault((scope,str(key)),[])
        # Referring to earlier returns does not invent persistent physical damage.
        if prior:
            text += ' Earlier accounts remain attached to this entry.'
        details=[]
        blocks=[paragraph(text)]
        if scope=='territory':
            place=next(t for t in all_places if str(t['id'])==str(key))
            event_name=(event.get('payload') or {}).get('territory') or place['territory']
            local_text=local_reconstruction(event_name,event.get('event_type',''),bool(prior))
            details=[local_text]
            blocks=[{**paragraph(local_text),'provenance_class':'connective_fiction'},
                    {'type':'evidence_excerpt','source':'Register annotation · compiled from the cited return','text':text}]
            evidence=list(evidence)+['Local notices, queues and reactions are invented connective detail. The cited event alone establishes campaign facts.']
        entry=save_entry(store,scope,key,entry_key,event.get('event_type','record'),title,blocks,evidence,event,prior,created_at=generated_at,details=details)
        prior.append(entry)
    # Current battle projection chooses the corrected event; removed/superseded
    # accounts stay inactive rather than becoming current territorial history.
    anchors=[]
    for battle in battles:
        event=current_battle(battle,events)
        if not event:
            # Some legacy baseline rows have no factual event anchor.
            snapshot=store.latest_snapshot() or {}
            event={'event_type':'battle_result','payload':battle,'occurred_at':battle.get('date'),
                   'source_id':snapshot.get('source_id','baseline:snapshot-0001'),
                   'source_locator':f"Battles!row {battle.get('source_row') or 'unknown'}"}
        anchors.append((event,battle))
    items=[(e,None) for e in events if not e.get('event_key','').startswith('baseline:') and e.get('event_type') not in ('battle_result','battle_record_corrected','battle_record_removed')]+anchors
    for event,battle in sorted(items,key=lambda pair:(pair[0].get('occurred_at') or pair[0].get('observed_at') or '',pair[0].get('event_id',''))):
        p=event.get('payload') or {}; kind=event.get('event_type','')
        if kind=='fighter_stat_changed' and p.get('field')=='Cost':
            continue
        evidence=evidence_for(event)
        if battle:
            evidence=[f"{battle.get('attacker')} / {battle.get('defender')}",f"Scenario: {battle.get('scenario')}",f"Winner: {battle.get('winner') or 'Unrecorded'}",f"Territory: {battle.get('territory') or 'Unrecorded'}",'Individual attendance, witness accounts and infrastructure damage are not recorded.']
            place=locate_place({},all_places,battle.get('territory'))
        elif kind.startswith('territory_'):
            place=locate_place(p.get('after_state') or p.get('state'),all_places,p.get('territory'))
        else:
            place=None
        entry_key='battle:'+str(battle.get('source_battle_key') or battle['id']) if battle else event.get('event_id')
        if place:
            title,text=place_event_text({**place,'territory':p.get('territory') or place['territory']},event,battle)
            add('territory',place['id'],entry_key,event,title,text,evidence)
        affected={str(s['entity_key']) for s in event.get('subjects',[]) if s.get('entity_type')=='gang'}
        if battle:
            affected.update(str(g['gang_id']) for g in gangs if g['name'] in (battle.get('attacker'),battle.get('defender'),battle.get('winner'),battle.get('territory_claimer')))
        for gang in gangs:
            if str(gang['gang_id']) in affected:
                title,text=gang_event_text(gang,event,battle)
                add('gang',gang['gang_id'],entry_key,event,title,text,evidence)


AMBIENT = {
    'c-nine': ('The quiet shift', 'A notice on the work gate asks residents to attend a voluntary meal after shift. Someone has crossed out “voluntary” and written it again in a smaller hand. The kitchen says it is only trying to make the queues orderly.'),
    'orlock': ('A complaint over the loading bell', 'The loading bell has begun sounding before the market stalls close. Traders complain that their customers are being called back to work; the notice beside the bell says the hours have not changed.'),
    'van saar': ('A box no one will open', 'A sealed measuring box has appeared beside the public lumen switch. A paper seal forbids interference. The stallholders have moved their awnings so they can still see the display without standing beside it.'),
    'palanite': ('The queue for inspection', 'A new inspection notice has made the morning queue longer. One resident has started selling numbered scraps of paper. The notice says nothing about scraps of paper.'),
    'enforcer': ('The queue for inspection', 'A new inspection notice has made the morning queue longer. One resident has started selling numbered scraps of paper. The notice says nothing about scraps of paper.'),
    'squat': ('Chalk on the bulkhead', 'Survey marks have appeared on a bulkhead the stallholders use for prices. Nobody agrees whether the chalk denotes a claim or a repair. The prices are now written carefully between the marks.'),
    'ironhead': ('Chalk on the bulkhead', 'Survey marks have appeared on a bulkhead the stallholders use for prices. Nobody agrees whether the chalk denotes a claim or a repair. The prices are now written carefully between the marks.'),
    'escher': ('The jars behind the counter', 'A medicine seller now keeps the empty jars instead of throwing them out. Customers have started bringing their own lids. The seller insists this is a matter of housekeeping and refuses to elaborate.'),
    'goliath': ('A new use for the weighing scale', 'The market scale has become the subject of a lifting contest. Its owner has posted a repair charge beside the weights and begun taking the charge before anyone touches the beam.'),
    'cawdor': ('A shrine beside the ration hatch', 'A small shrine has appeared beside the ration hatch. Someone leaves it a spoonful before every meal; by the next shift the spoon is clean. The hatch keeper denies responsibility for either part of the custom.'),
    'delaque': ('The shutters stay closed', 'The upper shutters remain closed even during market hours. A trader says the room is empty. Another points out that the dust below its door is disturbed every morning.'),
}


def maybe_ambient(store, gangs, territories, at=None, chance=0.25, limit=2):
    if not llm_writer.API_KEY:
        return 0
    at=at or datetime.now(timezone.utc)
    if isinstance(at,str):
        at=datetime.fromisoformat(at.replace('Z','+00:00'))
    local=at.astimezone(director.campaign_timezone(at))
    week=local.strftime('%G-W%V')
    state_key='ambient_checked:'+week
    if store.get_state(state_key):
        return 0
    by_id={str(g['gang_id']):g for g in gangs}
    created=0
    for territory in sorted(territories,key=lambda t:hash_of([week,t['id']])):
        if created>=limit:
            break
        gang=by_id.get(str(territory.get('gang_id')))
        if not gang or int(hash_of([week,territory['id']])[:8],16)/0xffffffff>=chance:
            continue
        prior=store.db.execute("SELECT created_at FROM narrative_entries WHERE scope_type='territory' AND scope_key=? AND provenance_class='connective_fiction' ORDER BY created_at DESC LIMIT 1",(str(territory['id']),)).fetchone()
        if prior and (at-datetime.fromisoformat(prior['created_at'])).total_seconds()<7*86400:
            continue
        faction=(gang.get('name','')+' '+gang.get('gang_type','')).lower()
        title,text=next((v for k,v in AMBIENT.items() if k in faction),('The stall by the work gate','A stall has reopened beside the work gate. The owner has painted over the old prices and claims the surviving figures are introductory offers. The neighboring stallholders remember the same offers from before the shutters came down.'))
        _,stake,resource=local_focus(territory['territory'])
        text+=f' Here, small arrangements still turn on {stake}.'
        previous_reports=[json.loads(row[0]) for row in store.db.execute("SELECT document_json FROM narrative_entries WHERE scope_type='territory' AND scope_key=? AND provenance_class='connective_fiction'",(str(territory['id']),))]
        used={block.get('text') for doc in previous_reports for block in doc.get('blocks',[])}
        if text in used:
            alternatives=[
                ('A queue of borrowed tokens',f'The queue for {resource} now advances by borrowed tokens. Their owner expects them back before the next shift. Several residents have begun carving copies, and nobody will admit which pattern came first.'),
                ('The repair everyone remembers',f'A repair beside the work gate has acquired three dates and two different accounts of who paid for it. Those who depend on {stake} agree only that the old fault was more convenient for someone.'),
                ('The name beneath the paint',f'An old painted name has shown through a fresh notice. The stallholders have started using it to give directions again. The person responsible for the notice says this was an improvement in public legibility.'),
                ('One shift of quiet',f'The usual argument over {resource} failed to start this shift. A vendor has called the quiet suspicious and raised a shutter just far enough to keep watch. Nobody else is willing to admit they noticed it.'),
            ]
            unused=[item for item in alternatives if item[1] not in used]
            if not unused:
                continue
            title,text=unused[int(hash_of([week,territory['id'],'variant'])[:8],16)%len(unused)]
        previous=[item['entry_id'] for item in read_stream(store,'territory',territory['id'])[:2]][::-1]
        save_entry(store,'territory',territory['id'],'ambient:'+week,'ambient_report',title,[paragraph(text)],
                   [f"Composition context: {territory['territory']}; recorded holder {gang['name']}",
                    'Invented local vignette. No battle, casualty, income, conversion, ownership change or game effect is asserted.'],
                   previous=previous,provenance='connective_fiction',created_at=at.isoformat(),details=[text])
        created+=1
    store.db.execute("INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(state_key,str(created)))
    return created
