"""Discovery, approval, source change and future-packet boundaries."""
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from voice_layers import build_voice_layers
from voice_proposals import scan, proposals, review, apply_approved, ensure


class FakeStore:
 def __init__(self):
  self.db=sqlite3.connect(":memory:")
  self.db.row_factory=sqlite3.Row
  self._lock=threading.RLock()
  self.db.executescript("""
   CREATE TABLE gangs (gang_id TEXT PRIMARY KEY,name TEXT,gang_type TEXT,
    active INTEGER,backstory TEXT,backstory_source TEXT);
   CREATE TABLE fighters (id INTEGER PRIMARY KEY,name TEXT,gang_id TEXT,listed_in_source INTEGER,
    mechanics_json TEXT);
   CREATE TABLE story_artifacts (scope_type TEXT,scope_key TEXT,active INTEGER,generated_at TEXT,
    document_json TEXT);
  """)
  ensure(self)
 def gang(self,gid,name,faction,backstory=""):
  self.db.execute("INSERT INTO gangs VALUES (?,?,?,1,?,?)",
   (gid,name,faction,backstory,"player-authored / campaign Sheet" if backstory else "not-provided"))
 def fighter(self,fid,gid,name,bio=""):
  self.db.execute("INSERT INTO fighters VALUES (?,?,?,?,?)",
   (fid,name,gid,1,json.dumps({"Backstory":bio})))
 def edit_fighter_bio(self,fid,bio):
  self.db.execute("UPDATE fighters SET mechanics_json=? WHERE id=?",(json.dumps({"Backstory":bio}),fid))
 def close(self):self.db.close()


class VoiceProposalTests(unittest.TestCase):
 def setUp(self):
  self.store=FakeStore()
 def tearDown(self):
  self.store.close()

 def test_new_fighter_detected_then_owner_approved(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(42,"orlock","New Driver","He checks each freight load twice. The crew relies on his accurate cargo records.")
  self.assertEqual(scan(self.store),1)
  row=proposals(self.store,"pending")[0]
  self.assertEqual(row["kind"],"fighter")
  self.assertIn("cargo",row["source_excerpt"])
  self.assertIn("trade_and_debt",row["proposed_tags"])
  neutral=build_voice_layers({"gang":"The Slag Eaters","subject_name":"New Driver"})
  self.assertEqual(neutral["individual"]["tags"],[])
  approved=review(self.store,row["proposal_key"],row["source_hash"],"approved",
                  ["trade_and_debt"],"Precise about freight loading and signed cargo tallies.")
  self.assertEqual(approved["status"],"approved")
  current=apply_approved(self.store,neutral,"orlock",42)
  self.assertEqual(current["individual"]["tags"],["trade_and_debt"])
  self.assertEqual(current["individual"]["provenance"],"owner_approved_source_grounded_proposal")
  self.assertEqual(scan(self.store),0)
  self.assertEqual(len(proposals(self.store,"approved")),1)

 def test_biography_revision_revokes_approval(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(1,"orlock","New Pilot","He plans each route and checks the tunnel charts before setting off.")
  scan(self.store)
  p=proposals(self.store,"pending")[0]
  review(self.store,p["proposal_key"],p["source_hash"],"approved",["survey_and_routes"],"Studies routes.")
  self.store.edit_fighter_bio(1,"Now they keep an engine maintenance register under the seat.")
  self.assertEqual(scan(self.store),1)
  changed=proposals(self.store,"pending")[0]
  self.assertNotEqual(changed["source_hash"],p["source_hash"])
  self.assertEqual(changed["approved_tags"],[])
  baseline=build_voice_layers({"gang":"The Slag Eaters","subject_name":"New Pilot"})
  self.assertEqual(apply_approved(self.store,baseline,"orlock",1)["individual"]["tags"],[])
  with self.assertRaisesRegex(ValueError,"Source changed"):
   review(self.store,p["proposal_key"],p["source_hash"],"approved",["survey_and_routes"],"Old voice")

 def test_pending_source_modified_without_rescan_is_rejected(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(12,"orlock","Clerk","He keeps a careful record of cargo fees and shipments.")
  scan(self.store)
  p=proposals(self.store,"pending")[0]
  self.store.edit_fighter_bio(12,"New wording: the clerk now repairs broken equipment.")
  with self.assertRaisesRegex(ValueError,"Authored source changed"):
   review(self.store,p["proposal_key"],p["source_hash"],"approved",
          ["trade_and_debt"],"Based on stale fees.")

 def test_changed_source_cannot_keep_active_profile_before_rescan(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(13,"orlock","Watcher","He maps tunnels and watches for hidden routes.")
  scan(self.store)
  p=proposals(self.store,"pending")[0]
  review(self.store,p["proposal_key"],p["source_hash"],"approved",
         ["survey_and_routes"],"Route-conscious watcher.")
  v=build_voice_layers({"gang":"The Slag Eaters","subject_name":"Watcher"})
  self.assertEqual(apply_approved(self.store,v,"orlock",13)["individual"]["tags"],["survey_and_routes"])
  self.store.edit_fighter_bio(13,"He repairs machinery and checks each damaged component.")
  fresh=build_voice_layers({"gang":"The Slag Eaters","subject_name":"Watcher"})
  self.assertEqual(apply_approved(self.store,fresh,"orlock",13)["individual"]["tags"],[])

 def test_new_patrol_gang_stays_neutral_until_approved(self):
  text="The precinct's checks focus on transit warrants and the handling of confiscated cargo."
  self.store.gang("patrol","Patrol do spraw alkoholu i broni","Palanite Enforcers",text)
  scan(self.store)
  p=next(x for x in proposals(self.store) if x["kind"]=="gang")
  self.assertEqual(p["status"],"pending")
  neutral=build_voice_layers({"gang":"Patrol do spraw alkoholu i broni",
                              "affiliation":"Palanite Enforcers","subject_name":"Unknown"})
  self.assertEqual(neutral["gang"]["tags"],[])
  self.assertEqual(apply_approved(self.store,neutral,"patrol",999)["gang"]["tags"],[])
  review(self.store,p["proposal_key"],p["source_hash"],"approved",["orders_and_checks"],
         "Clipped checkpoint speech, attentive to transit warrants and confiscated cargo.")
  updated=build_voice_layers({"gang":"Patrol do spraw alkoholu i broni",
                              "affiliation":"Palanite Enforcers","subject_name":"Unknown"})
  approved=apply_approved(self.store,updated,"patrol",999)
  self.assertEqual(approved["gang"]["tags"],["orders_and_checks"])
  self.assertNotIn("rigid_discipline",approved["gang"]["tags"])

 def test_missing_source_cannot_be_approved(self):
  self.store.gang("new","Fresh Gang","House Orlock")
  scan(self.store)
  p=proposals(self.store,"awaiting_source")[0]
  self.assertFalse(p["source_hash"])
  with self.assertRaisesRegex(ValueError,"No authored source"):
   review(self.store,p["proposal_key"],p["source_hash"],"approved",["crew_solidarity"],"Crew")

 def test_gm_only_section_not_exposed(self):
  story="Public precinct sends officers to inspect transit permits and maintain order.\n\nTajna Prawda (Tylko dla oczu Arbitra)\nSecret mission classified for command."
  self.store.gang("new","Another Precinct","Palanite Enforcers",story)
  scan(self.store)
  p=proposals(self.store,"pending")[0]
  self.assertNotIn("Secret mission",json.dumps(p))
  self.assertIn("Public precinct",p["source_excerpt"])

 def test_existing_canon_fighter_never_reproposed(self):
  self.store.gang("c9","THE C-NINE +++ [GEOTHERMAL PROSPECT DETAIL C-9]","Genestealer Cults")
  self.store.fighter(7,"c9","Garrick Voss","Garrick Voss keeps the official survey charts.")
  scan(self.store)
  self.assertFalse([x for x in proposals(self.store) if x["kind"]=="fighter"])

 def test_accepted_biography_used_when_no_sheet_backstory(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(10,"orlock","New Ganger")
  doc={"writer_status":"ready","external_request_id":"external-id","external_markdown":
       "New Ganger inspects the cargo lashing before every trip, using the same careful tool checks."}
  self.store.db.execute("INSERT INTO story_artifacts VALUES (?,?,?,?,?)",
    ("fighter_biography","10",1,"2026-11-09",json.dumps(doc)))
  self.assertEqual(scan(self.store),1)
  p=proposals(self.store,"pending")[0]
  self.assertEqual(p["source_kind"],"accepted_fighter_biography")
  self.assertIn("cargo",p["source_excerpt"])

 def test_explicit_rejection_preserved_until_source_changes(self):
  self.store.gang("orlock","The Slag Eaters","House Orlock")
  self.store.fighter(10,"orlock","Second Driver","He checks the damaged freight rig before every shift.")
  scan(self.store)
  p=proposals(self.store,"pending")[0]
  review(self.store,p["proposal_key"],p["source_hash"],"rejected")
  self.assertEqual(scan(self.store),0)
  self.assertEqual(proposals(self.store,"rejected")[0]["status"],"rejected")

 def test_external_attachment_does_not_inherit_host_overlay(self):
  self.store.gang("new","Patrol do spraw alkoholu i broni","Palanite Enforcers",
                  "Officers check warrants and road cargo before confiscation.")
  scan(self.store)
  p=next(x for x in proposals(self.store) if x["kind"]=="gang")
  review(self.store,p["proposal_key"],p["source_hash"],"approved",["orders_and_checks"],"Check warrants.")
  voice=build_voice_layers({"gang":"Ethernetans 2.0","affiliation":"House Van Saar",
                            "subject_name":"Dredd 2D"})
  self.assertIn("sealed_household_orders",voice["gang"]["tags"])
  self.assertNotIn("orders_and_checks",apply_approved(self.store,voice,"new",77)["gang"]["tags"])


if __name__=="__main__":
 unittest.main()
