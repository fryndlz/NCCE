"""Persist already-read campaign Sheet snapshots and deterministic factual deltas.

The Google adapter belongs at the boundary and must remain read-only. This module
accepts normalized snapshots, records their provenance, and emits only mechanical
facts supported by consecutive snapshots.
"""
from __future__ import annotations

from datetime import datetime, timezone

from diff import snapshot_event_drafts

SHEET_SOURCE_ID = "live:campaign-sheet"
SHEET_ID = "1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00"
SHEET_URI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"


def _normal_key(value: str) -> str:
    # Keep entity identity aligned with migration backfill and diff.py.
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def _subject_entity(store, subject: dict, source_id: str) -> dict:
    entity_type = subject["entity_type"]
    entity_key = subject["entity_key"]
    if entity_type == "territory":
        entity_key = _normal_key(entity_key)
    entity_id = store.register_entity(
        entity_type,
        entity_key,
        subject["display_name"],
        "mechanical_fact",
        source_id,
    )
    return {"entity_id": entity_id, "role": subject.get("role", "affected")}


def ingest_snapshot(store, snapshot: dict, source_id: str = SHEET_SOURCE_ID) -> dict:
    """Save a normalized snapshot and its idempotent event diff.

    `captured_at` is observation time only. Changes without an explicit source date
    retain `occurred_at=None`; the ingester never invents when they happened.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be an object")
    observed_at = snapshot.get("captured_at") or datetime.now(timezone.utc).isoformat()
    store.record_source(
        source_id,
        "campaign_sheet",
        "mechanical_fact",
        "Authoritative campaign Google Sheet",
        source_uri=SHEET_URI,
    )
    payload = dict(snapshot)
    payload.update({
        "captured_at": observed_at,
        "source_id": source_id,
        "provenance_class": "mechanical_fact",
    })
    snapshot_id, snapshot_created = store.save_snapshot(payload)
    target = store.snapshot(snapshot_id)
    if target is None:
        raise RuntimeError(f"Saved snapshot {snapshot_id} could not be read back")
    before = store.snapshot_before(snapshot_id)
    previous = before["payload"] if before else None
    drafts = snapshot_event_drafts(previous, target["payload"], snapshot_id)

    created_events = []
    for draft in drafts:
        subjects = [_subject_entity(store, item, source_id) for item in draft["subjects"]]
        prior = store.event_by_key(draft["event_key"])
        supersedes_event_id = None
        correction_reason = None
        if draft["event_type"] == "battle_record_corrected":
            if prior:
                supersedes_event_id = prior["supersedes_event_id"]
                correction_reason = prior["correction_reason"]
            else:
                supersedes_event_id = store.latest_event_by_source_locator(draft["source_locator"])
                correction_reason = "Authoritative Sheet battle row changed in a later snapshot"
        event_id, created = store.record_event(
            draft["event_key"],
            draft["event_type"],
            draft["payload"],
            "mechanical_fact",
            source_id=source_id,
            source_locator=draft["source_locator"],
            occurred_at=draft["occurred_at"],
            observed_at=target["payload"]["captured_at"],
            confidence=draft["confidence"],
            from_snapshot_id=before["id"] if before else None,
            to_snapshot_id=snapshot_id,
            subjects=subjects,
            supersedes_event_id=supersedes_event_id,
            correction_reason=correction_reason,
        )
        if created:
            created_events.append(event_id)

    return {
        "snapshot_id": snapshot_id,
        "snapshot_created": snapshot_created,
        "events_created": created_events,
        "events_considered": len(drafts),
    }
