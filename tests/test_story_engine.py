"""Story-loop regressions using disposable SQLite and synthetic Sheet snapshots."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from store import Store
from sync import ingest_snapshot
from story_engine import document_for, read_memories, regenerate, select_mind

C9 = "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]"
KLY = "Kły Sprawiedliwości"
AT = "2026-10-25T12:00:00+00:00"


def campaign():
    return {
        "snapshot_version": 1, "captured_at": "2026-10-24T18:00:00+00:00",
        "gangs": {
            C9: {"gang_id": "g1", "name": C9, "gang_type": "Genestealer Cults", "credits": 60, "reputation": 9, "rating": 900,
                 "fighters": {
                     "Mara Kel": {"Name": "Mara Kel", "Type": "Neophyte Hybrids", "Class": "Ganger", "XP": 4, "Kills": 2, "Advancements": "Willpower", "Effects": None, "Status": "Active", "Weapons": "Lasgun", "Wargear": "Hazard suit", "Skills": None, "S": 3, "T": 3, "Int": 8, "Cl": 5},
                     "Old Hand": {"Name": "Old Hand", "Type": "Neophyte Hybrids", "Class": "Ganger", "XP": 0, "Kills": 0, "Advancements": None, "Effects": None, "Status": "Killed", "Weapons": "Autogun"},
                 }},
            "Ethernetans 2.0": {"gang_id": "g2", "name": "Ethernetans 2.0", "gang_type": "House Van Saar", "credits": 80, "reputation": 4, "rating": 800,
                               "fighters": {"Maex": {"Name": "Maex", "Type": "Subtek", "Class": "Juve", "XP": 5, "Kills": 2, "Advancements": "Cool", "Effects": None, "Status": "Active", "Weapons": "Lasgun", "Wargear": "Mesh armour", "Skills": None, "S": 3, "T": 3, "Int": 6, "Cl": 6}}},
            KLY: {"gang_id": "g3", "name": KLY, "gang_type": "Palanite Enforcers", "credits": 40, "reputation": 3, "rating": 850,
                  "fighters": {"Rook": {"Name": "Rook", "Type": "Patrolman", "Class": "Ganger", "XP": 1, "Kills": 0, "Status": "Active", "Weapons": "Stub gun"}}},
        },
        "territories": [{"Territory ID": "t1", "Territory": "Promethium Cache", "Gang ID": "g1", "Gang": C9, "Card": "4♦"}],
        "battles": [{"source_row": 2, "date": "2026-10-20", "scenario": "The Trap", "attacker": "The Slag Eaters", "defender": KLY, "winner": "The Slag Eaters", "territory": "Settlement", "territory_claimer": "The Slag Eaters", "notes": None}],
    }


def latest_game(before):
    after = deepcopy(before)
    after["captured_at"] = "2026-10-25T10:00:00+00:00"
    after["gangs"][C9]["fighters"]["Mara Kel"].update(XP=5, Status="Recovery", Effects="Injuries: Critical Injury")
    after["battles"] = [{"source_row": 2, "date": "2026-10-25", "scenario": "Takeover", "attacker": KLY, "defender": C9, "winner": C9, "territory": "Promethium Cache", "territory_claimer": C9, "notes": None}, dict(before["battles"][0], source_row=3)]
    return after


def apply(store, snapshot):
    result = ingest_snapshot(store, snapshot)
    store.project_snapshot(snapshot)
    return result, regenerate(store)


def fighter(store, name):
    return dict(store.db.execute("SELECT * FROM fighters WHERE name=?", (name,)).fetchone())


def mechanical_records(store):
    return ([tuple(row) for row in store.db.execute("SELECT * FROM campaign_events ORDER BY event_id")],
            [tuple(row) for row in store.db.execute("SELECT * FROM snapshots ORDER BY id")])


def _with_store(check):
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as folder:
        store = Store(Path(folder) / "story-test.db")
        try:
            check(store)
        finally:
            store.close()


def test_seeded_app_can_generate_before_its_first_live_refresh():
    from seed import main as seed_database
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as folder:
        path = Path(folder) / "fresh-preview.db"
        seed_database(str(path))
        store = Store(path)
        try:
            result = regenerate(store)
            assert result["fighters"] > 0
            mara = fighter(store, "Mara Kel")
            memories = read_memories(store, mara["id"])
            assert memories and all(memory["evidence"] for memory in memories)
            for memory in memories:
                assert store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id=?", (memory["source_id"],)).fetchone()
            assert not store.db.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            store.close()


def test_first_live_refresh_bridges_seed_fields_without_inventing_new_stat_changes():
    """A free-host restart must still notice Mara's injury relative to the seed."""
    from seed import main as seed_database
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as folder:
        path = Path(folder) / "fresh-live-preview.db"
        seed_database(str(path))
        store = Store(path)
        try:
            live = {"snapshot_version": 1, "captured_at": AT, "gangs": {}, "territories": [], "battles": []}
            aliases = {"type": "Type", "class": "Class", "cost": "Cost", "xp": "XP", "kills": "Kills", "advancements": "Advancements", "effects": "Effects", "status": "Status"}
            for gang_row in store.db.execute("SELECT * FROM gangs"):
                gang = dict(gang_row)
                gang["fighters"] = {}
                for fighter_row in store.db.execute("SELECT * FROM fighters WHERE gang_id=?", (gang["gang_id"],)):
                    record = dict(fighter_row)
                    # BS and T are newly supplied live data, not advancements.
                    state = {label: record[column] for column, label in aliases.items()}
                    state.update(Name=record["name"], BS=4, T=3)
                    gang["fighters"][record["name"]] = state
                live["gangs"][gang["name"]] = gang
            mara = fighter(store, "Mara Kel")
            assert mara["xp"] == 4 and mara["status"] == "Active"
            live["gangs"][mara["gang_name"]]["fighters"]["Mara Kel"].update(XP=5, Status="Recovery", Effects="Injuries: Critical Injury")
            result, generated = apply(store, live)
            assert generated["changed"] and result["events_created"]
            mara = fighter(store, "Mara Kel")
            memories = read_memories(store, mara["id"])
            critical = next(memory for memory in memories if "critical" in memory["tags"] and not memory["baseline"] and memory["memory_type"] == "observation")
            assert critical["source_event_ids"]
            assert set(critical["source_event_ids"]) <= set(result["events_created"])
            assert any("critical" in thought["tags"] for thought in select_mind(mara, memories, at=AT))
            events = store.events(limit=500)
            assert not any(event["event_type"] == "fighter_stat_changed" and event["payload"].get("field") in {"BS", "T"} for event in events)
            assert {event["event_type"] for event in events} >= {"fighter_xp_changed", "fighter_status_changed", "fighter_effects_changed"}
        finally:
            store.close()


def test_fresh_baseline_retains_evidence_when_writer_is_unconfigured():
    def check(store):
        apply(store, campaign())
        maex = fighter(store, "Maex")
        memories = read_memories(store, maex["id"])
        advancement = next(m for m in memories if m["title"] == "Advancement recorded")
        assert advancement["content"] == ""
        assert advancement["writer_status"] == "unconfigured"
        assert "Advancement recorded: Cool" in advancement["evidence"]
        assert advancement["provenance_class"] == "inference"
        assert store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id=?", (advancement["source_id"],)).fetchone()
        assert advancement["baseline"] and advancement["occurred_at"] is None
        assert not store.db.execute("PRAGMA foreign_key_check").fetchall()
    _with_store(check)


def test_critical_injury_creates_sourced_history_and_current_thought():
    def check(store):
        before = campaign()
        apply(store, before)
        result, generated = apply(store, latest_game(before))
        mara = fighter(store, "Mara Kel")
        memories = read_memories(store, mara["id"])
        critical = next(m for m in memories if m["memory_type"] == "observation" and "critical" in m["tags"])
        assert generated["changed"] and critical["source_event_ids"]
        assert set(critical["source_event_ids"]) <= set(result["events_created"])
        assert any("Critical Injury" in fact for fact in critical["evidence"])
        assert critical["content"] == ""
        assert critical["writer_status"] == "unconfigured"
        assert critical["observed_at"] == "2026-10-25T10:00:00+00:00" and critical["occurred_at"] is None
        mind = select_mind(mara, memories, at=AT)
        assert 2 <= len(mind) <= 4
        assert len({thought["memory_id"] for thought in mind}) == len(mind)
        assert any("critical" in thought["tags"] for thought in mind)
        for thought in mind:
            assert thought["memory_id"] in {m["id"] for m in memories}
    _with_store(check)


def test_replaying_sync_and_generation_does_not_duplicate_history():
    def check(store):
        before = campaign()
        apply(store, before)
        after = latest_game(before)
        apply(store, after)
        counts = tuple(store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("story_memories", "story_artifacts", "campaign_events", "snapshots"))
        result, regenerated = apply(store, after)
        assert not result["events_created"] and not regenerated["changed"]
        assert tuple(store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("story_memories", "story_artifacts", "campaign_events", "snapshots")) == counts
        regenerate(store, force=True)
        assert tuple(store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("story_memories", "story_artifacts", "campaign_events", "snapshots")) == counts
    _with_store(check)


def test_recovery_closes_current_critical_concern_but_preserves_memory():
    def check(store):
        before = campaign()
        injured = latest_game(before)
        apply(store, before)
        apply(store, injured)
        recovered = deepcopy(injured)
        recovered["captured_at"] = "2026-10-26T10:00:00+00:00"
        recovered["gangs"][C9]["fighters"]["Mara Kel"].update(Status="Active", Effects=None, XP=6)
        apply(store, recovered)
        mara = fighter(store, "Mara Kel")
        memories = read_memories(store, mara["id"])
        assert any("critical" in m["tags"] for m in memories)
        mind = select_mind(mara, memories, at="2026-10-26T12:00:00+00:00")
        assert not any("critical" in thought["tags"] for thought in mind)
        assert not any("recovery" in thought["tags"] and "return" not in thought["tags"] for thought in mind)
        assert any("return" in thought["tags"] for thought in mind)
    _with_store(check)


def test_first_known_state_does_not_drift_with_current_xp():
    def check(store):
        before = campaign()
        apply(store, before)
        mara_id = fighter(store, "Mara Kel")["id"]
        first = next(m for m in read_memories(store, mara_id) if m["memory_key"] == "first-known-state")
        evidence = first["evidence"]
        apply(store, latest_game(before))
        later = next(m for m in read_memories(store, mara_id) if m["memory_key"] == "first-known-state")
        assert later["evidence"] == evidence
        assert "XP: 4" in evidence and "XP: 5" not in evidence
    _with_store(check)


def test_deceased_fighters_have_no_mind_or_new_posthumous_reflection():
    def check(store):
        apply(store, campaign())
        dead = fighter(store, "Old Hand")
        memories = read_memories(store, dead["id"])
        assert select_mind(dead, memories, at=AT) == []
        assert not any(memory["memory_type"] == "reflection" for memory in memories)
    _with_store(check)


def test_weapon_and_promotion_changes_are_memorable():
    def check(store):
        before = campaign()
        apply(store, before)
        changed = deepcopy(before)
        changed["captured_at"] = AT
        changed["gangs"]["Ethernetans 2.0"]["fighters"]["Maex"].update(Class="Specialist", Weapons="Plasma gun")
        result, _ = apply(store, changed)
        memories = read_memories(store, fighter(store, "Maex")["id"])
        new = [m for m in memories if set(m["source_event_ids"]) & set(result["events_created"]) and m["memory_type"] == "observation"]
        assert any("promotion" in m["tags"] for m in new)
        assert any("equipment" in m["tags"] for m in new)
        assert all(m["content"] == "" and m["writer_status"] == "unconfigured" for m in new)
        assert any("Plasma gun" in fact for m in new for fact in m["evidence"])
        assert any("Role: Juve → Specialist" in m["evidence"] for m in new)
    _with_store(check)


def test_regeneration_versions_artifacts_and_preserves_authored_and_mechanical_records():
    def check(store):
        before = campaign()
        ingest_snapshot(store, before)
        store.project_snapshot(before)
        fighter_text = "KEL, Mara\nWorkshop Audit — 781.M41\n‘It is one workshop.’\n[ERR::INDEX]"
        gang_text = "THE PROSPECT\nAuthored canon; deliberate contradictions.\n+++ RECORD TERMINATES +++"
        store.db.execute("UPDATE fighters SET backstory=?,backstory_source='player-authored / C-NINE story' WHERE name='Mara Kel'", (fighter_text,))
        store.db.execute("UPDATE gangs SET backstory=?,backstory_source='canon_authored' WHERE gang_id='g1'", (gang_text,))
        store.db.commit()
        mechanical_before = mechanical_records(store)
        regenerate(store)
        assert mechanical_records(store) == mechanical_before
        first_artifacts = store.db.execute("SELECT count(*) FROM story_artifacts").fetchone()[0]
        apply(store, latest_game(before))
        assert fighter(store, "Mara Kel")["backstory"] == fighter_text
        assert store.db.execute("SELECT backstory FROM gangs WHERE gang_id='g1'").fetchone()[0] == gang_text
        assert store.db.execute("SELECT count(*) FROM story_artifacts").fetchone()[0] > first_artifacts
        assert store.db.execute("SELECT count(*) FROM story_artifacts WHERE active=0").fetchone()[0] > 0
        assert not store.db.execute("SELECT scope_type,scope_key FROM story_artifacts WHERE active=1 GROUP BY scope_type,scope_key HAVING count(*)>1").fetchall()
    _with_store(check)


def test_latest_report_matches_its_current_battle_instead_of_shifted_row():
    def check(store):
        before = campaign()
        apply(store, before)
        apply(store, latest_game(before))
        row = store.db.execute("SELECT * FROM battles WHERE active=1 AND date='2026-10-25'").fetchone()
        report = document_for(store, "battle_report", row["id"])
        text = " ".join(block.get("text", "") for block in report["blocks"])
        all_text = json.dumps(report, ensure_ascii=False)
        assert "Takeover" in all_text and "Promethium Cache" in all_text
        assert "C-NINE" in all_text and KLY in all_text
        assert "The Slag Eaters" not in text
        assert report["blocks"] == [] and report["writer_status"] == "unconfigured"
        assert report["evidence"] and report["source_event_ids"]
        assert report["provenance_class"] == "inference"
    _with_store(check)


def test_corrected_or_removed_battle_does_not_leave_current_false_outcome_memories():
    def check(store):
        before = campaign()
        after = latest_game(before)
        apply(store, before)
        apply(store, after)
        mara_id = fighter(store, "Mara Kel")["id"]
        victory_ids = {memory["id"] for memory in read_memories(store, mara_id) if "victory" in memory["tags"]}
        corrected = deepcopy(after)
        corrected["captured_at"] = "2026-10-25T11:00:00+00:00"
        corrected["battles"][0].update(winner=KLY, territory_claimer=KLY)
        result, _ = apply(store, corrected)
        correction_ids = {event["event_id"] for event in store.events(limit=500) if event["event_type"] == "battle_record_corrected"}
        assert correction_ids & set(result["events_created"])
        current = [memory for memory in read_memories(store, mara_id) if memory["memory_type"] == "observation" and "battle" in memory["tags"] and "Scenario: Takeover" in memory["evidence"]]
        assert current and all(f"Winner: {KLY}" in memory["evidence"] for memory in current)
        assert any(set(memory["source_event_ids"]) & correction_ids for memory in current)
        assert not victory_ids & {memory["id"] for memory in read_memories(store, mara_id)}
        removed = deepcopy(corrected)
        removed["captured_at"] = "2026-10-25T12:00:00+00:00"
        removed["battles"] = [dict(corrected["battles"][1], source_row=2)]
        apply(store, removed)
        assert not any("battle" in memory["tags"] and "Scenario: Takeover" in memory["evidence"] for memory in read_memories(store, mara_id))
        assert store.db.execute("SELECT count(*) FROM story_memories WHERE fighter_id=? AND active=0", (mara_id,)).fetchone()[0] > 0
    _with_store(check)


def test_voice_profile_changes_which_equally_salient_memory_leads_the_mind():
    memories = []
    for key, topic in (("a-training", "skill"), ("z-combat", "kills")):
        memories.append({"id": key, "memory_key": key, "memory_type": "observation", "content": f"A remembered {topic} event.", "importance": 7, "observed_at": AT, "occurred_at": None, "baseline": False, "tags": [topic], "source_event_ids": [key], "evidence": [f"Recorded {topic} change."]})
    analytical = {"class": "Ganger", "status": "Active", "effects": None, "voice_profile_json": json.dumps({"traits": ["analytical"]})}
    blooded = {**analytical, "voice_profile_json": json.dumps({"traits": ["blooded"]})}
    analytical_mind = select_mind(analytical, memories, at=AT)
    blooded_mind = select_mind(blooded, memories, at=AT)
    assert analytical_mind[0]["memory_id"] == "a-training"
    assert blooded_mind[0]["memory_id"] == "z-combat"
    assert {m["memory_id"] for m in analytical_mind} == {m["memory_id"] for m in blooded_mind}


def test_non_c9_sheet_backstory_and_notes_survive_without_false_c9_source_links():
    def check(store):
        store.db.execute("INSERT INTO lore_sources(title,source_type,content,source_url) VALUES('C-NINE archive','canonical player-authored lore','A separate C-NINE canonical source.','https://example.invalid/c-nine')")
        store.db.commit()
        authored = "MAEX — Private calibration log\n‘I keep the damaged instruments. They tell me where the limits were.’\nReference 17-B."
        notes = "Player note: prefers damaged equipment."
        before = campaign()
        record = before["gangs"]["Ethernetans 2.0"]["fighters"]["Maex"]
        record.update(Backstory=authored, **{"Fighter Notes": notes})
        apply(store, before)
        maex = fighter(store, "Maex")
        assert maex["backstory"] == authored and maex["notes"] == notes
        assert maex["provenance_class"] == "player_authored"
        assert "campaign Sheet" in maex["backstory_source"]
        assert store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id='canon:c-nine-story-export'").fetchone()
        links = [row[0] for row in store.db.execute("""SELECT ne.source_id FROM narrative_evidence ne JOIN story_memories sm ON ne.artifact_key=sm.memory_id
            WHERE ne.artifact_type='story_memory' AND sm.fighter_id=? AND sm.active=1 AND ne.source_id IS NOT NULL""", (maex["id"],))]
        assert "player:campaign-sheet-lore" in links
        assert "canon:c-nine-story-export" not in links
        changed = deepcopy(before)
        changed["captured_at"] = AT
        changed["gangs"]["Ethernetans 2.0"]["fighters"]["Maex"]["XP"] = 6
        apply(store, changed)
        assert fighter(store, "Maex")["backstory"] == authored
    _with_store(check)


def test_resolved_gangmate_capture_stays_in_history_without_current_captivity_thought():
    def check(store):
        before = campaign()
        before["gangs"][C9]["fighters"]["Elias"] = {"Name": "Elias", "Type": "Neophyte Hybrids", "Class": "Ganger", "XP": 0, "Kills": 0, "Effects": None, "Status": "Active"}
        apply(store, before)
        captured = deepcopy(before)
        captured["captured_at"] = "2026-10-25T09:00:00+00:00"
        captured["gangs"][C9]["fighters"]["Elias"]["Status"] = "Captured"
        apply(store, captured)
        mara = fighter(store, "Mara Kel")
        capture = next(memory for memory in read_memories(store, mara["id"]) if memory["memory_type"] == "observation" and {"captivity", "belonging"} <= set(memory["tags"]))
        assert capture["source_event_ids"]
        assert any("Elias" in fact for fact in capture["evidence"]), "A shared status event must name its subject in the evidence block."
        returned = deepcopy(captured)
        returned["captured_at"] = "2026-10-25T11:00:00+00:00"
        returned["gangs"][C9]["fighters"]["Elias"]["Status"] = "Active"
        apply(store, returned)
        memories = read_memories(store, mara["id"])
        history = [memory for memory in memories if set(memory["source_event_ids"]) & set(capture["source_event_ids"])]
        assert history and all("history_only" in memory["tags"] for memory in history)
        assert any("Current source status for Elias: Active" in memory["evidence"] for memory in history)
        assert not any(set(thought["source_event_ids"]) & set(capture["source_event_ids"]) for thought in select_mind(fighter(store, "Mara Kel"), memories, at=AT))
    _with_store(check)


if __name__ == "__main__":
    checks = [value for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    failures = []
    for check in checks:
        try:
            check()
            print("PASS", check.__name__)
        except Exception as error:
            failures.append((check.__name__, error))
            print("FAIL", check.__name__, repr(error))
    if failures:
        raise AssertionError(f"{len(failures)} story checks failed: " + ", ".join(name for name, _ in failures))
    print(f"ok ({len(checks)} story checks)")
