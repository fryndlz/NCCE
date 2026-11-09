"""Provenance-labelled voice cues for external NCCE writing packets.

Voice layers are writing guidance, not event facts, stable fighter attributes or
mechanical changes. Only explicit editorial profiles receive dialect/style tags.
Unknown gangs and fighters retain their known names/roles without invented traits.
"""
from __future__ import annotations

PROFILE_VERSION = 1

FACTION_PROFILES = {
    "Ironhead Squat Prospectors": {
        "tags": ["ancestral_charters", "kinship", "claims_and_shares", "independent_prospecting", "engineering", "inheritance"],
        "lens": "Necromundan Ironhead Kin: ancestral Great Charters, fierce claim rights, prospecting, mechanical ingenuity, wealth and reputation. Lost Urlish Core is NOT an active oracle; no generic fantasy dwarf dialect.",
        "provenance": "rulebook_lore_and_accepted_campaign_style",
        "source": "Necromunda: Halls of the Ancients; accepted Helmaeth biographies, NCCE faction biography styles",
    },
    "House Van Saar": {
        "tags": ["technological_specialisation", "clearance_hierarchy", "equipment_maintenance", "controlled_knowledge", "radiation_risk"],
        "lens": "Van Saar technology and House hierarchy: capability is not clearance, instruments may fail to capture human consequences, technical work carries hidden costs. STC access is restricted and NEVER generic fighter knowledge.",
        "provenance": "rulebook_lore_and_accepted_campaign_style",
        "source": "Necromunda: House of Artifice; accepted Ethernetans biographies, NCCE faction biography styles",
    },
    "House Ran Lo": {
        "tags": ["financial_patronage", "credit_and_debt", "auditing_conclave", "noble_house_interest"],
        "lens": "Noble House financial influence: mutual profit, patronage, auditing, debt and commercially motivated armed support. An allied auditor is not a Squat and does not necessarily oppose the gang.",
        "provenance": "rulebook_lore_and_accepted_campaign_style",
        "source": "Necromunda: House of Iron; accepted Eliot Ness Gelt-scrivener document and owner direction for Frank J. WIlson",
    },
    "House Helmawr": {
        "tags": ["noble_household_authority", "sealed_orders", "protective_duty", "privilege_and_access", "custody"],
        "lens": "The Palanite Household protects the Imperial House's assigned interests under sealed authority. Its Companions are privileged attachments, NOT ordinary precinct Enforcers or Van Saar technicians.",
        "provenance": "accepted_campaign_style",
        "source": "Accepted Dredd 2D and Dredd 3D Household attachment directives; NCCE faction biography styles",
    },
    "House Orlock": {
        "tags": ["industrial_labour", "mining", "haulage", "road_crews", "crew_reputation"],
        "lens": "Working House of Iron: freight, dangerous labour, roads and crew ties. Do not assume every Orlock works on the road.",
        "provenance": "rulebook_lore",
        "source": "Necromunda: House of Iron",
    },
}

GANG_PROFILES = {
    "Helmaeth Expeditionary Force": {
        "faction": "Ironhead Squat Prospectors",
        "tags": ["helmaeth_kin", "speculative_claims", "dangerous_recovery", "hard_bargains", "ancestral_reputation", "raider_heritage"],
        "register": "Kin among the prospectors: plain, stubborn, commercially sharp; talk about shares, seams, recoveries, the Charter, tools, claimed ground and family names. Dry wry humour, not bureaucratic compliance prose or generic fantasy-dwarf speech. Helmaeth's pirate/poison-sea history is heritage, not an assumed current Dominion mission.",
        "provenance": "accepted_generated_fiction_style_with_owner_correction",
        "source": "Accepted Helmaeth Charter Roll entries and owner correction (8 Nov 2026), NCCE Faction biography styles",
    },
    "Ethernetans 2.0": {
        "faction": "House Van Saar",
        "tags": ["field_tech_detail", "data_and_measurement", "technical_risk", "clearance_conflict", "equipment_recovery"],
        "register": "Technically precise, restrained and dryly sardonic; people register calibration, failure modes, risk, permissions and recoverability in different ways. A field Tek-hunter need not sound like an Archeotek or a maintenance Subtek. No generic 'logical' robot talk.",
        "provenance": "accepted_generated_fiction_style",
        "source": "Accepted Maex, Sigmund, Larz Pulse and Peter Apex records; NCCE Faction biography styles",
    },
    "Auditing Conclave": {
        "faction": "House Ran Lo",
        "tags": ["allied_financial_delegation", "profit_protection", "debt_service"],
        "register": "Controlled and sharp language of credit, risks, obligations and collection. Avoid assuming hostility to the ally; Auditor and indebted Gelt-scrivener have different interests and voices.",
        "provenance": "owner_editorial_and_accepted_generated_fiction",
        "source": "Approved Eliot Ness bonded service, Queue row 107; owner-described Ran Lo alliance",
    },
    "Palanite Household Companions": {
        "faction": "House Helmawr",
        "tags": ["sealed_household_orders", "protective_attachment", "independent_chain_of_command", "controlled_information"],
        "register": "Restrained, severe and economical. Duty defined by sealed Household interest; high authority without public explanation. First-person thoughts need not sound like directives. Avoid automatic fanatical belief, mindlessness or clone kinship.",
        "provenance": "accepted_generated_fiction_style",
        "source": "Accepted Dredd 2D / Dredd 3D directives, NCCE Faction biography styles",
    },
    "The Slag Eaters": {
        "faction": "House Orlock",
        "tags": ["texan_road_gang", "working_road_crew", "rough_wit", "truckers_and_outlaws"],
        "register": "Texan-flavoured road-gang English: natural colloquial rhythm, dry humour, plain-speaking, road and iron vocabulary. Avoid phonetic caricature, forced yeehaws and identical accents.",
        "provenance": "owner_editorial",
        "source": "NCCE writing conversation, owner approval 2026-11-09; accepted Slag Eaters biographies",
    },
}

# Individual cues explicitly accepted in editorial discussion, never inferred from
# rank, a fighter's name alone, XP/kills, or automatically generated memories.
INDIVIDUAL_PROFILES = {
    ("Helmaeth Expeditionary Force", "Horgar"): {
        "tags": ["speculative_ambition", "discoverer_credit"],
        "register": "Would rather risk a new strike than take safe sorting wages; cares that the discoverer's name is recorded.",
        "source": "Accepted Horgar sign-on, Queue row 90",
    },
    ("Helmaeth Expeditionary Force", "Dwalin"): {
        "tags": ["hands_on_machine_judgement", "crew_before_cargo"],
        "register": "Machine operator listens to stressed plant; willing to cut loose valuable cargo to bring kin back.",
        "source": "Accepted Dwalin sign-on, Queue row 91",
    },
    ("Helmaeth Expeditionary Force", "Snarn"): {
        "tags": ["survey_precision", "shared_kin_maps"],
        "register": "Trusts soundings and maps more than assurances; wants routes recorded for the kin.",
        "source": "Accepted Snarn sign-on, Queue row 92",
    },
    ("Helmaeth Expeditionary Force", "Bimbur"): {
        "tags": ["apprentice_credit", "hard_bargaining"],
        "register": "Hard-headed Exo Master who insists junior labour gets named and paid, even at personal cost.",
        "source": "Accepted Bimbur sign-on, Queue row 93",
    },
    ("Helmaeth Expeditionary Force", "Tofur"): {
        "tags": ["independent_accountability", "quiet_reliability"],
        "register": "Dependable stores hand who wants to be judged and paid for work, without another kin vouching.",
        "source": "Accepted Tofur sign-on, Queue row 94",
    },
    ("Helmaeth Expeditionary Force", "Dorin"): {
        "tags": ["skeptical_questions", "recorded_dissent"],
        "register": "Questions instructions and who owns their consequences; maintains the right to record an objection, not to disregard an order.",
        "source": "Accepted Dorin sign-on, Queue row 95",
    },
    ("Helmaeth Expeditionary Force", "Brokk"): {
        "tags": ["measurement_integrity", "refuses_false_certainty"],
        "register": "Precise specialist; distinguishes sound measurement from guarantees about yield.",
        "source": "Accepted Brokk sign-on, Queue row 96",
    },
    ("Helmaeth Expeditionary Force", "Dazor"): {
        "tags": ["parley_before_battle", "defends_claim_rights"],
        "register": "Claim defender who wants authority to negotiate before risking a fight; not a pacifist or a claim adjudicator.",
        "source": "Accepted Dazor sign-on, Queue row 99",
    },
    ("Helmaeth Expeditionary Force", "Thrain"): {
        "tags": ["charter_master", "claims_and_common_account"],
        "register": "Leads the expedition and weighs opportunity against claim rights, crew shares and communal risk.",
        "source": "Accepted Thrain charter, Queue row 103",
    },
    ("Helmaeth Expeditionary Force", "Brint"): {
        "tags": ["battle_hardened_claim_guard", "withdrawal_responsibility"],
        "register": "Veteran Drill Master; remembers kin lost defending untenable seams; insists retreat and stand-fast orders carry responsibility.",
        "source": "Accepted Brint sign-on, Queue row 105",
    },
    ("Ethernetans 2.0", "Maex"): {
        "tags": ["curious_salvager", "tests_clearance_boundaries"],
        "register": "Quick with repairs; curiosity about the next sealed mechanism exceeds assigned access.",
        "source": "Accepted Maex personnel register, Queue row 84",
    },
    ("Ethernetans 2.0", "Sigmund"): {
        "tags": ["private_exposure_records", "distrusts_nominal_safety"],
        "register": "Exacting Tek-hunter; notices symptoms dismissed by passing instrument readings; quietly keeps a second ledger.",
        "source": "Accepted Sigmund reliability register, Queue row 86",
    },
    ("Ethernetans 2.0", "Larz Pulse"): {
        "tags": ["fire_control_geometry", "collateral_awareness"],
        "register": "Practical field specialist; thinks in lines of fire, secondary effects and where a shot goes after impact.",
        "source": "Accepted Larz Pulse fire-control record, Queue row 87",
    },
    ("Ethernetans 2.0", "Peter Apex"): {
        "tags": ["restricted_archeotek_perspective", "underhive_salvage_origin", "humility_before_ancient_technology"],
        "register": "Archeotek once valued devices for salvage; an exceptionally permitted partial view of ancient STC apparatus sharpened caution about what should be opened. Do NOT generalize this clearance.",
        "source": "Accepted Peter Apex restricted record, Queue row 88",
    },
    ("Helmaeth Expeditionary Force", "Eliot Ness"): {
        "tags": ["bonded_debt_service", "insists_on_debt_reduction"],
        "register": "Indebted Gelt-scrivener assigned to the Auditor; presses for service pay to reduce the ledger rather than roll into further charges.",
        "source": "Approved Eliot Ness document, Queue row 107",
    },
    ("Ethernetans 2.0", "Dredd 2D"): {
        "tags": ["sealed_household_duty", "conditioned_guard", "no_local_reassignment"],
        "register": "Household protective attachment, conditioned for service; obeys sealed interests rather than Ethernetans' recovery priorities. Private beliefs remain unknown.",
        "source": "Accepted Dredd 2D attachment directive, Queue row 80",
    },
    ("Ethernetans 2.0", "Dredd 3D"): {
        "tags": ["independent_household_authority", "sealed_service_particulars", "no_local_reassignment"],
        "register": "Household Companion who may act to protect sealed interests without technical officers' permission; personal motives and earlier service remain unknown.",
        "source": "Accepted Dredd 3D attachment directive, Queue row 89",
    },
    ("The Slag Eaters", "John Bullet"): {
        "tags": ["sharp_tongued", "supplier_sceptic", "trader_pragmatism"],
        "register": "Suspicious ammo merchant; sly, practical, speaks of stock, faults, suppliers and prices.",
    },
    ("The Slag Eaters", "Boomer"): {
        "tags": ["impulsive", "risk_taker", "fast_conversational"],
        "register": "Young hotshot; quicker and more animated, minimizes danger, never claims unrecorded heroics.",
    },
    ("The Slag Eaters", "Eisen"): {
        "tags": ["economical", "commanding", "methodical"],
        "register": "Seasoned road captain; concise and authoritative; preparation rather than bravado.",
    },
}


# Explicit, accepted external attachments: the host gang does not supply the
# individual's faction or local voice. Never guess these from fighter rank alone.
ATTACHMENTS = {
    ("Helmaeth Expeditionary Force", "Frank J. WIlson"): ("House Ran Lo", "Auditing Conclave"),
    ("Helmaeth Expeditionary Force", "Eliot Ness"): ("House Ran Lo", "Auditing Conclave"),
    ("Helmaeth Expeditionary Force", "Bop"): ("", "Independent Hired Gun"),
    ("Helmaeth Expeditionary Force", "Alrik III"): ("", "Independent Prospecting Retainer"),
    ("Ethernetans 2.0", "Dredd 2D"): ("House Helmawr", "Palanite Household Companions"),
    ("Ethernetans 2.0", "Dredd 3D"): ("House Helmawr", "Palanite Household Companions"),
}


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def build_voice_layers(context):
    """Build independent faction/gang/fighter lenses from supplied context.

    No live roster queries, generated prose interpretation or historical
    extrapolation. Keys are deliberately separate to avoid personality
    laundering through faction affiliation.
    """
    if not isinstance(context, dict):
        context = {}
    gang_name = _text(context.get("gang")) or _text(context.get("name"))
    faction_name = _text(context.get("affiliation")) or _text(context.get("faction"))
    subject_name = _text(context.get("subject_name"))
    inferred = context.get("inferred_identity") or []
    role, fighter_type = "", ""
    if isinstance(inferred, list):
        for item in inferred:
            if not isinstance(item, dict) or item.get("source") != "mechanical_fact":
                continue
            if item.get("label") == "Recorded role":
                role = _text(item.get("value"))
            elif item.get("label") == "Recorded fighter type":
                fighter_type = _text(item.get("value"))
    attachment = ATTACHMENTS.get((gang_name, subject_name))
    style_gang_name = attachment[1] if attachment else gang_name
    if attachment:
        faction_name = attachment[0]  # Canonical House affiliation overrides host roster location.
    if not faction_name and style_gang_name in GANG_PROFILES:
        faction_name = GANG_PROFILES[style_gang_name]["faction"]

    faction = {"name": faction_name, "tags": [], "provenance": "recorded_affiliation" if faction_name else "unknown"}
    if faction_name in FACTION_PROFILES:
        faction.update(FACTION_PROFILES[faction_name])

    gang = {"name": style_gang_name, "tags": [], "provenance": "recorded_affiliation" if gang_name else "unknown"}
    if attachment:
        gang["host_gang"] = gang_name
        gang["provenance"] = "accepted_attachment_biography"
    if style_gang_name in GANG_PROFILES:
        gang.update({key: value for key, value in GANG_PROFILES[style_gang_name].items() if key != "faction"})

    individual = {
        "name": subject_name, "role": role, "fighter_type": fighter_type,
        "tags": [], "provenance": "recorded_role_only",
    }
    entry = INDIVIDUAL_PROFILES.get((gang_name, subject_name))
    if entry:
        individual.update(entry)
        individual["provenance"] = "accepted_biography_voice_inference" if entry.get("source") else "owner_editorial_from_accepted_examples"

    return {
        "schema_version": PROFILE_VERSION,
        "purpose": "writer_style_guidance_only",
        "composition_order": ["source_event_and_awareness", "faction", "gang", "individual"],
        "faction": faction,
        "gang": gang,
        "individual": individual,
        "guardrails": [
            "Event mechanics, provenance and chronology override all voice cues.",
            "Faction supplies social vocabulary, gang supplies local register, individual supplies personal diction and priorities.",
            "Do not infer nationality or in-world Earth origin from a stylistic reference to Texas.",
            "No invented witnessed battle actions, kills, injuries, motives or historical relationships.",
            "Accepted biography informs perspective but is not a new memory event.",
            "Unknown personal voice stays neutral; never copy the gang dialect uniformly into every fighter.",
        ],
    }
