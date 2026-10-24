# NCCE — Necromunda Campaign Chronicle Engine

Current seeded application build: v0.3 prototype.

This build pivots the project away from being a second Munda Manager. Mechanical data is evidence. The product is the persistent story generated from that evidence.

## Start on Windows

1. Extract the ZIP somewhere normal, e.g. `C:\Games\Krakaumunda Story Engine`.
2. Double-click **START NECROMUNDA.bat**.
3. Leave the black launcher window open while using the app.

The launcher finds Python 3, starts the local server, opens the browser, and keeps errors visible. There are no third-party Python packages.

## What v0.3 contains

- **Chronicle** homepage: campaign-level narrative, recent events, downtime.
- **Gang histories**: authored where available, otherwise inferred from faction + campaign record + holdings.
- **Persistent people**: 92 fighters imported from the current source roster.
- **Ganger backstories**: all 21 C-NINE roster entries use matching authored C-NINE material where available; missing gang material is mechanically inferred and labelled as such.
- **Ganger tracker**: baseline observations for XP, kills, advancements, injuries/effects and status. Future snapshots are designed to append exact deltas.
- **Mind**: moodlets and current reflections derived from status, injury, kills, class and canonical context.
- **Memory stream**: observations and reflections carry source/confidence metadata.
- **Places**: region and territory histories generated from ownership and battle context.
- **Downtime reports**: one current report per gang, driven by latest battle and roster state.
- **C-NINE archive**: complete exported `CAMPAIGN LOG` + `PERSONNEL FILES` from the canonical Google Doc embedded locally.
- **Battle chronicle**: all 25 baseline battles expressed as factual narrative anchors.
- **Provenance ledger**: schema migration 1 records source authority, stable entities, immutable campaign events and links from story artifacts to their evidence.

## Story-engine model

The engine separates four layers:

1. **Mechanical truth**: authoritative campaign state. Never rewritten by narrative generation.
2. **Observations / stims**: meaningful changes such as injury, death, advance, capture, recruitment, territory change and battle outcome.
3. **Character interpretation**: personality/context converts observations into moodlets, memories, relationships and thoughts.
4. **Reflection / chronicle**: accumulated evidence becomes higher-level character arcs, gang histories, place histories and campaign narratives.

Generated content stores provenance and confidence so authored lore, mechanical inference and connective fiction remain distinguishable.

## Important baseline limitation

Snapshot 0001 tells us each fighter's **current** XP, kills, injuries, advancements and status. It cannot reconstruct the exact date/order of every pre-baseline change unless that history exists in authored material. v0.3 therefore labels these as baseline observations. Once live snapshot sync is connected, every new change can be recorded exactly.

## Next engineering layer

Live read-only Google Sheet synchronization and snapshot comparison. A new battle/state change will emit structured events into the story engine, update affected memories/moodlets/relationships, generate downtime, and advance gang/place/campaign chronicles. Existing databases migrate in place; the seed command refuses to replace an existing database.
