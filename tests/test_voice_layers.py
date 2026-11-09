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
