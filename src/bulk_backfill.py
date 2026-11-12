"""Finite, owner-authorized historical fighter-memory backfill.

Bulk records are segregated from the ordinary five-item Exchange outbox.
The final commit deliberately reuses exchange_automation.deliver and its source
revision, target identity, audit, backup, replay and receipt protections.
No model is called here and no job can authorize itself.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4
import json
import re

import exchange_automation as exchange
from writing_exchange import packed

TERMINAL = {"IMPORTED", "ESCALATED"}
ACTIVE_JOBS = {"PREPARED", "AUTHORIZED", "RUNNING"}
MAX_PAGE = 50
MAX_CHARS = 350


def _job(store, job_id):
    row = store.db.execute(
        "SELECT * FROM writing_bulk_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        raise ValueError("Unknown historical backfill job")
    return dict(row)


def _item(store, job_id, request_id):
    row = store.db.execute(
        "SELECT * FROM writing_bulk_items WHERE job_id=? AND request_id=?",
        (job_id, request_id),
    ).fetchone()
    if not row:
        raise ValueError("Request is not part of this backfill snapshot")
    return dict(row)


def _audit(store, job_id, request_id, action, detail=""):
    store.db.execute(
        """INSERT INTO writing_bulk_audit(job_id,request_id,action,detail,at_utc)
           VALUES(?,?,?,?,?)""",
        (job_id, request_id, action, str(detail)[:2000], exchange.now()),
    )


def is_reserved(store, key):
    """Do not allow the normal producer to claim an unfinished bulk target."""
    return bool(store.db.execute(
        """SELECT 1 FROM writing_bulk_items
           WHERE target_key=? AND state IN ('PENDING','WRITING','HELD')
           LIMIT 1""", (key,)
    ).fetchone())


def list_jobs(store):
    jobs = [dict(r) for r in store.db.execute(
        "SELECT * FROM writing_bulk_jobs ORDER BY created_at DESC"
    )]
    for job in jobs:
        counts = store.db.execute(
            """SELECT state,count(*) AS n FROM writing_bulk_items
               WHERE job_id=? GROUP BY state""", (job["job_id"],)
        ).fetchall()
        job["counts"] = {r["state"]: r["n"] for r in counts}
    return jobs


def get_job(store, job_id):
    return next((j for j in list_jobs(store) if j["job_id"] == job_id), _job(store, job_id))


def create_job(store, gang_id):
    """Snapshot existing eligible targets, not a live query that can grow later.

    PREPARED is *not* consent to auto-import. Approval is a separate operation.
    Already claimed normal work stays entirely in the normal lane.
    """
    from writing_waterfall import order
    if not isinstance(gang_id, str) or not gang_id.strip() or len(gang_id) > 150:
        raise ValueError("Exact NCCE gang_id is required")
    with store._lock:
        if store.db.in_transaction:
            raise RuntimeError("Backfill snapshot needs its own transaction")
        gang = store.db.execute(
            "SELECT gang_id,name,gang_type FROM gangs WHERE gang_id=?",
            (gang_id,),
        ).fetchone()
        if not gang:
            raise ValueError("Unknown gang ID; never resolve by approximate name")
        fighter_ids = {
            str(row["id"])
            for row in store.db.execute(
                "SELECT id FROM fighters WHERE gang_id=?", (gang_id,)
            )
        }
        available = [
            c for c in exchange.candidates(store)
            if c["form"] == "fighter_memory"
            and c["entity_type"] == "fighter"
            and c["entity_key"] in fighter_ids
            and not c["approved"]
        ]
        available.sort(key=order)
        job_id = str(uuid4())
        created = []
        skipped = 0
        with store.db:
            store.db.execute(
                """INSERT INTO writing_bulk_jobs
                   (job_id,gang_id,gang_name,state,approval_policy,
                    snapshot_count,skipped_count,created_at)
                   VALUES(?,?,?,'PREPARED','MANUAL',0,0,?)""",
                (job_id, gang_id, gang["name"], exchange.now()),
            )
            for c in available:
                key = exchange.target_key(c)
                # Existing requests include imports, manual holds and revisions.
                # Bulk must never acquire, reset or overwrite those identities.
                if store.db.execute(
                    "SELECT 1 FROM writing_exchange_requests WHERE target_key=? LIMIT 1",
                    (key,),
                ).fetchone():
                    skipped += 1
                    continue
                rid = str(uuid4())
                packet = exchange._packet(store, c, rid)
                source_seal = exchange.seal(c)
                packet["request"]["source_revision"] = source_seal
                packet["context"].append({
                    "section": "brief", "provenance": "instruction",
                    "source_ref": "owner-authorized finite historical backfill",
                    "event_at_utc": "", "source_event_ids": "",
                    "text": (
                        "This request belongs to a finite backfill job. Draft from "
                        "the sealed mechanical evidence and approved character canon. "
                        "Preserve chronology and voice. A job-specific owner authorization "
                        "may permit automatic publication after checks, without changing "
                        "the default manual approval of ordinary Exchange requests. "
                        "Fighter memory: at most 350 characters including Markdown title."
                    ),
                })
                store.db.execute(
                    """INSERT INTO writing_exchange_requests
                       (request_id,target_key,packet_json,target_json,source_revision,
                        state,created_at,policy_version,queue_rank,dependencies_json,
                        bulk_job_id)
                       VALUES(?,?,?,?,?,'DEFERRED',?,1,?,'[]',?)""",
                    (
                        rid, key, packed(packet),
                        packed({"target": c, "original": exchange.projection(store, c)}),
                        source_seal, exchange.now(), len(created), job_id,
                    ),
                )
                store.db.execute(
                    """INSERT INTO writing_bulk_items
                       (job_id,request_id,fighter_id,sequence,target_key,source_seal,
                        state,updated_at)
                       VALUES(?,?,?,?,?,?,'PENDING',?)""",
                    (
                        job_id, rid, int(c["entity_key"]), len(created) + 1,
                        key, source_seal, exchange.now(),
                    ),
                )
                created.append(rid)
            store.db.execute(
                """UPDATE writing_bulk_jobs SET snapshot_count=?,skipped_count=?
                   WHERE job_id=?""", (len(created), skipped, job_id)
            )
            _audit(store, job_id, None, "SNAPSHOT", f"{len(created)} items; {skipped} existing requests skipped")
    return get_job(store, job_id)


def authorize_job(store, job_id, expected_count):
    """Explicit, scoped owner approval; the default always stays MANUAL."""
    with store._lock:
        with store.db:
            job = _job(store, job_id)
            if job["state"] != "PREPARED":
                raise ValueError("Only a prepared job may be authorized")
            if type(expected_count) is not int or expected_count != job["snapshot_count"]:
                raise ValueError("Backfill snapshot count changed or was not confirmed")
            if expected_count == 0:
                store.db.execute(
                    "UPDATE writing_bulk_jobs SET state='COMPLETED',closed_at=? WHERE job_id=?",
                    (exchange.now(), job_id),
                )
                _audit(store, job_id, None, "EMPTY", "No unclaimed eligible memories")
            else:
                store.db.execute(
                    """UPDATE writing_bulk_jobs
                       SET state='AUTHORIZED',approval_policy='AUTO',authorized_at=?
                       WHERE job_id=?""", (exchange.now(), job_id)
                )
                _audit(store, job_id, None, "AUTHORIZE", "Owner accepted this finite snapshot")
    return get_job(store, job_id)


def _continuity(store, item):
    """Accepted earlier bulk prose, a fictional continuity lens, not new facts."""
    previous = store.db.execute(
        """SELECT q.packet_json,q.raw_markdown FROM writing_bulk_items i
           JOIN writing_exchange_requests q USING(request_id)
           WHERE i.job_id=? AND i.fighter_id=? AND i.sequence<?
             AND i.state='IMPORTED'
           ORDER BY i.sequence DESC LIMIT 3""",
        (item["job_id"], item["fighter_id"], item["sequence"]),
    ).fetchall()
    result = []
    for row in reversed(previous):
        packet = exchange.load(row["packet_json"])
        result.append({
            "form": "fighter_memory",
            "title": packet["request"]["title"],
            "text": row["raw_markdown"],
        })
    return result


def _packet_for_item(store, item):
    request = store.db.execute(
        "SELECT packet_json FROM writing_exchange_requests WHERE request_id=?",
        (item["request_id"],),
    ).fetchone()
    packet = deepcopy(exchange.load(request["packet_json"]))
    references = _continuity(store, item)
    if references:
        packet["context"].append({
            "section": "existing_fiction",
            "provenance": "accepted_generated_fiction",
            "source_ref": "Previously imported memories from this same backfill snapshot",
            "event_at_utc": "", "source_event_ids": "",
            "text": packed(references),
        })
    return packet


def claim(store, job_id, limit=25, known_request_ids=()):
    """Claim the next batch and recover interrupted Sheet publications.

    A lost transport response must not strand a WRITING item forever. The
    client supplies IDs already persisted to Bulk Items, so only genuinely
    missing claims are re-exposed. No saved draft or source is overwritten.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        raise ValueError("Claim limit must be 1–50")
    if not isinstance(known_request_ids, (list, tuple)) or len(known_request_ids) > 10000:
        raise ValueError("Invalid already-published bulk ID list")
    known = set(known_request_ids)
    if any(not isinstance(x, str) or len(x) > 128 for x in known):
        raise ValueError("Invalid bulk request ID")
    with store._lock:
        with store.db:
            job = _job(store, job_id)
            if job["state"] not in ("AUTHORIZED", "RUNNING"):
                raise ValueError("Job needs explicit authorization before writing")
            interrupted = [
                dict(r) for r in store.db.execute(
                    """SELECT * FROM writing_bulk_items
                       WHERE job_id=? AND state='WRITING' ORDER BY sequence""",
                    (job_id,)
                ) if r["request_id"] not in known
            ][:limit]
            remaining = limit - len(interrupted)
            rows = store.db.execute(
                """SELECT i.* FROM writing_bulk_items i
                   WHERE i.job_id=? AND i.state='PENDING'
                   AND NOT EXISTS (
                     SELECT 1 FROM writing_bulk_items prior
                     WHERE prior.job_id=i.job_id AND prior.fighter_id=i.fighter_id
                       AND prior.sequence<i.sequence AND prior.state!='IMPORTED'
                   )
                   ORDER BY i.sequence LIMIT ?""",
                (job_id, remaining),
            ).fetchall() if remaining else []
            new_items = [dict(r) for r in rows]
            for item in new_items:
                store.db.execute(
                    """UPDATE writing_bulk_items
                       SET state='WRITING',updated_at=?
                       WHERE request_id=? AND state='PENDING'""",
                    (exchange.now(), item["request_id"]),
                )
            if new_items:
                store.db.execute(
                    "UPDATE writing_bulk_jobs SET state='RUNNING' WHERE job_id=?",
                    (job_id,),
                )
                _audit(store, job_id, None, "CLAIM", f"{len(new_items)} new items")
            if interrupted:
                _audit(store, job_id, None, "RECOVER", f"{len(interrupted)} unpublished claims")
            return [
                {"job_id": job_id, "request_id": item["request_id"],
                 "sequence": item["sequence"], "fighter_id": item["fighter_id"],
                 "status": "WRITING", "packet": _packet_for_item(store, item)}
                for item in interrupted + new_items
            ]


def list_items(store, job_id, after_sequence=0, limit=25, include_packets=True):
    _job(store, job_id)
    if type(after_sequence) is not int or after_sequence < 0:
        raise ValueError("Invalid sequence cursor")
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        raise ValueError("Page limit must be 1–50")
    rows = [
        dict(r) for r in store.db.execute(
            """SELECT i.*,q.source_revision,q.imported_at
               FROM writing_bulk_items i
               JOIN writing_exchange_requests q USING(request_id)
               WHERE i.job_id=? AND i.sequence>?
               ORDER BY i.sequence LIMIT ?""",
            (job_id, after_sequence, limit),
        )
    ]
    for item in rows:
        if include_packets and item["state"] in ("PENDING", "WRITING", "HELD"):
            item["packet"] = _packet_for_item(store, item)
    return rows


def _validate_text(text):
    if not isinstance(text, str) or not text.strip():
        return "Complete memory text is required"
    if len(text) > MAX_CHARS:
        return f"Fighter memory exceeds {MAX_CHARS} characters including Markdown"
    if not re.match(r"\A\*\*[^*\n]{2,100}\*\*\n\n\S", text):
        return "Expected a bold Markdown title, a blank line and memory prose"
    return ""


def submit(store, job_id, request_id, source_revision, text, note=""):
    """Validate a staged draft, then use the *existing* exchange importer."""
    with store._lock:
        job = _job(store, job_id)
        item = _item(store, job_id, request_id)
        request = store.db.execute(
            "SELECT * FROM writing_exchange_requests WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if item["state"] == "IMPORTED":
            if text == request["raw_markdown"] and source_revision == request["source_revision"]:
                return {"status": "imported", "request_id": request_id,
                        "receipt": item["receipt"], "reused": True}
            raise ValueError("Already imported; request a versioned manual correction")
        if job["state"] not in ("AUTHORIZED", "RUNNING") or job["approval_policy"] != "AUTO":
            raise ValueError("No active owner-authorized auto-approval for this job")
        if item["state"] not in ("PENDING", "WRITING"):
            raise ValueError("This item is held or escalated; resolve before retry")
        earlier = store.db.execute(
            """SELECT 1 FROM writing_bulk_items WHERE job_id=? AND fighter_id=?
               AND sequence<? AND state!='IMPORTED' LIMIT 1""",
            (job_id, item["fighter_id"], item["sequence"]),
        ).fetchone()
        if earlier:
            raise ValueError("Earlier memories for this fighter must be imported first")
        error = _validate_text(text)
        if source_revision != request["source_revision"]:
            error = "Source revision does not match this snapshot"
        if error:
            with store.db:
                store.db.execute(
                    """UPDATE writing_bulk_items SET state='HELD',writer_text_md=?,
                       error=?,updated_at=? WHERE request_id=?""",
                    (text if isinstance(text, str) else "", error, exchange.now(), request_id),
                )
                _audit(store, job_id, request_id, "HOLD", error)
            return {"status": "held", "request_id": request_id, "error": error}
        payload = {
            "request_id": request_id, "status": "READY",
            "source_revision": source_revision,
            "writer_text_md": text, "writer_note": str(note)[:2000],
        }
        # A crash after the importer commits is safe: its exact delivery receipt
        # is idempotent, and a retry reconciles the item rather than creating prose.
        result = exchange.deliver(store, payload, bulk_internal=True)
        with store.db:
            store.db.execute(
                """UPDATE writing_bulk_items SET state=?,writer_text_md=?,
                   receipt=?,error=?,updated_at=? WHERE request_id=?""",
                (
                    "IMPORTED" if result["status"] == "imported" else "HELD",
                    text, result.get("receipt"), result.get("error", ""), exchange.now(),
                    request_id,
                ),
            )
            _audit(store, job_id, request_id,
                   "IMPORTED" if result["status"] == "imported" else "HOLD",
                   result.get("receipt") or result.get("error", ""))
        return result


def retry_held(store, job_id, request_id):
    """Reopen a held *draft*, never an imported record; keep the same identity."""
    with store._lock:
        with store.db:
            job = _job(store, job_id)
            item = _item(store, job_id, request_id)
            if job["state"] not in ("AUTHORIZED", "RUNNING") or item["state"] != "HELD":
                raise ValueError("Only a held draft in an active job may be retried")
            request = store.db.execute(
                "SELECT * FROM writing_exchange_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            c = [
                c for c in exchange.candidates(store)
                if exchange.target_key(c) == item["target_key"]
            ]
            if len(c) != 1 or not exchange.source_matches(store, c[0], request):
                raise ValueError("Source changed; escalate for manual reconciliation")
            if request["state"] not in ("HOLD", "DEFERRED"):
                raise ValueError("Bulk import target is not retryable")
            store.db.execute(
                """UPDATE writing_exchange_requests
                   SET state='DEFERRED',error='' WHERE request_id=?""",
                (request_id,),
            )
            store.db.execute(
                """UPDATE writing_bulk_items
                   SET state='PENDING',error='',updated_at=? WHERE request_id=?""",
                (exchange.now(), request_id),
            )
            _audit(store, job_id, request_id, "RETRY", "Preserved request ID and audit")
    return _item(store, job_id, request_id)


def escalate(store, job_id, request_id):
    """Return an unimported item to the normal manual-approval lane."""
    with store._lock:
        with store.db:
            item = _item(store, job_id, request_id)
            if item["state"] not in ("HELD", "PENDING", "WRITING"):
                raise ValueError("Only an unimported item can be escalated")
            request = store.db.execute(
                "SELECT * FROM writing_exchange_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if not request or request["bulk_job_id"] != job_id:
                raise ValueError("Bulk request identity changed")
            store.db.execute(
                """UPDATE writing_exchange_requests
                   SET bulk_job_id=NULL,state='DEFERRED',error=''
                   WHERE request_id=? AND state IN ('DEFERRED','HOLD')""",
                (request_id,),
            )
            store.db.execute(
                """UPDATE writing_bulk_items
                   SET state='ESCALATED',updated_at=? WHERE request_id=?""",
                (exchange.now(), request_id),
            )
            _audit(store, job_id, request_id, "ESCALATE", "Normal Exchange; manual owner approval")
    return _item(store, job_id, request_id)


def correct_import(store, job_id, request_id, expected_receipt):
    """An imported memory's correction uses the normal versioned review API."""
    item = _item(store, job_id, request_id)
    if item["state"] != "IMPORTED" or item["receipt"] != expected_receipt:
        raise ValueError("Exact imported item receipt required")
    result = exchange.request_revision(store, request_id, expected_receipt)
    with store._lock, store.db:
        _audit(store, job_id, request_id, "CORRECTION", result["request_id"])
    return result


def finish(store, job_id):
    """Snapshot terminates; unresolved draft errors must be escalated first."""
    with store._lock:
        with store.db:
            job = _job(store, job_id)
            if job["state"] not in ("AUTHORIZED", "RUNNING"):
                raise ValueError("Job is not active")
            states = [
                r["state"] for r in store.db.execute(
                    "SELECT state FROM writing_bulk_items WHERE job_id=?", (job_id,)
                )
            ]
            if any(s not in TERMINAL for s in states):
                raise ValueError("Unfinished items remain; import or escalate them")
            state = "COMPLETED_WITH_ERRORS" if "ESCALATED" in states else "COMPLETED"
            store.db.execute(
                "UPDATE writing_bulk_jobs SET state=?,closed_at=? WHERE job_id=?",
                (state, exchange.now(), job_id),
            )
            _audit(store, job_id, None, "FINISH", state)
    return get_job(store, job_id)


def cancel(store, job_id):
    """Release unimported requests back to normal without losing their UUIDs."""
    with store._lock:
        with store.db:
            job = _job(store, job_id)
            if job["state"] not in ACTIVE_JOBS:
                raise ValueError("Only an active job can be cancelled")
            rows = store.db.execute(
                "SELECT * FROM writing_bulk_items WHERE job_id=? AND state!='IMPORTED'",
                (job_id,),
            ).fetchall()
            for item in rows:
                store.db.execute(
                    """UPDATE writing_exchange_requests
                       SET bulk_job_id=NULL,state='DEFERRED',error=''
                       WHERE request_id=? AND state IN ('DEFERRED','HOLD')""",
                    (item["request_id"],),
                )
                store.db.execute(
                    """UPDATE writing_bulk_items SET state='ESCALATED',updated_at=?
                       WHERE request_id=?""", (exchange.now(), item["request_id"])
                )
                _audit(store, job_id, item["request_id"], "CANCEL_RELEASE", "Normal review")
            store.db.execute(
                "UPDATE writing_bulk_jobs SET state='CANCELLED',closed_at=? WHERE job_id=?",
                (exchange.now(), job_id),
            )
            _audit(store, job_id, None, "CANCEL", f"Released {len(rows)} unimported requests")
    return get_job(store, job_id)


def audit(store, job_id, limit=100):
    _job(store, job_id)
    return [
        dict(r) for r in store.db.execute(
            """SELECT * FROM writing_bulk_audit WHERE job_id=?
               ORDER BY audit_id DESC LIMIT ?""", (job_id, min(max(int(limit), 1), 500))
        )
    ]
