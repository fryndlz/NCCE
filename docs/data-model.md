# Data model

## Source authority levels
1. Structured campaign state: authoritative mechanical state.
2. Battles rows: authoritative for recorded scenario/result/territory fields.
3. Free-text Notes / Gang Notes: contextual evidence, not automatically authoritative structured state.
4. Generated narrative: interpretation only; never feeds back into mechanical truth.

## Snapshot
A snapshot stores campaign, gangs, territories, fighters, and the complete known battle ledger at a point in time.

## Event
A battle event stores:
- stable event id
- date and source row
- scenario
- participants
- winner
- territory and claimer
- raw human notes
- state delta since previous snapshot
- confidence / ambiguity flags

## Narrative layers
Each factual event may later produce:
- neutral/diegetic battle report
- participant gang chronicle updates
- relationship/rivalry updates
- campaign-level chronicle update

Narrative never mutates the factual event ledger.
