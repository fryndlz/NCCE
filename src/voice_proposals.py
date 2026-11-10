"""Detect and review source-grounded fighter/gang voice suggestions.

The source excerpt comes from player-authored material or an accepted fighter
biography. Topic cues suggest writing directions for editorial review. GM-only
material is excluded from review packets.
Approved overrides are SQLite-backed and participate only in *future* packets.
"""
from __future__ import annotations
import hashlib
from copy import deepcopy
import json
import re
from datetime import datetime, timezone
from voice_layers import load_registry

SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_proposals (
 proposal_key TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('gang','fighter')),
 gang_id TEXT NOT NULL,
 fighter_id INTEGER,
 name TEXT NOT NULL,
 host_name TEXT NOT NULL,
 faction TEXT NOT NULL,
 source_kind TEXT NOT NULL,
 source_hash TEXT NOT NULL,
 source_excerpt TEXT NOT NULL,
 proposed_tags_json TEXT NOT NULL,
 proposed_register TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('awaiting_source','pending','approved','rejected')),
 approved_tags_json TEXT NOT NULL DEFAULT '[]',
 approved_register TEXT NOT NULL DEFAULT '',
 reviewed_hash TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_proposal_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 proposal_key TEXT NOT NULL,
 action TEXT NOT NULL,
 source_hash TEXT NOT NULL,
 details_json TEXT NOT NULL,
 at TEXT NOT NULL
);
"""

# Generic *text evidence* signals, never role- or species-derived psychology.
CUES = {
 "tools_and_repairs": (r"\b(repair|maintain|fitter|maintenance|napraw|mechanic|tool|instrument|regulator|spanner)\w*\b",),
 "survey_and_routes": (r"\b(survey|map|chart|tunnel|route|passage|sounding|galer|wyrobisk|tunel|prospect)\w*\b",),
 "crew_solidarity": (r"\b(crew|kin|brother|family|worker|labourer|rodzin|załog|brat|team)\w*\b",),
 "trade_and_debt": (r"\b(trade|credit|debt|fee|profit|cargo|claim|share|shipment|dług|handel|udział|ładun)\w*\b",),
 "orders_and_checks": (r"\b(order|warrant|permit|procedure|inspection|authority|check|rozkaz|procedur|kontrol|zezwolen|sprawd)\w*\b",),
 "hazards_and_exposure": (r"\b(hazard|injur|exposure|radiation|collapse|toxic|risk|wound|ran|zagroż|promieni|skażen)\w*\b",),
 "tracking_and_watch": (r"\b(watch|track|scout|observe|patrol|trace|trop|zwiad|obserw|wart)\w*\b",),
 "names_and_records": (r"\b(personnel file|personnel record|registration|registry|clerical error|collective designation)\b",),
}
SKIP_SECTIONS = (r"\bTajna Prawda\b", r"\bOnly for (?:the )?(?:GM|Arbiter)\b",
                 r"\bGM[- ]ONLY\b", r"\bTYLKO DLA OCZU ARBITRA\b", r"\bsecret for the arbiter\b")
LEGACY_EXCERPT_PREFIX = "Evidence excerpt (not an inferred personality): "
VOICE_SUGGESTIONS = {
 "tools_and_repairs": "When relevant, name the part, symptom, or check the subject would recognize.",
 "survey_and_routes": "Describe routes through landmarks and practical choices about where to go next.",
 "crew_solidarity": "When crew ties matter, show them through who gets warned, helped, or trusted.",
 "trade_and_debt": "When a bargain matters, show what is owed, who owes it, and what changes the price.",
 "orders_and_checks": "When procedure matters, distinguish what was ordered from what the subject actually checked.",
 "hazards_and_exposure": "Describe danger through the signs the subject could notice and the precautions they could take.",
 "tracking_and_watch": "Separate what the subject saw from what they inferred about someone’s movements.",
 "names_and_records": "Where paperwork shapes identity, distinguish the name or label on the record from what people actually call the subject.",
}
RETRY_FOCUSES = (
 "Build the voice around a concrete detail the subject could notice in this passage.",
 "Use vocabulary the subject would know from the work or circumstances shown here.",
 "Focus on what the subject could say firsthand and where their knowledge stops.",
)


def suggested_register(tags):
 return " ".join(VOICE_SUGGESTIONS[tag] for tag in tags if tag in VOICE_SUGGESTIONS)


def editable_register(value, tags):
 if value.startswith(LEGACY_EXCERPT_PREFIX):
  return suggested_register(tags)
 return value


def now():
 return datetime.now(timezone.utc).isoformat()


def safe_source(value):
 text = str(value or "").strip()
 for marker in SKIP_SECTIONS:
  found = re.search(marker, text, flags=re.I)
  if found: text = text[:found.start()]
 return text.strip()


def source_hash(text):
 return hashlib.sha256(text.encode("utf-8")).hexdigest()


def excerpt_and_tags(text, offset=0):
 # Short, exact readable evidence span, rather than invented psychological summary.
 paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n",text[:20000]) if p.strip()]
 paragraphs = [p for p in paragraphs if not p.startswith(("+++","[","**")) and len(p) >= 35] or paragraphs
 if not paragraphs:return "",[]
 ranked = []
 for i,p in enumerate(paragraphs):
  cues = [key for key,patterns in CUES.items() if any(re.search(pat,p,re.I) for pat in patterns)]
  ranked.append((len(cues), min(len(p),350), -i, p, cues))
 _,_,_,winner,tags = sorted(ranked,reverse=True)[offset % len(ranked)]
 return winner[:340].rstrip(),tags[:5]


def ensure(store):
 # No schema-18 change; this feature owns its private, additive tables.
 store.db.executescript(SCHEMA)


def _has_profile(data, kind, host, name):
 if kind == "gang":
  return host in data["gangs"] and data["gangs"][host].get("review_status","approved") == "approved"
 return (host+"::"+name) in data["individuals"]


def _accepted_bio(store, fid):
 from narrative_context import prose, usable
 for row in store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type='fighter_biography' AND scope_key=? AND active=1 ORDER BY generated_at DESC LIMIT 1",(str(fid),)):
  try:
   document=json.loads(row[0])
   if usable(document):
    return safe_source(document.get("external_markdown") or prose(document))
  except (ValueError, TypeError):pass
 return ""


def _current_source(store, row):
 """Read the current source before reviewing or applying a proposal."""
 if row["kind"]=="gang":
  g=store.db.execute("SELECT backstory,backstory_source,active FROM gangs WHERE gang_id=?",
   (row["gang_id"],)).fetchone()
  if not g or not g["active"]:return "", ""
  text=safe_source(g["backstory"] if g["backstory_source"]=="player-authored / campaign Sheet" else "")
  source_kind="player_authored_gang_backstory"
 else:
  f=store.db.execute("SELECT mechanics_json,listed_in_source FROM fighters WHERE id=? AND gang_id=?",
   (row["fighter_id"],row["gang_id"])).fetchone()
  if not f or not f["listed_in_source"]:return "", ""
  try: raw=json.loads(f["mechanics_json"] or "{}")
  except (ValueError,TypeError):raw={}
  text=safe_source(raw.get("Backstory") or "")
  source_kind="player_authored_fighter_backstory" if text else "accepted_fighter_biography"
  if not text:text=_accepted_bio(store,row["fighter_id"])
 return text, source_hash(source_kind+"\n"+text) if text else ""


def _current_fingerprint(store, row):
 return _current_source(store,row)[1]


def _put(store,key,kind,gid,fid,name,host,faction,source,source_kind):
 source=safe_source(source)
 h=source_hash(source_kind+"\n"+source) if source else ""
 quote,tags=excerpt_and_tags(source)
 status="pending" if quote else "awaiting_source"
 # Explicit citation gives reviewers exactly the authored source, not an invented event.
 hint=suggested_register(tags)
 old=store.db.execute("SELECT source_hash,status FROM voice_proposals WHERE proposal_key=?",(key,)).fetchone()
 if old and old["source_hash"]==h:
  store.db.execute("UPDATE voice_proposals SET name=?,host_name=?,faction=?,source_kind=? WHERE proposal_key=?",
   (name,host,faction,source_kind,key))
  return False
 if old:
  store.db.execute("""UPDATE voice_proposals SET name=?,host_name=?,faction=?,source_kind=?,
   source_hash=?,source_excerpt=?,proposed_tags_json=?,proposed_register=?,status=?,
   approved_tags_json='[]',approved_register='',reviewed_hash='',updated_at=? WHERE proposal_key=?""",
   (name,host,faction,source_kind,h,quote,json.dumps(tags),hint,status,now(),key))
  action="source_changed_review_revoked"
 else:
  store.db.execute("""INSERT INTO voice_proposals
   (proposal_key,kind,gang_id,fighter_id,name,host_name,faction,source_kind,source_hash,source_excerpt,
    proposed_tags_json,proposed_register,status,updated_at)
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
   (key,kind,gid,fid,name,host,faction,source_kind,h,quote,json.dumps(tags),hint,status,now()))
  action="detected"
 store.db.execute("""INSERT INTO voice_proposal_audit(proposal_key,action,source_hash,details_json,at)
  VALUES(?,?,?,?,?)""",(key,action,h,json.dumps({"source_kind":source_kind,"excerpt":quote},ensure_ascii=False),now()))
 return True


def scan(store):
 """Idempotently discover missing profiles after a successfully imported roster."""
 data=load_registry()
 ensure(store)
 with store._lock,store.db:
  changed=0
  for g in store.db.execute("SELECT gang_id,name,gang_type,backstory,backstory_source FROM gangs WHERE active=1").fetchall():
   gid,host,faction=g["gang_id"],g["name"],g["gang_type"] or ""
   canonical=data["aliases"].get(host,host)
   if not _has_profile(data,"gang",canonical,""):
    source=g["backstory"] if g["backstory_source"]=="player-authored / campaign Sheet" else ""
    changed+=_put(store,"gang:"+gid,"gang",gid,None,host,host,faction,source,"player_authored_gang_backstory")
   for f in store.db.execute("SELECT id,name,mechanics_json FROM fighters WHERE gang_id=? AND listed_in_source=1",(gid,)).fetchall():
    name=f["name"]
    if _has_profile(data,"fighter",canonical,name) or (canonical+"::"+name) in data["attachments"]:
     continue
    try:raw=json.loads(f["mechanics_json"] or "{}")
    except (ValueError,TypeError):raw={}
    src=safe_source(raw.get("Backstory") or "")
    kind="player_authored_fighter_backstory" if src else "accepted_fighter_biography"
    if not src:src=_accepted_bio(store,f["id"])
    changed+=_put(store,"fighter:"+str(f["id"]),"fighter",gid,f["id"],name,host,faction,src,kind)
  return changed


def proposals(store, status=None):
 query="SELECT * FROM voice_proposals"
 params=()
 if status and status!="all":
  if status not in ("pending","awaiting_source","approved","rejected"):
   raise ValueError("Invalid status filter")
  query+=" WHERE status=?";params=(status,)
 rows=[]
 for row in store.db.execute(query+" ORDER BY kind,host_name,name",params):
  item=dict(row)
  for key in ("proposed_tags_json","approved_tags_json"):
   item[key[:-5]]=json.loads(item.pop(key))
  item["proposed_register"]=editable_register(item["proposed_register"],item["proposed_tags"])
  item["source_url"]=("https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit"
   if item["source_kind"].startswith("player_authored") else
   "https://docs.google.com/spreadsheets/d/1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas/edit")
  item["source_locator"]=(item["host_name"]+" / "+("GANG BACKSTORY" if item["kind"]=="gang" else item["name"]+" / Backstory"))
  rows.append(item)
 return rows


def review(store,key,expected_hash,decision,tags=None,register=None):
 if decision not in ("approved","rejected","regenerate"):raise ValueError("Invalid review decision")
 if not isinstance(key,str) or len(key)>128:raise ValueError("Invalid proposal key")
 if not isinstance(expected_hash,str):raise ValueError("Source hash required")
 with store._lock,store.db:
  row=store.db.execute("SELECT * FROM voice_proposals WHERE proposal_key=?",(key,)).fetchone()
  if not row:raise ValueError("Unknown voice proposal")
  if row["source_hash"]!=expected_hash:raise ValueError("Source changed; refresh review")
  source,current_hash=_current_source(store,row)
  if current_hash!=expected_hash:raise ValueError("Authored source changed since discovery; refresh sync and review")
  if not source:raise ValueError("No authored source to review")
  if decision=="regenerate":
   if row["status"]!="rejected":raise ValueError("Only rejected proposals can be regenerated")
   attempts=store.db.execute("SELECT count(*) FROM voice_proposal_audit WHERE proposal_key=? AND source_hash=? AND action='regenerated'",
                             (key,expected_hash)).fetchone()[0]
   quote,tags=excerpt_and_tags(source,attempts)
   register=" ".join(filter(None,(suggested_register(tags),RETRY_FOCUSES[attempts % len(RETRY_FOCUSES)])))
   stamp=now()
   store.db.execute("""UPDATE voice_proposals SET source_excerpt=?,proposed_tags_json=?,proposed_register=?,
    status='pending',updated_at=? WHERE proposal_key=?""",(quote,json.dumps(tags),register,stamp,key))
   store.db.execute("INSERT INTO voice_proposal_audit(proposal_key,action,source_hash,details_json,at) VALUES(?,?,?,?,?)",
    (key,"regenerated",expected_hash,json.dumps({"attempt":attempts+1,"excerpt":quote,"tags":tags,"register":register},ensure_ascii=False),stamp))
   return {"proposal_key":key,"status":"pending","tags":tags}
  if decision=="rejected" and row["status"]=="rejected":raise ValueError("This proposal is already rejected")
  if row["status"] not in ("pending","approved","rejected"):raise ValueError("No authored source to approve")
  if decision=="approved":
   if tags is None:tags=json.loads(row["proposed_tags_json"])
   if register is None:register=editable_register(row["proposed_register"],json.loads(row["proposed_tags_json"]))
   if isinstance(register,str) and (register.strip().startswith(LEGACY_EXCERPT_PREFIX) or register.strip()==row["source_excerpt"]):
    raise ValueError("Enter voice guidance distinct from the source excerpt")
   if not isinstance(tags,list) or len(tags)>12 or any(not isinstance(x,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,55}",x) for x in tags):
    raise ValueError("Invalid proposed tags")
   if not isinstance(register,str) or not register.strip() or len(register)>1200:
    raise ValueError("Nonempty editorial register (max 1200 chars) required")
   tags=list(dict.fromkeys(tags))
  else:tags=[];register=""
  store.db.execute("""UPDATE voice_proposals SET status=?,approved_tags_json=?,approved_register=?,
   reviewed_hash=?,updated_at=? WHERE proposal_key=?""",
   (decision,json.dumps(tags),register,expected_hash if decision=="approved" else "",now(),key))
  details={"tags":tags,"register":register}
  if decision=="rejected":
   reviewed_tags=json.loads(row["approved_tags_json"] if row["status"]=="approved" else row["proposed_tags_json"])
   reviewed_register=row["approved_register"] if row["status"]=="approved" else editable_register(row["proposed_register"],reviewed_tags)
   details={"excerpt":row["source_excerpt"],"tags":reviewed_tags,"register":reviewed_register}
  store.db.execute("INSERT INTO voice_proposal_audit(proposal_key,action,source_hash,details_json,at) VALUES(?,?,?,?,?)",
   (key,decision,expected_hash,json.dumps(details,ensure_ascii=False),now()))
  return {"proposal_key":key,"status":decision,"tags":tags}


def apply_approved(store,layers,gang_id,fighter_id):
 """Only reviewed exact-source profiles add style to a *future* writer packet."""
 # Safe for tests, old read-only DBs, and a first launch before migration.
 if not store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='voice_proposals'").fetchone():
  return layers
 # Called during exchange packet creation with already-prepared DB.
 for key,target in (("gang:"+str(gang_id),"gang"),("fighter:"+str(fighter_id),"individual")):
  row=store.db.execute("SELECT * FROM voice_proposals WHERE proposal_key=?",(key,)).fetchone()
  if not row or row["status"]!="approved" or row["reviewed_hash"]!=row["source_hash"]:continue
  if _current_fingerprint(store,row)!=row["source_hash"]:continue
  if target=="gang" and layers["gang"].get("host_gang"):continue  # Outsider never inherits host.
  tags=json.loads(row["approved_tags_json"])
  if target=="gang" and layers["gang"].get("provenance") not in ("unknown","recorded_affiliation"):continue
  if target=="individual" and layers["individual"].get("tags"):continue  # Accepted static profile wins.
  # The excluded Patrol has no faction styles before approval.
  # On approval restore its generic faction frame, never a sibling precinct.
  if target=="gang" and layers["gang"].get("review_status")=="excluded_until_onboarded":
   faction_name=layers["faction"].get("name","")
   if faction_name:
    faction_profile=load_registry()["factions"].get(faction_name)
    if faction_profile and faction_profile.get("review_status","approved")=="approved":
     layers["faction"].update(deepcopy(faction_profile))
  section=layers[target]
  section.update(tags=tags,register=row["approved_register"],
     provenance="owner_approved_source_grounded_proposal",
     source=row["source_kind"]+"#sha256:"+row["source_hash"],
     review_status="approved")
 return layers
