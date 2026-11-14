"""Source-audited placement policy for the Slag Eaters' 2026-10-25 roster normalization.

The campaign ledger remains immutable. These precise event IDs were checked
against Writing Exchange Bulk Context evidence: the tokens before and after
are equivalent, differing in semicolon/newline formatting or Effects/Injuries
field category only. They are observations of an existing state, not fresh
injuries, advancements, deaths, or clock ticks.

An accepted writer correction is preserved under the same memory key/receipt;
the presentation places the text in a Continuity section rather than a dated
incident timeline. Future unknown events are not inferred from this list.
"""
from __future__ import annotations

SOURCE_NORMALIZATIONS = {
    # Original Bulk Items row: event ID, evidence-bound classification.
    "8bfd161b99e8e24f88ab9320e3bbcb69": (28, "Boomer", "Enfeebled and Convalescence remain recorded; Effects moved to Injuries."),
    "9b9a08f478b6b225c58913ca6f280523": (30, "Eisen", "Existing Ballistic Skill and Toughness advancements were reformatted."),
    "f2a5cdbb717880e02eea97dcddb1f19a": (33, "Gauge", "Existing Movement and Willpower advancements were reformatted."),
    "562ad8097d694f950181ae8d0daedfec": (36, "Gregg", "Existing Toughness and Weapon Skill advancements were reformatted."),
    "3da73a2cefb118ce50deb36568ff04f3": (37, "Dax", "Horrid Scars and Out Cold remain recorded; Effects moved to Injuries."),
    "9100fe0ca8aaecc3c69686ca40de30dc": (38, "Dax", "Existing Ballistic Skill and Toughness advancements were reformatted."),
    "6db2585eb6c8c442286c45b5994f9273": (39, "Ash", "Spinal Injury was already recorded in the baseline; Effects moved to Injuries."),
    "aeadf5ad1be16c935145895a392a84f1": (40, "Ash", "The same five advancements were known in baseline; only list formatting changed."),
    "aada947d40ba33bcf179e8a6f281f7d1": (41, "Juvie", "Memorable Death was already recorded; Effects moved to Injuries. This is not a second death."),
    "be508312f7f291699f8aa4637110bf71": (42, "Duster", "Hand Injury, Partially Deafened and Humiliated were already recorded; Effects moved to Injuries."),
}

# The undated Juvie legacy snapshot itself reports status Killed.
# It cannot date or authenticate the earlier first-person imagined vignette.
UNANCHORED_LEGACY_VIGNETTE = "legacy:14"


def is_source_normalization(event_id):
    return event_id in SOURCE_NORMALIZATIONS


def placement(memory):
    ids = memory.get("source_event_ids", [])
    if memory.get("memory_type") == "observation" and len(ids) == 1:
        item = SOURCE_NORMALIZATIONS.get(ids[0])
        if item:
            return {
                "class": "continuity",
                "source_kind": "roster_field_normalization",
                "bulk_row": item[0],
                "note": item[2] + " The later snapshot observation is not the occurrence date. Published prose retained unchanged.",
                "incident_count": 0,
            }
    if (memory.get("memory_type") == "observation"
            and memory.get("memory_key") == UNANCHORED_LEGACY_VIGNETTE
            and memory.get("baseline")):
        return {
            "class": "undated_vignette",
            "source_kind": "undated_baseline",
            "bulk_row": 8,
            "note": "The recorded baseline already lists Juvie as Killed. This first-person fictional vignette has no sourced pre-death date and must not be read as a later living incident.",
            "incident_count": 0,
        }
    return None
