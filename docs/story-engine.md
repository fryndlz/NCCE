# Story Engine Architecture

## Event cadence

This is turn/campaign based, not a continuous life simulation. The cognitive tick is a meaningful campaign event: battle, injury, recovery, death, advancement, recruitment, purchase, capture/release, territory change, reputation change, alliance event or downtime event.

## Cognitive pipeline

Mechanical delta -> Stim/Observation -> Character filtering -> Moodlet -> Memory -> Reflection -> Narrative thread -> Chronicle.

### Stim payload

- event type and tags
- affected entities
- importance/priority
- emotional dimensions where useful
- location/territory
- factual evidence pointer

### Memory retrieval

Rank candidate memories by recency + importance + relevance. Reflections cite the observations/reflections used to form them.

### Mood vs personality

Personality is slow-changing disposition inferred/seeded from role, authored backstory and accumulated behavior. Moodlets are temporary or persistent emotional consequences of events. Moodlets should compete by intensity rather than producing every possible reaction simultaneously.

### Narrative truth classes

- `player_authored`: explicitly supplied by a player.
- `canon_authored`: established campaign canon.
- `mechanical_fact`: directly recorded or deterministically derived from authoritative mechanical state.
- `inference`: interpretation strongly suggested by facts and context.
- `connective_fiction`: diegetic detail used to make a record readable.

No lower truth class may overwrite a higher one.

The SQLite provenance registry retains source authority and locators. Campaign events have stable IDs and idempotency keys, are immutable, and link to affected entities by role. Narrative artifacts cite source events and/or authored sources. When the baseline cannot establish when an old change occurred, the event date remains unknown; the observed time only says when the application first recorded it.

## Scopes

The same event updates several scopes:

- fighter
- relationship
- gang
- territory
- region
- campaign

This is the primary multiplier: one mechanical event should generate many contextually different consequences without requiring bespoke authoring.
