# Handoff Status

## Existing build
This repository is based on the functional v0.3 prototype produced in the prior ChatGPT project.

Present files include:
- local Python HTTP server and browser UI
- SQLite persistence
- baseline campaign data
- fighter dataset
- story/narrative prototype code
- C-NINE lore export
- Windows launcher
- tests

The previous prototype reported a baseline of roughly 6 gangs, 92 persistent fighters, 24 territory records and 25 historical battles. Verify these counts from the current database/code rather than trusting this note.

## Known weakness
The application originally drifted toward being a worse Munda Manager: standings, gang stats and battle rows. The product pivot is explicit: story is primary, mechanics are evidence.

## Historical reconstruction limitation
Current state cannot reliably reconstruct exact chronology of all pre-baseline fighter changes. Existing injuries/XP/advancements should be treated as baseline observations unless independently supported by authored historical records. From live synchronization onward, every detected change must be timestamped and retained.

## C-NINE
The canonical C-NINE source is in `data/lore/C-NINE Story - canonical export.txt`. It contains both CAMPAIGN LOG and PERSONNEL FILES. Prefer authored biographies and events from it over generated replacements. Preserve its contradictions/redactions intentionally.

## Highest-priority next milestones
1. Inspect and run current app/tests. Document what v0.3 actually implements versus what was claimed. **Completed in `docs/IMPLEMENTATION_AUDIT.md`.**
2. Make Chronicle the primary UI and demote raw Munda Manager-like views. **Core direction implemented; mechanical gang summary metrics are relegated to evidence detail.**
3. Implement robust entity/event/provenance schema in SQLite. **Completed as schema migration 1; baseline rows are backfilled without inventing historical dates.**
4. Implement live read-only Google Sheet synchronization and snapshot persistence. **Next. Snapshot persistence primitives now exist; Google read adapter is not connected.**
5. Implement deterministic snapshot diff -> factual event ledger.
6. Implement character change tracker for all future changes.
7. Implement stim/mood/memory/reflection pipeline with source pointers.
8. Generate initial non-C-NINE gang/character/place histories with explicit inference provenance.
9. Implement downtime event generation and campaign-level chronicle updates.
10. Only after the story loop is convincing, improve graphics/presentation and consider Unity.

## Development behavior
Do not ask the user for routine reversible implementation decisions. Make sensible decisions and continue. Ask only when a choice materially affects desired behavior, canon, permissions/credentials, cost, or irreversible data changes.
