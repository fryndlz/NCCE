"""Portable NCCE literary layer, selected AFTER evidence and voice identity.

This module does not write prose, change mechanics, or approve drafts.  It
supplies form-specific craft guidance, correctly scoped gang registers, and
source-labelled non-exhaustive examples to newly prepared writing packets.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "literary_profiles.v2.json"
STANDARD_BIO = "fighter_biography"


@lru_cache(maxsize=1)
def load_literary_policy():
    data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    validate_policy(data)
    return data


def validate_policy(data):
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise ValueError("Unsupported literary policy schema")
    for k in ("form_overrides", "universal_craft", "faction_profiles",
              "gang_profiles", "example_library", "policy_boundaries"):
        if k not in data or not isinstance(data[k], (dict if k != "example_library" and k != "universal_craft" else list)):
            raise ValueError("Malformed literary policy: " + k)
    biography = data["form_overrides"].get(STANDARD_BIO, {})
    span = biography.get("target_characters")
    cap = biography.get("hard_max_characters")
    if (not isinstance(span, list) or len(span) != 2 or
        any(type(x) is not int or x <= 0 for x in span) or
        span[0] > span[1] or type(cap) is not int or cap < span[1]):
        raise ValueError("Invalid owner-directed biography target/cap policy")
    if any(x.get("status", "").strip() == "" or not x.get("source") for x in data["example_library"]):
        raise ValueError("All literary examples need provenance labels and a source")
    if len({x["id"] for x in data["example_library"]}) != len(data["example_library"]):
        raise ValueError("Duplicate literary exemplar ID")
    return data


def measure_prose(form, markdown, data=None):
    """An explicit craft gate, never an automatic edit or publication decision."""
    if not isinstance(markdown, str):
        raise ValueError("Prose must be a Markdown string")
    data = data or load_literary_policy()
    rule = data["form_overrides"].get(form, {})
    count = len(markdown)
    hard = rule.get("hard_max_characters")
    target = rule.get("target_characters")
    return {
        "form": form,
        "characters_including_markdown": count,
        "target_characters": target,
        "hard_max_characters": hard,
        "within_target": None if not target else target[0] <= count <= target[1],
        "hard_limit_ok": hard is None or count <= hard,
        "status": "over_hard_cap" if hard is not None and count > hard else
                  ("outside_target_review" if target and not target[0] <= count <= target[1] else "ok"),
    }


def resolve_literary_policy(form, voice_layers=None, gang=None, faction=None,
                            audience=None, genre=None, data=None):
    """Resolve a single form+speaker+audience lens with deliberate neutral fallback.

    The voice layer provides the canonical *stylistic* affiliation, including
    external attachments, so outsiders never borrow the hosting gang's prose.
    Unapproved Patrol cultures never inherit Kły's style.
    """
    data = data or load_literary_policy()
    validate_policy(data)
    voices = voice_layers if isinstance(voice_layers, dict) else {}
    group = voices.get("gang") if isinstance(voices.get("gang"), dict) else {}
    base = voices.get("faction") if isinstance(voices.get("faction"), dict) else {}
    gang_name = group.get("name") or gang or ""
    faction_name = base.get("name") or faction or ""
    if group.get("review_status") in ("pending_editorial", "excluded_until_onboarded"):
        gang_profile = None
    else:
        gang_profile = data["gang_profiles"].get(gang_name)
    faction_profile = data["faction_profiles"].get(faction_name)
    examples = [deepcopy(x) for x in data["example_library"]
                if x["gang"] == gang_name and x["form"] == form][:2]
    form_rules = deepcopy(data["form_overrides"].get(form, {}))
    return {
        "schema_version": data["schema_version"],
        "literary_version": data["policy_version"],
        "purpose": "literary_craft_guidance_only",
        "form": form,
        "form_rules": form_rules,
        "unlisted_form": form not in data["form_overrides"],
        "fallback": "Use the active NCCE runtime form contract for this form; no biography limits for other forms.",
        "faction": {"name": faction_name, "profile": deepcopy(faction_profile)} if faction_profile else
                   {"name": faction_name, "profile": None},
        "gang": {"name": gang_name, "profile": deepcopy(gang_profile)} if gang_profile else
                {"name": gang_name, "profile": None},
        "narrator_audience": audience or "not provided; use the requested context, never assume a superior's document",
        "document_genre": genre or "not provided; choose only where the request warrants it",
        "craft": list(data["universal_craft"]),
        "example_policy": "Illustrative, non-exhaustive; never copy characters, mechanics, structure or phrases as a template.",
        "illustrative_examples": examples,
        "knowledge_order": ["documented_character_knowledge_at_event",
                            "document_audience", "document_genre"],
        "review": {"draft_state": "WRITING until explicit owner approval",
                   "ready_state": "READY only for the verified approved exact text",
                   "existing_prose": "never rewrite existing requests when style policy changes"},
        "source": "NCCE portable prose skill and owner-authorized decisions; exemplar sources individually labelled",
    }
