# Story Engine Architecture

## Layers

### 1. Authoritative mechanical state
Read-only campaign Sheet. Snapshot it after processed matches.

### 2. Factual event ledger
Diff consecutive snapshots and combine with the Battles ledger. Store atomic events such as fighter XP change, injury, death, recruitment, purchase, status change, territory transfer and battle result.

### 3. Observation / stim layer
Translate factual events into observations for affected entities. A death may stimulate comrades, rivals, the gang and a territory. Propagation must be bounded and relevant.

### 4. Persistent entity minds/history
Characters: stable traits/tendencies, memories, moodlets, relationships, current concerns, reflections.
Gangs: identity, values, relationships, strategic condition, recurring themes.
Places: ownership, violence, economic role, rumours, recurring actors.
Region: major trends, conflicts and power shifts.

### 5. Reflection
Periodically synthesize higher-order conclusions from important retrieved memories. Reflections cite their source memories and can later be revised or superseded rather than rewriting mechanical history.

### 6. Narrative artifacts
Character biography updates, thoughts, gang chronicle, territory chronicle, battle reports, downtime reports and campaign chronicle.

## Turn-based cadence
No fake real-time life simulation. Process meaningful events. Generate downtime as sparse event-driven slices between battles. A downtime event can itself create observations and social propagation.

## LLM boundary
Deterministic code owns mechanical extraction, diffing, IDs, provenance and persistence. LLMs may interpret, infer, write, rank narrative salience and generate connective fiction, but may not invent mechanical outcomes.

## Future presentation
Expose the engine through stable local HTTP/JSON APIs. Browser UI is current client. Unity can later consume the same API.
