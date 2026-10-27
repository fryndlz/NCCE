"""Read-only import and chronology rules for Munda Manager archive tabs.

Archive rows are evidence from Munda Manager. Session timestamps define the
operational battle window; activity timestamps are record timestamps and are
classified against those windows without claiming individual attendance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


ARCHIVE_TABS = {
    "MUNDA_ACTIVITY_RAW": "gang_logs",
    "MUNDA_BATTLES_RAW": "campaign_battles",
    "MUNDA_SESSIONS_RAW": "battle_sessions",
}

ARCHIVE_COLUMNS = (
    "Source Table", "Record ID", "Version Hash", "Created At", "Updated At",
    "Gang ID", "Fighter ID", "Campaign ID", "Action Type", "Description",
    "Status", "Scenario", "Participants JSON", "Campaign Battle ID", "Raw JSON", "Archived At",
)

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_FIGHTER_IN_DESCRIPTION = re.compile(r'\bfighter\s+["\']([^"\']+)["\']', re.I)
_XP_DELTA = re.compile(r"\bXP\s+(?:changed|increased|decreased)\s+from\s+(-?\d+)\s+to\s+(-?\d+)\b", re.I)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_instant(value: Any) -> tuple[str | None, str | None, str | None]:
    """Return original text, UTC instant, and parse warning; never guess a zone."""
    original = _text(value)
    if not original:
        return None, None, None
    try:
        parsed = datetime.fromisoformat(original.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return original, None, "invalid timestamp"
    if parsed.tzinfo is None:
        return original, None, "timestamp has no timezone offset"
    return original, parsed.astimezone(timezone.utc).isoformat(), None


def _parse_json_value(value: Any) -> tuple[Any, str | None]:
    if value is None or value == "":
        return None, None
    if isinstance(value, (list, dict)):
        return value, None
    if not isinstance(value, str):
        return value, None
    try:
        return json.loads(value), None
    except (TypeError, json.JSONDecodeError):
        return None, "invalid JSON"


def _nested(record: dict, key: str) -> Any:
    value = record.get(key)
    if value not in (None, ""):
        return value
    return None


def _participants(value: Any) -> tuple[Any, list[str], str | None]:
    parsed, warning = _parse_json_value(value)
    gang_ids: set[str] = set()

    def visit(item, participant_context=False):
        if isinstance(item, dict):
            for key, nested in item.items():
                if _UUID.match(str(key).strip()) and isinstance(nested, dict):
                    gang_ids.add(str(key).strip())
            for key in ("gang_id", "gangId", "gangID", "attacker_id", "defender_id", "challenger_gang_id", "challenged_gang_id"):
                candidate = item.get(key)
                if candidate not in (None, ""):
                    gang_ids.add(str(candidate))
            if participant_context and item.get("id") is not None and any(key in item for key in ("role", "type", "gang_name", "gangName")):
                gang_ids.add(str(item["id"]))
            containers = {"participants", "gangs", "gang", "attacker", "defender", "challenger", "challenged", "attackers", "defenders", "gang_ids", "gangIds"}
            for key, nested in item.items():
                if key in containers and isinstance(nested, (dict, list)):
                    visit(nested, True)
        elif isinstance(item, list):
            if participant_context and item and all(isinstance(nested, str) and _UUID.match(nested.strip()) for nested in item):
                gang_ids.update(nested.strip() for nested in item)
            else:
                for nested in item:
                    if isinstance(nested, dict):
                        visit(nested, True)

    visit(parsed, True)
    return parsed, sorted(gang_ids), warning


def _normalize_row(tab: str, source_row: int, header: list[Any], values: list[Any]) -> dict | None:
    if not values or not any(value not in (None, "") for value in values):
        return None
    row = {str(header[index]).strip(): values[index] if index < len(values) else None
           for index in range(len(header)) if header[index] not in (None, "")}
    raw_cell = row.get("Raw JSON")
    raw_record, raw_error = _parse_json_value(raw_cell)
    if not isinstance(raw_record, dict):
        raw_record = {}
        if raw_cell not in (None, "") and raw_error is None:
            raw_error = "raw record is not an object"

    source_table = _text(row.get("Source Table")) or ARCHIVE_TABS[tab]
    record_id = _text(row.get("Record ID")) or _text(raw_record.get("id"))
    if not record_id:
        return {"tab": tab, "source_row": source_row, "row": row,
                "errors": ["missing record ID"]}

    def field(projected, raw_name=None):
        value = _nested(raw_record, raw_name or projected)
        return value if value is not None else row.get(projected)

    created_raw, created_utc, created_error = parse_instant(field("Created At", "created_at"))
    updated_raw, updated_utc, updated_error = parse_instant(field("Updated At", "updated_at"))
    archived_raw, archived_utc, archived_error = parse_instant(row.get("Archived At"))
    participants_value = field("Participants JSON", "participants")
    participants, participant_gangs, participant_error = _participants(participants_value)
    source_row_json = _json(row)
    raw_record_json = raw_cell if isinstance(raw_cell, str) else _json(raw_record)
    content = dict(raw_record) if raw_record else {key: value for key, value in row.items() if key != "Archived At"}
    payload_hash = _digest(content)
    version_hash = _text(row.get("Version Hash"))
    versioned = source_table in {"campaign_battles", "battle_sessions"}
    if versioned and not version_hash:
        version_hash = payload_hash
    if not versioned:
        version_hash = "append-only"

    gang_id = _text(field("Gang ID", "gang_id"))
    fighter_id = _text(field("Fighter ID", "fighter_id"))
    description = _text(field("Description", "description"))
    fighter_name = None
    if description:
        match = _FIGHTER_IN_DESCRIPTION.search(description)
        if match:
            fighter_name = match.group(1).strip()
    for key in ("fighter_name", "fighterName", "name"):
        if raw_record.get(key) and fighter_id:
            fighter_name = str(raw_record[key]).strip()
            break

    errors = [error for error in (raw_error, created_error, updated_error, archived_error, participant_error) if error]
    return {
        "source_table": source_table,
        "record_id": record_id,
        "version_hash": version_hash,
        "payload_hash": payload_hash,
        "versioned": versioned,
        "created_at_raw": created_raw,
        "created_at_utc": created_utc,
        "updated_at_raw": updated_raw,
        "updated_at_utc": updated_utc,
        "archived_at_raw": archived_raw,
        "archived_at_utc": archived_utc,
        "gang_id": gang_id,
        "fighter_id": fighter_id,
        "fighter_name_hint": fighter_name,
        "campaign_id": _text(field("Campaign ID", "campaign_id")),
        "action_type": _text(field("Action Type", "action_type")),
        "description": description,
        "status": _text(field("Status", "status")),
        "scenario": _text(field("Scenario", "scenario")),
        "participants": participants,
        "participant_gang_ids": participant_gangs,
        "campaign_battle_id": _text(field("Campaign Battle ID", "campaign_battle_id")),
        "record": raw_record,
        "raw_record_json": raw_record_json,
        "source_row": source_row,
        "source_tab": tab,
        "source_row_json": source_row_json,
        "errors": errors,
    }


def parse_archive_tabs(sheets: dict[str, list[list[Any]]]) -> dict:
    """Normalize the three raw archive tabs; ignore blank/trailing rows."""
    records: list[dict] = []
    row_errors: list[dict] = []
    missing_tabs = []
    tab_counts = {}
    for tab, source_name in ARCHIVE_TABS.items():
        rows = sheets.get(tab)
        if not rows:
            missing_tabs.append(tab)
            tab_counts[tab] = 0
            continue
        header = [str(value).strip() if value is not None else "" for value in rows[0]]
        missing_headers = [column for column in ARCHIVE_COLUMNS if column not in header]
        if missing_headers:
            row_errors.append({"tab": tab, "source_row": 1,
                               "errors": ["missing expected columns: " + ", ".join(missing_headers)]})
        count = 0
        for source_row, values in enumerate(rows[1:], start=2):
            item = _normalize_row(tab, source_row, header, values)
            if not item:
                continue
            if "source_table" not in item:
                row_errors.append(item)
                continue
            if item["source_table"] != source_name:
                item["errors"].append(f"source table is {item['source_table']}, expected {source_name}")
            records.append(item)
            count += 1
            if item["errors"]:
                row_errors.append({"tab": tab, "source_row": source_row, "record_id": item["record_id"], "errors": item["errors"]})
        tab_counts[tab] = count
    return {"records": records, "missing_tabs": missing_tabs, "tab_counts": tab_counts,
            "row_errors": row_errors}


def latest_versions(records: list[dict], source_table: str) -> list[dict]:
    """Choose the version with the latest valid archive observation per source ID."""
    grouped: dict[str, list[dict]] = {}
    for record in records:
        if record.get("source_table") == source_table:
            grouped.setdefault(record["record_id"], []).append(record)
    selected = []
    for record_id, versions in grouped.items():
        versions.sort(key=lambda item: (
            item.get("archived_at_utc") is not None,
            item.get("archived_at_utc") or "",
            item.get("version_hash") or "",
        ))
        selected.append(versions[-1])
    return sorted(selected, key=lambda item: (item.get("created_at_utc") or "", item["record_id"]))


def _gang_ids(battle: dict) -> list[str]:
    result = set(battle.get("participant_gang_ids") or [])
    for key in ("attacker_id", "defender_id", "challenger_gang_id", "challenged_gang_id"):
        value = battle.get("record", {}).get(key)
        if value not in (None, ""):
            result.add(str(value))
    return sorted(result)


def _terminal_session(status: Any) -> bool:
    value = re.sub(r"[^a-z]+", "_", str(status or "").casefold()).strip("_")
    if value in {"pre_battle", "in_progress", "in_progress_battle", "scheduled", "draft", "active", "open", "started", "running", "ongoing", "cancelled", "canceled", "abandoned", "void"}:
        return False
    return True


def _participant_entry(participants: Any, gang_id: str) -> dict | None:
    parsed, _ = _parse_json_value(participants)
    containers = {"participants", "gangs", "gang", "attacker", "defender", "challenger", "challenged", "attackers", "defenders"}
    def find(item):
        if isinstance(item, list):
            for nested in item:
                result = find(nested)
                if result:
                    return result
        elif isinstance(item, dict):
            for key, nested in item.items():
                if str(key) == str(gang_id) and isinstance(nested, dict):
                    return {"gang_id": key, **nested}
            candidate = next((item.get(key) for key in ("gang_id", "gangId", "gangID") if item.get(key) is not None), None)
            if candidate is None and item.get("id") is not None and any(key in item for key in ("role", "type", "gang_name", "gangName")):
                candidate = item.get("id")
            if str(candidate or "") == str(gang_id):
                return item
            for key, nested in item.items():
                if key in containers and isinstance(nested, (dict, list)):
                    result = find(nested)
                    if result:
                        return result
        return None
    return find(parsed)


def _is_ally(participant: dict) -> bool:
    role = " ".join(str(participant.get(key) or "") for key in ("role", "type", "status")).casefold()
    explicit = participant.get("is_ally", participant.get("isAlly"))
    flagged = explicit is True or (isinstance(explicit, str) and explicit.strip().casefold() in {"true", "yes", "1"})
    return flagged or "ally" in role or "allied" in role


def _xp_participation(activity: dict, gang_id: str | None, battle: dict | None) -> dict:
    """Infer participation only from a positive XP change in an involved gang."""
    if not battle or not gang_id or str(gang_id) not in set(battle.get("gang_ids", [])):
        return {"status": "unknown", "basis": None, "confidence": "unavailable"}
    action = str(activity.get("action_type") or "").casefold()
    match = _XP_DELTA.search(str(activity.get("description") or ""))
    if "xp" not in action or not match:
        return {"status": "unknown", "basis": None, "confidence": "unavailable"}
    before, after = int(match.group(1)), int(match.group(2))
    if after <= before:
        return {"status": "not_supported", "basis": "non_positive_xp_delta", "confidence": "recorded",
                "xp_before": before, "xp_after": after}
    participant = _participant_entry(battle.get("participants"), str(gang_id))
    if participant and _is_ally(participant):
        return {"status": "unknown", "basis": "ally_xp_excluded", "confidence": "unavailable"}
    explicit = bool(re.search(r"\b(participat(?:ed|ion)|took part|battle xp|game xp)\b", str(activity.get("description") or ""), re.I))
    return {"status": "inferred", "basis": "explicit_xp_reason" if explicit else "positive_xp_delta_in_battle_window",
            "confidence": "strong_inference" if explicit else "inference", "xp_before": before, "xp_after": after}


def window_playtime(windows):
    """Union complete session intervals; breaks and overlaps are not double-counted."""
    intervals = sorted((datetime.fromisoformat(w['start_at']), datetime.fromisoformat(w['end_at']))
                       for w in windows if w.get('start_at') and w.get('end_at') and w['end_at'] >= w['start_at'])
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return int(sum((end-start).total_seconds() for start, end in merged)) if intervals else None


def build_timeline(records: list[dict], gang_names: dict[str, str] | None = None,
                   fighter_names: dict[tuple[str, str], str] | None = None,
                   territories: dict[str, str] | None = None, now: str | None = None) -> dict:
    """Join records and classify activity against a separate sequence per gang."""
    gang_names = gang_names or {}
    fighter_names = fighter_names or {}
    territories = territories or {}
    now_raw, now_utc, _ = parse_instant(now or datetime.now(timezone.utc).isoformat())
    all_battles = latest_versions(records, "campaign_battles")
    sessions = latest_versions(records, "battle_sessions")
    activities = sorted((record for record in records if record.get("source_table") == "gang_logs"),
                        key=lambda item: (item.get("created_at_utc") or "", item["record_id"]))

    battle_by_id = {item["record_id"]: item for item in all_battles}
    sessions_by_battle: dict[str, list[dict]] = {}
    orphan_sessions = []
    for session in sessions:
        battle_id = session.get("campaign_battle_id") or session.get("record", {}).get("campaign_battle_id")
        if battle_id and battle_id in battle_by_id:
            sessions_by_battle.setdefault(str(battle_id), []).append(session)
        else:
            orphan_sessions.append(session)

    battle_items = []
    build_warnings = []
    windows_by_gang: dict[str, list[dict]] = {}
    for battle in all_battles:
        battle_id = battle["record_id"]
        battle_record = battle.get("record") or {}
        participant_ids = _gang_ids(battle)
        linked = sessions_by_battle.get(battle_id, [])
        windows = []
        for session in linked:
            status = session.get("status") or session.get("record", {}).get("status")
            normalized_status = re.sub(r"[^a-z]+", "_", str(status or "").casefold()).strip("_")
            canceled = normalized_status in {"cancelled", "canceled", "abandoned", "void"}
            start = None if canceled else session.get("created_at_utc")
            end = session.get("updated_at_utc") if not canceled and _terminal_session(status) else None
            if start and end and end < start:
                end = None
                status_warning = "session end precedes its start"
            elif canceled:
                status_warning = "session was cancelled or abandoned; no candidate battle window is inferred"
            elif not start or not end:
                status_warning = "session does not provide a complete timed window"
            else:
                status_warning = None
            windows.append({"session_id": session["record_id"], "start_at": start,
                            "end_at": end, "start_raw": session.get("created_at_raw"),
                            "end_raw": session.get("updated_at_raw"), "status": status,
                            "scenario": session.get("scenario") or battle.get("scenario"),
                            "warning": status_warning, "source_row": session.get("source_row"),
                            "archived_at": session.get("archived_at_raw")})

        starts = [window["start_at"] for window in windows if window.get("start_at")]
        valid = [window for window in windows if window.get("start_at") and window.get("end_at")]
        if starts and len(valid) == len(windows):
            start_at = min(starts)
            end_at = max(window["end_at"] for window in valid)
            timing = "session_timestamp_proxy"
            warnings = ["multiple linked sessions combined into one battle span"] if len(valid) > 1 else []
        elif starts:
            start_at = min(starts)
            end_at = None
            timing = "incomplete_session"
            warnings = ["one or more linked sessions do not provide a complete timed window"]
        else:
            start_at = end_at = None
            timing = "unavailable"
            warnings = ["no complete linked session window"]
        territory_id = battle_record.get("territory_id") or battle_record.get("campaign_territory_id")
        item = {
            "battle_id": battle_id,
            "source_table": "campaign_battles",
            "source_version_hash": battle.get("version_hash"),
            "documented_at": battle.get("created_at_utc"),
            "documented_at_raw": battle.get("created_at_raw"),
            "start_at": start_at, "end_at": end_at, "timing_basis": timing,
            "timing_warnings": warnings,
            "sessions": windows,
            "playtime_seconds": window_playtime(windows),
            "gang_ids": participant_ids,
            "gangs": [{"gang_id": gang_id, "name": gang_names.get(gang_id, "Gang " + gang_id[:8])} for gang_id in participant_ids],
            "attacker": gang_names.get(str(battle_record.get("attacker_id") or battle_record.get("challenger_gang_id") or "")),
            "defender": gang_names.get(str(battle_record.get("defender_id") or battle_record.get("challenged_gang_id") or "")),
            "scenario": battle.get("scenario") or battle_record.get("scenario"),
            "status": battle.get("status") or battle_record.get("status"),
            "attacker_gang_id": battle_record.get("attacker_id") or battle_record.get("challenger_gang_id"),
            "defender_gang_id": battle_record.get("defender_id") or battle_record.get("challenged_gang_id"),
            "winner_gang_id": battle_record.get("winner_id") or battle_record.get("winner_gang_id"),
            "winner": gang_names.get(str(battle_record.get("winner_id") or battle_record.get("winner_gang_id") or "")),
            "cycle": battle_record.get("cycle"),
            "territory_id": str(territory_id) if territory_id else None,
            "territory": territories.get(str(territory_id)) if territory_id else None,
            "participants": battle.get("participants"),
            "source_row": battle.get("source_row"),
            "raw_record": battle.get("record"),
            "recorded_note": battle_record.get("note"),
        }
        battle_items.append(item)
        for gang_id in participant_ids:
            for session in windows:
                if session.get("start_at"):
                    windows_by_gang.setdefault(gang_id, []).append({**item, **session, "gang_id": gang_id,
                                                                     "session_id": session["session_id"]})
        if len(windows) > 1:
            build_warnings.append({"kind": "multiple_sessions_combined", "record_id": battle_id,
                             "session_ids": [window["session_id"] for window in windows],
                             "message": "linked session windows are shown as one battle span"})

    for gang_id in windows_by_gang:
        windows_by_gang[gang_id].sort(key=lambda item: (item["start_at"], item.get("end_at") or "", item["battle_id"]))

    events = []
    for activity in activities:
        record = activity.get("record") or {}
        gang_id = activity.get("gang_id") or record.get("gang_id")
        fighter_id = activity.get("fighter_id") or record.get("fighter_id")
        event_at = activity.get("created_at_utc")
        candidates = windows_by_gang.get(str(gang_id), []) if gang_id else []
        matches = [window for window in candidates if window.get("end_at") and event_at and window["start_at"] <= event_at <= window["end_at"]]
        open_matches = [window for window in candidates if not window.get("end_at") and event_at and window["start_at"] <= event_at]
        next_battle = None
        preceding = None
        phase = "unavailable" if not event_at else "pre_first_battle"
        confidence = "unavailable" if not event_at else "recorded_time"
        battle_id = None
        if event_at and open_matches and (matches or len(open_matches) > 1):
            phase = "ambiguous_overlap"
            confidence = "overlapping_or_incomplete_windows"
        elif event_at and open_matches:
            phase = "open_battle_window"
            confidence = "incomplete_session"
            battle_id = open_matches[0]["battle_id"]
        elif event_at and len(matches) == 1:
            phase = "during_battle"
            confidence = "session_timestamps"
            battle_id = matches[0]["battle_id"]
        elif event_at and len(matches) > 1:
            phase = "ambiguous_overlap"
            confidence = "overlapping_windows"
            battle_id = None
        elif event_at and candidates:
            prior = [window for window in candidates if window.get("end_at") and window["end_at"] < event_at]
            upcoming = [window for window in candidates if window["start_at"] > event_at]
            if upcoming:
                next_battle = min(upcoming, key=lambda item: item["start_at"])
                if prior:
                    preceding = max(prior, key=lambda item: item["end_at"])
                    if preceding["battle_id"] == next_battle["battle_id"]:
                        phase = "inter_session_gap"
                        confidence = "same_battle_multiple_sessions"
                        battle_id = preceding["battle_id"]
                    elif event_at > preceding["end_at"]:
                        phase = "downtime"
                        confidence = "candidate_session_window"
                else:
                    phase = "pre_first_battle"
                    confidence = "candidate_session_window"
            elif prior:
                preceding = max(prior, key=lambda item: item["end_at"])
                phase = "current_downtime"
                confidence = "candidate_session_window"
            else:
                # An event after a started but unfinished window cannot safely be
                # called downtime, because the session has no confirmed end yet.
                open_windows = [window for window in candidates if not window.get("end_at") and window["start_at"] <= event_at]
                if open_windows:
                    phase = "open_battle_window"
                    confidence = "incomplete_session"
                elif any(window["start_at"] > event_at for window in candidates):
                    phase = "pre_first_battle"
                    confidence = "candidate_session_window"
        elif event_at and not candidates:
            phase = "unassigned"
            confidence = "no_timed_battle_for_gang"

        action_type = activity.get("action_type") or record.get("action_type")
        matched_battle = next((window for window in candidates if window.get("battle_id") == battle_id), None)
        participation = _xp_participation({**activity, "action_type": action_type,
                                           "description": activity.get("description") or record.get("description")},
                                          str(gang_id) if gang_id else None, matched_battle)
        territory_id = record.get("territory_id") or record.get("campaign_territory_id")
        event = {
            "event_id": activity["record_id"],
            "source_table": activity["source_table"],
            "source_tab": activity.get("source_tab"),
            "source_row": activity.get("source_row"),
            "source_version_hash": activity.get("version_hash"),
            "recorded_at": activity.get("created_at_utc"),
            "recorded_at_raw": activity.get("created_at_raw"),
            "archived_at": activity.get("archived_at_raw"),
            "gang_id": str(gang_id) if gang_id else None,
            "gang_name": gang_names.get(str(gang_id)) if gang_id else None,
            "fighter_id": str(fighter_id) if fighter_id else None,
            "fighter_name": fighter_names.get((str(gang_id or ""), str(fighter_id or ""))) or activity.get("fighter_name_hint"),
            "entity_label": (fighter_names.get((str(gang_id or ""), str(fighter_id or ""))) or activity.get("fighter_name_hint") or ("Fighter " + str(fighter_id)[:8])) if fighter_id else gang_names.get(str(gang_id)) if gang_id else "Campaign",
            "action_type": action_type,
            "territory_id": str(territory_id) if territory_id else None,
            "place_name": territories.get(str(territory_id)) if territory_id else None,
            "description": activity.get("description") or record.get("description"),
            "status": activity.get("status"),
            "phase": phase,
            "confidence": "candidate_session_window" if confidence == "session_timestamps" else confidence,
            "participation": participation,
            "battle_id": battle_id,
            "preceding_battle_id": preceding.get("battle_id") if preceding else None,
            "next_battle_id": next_battle.get("battle_id") if next_battle else None,
            "evidence": {"timestamp": activity.get("created_at_raw"), "basis": "gang_logs.created_at", "session_window_rule": "candidate proxy: session.created_at through session.updated_at", "not_confirmed_gameplay_boundary": True},
            "raw_record": record,
            "parse_errors": activity.get("errors", []),
        }
        events.append(event)

    warnings = build_warnings
    for session in orphan_sessions:
        warnings.append({"kind": "orphan_session", "record_id": session["record_id"],
                         "status": session.get("status"), "created_at": session.get("created_at_raw"),
                         "campaign_battle_id": session.get("campaign_battle_id"),
                         "source_row": session.get("source_row")})
    for battle in battle_items:
        if battle["timing_basis"] == "unavailable":
            warnings.append({"kind": "battle_without_timing", "record_id": battle["battle_id"],
                             "documented_at": battle["documented_at_raw"], "source_row": battle.get("source_row")})
        for session in battle["sessions"]:
            if session.get("warning"):
                warnings.append({"kind": "incomplete_session_window", "record_id": session["session_id"],
                                 "battle_id": battle["battle_id"], "message": session["warning"]})
    for gang_id, windows in windows_by_gang.items():
        for index, left in enumerate(windows):
            for right in windows[index + 1:]:
                if left.get("end_at") and right.get("start_at") and right["start_at"] >= left["end_at"]:
                    break
                if not left.get("end_at") or not right.get("start_at") or right["start_at"] >= left["end_at"]:
                    continue
                if left.get("battle_id") != right.get("battle_id"):
                    warnings.append({"kind": "overlapping_gang_battles", "gang_id": gang_id,
                                     "first_battle_id": left["battle_id"], "second_battle_id": right["battle_id"]})
                else:
                    warnings.append({"kind": "overlapping_battle_sessions", "gang_id": gang_id,
                                     "battle_id": left["battle_id"], "first_session_id": left.get("session_id"),
                                     "second_session_id": right.get("session_id")})

    events.sort(key=lambda item: (item.get("recorded_at") or "", item["event_id"]))
    return {"battles": sorted(battle_items, key=lambda item: (item.get("start_at") or item.get("documented_at") or "", item["battle_id"])),
            "events": events, "warnings": warnings,
            "stats": {"activity_records": len(activities), "battle_records": len(all_battles),
                      "session_records": len(sessions), "orphan_sessions": len(orphan_sessions),
                      "timed_battles": sum(1 for item in battle_items if item["start_at"] and item["end_at"]),
                      "classified_during_battle": sum(1 for item in events if item["phase"] == "during_battle"),
                      "classified_downtime": sum(1 for item in events if item["phase"] in {"downtime", "current_downtime"})}}
