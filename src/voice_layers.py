"""Provenance-labelled voice cues for external NCCE writing packets.

Voice layers are writing guidance, not event facts, stable fighter attributes or
mechanical changes. Only explicit editorial profiles receive dialect/style tags.
Unknown gangs and fighters retain their known names/roles without invented traits.
"""
from __future__ import annotations

PROFILE_VERSION = 1

FACTION_PROFILES = {
    "House Orlock": {
        "tags": ["industrial_labour", "mining", "haulage", "road_crews", "crew_reputation"],
        "lens": "Working House of Iron: freight, dangerous labour, roads and crew ties. Do not assume every Orlock works on the road.",
        "provenance": "rulebook_lore",
        "source": "Necromunda: House of Iron",
    },
}

GANG_PROFILES = {
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
    if not faction_name and gang_name in GANG_PROFILES:
        faction_name = GANG_PROFILES[gang_name]["faction"]

    faction = {"name": faction_name, "tags": [], "provenance": "recorded_affiliation" if faction_name else "unknown"}
    if faction_name in FACTION_PROFILES:
        faction.update(FACTION_PROFILES[faction_name])

    gang = {"name": gang_name, "tags": [], "provenance": "recorded_affiliation" if gang_name else "unknown"}
    if gang_name in GANG_PROFILES:
        gang.update({key: value for key, value in GANG_PROFILES[gang_name].items() if key != "faction"})

    individual = {
        "name": subject_name, "role": role, "fighter_type": fighter_type,
        "tags": [], "provenance": "recorded_role_only",
    }
    entry = INDIVIDUAL_PROFILES.get((gang_name, subject_name))
    if entry:
        individual.update(entry)
        individual["provenance"] = "owner_editorial_from_accepted_examples"

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
