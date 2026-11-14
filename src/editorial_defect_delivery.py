"""Finite owner-approved editorial defect revision relay.

A temporary Render variable carries nine exact approved manuscript snapshots
and their canonical imported-parent receipts. Existing NCCE request_revision
and deliver functions enforce immutable source identity, revision ordering,
writer contracts and duplicate delivery handling.
"""
from __future__ import annotations
import json
import os
from uuid import UUID

import exchange_automation as exchange

ENV_KEY="NCCE_DEFECT_CORRECTIONS_JSON"
OWNER_MARKER="owner_approved_9_slag_defects_2026-11-14"
EXPECTED=9

def parse(raw):
    if not isinstance(raw,str) or len(raw.encode("utf-8"))>25000:
        raise ValueError("Invalid defect manifest length")
    data=json.loads(raw)
    if not isinstance(data,dict) or set(data)!={"approval","items"} or data["approval"]!=OWNER_MARKER:
        raise ValueError("Invalid defect owner approval marker")
    items=data["items"]
    if not isinstance(items,list) or len(items)!=EXPECTED:
        raise ValueError("Expected exactly nine approved defects")
    seen=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!={"bulk_row","parent_id","parent_receipt","form","text"}:
            raise ValueError("Defect manifest item schema mismatch")
        if type(item["bulk_row"]) is not int or item["bulk_row"] not in (31,47,48,49,51,52,53,54,58) or item["bulk_row"] in seen:
            raise ValueError("Duplicate or unexpected QA row")
        seen.add(item["bulk_row"])
        pid=item["parent_id"]
        if not isinstance(pid,str) or str(UUID(pid))!=pid:
            raise ValueError("Parent UUID is not canonical")
        if not isinstance(item["parent_receipt"],str) or not item["parent_receipt"].startswith("exchange:"+pid+":"):
            raise ValueError("Parent receipt mismatch")
        if item["form"]!=("fighter_memory" if item["bulk_row"]==31 else "fighter_reflection"):
            raise ValueError("Wrong prose form")
        text=item["text"]
        if not isinstance(text,str) or not text.strip() or len(text)>30000:
            raise ValueError("Missing or oversized approved text")
        if item["form"]=="fighter_memory" and len(text)>350:
            raise ValueError("Fighter memory exceeds 350 characters")
        if item["form"]=="fighter_reflection" and not 60<=len(text.split())<=130:
            raise ValueError("Reflection outside editorial word target")
    return sorted(items,key=lambda x:x["bulk_row"])

def apply(store, raw):
    items=parse(raw)
    # Read-only preflight all nine before creating any revision request.
    # Existing imported outcomes can be safely reused on service restarts.
    found=[]
    with store._lock:
        for item in items:
            parent=store.db.execute("SELECT * FROM writing_exchange_requests WHERE request_id=?",
                                    (item["parent_id"],)).fetchone()
            if not parent or parent["state"]!="IMPORTED" or parent["receipt"]!=item["parent_receipt"]:
                raise ValueError("Imported parent absent or changed at QA row "+str(item["bulk_row"]))
            packet=json.loads(parent["packet_json"])
            if packet["request"]["form"]!=item["form"]:
                raise ValueError("Parent form mismatch")
            latest=store.db.execute("SELECT * FROM writing_exchange_requests WHERE target_key=? AND state='IMPORTED' ORDER BY rowid DESC LIMIT 1",
                                    (parent["target_key"],)).fetchone()
            waiting=store.db.execute("SELECT * FROM writing_exchange_requests WHERE target_key=? AND revision_of IS NOT NULL AND state IN ('PENDING','DEFERRED','HOLD') ORDER BY rowid DESC LIMIT 1",
                                     (parent["target_key"],)).fetchone()
            if latest is None:
                raise ValueError("No imported target")
            if latest["request_id"]==parent["request_id"]:
                candidates=[c for c in exchange.candidates(store) if exchange.target_key(c)==parent["target_key"]]
                if len(candidates)!=1 or exchange._current_markdown(store,candidates[0])!=parent["raw_markdown"] or exchange.semantic_seal(store,candidates[0])!=exchange.semantic_seal(store,exchange.load(parent["target_json"])["target"]):
                    raise ValueError("Source or current prose mismatch at QA row "+str(item["bulk_row"]))
                if waiting and not (waiting["revision_of"]==parent["request_id"] and waiting["state"] in ("PENDING","DEFERRED")):
                    raise ValueError("Conflicting correction already exists")
            else:
                # Only idempotent rerun after our exact text was imported.
                if latest["raw_markdown"]!=item["text"] or latest["revision_of"]!=parent["request_id"] or not latest["receipt"]:
                    raise ValueError("Newer unexpected import exists")
            found.append((item,parent,latest))
    outcome={"imported":[],"already_imported":[],"held":[]}
    for item,parent,latest in found:
        n=item["bulk_row"]
        if latest["request_id"]!=parent["request_id"]:
            outcome["already_imported"].append({"bulk_row":n,"request_id":latest["request_id"],"receipt":latest["receipt"]})
            continue
        revision=exchange.request_revision(store,parent["request_id"],parent["receipt"])
        rid=revision["request_id"]
        row=store.db.execute("SELECT source_revision,state,revision_of,expected_receipt FROM writing_exchange_requests WHERE request_id=?",(rid,)).fetchone()
        if not row or row["revision_of"]!=parent["request_id"] or row["expected_receipt"]!=parent["receipt"] or row["state"] not in ("PENDING","DEFERRED"):
            raise ValueError("New correction request integrity mismatch")
        receipt=exchange.deliver(store,{"request_id":rid,"status":"READY","source_revision":row["source_revision"],
                                        "writer_text_md":item["text"],
                                        "writer_note":"Exact owner-approved Slag Eaters Final QA defect revision 2026-11-14",
                                        "completed_at_utc":""})
        if receipt["status"]=="imported":
            outcome["imported"].append({"bulk_row":n,"request_id":rid,"receipt":receipt["receipt"]})
        else:
            outcome["held"].append({"bulk_row":n,"request_id":rid,"error":receipt.get("error","")[:250]})
    return outcome

def apply_from_environment(store):
    raw=os.environ.get(ENV_KEY,"").strip()
    return apply(store,raw) if raw else None
