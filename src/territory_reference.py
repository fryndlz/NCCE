"""Concise paraphrases verified against the supplied 2023 Core Rulebook.

These describe a TYPE, not events, ownership, or benefits actually claimed in
Krakamunda. No PDF contents or model recollections are loaded at runtime.
"""
import copy
import re

REVISION = 'core-2023-territories-1'
BOOK = 'Necromunda: Core Rulebook (2023)'
# Printed page, type, function, rule significance, associated House.
_CARDS = [
 (173, 'Settlement', 'Scrap-built habitation established by settlers in the underhive or wastes.', 'Income, reputation and potential recruitment. A gang’s starting Settlement represents its protected hideout.', None),
 (173, 'Old Ruins', 'Ruined structures shelter salvage from earlier ages beneath ash and rubble.', 'Salvage income; Dome Runners improve the return.', None),
 (173, 'Rogue Doc Shop', 'An unofficial healer offers medical services in exchange for protection.', 'Law-abiding gangs can recruit a Rogue Doc; Outlaws receive income instead.', None),
 (173, 'Promethium Cache', 'A stored reserve of industrial fuel in tanks and drums; a major fire risk.', 'Supplies incendiary charges and support for Blaze weapons.', None),
 (174, 'Wastes', 'Expanses of ash, rubble and metal wreckage lie between more valuable sites.', 'Control affects territory challenges and can enable an ambush when defending an existing holding.', None),
 (174, 'Sludge Sea', 'Hive drainage collects into foul, fuming lakes of contaminated water and effluent.', 'Provides choke gas grenades.', None),
 (174, 'Workshop', 'A scrap yard and machine workshop inhabited by reclusive repairers and ammunition specialists.', 'Law-abiding gangs can recruit an Ammo-jack; Outlaws receive income instead.', None),
 (174, 'Collapsed Dome', 'A fallen hive dome contains buried salvage beneath unstable wreckage.', 'Risk-dependent salvage income; an unsuccessful expedition can injure a fighter.', None),
 (175, 'Refuse Drift', 'Accumulated waste forms shifting heaps through the underhive.', 'Scavenging income carries waste-lurker risk. Cawdor gain reputation and avoid that risk.', 'Cawdor'),
 (175, 'Corpse Farm', 'A shunned processing trade converts dead bodies into food for the hive.', 'Income depends on roster losses after a battle; Cawdor receive enhanced income and reputation.', 'Cawdor'),
 (175, 'Bone Shrine', 'A devotional site constructed from bones and hanging ropes, receiving offerings for blessings.', 'Offering income; Cawdor receive increased income and reputation.', 'Cawdor'),
 (176, 'Drinking Hole', 'A liquor den where hivers seek respite, courage and company.', 'Reputation and drinking-related combat effects; Delaque can interfere with opponents through spiked drinks.', 'Delaque'),
 (176, 'Gambling Den', 'A venue for gambling, fortunes and enforceable debts.', 'Variable income and reputation; Delaque can call in a debt to keep an opponent out of a battle.', 'Delaque'),
 (177, 'Needle Ways', 'A concealed network of vents, crawl tunnels and pipes enables unseen movement through the hive.', 'Selected fighters gain Infiltrate; Delaque can select more fighters.', 'Delaque'),
 (177, 'Synth Still', 'Reclaimed vats, pipes and cylinders support skilled manufacture of medicines, poisons and narcotics.', 'Improved access to specified chemical equipment and weapons; Escher gain cheaper access and reputation.', 'Escher'),
 (177, 'Stinger Mould Sprawl', 'A dangerous medicinal fungus grows in irradiated fungal expanses.', 'Supports injury treatment; Escher gain stronger healing options and reputation.', 'Escher'),
 (178, 'Narco Den', 'A place where rich and poor consume intoxicants to pursue dreams or escape distress.', 'Income; enhanced Escher income and reputation, with further income interaction with a Synth Still.', 'Escher'),
 (178, 'Slag Furnace', 'An operating furnace extracts molten metal from slag and ore.', 'Income; Goliath gain reputation and potential recruits.', 'Goliath'),
 (178, 'Fighting Pit', 'A public arena cultivates feared fighters through violent entertainment.', 'Provides hired Hive Scum for battles; Goliath gain reputation.', 'Goliath'),
 (178, 'Smelting Works', 'Valuable seams and crags of industrial slag remain from the hive’s ancient manufacture.', 'Income; Goliath receive enhanced returns, improved further when combined with a Slag Furnace.', 'Goliath'),
 (179, 'Mine Workings', 'Open-cast excavation of a mineral mass yields valuable ores and gems.', 'Income; captives may be forced to work here and remain with a transferred holding. Rescue remains possible. Orlock gain reputation.', 'Orlock'),
 (179, 'Tunnels', 'Principal passages through the hive allow movement between locations and access for attacks.', 'Selected fighters can deploy through tunnel entrances; Orlock gain reputation and larger deployment groups.', 'Orlock'),
 (180, 'Toll Crossing', 'A bridge, bottleneck or crossing offers relatively swift, safe passage for a fee.', 'Income; Orlock gain an opening initiative advantage and may sell that advantage to others.', 'Orlock'),
 (180, 'Generatorium', 'Taps into energy conduits or aging generators supply local light and power.', 'Control can interrupt battlefield power; automatic restart is possible. Van Saar gain reputation.', 'Van Saar'),
 (181, 'Archaeotech Device', 'An ancient technological relic has unusual capabilities and substantial hazards.', 'Adds selected weapon traits together with instability; Van Saar gain enhanced options and reputation.', 'Van Saar'),
 (181, 'Tech Bazaar', 'A technology and arms market brings merchants, prospectors and Gun-guild agents together.', 'Income and discounted equipment opportunities; Van Saar gain reputation and an income interaction with an Archaeotech Device.', 'Van Saar'),
]

def normalized(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()

CARDS = {normalized(row[1]): {
    'type': row[1], 'function': row[2], 'rule_significance': row[3],
    'enhanced_boon_house': row[4], 'source': {'title': BOOK,
    'edition': '2023', 'printed_page': row[0], 'pdf_page': row[0]+1,
    'section': 'Dominion Campaign Territories', 'verification': 'text and rendered page checked'},
    'authority': 'rulebook_type_definition', 'revision': REVISION,
} for row in _CARDS}
ALIASES = {'archaeotech': 'archaeotech device', 'mine works': 'mine workings'}

def lookup(value):
    key = normalized(value)
    key = ALIASES.get(key, key)
    return copy.deepcopy(CARDS.get(key))

def for_packet(form, packet):
    """Use explicit current/event type fields, never an incidental prose mention.

    Conflicting or missing types stay unresolved. No current database lookup is
    permitted here: an old event must not inherit today's reclassified type.
    """
    if not (form.startswith('territory_') or form.startswith('place_')):
        return None
    context = packet.get('writer_context') or {}
    state = context.get('state_at_event') or {}
    direct = [context.get('territory_type'), state.get('name')]
    explicit = [lookup(x) for x in direct if x]
    # Baseline evidence is generated by the app, not arbitrary authored prose.
    if not explicit:
        for line in packet.get('evidence', []):
            match = re.fullmatch(r'Recorded type at first description:\s*(.+)', str(line))
            if match: explicit.append(lookup(match[1]))
    # Older territory packets have only an exact type as their subject.
    if not explicit and lookup(packet.get('subject')):
        explicit = [lookup(packet['subject'])]
    found = {x['type']: x for x in explicit if x}
    if len(found) == 1 and all(explicit):
        return {**next(iter(found.values())),
                'boundary': 'General type context only. Benefits are possibilities, not recorded campaign occurrences; House affinity does not identify the owner.'}
    return {'status': 'unverified', 'reason': 'No unique supported territory type; do not fill the rulebook gap from model memory.',
            'revision': REVISION}
