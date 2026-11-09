"""Regression checks for layered identity in NCCE writer packets."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voice_layers import build_voice_layers


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

    def test_unprofiled_ethernetans_fighter_gets_gang_not_personality(self):
        voice = build_voice_layers({"gang": "Ethernetans 2.0",
                                    "affiliation": "House Van Saar",
                                    "subject_name": "Unknown Tek-hunter"})
        self.assertIn("field_tech_detail", voice["gang"]["tags"])
        self.assertEqual(voice["individual"]["tags"], [])

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
