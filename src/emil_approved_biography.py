"""One-shot recovery of Emil's explicitly approved biography.

The earlier overlength delivery left the original request in backend HOLD.
The replacement is finite and owner-authorized: a temporary environment
manifest supplies the exact approved Markdown. Only this specific request
may be reopened, and only after all existing canonical source checks pass.
No other holds or requests are modified.
"""
from __future__ import annotations

import json
import os
from uuid import UUID

import exchange_automation

ENV = "NCCE_EMIL_APPROVED_BIO_JSON"
REQUEST_ID = "16ba7351-36ce-48e0-8e9c-082a2c279ec3"
HOLD_PREFIX = "Fighter biography exceeds the owner-approved 2,300-character hard cap"


def parse(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 12000:
        raise ValueError("Emil manifest invalid length")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {
        "request_id", "source_revision", "approval", "text"
    }:
        raise ValueError("Emil manifest fields mismatch")
    if str(UUID(payload["request_id"])) != REQUEST_ID or payload["request_id"] != REQUEST_ID:
        raise ValueError("Emil request ID mismatch")
    if payload["approval"] != "owner_approved_exact_emil_biography_2026-11-14":
        raise ValueError("Owner approval marker mismatch")
    if not isinstance(payload["source_revision"], str) or not payload["source_revision"].startswith("sha256:"):
        raise ValueError("Source revision missing")
    text = payload["text"]
    if not isinstance(text, str) or not text.strip() or len(text) > 2300 or len(text) < 300:
        raise ValueError("Biography must be 300–2,300 characters, Markdown included")
    return payload


def apply(store, raw):
    payload = parse(raw)
    rid = payload["request_id"]
    with store._lock:
        row = store.db.execute(
            "SELECT * FROM writing_exchange_requests WHERE request_id=?", (rid,)
        ).fetchone()
        if row is None:
            raise ValueError("Approved Emil request not found")
        if row["source_revision"] != payload["source_revision"] or row["revision_of"]:
            raise ValueError("Original request identity or source revision changed")
        packet = json.loads(row["packet_json"])
        req = packet.get("request", {})
        if req.get("form") != "fighter_biography" or req.get("entity_key") != "100" or req.get("request_id") != rid:
            raise ValueError("Not Emil's original biography request")
        if row["state"] == "IMPORTED":
            if row["raw_markdown"] != payload["text"] or not row["receipt"]:
                raise ValueError("Already-imported biography differs from approved text")
            return {"status": "already_imported", "request_id": rid, "receipt": row["receipt"]}
        if row["state"] != "HOLD" or not (row["error"] or "").startswith(HOLD_PREFIX):
            raise ValueError("Emil is not held for the documented overlength reason")
        if row["receipt"] or row["imported_at"]:
            raise ValueError("Held request unexpectedly has a published receipt")
        candidates = [c for c in exchange_automation.candidates(store)
                      if exchange_automation.target_key(c) == row["target_key"]]
        if len(candidates) != 1:
            raise ValueError("Biography target missing or ambiguous")
        candidate = candidates[0]
        if candidate["form"] != "fighter_biography" or candidate["entity_type"] != "fighter":
            raise ValueError("Candidate is not a fighter biography")
        if candidate["approved"] or not exchange_automation.source_matches(store, candidate, row):
            raise ValueError("Emil source changed or approved prose already exists")
        # This transition only lifts the exact, historically documented length
        # rejection. Never change the sealed source revision or prior audit.
        with store.db:
            changed = store.db.execute(
                "UPDATE writing_exchange_requests SET state='PENDING',error='' "
                "WHERE request_id=? AND state='HOLD' AND error=?",
                (rid, row["error"]),
            ).rowcount
            if changed != 1:
                raise ValueError("Emil hold changed during recovery")
    # Canonical delivery rechecks source, exact target, caps and audit receipts.
    result = exchange_automation.deliver(store, {
        "request_id": rid,
        "status": "READY",
        "source_revision": payload["source_revision"],
        "writer_text_md": payload["text"],
        "writer_note": "Exact Emil biography approved by owner 2026-11-14; recovered previous overlength HOLD",
        "completed_at_utc": "",
    })
    return {
        "status": result["status"],
        "request_id": rid,
        "receipt": result.get("receipt"),
        "error": result.get("error"),
    }


def apply_from_environment(store):
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    return apply(store, raw)
