# NCCE — Necromunda Campaign Chronicle Engine

Current application build: NCCE v0.5 hosted-access preview.

This build pivots the project away from being a second Munda Manager. Mechanical data is evidence. The product is the persistent story generated from that evidence.

## Local Windows preview

From this repository checkout, double-click **START NECROMUNDA.bat** and leave the black launcher window open while using the app.

The launcher finds Python 3, starts the local server, opens the browser, and keeps errors visible. There are no third-party Python packages.

## Share with friends

The Windows launcher is a local development preview. To open NCCE by link on friends' computers and phones, see [Private hosted deployment](docs/HOSTED_DEPLOYMENT.md). The free preview recipe is `render.yaml`; the separate paid persistent recipe is `render.production.yaml` and requires owner approval before use.

## What the current build contains

- **Chronicle** homepage: campaign-level narrative, recent events, downtime.
- **Gang histories**: authored where available, otherwise inferred from faction + campaign record + holdings.
- **Persistent people**: 92 fighters imported from the current source roster.
- **Ganger backstories**: all 21 C-NINE roster entries use matching authored C-NINE material where available; missing gang material is mechanically inferred and labelled as such.
- **Ganger tracker**: baseline observations for XP, kills, advancements, injuries/effects and status. Live snapshots append exact deltas to the campaign ledger.
- **Mind**: moodlets and current reflections derived from status, injury, kills, class and canonical context.
- **Memory stream**: observations and reflections carry source/confidence metadata.
- **Places**: region and territory histories generated from ownership and battle context.
- **Downtime reports**: one current report per gang, driven by latest battle and roster state.
- **C-NINE archive**: complete exported `CAMPAIGN LOG` + `PERSONNEL FILES` from the canonical Google Doc embedded locally.
- **Battle chronicle**: all 25 baseline battles expressed as factual narrative anchors.
- **Provenance ledger**: schema migrations 1–3 record source authority, stable entities, immutable campaign events, current roster membership and links from story artifacts to their evidence.
- **Live Sheet refresh**: reads the link-shared Krakamunda workbook on startup and every 15 minutes while the app is running, records factual changes and refreshes the local roster, holdings and battles. A manual refresh button is also available.

## Story-engine model

The engine separates four layers:

1. **Mechanical truth**: authoritative campaign state. Never rewritten by narrative generation.
2. **Observations / stims**: meaningful changes such as injury, death, advance, capture, recruitment, territory change and battle outcome.
3. **Character interpretation**: personality/context converts observations into moodlets, memories, relationships and thoughts.
4. **Reflection / chronicle**: accumulated evidence becomes higher-level character arcs, gang histories, place histories and campaign narratives.

Generated content stores provenance and confidence so authored lore, mechanical inference and connective fiction remain distinguishable.

## Important baseline limitation

The original baseline tells us each fighter's **current** XP, kills, injuries, advancements and status. It cannot reconstruct the exact date/order of pre-baseline changes unless that history exists in authored material. Those remain baseline observations. The live-sync preview records changes from its first successful Sheet snapshot onward.

## Snapshot ingest and next engineering layer

Normalized snapshots can be persisted with deduplication and compared deterministically. The event ledger records fighter/gang changes, battle additions/corrections/removals, and unambiguous territory transfers with source and snapshot provenance; it does not invent dates for undated changes. Fighter pages and the Chronicle expose those campaign events. While running, the app reads the link-shared Sheet through its XLSX export using Python's standard library; requests are read-only and need no stored credentials. Story-generation reactions, memories, downtime, and evolving chronicles remain the next engine layer. Existing databases migrate in place; the seed command refuses to replace an existing database.
