"""Historical gang coverage and isolation from the fighter writing pipeline."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gang_battle_history import project
from store import Store
from story_engine import regenerate


def test_initial_snapshot_corrections_removals_and_preservation():
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "campaign.db")
        try:
            gangs = {name: {"name": name, "gang_id": key, "fighters": {"Test fighter": {"Status": "Active"}}}
                     for key, name in zip("abcdef", ("Alpha", "Beta", "Gamma", "Delta", "Echo", "Foxtrot"))}
            battle = dict(source_row=2, source_battle_id="battle-1", date="2026-07-01",
                          scenario="The Trap", attacker="Alpha", defender="Beta",
                          winner="Beta", territory="Old Ruins")
            other = dict(battle, source_row=3, source_battle_id="battle-2",
                         scenario="Ambush", attacker="Delta", defender=None, winner=None)
            store.project_snapshot(dict(gangs=gangs, battles=[battle, other]))
            first = store.gang("a")["battles"][0]
            assert first["gang_result"] == "Lost" and first["opponents"] == ["Beta"]
            assert first["source_locator"] == "Battles!battle id:battle-1"
            assert first["source_event_ids"] == []
            assert store.gang("b")["battles"][0]["gang_result"] == "Won"
            assert store.gang("d")["battles"][0]["opponents"] == []
            assert not store.gang("e")["battles"]
            fighter_id = store.gang("a")["fighters"][0]["id"]
            with store.db:
                store.db.execute("""INSERT INTO story_memories
                    (memory_id,fighter_id,memory_key,memory_type,title,content,importance,created_at,
                     tags_json,evidence_json,source_event_ids_json,source_observation_ids_json,generation_version,writer_status,source_id)
                    VALUES ('accepted',?,'gang-record:id:battle-1','observation','Title','Accepted wording',
                            6,'2026-07-01','[]','[]','[]','[]','previous','ready','baseline:snapshot-0001')""", (fighter_id,))
                for request_id, revision_of in (("imported", None), ("revision", "imported")):
                    store.db.execute("""INSERT INTO writing_exchange_requests
                        (request_id,target_key,packet_json,target_json,source_revision,state,created_at,
                         receipt,raw_markdown,revision_of)
                        VALUES (?,?,'{}','{}',?,?, '2026-07-01',?,?,?)""",
                        (request_id, f'["memory",[{fighter_id},"gang-record:id:battle-1"]]',
                         request_id, "PENDING" if revision_of else "IMPORTED",
                         None if revision_of else "receipt", None if revision_of else "Accepted wording",
                         revision_of))
            requests_before = [tuple(r) for r in store.db.execute(
                "SELECT * FROM writing_exchange_requests ORDER BY request_id")]
            before = tuple(store.db.execute("SELECT * FROM story_memories WHERE memory_id='accepted'").fetchone())
            regenerate(store, force=True, writer_enabled=False)
            store.project_snapshot(dict(gangs=gangs, battles=[dict(battle, source_row=8, winner="Alpha")]))
            regenerate(store, force=True, writer_enabled=False)
            corrected = store.gang("a")["battles"]
            assert len(corrected) == 1 and corrected[0]["id"] == first["id"]
            assert corrected[0]["gang_result"] == "Won"
            assert not store.gang("d")["battles"]
            assert [tuple(r) for r in store.db.execute("SELECT * FROM story_memories WHERE memory_key LIKE 'gang%'")] == [before]
            assert [tuple(r) for r in store.db.execute(
                "SELECT * FROM writing_exchange_requests ORDER BY request_id")] == requests_before
        finally:
            store.close()


def test_archive_link_includes_additional_participant_and_excludes_removed():
    current = dict(id=1, date="2026-07-01", scenario="The Trap",
                   attacker="Alpha", defender="Beta", winner="Beta")
    archive = dict(battle_id="raw", documented_at="2026-07-01T09:00:00Z", scenario="The Trap",
                   gang_ids=["a", "b", "c"], attacker="Alpha", defender="Beta", territory="Old Ruins")
    names = dict(a="Alpha", b="Beta", c="Gamma")
    history = project([current], [archive], names, [])
    assert set(history) == set(names)
    assert history["c"][0]["opponents"] == ["Alpha", "Beta"]
    assert history["c"][0]["territory"] == "Old Ruins"
    assert history["c"][0]["archive_battle_id"] == "raw"
    assert history["c"][0]["gang_result"] == "Lost"
    explicit = dict(current, source_battle_key="id:raw")
    unrelated = dict(event_type="battle_result", event_id="different",
                     payload=dict(current, battle_key="id:another-battle"))
    assert project([explicit], [archive], names, [unrelated])["a"][0]["source_event_ids"] == []
    assert project([], [archive], names, []) == {}


if __name__ == "__main__":
    test_initial_snapshot_corrections_removals_and_preservation()
    test_archive_link_includes_additional_participant_and_excludes_removed()
    print("ok (historical gang battle coverage)")
