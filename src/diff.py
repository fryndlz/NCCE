"""Pure snapshot comparison. This module has no Google access and performs no writes."""
from __future__ import annotations

import re
import unicodedata
from snapshot import battle_content_signature, battle_identity, battle_records

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
BATTLE_FIELDS = ("date", "scenario", "attacker", "defender", "winner", "territory", "territory_claimer", "notes")


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


def _battle_source_id(battle: dict):
    value = battle.get("source_battle_id") or battle.get("battle_id")
    if value:
        return str(value)
    key = str(battle.get("battle_key") or battle.get("source_battle_key") or "")
    return key[3:].split("#duplicate:", 1)[0] if key.startswith("id:") else None


def _battle_ids_compatible(old: dict, new: dict) -> bool:
    old_id, new_id = _battle_source_id(old), _battle_source_id(new)
    return not old_id or not new_id or old_id == new_id


def _matched_battles(old_rows: list[dict], new_rows: list[dict]):
    """Pair encounters independently of source-row insertion or ordering.

    Source IDs are strongest. Unique fallback identities bridge legacy data and
    newly discovered IDs. Ambiguous fallback duplicates are matched only when
    their full content agrees; edits to them stay separate removal/addition
    events rather than being silently merged.
    """
    old = {battle_identity(row): row for row in battle_records(old_rows)}
    new = {battle_identity(row): row for row in battle_records(new_rows)}
    paired = [(old.pop(key), new.pop(key)) for key in sorted(set(old) & set(new))]

    old_groups, new_groups = {}, {}
    for key, row in old.items():
        old_groups.setdefault(battle_identity(row, prefer_source=False), []).append(key)
    for key, row in new.items():
        new_groups.setdefault(battle_identity(row, prefer_source=False), []).append(key)
    for fallback in sorted(set(old_groups) & set(new_groups)):
        old_keys, new_keys = old_groups[fallback], new_groups[fallback]
        if len(old_keys) == len(new_keys) == 1:
            old_key, new_key = old_keys[0], new_keys[0]
            if _battle_ids_compatible(old[old_key], new[new_key]):
                paired.append((old.pop(old_key), new.pop(new_key)))
            continue
        for old_key in old_keys:
            if old_key not in old:
                continue
            matches = [key for key in new_keys if key in new and _battle_ids_compatible(old[old_key], new[key]) and battle_content_signature(old[old_key]) == battle_content_signature(new[key])]
            if matches:
                new_key = sorted(matches, key=lambda key: int(new[key].get("source_row") or 0))[0]
                paired.append((old.pop(old_key), new.pop(new_key)))

    # An isolated edit to date, scenario or a party can change the fallback
    # identity. Accept it as a correction only if two identity components and
    # the worksheet row still agree, with no unrelated unmatched encounters.
    if len(old) == len(new) == 1:
        old_key, new_key = next(iter(old)), next(iter(new))
        a, b = old[old_key], new[new_key]
        same = sum((
            _key(a.get("date")) == _key(b.get("date")),
            _key(a.get("scenario")) == _key(b.get("scenario")),
            sorted(_key(a.get(k)) for k in ("attacker", "defender")) == sorted(_key(b.get(k)) for k in ("attacker", "defender")),
        ))
        if a.get("source_row") == b.get("source_row") and same >= 2 and _battle_ids_compatible(a, b):
            paired.append((old.pop(old_key), new.pop(new_key)))
    return paired, list(old.values()), list(new.values())


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

    matched_battles, removed_battles, added_battles = _matched_battles(before.get("battles", []), after.get("battles", []))
    gang_by_name = {_key(g.get("name")): (gang_id, g) for gang_id, g in after_gangs.items() if g.get("name")}
    for battle in sorted(added_battles, key=battle_identity):
        row_number, battle_key = battle.get("source_row"), battle_identity(battle)
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
        payload.update(source_row=row_number, battle_key=battle_key, source_battle_key=battle_key)
        if battle.get("source_battle_id"):
            payload["source_battle_id"] = battle["source_battle_id"]
        drafts.append(_event(
            f"snapshot:{target_snapshot_id}:battle:{battle_key}", "battle_result", f"Battles!battle {battle_key}",
            payload, subjects, occurred_at=battle.get("date"),
        ))
    for old, new in sorted(matched_battles, key=lambda pair: battle_identity(pair[1])):
        row_number, battle_key = new.get("source_row"), battle_identity(new)
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
            f"snapshot:{target_snapshot_id}:battle-correction:{battle_key}", "battle_record_corrected",
            f"Battles!battle {battle_key}", {"source_row": row_number, "previous_source_row": old.get("source_row"), "battle_key": battle_key, "source_battle_key": battle_key, "previous_source_battle_key": battle_identity(old), "changes": changes, "current": {field: new.get(field) for field in BATTLE_FIELDS}},
            # The battle date is not the date the source row was corrected.
            list(unique_subjects.values()), occurred_at=None,
        ))
    for battle in sorted(removed_battles, key=battle_identity):
        row_number, battle_key = battle.get("source_row"), battle_identity(battle)
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
            f"snapshot:{target_snapshot_id}:battle-removed:{battle_key}", "battle_record_removed",
            f"Battles!battle {battle_key}", {"source_row": row_number, "battle_key": battle_key, "source_battle_key": battle_key, "last_recorded": {field: battle.get(field) for field in BATTLE_FIELDS}},
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
