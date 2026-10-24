# v0.3 Implementation Audit

Reviewed 2026-10-24 against `PRODUCT_VISION.md`, `STORY_ENGINE_ARCHITECTURE.md`, and `HANDOFF_STATUS.md`.

## Product and architecture fit

The product goal is a persistent story engine driven by read-only mechanical evidence. The user-facing result is an evolving chronicle of people, gangs, places, and campaign history. Canon remains authored, mechanical state remains factual, and generated narrative remains inference with traceable evidence. The intended cadence is meaningful campaign events, not continuous simulated life. The current v0.3 build is a seeded narrative prototype consistent with that direction; it is not yet a live synchronization or event-processing engine.

## Verified baseline

The checked-in SQLite database contains 6 gangs, 92 fighters, 24 territory rows, 25 battles, 198 fighter events, 388 memories, 7 narrative threads, 6 downtime reports, and 1 snapshot. These counts match the handoff's approximate baseline. This review did not edit the database, seed files, or authoritative campaign sources.

## Milestones

| Handoff milestone | Current implementation | Status |
| --- | --- | --- |
| Inspect and run app/tests; record actual state | Source and seeded DB reviewed. Target server prints its startup banner on an available port, but health requests from this environment time out. Existing test file is pytest-style but pytest is not installed; direct invocation exposed a SQLite connection cleanup issue on Windows, fixed with `Store.close()` and `finally`. | Done for this review; runtime access limitation documented below |
| Chronicle primary; demote raw bookkeeping views | Chronicle is the homepage and navigation leads with Chronicle, gangs, people, and places. Gang list cards displayed reputation, territories, and rating; those summary metrics are now removed from the cards and retained in a gang detail evidence panel. Fighter pages still present raw state as evidence. | In progress, core direction implemented |
| Robust entity/event/provenance schema | SQLite has snapshots, entities, fighter events, memories, moodlets, narrative threads, and source/confidence fields. It lacks a general event ledger, unified provenance classes, stable cross-entity source links, and migration/version handling. | Partial |
| Read-only live Google Sheet sync and snapshot persistence | Parser builds a normalized snapshot from supplied tab values; no Google adapter or live sync exists. One seed snapshot is present. | Not implemented |
| Deterministic snapshot diff to factual event ledger | `diff.py` compares fields and fighter sets as pure helpers. No durable event creation or territory/battle diff pipeline is connected. | Partial |
| Future fighter change tracker | Baseline observations exist; no live snapshot loop exists to append exact future changes. | Not implemented |
| Stim, mood, memory, reflection pipeline with source pointers | Seed code creates simple baseline events, memories, moodlets, and reflections. Runtime processing, retrieval, propagation, thresholded reflection, and complete source pointers are absent. | Seeded prototype only |
| Inferred histories for non-C-NINE entities | Gang, fighter, territory, and region histories are seeded; fighter and gang histories carry inference/authored labels. Some generated territorial material is stored without a consistent provenance class. | Partial |
| Event-driven downtime and campaign chronicle updates | Downtime and region text are generated once during seeding. They do not advance when new campaign events arrive. | Seeded prototype only |
| Improve presentation / consider Unity after story loop | Browser UI exists; the story loop is not yet operational. | Not started |

## Run and test notes

- The workspace's `python` command points to the Windows Store stub. The bundled Python runtime at `C:\Users\Blazej\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` runs the project.
- `python -m unittest discover -s tests -v` reports zero tests because `test_core.py` uses pytest-style test functions and has no `unittest.TestCase` classes.
- `python -m pytest -q` cannot run because pytest is not installed.
- The test module's direct-run path is the current dependency-free test entry point. Windows requires explicitly closing the SQLite connection before its temporary directory can be removed; that was repaired in this review.
- Port 8765 was already serving the older standings-first `necromunda-chronicle` app. The v0.3 server started on 8766; the in-app browser could not reach that port in this environment, so browser verification of that separate instance was unavailable.

## Next engineering priority

Continue the UI pivot with focused evidence panels, then add schema migrations and a durable factual event ledger before connecting any narrative generation to future snapshots. Keep Sheet access read-only; never infer historical chronology from baseline values alone.
