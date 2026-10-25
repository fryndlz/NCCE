"""Guard against C-NINE vocabulary leaking into another gang's voice."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from story_prose import observation_text, voice_profile


def test_palanite_voice_uses_its_own_faction_context():
    gang = {"name": "Kły Sprawiedliwości", "gang_type": "Palanite Enforcers"}
    fighter = {"name": "Rook", "gang_name": gang["name"], "class": "Ganger", "type": "Patrolman"}
    profile = voice_profile(fighter, gang)
    recovery = observation_text(fighter, gang, "fighter_status_changed", {
        "field": "Status", "before": "Active", "after": "Recovery",
    })
    defeat = observation_text(fighter, gang, "gang_battle_outcome", {
        "winner": "The Slag Eaters", "territory": "Promethium Cache",
    }, context={"battle": {"winner": "The Slag Eaters", "territory": "Promethium Cache"}})

    assert profile["register"] == "precinct"
    assert "precinct" in recovery.casefold()
    assert "detail" not in recovery.casefold()
    assert "detail" not in defeat.casefold()
    assert "cleaner account" not in defeat.casefold()


def test_c_nine_alone_receives_the_c_nine_register():
    gang = {"name": "THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]", "gang_type": "Genestealer Cults"}
    fighter = {"name": "Mara Kel", "gang_name": gang["name"], "class": "Ganger", "type": "Neophyte Hybrids"}
    assert voice_profile(fighter, gang)["register"] == "crew"


if __name__ == "__main__":
    checks = [value for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    for check in checks:
        check()
        print("PASS", check.__name__)
    print(f"ok ({len(checks)} voice checks)")
