"""Regression tests for versioned portable literary policy and live exchange hooks."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from literary_policy import load_literary_policy, resolve_literary_policy, measure_prose
from portable_packet import build_portable_zip
from exchange_automation import _packet, prospective_biography_length_error
sys.path.insert(0,str(ROOT/'scripts'))
from record_owner_literary_decision import record_owner_decision
from test_voice_packets import StoreStub, request_for


class PortableLiteraryTests(unittest.TestCase):
    def test_process_page_explains_real_identity_and_deployment_boundary(self):
        page=(ROOT/"web/writing-process.html").read_text(encoding="utf-8")
        self.assertIn("Palanite Enforcers",page)
        self.assertIn("Kły Sprawiedliwości",page)
        self.assertIn("Patrol do spraw alkoholu i broni",page)
        self.assertIn("Other prose forms",page)
        self.assertIn("Render deployment is not yet verified",page)
        self.assertIn("/api/portable-writing-packet.zip",page)
        self.assertNotIn("Gang Biography</strong><p>1,900",page)

    def test_form_specific_lengths_and_hard_cap(self):
        self.assertTrue(measure_prose("fighter_biography","a"*2000)["hard_limit_ok"])
        self.assertEqual(measure_prose("fighter_biography","x"*2300)["status"],"outside_target_review")
        self.assertEqual(measure_prose("fighter_biography","x"*2301)["status"],"over_hard_cap")
        self.assertEqual(measure_prose("fighter_biography","x"*1900)["status"],"ok")
        self.assertIsNone(measure_prose("fighter_memory","x"*2301)["hard_max_characters"])
        self.assertIsNone(measure_prose("gang_history","x"*3500)["hard_max_characters"])

    def test_distinct_palanite_gangs_never_share_local_register(self):
        kly=resolve_literary_policy("fighter_biography",gang="Kły Sprawiedliwości",faction="Palanite Enforcers")
        patrol=resolve_literary_policy("fighter_biography",gang="Patrol do spraw alkoholu i broni",faction="Palanite Enforcers")
        self.assertIn("pack loyalty", kly["gang"]["profile"]["upper_authority"])
        self.assertIsNone(patrol["gang"]["profile"])
        self.assertIsNotNone(patrol["faction"]["profile"])

    def test_unapproved_voice_stays_neutral_and_external_is_independent(self):
        v={"gang":{"name":"Patrol do spraw alkoholu i broni","review_status":"excluded_until_onboarded"},
           "faction":{"name":"Palanite Enforcers"}}
        self.assertIsNone(resolve_literary_policy("fighter_mind",voice_layers=v)["gang"]["profile"])
        v2={"gang":{"name":"Peregrine's Due","host_gang":"Geothermal Prospect Detail C-9"},
            "faction":{"name":"Independent"}}
        outsider=resolve_literary_policy("fighter_memory",voice_layers=v2)
        self.assertIsNone(outsider["gang"]["profile"])
        self.assertFalse(outsider["illustrative_examples"])

    def test_examples_illustrative_only_and_only_matching_form(self):
        slag=resolve_literary_policy("fighter_biography",gang="The Slag Eaters")
        self.assertEqual(len(slag["illustrative_examples"]),2)
        self.assertTrue(all("IMPORTED" in e["status"] for e in slag["illustrative_examples"]))
        self.assertIn("non-exhaustive",slag["example_policy"])
        memory=resolve_literary_policy("fighter_memory",gang="The Slag Eaters")
        self.assertEqual(memory["illustrative_examples"],[])
        self.assertEqual(memory["form_rules"]["target_characters"],[350,400])

    def test_character_knowledge_before_audience_and_genre(self):
        value=resolve_literary_policy("fighter_biography",
                     gang="Geothermal Prospect Detail C-9",faction="Genestealer Cults",
                     audience="restricted reader",genre="labour personnel dossier")
        self.assertEqual(value["knowledge_order"][0],"documented_character_knowledge_at_event")
        self.assertEqual(value["narrator_audience"],"restricted reader")
        self.assertIn("redactions",value["gang"]["profile"]["institutional_record"])
        self.assertIn("dossier",value["gang"]["profile"]["document_genres"][0])

    def test_unknown_category_is_safe_general_fallback(self):
        other=resolve_literary_policy("new_category_not_yet_reviewed")
        self.assertTrue(other["unlisted_form"])
        self.assertEqual(other["illustrative_examples"],[])
        self.assertEqual(other["form_rules"],{})

    def test_versioned_owner_decision_requires_scoped_changed_reference(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"config").mkdir()
            (root/"skills/ncce-prose-portability").mkdir(parents=True)
            shutil.copy(ROOT/"config/literary_profiles.v2.json",
                        root/"config/literary_profiles.v2.json")
            (root/"skills/ncce-prose-portability/CHANGELOG.md").write_text("# Changes\\n")
            (root/"skills/ncce-prose-portability/decisions.jsonl").write_text("")
            (root/"scope-ref.md").write_text("Owner approved example: no copied templates.")
            result=record_owner_decision(
                root=root,expected_version="2.1.0",new_version="2.1.1",
                scope="form",decision="A new specifically scoped form rule",
                source="Explicit owner chat correction",changed_files=["scope-ref.md"])
            self.assertEqual(result["new_version"],"2.1.1")
            self.assertEqual(json.loads((root/"config/literary_profiles.v2.json").read_text())["policy_version"],"2.1.1")
            self.assertIn("form", (root/"skills/ncce-prose-portability/CHANGELOG.md").read_text())
            self.assertEqual(len((root/"skills/ncce-prose-portability/decisions.jsonl").read_text().splitlines()),1)
            with self.assertRaises(ValueError):
                record_owner_decision(
                    root=root,expected_version="2.1.0",new_version="2.1.2",
                    scope="form",decision="Unverified",source="User",
                    changed_files=["scope-ref.md"])

    def test_export_is_valid_and_identifies_exact_source_files(self):
        binary,manifest=build_portable_zip()
        self.assertGreater(len(binary),1000)
        self.assertEqual(manifest["packet_version"],"2.1.0")
        with ZipFile(io.BytesIO(binary)) as archive:
            self.assertIn("MANIFEST.json",archive.namelist())
            self.assertIn("skills/ncce-prose-portability/SKILL.md",archive.namelist())
            self.assertIn("config/literary_profiles.v2.json",archive.namelist())
            self.assertEqual(json.loads(archive.read("MANIFEST.json"))["files"],manifest["files"])

    def test_new_fighter_packet_contains_separate_literary_guidance(self):
        store=StoreStub()
        store.add(9,"Garrick Voss","THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]","Genestealer Cults")
        packet=_packet(store,request_for(9,"Garrick Voss"),"new-writer-packet")
        sections={x["section"]:x for x in packet["context"]}
        self.assertIn("voice_layers",sections)
        self.assertIn("literary_policy",sections)
        literary=json.loads(sections["literary_policy"]["text"])
        self.assertEqual(literary["form"],"fighter_memory")
        self.assertEqual(literary["gang"]["name"],"Geothermal Prospect Detail C-9")
        self.assertEqual(literary["form_rules"]["target_characters"],[350,400])
        self.assertEqual(literary["purpose"],"literary_craft_guidance_only")
        self.assertEqual(sections["literary_policy"]["provenance"],"style_guidance")

    def test_sealed_cap_survives_policy_version_update(self):
        meta={"literary_version":"2.9.3","form":"fighter_biography",
              "form_rules":{"hard_max_characters":2450}}
        req={"packet_json":json.dumps({"request":{"form":"fighter_biography"},
            "context":[{"section":"literary_policy","text":json.dumps(meta)}]})}
        self.assertEqual(prospective_biography_length_error(req,"b"*2450),"")
        self.assertIn("2,450",prospective_biography_length_error(req,"b"*2451))

    def test_retroactive_cap_does_not_touch_old_issued_packet(self):
        request={"packet_json":json.dumps({"request":{"form":"fighter_biography"},"context":[]})}
        self.assertEqual(prospective_biography_length_error(request,"a"*3000),"")

    def test_prospective_cap_only_for_new_bio_requests(self):
        meta={"literary_version":"2.1.0","form":"fighter_biography","form_rules":{"hard_max_characters":2300}}
        req={"packet_json":json.dumps({"request":{"form":"fighter_biography"},
               "context":[{"section":"literary_policy","text":json.dumps(meta)}]})}
        error=prospective_biography_length_error(req,"**"+("a"*2300)+"**")
        self.assertIn("2,300",error)
        self.assertEqual(prospective_biography_length_error(req,"a"*2000),"")
        mem={"packet_json":json.dumps({"request":{"form":"fighter_memory"},
               "context":[{"section":"literary_policy","text":json.dumps(meta)}]})}
        self.assertEqual(prospective_biography_length_error(mem,"a"*2800),"")


if __name__=="__main__":
    unittest.main()
