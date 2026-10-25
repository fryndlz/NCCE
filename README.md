# NCCE — Necromunda Campaign Chronicle Engine

Current source and hosted version: **v0.6.1 — Roster visibility and voice correction**, SQLite schema 4. The Render service now uses a 1 GB persistent disk at `/var/data`; its database path is `/var/data/ncce-preview.db`.

Open the [hosted preview](https://ncce-private-preview.onrender.com/) and use your existing invitation passphrase. See [hosting details](docs/HOSTED_DEPLOYMENT.md) for storage, cost, and backup limitations.

## What this version does

- Reads the authoritative Krakamunda Sheet on startup, every 15 minutes, or on manual refresh.
- Records factual changes and stable battle identities without writing to the Sheet.
- Turns meaningful fighter changes and shared gang events into voiced memories with a separate mechanical evidence block.
- Selects two to four supported current thoughts using importance, recency, relevance and fighter-specific biases.
- Generates reflections from linked observations, and regenerates histories, battle reports, downtime and campaign narratives when their evidence changes.
- Preserves authored lore and distinguishes it from generated inference. Generated versions remain traceable to their sources.
- Provides search and filters for Fighters, Gangs, Places and Battles, with a responsive dossier layout.

The current prose writer is deterministic local code. It needs no language-model API key or paid generation service. Its limits and exact rules are documented in [Current design](docs/CURRENT_DESIGN.md); version changes are in [Changelog](CHANGELOG.md).

## Local development

Double-click **START NECROMUNDA.bat**, or run:

```powershell
python src/server.py
```

Python 3 and its standard library are sufficient. The runtime database is derived, ignored by Git, and migrated in place. The seed command refuses to replace an existing database.

## Verification

```powershell
python tests/test_core.py
python tests/test_battle_identity.py
python tests/test_story_engine.py
node --check web/app.js
```

An additional HTTP check starts a disposable authenticated server and reads the live Sheet:

```powershell
python tests/smoke_server.py
```

Mechanical facts remain authoritative. Authored C-NINE lore remains canon. Generated narrative remains inference. Earlier baseline fields do not establish the date or order of older events, and gang participation does not establish individual fighter attendance.
