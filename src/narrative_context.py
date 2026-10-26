"""Bounded, provenance-separated narrative context shared by every writer form.

Generated continuity is never inserted into the mechanical event ledger.
"""
import json
from datetime import datetime, timezone
import writer_contract


def instant(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def prose(document):
    def blocks(items):
        return '\n\n'.join(filter(None, (str(item.get('text') or '') + '\n' + blocks(item.get('blocks', [])) for item in items)))
    return blocks(document.get('blocks', [])).strip()


def usable(document):
    return document.get('writer_status') == 'ready' and document.get('writer_revision') == writer_contract.REVISION


def authored(row):
    source = str(row.get('backstory_source', '')).lower()
    return row.get('backstory') if 'mechanic' not in source and any(x in source for x in ('authored', 'canon', 'c-nine story', 'player')) else None


def fighter_at_event(store, fighter, gang, event, baseline=False):
    """Build a historical voice lens without today's injuries, equipment or rank."""
    cutoff=instant(event.get('occurred_at') or event.get('observed_at'))
    snapshots=store.db.execute('SELECT captured_at,payload_json FROM snapshots ORDER BY captured_at '+('ASC' if baseline else 'DESC'))
    for row in snapshots:
        if not baseline and (cutoff is None or instant(row['captured_at']) is None or instant(row['captured_at'])>cutoff):
            continue
        snapshot=json.loads(row['payload_json'])
        gangs=snapshot.get('gangs')
        if not isinstance(gangs,dict): continue  # legacy seed snapshots contain counts only
        matches=[g for g in gangs.values() if isinstance(g,dict) and str(g.get('gang_id'))==str(fighter.get('gang_id'))]
        if len(matches)!=1: continue
        source_gang=matches[0]
        matches=[value for name,value in source_gang.get('fighters',{}).items() if str(name).strip().casefold()==str(fighter['name']).strip().casefold()]
        if len(matches)!=1: continue
        source=matches[0]
        view={**fighter,'mechanics_json':json.dumps(source),'mechanics':source}
        for target,field in {'class':'Class','type':'Type','status':'Status','effects':'Effects','xp':'XP','kills':'Kills','weapons':'Weapons','wargear':'Wargear','advancements':'Advancements','skills':'Skills'}.items():
            view[target]=source.get(field)
        return view,{**gang,'name':source_gang.get('name',gang.get('name')),'gang_type':source_gang.get('gang_type')}
    # No historical roster: authored voice and explicit identity remain available;
    # transient current state cannot be treated as historical evidence.
    view={**fighter,'mechanics_json':'{}','mechanics':{}}
    for key in ('class','type','status','effects','xp','kills','weapons','wargear','advancements','skills'):
        view[key]=None
    return view,gang


def origin(store, scope, key, as_of=None):
    row = store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type=? AND scope_key=? AND active=1 ORDER BY generated_at DESC LIMIT 1", (scope, str(key))).fetchone()
    if not row:
        return None
    document = json.loads(row[0])
    cutoff=instant(as_of)
    written=instant(document.get('generated_at'))
    if cutoff and (written is None or written>cutoff):
        return None
    if usable(document):
        return {'provenance': 'generated_fiction', 'form': scope, 'text': prose(document),
                'subject': document.get('composition', {}).get('subject', document.get('title'))}
    return None


def preceding(store, scope, key, at, ids=(), exclude=None):
    """Only earlier accepted new-policy stories, never legacy prose or future facts.

    Explicit IDs allow the current chronological rebuild to read entries just saved.
    Undated entries are excluded from dated continuity rather than assigned a time.
    """
    cutoff = instant(at)
    if cutoff is None:
        return []
    wanted = set(ids)
    candidates = []
    for row in store.db.execute('SELECT * FROM narrative_entries WHERE scope_type=? AND scope_key=? AND active=1', (scope, str(key))):
        if row['entry_key'] == exclude or (wanted and row['entry_id'] not in wanted):
            continue
        document = json.loads(row['document_json'])
        context = document.get('writer_context', {})
        when = instant(context.get('occurred_at') or context.get('observed_at') or (row['created_at'] if row['provenance_class'] == 'connective_fiction' else None))
        if usable(document) and when and when < cutoff:
            candidates.append((when, {'entry_id': row['entry_id'], 'at': when.isoformat(),
                                      'provenance': row['provenance_class'], 'text': prose(document)}))
    return [item for _, item in sorted(candidates, key=lambda pair: (pair[0], pair[1]['entry_id']))[-4:]]


def entity_context(store, scope, key, at=None, previous=(), exclude=None):
    """Current identity is labelled separately; historical events never get current holdings."""
    result = {'baseline': None, 'authored_context': None, 'earlier_stories': []}
    if scope in ('gang', 'territory'):
        result['baseline'] = origin(store, scope + '_origin', key)
        result['earlier_stories'] = preceding(store, scope, key, at, previous, exclude)
    if scope == 'gang':
        row = store.db.execute('SELECT * FROM gangs WHERE gang_id=?', (str(key),)).fetchone()
        if row:
            row = dict(row)
            result.update(name=row.get('name'), faction=row.get('gang_type'), authored_context=authored(row))
    elif scope == 'fighter':
        row = store.db.execute('SELECT * FROM fighters WHERE id=?', (key,)).fetchone()
        if row:
            row = dict(row)
            result.update(name=row.get('name'), authored_context=authored(row), baseline=origin(store, 'fighter_biography', key))
    return result


def territory_state_at(store, territory, at):
    """Use a snapshot at/before the event, never silently apply today's ownership.

    Pre-baseline events have no historical state unless their own payload supplies it.
    Match only unique stable IDs, cards or names as in the factual association layer.
    """
    cutoff = instant(at)
    if cutoff is None:
        return {'timing': 'undated; historical owner unavailable'}
    for row in store.db.execute('SELECT captured_at,payload_json FROM snapshots ORDER BY captured_at DESC'):
        stamp = instant(row['captured_at'])
        if not stamp or stamp > cutoff:
            continue
        snapshot = json.loads(row['payload_json'])
        states = snapshot.get('territories', [])
        if not isinstance(states,list): continue
        source_id=territory.get('source_territory_id')
        if source_id:
            matches=[state for state in states if str(state.get('source_territory_key') or state.get('Territory ID') or state.get('territory_id'))==str(source_id)]
        elif territory.get('card'):
            matches=[state for state in states if state.get('Card')==territory['card']]
        else:
            matches=[state for state in states if state.get('Territory')==territory['territory']]
            count=store.db.execute('SELECT count(*) FROM territories WHERE territory=?',(territory['territory'],)).fetchone()[0]
            if count!=1: matches=[]
        # A duplicated source ID may denote several holdings; never choose arbitrarily.
        if len(matches) == 1:
            state = matches[0]
            return {'name': state.get('Territory'), 'holder': state.get('Gang'), 'holder_id': state.get('Gang ID'),
                    'as_of': row['captured_at'], 'basis': 'recorded snapshot at or before event'}
    return {'timing': 'before earliest matching snapshot; historical owner unavailable'}


def document_packet(store, form, key, document):
    """Whitelist prompt fields; old template text and application status never become prose seeds."""
    context = {k: v for k, v in (document.get('writer_context') or {}).items()
               if k not in {'prior_entry', 'prior_entries', 'continuity_reference', 'guardrails'}}
    if isinstance(context.get('continuity'), dict):
        context['continuity'] = {k: v for k, v in context['continuity'].items() if k != 'invented_details'}
    packet = {'subject': document.get('title'), 'evidence': document.get('evidence', document.get('mechanical_evidence', [])),
              'source_event_ids': document.get('source_event_ids', []), 'writer_context': context}
    if document.get('recorded_notes'):
        packet['authored_testimony']=document['recorded_notes']
    # Retain real dates only in context for ordering. The response never writes dates.
    events = []
    if store:
        for event_id in packet['source_event_ids']:
            row = store.db.execute('SELECT event_type,occurred_at,observed_at,payload_json FROM campaign_events WHERE event_id=?', (event_id,)).fetchone()
            if row:
                events.append({'event_id': event_id, 'type': row['event_type'], 'occurred_at': row['occurred_at'],
                               'observed_at': row['observed_at'], 'facts': json.loads(row['payload_json'])})
        events.sort(key=lambda e: (instant(e['occurred_at'] or e['observed_at']) or datetime.min.replace(tzinfo=timezone.utc), e['event_id']))
        packet['events_in_order'] = events
        scope = 'fighter' if form == 'fighter_biography' else 'territory' if form.startswith('territory') else 'gang' if form in ('gang_origin', 'gang_history', 'downtime') else None
        if scope:
            entity = entity_context(store, scope, key, document.get('occurred_at') or document.get('generated_at'))
            if form.endswith('_origin') or form == 'fighter_biography':
                entity['baseline'] = None  # replacement origins do not inherit their old wording
            packet['subject_context'] = entity
        if form in ('battle_report','relationship','region_history'):
            names=set()
            for event in events:
                facts=event['facts']
                names.update(facts.get(k) for k in ('attacker','defender','winner') if facts.get(k))
            packet['parties']=[entity_context(store,'gang',row['gang_id']) for row in store.db.execute('SELECT gang_id,name FROM gangs WHERE active=1') if row['name'] in names]
    return packet
