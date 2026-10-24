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

- AUTHOR: explicitly supplied by player/canonical lore.
- FACT: directly derived from authoritative mechanical state.
- INFERENCE: interpretation strongly suggested by facts.
- FICTION: connective diegetic detail generated to make the history readable.

No lower truth class may overwrite a higher one.

## Scopes

The same event updates several scopes:

- fighter
- relationship
- gang
- territory
- region
- campaign

This is the primary multiplier: one mechanical event should generate many contextually different consequences without requiring bespoke authoring.
