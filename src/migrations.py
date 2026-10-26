"""Forward-only SQLite migrations for the persistent story engine."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

SCHEMA_VERSION = 9
PROVENANCE_CLASSES = (
    "mechanical_fact",
    "player_authored",
    "canon_authored",
    "inference",
    "connective_fiction",
)
_PROVENANCE_SQL = "'mechanical_fact','player_authored','canon_authored','inference','connective_fiction'"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _normal_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    return re.sub(r"\s+", " ", value)


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def _add_column(db: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    if name not in _table_columns(db, table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _source(
    db: sqlite3.Connection,
    source_id: str,
    source_type: str,
    authority_class: str,
    title: str,
    source_uri: str | None,
    source_locator: str | None,
    retrieved_at: str | None,
    content_hash: str | None = None,
) -> str:
    db.execute(
        """INSERT OR IGNORE INTO provenance_sources
           (source_id,source_type,authority_class,title,source_uri,source_locator,retrieved_at,content_hash,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (source_id, source_type, authority_class, title, source_uri, source_locator, retrieved_at, content_hash, _now()),
    )
    existing = db.execute(
        "SELECT source_type,authority_class FROM provenance_sources WHERE source_id=?", (source_id,)
    ).fetchone()
    if existing["source_type"] != source_type or existing["authority_class"] != authority_class:
        raise ValueError(f"Provenance source identity collision: {source_id}")
    return source_id


def _entity(
    db: sqlite3.Connection,
    entity_type: str,
    entity_key: str,
    display_name: str,
    source_id: str,
    created_at: str,
) -> str:
    entity_id = _stable_id(f"{entity_type}:{entity_key}")
    db.execute(
        """INSERT OR IGNORE INTO entities
           (entity_id,entity_type,entity_key,display_name,provenance_class,source_id,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (entity_id, entity_type, entity_key, display_name, "mechanical_fact", source_id, created_at),
    )
    return entity_id


def _event(
    db: sqlite3.Connection,
    *,
    event_key: str,
    event_type: str,
    occurred_at: str | None,
    observed_at: str,
    source_id: str,
    source_locator: str,
    payload: dict,
    confidence: float,
) -> str:
    event_id = _stable_id(f"campaign-event:{event_key}")
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    db.execute(
        """INSERT OR IGNORE INTO campaign_events
           (event_id,event_key,event_type,occurred_at,observed_at,created_at,provenance_class,
            source_id,source_locator,payload_json,confidence)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (event_id, event_key, event_type, occurred_at, observed_at, _now(), "mechanical_fact",
         source_id, source_locator, payload_json, confidence),
    )
    existing = db.execute(
        "SELECT event_id,payload_json,event_type FROM campaign_events WHERE event_key=?", (event_key,)
    ).fetchone()
    if existing["payload_json"] != payload_json or existing["event_type"] != event_type:
        raise ValueError(f"Immutable campaign event key reused with different data: {event_key}")
    return existing["event_id"]


def _subject(db: sqlite3.Connection, event_id: str, entity_id: str, role: str) -> None:
    db.execute(
        "INSERT OR IGNORE INTO event_subjects(event_id,entity_id,role) VALUES(?,?,?)",
        (event_id, entity_id, role),
    )


def _evidence(
    db: sqlite3.Connection,
    *,
    artifact_type: str,
    artifact_key: str,
    evidence_role: str,
    created_at: str,
    event_id: str | None = None,
    source_id: str | None = None,
) -> None:
    db.execute(
        """INSERT INTO narrative_evidence
           (artifact_type,artifact_key,event_id,source_id,evidence_role,created_at)
           SELECT ?,?,?,?,?,? WHERE NOT EXISTS (
             SELECT 1 FROM narrative_evidence WHERE artifact_type=? AND artifact_key=?
               AND ifnull(event_id,'')=ifnull(?,'') AND ifnull(source_id,'')=ifnull(?,'')
               AND evidence_role=?
           )""",
        (artifact_type, artifact_key, event_id, source_id, evidence_role, created_at,
         artifact_type, artifact_key, event_id, source_id, evidence_role),
    )


def _create_foundation(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE provenance_sources(
             source_id TEXT PRIMARY KEY,
             source_type TEXT NOT NULL,
             authority_class TEXT NOT NULL CHECK(authority_class IN (""" + _PROVENANCE_SQL + """)),
             title TEXT NOT NULL,
             source_uri TEXT,
             source_locator TEXT,
             retrieved_at TEXT,
             content_hash TEXT,
             metadata_json TEXT NOT NULL DEFAULT '{}',
             created_at TEXT NOT NULL
           )"""
    )
    db.execute(
        """CREATE TABLE entities(
             entity_id TEXT PRIMARY KEY,
             entity_type TEXT NOT NULL CHECK(entity_type IN ('gang','fighter','territory','region','campaign')),
             entity_key TEXT NOT NULL,
             display_name TEXT NOT NULL,
             provenance_class TEXT NOT NULL CHECK(provenance_class IN (""" + _PROVENANCE_SQL + """)),
             source_id TEXT REFERENCES provenance_sources(source_id),
             created_at TEXT NOT NULL,
             retired_at TEXT,
             UNIQUE(entity_type,entity_key)
           )"""
    )
    db.execute(
        """CREATE TABLE campaign_events(
             event_id TEXT PRIMARY KEY,
             event_key TEXT NOT NULL UNIQUE,
             event_type TEXT NOT NULL,
             occurred_at TEXT,
             observed_at TEXT NOT NULL,
             created_at TEXT NOT NULL,
             provenance_class TEXT NOT NULL CHECK(provenance_class IN (""" + _PROVENANCE_SQL + """)),
             source_id TEXT REFERENCES provenance_sources(source_id),
             source_locator TEXT,
             from_snapshot_id INTEGER REFERENCES snapshots(id),
             to_snapshot_id INTEGER REFERENCES snapshots(id),
             payload_json TEXT NOT NULL,
             confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence >= 0.0 AND confidence <= 1.0),
             supersedes_event_id TEXT REFERENCES campaign_events(event_id),
             correction_reason TEXT
           )"""
    )
    db.execute(
        """CREATE TABLE event_subjects(
             event_id TEXT NOT NULL REFERENCES campaign_events(event_id),
             entity_id TEXT NOT NULL REFERENCES entities(entity_id),
             role TEXT NOT NULL,
             PRIMARY KEY(event_id,entity_id,role)
           )"""
    )
    db.execute(
        """CREATE TABLE narrative_evidence(
             evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
             artifact_type TEXT NOT NULL,
             artifact_key TEXT NOT NULL,
             event_id TEXT REFERENCES campaign_events(event_id),
             source_id TEXT REFERENCES provenance_sources(source_id),
             evidence_role TEXT NOT NULL,
             created_at TEXT NOT NULL,
             CHECK(event_id IS NOT NULL OR source_id IS NOT NULL)
           )"""
    )
    db.execute("CREATE INDEX campaign_events_time_idx ON campaign_events(occurred_at,observed_at)")
    db.execute("CREATE INDEX campaign_events_type_idx ON campaign_events(event_type,provenance_class)")
    db.execute("CREATE INDEX event_subjects_entity_idx ON event_subjects(entity_id,role)")
    db.execute("CREATE INDEX narrative_evidence_artifact_idx ON narrative_evidence(artifact_type,artifact_key)")
    db.execute(
        """CREATE TRIGGER campaign_events_immutable_update BEFORE UPDATE ON campaign_events
           BEGIN SELECT RAISE(ABORT,'Campaign events are immutable; add a superseding event'); END"""
    )
    db.execute(
        """CREATE TRIGGER campaign_events_immutable_delete BEFORE DELETE ON campaign_events
           BEGIN SELECT RAISE(ABORT,'Campaign events are immutable'); END"""
    )

    for table, name, definition in (
        ("snapshots", "payload_hash", "TEXT"),
        ("snapshots", "source_id", "TEXT REFERENCES provenance_sources(source_id)"),
        ("snapshots", "provenance_class", "TEXT NOT NULL DEFAULT 'mechanical_fact' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("gangs", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("territories", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("fighters", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("battles", "provenance_class", "TEXT NOT NULL DEFAULT 'mechanical_fact' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("battles", "chronicle_provenance_class", "TEXT NOT NULL DEFAULT 'connective_fiction' CHECK(chronicle_provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("fighter_events", "campaign_event_id", "TEXT REFERENCES campaign_events(event_id)"),
        ("fighter_events", "source_id", "TEXT REFERENCES provenance_sources(source_id)"),
        ("fighter_events", "provenance_class", "TEXT NOT NULL DEFAULT 'mechanical_fact' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("memories", "campaign_event_id", "TEXT REFERENCES campaign_events(event_id)"),
        ("memories", "source_observation_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("memories", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("memories", "source_id", "TEXT REFERENCES provenance_sources(source_id)"),
        ("moodlets", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("moodlets", "source_id", "TEXT REFERENCES provenance_sources(source_id)"),
        ("moodlets", "campaign_event_id", "TEXT REFERENCES campaign_events(event_id)"),
        ("moodlets", "source_observation_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("narrative_threads", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("regions", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("downtime_reports", "provenance_class", "TEXT NOT NULL DEFAULT 'inference' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("lore_sources", "provenance_class", "TEXT NOT NULL DEFAULT 'canon_authored' CHECK(provenance_class IN (" + _PROVENANCE_SQL + "))"),
        ("lore_sources", "provenance_source_id", "TEXT REFERENCES provenance_sources(source_id)"),
    ):
        _add_column(db, table, name, definition)
    db.execute("CREATE UNIQUE INDEX snapshots_payload_hash_idx ON snapshots(payload_hash) WHERE payload_hash IS NOT NULL")


def _backfill(db: sqlite3.Connection) -> None:
    now = _now()
    state = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM system_state")}
    observed_at = state.get("last_sync") or now
    db.execute("UPDATE system_state SET value='NCCE v0.3 Prototype' WHERE key='engine_version' AND value='0.3 Story Engine Prototype'")
    sheet_id = "1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00"
    sheet_uri = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    snapshot = db.execute("SELECT source_hash FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
    sheet_source = _source(
        db, "baseline:snapshot-0001", "seeded_campaign_baseline", "mechanical_fact",
        "Campaign Sheet baseline snapshot 0001", sheet_uri,
        "Seeded v0.3 baseline; exact pre-baseline chronology unavailable",
        observed_at, snapshot["source_hash"] if snapshot else None,
    )

    lore = db.execute("SELECT id,title,source_url,content FROM lore_sources ORDER BY id LIMIT 1").fetchone()
    canon_source = None
    if lore:
        content_hash = hashlib.sha256((lore["content"] or "").encode("utf-8")).hexdigest()
        canon_source = _source(
            db, "canon:c-nine-story-export", "authored_campaign_lore", "canon_authored",
            lore["title"] or "C-NINE Story canonical export", lore["source_url"],
            "data/lore/C-NINE Story - canonical export.txt", observed_at, content_hash,
        )
        db.execute(
            "UPDATE lore_sources SET provenance_class='canon_authored',provenance_source_id=? WHERE id=?",
            (canon_source, lore["id"]),
        )

    entity_time = observed_at
    gang_entities: dict[str, str] = {}
    gang_names: dict[str, str] = {}
    for row in db.execute("SELECT gang_id,name,backstory_source FROM gangs"):
        entity_id = _entity(db, "gang", str(row["gang_id"]), row["name"], sheet_source, entity_time)
        gang_entities[str(row["gang_id"])] = entity_id
        gang_names[_normal_key(row["name"])] = entity_id
        source = (row["backstory_source"] or "").casefold()
        provenance = "canon_authored" if ("c-nine" in source or "canon" in source) else ("player_authored" if "player" in source else "inference")
        db.execute("UPDATE gangs SET provenance_class=? WHERE gang_id=?", (provenance, row["gang_id"]))

    fighter_entities: dict[int, str] = {}
    fighter_ids: dict[int, dict] = {}
    for row in db.execute("SELECT id,gang_id,gang_name,name,backstory_source FROM fighters"):
        entity_key = f"{row['gang_id']}/{_normal_key(row['name'])}"
        entity_id = _entity(db, "fighter", entity_key, row["name"], sheet_source, entity_time)
        fighter_entities[row["id"]] = entity_id
        fighter_ids[row["id"]] = dict(row)
        source = (row["backstory_source"] or "").casefold()
        provenance = "canon_authored" if ("c-nine" in source or "canon" in source) else ("player_authored" if "player" in source else "inference")
        db.execute("UPDATE fighters SET provenance_class=? WHERE id=?", (provenance, row["id"]))

    territory_entities: dict[str, str] = {}
    for row in db.execute("SELECT DISTINCT territory FROM territories"):
        territory_key = _normal_key(row["territory"])
        territory_entities[territory_key] = _entity(db, "territory", territory_key, row["territory"], sheet_source, entity_time)
    for row in db.execute("SELECT id,backstory FROM territories"):
        db.execute("UPDATE territories SET provenance_class='inference' WHERE id=?", (row["id"],))
    for row in db.execute("SELECT name FROM regions"):
        region_key = _normal_key(row["name"])
        _entity(db, "region", region_key, row["name"], sheet_source, entity_time)
    _entity(db, "campaign", "campaign", state.get("campaign_name", "Campaign"), sheet_source, entity_time)

    # Give existing snapshots a content digest without changing their payloads.
    for row in db.execute("SELECT id,payload_json,payload_hash FROM snapshots"):
        if not row["payload_hash"]:
            digest = hashlib.sha256((row["payload_json"] or "{}").encode("utf-8")).hexdigest()
            db.execute("UPDATE snapshots SET payload_hash=?,source_id=?,provenance_class='mechanical_fact' WHERE id=?", (digest, sheet_source, row["id"]))

    # Re-express baseline fighter observations as immutable, source-linked campaign events.
    for row in db.execute("SELECT * FROM fighter_events ORDER BY id"):
        fighter = fighter_ids.get(row["fighter_id"])
        if not fighter:
            continue
        event_key = f"baseline:fighter-event:{row['id']}"
        event_id = _event(
            db, event_key=event_key, event_type=row["event_type"], occurred_at=row["event_date"],
            observed_at=observed_at, source_id=sheet_source,
            source_locator=f"baseline fighter {fighter['gang_id']}/{fighter['name']}; legacy event {row['id']}",
            payload={"title": row["title"], "detail": row["detail"], "legacy_fighter_event_id": row["id"]},
            confidence=float(row["confidence"] if row["confidence"] is not None else 1.0),
        )
        _subject(db, event_id, fighter_entities[fighter["id"]], "affected")
        gang_entity = gang_entities.get(str(fighter["gang_id"]))
        if gang_entity:
            _subject(db, event_id, gang_entity, "gang_context")
        db.execute(
            "UPDATE fighter_events SET campaign_event_id=?,source_id=?,provenance_class='mechanical_fact' WHERE id=?",
            (event_id, sheet_source, row["id"]),
        )

    # Battles carry source row identities, not invented IDs or reconstructed chronology.
    for row in db.execute("SELECT * FROM battles ORDER BY source_row"):
        if row["source_row"] is None:
            continue
        event_id = _event(
            db, event_key=f"baseline:battle-row:{row['source_row']}", event_type="battle_result",
            occurred_at=row["date"], observed_at=observed_at, source_id=sheet_source,
            source_locator=f"Battles!row {row['source_row']}",
            payload={key: row[key] for key in (
                "source_row","date","scenario","attacker","defender","winner","territory",
                "territory_claimer","notes",
            )}, confidence=1.0,
        )
        for field, role in (("attacker", "attacker"), ("defender", "defender"),
                            ("winner", "winner"), ("territory_claimer", "claimer")):
            name = row[field]
            entity_id = gang_names.get(_normal_key(name)) if name else None
            if name and not entity_id:
                entity_id = _entity(db, "gang", f"source-name/{_normal_key(name)}", name, sheet_source, entity_time)
                gang_names[_normal_key(name)] = entity_id
            if entity_id:
                _subject(db, event_id, entity_id, role)
        if row["territory"]:
            territory_key = _normal_key(row["territory"])
            territory_id = territory_entities.get(territory_key)
            if not territory_id:
                territory_id = _entity(db, "territory", territory_key, row["territory"], sheet_source, entity_time)
                territory_entities[territory_key] = territory_id
            _subject(db, event_id, territory_id, "location")
        db.execute(
            "UPDATE battles SET chronicle_provenance_class='connective_fiction' WHERE id=?", (row["id"],)
        )
        _evidence(db, artifact_type="battle_chronicle", artifact_key=str(row["id"]),
                  event_id=event_id, evidence_role="factual_anchor", created_at=now)

    # Preserve existing memory links; reflections cite all available baseline observations.
    event_ids_by_fighter: dict[int, list[str]] = {}
    for row in db.execute("SELECT id,fighter_id,campaign_event_id FROM fighter_events ORDER BY id"):
        if row["campaign_event_id"]:
            event_ids_by_fighter.setdefault(row["fighter_id"], []).append(row["campaign_event_id"])
    for row in db.execute("SELECT id,fighter_id,memory_type,source_event_id FROM memories"):
        source_event = db.execute(
            "SELECT campaign_event_id,source_id FROM fighter_events WHERE id=?", (row["source_event_id"],)
        ).fetchone() if row["source_event_id"] else None
        linked = [source_event["campaign_event_id"]] if source_event and source_event["campaign_event_id"] else []
        if row["memory_type"] == "reflection" and not linked:
            linked = event_ids_by_fighter.get(row["fighter_id"], [])
        provenance = "mechanical_fact" if row["memory_type"] == "observation" else "inference"
        db.execute(
            """UPDATE memories SET campaign_event_id=?,source_observation_ids_json=?,
               provenance_class=?,source_id=? WHERE id=?""",
            (linked[0] if linked else None, json.dumps(linked), provenance,
             source_event["source_id"] if source_event else (sheet_source if provenance == "inference" else None),
             row["id"]),
        )
        for event_id in linked:
            _evidence(db, artifact_type="memory", artifact_key=str(row["id"]), event_id=event_id,
                      evidence_role="source_observation", created_at=now)

    for row in db.execute("SELECT id,fighter_id,source FROM moodlets"):
        authored_context = "canonical" in (row["source"] or "").casefold()
        linked = event_ids_by_fighter.get(row["fighter_id"], [])
        source_id = canon_source if authored_context and canon_source else sheet_source
        db.execute(
            "UPDATE moodlets SET provenance_class='inference',source_id=?,campaign_event_id=?,source_observation_ids_json=? WHERE id=?",
            (source_id, linked[0] if linked else None, json.dumps(linked), row["id"]),
        )
        for event_id in linked:
            _evidence(db, artifact_type="moodlet", artifact_key=str(row["id"]), event_id=event_id,
                      evidence_role="character_context", created_at=now)
        _evidence(db, artifact_type="moodlet", artifact_key=str(row["id"]), source_id=source_id,
                  evidence_role="interpretation_source", created_at=now)

    for row in db.execute("SELECT id,backstory,provenance_class FROM fighters"):
        if row["provenance_class"] == "canon_authored" and canon_source:
            _evidence(db, artifact_type="fighter_backstory", artifact_key=str(row["id"]),
                      source_id=canon_source, evidence_role="authored_source", created_at=now)
        else:
            for event_id in event_ids_by_fighter.get(row["id"], []):
                _evidence(db, artifact_type="fighter_backstory", artifact_key=str(row["id"]),
                          event_id=event_id, evidence_role="mechanical_basis", created_at=now)

    for row in db.execute("SELECT gang_id,backstory,provenance_class FROM gangs"):
        artifact_key = str(row["gang_id"])
        if row["provenance_class"] == "canon_authored" and canon_source:
            _evidence(db, artifact_type="gang_backstory", artifact_key=artifact_key,
                      source_id=canon_source, evidence_role="authored_source", created_at=now)
        else:
            for event in db.execute(
                """SELECT DISTINCT es.event_id FROM event_subjects es JOIN campaign_events ce USING(event_id)
                   JOIN entities e USING(entity_id) WHERE e.entity_type='gang' AND e.entity_key=?""",
                (artifact_key,),
            ):
                _evidence(db, artifact_type="gang_backstory", artifact_key=artifact_key,
                          event_id=event["event_id"], evidence_role="campaign_history", created_at=now)
            _evidence(db, artifact_type="gang_backstory", artifact_key=artifact_key,
                      source_id=sheet_source, evidence_role="campaign_baseline", created_at=now)

    for row in db.execute("SELECT id,territory FROM territories"):
        territory_entity = territory_entities.get(_normal_key(row["territory"]))
        if territory_entity:
            for event in db.execute(
                "SELECT event_id FROM event_subjects WHERE entity_id=? AND role='location'", (territory_entity,)
            ):
                _evidence(db, artifact_type="territory_backstory", artifact_key=str(row["id"]),
                          event_id=event["event_id"], evidence_role="recorded_battle", created_at=now)
        _evidence(db, artifact_type="territory_backstory", artifact_key=str(row["id"]),
                  source_id=sheet_source, evidence_role="territory_baseline", created_at=now)

    for row in db.execute("SELECT id FROM downtime_reports"):
        _evidence(db, artifact_type="downtime_report", artifact_key=str(row["id"]),
                  source_id=sheet_source, evidence_role="generated_from_baseline", created_at=now)
    for row in db.execute("SELECT id,scope_type,scope_key FROM narrative_threads"):
        _evidence(db, artifact_type="narrative_thread", artifact_key=str(row["id"]),
                  source_id=sheet_source, evidence_role="generated_from_campaign_history", created_at=now)

    for row in db.execute("SELECT name FROM regions"):
        artifact_key = _normal_key(row["name"])
        for event in db.execute("SELECT event_id FROM campaign_events WHERE event_type='battle_result'"):
            _evidence(db, artifact_type="region_backstory", artifact_key=artifact_key,
                      event_id=event["event_id"], evidence_role="campaign_history", created_at=now)
        _evidence(db, artifact_type="region_backstory", artifact_key=artifact_key,
                  source_id=sheet_source, evidence_role="campaign_baseline", created_at=now)

    gang_ids_by_name = {_normal_key(name): entity_id for name, entity_id in gang_names.items()}
    for row in db.execute("SELECT id,gang_id FROM downtime_reports"):
        entity_id = gang_entities.get(str(row["gang_id"]))
        if entity_id:
            for event in db.execute("SELECT event_id FROM event_subjects WHERE entity_id=?", (entity_id,)):
                _evidence(db, artifact_type="downtime_report", artifact_key=str(row["id"]),
                          event_id=event["event_id"], evidence_role="gang_history", created_at=now)

    for row in db.execute("SELECT id,scope_type,scope_key FROM narrative_threads WHERE scope_type='relationship'"):
        for name in (row["scope_key"] or "").split("|"):
            entity_id = gang_ids_by_name.get(_normal_key(name))
            if entity_id:
                for event in db.execute("SELECT event_id FROM event_subjects WHERE entity_id=?", (entity_id,)):
                    _evidence(db, artifact_type="narrative_thread", artifact_key=str(row["id"]),
                              event_id=event["event_id"], evidence_role="relationship_history", created_at=now)


def migrate(db: sqlite3.Connection) -> int:
    """Upgrade a legacy v0.3 database without discarding its contents."""
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations(
             version INTEGER PRIMARY KEY,
             name TEXT NOT NULL,
             applied_at TEXT NOT NULL
           )"""
    )
    current = db.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError(f"Database schema {current} is newer than this app supports ({SCHEMA_VERSION})")
    if current < 1:
        db.execute("BEGIN IMMEDIATE")
        try:
            _create_foundation(db)
            _backfill(db)
            db.execute(
                """CREATE TRIGGER snapshots_immutable_update BEFORE UPDATE ON snapshots
                   BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END"""
            )
            db.execute(
                """CREATE TRIGGER snapshots_immutable_delete BEFORE DELETE ON snapshots
                   BEGIN SELECT RAISE(ABORT,'Snapshots are immutable'); END"""
            )
            db.execute(
                """CREATE TRIGGER provenance_sources_immutable_update BEFORE UPDATE ON provenance_sources
                   BEGIN SELECT RAISE(ABORT,'Provenance sources are immutable; register a new source version'); END"""
            )
            db.execute(
                """CREATE TRIGGER provenance_sources_immutable_delete BEFORE DELETE ON provenance_sources
                   BEGIN SELECT RAISE(ABORT,'Provenance sources are immutable'); END"""
            )
            db.execute(
                "INSERT INTO schema_migrations(version,name,applied_at) VALUES(1,?,?)",
                ("durable provenance and event foundation", _now()),
            )
            db.execute("PRAGMA user_version=1")
            db.commit()
        except Exception:
            db.rollback()
            raise
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        db.execute("BEGIN IMMEDIATE")
        try:
            _add_column(db, "territories", "source_territory_id", "TEXT")
            _add_column(db, "territories", "active", "INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))")
            _add_column(db, "fighters", "listed_in_source", "INTEGER NOT NULL DEFAULT 1 CHECK(listed_in_source IN (0,1))")
            _add_column(db, "battles", "active", "INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS territories_source_id_idx ON territories(source_territory_id) WHERE source_territory_id IS NOT NULL")
            db.execute("CREATE INDEX IF NOT EXISTS territories_active_idx ON territories(active,gang_id)")
            db.execute(
                "INSERT INTO schema_migrations(version,name,applied_at) VALUES(2,?,?)",
                ("live Sheet current-state projection", _now()),
            )
            db.execute("PRAGMA user_version=2")
            db.commit()
        except Exception:
            db.rollback()
            raise
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 3:
        db.execute("BEGIN IMMEDIATE")
        try:
            _add_column(db, "gangs", "active", "INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))")
            db.execute("CREATE INDEX IF NOT EXISTS gangs_active_idx ON gangs(active,name)")
            db.execute(
                "INSERT INTO schema_migrations(version,name,applied_at) VALUES(3,?,?)",
                ("current campaign membership projection", _now()),
            )
            db.execute("PRAGMA user_version=3")
            db.commit()
        except Exception:
            db.rollback()
            raise
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 4:
        db.execute("BEGIN IMMEDIATE")
        try:
            _add_column(db, "fighters", "mechanics_json", "TEXT NOT NULL DEFAULT '{}'" )
            _add_column(db, "fighters", "voice_profile_json", "TEXT NOT NULL DEFAULT '{}'" )
            _add_column(db, "battles", "source_battle_key", "TEXT")
            db.execute("""CREATE TABLE story_memories(
                memory_id TEXT PRIMARY KEY, fighter_id INTEGER NOT NULL REFERENCES fighters(id),
                memory_key TEXT NOT NULL, memory_type TEXT NOT NULL CHECK(memory_type IN ('observation','reflection')),
                title TEXT NOT NULL, content TEXT NOT NULL, importance REAL NOT NULL CHECK(importance BETWEEN 0 AND 10),
                occurred_at TEXT, observed_at TEXT, created_at TEXT NOT NULL,
                tags_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
                source_event_ids_json TEXT NOT NULL, source_observation_ids_json TEXT NOT NULL,
                source_id TEXT REFERENCES provenance_sources(source_id), provenance_class TEXT NOT NULL DEFAULT 'inference',
                confidence REAL NOT NULL DEFAULT 0.65, baseline INTEGER NOT NULL DEFAULT 0,
                generation_version TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
            )""")
            db.execute("CREATE INDEX story_memories_fighter_idx ON story_memories(fighter_id,active,observed_at)")
            db.execute("""CREATE TABLE story_artifacts(
                artifact_id TEXT PRIMARY KEY, scope_type TEXT NOT NULL, scope_key TEXT NOT NULL,
                document_json TEXT NOT NULL, input_hash TEXT NOT NULL, generation_version TEXT NOT NULL,
                generated_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(scope_type,scope_key,input_hash,generation_version)
            )""")
            db.execute("CREATE INDEX story_artifacts_scope_idx ON story_artifacts(scope_type,scope_key,active)")
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(4,?,?)",
                       ("event-driven fighter memories and versioned narrative artifacts", _now()))
            db.execute("PRAGMA user_version=4")
            db.commit()
        except Exception:
            db.rollback()
            raise
    if db.execute('PRAGMA user_version').fetchone()[0] < 5:
        db.execute('BEGIN IMMEDIATE')
        try:
            _add_column(db, 'fighters', 'writer_identity_json', "TEXT NOT NULL DEFAULT '{}'")
            _add_column(db, 'territories', 'mechanics_json', "TEXT NOT NULL DEFAULT '{}'")
            _add_column(db, 'story_memories', 'writer_context_json', "TEXT NOT NULL DEFAULT '{}'")
            db.execute('''CREATE TABLE narrative_entries(
                entry_id TEXT PRIMARY KEY, scope_type TEXT NOT NULL CHECK(scope_type IN ('territory','gang')),
                scope_key TEXT NOT NULL, entry_key TEXT NOT NULL, event_type TEXT NOT NULL,
                title TEXT NOT NULL, document_json TEXT NOT NULL,
                occurred_at TEXT, observed_at TEXT, created_at TEXT NOT NULL,
                provenance_class TEXT NOT NULL CHECK(provenance_class IN ('inference','connective_fiction')),
                source_event_ids_json TEXT NOT NULL, continuity_json TEXT NOT NULL,
                generation_version TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)''')
            db.execute('CREATE INDEX narrative_entries_scope_idx ON narrative_entries(scope_type,scope_key,active,created_at)')
            db.execute('''CREATE TABLE writer_identity_revisions(
                revision_id TEXT PRIMARY KEY, fighter_id INTEGER NOT NULL REFERENCES fighters(id),
                identity_json TEXT NOT NULL, provenance_class TEXT NOT NULL DEFAULT 'player_authored',
                created_at TEXT NOT NULL)''')
            db.execute('INSERT INTO schema_migrations(version,name,applied_at) VALUES(5,?,?)',
                       ('writing director, authored identities and persistent place/gang streams', _now()))
            db.execute('PRAGMA user_version=5')
            db.commit()
        except Exception:
            db.rollback()
            raise
    if db.execute('PRAGMA user_version').fetchone()[0] < 6:
        db.execute('BEGIN IMMEDIATE')
        try:
            _add_column(db, 'story_memories', 'writer_status', "TEXT NOT NULL DEFAULT 'ready'")
            db.execute('''CREATE TABLE writer_result_cache(
                prompt_hash TEXT PRIMARY KEY, result_json TEXT NOT NULL,
                model TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(6,?,?)",
                       ('provider-backed narrative writer and reusable generated text', _now()))
            db.execute('PRAGMA user_version=6')
            db.commit()
        except Exception:
            db.rollback()
            raise
    if db.execute('PRAGMA user_version').fetchone()[0] < 7:
        db.execute('BEGIN IMMEDIATE')
        try:
            _add_column(db, 'story_memories', 'content_runs_json', "TEXT NOT NULL DEFAULT '[]'")
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(7,?,?)",
                       ('semantic inline narrative marks for red critical statuses and missing information', _now()))
            db.execute('PRAGMA user_version=7')
            db.commit()
        except Exception:
            db.rollback()
            raise
    if db.execute('PRAGMA user_version').fetchone()[0] < 8:
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('''CREATE TABLE IF NOT EXISTS campaign_archive_records(
                    source_table TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    version_hash TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at_raw TEXT,
                    created_at_utc TEXT,
                    updated_at_raw TEXT,
                    updated_at_utc TEXT,
                    archived_at_raw TEXT,
                    archived_at_utc TEXT,
                    imported_at_utc TEXT NOT NULL,
                    source_tab TEXT NOT NULL,
                    source_row INTEGER,
                    source_row_json TEXT NOT NULL,
                    raw_record_json TEXT NOT NULL,
                    normalized_json TEXT NOT NULL,
                    PRIMARY KEY(source_table,record_id,version_hash)
                )''')
            db.execute('CREATE INDEX IF NOT EXISTS campaign_archive_record_time_idx ON campaign_archive_records(source_table,created_at_utc)')
            db.execute('CREATE INDEX IF NOT EXISTS campaign_archive_version_idx ON campaign_archive_records(source_table,record_id,archived_at_utc)')
            db.execute('''CREATE TABLE IF NOT EXISTS campaign_archive_conflicts(
                    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_table TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    version_hash TEXT NOT NULL,
                    existing_payload_hash TEXT NOT NULL,
                    conflicting_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    source_tab TEXT NOT NULL,
                    source_row INTEGER,
                    source_row_json TEXT NOT NULL,
                    raw_record_json TEXT NOT NULL,
                    UNIQUE(source_table,record_id,version_hash,conflicting_payload_hash)
                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS campaign_archive_import_runs(
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imported_at_utc TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )''')
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(8,?,?)",
                       ('Munda Manager raw archive import and campaign history timeline', _now()))
            db.execute('PRAGMA user_version=8')
            db.commit()
        except Exception:
            db.rollback()
            raise
    if db.execute('PRAGMA user_version').fetchone()[0] < 9:
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('''CREATE TABLE IF NOT EXISTS writer_requests(
                    request_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    request_id TEXT,
                    response_id TEXT,
                    form TEXT NOT NULL,
                    subject_type TEXT,
                    subject_key TEXT,
                    subject_name TEXT,
                    model TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    error_text TEXT
                )''')
            db.execute('CREATE INDEX writer_requests_run_idx ON writer_requests(run_id,request_row_id)')
            db.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(9,?,?)",
                       ('scoped writer checks and per-request usage provenance', _now()))
            db.execute('PRAGMA user_version=9')
            db.commit()
        except Exception:
            db.rollback()
            raise
    return SCHEMA_VERSION
