"""One reviewed runtime specification for every narrative form; no provider calls."""
from pathlib import Path

REVISION = 'narrative-contract-v6'
RUNTIME_PATH = Path(__file__).resolve().parents[1] / 'docs/writing_sources/WRITER_RUNTIME_CONTRACT.md'
PERSONAL = {'fighter_memory', 'fighter_reflection'}
BRIEFS = {
    'fighter_memory': 'EVENT. One short first-person memory, 40–100 words. Start with this experience and develop a specific reaction. Background is a lens, never a recap. No document heading or institutional voice.',
    'fighter_reflection': 'REFLECTION. First person, 60–130 words. Connect the cited experiences into a particular present concern or intention. No generic life lesson or document heading.',
    'fighter_biography': 'BASELINE. A distinctive third-person life sketch, 140–240 words. Separate formative fictional background from undated current recorded condition. Respect authored history and embodiment.',
    'gang_origin': 'BASELINE. Establish a particular gang culture and background, 140–240 words. Use its own faction and composition; no invented campaign victories or roster relationships.',
    'gang_history': 'HISTORY. A coherent account of this gang across the supplied dated changes, 150–260 words. Preserve its established character and the sequence of events.',
    'territory_origin': 'BASELINE. Establish a memorable inhabited place, 150–240 words. Use physical setting, local practice and a distinctive historical detail. An Imperial territorial assessment is suitable unless context suggests another author.',
    'territory_history': 'HISTORY. Develop this place through the supplied chronological events, 150–260 words. Preserve its baseline and distinguish the owner at each point.',
    'place_event': 'EVENT. A local document about this one change, 90–180 words. Show its effect on the established place. An official remark may reveal a credible institutional interest.',
    'place_ambient': 'AMBIENT. One small, self-contained local incident, 100–200 words, using the established place and holder at that time. It may be strange, mundane, comic or unsettling. No tabletop effects.',
    'gang_event': 'EVENT. A specific gang account, 90–180 words, of this change and its nonmechanical repercussions. Use the gang’s own culture; do not invent deployment or transactions.',
    'battle_report': 'EVENT. An engagement account, 170–300 words. Anchor participants, scenario, outcome and known casualties to evidence. Use the setting and aftermath for connective fiction, never invented tactics, attacks or attendance. Attribute authored testimony.',
    'downtime': 'HISTORY. An inter-battle account, 140–240 words. Connect the supplied events in order and ground them in the gang’s life. No invented purchases, recoveries or other mechanical changes.',
    'region_history': 'HISTORY. A district chronicle, 170–300 words. Give the supplied sequence a clear narrative shape and material setting. Preserve the limits of recorded political relationships.',
    'relationship': 'HISTORY. An account of repeated contact, 100–180 words. Distinguish recorded encounters from fictional reputations or interpretations. No invented alliance, feud or shared past presented as fact.',
}

# Deliberately unrelated demonstration subjects. Never incorporated into campaign data.
PERSONAL_EXAMPLE = '''STYLE DEMONSTRATION — fictional subject, not campaign evidence.
Input: A fictional repair worker has suffered a serious injury and is recovering. No injury mechanism is known.
Output: I tried the small spanner this morning. Getting it off the hook was easy enough; putting it back took both hands. I've left the larger tools where they are. Someone else can complain about the pump until I can hold the bloody thing steady.
Notice: one present experience, ordinary vocabulary and a concrete consequence. No invented attack or clinical diagnosis. Do not reuse the spanner or pump for unrelated fighters.'''

DOCUMENT_EXAMPLE = '''STYLE DEMONSTRATION — all names, numbers and events below are illustrative fiction, NOT campaign facts.
Heading: ADEPTUS ADMINISTRATUM — DEPARTMENTO TERRITORIALIS
Subject: Ossuary of Saint Tindalos the Unburied
Body heading: TERRITORIAL ASSESSMENT
Housed within a collapsed ventilation cathedral beneath a defunct corpse-starch works, the Ossuary contains the lacquered bones of forty thousand hive labourers lost to the Great Sump Fever.
Local tradition holds that Saint Tindalos continued preaching for seventeen days after his death. Pilgrims and gangers alike leave finger bones, spent casings, and ration tokens in exchange for his protection.
Three successive custodians have disappeared. The fourth was found incorporated into the eastern reliquary wall.
Closing label: RECOMMENDATION
Closing: Maintain tithe exemption. Refrain from further inspection.
Notice: specific construction, a local custom, a compact development and a credible institutional response. These devices transfer to other forms; this institution and lore do not. A gang letter or personnel account should use its own speaker and concerns, not imitate territorial administration.'''

EVENT_EXAMPLE = '''EVENT STYLE DEMONSTRATION — illustrative, not campaign evidence.
Input: An established shrine is now classified as a Settlement. The cause of the change is unknown.
Subject: Reclassification of Ecclesiarchal Holding
Recent surveys indicate that the Ossuary's adjoining chambers have been converted into permanent habitation. Scrap-built dwellings now surround the reliquaries, with a functioning water still, trading stalls, and an estimated eighty-seven residents.
The Saint's altar remains intact, although its eastern wall now supports a communal cookhouse.
ADMINISTRATUM REMARK: Reclassify holding as Settlement. Residential tithes applicable. Previous exemptions revoked.
Notice: physical expression of the known change; fictional civilian details do not assign a cause, purchase or game benefit. Do not reuse this setting or automatically add taxes to other accounts.'''

PERSONNEL_EXAMPLE = '''STYLE DEMONSTRATION — fictional person, not campaign evidence.
Heading: TRANSPORT GUILD — PERSONNEL OFFICE
Subject: Venn, Loader Third Class
Venn spent eleven years checking seals on freight cages. The work left a permanent grey line beneath his fingernails and a habit of counting every person who entered a room. He still sleeps beside the door, where a late arrival will have to step over him.
His transfer request was returned three times for insufficient literacy. On the fourth submission, the same clerk accepted a thumbprint.
Closing label: SERVICE NOTE
Closing: Retain on the night roster. The day supervisor has requested no further correspondence.
Notice: a short life expressed through work, habit and an institutional response, not a list of statistics. These are freely invented background details for this example; do not transplant them or overwrite authored life history.'''

COLLECTIVE_EXAMPLE = '''STYLE DEMONSTRATION — fictional gang and event, not campaign evidence.
Input: The Brass Widows lost control of a toll bridge. No casualties or individual attendance are recorded.
Heading: BRASS WIDOWS — HOUSE ACCOUNT
Subject: The bridge receipts
The bridge box came back empty. Someone had taken the trouble to wrap the key in a clean rag and put it inside.
At supper, the collectors sat at their usual end of the table. There was no collection to count, so they ate with everyone else. The youngest asked whether they would be going back tomorrow. Nobody answered until the plates had been cleared.
Closing: Keep the box. We paid for it.
Notice: ownership loss expressed through a compatible small civilian aftermath. No invented attack, named fighter deployment, casualty or game-credit deduction. The speaker has a particular concern; no explanatory moral is needed. Other gangs require their own vocabulary and form.'''

def contract(form):
    if form not in BRIEFS:
        raise ValueError(f'Unsupported narrative form: {form}')
    common = RUNTIME_PATH.read_text(encoding='utf-8-sig').strip()
    if form in PERSONAL:
        example = PERSONAL_EXAMPLE
    elif form == 'fighter_biography':
        example = PERSONNEL_EXAMPLE
    elif form.startswith('territory') or form.startswith('place_'):
        example = DOCUMENT_EXAMPLE + '\n\n' + EVENT_EXAMPLE
    else:
        example = COLLECTIVE_EXAMPLE
    return common + '\n\n' + example + '\n\nREQUESTED FORM: ' + form + '\n' + BRIEFS[form]
