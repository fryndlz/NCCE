"""Resolve provenance-labelled faction / gang / individual writer voice profiles.

The JSON registry is editorial guidance, never mechanical or historical evidence.
Fighters attached to a host gang may have a different faction and local register.
Unknown and pending gangs do not acquire fabricated stylistic identities.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "voice_registry.v1.json"
PROFILE_VERSION = 1
GUARDRAILS = [
    "Event mechanics, chronology and the fighter's actual awareness outrank all voice tags.",
    "Faction supplies social frame; gang supplies local register; individual provides distinct perspective.",
    "An accepted biography is a voice lens, not evidence that its anecdotes happened in a new memory event.",
    "Never leak GM-only secrets into ordinary memory context without explicit character-specific awareness.",
    "Do not derive gender, private thought, ethnicity, sentience, battle attendance or nationality from names, role or stylistic comparisons.",
    "A host gang does not confer its culture on externally affiliated fighters.",
    "An unapproved or unknown profile stays neutral; never auto-generate an accent or personality.",
]


def validate_registry(data):
    if not isinstance(data, dict) or data.get("schema_version") != PROFILE_VERSION:
        raise ValueError("Unsupported NCCE voice registry schema")
    for key in ("factions", "gangs", "individuals", "attachments", "aliases"):
        if not isinstance(data.get(key), dict):
            raise ValueError("Missing voice registry mapping: " + key)
    if not isinstance(data.get("excluded_gangs"), list):
        raise ValueError("Missing excluded_gangs list")
    for kind in ("factions", "gangs", "individuals"):
        for key, value in data[kind].items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("Invalid " + kind + " record")
            if not isinstance(value.get("tags", []), list) or any(not isinstance(x, str) for x in value.get("tags", [])):
                raise ValueError("Invalid voice tags in " + kind + ":" + key)
            if not isinstance(value.get("source", ""), str):
                raise ValueError("Voice source must be a string: " + key)
            if value.get("review_status", "approved") not in ("approved", "pending_editorial"):
                raise ValueError("Unknown review status: " + key)
    for key, value in data["attachments"].items():
        if "::" not in key or not isinstance(value, list) or len(value) != 2 or not all(isinstance(x, str) for x in value):
            raise ValueError("Invalid attachment mapping: " + key)
    for key, value in data["aliases"].items():
        if not isinstance(key, str) or value not in data["gangs"]:
            raise ValueError("Alias must target an existing gang: " + str(key))
    if set(data["excluded_gangs"]) & set(data["gangs"]):
        raise ValueError("An excluded gang cannot have an active profile")
    return data


@lru_cache(maxsize=1)
def load_registry():
    with REGISTRY_PATH.open(encoding="utf-8") as file:
        return validate_registry(json.load(file))


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _profile(base, record):
    if not isinstance(record, dict):
        return base
    if record.get("review_status", "approved") != "approved":
        base["review_status"] = "pending_editorial"
        return base
    base.update(record)
    return base


def build_voice_layers(context, registry=None):
    """Build only provenance-labelled editorial cues from known identity data.

    An optional injected registry is used for tests and owner-assisted onboarding.
    Never inspect fighter mechanics to invent voice.
    """
    data = validate_registry(registry) if registry is not None else load_registry()
    if not isinstance(context, dict):
        context = {}
    gang_raw = _text(context.get("gang")) or _text(context.get("host_gang"))
    if not gang_raw and not context.get("subject_name"):
        gang_raw = _text(context.get("name"))
    host = data["aliases"].get(gang_raw, gang_raw)
    subject = _text(context.get("subject_name"))
    faction_name = _text(context.get("affiliation")) or _text(context.get("faction"))
    inferred = context.get("inferred_identity") or []
    role = fighter_type = ""
    if isinstance(inferred, list):
        for item in inferred:
            if not isinstance(item, dict) or item.get("source") != "mechanical_fact":
                continue
            if item.get("label") == "Recorded role":
                role = _text(item.get("value"))
            elif item.get("label") == "Recorded fighter type":
                fighter_type = _text(item.get("value"))

    excluded = host in data["excluded_gangs"]
    attached = data["attachments"].get(host + "::" + subject) if host and subject else None
    style_name = attached[1] if attached else host
    if attached:
        faction_name = attached[0]
    elif not faction_name and style_name in data["gangs"]:
        faction_name = data["gangs"][style_name].get("faction", "")

    faction = {"name": faction_name, "tags": [], "provenance": "recorded_affiliation" if faction_name else "unknown"}
    gang = {"name": style_name, "tags": [], "provenance": "recorded_affiliation" if host else "unknown"}
    individual = {"name": subject, "role": role, "fighter_type": fighter_type,
                  "tags": [], "provenance": "recorded_role_only"}

    if excluded:
        gang["review_status"] = "excluded_until_onboarded"
    else:
        faction = _profile(faction, data["factions"].get(faction_name))
        gang = _profile(gang, data["gangs"].get(style_name))
        if attached:
            gang["host_gang"] = gang_raw
            gang["provenance"] = "authored_external_affiliation"
        profile = data["individuals"].get(host + "::" + subject)
        if profile is None and attached:
            profile = data["individuals"].get(style_name + "::" + subject)
        individual = _profile(individual, profile)
        if profile is not None and individual.get("tags"):
            individual["provenance"] = profile.get("provenance") or ("accepted_biography_voice_inference" if profile.get("source") else "owner_editorial_from_accepted_examples")

    return {
        "schema_version": PROFILE_VERSION,
        "registry_version": data.get("registry_version", ""),
        "purpose": "writer_style_guidance_only",
        "composition_order": ["source_event_and_awareness", "faction", "gang", "individual"],
        "faction": faction, "gang": gang, "individual": individual,
        "guardrails": GUARDRAILS,
    }
