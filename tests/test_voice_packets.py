"""Packet-level checks: editorial profiles must not change mechanical facts."""
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from exchange_automation import _packet, seal


class StoreStub:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE gangs (gang_id TEXT PRIMARY KEY, name TEXT, gang_type TEXT);
            CREATE TABLE fighters (id INTEGER PRIMARY KEY, name TEXT, gang_id TEXT, gang_name TEXT, writer_identity_json TEXT);
            CREATE TABLE campaign_events (
                event_id TEXT, event_type TEXT, occurred_at TEXT,
                observed_at TEXT, payload_json TEXT
            );
        """)

    def add(self, fighter_id, fighter_name, gang_name, faction):
        gang_id = "gang-" + str(fighter_id)
        self.db.execute("INSERT INTO gangs VALUES (?, ?, ?)", (gang_id, gang_name, faction))
        self.db.execute("INSERT INTO fighters (id,name,gang_id,gang_name) VALUES (?, ?, ?, ?)",
                        (fighter_id, fighter_name, gang_id, gang_name))


def request_for(fighter_id, name):
    return {
        "kind": "memory", "key": [fighter_id, "legacy:test"],
        "form": "fighter_memory", "entity_type": "fighter",
        "entity_key": str(fighter_id), "title": "Known at baseline",
        "event_at_utc": "", "facts": {"evidence_json": ["Campaign baseline: 0 XP, 0 kills"]},
        "context": {"subject_name": name}, "ready": False,
    }


class VoicePacketTests(unittest.TestCase):
    def test_cnine_fallback_uses_roster_identity_without_modifying_facts(self):
        store = StoreStub()
        store.add(1, "Garrick Voss", "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]", "Genestealer Cults")
        target = request_for(1, "Garrick Voss")
        prior = seal(target)
        packet = _packet(store, target, "request-test-cn")
        sections = {x["section"]: x for x in packet["context"]}
        self.assertEqual(packet["request"]["source_revision"], prior)
        self.assertEqual(json.loads(sections["mechanics"]["text"])["evidence_json"],
                         ["Campaign baseline: 0 XP, 0 kills"])
        self.assertNotIn("gang", json.loads(sections["character_context"]["text"]))
        self.assertEqual(sections["voice_layers"]["provenance"], "style_guidance")
        voice = json.loads(sections["voice_layers"]["text"])
        self.assertEqual(voice["gang"]["name"], "Geothermal Prospect Detail C-9")
        self.assertIn("survey_accuracy", voice["individual"]["tags"])

    def test_owner_authored_identity_is_explicit_and_prioritized(self):
        store = StoreStub()
        store.add(10, "New Fighter", "The Slag Eaters", "House Orlock")
        store.db.execute("UPDATE fighters SET writer_identity_json=? WHERE id=10",
                         (json.dumps({"voice": ["terse", "careful"], "narration_mode": "sapient"}),))
        packet = _packet(store, request_for(10, "New Fighter"), "request-authored-identity")
        voice = json.loads(next(x["text"] for x in packet["context"] if x["section"] == "voice_layers"))
        self.assertEqual(voice["individual"]["authored_identity"]["voice"], ["terse", "careful"])
        self.assertEqual(voice["individual"]["authored_identity_source"], "player_authored_identity")

    def test_patrol_new_roster_identity_stays_neutral(self):
        store = StoreStub()
        store.add(2, "New Fighter", "Patrol do spraw alkoholu i broni", "Palanite Enforcers")
        voice = json.loads(next(x["text"] for x in _packet(store, request_for(2, "New Fighter"),
            "request-test-patrol")["context"] if x["section"] == "voice_layers"))
        self.assertEqual(voice["gang"]["tags"], [])
        self.assertEqual(voice["faction"]["tags"], [])
        self.assertEqual(voice["gang"]["review_status"], "excluded_until_onboarded")

    def test_external_cnine_affiliation_overrides_host_roster(self):
        store = StoreStub()
        store.add(3, "Lady Marcella Veyne",
                  "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]", "Genestealer Cults")
        voice = json.loads(next(x["text"] for x in _packet(store, request_for(3, "Lady Marcella Veyne"),
            "request-test-outsider")["context"] if x["section"] == "voice_layers"))
        self.assertEqual(voice["gang"]["name"], "Peregrine's Due")
        self.assertEqual(voice["faction"]["name"], "Independent")
        self.assertNotIn("shared_presence_when_known", voice["gang"]["tags"])


if __name__ == "__main__":
    unittest.main()
