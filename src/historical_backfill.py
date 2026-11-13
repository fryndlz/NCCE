"""Isolated, owner-authorised historical prose backfill.

This module owns a finite *snapshot* of existing story slots. It never calls a
model and never writes campaign facts. Only the existing exchange.deliver()
commits prose; bulk items do not occupy the normal Queue.
"""
from __future__ import annotations

from collections import Counter
import json
from uuid import uuid4

import exchange_automation as exchange
from writing_exchange import digest, packed
from writing_waterfall import context as continuity, dependencies, order, plan, VERSION

OPEN = ("PREPARED", "ACTIVE")
FORMS = frozenset(("fighter_memory", "fighter_reflection"))
TERMINAL = frozenset(("IMPORTED", "HOLD", "SKIPPED"))


def now():
    return exchange.now()


def _row(row):
    return dict(row) if row is not None else None


def _job(store, job_id):
    row = store.db.execute(
        "SELECT * FROM historical_backfill_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Unknown historical backfill job")
    return dict(row)


def _items(store, job_id):
    return [dict(r) for r in store.db.execute(
        "SELECT * FROM historical_backfill_items WHERE job_id=? ORDER BY ordinal",
        (job_id,),
    )]


def _eligible(store, candidate, gang_ids):
    if candidate["form"] not in FORMS or candidate["entity_type"] != "fighter":
        return False
    row = store.db.execute(
        "SELECT gang_id FROM fighters WHERE id=?", (candidate["entity_key"],)
    ).fetchone()
    return bool(row and str(row["gang_id"]) in gang_ids and not candidate["approved"])


def _normal_conflict(store, key):
    # Do not steal a claimed, held, pending or already imported normal request.
    return store.db.execute(
        """SELECT 1 FROM writing_exchange_requests
           WHERE target_key=? AND state IN ('PENDING','DEFERRED','HOLD','IMPORTED')
           LIMIT 1""", (key,)
    ).fetchone() is not None


def reserved_targets(store):
    """Prevent normal preparation from claiming an active backfill's slots.

    The table-existence check makes this feature inert on older test fixtures.
    """
    if not store.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_backfill_items'"
    ).fetchone():
        return set()
    return {r[0] for r in store.db.execute(
        """SELECT i.target_key FROM historical_backfill_items i
           JOIN historical_backfill_jobs j USING(job_id)
           WHERE j.state IN ('PREPARED','ACTIVE')
             AND i.state NOT IN ('IMPORTED','SKIPPED')"""
    )}


def is_bulk_request(store, request_id):
    if not store.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_backfill_items'"
    ).fetchone():
        return False
    return bool(store.db.execute(
        "SELECT 1 FROM historical_backfill_items WHERE request_id=?",
        (request_id,),
    ).fetchone())


def create(store, gang_ids=None, *, gang_names=None, house_types=None, owner_authorized=False):
    """Snapshot only explicit gang IDs and currently incomplete fighter memories.

    No prose is imported, no existing Queue cell is changed, and overlapping
    active gangs are refused. Authority is per finite job, never a writer default.
    """
    if owner_authorized is not True:
        raise ValueError("Explicit owner authorization is required for this job")
    gang_ids=gang_ids or []
    gang_names=gang_names or []
    house_types=house_types or []
    if any(not isinstance(seq,list) or len(seq)>100 for seq in (gang_ids,gang_names,house_types)):
        raise ValueError("Gang selectors must be lists of at most 100 entries")
    if not any((gang_ids,gang_names,house_types)):
        raise ValueError("Choose explicit gang IDs, names or House/faction types")
    with store._lock:
        if store.db.in_transaction:
            raise RuntimeError("Backfill creation requires its own transaction")
        gangs=[dict(r) for r in store.db.execute("SELECT gang_id,name,gang_type FROM gangs")]
        found = {str(g["gang_id"]): g["name"] for g in gangs}
        requested={str(g) for g in gang_ids}
        def normalized(value):
            return " ".join(str(value or "").strip().casefold().split())
        def house_key(value):
            value=normalized(value)
            return value[6:] if value.startswith("house ") else value
        for label in gang_names:
            label_key=normalized(label)
            exact=[str(g["gang_id"]) for g in gangs
                   if normalized(g["name"])==label_key]
            if not exact and label_key in ("c-nine","c9"):
                # A display shorthand for canonical Geothermal Prospect Detail C-9.
                exact=[str(g["gang_id"]) for g in gangs
                       if normalized(g["name"]).startswith("c-nine")]
            if len(exact)!=1:
                raise ValueError("A selected gang name is absent or ambiguous: "+str(label))
            requested.add(exact[0])
        for house in house_types:
            matches=[str(g["gang_id"]) for g in gangs
                     if house_key(g["gang_type"])==house_key(house)]
            if not matches:
                raise ValueError("No active NCCE gang of House/faction: "+str(house))
            requested.update(matches)
        names=tuple(sorted(requested))
        if not names or len(names)>100 or any(g not in found for g in names):
            raise ValueError("Every requested gang must exist in NCCE")
        for row in store.db.execute(
            "SELECT scope_json FROM historical_backfill_jobs WHERE state IN ('PREPARED','ACTIVE')"
        ):
            if set(json.loads(row[0])) & set(names):
                raise ValueError("A selected gang already has an active backfill")
        candidates = exchange.candidates(store)
        selected = sorted((c for c in candidates if _eligible(store, c, set(names))), key=order)
        job_id = str(uuid4())
        created = now()
        prepared = []
        skipped = []
        for c in selected:
            key = exchange.target_key(c)
            if _normal_conflict(store, key):
                skipped.append({"target_key": key, "reason": "Existing normal Exchange request"})
                continue
            if key in reserved_targets(store):
                skipped.append({"target_key": key, "reason": "Already reserved by another job"})
                continue
            prepared.append((c, key))
        with store.db:
            store.db.execute(
                """INSERT INTO historical_backfill_jobs
                   (job_id,scope_json,state,created_at,authorized_at,manifest_json)
                   VALUES(?,?,'ACTIVE',?,?,?)""",
                (job_id, packed(list(names)), created, created,
                 packed({"gangs": {g: found[g] for g in names},
                         "form_scope": sorted(FORMS), "source_count": len(selected),
                         "skipped": skipped, "policy": "one_off_auto_approve"})),
            )
            for index, (c, key) in enumerate(prepared):
                rid=str(uuid4())
                base_packet=exchange._packet(store,c,rid)
                # Freeze all source/identity/style context at authorisation.
                # Dependency continuity is the ONLY context added later.
                store.db.execute(
                    """INSERT INTO historical_backfill_items
                       (request_id,job_id,ordinal,target_key,entity_key,form,
                        source_seal,context_seal,snapshot_json,packet_json,
                        state,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,'PENDING',?)""",
                    (rid,job_id,index,key,c["entity_key"],c["form"],
                     exchange.semantic_seal(store,c),
                     digest(base_packet["context"]),
                     packed({"target":c,"original":exchange.projection(store,c)}),
                     packed(base_packet),created),
                )
            # Conflicts are visible in the item ledger, not silently dropped.
            by_key={exchange.target_key(c):c for c in selected}
            for index, skip in enumerate(skipped, len(prepared)):
                c=by_key[skip["target_key"]]
                store.db.execute(
                    """INSERT INTO historical_backfill_items
                       (request_id,job_id,ordinal,target_key,entity_key,form,
                        source_seal,snapshot_json,state,created_at,error)
                       VALUES(?,?,?,?,?,?,?,?,'SKIPPED',?,?)""",
                    (str(uuid4()),job_id,index,skip["target_key"],c["entity_key"],c["form"],
                     exchange.semantic_seal(store,c),
                     packed({"target":c,"original":exchange.projection(store,c)}),
                     created,skip["reason"]),
                )
        return {"job_id":job_id,"state":"ACTIVE","scope":list(names),
                "discovered":len(selected),"queued":len(prepared),"skipped":skipped}


def summary(store, job_id, include_items=False):
    job = _job(store, job_id)
    items = _items(store,job_id)
    result = {"job_id":job_id,"scope":json.loads(job["scope_json"]),
              "state":job["state"],"created_at":job["created_at"],
              "authorized_at":job["authorized_at"],"closed_at":job["closed_at"],
              "count":len(items),"statuses":dict(Counter(x["state"] for x in items)),
              "manifest":json.loads(job["manifest_json"])}
    if include_items:
        result["items"] = [{
            "request_id":x["request_id"],"target_key":x["target_key"],
            "entity_key":x["entity_key"],"form":x["form"],
            "title":json.loads(x["snapshot_json"])["target"]["title"],
            "status":x["state"],"error":x["error"],
            "receipt":x["receipt"],"source_revision":x["source_revision"],
            "text_length":len(x["writer_text_md"] or ""),
        } for x in items]
    return result


def poll(store, job_id, limit=25):
    """Release prerequisite-safe packets without exposing them in normal Queue."""
    limit = int(limit)
    if not 1 <= limit <= 50:
        raise ValueError("Poll size must be between 1 and 50")
    with store._lock:
        job = _job(store,job_id)
        if job["state"] != "ACTIVE":
            return {"packets":[],"job":summary(store,job_id)}
        items = _items(store,job_id)
        in_flight = [x for x in items if x["state"]=="WRITING"]
        packets = [json.loads(x["packet_json"]) for x in in_flight[:limit]]
        if len(packets) >= limit:
            return {"packets":packets,"job":summary(store,job_id)}
        candidates = exchange.candidates(store)
        lookup = {exchange.target_key(c):c for c in candidates}
        runnable, deps, blocked = plan(store,candidates)
        available = {exchange.target_key(c) for c in runnable}
        for item in items:
            if len(packets) >= limit:
                break
            if item["state"]!="PENDING":
                continue
            c=lookup.get(item["target_key"])
            if not c or exchange.semantic_seal(store,c)!=item["source_seal"]:
                with store.db:
                    store.db.execute(
                        "UPDATE historical_backfill_items SET state='HOLD',error=? WHERE request_id=?",
                        ("Underlying historical source changed since snapshot", item["request_id"]),
                    )
                continue
            if item["target_key"] not in available:
                continue
            if digest(exchange._packet(store,c,item["request_id"])["context"])!=item["context_seal"]:
                with store.db:
                    store.db.execute(
                        "UPDATE historical_backfill_items SET state='HOLD',error=? WHERE request_id=?",
                        ("Frozen authored/voice context changed; manual reconciliation required", item["request_id"]),
                    )
                continue
            refs=continuity(store,c,deps,candidates)
            packet=json.loads(item["packet_json"])
            packet["request"]["source_revision"]=exchange.revision(c,refs,store)
            packet["context"]+=exchange.supplements(c,refs)
            packet["context"].append({
                "section":"brief","provenance":"instruction",
                "source_ref":"Owner-authorized finite historical backfill "+job_id,
                "event_at_utc":"","source_event_ids":"",
                "text":("This specific historical backfill is owner-authorized for automatic approval. "
                        "Write accurate, polished prose consistent with prior accepted voices; "
                        "keep a fighter memory within 350 characters including Markdown. "
                        "This does not modify normal Exchange approval. "
                        "Do not claim any separate event or disclose GM-only knowledge."),
            })
            with store.db:
                store.db.execute(
                    """UPDATE historical_backfill_items SET state='WRITING',
                       packet_json=?,source_revision=?,dispatched_at=?
                       WHERE request_id=? AND state='PENDING'""",
                    (packed(packet),packet["request"]["source_revision"],now(),item["request_id"]),
                )
            packets.append(packet)
        return {"packets":packets,"job":summary(store,job_id),
                "blocked":len([x for x in items if x["state"]=="PENDING"
                               and x["target_key"] in blocked])}


def _validate_bulk_text(form, text):
    """Apply the live writing contract by prose form, not by bulk job.

    A fighter_memory has a 350-character hard cap including Markdown.
    A fighter_reflection is a distinct synthesis form and is not subject
    to that cap; the canonical exchange importer enforces its own
    30,000-character cell limit for all forms.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Complete nonempty bulk prose required")
    if form == "fighter_memory" and len(text) > 350:
        raise ValueError("Complete fighter memory (<=350 characters including Markdown) required")
    if len(text) >= 30000:
        raise ValueError("Bulk prose must be shorter than 30000 characters")


def deliver(store, job_id, payload):
    """Converge at the EXISTING validated importer, with an invisible bridge row."""
    if not isinstance(payload,dict):
        raise ValueError("Expected a delivery object")
    request_id=payload.get("request_id")
    text=payload.get("writer_text_md")
    if payload.get("status")!="READY":
        raise ValueError("Only READY bulk drafts can import")
    with store._lock:
        job = _job(store,job_id)
        item = store.db.execute(
            "SELECT * FROM historical_backfill_items WHERE job_id=? AND request_id=?",
            (job_id,request_id),
        ).fetchone()
        if not item:
            raise ValueError("Unknown request for this historical backfill")
        item = dict(item)
        _validate_bulk_text(item["form"], text)
        if payload.get("source_revision")!=item["source_revision"]:
            raise ValueError("Frozen dispatched revision does not match")
        if item["state"]=="IMPORTED":
            if item["writer_text_md"]!=text:
                raise ValueError("Imported bulk text is immutable; request manual revision")
            return {"status":"imported","request_id":request_id,
                    "receipt":item["receipt"],"imported_at_utc":item["imported_at"],"reused":True}
        # The canonical import commits before the bulk receipt is recorded.
        # Recover that receipt even if the projection or job changed meanwhile.
        committed = store.db.execute(
            """SELECT raw_markdown,writer_note,receipt,imported_at FROM writing_exchange_requests
               WHERE request_id=? AND target_key=? AND source_revision=? AND state='IMPORTED'""",
            (request_id,item["target_key"],item["source_revision"]),
        ).fetchone()
        if committed:
            if committed['raw_markdown'] != text:
                raise ValueError("Imported bulk text is immutable; request manual revision")
            with store.db:
                store.db.execute(
                    """UPDATE historical_backfill_items SET state='IMPORTED',writer_text_md=?,
                       writer_note=?,receipt=?,imported_at=?,error='' WHERE request_id=?""",
                    (text,committed['writer_note'],committed['receipt'],committed['imported_at'],request_id),
                )
            return {"status":"imported","request_id":request_id,"receipt":committed['receipt'],
                    "imported_at_utc":committed['imported_at'],"reused":True}
        if job["state"]!="ACTIVE" or item["state"]!="WRITING":
            raise ValueError("Bulk request is not awaiting a draft")
        packet=json.loads(item["packet_json"])
        request=packet["request"]
        if request["request_id"]!=request_id or request["source_revision"]!=item["source_revision"]:
            raise ValueError("Bulk packet ID or source revision mismatch")
        found=[c for c in exchange.candidates(store) if exchange.target_key(c)==item["target_key"]]
        error=""
        if len(found)!=1 or found[0]["approved"]:
            error="Target missing or already imported"
        elif exchange.semantic_seal(store,found[0])!=item["source_seal"]:
            error="Historical source changed since snapshot"
        elif digest(exchange._packet(store,found[0],request_id)["context"])!=item["context_seal"]:
            error="Frozen authored/voice context changed since snapshot"
        elif any(row[0]!=request_id for row in store.db.execute(
            """SELECT request_id FROM writing_exchange_requests
               WHERE target_key=? AND state IN ('PENDING','DEFERRED','HOLD','IMPORTED')""",
            (item["target_key"],),
        )):
            error="Conflicting normal Exchange request; no bulk import"
        if error:
            with store.db:
                store.db.execute(
                    "UPDATE historical_backfill_items SET state='HOLD',writer_text_md=?,error=? WHERE request_id=?",
                    (text,error,request_id),
                )
            return {"status":"held","request_id":request_id,"error":error}
        bridge=store.db.execute(
            "SELECT * FROM writing_exchange_requests WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if bridge is None:
            candidate=json.loads(item["snapshot_json"])
            from writing_waterfall import dependencies
            all_candidates=exchange.candidates(store)
            dep,missing=dependencies(store,all_candidates)
            reference=continuity(store,found[0],dep,all_candidates)
            if exchange.revision(found[0],reference,store)!=item["source_revision"]:
                with store.db:
                    store.db.execute(
                        "UPDATE historical_backfill_items SET state='HOLD',writer_text_md=?,error=? WHERE request_id=?",
                        (text,"Dependency source revision changed before import",request_id),
                    )
                return {"status":"held","request_id":request_id,
                        "error":"Dependency source revision changed before import"}
            with store.db:
                store.db.execute(
                    """INSERT INTO writing_exchange_requests
                       (request_id,target_key,packet_json,target_json,source_revision,
                        state,created_at,policy_version,queue_rank,dependencies_json)
                       VALUES(?,?,?,?,?,'PENDING',?,?,?,?)""",
                    (request_id,item["target_key"],item["packet_json"],
                     item["snapshot_json"],item["source_revision"],
                     item["created_at"],VERSION,-1,packed(reference)),
                )
        elif bridge["source_revision"]!=item["source_revision"]:
            raise ValueError("Existing import bridge has a different source revision")
        # No transaction is open here. The canonical exchange importer owns its
        # transaction and retains hashes, receipts and stale-source rejection.
        canonical=dict(
            request_id=request_id,source_revision=item["source_revision"],
            writer_text_md=text,writer_note=payload.get("writer_note",""),
            completed_at_utc=payload.get("completed_at_utc",""),
            status="READY",
        )
        result=exchange.deliver(store,canonical)
        with store.db:
            store.db.execute(
                """UPDATE historical_backfill_items
                   SET state=?,writer_text_md=?,writer_note=?,error=?,
                       receipt=?,imported_at=?
                   WHERE request_id=?""",
                ("IMPORTED" if result["status"]=="imported" else "HOLD",
                 text,canonical["writer_note"],result.get("error") or "",
                 result.get("receipt"),result.get("imported_at_utc"),request_id),
            )
        return result


def close(store, job_id, *, finalize_unresolved=False):
    with store._lock:
        job=_job(store,job_id)
        if job["state"] not in OPEN:
            return summary(store,job_id)
        states=Counter(x["state"] for x in _items(store,job_id))
        if finalize_unresolved and states["PENDING"]:
            # Explicit operator action, never part of the ordinary poll loop.
            # Do not terminate or overwrite drafts already being written.
            if states["WRITING"]:
                raise ValueError("Cannot finalize while claimed WRITING drafts remain")
            candidates=exchange.candidates(store)
            _,_,blocked=plan(store,candidates)
            with store.db:
                for item in _items(store,job_id):
                    if item["state"]!="PENDING":
                        continue
                    reasons=blocked.get(item["target_key"])
                    explanation="; ".join(reasons) if reasons else (
                        "Unprocessed at operator-requested early close")
                    store.db.execute(
                        """UPDATE historical_backfill_items SET state='HOLD',error=?
                           WHERE request_id=? AND state='PENDING'""",
                        (explanation,item["request_id"]),
                    )
            states=Counter(x["state"] for x in _items(store,job_id))
        if states["PENDING"] or states["WRITING"]:
            raise ValueError("Unresolved items remain; inspect blockers before closing")
        final="COMPLETED_WITH_ERRORS" if states["HOLD"] or states["SKIPPED"] else "COMPLETED"
        with store.db:
            store.db.execute(
                "UPDATE historical_backfill_jobs SET state=?,closed_at=? WHERE job_id=?",
                (final,now(),job_id),
            )
        return summary(store,job_id)


def cancel(store,job_id):
    with store._lock:
        job=_job(store,job_id)
        if job["state"] not in OPEN:
            raise ValueError("Only open jobs can be cancelled")
        with store.db:
            store.db.execute(
                "UPDATE historical_backfill_jobs SET state='CANCELLED',closed_at=? WHERE job_id=?",
                (now(),job_id),
            )
        return summary(store,job_id)


def request_manual_revision(store,job_id,request_id,receipt):
    """An imported bulk entry returns to the NORMAL correction queue.

    The original import ID and receipt are never altered; the normal correction
    receives a fresh request ID and demands individual owner approval.
    """
    with store._lock:
        item=store.db.execute(
            "SELECT * FROM historical_backfill_items WHERE job_id=? AND request_id=?",
            (job_id,request_id),
        ).fetchone()
        if not item or item["state"]!="IMPORTED" or item["receipt"]!=receipt:
            raise ValueError("Imported item and exact receipt required")
    return exchange.request_revision(store,request_id,receipt)
