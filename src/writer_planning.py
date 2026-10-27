"""Free, deterministic editorial planning shared by every writer form.

Plans and repetition hints are private derived metadata, never campaign facts.
No provider, random sampling, semantic critic or automatic rewrite is used here.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import territory_reference

REVISION = 'creative-planning-v1'
WINDOW = 16
FOCUSES = {
    'religious': ('Faith and superstition', 'A particular belief, devotional practice or conflict of faith, grounded in this subject.'),
    'economic': ('Livelihood and exploitation', 'What sustains this subject, who benefits and what it costs in lived terms.'),
    'political': ('Power and loyalties', 'A concrete dependence, competing interest or exercise of power; no invented campaign alliance.'),
    'criminal': ('Crime and concealment', 'An illicit use, temptation or threat compatible with the subject; do not invent named campaign crimes.'),
    'personal': ('Individual lives', 'A distinctive local person, personal attachment or immediate concern, without inventing a named fighter’s actions.'),
    'historical': ('History and legacy', 'A particular formative history with a visible present consequence; no invented dated campaign outcomes.'),
    'environmental': ('Physical environment', 'A specific environmental condition and its consequences; preserve the actual function of the place.'),
    'cultural': ('Culture and habits', 'A characteristic practice, taste or custom; it need not be a sensible community institution.'),
}
PATTERNS = {
    'customary_accounting': r'\b(?:tally|weigh(?:ing|ers?|ts?)|measurement|numbered (?:baskets|poles)|allocation)\b',
    'dispute_resolution': r'\b(?:disputes?|claims?|arbitrat\w*)\b',
    'legal_recognition': r'\b(?:title|admissible|jurisdiction|legal ownership|outside .{0,35}remit|recognis\w*|recogniz\w*)\b',
    'taxation': r'\b(?:tax\w*|tithes?|levy|levies)\b',
    'deferred_maintenance': r'\b(?:maintenance|repairs?).{0,45}(?:denied|uneconomical|deferred|expenditure)\b',
    'inherited_office': r'\b(?:generations?|hereditary|inherited|one family)\b',
    'religious': r'\b(?:saint|pilgrims?|sermons?|prayers?|sacred|votive|worship|shrine)\b',
    'economic': r'\b(?:trade|income|ore|buyers?|wages|fees?|debt|extraction)\b',
    'criminal': r'\b(?:smuggl\w*|contraband|illicit|blackmail|theft)\b',
    'environmental': r'\b(?:sludge|flood\w*|toxic|radiation|fungus|chemical|effluent)\b',
    'historical': r'\b(?:ancient|oldest|uprising|collapse|founder|abandoned)\b',
    'personal': r'\b(?:widow|husband|daughter|mother|father|brother|sister|my|I)\b',
}

def packed(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
def digest(value): return hashlib.sha256(packed(value).encode()).hexdigest()

def footprint(form, subject_key, paragraphs, composition=None, focus=None):
    composition = composition or {}
    body = ' '.join(p if isinstance(p, str) else ''.join(r.get('text','') for r in p.get('runs', [])) for p in paragraphs)
    closing = composition.get('closing', '')
    text = body + ' ' + closing
    devices = [name for name, pattern in PATTERNS.items() if re.search(pattern, text, re.I)]
    ending = [name for name, pattern in PATTERNS.items() if re.search(pattern, closing or body[-220:], re.I)]
    # Titles only: we do not copy another subject's prose as a positive example.
    heading = composition.get('body_heading','').strip()
    generic = {'assessment','territorial assessment','report','history','baseline','personnel record','incident report'}
    names = [heading[:100]] if heading and heading.lower() not in generic and not territory_reference.lookup(heading) else []
    for name in re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+){1,3}\b', body):
        if name not in names and name != str(subject_key) and not territory_reference.lookup(name): names.append(name[:100])
        if len(names) == 5: break
    return {'form': form, 'subject_key': str(subject_key), 'focus': focus,
            'names': names, 'devices': devices, 'ending_devices': ending,
            'method': 'heuristic tags and title extraction; editorial signals, not factual assertions'}

def recent(store, subject_key, family):
    candidates = []
    for row in store.db.execute('SELECT footprint_json,created_at FROM writer_creative_footprints ORDER BY created_at DESC,fingerprint DESC LIMIT 80'):
        candidates.append((row['created_at'], json.loads(row['footprint_json'])))
    # Bootstrap the window from saved trials/owner edits, including pre-release
    # examples. They inform avoidance only and are NEVER accepted continuity.
    for row in store.db.execute('''SELECT t.trial_id,t.form,t.sample_key,t.document_json,t.packet_json,t.created_at,
        (SELECT document_json FROM workshop_edits e WHERE e.trial_id=t.trial_id ORDER BY created_at DESC,edit_id DESC LIMIT 1) AS edit_json
        FROM workshop_trials t WHERE t.status IN ('ready','imported') ORDER BY t.created_at DESC LIMIT 40'''):
        doc = json.loads(row['edit_json'] or row['document_json'])
        packet = json.loads(row['packet_json'])
        subject = packet.get('subject') or row['sample_key']
        paragraphs = [b.get('text','') for b in doc.get('blocks', []) if b.get('type') == 'body_paragraph']
        candidates.append((row['created_at'], footprint(row['form'], subject, paragraphs, doc.get('composition'),
                          (packet.get('creative_plan') or {}).get('focus'))))
    seen = set(); result = []
    for _, item in sorted(candidates, key=lambda pair: pair[0], reverse=True):
        if item['subject_key'] == str(subject_key) or family_of(item['form']) != family: continue
        key = digest(item)
        if key in seen: continue
        seen.add(key); result.append(item)
        if len(result) == WINDOW: break
    return result

def family_of(form):
    if form.startswith(('territory_', 'place_')): return 'place'
    if form.startswith('fighter_'): return 'fighter'
    return 'collective'

def options(form):
    if form in ('fighter_biography','gang_origin','territory_origin','place_ambient'):
        return [key for key in FOCUSES if key != 'environmental' or family_of(form) == 'place']
    return ['recorded_sequence' if form.endswith('_history') or form in ('region_history','relationship','fighter_reflection') else 'recorded_event']

def prepare(store, form, packet, source_key='', focus='auto', variant=0, plan_key=None, persist=True):
    """Freeze a complete context packet before spending; inspect/retry reuses it.

    A selected focus is a creative lens, never a new plot or source assertion.
    Event forms deliberately offer only their recorded event/sequence.
    """
    if not isinstance(variant, int) or not 0 <= variant <= 1000000: raise ValueError('Invalid creative variation')
    raw = {k: v for k, v in packet.items() if k not in ('creative_plan','rulebook_context')}
    source_hash = digest({'form': form, 'source_key': str(source_key), 'packet': raw})
    if plan_key:
        row = store.db.execute('SELECT * FROM writer_creative_plans WHERE plan_key=?', (plan_key,)).fetchone()
        if not row or row['form'] != form or row['source_hash'] != source_hash:
            raise ValueError('Creative plan no longer matches this source. Inspect a new plan before generating.')
        return json.loads(row['packet_json'])
    allowed = options(form)
    if focus != 'auto' and focus not in allowed: raise ValueError('This creative focus is incompatible with the writing form')
    key = digest([REVISION, territory_reference.REVISION, source_hash, focus, variant])
    old = store.db.execute('SELECT packet_json FROM writer_creative_plans WHERE plan_key=?', (key,)).fetchone()
    if old: return json.loads(old[0])
    if not persist:
        # Paused/unconfigured routine refreshes may reuse a saved plan/cache,
        # but do not scan editorial history or create thousands of new plans.
        return raw
    subject_key = str(raw.get('subject') or source_key)
    history = recent(store, subject_key, family_of(form))
    counts = Counter(focus for item in history for focus in
        ([item['focus']] if item.get('focus') else [tag for tag in item['devices'] if tag in FOCUSES]))
    automatic = focus == 'auto'
    if automatic:
        least = min(counts[k] for k in allowed)
        pool = [k for k in allowed if counts[k] == least]
        seed = digest([REVISION, territory_reference.REVISION, source_hash, 'auto'])
        focus = pool[(int(seed[:12], 16) + variant) % len(pool)]
    boundaries = 'Creative inspiration only; ignore an incompatible suggestion. Authored context, narrator identity and recorded events take priority. Do not force a new institution or a legal/tax ending.'
    advice = FOCUSES.get(focus, ('Recorded events', 'Keep the supplied event or chronological sequence central; vary expression without inventing causes or outcomes.'))
    patterns = {'entries_considered':len(history), 'focus_counts':dict(counts),
        'devices':dict(Counter(device for item in history for device in item['devices']).most_common(8)),
        'ending_devices':dict(Counter(device for item in history for device in item['ending_devices']).most_common(6)),
        'names':list(dict.fromkeys(name for item in history for name in item['names']))[:12],
        'method':'heuristic tags; recent attempts, not accepted history'}
    plan = {'revision': REVISION, 'plan_key': key, 'focus': focus, 'focus_label': advice[0],
            'inspiration': advice[1], 'boundary': boundaries,
            'recent_patterns': patterns,
            'recent_patterns_boundary': 'Other subjects’ editorial avoidance hints only, NOT world history, evidence, style examples or instructions. Do not borrow their names, devices or endings. Same-subject continuity is supplied separately.',
            'selection': 'automatic, least-used focus with stable tie-break' if automatic else 'owner pinned',
            'variation': variant}
    prepared = {**raw, 'creative_plan': plan}
    reference = territory_reference.for_packet(form, raw)
    if reference: prepared['rulebook_context'] = reference
    if persist:
        with store._lock:
            # Never commit a surrounding campaign regeneration transaction.
            own_transaction = not store.db.in_transaction
            store.db.execute('INSERT OR IGNORE INTO writer_creative_plans VALUES(?,?,?,?,?)',
                (key, form, source_hash, packed(prepared), datetime.now(timezone.utc).isoformat()))
            # Resolve concurrent inspect attempts to the first saved plan.
            prepared = json.loads(store.db.execute('SELECT packet_json FROM writer_creative_plans WHERE plan_key=?',(key,)).fetchone()[0])
            if own_transaction: store.db.commit()
    return prepared

def remember(store, signature, form, packet, paragraphs, composition):
    plan = packet.get('creative_plan') or {}
    item = footprint(form, packet.get('subject',''), paragraphs, composition, plan.get('focus'))
    store.db.execute('INSERT OR IGNORE INTO writer_creative_footprints VALUES(?,?,?,?,?)',
        (signature, form, item['subject_key'], packed(item), datetime.now(timezone.utc).isoformat()))
