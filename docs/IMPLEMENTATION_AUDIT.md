# NCCE Implementation Audit

Reviewed 2026-10-25 against `PRODUCT_VISION.md`, `STORY_ENGINE_ARCHITECTURE.md`, and `HANDOFF_STATUS.md`.

## Product and architecture fit

The product goal is a persistent story engine driven by read-only mechanical evidence. The user-facing result is an evolving chronicle of people, gangs, places, and campaign history. Canon remains authored, mechanical state remains factual, and generated narrative remains inference with traceable evidence. The intended cadence is meaningful campaign events, not continuous simulated life. The app now ingests the link-readable Sheet and stores factual deltas; narrative reactions still need to be connected to those events.

## Verified baseline

The local SQLite database is at schema version 3 and contains 6 active gangs, 92 listed fighters, 24 active territory rows, 25 active battles, 198 legacy fighter events, 388 memories, 7 narrative threads, 6 downtime reports, 2 snapshots, 223 durable campaign events, 118 stable entities, 512 event/entity links, and 3 provenance sources. All foreign-key checks pass. Recoverable local backups exist at `data/chronicle.v0.3-pre-schema-v1.db`, `data/chronicle.pre-live-sync.db`, and `data/chronicle.pre-schema-v3.db`; runtime databases and backups are ignored by Git. The live Sheet itself was only fetched with GET requests.

## Milestones

| Handoff milestone | Current implementation | Status |
| --- | --- | --- |
| Inspect and run app/tests; record actual state | Source and seeded DB reviewed. Target server prints its startup banner on an available port, but health requests from this environment time out. Existing test file is pytest-style but pytest is not installed; direct invocation exposed a SQLite connection cleanup issue on Windows, fixed with `Store.close()` and `finally`. | Done for this review; runtime access limitation documented below |
| Chronicle primary; demote raw bookkeeping views | Chronicle is the homepage and navigation leads with Chronicle, gangs, people, and places. Gang list cards displayed reputation, territories, and rating; those summary metrics are now removed from the cards and retained in a gang detail evidence panel. Fighter pages still present raw state as evidence. | In progress, core direction implemented |
| Robust entity/event/provenance schema | Schema migration 1 adds version tracking, source registry, stable entities, immutable campaign events, event-to-entity roles, and narrative evidence links. Existing baseline fighter events and battles are backfilled without assigning unknown event dates. Snapshot saves are content-deduplicated and provenance is explicit on narrative rows. | Completed foundation |
| Read-only live Google Sheet sync and snapshot persistence | `google_sheets.py` fetches the link-readable XLSX export with Python's standard library; `snapshot.py` normalizes the actual Krakamunda workbook; `sync.py` records it. Server starts a sync on launch and every 15 minutes. A UI action requests an immediate refresh. | Implemented; live export verified |
| Deterministic snapshot diff to factual event ledger | `diff.py` compares gang/fighter fields and roster membership, battle additions/corrections/removals, and unambiguous territory ownership changes. `sync.py` persists immutable, idempotent events with source and snapshot pointers. Changes without an explicit source date have no invented occurrence time. | Completed and exercised against the current workbook |
| Future fighter change tracker | Fighter API and detail view include campaign-ledger events alongside baseline observations. Live updates refresh the current roster and append future changes to the ledger. | Implemented |
| Stim, mood, memory, reflection pipeline with source pointers | Seed code creates simple baseline events, memories, moodlets, and reflections. Runtime processing, retrieval, propagation, thresholded reflection, and complete source pointers are absent. | Seeded prototype only |
| Inferred histories for non-C-NINE entities | Gang, fighter, territory, and region histories are seeded; fighter and gang histories carry inference/authored labels. Some generated territorial material is stored without a consistent provenance class. | Partial |
| Event-driven downtime and campaign chronicle updates | Downtime and region text are generated once during seeding. They do not advance when new campaign events arrive. | Seeded prototype only |
| Improve presentation / consider Unity after story loop | Browser UI exists; the story loop is not yet operational. | Not started |

## Run and test notes

- The workspace's `python` command points to the Windows Store stub. The bundled Python runtime at `C:\Users\Blazej\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` runs the project.
- `python -m unittest discover -s tests -v` reports zero tests because `test_core.py` uses pytest-style test functions and has no `unittest.TestCase` classes.
- `python -m pytest -q` cannot run because pytest is not installed.
- The test module's direct-run path is the current dependency-free test entry point. It passes storage/parser checks, a stdlib XLSX parsing fixture, snapshot deduplication, idempotent event insertion, battle correction/removal, roster changes, and legacy migration checks.
- Live workbook export and normalization verified: 6 gangs, 92 fighters, 24 territory rows, and 25 battles. A disposable SQLite projection matched all four counts. The production derived database has a recoverable pre-sync backup at `data/chronicle.pre-live-sync.db`.
- The server's startup sync succeeded. This task's browser and shell environments cannot access its localhost routes, so direct HTTP UI verification remains unavailable here.

## Next engineering priority

Build runtime stim/observation handling from the new ledger, then generate sourced memories and narrative reactions. The live Sheet feed, current-state projection and factual event tracker are in place. Never write to the Sheet or infer historical chronology from baseline values alone.
