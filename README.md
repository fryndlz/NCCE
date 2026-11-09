# NCCE — Necromunda Campaign Chronicle Engine

Current source: **0.24.0**, SQLite schema **15**. Writer Workshop, JKSimmons, StoryTechMan and RAG have been removed. Prose generation is disabled until a replacement is agreed. Existing authored/generated prose, campaign data, the event ledger, memories and timeline are preserved.

The app reads Krakamunda on startup, every 15 minutes and on manual refresh. It keeps factual changes and fighter-relevant memory/thought causes; missing prose is marked paused. No provider key or paid writing setup is required.

Open the [hosted app](https://ncce-private-preview.onrender.com/) using the existing campaign passphrase. Persistent storage remains `/var/data/ncce-preview.db`. Retirement takes a verified backup beside that file before cancelling unfinished writing queues; historical audit/draft data stays on disk.

Run `python src/server.py`, or use **START NECROMUNDA.bat**. Python and its standard library are sufficient. Do not replace or reseed an existing campaign database.

See [Current technical design](docs/CURRENT_DESIGN.md), [handoff](docs/HANDOFF_STATUS.md) and [changelog](CHANGELOG.md). Older writing-system specifications are historical and marked retired.

Run the `tests/test_*.py` scripts with Python and the `tests/test_*_ui.cjs` checks with Node for regression verification. `tests/smoke_server.py` provides an opt-in authenticated HTTP/live read-only Sheet check. Tests use disposable databases and no provider calls.


## Editorial memory voice registry

Fighter memories, reflections and Mind thoughts use a three-layer **faction → gang → individual** voice resolver, after factual event and awareness checks. The versioned profile file is [`config/voice_registry.v1.json`](config/voice_registry.v1.json), with [onboarding instructions](docs/VOICE_REGISTRY.md) and the command-line editor `python scripts/voice_registry_cli.py`. The registry covers the five current campaign gangs, preserves independent allied/outsider voices, and leaves `Patrol do spraw alkoholu i broni` excluded until reviewed. A newly discovered gang uses neutral fallback and can be registered pending, then approved with sourced lore—no Python change needed. The profile is writing guidance only; no campaign facts, cognitive scoring, accepted prose or existing queue requests are rewritten. Tests: `python -m unittest discover -s tests -p 'test_voice_*.py' -v`.

