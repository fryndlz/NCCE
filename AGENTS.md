# NCCE - Codex Operating Brief

## Product
NCCE is the Necromunda Campaign Chronicle Engine. It is NOT a replacement for Munda Manager and must not drift into being a second roster/campaign spreadsheet viewer.

The value proposition is a persistent story engine in the spirit of Dwarf Fortress / RimWorld / X-COM: authoritative tabletop mechanical state produces fictional consequences, memories, relationships, mood, histories, downtime events and an overarching campaign chronicle.

## Permanent workspace
This repository is intended to live at `C:\Codex\NCCE`. Develop in place. Do not create versioned ZIPs as the normal workflow. Use Git for history once initialized.

## Authority hierarchy
1. Mechanical campaign truth: Google Sheet
   https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit?gid=0#gid=0
2. C-NINE authored campaign canon: Google Doc
   https://docs.google.com/document/d/1vAajSzxjaKXjAQ571gcTeM5ocqSVccUS1pljDR_Ysk4/edit?tab=t.0
3. C-NINE lore conventions from the prior project conversations `C-NINE naming and lore` and `Lore Formatting`; their essential constraints are captured below.
4. Current Necromunda rules authority: https://www.necroraw.com.ru/
5. Generated narrative is inference, never mechanical truth or authored canon.

Never write to or modify the authoritative campaign Sheet unless the user explicitly requests it. The application should read it and keep its own local derived state.

## Canonical terminology
C-NINE canonical name: `Geothermal Prospect Detail C-9`, shortened to `C-NINE`.
Do not use old variants.

C-NINE fiction uses an Imperial administrative / industrial record voice: bureaucratic classifications, cross-references, redactions, contradictory records, machine-spirit errors, liturgical language and implication rather than explicit exposition. Preserve established names and terminology from `data/lore/C-NINE Story - canonical export.txt`.

## Core design
Mechanical data is evidence. Narrative is a derived layer with provenance.

Pipeline:
`Sheet snapshot -> factual diff -> event ledger -> observations/stims -> memories/moodlets/relationships -> reflections -> character/gang/place/region narratives -> downtime reports/chronicle documents`.

The system should model:
- ganger backstory: prefer player-authored material; otherwise infer from raw stats, role, gang, history and campaign context
- gang backstory: authored if present, otherwise inferred from composition and campaign history
- territory backstory: type, ownership history, battles and generated local events
- region backstory: bird's-eye campaign history and power relationships
- ganger tracker: timestamp every future mechanical change to each fighter
- ganger mind/thoughts: current moodlets, concerns, opinions of gang/others, progress, memories and reflections
- downtime reports: event-driven inter-battle fiction inspired by the C-NINE campaign log
- battle reports: factual event plus diegetic interpretations
- campaign chronicle: emergent higher-level history

## Cognitive architecture
Adapt the Generative Agents approach:
- memory stream of observations
- retrieval weighted by recency, importance and relevance
- reflection when accumulated important memories cross a threshold
- reflections are stored as memories and retain pointers to source observations

Do NOT simulate meaningless continuous life between tabletop sessions. The natural simulation tick is a meaningful campaign event: battle result, injury, recovery, death, capture, recruitment, XP/advance, purchase/equipment change, territory change, alliance change, reputation/credit change, or generated downtime event.

Adapt Reaction System concepts:
- event -> stim
- stim is interpreted through relatively stable personality/tendencies and current context
- produces mood/reaction
- important reactions become memories
- stims can propagate socially to relevant gangmates/relationships

## Provenance
Every derived narrative datum should be tagged internally as one of:
- `mechanical_fact`
- `player_authored`
- `canon_authored`
- `inference`
- `connective_fiction`

Generated memories/reflections must retain source event IDs or observation IDs where possible. Do not silently turn inference into fact.

## UI priority
The app should not foreground rating/wealth tables. Primary navigation should foreground story:
- Chronicle / campaign situation
- Gangs and their evolving histories
- Characters with biography, tracker, memories, moodlets, thoughts, relationships and arc
- Places / territories and their histories
- Battles as narrative events
- Downtime
- World relationships / tensions

Mechanical state remains inspectable as evidence.

## Presentation
For now functionality is more important than graphics. Keep backend/API clean enough that the current browser UI can later be replaced or supplemented by Unity without rewriting the story engine.

## Current implementation
Read `docs/HANDOFF_STATUS.md` before changing code. Run tests and current application first. Continue the repository; do not rebuild from scratch.
