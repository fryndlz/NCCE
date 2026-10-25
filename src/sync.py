"""Persist already-read campaign Sheet snapshots and deterministic factual deltas.

The Google adapter belongs at the boundary and must remain read-only. This module
accepts normalized snapshots, records their provenance, and emits only mechanical
facts supported by consecutive snapshots.
"""
from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy

from diff import snapshot_event_drafts
from google_sheets import fetch_snapshot as fetch_live_snapshot

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


def _seed_baseline_snapshot(store, after):
    """Compare known seed fields with the first live read; new stats are baseline."""
    prior = store.latest_snapshot()
    if not prior or prior["payload"].get("snapshot_version") == after.get("snapshot_version"):
        return
    if not store.db.execute("SELECT 1 FROM fighter_events LIMIT 1").fetchone():
        return
    current_by_id = {str(g.get("gang_id")):g for g in (after.get("gangs") or {}).values()}
    before = {"snapshot_version":after.get("snapshot_version"), "captured_at":prior["captured_at"],
              "campaign":{}, "gangs":{}, "territories":[], "battles":[],
              "source_id":"baseline:snapshot-0001", "provenance_class":"mechanical_fact",
              "source_metadata":{"seed_bridge":True,"historical_occurrence_dates":"unknown"}}
    fields = {"Type":"type","Class":"class","Cost":"cost","XP":"xp","Kills":"kills",
              "Advancements":"advancements","Effects":"effects","Status":"status"}
    for row in store.db.execute("SELECT * FROM gangs WHERE active=1"):
        gang = dict(row); source = current_by_id.get(str(gang["gang_id"]),{})
        g = deepcopy(source)
        g.update({k:gang.get(k) for k in ("gang_id","name","gang_type","credits","reputation","rating","alignment","colour")})
        current_fighters = {_normal_key(name):record for name,record in (source.get("fighters") or {}).items()}
        g["fighters"] = {}
        for frow in store.db.execute("SELECT * FROM fighters WHERE gang_id=?",(gang["gang_id"],)):
            fighter = dict(frow)
            record = deepcopy(current_fighters.get(_normal_key(fighter["name"]),{}))
            record.update({field:(fighter.get(column) or None) if field in {"Advancements","Effects"} else fighter.get(column) for field,column in fields.items()})
            record["Name"] = fighter["name"]
            g["fighters"][fighter["name"]] = record
        before["gangs"][gang["name"]] = g
    before["battles"] = [dict(row) for row in store.db.execute("SELECT * FROM battles WHERE active=1")]
    for row in store.db.execute("SELECT * FROM territories WHERE active=1"):
        t = dict(row)
        before["territories"].append({"Territory":t["territory"],"Gang ID":t["gang_id"],"Gang":t["gang_name"],"Card":t["card"]})
    store.save_snapshot(before)


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
    _seed_baseline_snapshot(store, payload)
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
        if draft["event_type"] in {"battle_record_corrected", "battle_record_removed"}:
            if prior:
                supersedes_event_id = prior["supersedes_event_id"]
                correction_reason = prior["correction_reason"]
            else:
                supersedes_event_id = store.latest_event_by_source_locator(draft["source_locator"])
                correction_reason = (
                    "Authoritative Sheet battle row was removed in a later snapshot"
                    if draft["event_type"] == "battle_record_removed"
                    else "Authoritative Sheet battle row changed in a later snapshot"
                )
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


def sync_live_sheet(store) -> dict:
    """Fetch, ledger, and project one read-only snapshot of the live campaign Sheet."""
    snapshot = fetch_live_snapshot()
    with store._lock:
        ingested = ingest_snapshot(store, snapshot)
        projection = store.project_snapshot(snapshot)
        from story_engine import regenerate
        narrative = regenerate(store, ambient=True)
    return {**ingested, "projection": projection, "narrative": narrative, "source_metadata": snapshot.get("source_metadata", {})}
