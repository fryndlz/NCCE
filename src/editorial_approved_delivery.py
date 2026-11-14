"""One-shot owner-approved fighter-memory correction delivery.

A JSON manifest is injected temporarily through Render as
NCCE_APPROVED_CORRECTIONS_JSON. Each item must match an existing versioned
correction request, its imported parent, and the author's approved Markdown.
All publication uses exchange_automation.deliver (canonical source/receipt/
text validation), never writes to prose tables directly. No scheduled work.
"""
from __future__ import annotations

import hashlib
import json
import os
from uuid import UUID

import exchange_automation

ENV_KEY = "NCCE_APPROVED_CORRECTIONS_JSON"
EXPECTED_COUNT = 35
MAX_BYTES = 80000


def _canonical_uuid(value):
    if not isinstance(value, str):
        raise ValueError("Expected canonical UUID string")
    parsed = str(UUID(value))
    if value != parsed:
        raise ValueError("Noncanonical UUID")
    return parsed


def parse_manifest(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Approved manifest length invalid")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid approved correction manifest") from exc
    if not isinstance(data, dict) or set(data) != {"approval", "items"} or data["approval"] != "owner_approved_2026-11-14":
        raise ValueError("Missing exact owner approval declaration")
    items = data["items"]
    if not isinstance(items, list) or len(items) != EXPECTED_COUNT:
        raise ValueError("Approved correction manifest must cover exactly 35 requests")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"revision_id", "parent_id", "parent_receipt", "text", "text_sha256"}:
            raise ValueError("Unexpected correction item fields")
        rid = _canonical_uuid(item["revision_id"])
        pid = _canonical_uuid(item["parent_id"])
        if rid == pid or rid in seen:
            raise ValueError("Duplicate or self-referential correction request")
        seen.add(rid)
        txt = item["text"]
        if not isinstance(txt, str) or not txt.strip() or len(txt) > 350:
            raise ValueError("Invalid fighter-memory text length")
        if item["text_sha256"] != hashlib.sha256(txt.encode("utf-8")).hexdigest():
            raise ValueError("Approved prose snapshot hash mismatch")
        if not isinstance(item["parent_receipt"], str) or not item["parent_receipt"].startswith("exchange:" + pid + ":"):
            raise ValueError("Parent receipt mismatch")
    return items


def apply(store, raw):
    items = parse_manifest(raw)
    # Entire batch is preflighted before any publications. A real delivery can
    # still HOLD if the live source changed between preflight and publication.
    preflight = []
    for item in items:
        rid = item["revision_id"]
        rows = store.db.execute(
            "SELECT request_id,revision_of,expected_receipt,state,raw_markdown,receipt,source_revision,packet_json "
            "FROM writing_exchange_requests WHERE request_id=?", (rid,)
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("Missing or ambiguous correction request " + rid)
        row = dict(rows[0])
        if row["revision_of"] != item["parent_id"] or row["expected_receipt"] != item["parent_receipt"]:
            raise ValueError("Correction parent identity/receipt changed: " + rid)
        packet = json.loads(row["packet_json"])
        if packet.get("request", {}).get("form") != "fighter_memory":
            raise ValueError("Wrong correction form: " + rid)
        if row["state"] == "IMPORTED":
            if row["raw_markdown"] != item["text"] or not row["receipt"]:
                raise ValueError("Imported correction differs from approved text: " + rid)
        elif row["state"] not in ("PENDING", "DEFERRED"):
            raise ValueError("Correction not importable: " + rid + " state=" + row["state"])
        preflight.append((item, row))
    out = {"imported": [], "already_imported": [], "held": []}
    for item, row in preflight:
        rid = item["revision_id"]
        if row["state"] == "IMPORTED":
            out["already_imported"].append({"request_id": rid, "receipt": row["receipt"]})
            continue
        receipt = exchange_automation.deliver(store, {
            "request_id": rid, "status": "READY",
            "source_revision": row["source_revision"],
            "writer_text_md": item["text"],
            "writer_note": "Exact owner-approved Editorial Drafts snapshot, 2026-11-14",
            "completed_at_utc": "",
        })
        if receipt["status"] == "imported":
            out["imported"].append({"request_id": rid, "receipt": receipt["receipt"]})
        else:
            out["held"].append({"request_id": rid, "error": receipt.get("error", "")[:250]})
    return out


def apply_from_environment(store):
    raw = os.environ.get(ENV_KEY, "").strip()
    if not raw:
        return None
    # Log only identifiers and statuses; never log manuscript or the env value.
    return apply(store, raw)
