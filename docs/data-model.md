# Data model

## Provenance classes

Every stored narrative datum uses one of these classes:

- `mechanical_fact`: directly recorded campaign state or an event deterministically derived from it.
- `player_authored`: material explicitly supplied by a player.
- `canon_authored`: established campaign canon, including the C-NINE Story export.
- `inference`: a conclusion drawn from records, roles, patterns, or context.
- `connective_fiction`: generated detail used to make a record readable; it is never evidence that a mechanical event occurred.

These values are stored separately from the human-readable source label. A source record identifies its authority, locator, retrieval time, and optional content hash. Event and narrative records point to sources and to one another through stable IDs.

## Source authority levels

1. The campaign Sheet is authoritative for mechanical state.
2. Recorded Battles rows are authoritative for the structured result, participants, and territory fields they contain.
3. The C-NINE Story document is authoritative for C-NINE authored canon.
4. Free-text Sheet notes are contextual evidence, not automatically structured fact.
5. Generated narrative is interpretation only; it never feeds back into mechanical truth.

## Snapshot

A snapshot stores campaign, gangs, territories, fighters, and the complete known battle ledger at a point in time, with a required provenance source ID and provenance class. Its canonical content hash excludes the capture timestamp, so unchanged state from the same source is not stored as repeated snapshots. Existing snapshot payloads remain immutable; migrations only add hash and provenance metadata.

## Entity and event ledger

Entities use stable IDs and a `(type, source key)` identity for gangs, fighters, territories, regions, and the campaign. An event stores:

- deterministic event ID and unique idempotency key
- event type, event date when known, and observation time
- provenance class and source ID / source locator
- immutable structured payload and confidence
- before/after snapshot IDs when a future diff provides them
- affected entities with explicit roles such as attacker, winner, fighter, or location
- supersession links and a correction reason when a later record corrects an earlier interpretation

Events are append-only. A correction is represented by a new event that points to the event it supersedes. `occurred_at` remains empty when the baseline cannot establish the historical date; `observed_at` records when the application learned of it.

The v0.3 migration backfills baseline fighter observations and battle rows into this ledger. It does not infer pre-baseline fighter-change dates.

## Narrative layers
Each factual event may later produce:
- neutral/diegetic battle report
- participant gang chronicle updates
- relationship/rivalry updates
- campaign-level chronicle update

Narrative never mutates the factual event ledger. `narrative_evidence` links each story artifact to the source event(s) or authored source(s) that support it. Existing baseline memories retain their legacy fighter-event IDs and receive stable campaign-event pointers where such a pointer exists.

## Schema changes

SQLite `user_version` and `schema_migrations` track forward-only schema changes. The migration runs transactionally, retains existing tables and rows, and exposes the immutable ledger through the read-only `GET /api/events` endpoint. Optional filters are `limit` (capped at 500) and `entity_id`. Runtime database, WAL, and SHM files remain local derived state and are excluded from Git.
