"""Shared writing contracts, perspective packets, archive shells and date display.

The director handles prose/presentation only. Evidence and game state are inputs.
The bundled authoring specifications are reference documents, never executable code.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import calendar
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'director-1.0'
DATE_POLICY = {'timezone': 'Europe/Warsaw', 'check': 9, 'year': 998, 'millennium': 41}
CONTRACT_FILES = (
    'NARRATIVE_STYLE_MAP.json', 'NECROMUNDA_CHRONICLE_FORMATTING_STANDARD.md',
    'necromunda_chronicle_narrative_guardrails.md', 'NCCE_Date_Formatting_Specification.md',
    'dominion_territory_event_chronicle_rules.md',
)
FORMS = {
    'battle_report': ('incident_record', 'District archive compiler', 'Collated engagement returns'),
    'territory_history': ('survey_note', 'District survey compiler', 'Place description'),
    'place_event': ('local_account', 'Local account, compiled reconstruction', 'Territorial memory'),
    'place_ambient': ('local_rumour', 'Local report, fictional reconstruction', 'Life under the current holding'),
    'gang_history': ('gang_dossier', 'District archive compiler', 'Gang background'),
    'gang_event': ('gang_record', 'Gang record, compiled reconstruction', 'Changing gang circumstances'),
    'fighter_biography': ('personnel_dossier', 'Personnel archive compiler', 'Service background'),
    'fighter_memory': ('personal_impression', 'Subjective reconstruction', 'Personal memory'),
    'fighter_mind': ('personal_impression', 'Subjective reconstruction', 'Current concern'),
    'region_history': ('district_assessment', 'District archive compiler', 'Current campaign situation'),
    'downtime': ('interval_return', 'District archive compiler', 'Between engagements'),
    'relationship': ('comparative_review', 'District archive compiler', 'Recurring contact'),
}


def policy_hash():
    files = [ROOT / 'docs' / 'writing_sources' / name for name in CONTRACT_FILES]
    files.append(ROOT / 'docs' / 'WRITER_IDENTITY_TAGS.md')
    return hashlib.sha256(b''.join(path.read_bytes() for path in files if path.exists())).hexdigest()


def public_policy():
    path = ROOT / 'docs' / 'writing_sources' / 'NARRATIVE_STYLE_MAP.json'
    style = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    return {'version': VERSION, 'date': DATE_POLICY, 'palette': style.get('palette', {}),
            'ambient': {'cadence': 'weekly opportunity on successful refresh', 'chance': 0.25,
                        'maximum_per_week': 2, 'provenance_class': 'connective_fiction'},
            'contracts': list(CONTRACT_FILES), 'contract_hash': policy_hash()}


def campaign_timezone(at=None):
    try:
        return ZoneInfo(DATE_POLICY['timezone'])
    except ZoneInfoNotFoundError:
        # Windows Python may lack the IANA database. Use the contemporary EU
        # rule for this campaign's real-world source calendar in that case.
        at=at or datetime.now(timezone.utc)
        year=at.year
        def sunday(month):
            last=calendar.monthrange(year,month)[1]
            return last-(datetime(year,month,last).weekday()+1)%7
        utc=at.astimezone(timezone.utc).replace(tzinfo=None) if at.tzinfo else at
        boundary_hour=1 if at.tzinfo else 3
        summer=datetime(year,3,sunday(3),boundary_hour)<=utc<datetime(year,10,sunday(10),boundary_hour)
        return timezone(timedelta(hours=2 if summer else 1))


def format_date(value, meaningful_time=None):
    """Warsaw wall-calendar fraction; real year does not advance the M41 anchor."""
    if not value:
        return {'imperialDisplay': 'Date unrecorded', 'realDisplay': '', 'sourceTimestamp': value}
    raw = str(value).strip()
    date_only = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw))
    placeholder = meaningful_time is None and bool(re.search(r'T00:00:00(?:\.0+)?$',raw))
    try:
        local = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        zone = campaign_timezone(local)
        if date_only or placeholder:
            local = local.replace(hour=12, tzinfo=zone)
        elif local.tzinfo is None:
            local = local.replace(tzinfo=zone)
        else:
            local = local.astimezone(zone)
        # Same-zone subtraction implements the specification's local-calendar
        # elapsed/duration, including the date-only noon convention.
        start = datetime(local.year, 1, 1, tzinfo=zone)
        end = datetime(local.year + 1, 1, 1, tzinfo=zone)
        fraction = max(0, min(999, int((local - start).total_seconds() / (end - start).total_seconds() * 1000)))
        show_time = not date_only if meaningful_time is None else bool(meaningful_time) and not date_only
        # The source workbook often exports calendar dates as naive midnight.
        if placeholder:
            show_time = False
        months = ('January February March April May June July August September October November December').split()
        real = f'{local.day} {months[local.month-1]} {local.year}'
        if show_time:
            real += local.strftime(' · %H:%M')
        return {'imperialDisplay': f"9.{fraction:03d}.{DATE_POLICY['year']:03d}.M{DATE_POLICY['millennium']}",
                'realDisplay': real, 'sourceTimestamp': value, 'sourceTimezone': DATE_POLICY['timezone'],
                'fraction': fraction, 'hasMeaningfulTime': show_time}
    except (ValueError, TypeError, OverflowError):
        return {'imperialDisplay': 'Date unverified', 'realDisplay': 'Source date could not be interpreted', 'sourceTimestamp': value}


def record_date(record):
    if record.get('baseline') or record.get('is_baseline'):
        return {'imperialDisplay': 'Undated archive', 'realDisplay': 'Known at baseline · occurrence date unknown'}
    value = record.get('occurred_at') or record.get('event_date')
    basis = 'event' if value else 'composition' if record.get('provenance_class') == 'connective_fiction' else 'observation' if record.get('observed_at') else 'compilation'
    value = value or record.get('observed_at') or record.get('generated_at')
    result = format_date(value)
    result['basis'] = basis
    if basis != 'event' and value:
        result['realDisplay'] += ' · ' + ('fiction composed' if basis == 'composition' else 'compiled' if basis == 'compilation' else 'first observed; occurrence date unknown')
    return result


def _object(value):
    if isinstance(value, dict):
        return value
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


IDENTITY_FIELDS = ('being', 'species', 'lineage', 'ancestry', 'culture', 'institution', 'place',
                   'fighter_role', 'rules_type', 'work', 'occupation', 'training', 'condition',
                   'life_history', 'voice', 'gender', 'pronouns', 'narration_mode', 'writer_tags')


def validate_identity(value):
    if not isinstance(value, dict) or set(value) - set(IDENTITY_FIELDS):
        raise ValueError('Identity must be an object using the documented identity fields')
    if len(json.dumps(value)) > 12000:
        raise ValueError('Identity context is too long')
    for field, item in value.items():
        if not isinstance(item, (str, list)) or (isinstance(item, list) and any(not isinstance(x, str) for x in item)):
            raise ValueError(f'{field} must be text or a list of text values')
    if value.get('narration_mode') not in (None, '', 'sapient', 'sensory', 'task_log'):
        raise ValueError('Narration mode must be sapient, sensory, or task_log')
    return value


def identity_context(fighter, gang, legacy=None):
    recorded = _object(fighter.get('mechanics_json'))
    explicit = {key: fighter[key] for key in IDENTITY_FIELDS if fighter.get(key)}
    for key in IDENTITY_FIELDS:
        if recorded.get(key) or recorded.get(key.title()):
            explicit.setdefault(key, recorded.get(key) or recorded.get(key.title()))
    explicit.update(_object(fighter.get('writer_identity_json')))
    tags = []
    for key, value in explicit.items():
        values = value if isinstance(value, list) else [value]
        tags.extend(f'{key}:{str(item).strip()}' for item in values if str(item).strip())
    mode = explicit.get('narration_mode') or 'sapient'
    if not explicit.get('narration_mode'):
        if 'exotic beast' in str(fighter.get('class', '')).lower() or (legacy or {}).get('register') == 'sensory':
            mode = 'sensory'
        being_value = explicit.get('being') or explicit.get('species') or ''
        beings = ' '.join(being_value).lower() if isinstance(being_value,list) else str(being_value).lower()
        if any(x in beings for x in ('dog', 'animal', 'beast', 'canid')):
            mode = 'sensory'
        if beings in ('automaton', 'servitor'):
            mode = 'task_log'
    return {'identity': explicit, 'tags': tags, 'narration_mode': mode,
            'recorded_category': fighter.get('class'), 'recorded_type': fighter.get('type'),
            'affiliation': gang.get('gang_type'), 'gang': gang.get('name'),
            'authored_context': fighter.get('backstory') if any(token in str(fighter.get('backstory_source', '')).lower() for token in ('authored','c-nine story','canon')) and 'mechanic' not in str(fighter.get('backstory_source','')).lower() else None,
            'knowledge_boundary': 'Only sourced personal events and attributed shared news; no hidden motives or unseen battle actions.',
            'guardrails': ['Identity does not change event importance or mechanics.',
                          'Affiliation supplies context, not automatic private beliefs.',
                          'Gender, species, occupation and secret knowledge are never guessed from names.']}


def character_text(text, packet, topic, reflection=False):
    """Bounded rendering for non-verbal and task-limited perspectives."""
    mode = packet.get('narration_mode', 'sapient')
    if mode == 'sensory':
        if any(x in topic for x in ('status', 'effect', 'injur')):
            return 'Movement checks against the body’s limits. Familiar cues remain; comfort and threat are felt before anything like a reason.'
        if any(x in topic for x in ('loss', 'captur', 'death')):
            return 'A familiar presence is absent. The expected cue has no answer; the old association remains.'
        if reflection:
            return 'Repeated cues settle into recognition: where to hesitate, what to approach, which familiar signals still lead toward safety.'
        return 'Familiar signals arrive in a changed pattern. Recognition comes before explanation; the response is rendered here as sensation and learned association.'
    if mode == 'task_log':
        return ('Retained associations compared. The instruction persists; the conditions under which it can be fulfilled have changed.' if reflection else
                'State amendment retained. Current instruction remains pending against the amended condition; no independent motive is established.')
    return clean_generated_text(text)


def character_biography(fighter, gang, text):
    packet=identity_context(fighter,gang)
    if str(fighter.get('status','')).lower() in ('dead','killed'):
        return f"The closed personnel file retains {fighter['name']} among the dead of {gang.get('name') or fighter.get('gang_name') or 'the gang'}. Their recorded service remains part of the account. Earlier changes belong to their history; no present intentions are attributed to them."
    if packet['narration_mode']=='sensory':
        return f"The surviving account follows {fighter['name']} through its associations with the gang. Its impressions are rendered through sensation, learned cues and familiar presence. A human sentence here is an interpretation of that experience, not proof of a spoken account."
    if packet['narration_mode']=='task_log':
        return f"The surviving service record retains {fighter['name']} as a continuing entity. Changes in condition, task and retained associations belong to that record; an independent human motive is not established."
    work=packet['identity'].get('work') or packet['identity'].get('occupation')
    if work:
        label=', '.join(work) if isinstance(work,list) else work
        text=f"The personal file records work in {label}.\n\n"+text
    return text


def clean_generated_text(text):
    """Translate only generated prose, never source notes or evidence."""
    replacements = ((r'\bXP\b', 'experience'), (r'\bOOA\b', 'incapacitated'),
                    (r'\bCool check\b', 'composure under pressure'),
                    (r'\bRating\b', 'assessed strength'), (r'\bDowntime\b', 'the interval'),
                    (r'\bscenario rules\b', 'terms of the engagement'))
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, str(text), flags=re.I)
    return str(text)


def direct_document(scope, key, document, record=None, packet=None):
    """Attach a credible document form before presentation; source notes stay intact."""
    document = dict(document)
    form, author, purpose = FORMS.get(scope, ('archive_record', 'Archive compiler', 'Campaign record'))
    record = record or document
    # Fully authored source content is never rewritten by this compiler.
    if document.get('provenance_class') not in ('player_authored', 'canon_authored'):
        def clean_block(block):
            block = dict(block)
            if block.get('text'):
                block['text'] = clean_generated_text(block['text'])
            if block.get('blocks'):
                block['blocks'] = [clean_block(child) for child in block['blocks']]
            return block
        document['blocks'] = [clean_block(block) for block in document.get('blocks', [])]
    document.update(director_version=VERSION, document_type=form,
                    author=document.get('author', author), purpose=purpose,
                    reference=f'NC/{scope.upper()}/{key}',
                    knowledge_boundary='Compiled from cited returns; unrecorded actions and private motives remain unknown.')
    document['date_display'] = record_date(record)
    document['metadata'] = [{'label': 'Reference', 'value': document['reference']},
                            {'label': 'Source', 'value': document['author']},
                            {'label': 'Record', 'value': purpose}]
    document.setdefault('termination', {'type': 'record_termination', 'text': '// RECORD ENDS //'})
    if packet:
        document['writer_context'] = packet
    return document
