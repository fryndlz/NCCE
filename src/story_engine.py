"""Event-driven story layer. Mechanical records are never rewritten.

Evidence, salience and persistence are local deterministic logic; prose is drafted
by llm_writer when configured. Every interpretation keeps separate evidence and
versioned source links.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

import story_prose as prose
import writing_director as director
import world_streams
import llm_writer

VERSION = "0.8.2"
GENERATION = "story-0.8.2"
REFLECTION_THRESHOLD = 12.0
RECENCY_HALF_LIFE_DAYS = 14.0

# Importance is narrative salience on a documented 0–10 scale, not psychological certainty.
RULES = {
    "baseline": (4, "Known at baseline", ["identity"]),
    "advancement": (7, "Advancement recorded", ["advancement", "growth"]),
    "effect": (7, "Condition recorded", ["injury"]),
    "status": (6, "Status recorded", ["status"]),
    "fighter_xp_changed": (4, "Experience changed", ["growth", "experience"]),
    "fighter_kills_changed": (7, "Combat record changed", ["violence", "kills"]),
    "fighter_advancement_changed": (7, "Advancement recorded", ["advancement", "growth"]),
    "fighter_skills_changed": (7, "Skills changed", ["skill", "growth"]),
    "fighter_effects_changed": (7, "Condition changed", ["injury"]),
    "fighter_status_changed": (6, "Status changed", ["status"]),
    "fighter_weapons_changed": (6, "Weapons changed", ["equipment", "weapon"]),
    "fighter_wargear_changed": (5, "Wargear changed", ["equipment"]),
    "fighter_stat_changed": (6, "Characteristic changed", ["growth"]),
    "fighter_recruited": (6, "Joined the roster", ["belonging", "recruitment"]),
    "fighter_unlisted": (3, "No longer listed in source", ["roster"]),
    "gang_battle_outcome": (6, "Gang battle outcome", ["battle", "outcome"]),
    "gangmate_loss": (9, "A gangmate was lost", ["grief", "belonging"]),
    "gangmate_captured": (8, "A gangmate was captured", ["captivity", "belonging"]),
    "territory_holder_changed": (6, "Territory changed hands", ["territory", "outcome"]),
    "combat_record": (6, "Combat record at baseline", ["violence", "kills"]),
    "gang_reputation_changed": (6, "Gang reputation changed", ["reputation", "belonging"]),
    "gang_alignment_changed": (8, "Gang allegiance changed", ["allegiance", "belonging"]),
}

LABELS = {
    "critical": "Critical injury", "injury": "Living with injury", "recovery": "Recovering",
    "return": "Back on duty", "captivity": "Captivity", "grief": "Loss", "growth": "Progress",
    "advancement": "Advancement", "skill": "A new skill", "promotion": "New responsibility",
    "equipment": "Equipment", "weapon": "A changed loadout", "victory": "Victory",
    "defeat": "Defeat", "battle": "The gang's last battle", "territory": "Ground held and lost",
    "kills": "The cost of violence", "belonging": "The gang", "identity": "A place in the gang",
    "humiliation": "Humiliation", "grudge": "A grudge", "scars": "Scars", "reflection": "Looking back",
    "roster": "An uncertain place", "retirement": "Leaving the line", "status": "Current condition",
    "reputation": "The gang's name", "allegiance": "Allegiance",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def normal(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip().casefold())


def display(value):
    if value in (None, ""):
        return "None recorded"
    if isinstance(value, (list, dict)):
        return "; ".join(f"{k}: {display(v)}" for k, v in value.items()) if isinstance(value, dict) else ", ".join(map(str, value))
    return str(value)


def event_evidence(event):
    p = event.get("payload") or {}
    et = event.get("event_type", "")
    if et in ("gangmate_loss", "gangmate_captured"):
        return [f"{display(p.get('subject_name'))}: {display(p.get('after') or p.get('status'))}", "Shared gang news; personal witnessing is not recorded."]
    if p.get("field") and "before" in p:
        label = {"XP": "Experience", "Cl": "Cool", "Wil": "Willpower", "Class": "Role", "Type": "Fighter type"}.get(p["field"], p["field"])
        return [f"{label}: {display(p.get('before'))} → {display(p.get('after'))}"]
    if et in ("battle_result", "gang_battle_outcome"):
        facts = [f"{display(p.get('attacker'))} vs {display(p.get('defender'))}",
                 f"Scenario: {display(p.get('scenario'))}", f"Winner: {display(p.get('winner'))}"]
        if p.get("territory"):
            facts.append(f"Territory: {p['territory']}")
        facts.append("Gang outcome; individual attendance is not recorded.")
        return facts
    if et == "territory_holder_changed":
        before=(p.get('before_state') or {}).get('Gang') or p.get('before_owner')
        after=(p.get('after_state') or {}).get('Gang') or p.get('after_owner')
        return [f"{display(p.get('territory'))}: {display(before)} → {display(after)}"]
    if et.startswith('territory_'):
        facts=[f"Territory: {display(p.get('territory'))}"]
        facts.extend(f"{field}: {display(delta.get('before'))} → {display(delta.get('after'))}" for field,delta in (p.get('changes') or {}).items())
        if et=='territory_unlisted':facts.append('Absent from the new source return; destruction or abandonment is not established.')
        return facts
    if et in ("gangmate_loss", "gangmate_captured"):
        return [f"{display(p.get('subject_name'))}: {display(p.get('after') or p.get('status'))}", "Shared gang news; personal witnessing is not recorded."]
    if p.get("detail"):
        prefix = "Advancement recorded: " if et == "advancement" else "Recorded condition: " if et == "effect" else "Status recorded: " if et == "status" else ""
        return [prefix + p["detail"]]
    if et == "fighter_unlisted":
        return ["Present in the previous Sheet snapshot; absent in the next. This does not establish death or retirement."]
    if et == "fighter_recruited":
        return ["Fighter appears in the roster in a later snapshot. Exact recruitment date is not supplied."]
    return [f"{k.replace('_', ' ').capitalize()}: {display(v)}" for k, v in p.items() if k not in {"state", "last_recorded_state", "source_row", "battle_key", "batch"}][:6]


def classify(event_type, payload):
    importance, title, tags = RULES.get(event_type, (4, event_type.replace("_", " ").capitalize(), ["campaign"]))
    tags = list(tags)
    after = normal(payload.get("after", payload.get("detail", "")))
    if "critical injury" in after:
        importance, title = 9, "Critical injury recorded"
        tags = ["critical", "injury"] + tags
    elif any(w in after for w in ("injur", "hobbled", "enfeebled", "deafened", "wound")):
        tags = ["injury"] + tags
    for word, tag in (("recovery", "recovery"), ("convalescence", "recovery"), ("captur", "captivity"),
                      ("humiliat", "humiliation"), ("enmity", "grudge"), ("scar", "scars"), ("retired", "retirement")):
        if word in after:
            tags.insert(0, tag)
    if event_type in ("status", "fighter_status_changed"):
        if after in ("killed", "dead"):
            importance, title, tags = 10, "Death recorded", ["death"]
        elif after == "active" and payload.get("before"):
            title, tags = "Returned to active duty", ["return", "recovery"]
    if event_type == "fighter_stat_changed" and payload.get("field") in ("Class", "Type"):
        importance, title, tags = 8, "Role changed", ["promotion", "growth", "responsibility"]
    if event_type == "fighter_stat_changed" and payload.get("field") == "Cost":
        importance, title, tags = 2, "Roster value changed", ["roster"]
    if event_type == "fighter_xp_changed":
        before, after_value = payload.get("before"), payload.get("after")
        if isinstance(before, (int, float)) and isinstance(after_value, (int, float)) and after_value < before:
            title = "Experience balance decreased"
    return float(importance), title, list(dict.fromkeys(tags))


def _all_events(store):
    events = []
    subjects = defaultdict(list)
    for row in store.db.execute("SELECT es.event_id,e.*,es.role FROM event_subjects es JOIN entities e USING(entity_id)"):
        item = dict(row)
        subjects[item.pop("event_id")].append(item)
    for row in store.db.execute("SELECT * FROM campaign_events ORDER BY coalesce(occurred_at,observed_at),created_at,event_id"):
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        item["subjects"] = subjects[item["event_id"]]
        events.append(item)
    return events


def _authored(row):
    source = normal(row.get("backstory_source"))
    return bool(row.get("backstory")) and ("authored" in source or "c-nine story" in source or "canon" in source) and "mechanic" not in source


def _retained_writer_content(store,fighter_id,memory_key,writer_status):
    if writer_status.get('status') not in {'pending','error','unconfigured'}:
        return None
    previous=store.db.execute("""SELECT content,content_runs_json FROM story_memories
        WHERE fighter_id=? AND memory_key=? AND writer_status IN ('ready','stale') AND content!=''
        ORDER BY created_at DESC LIMIT 1""",(fighter_id,memory_key)).fetchone()
    if not previous:
        return None
    try:runs=json.loads(previous['content_runs_json'] or '[]')
    except (ValueError,TypeError):runs=[]
    return previous['content'],runs,{'status':'stale','message':'Earlier draft retained; this limited run did not replace it.'}


def _memory(store, fighter, gang, key, et, payload, event=None, context=None, baseline=False, evidence=None, prior=()):
    event = event or {}
    importance, title, tags = classify(et, payload)
    context = context or {}
    if et == "gang_battle_outcome":
        victory = payload.get("winner") == gang.get("name")
        tags.insert(0, "victory" if victory else "defeat" if payload.get("winner") else "battle")
        title = "Gang victory recorded" if victory else "Gang defeat recorded" if payload.get("winner") else "Gang engagement recorded"
    packet=director.identity_context(fighter,gang,prose.voice_profile(fighter,gang))
    written,writer_status=llm_writer.write_memory(store,fighter,gang,title,evidence or event_evidence({'event_type':et,'payload':payload}),packet,prior)
    content='\n\n'.join(llm_writer.paragraph_text(p) for p in written)
    content_runs=[llm_writer.paragraph_runs(p) for p in written]
    if not content:
        retained=_retained_writer_content(store,fighter['id'],key,writer_status)
        if retained: content,content_runs,writer_status=retained
    return {"memory_key": key, "memory_type": "observation", "title": title, "content": content,
            "importance": importance, "occurred_at": event.get("occurred_at"), "observed_at": event.get("observed_at"),
            "tags": list(dict.fromkeys(tags)), "evidence": evidence or event_evidence({"event_type": et, "payload": payload}),
            "source_event_ids": [event["event_id"]] if event.get("event_id") else [], "source_observation_ids": [],
            "source_id": event.get("source_id") or "baseline:snapshot-0001", "provenance_class": "inference",
            "writer_context":packet,"writer_content_runs":content_runs,"writer_status":writer_status.get('status','pending'),
            "confidence": 0.65, "baseline": baseline, "batch": str(event.get("to_snapshot_id") or ("baseline" if baseline else event.get("observed_at") or key))}


def _memory_id(fighter_id, memory):
    semantic = {k:memory.get(k) for k in ("memory_key","memory_type","title","content","writer_content_runs","importance","occurred_at","observed_at","tags","evidence","source_event_ids","source_observation_ids","source_id","baseline","writer_context")}
    return digest([fighter_id, GENERATION, semantic])[:32]


def _save_memory(store, fighter_id, memory, generated_at):
    memory_id = _memory_id(fighter_id, memory)
    memory["id"] = memory["memory_id"] = memory_id
    values = (memory_id, fighter_id, memory["memory_key"], memory["memory_type"], memory["title"], memory["content"], memory["importance"],
              memory.get("occurred_at"), memory.get("observed_at"), generated_at, encode(memory["tags"]), encode(memory["evidence"]),
              encode(memory["source_event_ids"]), encode(memory["source_observation_ids"]), memory["source_id"], "inference", memory["confidence"], int(memory["baseline"]), GENERATION, encode(memory.get('writer_context',{})),memory.get('writer_status','pending'),encode(memory.get('writer_content_runs',[])))
    store.db.execute("""INSERT INTO story_memories(memory_id,fighter_id,memory_key,memory_type,title,content,importance,occurred_at,observed_at,created_at,
        tags_json,evidence_json,source_event_ids_json,source_observation_ids_json,source_id,provenance_class,confidence,baseline,generation_version,writer_context_json,writer_status,content_runs_json,active)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(memory_id) DO UPDATE SET active=1,writer_status=excluded.writer_status,content_runs_json=excluded.content_runs_json""", values)
    for event_id in memory["source_event_ids"]:
        _link(store, "story_memory", memory_id, event_id=event_id)
    _link(store, "story_memory", memory_id, source_id=memory["source_id"])
    for source_id in memory.get("context_source_ids", []):
        if store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id=?",(source_id,)).fetchone():
            _link(store,"story_memory",memory_id,source_id=source_id)
    return memory


def _link(store, artifact_type, key, event_id=None, source_id=None):
    # Avoid nested transaction context managers committing part of a regeneration.
    store.db.execute("""INSERT INTO narrative_evidence(artifact_type,artifact_key,event_id,source_id,evidence_role,created_at)
        SELECT ?,?,?,?,'generation_source',? WHERE NOT EXISTS(SELECT 1 FROM narrative_evidence WHERE artifact_type=? AND artifact_key=?
        AND ifnull(event_id,'')=ifnull(?,'') AND ifnull(source_id,'')=ifnull(?,''))""",
        (artifact_type,key,event_id,source_id,now(),artifact_type,key,event_id,source_id))


def _artifact(store, scope, key, document, input_hash, generated_at):
    document = dict(document)
    document.update(provenance_class="inference", generated_at=generated_at, generation_version=GENERATION)
    prior=store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type=? AND scope_key=? AND active=1 ORDER BY generated_at DESC LIMIT 1",(scope,str(key))).fetchone()
    if prior:
        old=json.loads(prior[0])
        if old.get('writer_status') in ('ready','stale'):
            context=dict(document.get('writer_context') or {})
            context.pop('prior_entry',None)
            context['continuity_reference']={'earlier_document_exists':True,
                'source_event_ids':old.get('source_event_ids',[]),
                'instruction':'Earlier generated prose is not evidence; use only facts in this packet.'}
            document['writer_context']=context
    paragraphs,writer_status=llm_writer.write_document(store,scope,key,document)
    document=llm_writer.apply(document,paragraphs,writer_status)
    if prior:
        document=llm_writer.retain_previous(document,old,writer_status)
    scope_form={'gang_origin':'gang_history','territory_origin':'territory_history'}.get(scope,scope)
    document = director.direct_document(scope_form,key,document)
    document.setdefault("source_event_ids", [])
    snapshot = store.latest_snapshot()
    document.setdefault("source_ids", ["live:campaign-sheet" if snapshot and snapshot.get("source_id") == "live:campaign-sheet" else "baseline:snapshot-0001"])
    if document.get('writer_context',{}).get('identity') and store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id='player:writer-identities'").fetchone():
        document['source_ids']=list(dict.fromkeys(document['source_ids']+['player:writer-identities']))
    if "C-NINE" in _text(document) and store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id='canon:c-nine-story-export'").fetchone():
        document["source_ids"] = list(dict.fromkeys(document["source_ids"]+["canon:c-nine-story-export"]))
    semantic = {k:v for k,v in document.items() if k not in {'generated_at','date_display'}}
    artifact_hash = digest([input_hash,semantic])
    artifact_id = digest([scope, str(key), artifact_hash, GENERATION])[:32]
    store.db.execute("UPDATE story_artifacts SET active=0 WHERE scope_type=? AND scope_key=?", (scope,str(key)))
    store.db.execute("""INSERT INTO story_artifacts(artifact_id,scope_type,scope_key,document_json,input_hash,generation_version,generated_at,active)
        VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(artifact_id) DO UPDATE SET active=1""", (artifact_id,scope,str(key),encode(document),artifact_hash,GENERATION,generated_at))
    for event_id in document["source_event_ids"]:
        _link(store, scope, artifact_id, event_id=event_id)
    for source_id in document["source_ids"]:
        if store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id=?", (source_id,)).fetchone():
            _link(store, scope, artifact_id, source_id=source_id)
    return document


def document_for(store, scope, key):
    row = store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type=? AND scope_key=? AND active=1 ORDER BY generated_at DESC LIMIT 1", (scope,str(key))).fetchone()
    return json.loads(row[0]) if row else None


def _document(title, text, evidence, events=()):
    return {"title": title, "blocks": [{"type": "paragraph", "text": p} for p in text.split("\n\n") if p.strip()],
            "evidence": evidence, "source_event_ids": list(dict.fromkeys(events))}


def _text(document):
    return "\n\n".join(block.get("text", "") for block in document.get("blocks", []) if block.get("text"))


def _first_known(store, fighter):
    for row in store.db.execute("SELECT id,captured_at,source_id,payload_json FROM snapshots ORDER BY id"):
        payload = json.loads(row["payload_json"])
        gangs = payload.get("gangs")
        if not isinstance(gangs,dict):
            continue
        for gang in gangs.values():
            if str(gang.get("gang_id")) != str(fighter["gang_id"]):
                continue
            for name,record in (gang.get("fighters") or {}).items():
                if normal(name) == normal(fighter["name"]):
                    return record, dict(row)
    return {"XP":fighter.get("xp"),"Kills":fighter.get("kills"),"Status":fighter.get("status"),"Advancements":fighter.get("advancements"),"Effects":fighter.get("effects")}, None


def _current_battle_event(battle, events):
    """Resolve an account against today's active facts and its correction chain."""
    from snapshot import battle_identity
    current_key = battle_identity(battle)
    fallback = battle_identity(battle,prefer_source=False)
    matches = []
    fields = ("date","scenario","attacker","defender","winner","territory","territory_claimer")
    for event in events:
        if event["event_type"] not in {"battle_result","battle_record_corrected"}:
            continue
        p = event["payload"]
        facts = p.get("current") if event["event_type"] == "battle_record_corrected" else p
        if not isinstance(facts,dict):
            continue
        same_identity = (p.get("battle_key") or p.get("source_battle_key")) == current_key or battle_identity(facts,prefer_source=False) == fallback
        if same_identity and all(facts.get(k) == battle.get(k) for k in fields):
            matches.append(event)
    if not matches:
        return None
    chosen = max(matches,key=lambda e:(e.get("observed_at") or "",e.get("created_at") or "",e["event_id"]))
    return {**chosen,"payload":{k:battle.get(k) for k in fields},
            "occurred_at":chosen.get("occurred_at") if chosen["event_type"] == "battle_result" else None}


def regenerate(store, force=False, ambient=False, writer_enabled=True, fighter_ids=None, call_budget=None, writer_run_id=None):
    """Regenerate all views, or only selected fighters when fighter_ids is supplied."""
    target_fighter_ids = None if fighter_ids is None else {int(value) for value in fighter_ids}
    if target_fighter_ids is not None and len(target_fighter_ids) != 1:
        raise ValueError("A scoped writer run must target exactly one fighter")
    llm_writer.reset_budget(call_budget,writer_run_id)
    llm_writer.set_enabled(writer_enabled)
    with store._lock:
        lore = store.db.execute("SELECT * FROM lore_sources ORDER BY id LIMIT 1").fetchone()
        if lore and not store.db.execute("SELECT 1 FROM provenance_sources WHERE source_id='canon:c-nine-story-export'").fetchone():
            store.record_source("canon:c-nine-story-export","authored_campaign_lore","canon_authored",lore["title"] or "C-NINE Story",source_uri=lore["source_url"],content_hash=hashlib.sha256(lore["content"].encode("utf-8")).hexdigest())
        gangs = [dict(r) for r in store.db.execute("SELECT * FROM gangs WHERE active=1 ORDER BY gang_id")]
        fighters = [dict(r) for r in store.db.execute("SELECT * FROM fighters ORDER BY id")]
        if target_fighter_ids is not None and not target_fighter_ids.issubset({int(f["id"]) for f in fighters}):
            raise ValueError("The selected fighter does not exist")
        battles = [dict(r) for r in store.db.execute("SELECT * FROM battles WHERE active=1 ORDER BY date,source_row")]
        territories = [dict(r) for r in store.db.execute("SELECT * FROM territories WHERE active=1 ORDER BY id")]
        events = _all_events(store)
        source_fields = ("id","gang_id","gang_name","name","type","class","xp","kills","advancements","effects","status","notes","mechanics_json","listed_in_source","writer_identity_json")
        source_fighters = [{**{k:f.get(k) for k in source_fields}, "authored_backstory":f.get("backstory") if _authored(f) else None} for f in fighters]
        code_hash = digest([Path(module.__file__).read_text(encoding='utf-8') for module in (prose,director,world_streams,llm_writer)] + [Path(__file__).read_text(encoding='utf-8'),director.policy_hash()])
        fingerprint = digest([GENERATION,code_hash,llm_writer.availability(), source_fighters,
                              [{k:v for k,v in g.items() if k not in {"backstory","provenance_class","backstory_source"}} for g in gangs],
                              [{k:v for k,v in b.items() if k not in {"chronicle","chronicle_provenance_class"}} for b in battles],
                              [{k:v for k,v in t.items() if k not in {"backstory","provenance_class"}} for t in territories],
                              [e["event_id"] for e in events]])
        retry_writer=False
        if llm_writer.API_KEY:
            retry_writer=bool(store.db.execute("SELECT 1 FROM story_memories WHERE writer_status IN ('pending','unconfigured','error') LIMIT 1").fetchone())
            artifact_rows=store.db.execute("SELECT document_json FROM story_artifacts WHERE active=1").fetchall()
            entry_rows=store.db.execute("SELECT document_json FROM narrative_entries WHERE active=1").fetchall()
            retry_writer=retry_writer or any(json.loads(r[0]).get('writer_status') in ('pending','unconfigured','error') for r in artifact_rows)
            retry_writer=retry_writer or any(json.loads(r[0]).get('writer_status') in ('pending','unconfigured','error') for r in entry_rows)
        if target_fighter_ids is None and not force and not retry_writer and store.get_state("story_input_hash") == fingerprint:
            with store.db:
                added=world_streams.maybe_ambient(store,gangs,territories) if ambient else 0
                if added:
                    store.db.execute("UPDATE system_state SET value=? WHERE key='story_revision'",(digest([fingerprint,now()])[:16],))
            return {"changed": bool(added), "revision": store.get_state('story_revision',fingerprint[:16]), 'ambient_created':added}
        generated_at = now()
        by_gang = {str(g["gang_id"]): g for g in gangs}
        fighters_by_key = {f"{f['gang_id']}/{normal(f['name'])}":f for f in fighters}
        event_by_id = {e["event_id"]:e for e in events}
        direct_events = defaultdict(list)
        gang_events = defaultdict(list)
        for event in events:
            for subject in event["subjects"]:
                if subject["entity_type"] == "fighter" and subject["role"] == "affected":
                    direct_events[subject["entity_key"]].append(event)
                elif subject["entity_type"] == "gang":
                    gang_events[subject["entity_key"]].append(event)
        all_memories = []
        with store.db:
            if target_fighter_ids is None:
                store.db.execute("UPDATE story_memories SET active=0")
            else:
                store.db.executemany("UPDATE story_memories SET active=0 WHERE fighter_id=?",[(value,) for value in target_fighter_ids])
            for fighter in fighters:
                if target_fighter_ids is not None and int(fighter["id"]) not in target_fighter_ids:
                    continue
                gang = by_gang.get(str(fighter["gang_id"]), {"name":fighter["gang_name"],"gang_type":""})
                voice = prose.voice_profile(fighter, gang)
                store.db.execute("UPDATE fighters SET voice_profile_json=? WHERE id=?", (encode(voice),fighter["id"]))
                fighter["voice_profile"] = voice
                key = f"{fighter['gang_id']}/{normal(fighter['name'])}"
                memories = []
                legacy = [dict(r) for r in store.db.execute("SELECT * FROM fighter_events WHERE fighter_id=? ORDER BY id", (fighter["id"],))]
                if legacy:
                    for item in legacy:
                        et = item["event_type"]
                        if et not in {"baseline","advancement","effect","status"}:
                            continue
                        event = event_by_id.get(item.get("campaign_event_id"), {})
                        payload = {"detail":item["detail"], "title":item["title"]}
                        memories.append(_memory(store,fighter,gang,f"legacy:{item['id']}",et,payload,event,baseline=True,prior=[m['content'] for m in memories[-3:]]))
                else:
                    # A first observed live roster is a baseline, not a fabricated recruitment history.
                    initial, snap = _first_known(store,fighter)
                    state = {k:initial.get(k) for k in ("XP","Kills","Status")}
                    evidence = [f"{k}: {display(v)}" for k,v in state.items()]
                    m = _memory(store,fighter,gang,"first-known-state","baseline",state,baseline=True,evidence=evidence)
                    m["source_id"] = "live:campaign-sheet" if snap and snap.get("source_id") == "live:campaign-sheet" else "baseline:snapshot-0001"
                    m["observed_at"] = snap.get("captured_at") if snap else None
                    memories.append(m)
                    for field, et in (("Advancements","advancement"),("Effects","effect"),("Status","status")):
                        if initial.get(field) and (field != "Status" or normal(initial[field]) != "active"):
                            m = _memory(store,fighter,gang,f"first-known-{field}",et,{"detail":initial[field]},baseline=True,prior=[m['content'] for m in memories[-3:]])
                            m["source_id"], m["observed_at"] = memories[0]["source_id"], memories[0]["observed_at"]
                            memories.append(m)
                for event in direct_events[key]:
                    if event["event_type"] not in RULES or event["event_key"].startswith("baseline:"):
                        continue
                    memories.append(_memory(store,fighter,gang,event["event_id"],event["event_type"],event["payload"],event,prior=[m['content'] for m in memories[-3:]]))
                # The newest gang record is shared context, never proof of individual attendance.
                if normal(fighter.get("status")) not in {"killed","dead","retired"}:
                    related = [b for b in battles if gang["name"] in (b.get("attacker"),b.get("defender"),b.get("winner"))]
                    latest = related[-1] if related else None
                    shared = [event for b in related if (event := _current_battle_event(b,events)) and not event["event_key"].startswith("baseline:")]
                    for event in gang_events[str(fighter["gang_id"])]:
                        if event["event_type"] == "territory_holder_changed":
                            memories.append(_memory(store,fighter,gang,f"shared:{event['event_id']}","territory_holder_changed",event["payload"],event,prior=[m['content'] for m in memories[-3:]]))
                        elif event["event_type"] in {"gang_reputation_changed","gang_alignment_changed"}:
                            memories.append(_memory(store,fighter,gang,f"shared:{event['event_id']}",event["event_type"],event["payload"],event,prior=[m['content'] for m in memories[-3:]]))
                        elif event["event_type"] == "fighter_status_changed" and normal(event["payload"].get("after")) in {"killed","dead","captured"}:
                            subjects = [s for s in event["subjects"] if s["entity_type"] == "fighter" and s["entity_key"] != key]
                            if subjects:
                                et = "gangmate_loss" if normal(event["payload"].get("after")) in {"killed","dead"} else "gangmate_captured"
                                p = {**event["payload"], "subject_name":subjects[0]["display_name"]}
                                memory = _memory(store,fighter,gang,f"shared:{event['event_id']}",et,p,event,context=p,prior=[m['content'] for m in memories[-3:]])
                                present = fighters_by_key.get(subjects[0]['entity_key'],{})
                                condition = normal(present.get('status'))
                                expected = {'killed','dead'} if et == 'gangmate_loss' else {'captured'}
                                if condition and condition not in expected:
                                    memory['tags'].append('history_only')
                                    memory['title'] = 'An earlier gang status entry'
                                    memory['content'] = f"The earlier return entered {p['subject_name']} as {p.get('after')}. The later roll says {present.get('status')}; I have to carry the amended account with the old one."
                                    memory['evidence'].append(f"Current source status for {p['subject_name']}: {present.get('status')}")
                                memories.append(memory)
                    seen = set()
                    for event in shared:
                        p = event["payload"]
                        # Old row-number correction histories are not replayed as battles.
                        signature = tuple(p.get(k) for k in ("date","scenario","attacker","defender","winner"))
                        if signature in seen:
                            continue
                        seen.add(signature)
                        memories.append(_memory(store,fighter,gang,f"gang:{event['event_id']}","gang_battle_outcome",p,event,context={"attendance":"unknown"},prior=[m['content'] for m in memories[-3:]]))
                    if latest and tuple(latest.get(k) for k in ("date","scenario","attacker","defender","winner")) not in seen:
                        e = _current_battle_event(latest,events) or {"occurred_at":latest.get("date")}
                        m = _memory(store,fighter,gang,f"gang-record:{latest.get('source_battle_key') or latest['id']}","gang_battle_outcome",latest,e,baseline=True,context={"attendance":"unknown"},prior=[m['content'] for m in memories[-3:]])
                        memories.append(m)
                if "C-NINE" in gang.get("name","") or "c-nine story" in normal(fighter.get("backstory_source")):
                    for m in memories:
                        m["context_source_ids"] = ["canon:c-nine-story-export"]
                elif "campaign sheet" in normal(fighter.get("backstory_source")):
                    for m in memories:
                        m["context_source_ids"] = ["player:campaign-sheet-lore"]
                if fighter.get('writer_identity_json') not in (None,'','{}'):
                    for m in memories:
                        m.setdefault('context_source_ids',[]).append('player:writer-identities')
                saved = [_save_memory(store,fighter["id"],m,generated_at) for m in memories]
                groups = defaultdict(list)
                if normal(fighter.get("status")) not in {"killed","dead"}:
                    for m in saved:
                        groups[m["batch"]].append(m)
                for batch, candidates in groups.items():
                    candidates = [m for m in candidates if m["importance"] >= 4]
                    if len(candidates) < 2 or sum(m["importance"] for m in candidates) < REFLECTION_THRESHOLD:
                        continue
                    cited = sorted(candidates,key=lambda m:(-m["importance"],m["memory_key"]))[:4]
                    ref_text,ref_status=llm_writer.write_memory(store,fighter,gang,'What stays with me',
                           list(dict.fromkeys(x for m in cited for x in m['evidence'])),voice['writer_context'],
                           prior=[{'title':m['title'],'tags':m['tags'],'importance':m['importance'],
                                   'evidence':m['evidence'],'source_event_ids':m['source_event_ids']} for m in cited],
                           form='fighter_reflection')
                    ref_content="\n\n".join(llm_writer.paragraph_text(p) for p in ref_text)
                    ref_runs=[llm_writer.paragraph_runs(p) for p in ref_text]
                    if not ref_content:
                        retained=_retained_writer_content(store,fighter['id'],f"reflection:{batch}",ref_status)
                        if retained: ref_content,ref_runs,ref_status=retained
                    ref = {"memory_key":f"reflection:{batch}", "memory_type":"reflection", "title":"What stays with me",
                           "content":ref_content,
                           "writer_content_runs":ref_runs,"writer_status":ref_status.get('status','pending'),
                           "importance":min(10,round(sum(m["importance"] for m in cited)/len(cited)+0.5,1)),
                           "occurred_at":None, "observed_at":max((m.get("observed_at") or "" for m in cited),default="") or None,
                           "tags":list(dict.fromkeys(["reflection"]+[t for m in cited for t in m["tags"]])),
                           "evidence":list(dict.fromkeys(x for m in cited for x in m["evidence"])),
                           "source_event_ids":list(dict.fromkeys(x for m in cited for x in m["source_event_ids"])),
                           "source_observation_ids":[m["id"] for m in cited], "source_id":cited[0]["source_id"],
                           "writer_context":voice['writer_context'],
                           "provenance_class":"inference", "confidence":0.6, "baseline":all(m["baseline"] for m in cited)}
                    saved.append(_save_memory(store,fighter["id"],ref,generated_at))
                all_memories.extend({**m,"fighter_id":fighter["id"],"gang_id":fighter["gang_id"]} for m in saved)
                if not _authored(fighter):
                    text = prose.fighter_biography(fighter,gang)
                    facts = [f"Role: {fighter.get('class')}",f"Type: {fighter.get('type')}",f"XP: {fighter.get('xp')}",f"Kills: {fighter.get('kills')}",f"Status: {fighter.get('status')}",f"Effects: {display(fighter.get('effects'))}",f"Advancements: {display(fighter.get('advancements'))}"]
                    facts.extend(voice.get('evidence',[]))
                    document = _document(fighter["name"],text,facts)
                    document['source_locator'] = f"gang:{fighter['gang_id']}:fighter:{fighter['name']}"
                    document['writer_context']=voice['writer_context']
                    doc = _artifact(store,"fighter_biography",fighter["id"],document,fingerprint,generated_at)
                    store.db.execute("UPDATE fighters SET backstory=?,backstory_source='mechanically-inferred',provenance_class='inference' WHERE id=?", (_text(doc),fighter["id"]))
            if target_fighter_ids is not None:
                return {"changed":True,"revision":fingerprint[:16],"memories":len(all_memories),
                        "fighters":len(target_fighter_ids),"generated_at":generated_at,
                        "writer":llm_writer.run_summary(),"memory_results":[
                            {"memory_id":m["id"],"title":m["title"],"writer_status":m["writer_status"]}
                            for m in all_memories]}
            for gang in gangs:
                fs = [f for f in fighters if str(f["gang_id"]) == str(gang["gang_id"])]
                if not _authored(gang):
                    origin = document_for(store,'gang_origin',gang['gang_id'])
                    if not origin:
                        origin = _artifact(store,'gang_origin',gang['gang_id'],_document(gang['name'],prose._culture(gang),[f"Faction at first description: {gang.get('gang_type')}"]),fingerprint,generated_at)
                    text = prose.gang_history(gang,fs,battles,territories)
                    related = [b for b in battles if gang['name'] in (b.get('attacker'),b.get('defender'),b.get('winner'))]
                    holders = [t['territory'] for t in territories if str(t.get('gang_id')) == str(gang['gang_id'])]
                    evidence = [f"Faction: {gang.get('gang_type')}",f"Listed fighters: {sum(f.get('listed_in_source',1) for f in fs)}",f"Recorded battles: {len(related)}",f"Recorded wins: {sum(b.get('winner') == gang['name'] for b in related)}",f"Current holdings: {', '.join(holders) or 'None recorded'}"]
                    anchors = [_current_battle_event(b,events) for b in related]
                    doc = _artifact(store,"gang_history",gang["gang_id"],_document(gang["name"],text,evidence,[e['event_id'] for e in anchors if e]),fingerprint,generated_at)
                    store.db.execute("UPDATE gangs SET backstory=?,backstory_source='mechanically-inferred',provenance_class='inference' WHERE gang_id=?", (_text(origin),gang["gang_id"]))
                doc = prose.downtime_document(gang,fs,[m for m in all_memories if str(m["gang_id"]) == str(gang["gang_id"])],battles)
                doc = _artifact(store,"downtime",gang["gang_id"],doc,fingerprint,generated_at)
                existing = store.db.execute("SELECT id FROM downtime_reports WHERE gang_id=? ORDER BY id DESC LIMIT 1",(gang["gang_id"],)).fetchone()
                if existing:
                    store.db.execute("UPDATE downtime_reports SET report=?,generated_at=?,period_label='Current campaign interval' WHERE id=?",(_text(doc),generated_at,existing[0]))
                else:
                    store.db.execute("INSERT INTO downtime_reports(gang_id,gang_name,period_label,report,generated_at) VALUES(?,?,'Current campaign interval',?,?)",(gang["gang_id"],gang["name"],_text(doc),generated_at))
            for territory in territories:
                origin = document_for(store,'territory_origin',territory['id'])
                if not origin:
                    opening=prose._PLACES.get(territory['territory'], f"The name {territory['territory']} marks a place where work and passage give an armed claim its value.")
                    origin = _artifact(store,'territory_origin',territory['id'],_document(territory['territory'],opening,[f"Recorded type at first description: {territory['territory']}"]),fingerprint,generated_at)
                text = prose.territory_history(territory,battles)
                related = [b for b in battles if b.get('territory') == territory['territory']]
                facts = [f"Recorded holder: {display(territory.get('gang_name'))}"] + [f"{b.get('date')}: {b.get('scenario')}; winner {display(b.get('winner'))}" for b in related]
                anchors = [_current_battle_event(b,events) for b in related]
                doc = _artifact(store,"territory_history",territory["id"],_document(territory["territory"],text,facts,[e['event_id'] for e in anchors if e]),fingerprint,generated_at)
                store.db.execute("UPDATE territories SET backstory=?,provenance_class='inference' WHERE id=?",(_text(origin),territory["id"]))
            world_streams.rebuild(store,gangs,territories,battles,events,_current_battle_event,event_evidence,generated_at)
            if ambient:
                world_streams.maybe_ambient(store,gangs,territories,at=generated_at)
            for battle in battles:
                document=prose.battle_report(battle,gangs,fighters,events)
                document['occurred_at']=battle.get('date')
                doc = _artifact(store,"battle_report",battle["id"],document,fingerprint,generated_at)
                store.db.execute("UPDATE battles SET chronicle=?,chronicle_provenance_class='inference' WHERE id=?",(_text(doc),battle["id"]))
            text = prose.region_history(gangs,territories,battles) if gangs else "The district record is awaiting its first verified campaign state."
            facts = [f"Active gangs: {len(gangs)}",f"Territory records: {len(territories)}",f"Recorded battles: {len(battles)}"] + [f"{g['name']} — reputation: {display(g.get('reputation'))}" for g in gangs]
            doc = _artifact(store,"region_history","campaign",_document("Krakaumunda",text,facts),fingerprint,generated_at)
            store.db.execute("UPDATE regions SET backstory=?,provenance_class='inference'",(_text(doc),))
            if not store.db.execute("SELECT 1 FROM regions").fetchone():
                store.db.execute("INSERT INTO regions(name,backstory,provenance_class) VALUES('Krakaumunda',?,'inference')",(_text(doc),))
            pairs = defaultdict(list)
            for battle in battles:
                if battle.get('attacker') and battle.get('defender'):
                    pairs[tuple(sorted((battle['attacker'],battle['defender'])))].append(battle)
            store.db.execute("UPDATE narrative_threads SET status='historical' WHERE scope_type='relationship'")
            for (a,b), encounters in pairs.items():
                if len(encounters) < 2:
                    continue
                scope_key = '|'.join((a,b))
                text = f"{a} and {b} recur on the same ground. Across {len(encounters)} recorded engagements, each name has become part of what the other gang must reckon with. Repetition gives the next meeting a history before it begins."
                anchors = [_current_battle_event(battle,events) for battle in encounters]
                doc = _artifact(store,'relationship',scope_key,_document(f'{a} / {b}',text,[f'Recorded encounters: {len(encounters)}'],[e['event_id'] for e in anchors if e]),fingerprint,generated_at)
                prior = next((dict(r) for r in store.db.execute("SELECT * FROM narrative_threads WHERE scope_type='relationship'") if set((r['scope_key'] or '').split('|')) == {a,b}),None)
                if prior:
                    store.db.execute("UPDATE narrative_threads SET summary=?,status='active',evidence_json=?,updated_at=? WHERE id=?",(_text(doc),encode(doc['source_event_ids']),generated_at,prior['id']))
                else:
                    store.db.execute("INSERT INTO narrative_threads(scope_type,scope_key,title,status,summary,evidence_json,updated_at) VALUES('relationship',?,?,'active',?,?,?)",(scope_key,f'{a} / {b}',_text(doc),encode(doc['source_event_ids']),generated_at))
            for k,v in {"story_input_hash":fingerprint,"story_revision":fingerprint[:16],"story_generated_at":generated_at,"story_generation_version":GENERATION,
                        "engine_version":f"NCCE v{VERSION} Campaign Minds","story_memory_count":len(all_memories),"story_writer":json.dumps(llm_writer.availability(),sort_keys=True)}.items():
                store.db.execute("INSERT INTO system_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
        return {"changed":True,"revision":fingerprint[:16],"memories":len(all_memories),"fighters":len(fighters),"generated_at":generated_at}


def read_memories(store, fighter_id):
    result = []
    for row in store.db.execute("SELECT * FROM story_memories WHERE fighter_id=? AND active=1 ORDER BY baseline ASC,coalesce(occurred_at,observed_at) DESC,created_at DESC,memory_type DESC,memory_key",(fighter_id,)):
        item = dict(row)
        item["id"] = item["memory_id"]
        item["is_baseline"] = bool(item["baseline"])
        for field in ("tags","evidence","source_event_ids","source_observation_ids"):
            item[field] = json.loads(item.pop(field+"_json"))
        item['date_display']=director.record_date(item)
        item['writer_context']=json.loads(item.pop('writer_context_json') or '{}')
        item['content_runs']=json.loads(item.pop('content_runs_json') or '[]')
        item['source_ids']=[r[0] for r in store.db.execute("SELECT DISTINCT source_id FROM narrative_evidence WHERE artifact_type='story_memory' AND artifact_key=? AND source_id IS NOT NULL",(item['memory_id'],))]
        result.append(item)
    return result


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (TypeError,ValueError):
        return None


def select_mind(fighter, memories, at=None):
    if normal(fighter.get("status")) in {"killed","dead"}:
        return []
    at = _timestamp(at) if at else datetime.now(timezone.utc)
    at = at or datetime.now(timezone.utc)
    active = set()
    condition = normal(str(fighter.get("effects") or "")+" "+str(fighter.get("status") or ""))
    for keyword, tag in (("critical injury","critical"),("recovery","recovery"),("convalescence","recovery"),("captur","captivity"),("injur","injury"),("humiliat","humiliation"),("enmity","grudge"),("scar","scars")):
        if keyword in condition:
            active.add(tag)
    if normal(fighter.get("class")) in {"juve","prospect"}:
        active.add("growth")
    if normal(fighter.get("class")) in {"leader","champion"}:
        active.update(("responsibility","belonging"))
    try:
        profile = fighter.get('voice_profile') or json.loads(fighter.get('voice_profile_json') or '{}')
    except (TypeError,ValueError):
        profile = {}
    preferences = set()
    trait_topics = {'practical':{'equipment','weapon','return'},'clinical':{'injury','recovery','grief'},
                    'responsible':{'belonging','grief','outcome','promotion'},'aspiring':{'growth','advancement','promotion'},
                    'enduring':{'injury','recovery','return'},'physical':{'equipment','weapon','growth'},
                    'analytical':{'skill','advancement','equipment'},'resolute':{'grudge','return','growth'},
                    'blooded':{'kills','battle'},'measured':{'territory','equipment'},'inward':{'reflection','identity'}}
    for trait in profile.get('traits',[]):
        preferences.update(trait_topics.get(trait,set()))
    if profile.get('register') == 'crew':
        preferences.add('belonging')
    scored = []
    for memory in memories:
        tags = set(memory.get("tags") or [])
        if tags & {"death","history_only"}:
            continue
        if "critical" in tags and "critical" not in active:
            continue
        if "captivity" in tags and "captivity" not in active and "belonging" not in tags:
            continue
        if "recovery" in tags and "recovery" not in active and "return" not in tags:
            continue
        if "injury" in tags and not active & {"injury","critical","recovery","scars","grudge","humiliation"} and "return" not in tags:
            continue
        date = _timestamp(memory.get("occurred_at") or memory.get("observed_at"))
        age = max(0,(at-date).total_seconds()/86400) if date else 180
        recency = 2 ** (-age / RECENCY_HALF_LIFE_DAYS)
        if memory.get("baseline") and not memory.get("occurred_at"):
            recency = min(recency,0.15)
        relevance = 1.0 if tags & active else 0.65 if tags & {"battle","equipment","promotion","advancement","return"} else 0.25
        if "return" in tags and normal(fighter.get("status")) == "active":
            relevance = 1.0
        # Closed bodily conditions remain memories but yield to current concerns.
        if tags & {"critical","recovery","captivity"} and not tags & active and "return" not in tags:
            relevance = 0.05
        bias = 1.0 if tags & preferences else 0.5 if tags & active else 0.0
        score = round(0.4*(memory["importance"]/10)+0.3*recency+0.25*relevance+0.05*bias,5)
        scored.append((score,memory,{"importance":round(memory["importance"]/10,3),"recency":round(recency,3),"relevance":relevance,"character_bias":bias}))
    scored.sort(key=lambda x:(-x[0],x[1]["memory_key"]))
    selected, used_events, primary = [], set(), set()
    for score, memory, details in scored:
        source_ids = set(memory.get("source_event_ids") or memory.get("source_observation_ids") or [memory["memory_key"]])
        tag = next((t for t in memory.get("tags",[]) if t in LABELS),"reflection")
        # Keep the small view varied and avoid showing a reflection beside the very same event.
        if source_ids & used_events or tag in primary:
            continue
        selected.append({**memory,"memory_id":memory.get("id"),"label":LABELS.get(tag,"A current concern"),"selection_score":score,"score_details":details})
        used_events.update(source_ids); primary.add(tag)
        if len(selected) == 4:
            break
    return selected


def fighter_story(store, fighter):
    memories = read_memories(store,fighter["id"])
    try:
        voice = json.loads(fighter.get("voice_profile_json") or "{}")
    except ValueError:
        voice = {}
    return {"memories":memories,"mind":select_mind(fighter,memories),"voice_profile":voice,
            "biography_document":document_for(store,"fighter_biography",fighter["id"]),
            "mind_policy":{"count":"2–4 when supported; no current thoughts for deceased fighters","recency_half_life_days":RECENCY_HALF_LIFE_DAYS,"weights":{"importance":0.4,"recency":0.3,"relevance":0.25,"character_bias":0.05}}}


def territory_writing_plan(store):
    territories = [dict(row) for row in store.db.execute("SELECT * FROM territories WHERE active=1 ORDER BY id")]
    origin_scopes = ("territory_origin", "territory_history")
    artifacts = []
    for territory in territories:
        for scope in origin_scopes:
            row = store.db.execute("SELECT document_json FROM story_artifacts WHERE scope_type=? AND scope_key=? AND active=1 ORDER BY generated_at DESC LIMIT 1",
                                   (scope, str(territory["id"]))).fetchone()
            if row:
                artifacts.append((scope, territory["id"], json.loads(row["document_json"])))
    stream_count = store.db.execute("SELECT COUNT(*) FROM narrative_entries WHERE scope_type='territory' AND active=1 AND provenance_class='inference'").fetchone()[0]
    expected = len(artifacts) + int(stream_count)
    return {"territories": len(territories), "place_documents": len(artifacts), "place_entries": int(stream_count), "entries_targeted": expected}, artifacts, territories


def regenerate_territory_writing(store, call_budget=None, writer_run_id=None):
    """Refresh only current place origin/history documents and place event entries."""
    if not llm_writer.API_KEY:
        raise RuntimeError("Writing provider is not configured; no request was made.")
    plan, artifacts, territories = territory_writing_plan(store)
    expected = plan["entries_targeted"]
    budget = llm_writer.MAX_CALLS if call_budget is None else max(1, min(llm_writer.MAX_CALLS, int(call_budget)))
    if expected > budget:
        raise RuntimeError(f"Territory pass needs {expected} entries; configured per-run writer budget is {budget}. No writing was started.")
    llm_writer.reset_budget(budget, writer_run_id)
    llm_writer.set_enabled(True)
    created = now()
    try:
        with store._lock, store.db:
            for scope, key, document in artifacts:
                input_hash = hashlib.sha256(json.dumps([GENERATION, scope, key, document], ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
                _artifact(store, scope, key, document, input_hash, created)
            gangs = [dict(row) for row in store.db.execute("SELECT * FROM gangs WHERE active=1 ORDER BY gang_id")]
            battles = [dict(row) for row in store.db.execute("SELECT * FROM battles WHERE active=1 ORDER BY date,source_row")]
            events = _all_events(store)
            world_streams.rebuild(store, gangs, territories, battles, events, _current_battle_event,
                                  event_evidence, created, territories_only=True)
            status_counts = defaultdict(int)
            for row in store.db.execute("SELECT document_json FROM story_artifacts WHERE active=1 AND scope_type IN ('territory_origin','territory_history')"):
                status_counts[json.loads(row[0]).get("writer_status", "missing")] += 1
            for row in store.db.execute("SELECT document_json FROM narrative_entries WHERE active=1 AND scope_type='territory' AND provenance_class IN ('inference','connective_fiction')"):
                status_counts[json.loads(row[0]).get("writer_status", "missing")] += 1
        return {**plan, "status_counts": dict(status_counts), "writer": llm_writer.run_summary()}
    finally:
        llm_writer.set_enabled(False)
