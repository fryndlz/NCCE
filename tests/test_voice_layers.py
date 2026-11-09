"""Regression checks for layered identity in NCCE writer packets."""
import sys
import unittest
import json
import tempfile
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voice_layers import build_voice_layers, load_registry, validate_registry
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from voice_registry_cli import update_registry


class VoiceLayersTest(unittest.TestCase):
    def test_slag_eaters_individual_voices_differ(self):
        base = {"gang": "The Slag Eaters", "affiliation": "House Orlock",
                "inferred_identity": [{"label": "Recorded role", "value": "Prospect", "source": "mechanical_fact"}]}
        john = build_voice_layers({**base, "subject_name": "John Bullet"})
        boomer = build_voice_layers({**base, "subject_name": "Boomer"})
        eisen = build_voice_layers({**base, "subject_name": "Eisen"})
        self.assertEqual(john["gang"]["tags"], boomer["gang"]["tags"])
        self.assertNotEqual(john["individual"]["tags"], boomer["individual"]["tags"])
        self.assertNotEqual(boomer["individual"]["tags"], eisen["individual"]["tags"])
        self.assertEqual(boomer["individual"]["role"], "Prospect")
        self.assertEqual(boomer["purpose"], "writer_style_guidance_only")

    def test_unprofiled_fighter_remains_unprofiled(self):
        result = build_voice_layers({"gang": "Unknown Gang", "affiliation": "House Orlock", "subject_name": "Unknown"})
        self.assertEqual(result["faction"]["tags"][0], "industrial_labour")
        self.assertEqual(result["gang"]["tags"], [])
        self.assertEqual(result["individual"]["tags"], [])

    def test_helmaeth_profile_keeps_individuals_distinct(self):
        base = {"gang": "Helmaeth Expeditionary Force",
                "affiliation": "Ironhead Squat Prospectors"}
        horgar = build_voice_layers({**base, "subject_name": "Horgar"})
        brint = build_voice_layers({**base, "subject_name": "Brint"})
        self.assertIn("ancestral_charters", horgar["faction"]["tags"])
        self.assertIn("helmaeth_kin", brint["gang"]["tags"])
        self.assertNotEqual(horgar["individual"]["tags"], brint["individual"]["tags"])
        self.assertEqual(brint["individual"]["provenance"], "accepted_biography_voice_inference")

    def test_ethernetans_profile_respects_rare_archeotek_clearance(self):
        base = {"gang": "Ethernetans 2.0", "affiliation": "House Van Saar"}
        maex = build_voice_layers({**base, "subject_name": "Maex"})
        apex = build_voice_layers({**base, "subject_name": "Peter Apex"})
        self.assertEqual(maex["gang"]["tags"], apex["gang"]["tags"])
        self.assertNotIn("restricted_archeotek_perspective", maex["individual"]["tags"])
        self.assertIn("restricted_archeotek_perspective", apex["individual"]["tags"])

    def test_palanite_attachment_not_van_saar_voice(self):
        base = {"gang": "Ethernetans 2.0", "affiliation": "House Van Saar",
                "inferred_identity": [{"label": "Recorded role", "value": "Champion",
                                       "source": "mechanical_fact"}]}
        for name in ("Dredd 2D", "Dredd 3D"):
            with self.subTest(name=name):
                voice = build_voice_layers({**base, "subject_name": name})
                self.assertEqual(voice["faction"]["name"], "House Helmawr")
                self.assertEqual(voice["gang"]["name"], "Palanite Household Companions")
                self.assertEqual(voice["gang"]["host_gang"], "Ethernetans 2.0")
                self.assertIn("sealed_household_orders", voice["gang"]["tags"])
                self.assertEqual(voice["individual"]["role"], "Champion")
                self.assertNotIn("clearance_conflict", voice["gang"]["tags"])

    def test_allied_and_hired_fighters_do_not_inherit_squat_kin_voice(self):
        base = {"gang": "Helmaeth Expeditionary Force", "affiliation": "Ironhead Squat Prospectors"}
        for name in ("Frank J. WIlson", "Eliot Ness"):
            with self.subTest(name=name):
                v = build_voice_layers({**base, "subject_name": name})
                self.assertEqual(v["faction"]["name"], "House Ran Lo")
                self.assertEqual(v["gang"]["name"], "Auditing Conclave")
                self.assertEqual(v["gang"]["host_gang"], "Helmaeth Expeditionary Force")
                self.assertNotIn("helmaeth_kin", v["gang"]["tags"])
        for name in ("Bop", "Alrik III"):
            with self.subTest(name=name):
                v = build_voice_layers({**base, "subject_name": name})
                self.assertEqual(v["faction"]["name"], "")
                self.assertEqual(v["gang"]["tags"], [])
                self.assertNotIn("helmaeth_kin", v["gang"]["tags"])

    def test_cyberachnid_is_profiled_nonhuman_without_human_voice(self):
        v = build_voice_layers({"gang": "Ethernetans 2.0", "affiliation": "House Van Saar",
                                "subject_name": "Cyberachnid"})
        self.assertIn("bio_mechanical_organism", v["individual"]["tags"])
        self.assertIn("DO NOT write human speech", v["individual"]["register"])

    def test_unprofiled_ethernetans_fighter_gets_gang_not_personality(self):
        voice = build_voice_layers({"gang": "Ethernetans 2.0",
                                    "affiliation": "House Van Saar",
                                    "subject_name": "Unknown Tek-hunter"})
        self.assertIn("field_tech_detail", voice["gang"]["tags"])
        self.assertEqual(voice["individual"]["tags"], [])

    def test_live_registry_has_all_five_current_gangs(self):
        registry = load_registry()
        for name in ("The Slag Eaters", "Geothermal Prospect Detail C-9",
                     "Kły Sprawiedliwości", "Ethernetans 2.0",
                     "Helmaeth Expeditionary Force"):
            self.assertEqual(registry["gangs"][name]["review_status"] if "review_status" in registry["gangs"][name] else "approved", "approved")
        self.assertIn("Patrol do spraw alkoholu i broni", registry["excluded_gangs"])

    def test_cnine_alias_and_fighter_knowledge_boundaries(self):
        v = build_voice_layers({
            "gang": "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]",
            "affiliation": "Genestealer Cults",
            "subject_name": "Garrick Voss",
        })
        self.assertEqual(v["gang"]["name"], "Geothermal Prospect Detail C-9")
        self.assertIn("unofficial_maps", v["individual"]["tags"])
        self.assertEqual(v["purpose"], "writer_style_guidance_only")
        self.assertNotIn("texan_road_gang", v["gang"]["tags"])

    def test_kly_public_profile_does_not_leak_gm_secret(self):
        v = build_voice_layers({
            "gang": "Kły Sprawiedliwości",
            "affiliation": "Palanite Enforcers", "subject_name": "Tomas",
        })
        self.assertIn("literal_warrant_checking", v["individual"]["tags"])
        self.assertIn("rigid_discipline", v["gang"]["tags"])
        self.assertNotIn("Adeptus Arbites", json.dumps(v))
        self.assertNotIn("undercover", json.dumps(v).lower())

    def test_patrol_excluded_and_neutral_until_approved(self):
        v = build_voice_layers({"gang": "Patrol do spraw alkoholu i broni",
                                "affiliation": "Palanite Enforcers",
                                "subject_name": "Any Patrol Fighter"})
        self.assertEqual(v["gang"]["tags"], [])
        self.assertEqual(v["individual"]["tags"], [])
        self.assertEqual(v["faction"]["tags"], [])
        self.assertEqual(v["gang"]["review_status"], "excluded_until_onboarded")

    def test_new_gang_registration_pending_then_approved(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "registry.json"
            path.write_text(json.dumps(deepcopy(load_registry())), encoding="utf-8")
            pending = update_registry(path, "register",
                                      gang="Patrol do spraw alkoholu i broni",
                                      faction="Palanite Enforcers",
                                      source="Player-authored Patrol source version X")
            v = build_voice_layers({"gang": "Patrol do spraw alkoholu i broni",
                                    "affiliation": "Palanite Enforcers"},
                                   registry=pending)
            self.assertEqual(v["gang"]["tags"], [])
            self.assertEqual(v["gang"]["review_status"], "pending_editorial")
            active = update_registry(path, "approve",
                                     gang="Patrol do spraw alkoholu i broni",
                                     register="Distinct owner-reviewed patrol register",
                                     tags="licensed_raid,permit_check",
                                     source="Editorial approval reference Y")
            v = build_voice_layers({"gang": "Patrol do spraw alkoholu i broni",
                                    "affiliation": "Palanite Enforcers"},
                                   registry=active)
            self.assertEqual(v["gang"]["tags"], ["licensed_raid", "permit_check"])
            self.assertNotIn("rigid_discipline", v["gang"]["tags"])
            with self.assertRaises(ValueError):
                update_registry(path, "register",
                                gang="Patrol do spraw alkoholu i broni",
                                faction="Palanite Enforcers", source="duplicate")
            added = update_registry(path, "add-fighter",
                                    gang="Patrol do spraw alkoholu i broni",
                                    fighter="Fighter A", register="Cited preference",
                                    tags="cautious", source="Accepted fighter account Z")
            vv = build_voice_layers({"gang": "Patrol do spraw alkoholu i broni",
                                     "subject_name": "Fighter A"}, registry=added)
            self.assertIn("cautious", vv["individual"]["tags"])

    def test_foreign_crew_under_cnine_uses_external_register(self):
        v = build_voice_layers({"gang": "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]",
                                "affiliation": "Genestealer Cults",
                                "subject_name": "Lady Marcella Veyne"})
        self.assertEqual(v["gang"]["name"], "Peregrine's Due")
        self.assertEqual(v["faction"]["name"], "Independent")
        self.assertIn("commercial_fixer", v["individual"]["tags"])
        self.assertNotIn("hereditary_deep_work", v["gang"]["tags"])

    def test_missing_gang_profile_does_not_guess_individual(self):
        v = build_voice_layers({"gang": "Unregistered Gang",
                                "affiliation": "House Orlock",
                                "subject_name": "Boomer"})
        self.assertEqual(v["gang"]["tags"], [])
        self.assertEqual(v["individual"]["tags"], [])

    def test_bad_alias_or_schema_rejected(self):
        bad = deepcopy(load_registry())
        bad["aliases"]["bad"] = "nonexistent"
        with self.assertRaises(ValueError):
            validate_registry(bad)
        bad = deepcopy(load_registry())
        bad["schema_version"] = 2
        with self.assertRaises(ValueError):
            validate_registry(bad)

    def test_no_identity_guessed_from_name(self):
        result = build_voice_layers({"subject_name": "Boomer"})
        self.assertEqual(result["individual"]["tags"], [])
        self.assertEqual(result["gang"]["name"], "")
        self.assertEqual(result["faction"]["name"], "")

    def test_no_contemporary_injury_leak(self):
        result = build_voice_layers({"gang": "The Slag Eaters", "subject_name": "Boomer",
                                     "effects": "Enfeebled", "status": "Retired",
                                     "inferred_identity": [{"label": "Recorded role", "source": "inference", "value": "Veteran"}]})
        self.assertEqual(result["individual"]["role"], "")
        self.assertNotIn("Enfeebled", str(result))
        self.assertNotIn("Retired", str(result))


if __name__ == "__main__":
    unittest.main()
