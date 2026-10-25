"""Regression checks for encounter identity when the Battles tab is reordered."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diff import snapshot_event_drafts
from snapshot import battle_identity, battle_records, build_snapshot_from_sheets


def battle(row, date="2026-10-20", scenario="The Trap", attacker="The Slag Eaters", defender="Kły Sprawiedliwości", winner="The Slag Eaters", territory="Settlement", notes=None, **extra):
    return dict(source_row=row, date=date, scenario=scenario, attacker=attacker, defender=defender, winner=winner, territory=territory, territory_claimer=winner, notes=notes, **extra)


def snapshot(rows):
    return {"snapshot_version": 1, "captured_at": "2026-10-25T12:00:00Z", "gangs": {}, "territories": [], "battles": rows}


def test_inserting_newest_battle_does_not_correct_shifted_history():
    older = battle(3, date="2026-10-17", scenario="Asset Seizure", attacker="Ethernetans 2.0", winner="Ethernetans 2.0", territory="Drinking Hole")
    before = [battle(2), older]
    latest = battle(2, date="2026-10-25", scenario="Takeover", attacker="Kły Sprawiedliwości", defender="C-NINE", winner="C-NINE", territory="Promethium Cache")
    after = [latest, dict(before[0], source_row=3), dict(older, source_row=4)]
    events = snapshot_event_drafts(snapshot(before), snapshot(after), 2)
    assert [event["event_type"] for event in events] == ["battle_result"]
    assert events[0]["payload"]["winner"] == "C-NINE"
    assert events[0]["payload"]["source_row"] == 2
    assert events[0]["source_locator"].startswith("Battles!battle ")
    reordered = [dict(after[2], source_row=2), dict(latest, source_row=3), dict(after[1], source_row=4)]
    assert not snapshot_event_drafts(snapshot(after), snapshot(reordered), 3)


def test_winner_and_notes_correction_retains_encounter():
    before = battle(2)
    after = dict(before, source_row=7, winner="Kły Sprawiedliwości", notes="A supplied account.")
    events = snapshot_event_drafts(snapshot([before]), snapshot([after]), 2)
    assert len(events) == 1 and events[0]["event_type"] == "battle_record_corrected"
    assert set(events[0]["payload"]["changes"]) == {"winner", "notes"}
    assert events[0]["payload"]["previous_source_row"] == 2
    assert events[0]["payload"]["source_row"] == 7
    assert events[0]["occurred_at"] is None
    assert battle_identity(before) == battle_identity(after)


def test_legacy_fallback_can_gain_source_id_without_replaying_battle():
    before = battle(2)
    enriched = dict(before, source_row=5, source_battle_id="source-log-1")
    assert not snapshot_event_drafts(snapshot([before]), snapshot([enriched]), 2)
    corrected = dict(enriched, winner="Kły Sprawiedliwości")
    events = snapshot_event_drafts(snapshot([before]), snapshot([corrected]), 3)
    assert len(events) == 1 and events[0]["event_type"] == "battle_record_corrected"
    assert events[0]["payload"]["battle_key"] == "id:source-log-1"


def test_duplicate_fallback_encounters_are_not_collapsed_or_misattributed():
    first = battle(2)
    second = battle(3, winner="Kły Sprawiedliwości", territory="Old Ruins")
    records = battle_records([first, second])
    assert len({record["battle_key"] for record in records}) == 2
    swapped = [dict(second, source_row=2), dict(first, source_row=3)]
    assert not snapshot_event_drafts(snapshot([first, second]), snapshot(swapped), 2)
    identical = battle_records([first, dict(first, source_row=3)])
    assert len({record["battle_key"] for record in identical}) == 2
    # Removing one duplicate is one removal, not the loss of the whole group.
    events = snapshot_event_drafts(snapshot([first, second]), snapshot([dict(first, source_row=2)]), 3)
    assert [event["event_type"] for event in events] == ["battle_record_removed"]
    assert events[0]["payload"]["last_recorded"]["territory"] == "Old Ruins"


def test_distinct_source_ids_never_merge_even_when_content_is_identical():
    before = battle(2, source_battle_id="one")
    after = dict(before, source_battle_id="two")
    events = snapshot_event_drafts(snapshot([before]), snapshot([after]), 2)
    assert {event["event_type"] for event in events} == {"battle_record_removed", "battle_result"}


def test_raw_dump_source_id_join_is_unique_and_keeps_visible_fields():
    row = ["2026-10-25", "Takeover", "Kły Sprawiedliwości", "C-NINE", "C-NINE", "Promethium Cache", "C-NINE", "Sheet note"]
    log = dict(id="source-log-25", created_at="2026-10-24T22:00:00Z", scenario_name="Takeover", attacker={"name": "Kły Sprawiedliwości"}, defender={"name": "C-NINE"}, territory_name="Promethium Cache", note="Raw note")
    sheets = {"Campaign": [], "Gangs": [], "Territories": [], "Battles": [["Date", "Scenario", "Attacker", "Defender", "Winner", "Territory", "Territory Claimer", "Notes"], row], "MAIN": [["Data Dump", json.dumps({"battle_logs": [log]})]]}
    result = build_snapshot_from_sheets(sheets)
    assert result["battles"][0]["battle_key"] == "id:source-log-25"
    assert result["battles"][0]["notes"] == "Sheet note"
    assert result["source_metadata"]["battle_ids_available"] == 1
    # Two indistinguishable raw records supply no reliable identity to join.
    sheets["MAIN"] = [["Data Dump", json.dumps({"battle_logs": [log, dict(log, id="another-source-log")]})]]
    result = build_snapshot_from_sheets(sheets)
    assert "source_battle_id" not in result["battles"][0]


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"ok ({len(tests)} battle identity checks)")
