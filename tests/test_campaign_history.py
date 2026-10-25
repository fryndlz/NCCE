"""Deterministic checks for read-only Munda Manager history imports."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campaign_history import ARCHIVE_COLUMNS, _participants, build_timeline, parse_archive_tabs
from store import Store

G1 = "11111111-1111-4111-8111-111111111111"
G2 = "22222222-2222-4222-8222-222222222222"
G3 = "33333333-3333-4333-8333-333333333333"
B1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
B3 = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
S1 = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
S2 = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
F1 = "ffffffff-ffff-4fff-8fff-ffffffffffff"


def wrapped(source_table, record_id, record, archived_at="2026-10-26T15:00:00+00:00", version_hash=None):
    from campaign_history import _digest, _json
    return {
        "source_table": source_table, "record_id": record_id,
        "version_hash": version_hash or _digest(record), "payload_hash": _digest(record),
        "versioned": source_table != "gang_logs",
        "created_at_raw": record.get("created_at"), "created_at_utc": _utc(record.get("created_at")),
        "updated_at_raw": record.get("updated_at"), "updated_at_utc": _utc(record.get("updated_at")),
        "archived_at_raw": archived_at, "archived_at_utc": _utc(archived_at),
        "gang_id": record.get("gang_id"), "fighter_id": record.get("fighter_id"),
        "fighter_name_hint": record.get("fighter_name"), "campaign_id": record.get("campaign_id"),
        "action_type": record.get("action_type"), "description": record.get("description"),
        "status": record.get("status"), "scenario": record.get("scenario"),
        "participants": record.get("participants"),
        "participant_gang_ids": record.get("participant_gang_ids", []),
        "campaign_battle_id": record.get("campaign_battle_id"), "record": record,
        "raw_record_json": _json(record), "source_row": 2, "source_tab": "fixture",
        "source_row_json": _json(record), "errors": [],
    }


def _utc(value):
    if not value:
        return None
    from datetime import datetime, timezone
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


def make_records():
    battle1 = wrapped("campaign_battles", B1, {
        "created_at": "2026-10-25T09:00:00+00:00", "attacker_id": G1, "defender_id": G2,
        "scenario": "Takeover", "status": "played", "winner_id": G1,
        "participants": [{"gang_id": G1, "role": "attacker"}, {"gang_id": G2, "role": "defender"}],
    })
    battle2 = wrapped("campaign_battles", B2, {
        "created_at": "2026-10-25T12:30:00+00:00", "attacker_id": G1, "defender_id": G2,
        "scenario": "Border Dispute", "status": "played",
        "participants": [{"gang_id": G1}, {"gang_id": G2}],
    })
    battle_without_session = wrapped("campaign_battles", B3, {
        "created_at": "2026-10-25T16:00:00+00:00", "attacker_id": G1, "defender_id": G2,
        "scenario": "Ambush", "status": "played",
    })
    session1 = wrapped("battle_sessions", S1, {
        "created_at": "2026-10-25T10:00:00+00:00", "updated_at": "2026-10-25T11:00:00+00:00",
        "campaign_battle_id": B1, "status": "completed", "scenario": "Takeover",
    })
    session2 = wrapped("battle_sessions", S2, {
        "created_at": "2026-10-25T13:00:00+00:00", "updated_at": "2026-10-25T14:00:00+00:00",
        "campaign_battle_id": B2, "status": "completed", "scenario": "Border Dispute",
    })
    def activity(record_id, at, action, description, gang=G1, fighter=F1):
        return wrapped("gang_logs", record_id, {"created_at": at, "gang_id": gang,
            "fighter_id": fighter, "action_type": action, "description": description,
            "fighter_name": "Mara Kel"})
    events = [
        activity("pre", "2026-10-25T09:30:00+00:00", "fighter_xp_changed", 'Fighter "Mara Kel" XP changed from 2 to 3'),
        activity("xp", "2026-10-25T10:30:00+00:00", "fighter_xp_changed", 'Fighter "Mara Kel" XP changed from 2 to 3'),
        activity("spent", "2026-10-25T10:35:00+00:00", "fighter_xp_changed", 'Fighter "Mara Kel" XP changed from 3 to 1'),
        activity("between", "2026-10-25T12:00:00+00:00", "fighter_injured", 'Fighter "Mara Kel" injury changed'),
        activity("latest", "2026-10-25T15:00:00+00:00", "fighter_recovered", 'Fighter "Mara Kel" returned to active status'),
        activity("other", "2026-10-25T10:30:00+00:00", "fighter_xp_changed", 'Fighter "Rival" XP changed from 2 to 3', gang=G3, fighter="other"),
    ]
    return [battle1, battle2, battle_without_session, session1, session2, *events]


def test_archive_parser_preserves_source_and_handles_bad_rows():
    raw = {"id": "activity-1", "gang_id": G1, "fighter_id": F1,
           "created_at": "2026-10-25T10:30:00+02:00", "action_type": "fighter_xp_changed",
           "description": 'Fighter "Mara Kel" XP changed from 2 to 3',
           "participants": [{"gang_id": G1}]}
    row = ["gang_logs", "activity-1", "v1", raw["created_at"], None, G1, F1, None,
           raw["action_type"], raw["description"], None, None, json.dumps(raw["participants"]), None,
           json.dumps(raw), "2026-10-26T12:00:00+00:00"]
    sheets = {tab: [list(ARCHIVE_COLUMNS)] for tab in ("MUNDA_ACTIVITY_RAW", "MUNDA_BATTLES_RAW", "MUNDA_SESSIONS_RAW")}
    sheets["MUNDA_ACTIVITY_RAW"].extend([row, [None] * 16])
    parsed = parse_archive_tabs(sheets)
    item = parsed["records"][0]
    assert parsed["tab_counts"]["MUNDA_ACTIVITY_RAW"] == 1
    assert item["created_at_raw"] == raw["created_at"]
    assert item["created_at_utc"] == "2026-10-25T08:30:00+00:00"
    assert item["raw_record_json"] == json.dumps(raw)
    assert item["fighter_name_hint"] == "Mara Kel"
    assert item["participant_gang_ids"] == [G1]
    malformed = list(row); malformed[12] = "not json"; malformed[14] = "not json"
    sheets["MUNDA_ACTIVITY_RAW"].append(malformed)
    parsed_bad = parse_archive_tabs(sheets)
    assert any("invalid JSON" in error for error in parsed_bad["records"][-1]["errors"])
    _, only_gangs, _ = _participants({"gangs": [{"gang_id": G1, "fighter_ids": [F1]}]})
    assert only_gangs == [G1]


def test_timeline_joins_exactly_and_classifies_by_gang_window():
    records = make_records()
    timeline = build_timeline(records, {G1: "House One", G2: "House Two"}, now="2026-10-26T00:00:00+00:00")
    events = {event["event_id"]: event for event in timeline["events"]}
    battles = {battle["battle_id"]: battle for battle in timeline["battles"]}
    assert events["pre"]["phase"] == "pre_first_battle"
    assert events["xp"]["phase"] == "during_battle"
    assert events["xp"]["participation"]["status"] == "inferred"
    assert events["xp"]["participation"]["basis"] == "positive_xp_delta_in_battle_window"
    assert events["spent"]["participation"]["status"] == "not_supported"
    assert events["between"]["phase"] == "downtime"
    assert events["latest"]["phase"] == "current_downtime"
    assert events["other"]["phase"] == "unassigned"
    assert events["xp"]["confidence"] == "candidate_session_window"
    assert events["xp"]["evidence"]["not_confirmed_gameplay_boundary"] is True
    assert battles[B1]["timing_basis"] == "session_timestamp_proxy"
    assert battles[B1]["winner"] == "House One"
    assert battles[B3]["timing_basis"] == "unavailable"
    assert any(warning["kind"] == "battle_without_timing" and warning["record_id"] == B3 for warning in timeline["warnings"])


def test_session_join_is_exact_orphan_is_preserved_and_ally_xp_is_unknown():
    records = make_records()
    orphan = wrapped("battle_sessions", "orphan", {"created_at": "2026-10-25T10:00:00+00:00",
        "updated_at": "2026-10-25T11:00:00+00:00", "campaign_battle_id": "not-a-battle", "status": "played", "scenario": "Takeover"})
    ally_battle = wrapped("campaign_battles", "ally-battle", {"attacker_id": G1, "defender_id": G2,
        "participants": [{"gang_id": G1, "role": "ally"}, {"gang_id": G2}], "scenario": "Raid"})
    ally_session = wrapped("battle_sessions", "ally-session", {"created_at": "2026-10-25T17:00:00+00:00",
        "updated_at": "2026-10-25T18:00:00+00:00", "campaign_battle_id": "ally-battle", "status": "completed"})
    ally_xp = wrapped("gang_logs", "ally-xp", {"created_at": "2026-10-25T17:30:00+00:00", "gang_id": G1,
        "fighter_id": F1, "action_type": "fighter_xp_changed", "description": 'Fighter "Mara Kel" XP changed from 1 to 2'})
    timeline = build_timeline([*records, orphan, ally_battle, ally_session, ally_xp])
    events = {event["event_id"]: event for event in timeline["events"]}
    assert events["ally-xp"]["phase"] == "during_battle" or events["ally-xp"]["phase"] == "ambiguous_overlap"
    assert events["ally-xp"]["participation"]["status"] == "unknown"
    assert events["ally-xp"]["participation"]["basis"] == "ally_xp_excluded"
    assert any(warning["kind"] == "orphan_session" and warning["record_id"] == "orphan" for warning in timeline["warnings"])


def test_multiple_sessions_keep_gaps_unresolved_and_overlaps_ambiguous():
    records = make_records()
    second_session = wrapped("battle_sessions", "second-session", {
        "created_at": "2026-10-25T11:30:00+00:00", "updated_at": "2026-10-25T12:00:00+00:00",
        "campaign_battle_id": B1, "status": "completed",
    })
    overlapping_battle = wrapped("campaign_battles", "overlap-battle", {
        "attacker_id": G1, "defender_id": G3, "participants": [{"gang_id": G1}, {"gang_id": G3}],
        "scenario": "Ambush",
    })
    overlapping_session = wrapped("battle_sessions", "overlap-session", {
        "created_at": "2026-10-25T10:20:00+00:00", "updated_at": "2026-10-25T10:40:00+00:00",
        "campaign_battle_id": "overlap-battle", "status": "completed",
    })
    gap_event = wrapped("gang_logs", "session-gap", {"created_at": "2026-10-25T11:15:00+00:00",
        "gang_id": G1, "fighter_id": F1, "action_type": "fighter_injured", "description": "Recorded injury"})
    overlap_event = wrapped("gang_logs", "overlap-event", {"created_at": "2026-10-25T10:30:00+00:00",
        "gang_id": G1, "fighter_id": F1, "action_type": "fighter_injured", "description": "Recorded injury"})
    timeline = build_timeline([*records, second_session, overlapping_battle, overlapping_session,
                               gap_event, overlap_event])
    events = {event["event_id"]: event for event in timeline["events"]}
    assert events["session-gap"]["phase"] == "inter_session_gap"
    assert events["session-gap"]["battle_id"] == B1
    assert events["overlap-event"]["phase"] == "ambiguous_overlap"
    assert any(warning["kind"] == "overlapping_gang_battles" for warning in timeline["warnings"])


def test_cancelled_session_does_not_create_a_battle_window():
    battle = wrapped("campaign_battles", "cancelled-battle", {"attacker_id": G1, "defender_id": G2,
        "participants": [{"gang_id": G1}, {"gang_id": G2}], "scenario": "Cancelled"})
    session = wrapped("battle_sessions", "cancelled-session", {"created_at": "2026-10-25T10:00:00+00:00",
        "updated_at": "2026-10-25T11:00:00+00:00", "campaign_battle_id": "cancelled-battle", "status": "cancelled"})
    event = wrapped("gang_logs", "after-cancel", {"created_at": "2026-10-25T10:30:00+00:00",
        "gang_id": G1, "fighter_id": F1, "action_type": "fighter_injured", "description": "Injury logged"})
    timeline = build_timeline([battle, session, event])
    assert timeline["battles"][0]["timing_basis"] == "unavailable"
    assert timeline["events"][0]["phase"] == "unassigned"
    assert any(warning["kind"] == "incomplete_session_window" for warning in timeline["warnings"])


def test_archive_import_is_idempotent_versioned_and_flags_same_version_conflicts():
    records = make_records()
    battle = next(item for item in records if item["record_id"] == B1)
    newer_record = dict(battle["record"], note="corrected note", updated_at="2026-10-25T12:00:00+00:00")
    from campaign_history import _digest, _json
    newer = wrapped("campaign_battles", B1, newer_record, archived_at="2026-10-26T16:00:00+00:00", version_hash="v2")
    version_conflict = dict(battle, payload_hash="different", record={**battle["record"], "note": "conflict"},
                            raw_record_json=_json({**battle["record"], "note": "conflict"}), version_hash=battle["version_hash"])
    version_conflict["payload_hash"] = _digest(version_conflict["record"])
    bundle = {"records": [*records, newer], "missing_tabs": [], "tab_counts": {}, "row_errors": []}
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as directory:
        store = Store(Path(directory) / "history.db")
        try:
            first = store.import_history_archives(bundle, "2026-10-26T17:00:00+00:00")
            again = store.import_history_archives(bundle, "2026-10-26T17:01:00+00:00")
            assert first["inserted"] == len(bundle["records"])
            assert again["inserted"] == 0
            assert store.db.execute("SELECT count(*) FROM campaign_archive_records WHERE source_table='campaign_battles' AND record_id=?", (B1,)).fetchone()[0] == 2
            conflict_bundle = {**bundle, "records": [version_conflict]}
            conflict_result = store.import_history_archives(conflict_bundle, "2026-10-26T17:02:00+00:00")
            assert conflict_result["conflicts"] == 1
            timeline = store.history_timeline()
            battle_versions = [battle for battle in timeline["battles"] if battle["battle_id"] == B1]
            assert len(battle_versions) == 1
            assert battle_versions[0]["source_version_hash"] == "v2"
            assert timeline["stats"]["conflicts"] == 1
        finally:
            store.close()


if __name__ == "__main__":
    test_archive_parser_preserves_source_and_handles_bad_rows()
    test_timeline_joins_exactly_and_classifies_by_gang_window()
    test_session_join_is_exact_orphan_is_preserved_and_ally_xp_is_unknown()
    test_multiple_sessions_keep_gaps_unresolved_and_overlaps_ambiguous()
    test_cancelled_session_does_not_create_a_battle_window()
    test_archive_import_is_idempotent_versioned_and_flags_same_version_conflicts()
    print("ok (6 campaign history checks)")
