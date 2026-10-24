"""Pure snapshot comparison. This module has no Google access and performs no writes."""
from __future__ import annotations

import re
import unicodedata

def changed_fields(before: dict, after: dict) -> dict:
    keys = set(before) | set(after)
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in sorted(keys)
        if before.get(key) != after.get(key)
    }


def fighter_delta(before: dict[str, dict], after: dict[str, dict]) -> dict:
    old_names, new_names = set(before), set(after)
    return {
        "recruited": sorted(new_names - old_names),
        "removed": sorted(old_names - new_names),
        "changed": {
            name: changed_fields(before[name], after[name])
            for name in sorted(old_names & new_names)
            if changed_fields(before[name], after[name])
        },
    }


GANG_FIELDS = ("name", "gang_type", "credits", "reputation", "rating", "alignment", "colour")
FIGHTER_FIELDS = (
    "Type", "Class", "Cost", "XP", "Kills", "M", "WS", "BS", "S", "T", "W", "I", "A",
    "Ld", "Cl", "Wil", "Int", "Weapons", "Wargear", "Skills", "Advancements", "Effects", "Status",
)
BATTLE_FIELDS = ("date", "scenario", "attacker", "defender", "winner", "territory", "territory_claimer")


def _key(value) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def _gangs(snapshot: dict) -> dict[str, dict]:
    result = {}
    for tab_name, gang in (snapshot.get("gangs") or {}).items():
        gang_id = gang.get("gang_id")
        if gang_id not in (None, ""):
            result[str(gang_id)] = {**gang, "name": gang.get("name") or tab_name}
    return result


def _event(event_key, event_type, source_locator, payload, subjects, occurred_at=None):
    return {
        "event_key": event_key,
        "event_type": event_type,
        "source_locator": source_locator,
        "payload": payload,
        "subjects": subjects,
        "occurred_at": occurred_at,
        "provenance_class": "mechanical_fact",
        "confidence": 1.0,
    }


def _gang_subject(gang_id, gang):
    return {"entity_type": "gang", "entity_key": str(gang_id), "display_name": gang.get("name") or str(gang_id)}


def _fighter_subject(gang_id, name, gang):
    return {
        "entity_type": "fighter",
        "entity_key": f"{gang_id}/{_key(name)}",
        "display_name": name,
        "gang_name": gang.get("name") or str(gang_id),
    }


def _territory_name(row: dict):
    for key in ("Territory", "territory", "Territory Name", "territory_name", "Name", "name"):
        if row.get(key) not in (None, ""):
            return str(row[key])
    return None


def _territory_owner(row: dict):
    for key in ("Gang ID", "gang_id", "Owner ID", "owner_id", "Gang", "gang", "Gang Name", "gang_name", "Owner", "owner"):
        if row.get(key) not in (None, ""):
            return str(row[key])
    return None


def _territories(snapshot: dict):
    records = {}
    ambiguous = set()
    for row_index, row in enumerate(snapshot.get("territories") or []):
        name = _territory_name(row)
        if not name:
            continue
        explicit_id = next((row.get(k) for k in ("Territory ID", "territory_id", "Record ID", "record_id", "ID", "id") if row.get(k) not in (None, "")), None)
        identity = f"id:{explicit_id}" if explicit_id is not None else f"name:{_key(name)}"
        if identity in records:
            ambiguous.add(identity)
        records[identity] = {"name": name, "owner": _territory_owner(row), "source_index": row_index}
    return records, ambiguous


def snapshot_event_drafts(before: dict | None, after: dict, target_snapshot_id: int) -> list[dict]:
    """Return factual event drafts for one consecutive pair of normalized snapshots.

    Snapshot capture time is an observation time, not the time a fighter or territory
    change occurred. Those deltas therefore have no `occurred_at` value. Only battle
    rows carry the source's recorded battle date.
    """
    if not before or before.get("snapshot_version") != after.get("snapshot_version"):
        return []
    drafts = []
    before_gangs, after_gangs = _gangs(before), _gangs(after)

    for gang_id in sorted(set(after_gangs) - set(before_gangs)):
        gang = after_gangs[gang_id]
        gang_subject = _gang_subject(gang_id, gang)
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:gang:{gang_id}:joined", "gang_joined_campaign",
            f"gang:{gang_id}",
            {field: gang.get(field) for field in GANG_FIELDS} | {"fighter_count": len(gang.get("fighters") or {})},
            [{**gang_subject, "role": "affected"}],
        ))
        for name, record in sorted((gang.get("fighters") or {}).items(), key=lambda item: _key(item[0])):
            name_key = _key(name)
            mechanical = {field: record.get(field) for field in FIGHTER_FIELDS if field in record}
            fighter = _fighter_subject(gang_id, name, gang)
            drafts.append(_event(
                f"snapshot:{target_snapshot_id}:fighter:{gang_id}:{name_key}:recruited", "fighter_recruited",
                f"gang:{gang_id}:fighter:{name}", {"present_before": False, "present_after": True, "state": mechanical},
                [{**fighter, "role": "affected"}, {**gang_subject, "role": "gang_context"}],
            ))
    for gang_id in sorted(set(before_gangs) - set(after_gangs)):
        gang = before_gangs[gang_id]
        gang_subject = _gang_subject(gang_id, gang)
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:gang:{gang_id}:unlisted", "gang_unlisted",
            f"gang:{gang_id}",
            {field: gang.get(field) for field in GANG_FIELDS},
            [{**gang_subject, "role": "affected"}],
        ))
        for name, record in sorted((gang.get("fighters") or {}).items(), key=lambda item: _key(item[0])):
            name_key = _key(name)
            mechanical = {field: record.get(field) for field in FIGHTER_FIELDS if field in record}
            fighter = _fighter_subject(gang_id, name, gang)
            drafts.append(_event(
                f"snapshot:{target_snapshot_id}:fighter:{gang_id}:{name_key}:unlisted", "fighter_unlisted",
                f"gang:{gang_id}:fighter:{name}", {"present_before": True, "present_after": False, "last_recorded_state": mechanical},
                [{**fighter, "role": "affected"}, {**gang_subject, "role": "gang_context"}],
            ))

    for gang_id in sorted(set(before_gangs) & set(after_gangs)):
        old, new = before_gangs[gang_id], after_gangs[gang_id]
        gang = new
        gang_subject = _gang_subject(gang_id, gang)
        for field in GANG_FIELDS:
            delta = changed_fields({field: old.get(field)}, {field: new.get(field)})
            if not delta:
                continue
            drafts.append(_event(
                f"snapshot:{target_snapshot_id}:gang:{gang_id}:{field}", f"gang_{field}_changed",
                f"gang:{gang_id}:{field}", {"field": field, **delta[field]}, [gang_subject],
            ))

        old_fighters, new_fighters = old.get("fighters") or {}, new.get("fighters") or {}
        old_by_key = {_key(name): (name, record) for name, record in old_fighters.items()}
        new_by_key = {_key(name): (name, record) for name, record in new_fighters.items()}
        for name_key in sorted(set(new_by_key) - set(old_by_key)):
            name, record = new_by_key[name_key]
            mechanical = {field: record.get(field) for field in FIGHTER_FIELDS if field in record}
            subject = _fighter_subject(gang_id, name, gang)
            drafts.append(_event(
                f"snapshot:{target_snapshot_id}:fighter:{gang_id}:{name_key}:recruited", "fighter_recruited",
                f"gang:{gang_id}:fighter:{name}", {"present_before": False, "present_after": True, "state": mechanical},
                [{**subject, "role": "affected"}, {**gang_subject, "role": "gang_context"}],
            ))
        for name_key in sorted(set(old_by_key) - set(new_by_key)):
            name, record = old_by_key[name_key]
            mechanical = {field: record.get(field) for field in FIGHTER_FIELDS if field in record}
            subject = _fighter_subject(gang_id, name, gang)
            drafts.append(_event(
                f"snapshot:{target_snapshot_id}:fighter:{gang_id}:{name_key}:unlisted", "fighter_unlisted",
                f"gang:{gang_id}:fighter:{name}", {"present_before": True, "present_after": False, "last_recorded_state": mechanical},
                [{**subject, "role": "affected"}, {**gang_subject, "role": "gang_context"}],
            ))
        for name_key in sorted(set(old_by_key) & set(new_by_key)):
            old_name, old_record = old_by_key[name_key]
            new_name, new_record = new_by_key[name_key]
            for field in FIGHTER_FIELDS:
                delta = changed_fields({field: old_record.get(field)}, {field: new_record.get(field)})
                if not delta:
                    continue
                event_type = {
                    "XP": "fighter_xp_changed", "Kills": "fighter_kills_changed",
                    "Advancements": "fighter_advancement_changed", "Effects": "fighter_effects_changed",
                    "Status": "fighter_status_changed", "Weapons": "fighter_weapons_changed",
                    "Wargear": "fighter_wargear_changed", "Skills": "fighter_skills_changed",
                }.get(field, "fighter_stat_changed")
                subject = _fighter_subject(gang_id, new_name, gang)
                drafts.append(_event(
                    f"snapshot:{target_snapshot_id}:fighter:{gang_id}:{name_key}:{field}", event_type,
                    f"gang:{gang_id}:fighter:{new_name}:{field}", {"field": field, **delta[field]},
                    [{**subject, "role": "affected"}, {**gang_subject, "role": "gang_context"}],
                ))

    old_battles = {int(b["source_row"]): b for b in before.get("battles", []) if b.get("source_row") is not None}
    new_battles = {int(b["source_row"]): b for b in after.get("battles", []) if b.get("source_row") is not None}
    gang_by_name = {_key(g.get("name")): (gang_id, g) for gang_id, g in after_gangs.items() if g.get("name")}
    for row_number in sorted(set(new_battles) - set(old_battles)):
        battle = new_battles[row_number]
        subjects = []
        for field, role in (("attacker", "attacker"), ("defender", "defender"), ("winner", "winner"), ("territory_claimer", "claimer")):
            name = battle.get(field)
            found = gang_by_name.get(_key(name)) if name else None
            if found:
                subjects.append({**_gang_subject(found[0], found[1]), "role": role})
        territory = battle.get("territory")
        if territory:
            subjects.append({"entity_type": "territory", "entity_key": _key(territory), "display_name": territory, "role": "location"})
        payload = {field: battle.get(field) for field in BATTLE_FIELDS}
        payload["source_row"] = row_number
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:battle:{row_number}", "battle_result", f"Battles!row {row_number}",
            payload, subjects, occurred_at=battle.get("date"),
        ))
    for row_number in sorted(set(old_battles) & set(new_battles)):
        old, new = old_battles[row_number], new_battles[row_number]
        changes = {field: {"before": old.get(field), "after": new.get(field)} for field in BATTLE_FIELDS if old.get(field) != new.get(field)}
        if not changes:
            continue
        subjects = []
        for battle in (old, new):
            for field, role in (("attacker", "participant"), ("defender", "participant"), ("winner", "winner"), ("territory_claimer", "claimer")):
                name = battle.get(field)
                found = gang_by_name.get(_key(name)) if name else None
                if found:
                    subjects.append({**_gang_subject(found[0], found[1]), "role": role})
        unique_subjects = {(s["entity_type"], s["entity_key"], s["role"]): s for s in subjects}
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:battle-correction:{row_number}", "battle_record_corrected",
            f"Battles!row {row_number}", {"source_row": row_number, "changes": changes},
            # The battle date is not the date the source row was corrected.
            list(unique_subjects.values()), occurred_at=None,
        ))
    for row_number in sorted(set(old_battles) - set(new_battles)):
        battle = old_battles[row_number]
        subjects = []
        for field, role in (("attacker", "participant"), ("defender", "participant"), ("winner", "winner"), ("territory_claimer", "claimer")):
            name = battle.get(field)
            found = gang_by_name.get(_key(name)) if name else None
            if found:
                subjects.append({**_gang_subject(found[0], found[1]), "role": role})
        if battle.get("territory"):
            territory = battle["territory"]
            subjects.append({"entity_type": "territory", "entity_key": _key(territory), "display_name": territory, "role": "location"})
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:battle-removed:{row_number}", "battle_record_removed",
            f"Battles!row {row_number}", {"source_row": row_number, "last_recorded": {field: battle.get(field) for field in BATTLE_FIELDS}},
            subjects, occurred_at=None,
        ))

    old_territories, old_ambiguous = _territories(before)
    new_territories, new_ambiguous = _territories(after)
    for identity in sorted((set(old_territories) & set(new_territories)) - old_ambiguous - new_ambiguous):
        old, new = old_territories[identity], new_territories[identity]
        if old["owner"] == new["owner"]:
            continue
        name = new["name"]
        subjects = [{"entity_type": "territory", "entity_key": _key(name), "display_name": name, "role": "location"}]
        for owner, role in ((old["owner"], "former_holder"), (new["owner"], "new_holder")):
            found = after_gangs.get(owner) or gang_by_name.get(_key(owner), (None, None))[1]
            if found:
                subjects.append({**_gang_subject(found.get("gang_id"), found), "role": role})
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:territory:{identity}:holder", "territory_holder_changed",
            f"Territories:{identity}", {"territory": name, "before_owner": old["owner"], "after_owner": new["owner"]},
            subjects,
        ))

    return sorted(drafts, key=lambda item: (item["event_type"], item["event_key"]))
