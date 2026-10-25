# NCCE current design: philosophy, behavior, and critique points

**Reviewed:** 25 October 2026

**Scope:** The current v0.5 hosted-access preview in this repository. This describes implemented behavior separately from the intended story engine. It is a design review aid, not a rules supplement.

## The product idea

NCCE is meant to turn a tabletop campaign into persistent fiction. The campaign Sheet supplies mechanical facts; player writing and the C-NINE archive supply authored fiction. NCCE then interprets those inputs into character histories, memories, moods, gang and place histories, downtime, and a campaign chronicle. Its intended feel is closer to Dwarf Fortress, RimWorld, or X-COM than to another roster manager.

The governing distinction is **recorded fact versus interpretation**. A Sheet row saying a fighter has five kills is evidence. “Proven killer” is an interpretation of that count. The first must remain authoritative; the second should be explainable, revisable, and visibly marked as generated. NCCE should process meaningful campaign events rather than invent a continuous off-table life.

The intended pipeline is:

`read-only Sheet snapshot → factual change → event ledger → observation/stim → character reaction → memory/reflection → updated histories and chronicle`

**Current state:** The app reads the Sheet, maintains a local current-state projection, and records factual changes. The later reaction and story update stages are still mostly a seeded prototype. This difference is central to evaluating the UI.

## What the current tabs do

| Area | Current behavior | Main design choice or limitation |
| --- | --- | --- |
| Chronicle | Shows a generated regional introduction, recent battle accounts, recent Sheet changes, and downtime excerpts. | Story leads the navigation, but much of its prose was generated once at seed time. |
| Gangs | Shows an authored C-NINE history where available and formulaic inferred histories for other gangs; detail pages show people, holdings, battles, and mechanical evidence. | Missing lore is filled from faction archetype, recorded wins/losses, rival frequency, and current holdings. |
| People | Shows each fighter's backstory, baseline change tracker, factual campaign changes, memory stream, Mind, and raw baseline fields. | A fighter is treated as a persistent narrative entity, but Mind is currently a small fixed rule set. |
| Places | Shows a generated region description and territory text based on territory type, current owner, and associated battles. | Place identity comes from campaign evidence plus hand-written flavor templates. |
| Battles | Shows Sheet results as short factual narrative anchors. | It does not reconstruct private action, motives, or a full battle report. Corrected Sheet rows can leave earlier prose marked stale. |
| Archive | Exposes the embedded C-NINE Story export. | Authored canon remains accessible beside generated text. |
| System | Shows engine and sync state. | This exposes implementation health rather than a player-facing story view. |

## Implemented code modules

This is the current v0.5 implementation map, not a target architecture. A module listed here may only provide part of its intended responsibility.

| Module | Responsibility in the current build | Important boundary |
| --- | --- | --- |
| `src/access.py` | Passphrase configuration and signed session-token validation for hosted access. | Access control does not change campaign data authority. |
| `src/google_sheets.py` | Fetches the link-readable Google workbook as XLSX. | Read-only source adapter; it does not edit the workbook. |
| `src/snapshot.py` | Parses workbook tabs and normalizes campaign, gang, fighter, territory, and battle rows. | The normalized battle record has gang-level participants; it has no fighter attendance list. |
| `src/models.py` | Dataclasses describing fighters, gangs, battles, and a campaign snapshot. | Data shapes only; not the narrative rules. |
| `src/diff.py` | Compares consecutive snapshots and drafts deterministic factual events for changed fields, roster additions/removals, battle additions/corrections/removals, and unambiguous territory transfers. | It records evidence and event subjects. It does not produce memories or reactions. |
| `src/sync.py` | Persists snapshot provenance, drafts/records factual events, and refreshes the current-state projection. | Snapshot capture time is observation time; it is not substituted for an unknown event date. It does not rerun story generation. |
| `src/store.py` | SQLite schema access, snapshot persistence, entities, event ledger, projections, and detail/API query assembly. | Current projection and immutable event ledger are different records. |
| `src/migrations.py` | Adds schema versions, provenance tables/links, and backfills legacy seed data and event evidence. | Backfill links can only use evidence available in the old records; they cannot reconstruct absent chronology. |
| `src/narrative.py` | Deterministic templates/rules for fighter and gang biographies, moodlets, current-thought snippets, battle anchors, territory/region prose, and downtime reports. | These are seeded/template outputs, not a live event-to-memory engine. |
| `src/seed.py` | Creates the initial SQLite database and seed-time narratives, fighter observations, moodlets, and reflections. | The operation is initialization; live sync does not call it again. |
| `src/server.py` | HTTP/JSON API, static app serving, startup synchronization, periodic synchronization, manual refresh, and request routing. | It schedules data refresh, not mind/reflection regeneration. |
| `src/baseline_data.py`, `data/fighters.json`, `data/lore/` | Legacy/static baseline data, roster source, and frozen C-NINE authored story export. | Static baseline values are not a substitute for the live Sheet. The live C-NINE document remains canonical when accessible. |
| `web/app.js`, `web/index.html` (and web assets) | Browser navigation, detail rendering, and styles for Chronicle, Gangs, People, Places, Battles, Archive, and System. | “People” is the current UI label for fighters; the campaign entity is a fighter. |
| `tests/test_core.py` | Dependency-light checks for parsing, persistence, idempotency, corrections/removals, and migration behavior. | Test coverage does not establish that the intended story loop exists. |

### Data path as implemented

`Google Sheets XLSX → snapshot parser/normalizer → snapshot comparison → factual campaign-event ledger → SQLite current-state projection → HTTP/JSON → browser UI`

The seed-time narrative path is separate:

`static baseline + authored C-NINE export → deterministic narrative templates → initial fighter memories/moodlets and initial gang/place/region/battle/downtime text`

The second path is not currently triggered by new live events. This is the main break between the implemented app and the intended story-engine pipeline.

The browser is a client of a Python HTTP/JSON service backed by SQLite. The app checks the link-readable campaign Sheet on startup and every 15 minutes while running; the Refresh button requests another read. It does not write to the Sheet. An optional passphrase protects the hosted preview. The original baseline cannot establish when older XP, injuries, or other fighter changes occurred. Future snapshot differences get an observation time; an actual event date is used only when the source supplies one.

## What “Mind” means today

The badge is **`label · intensity`**. The label is a rule-selected narrative state. The number is a hard-coded *intensity score*, not a percentage, probability, stat, or score from Necromunda rules. There is no published calibration explaining why 55 feels different from 45. The italic sentence below each badge is a fixed first-person line attached to that label, not a newly composed thought specific to that fighter.

Each moodlet also has a `valence` used only to choose a positive, negative, or neutral badge border, and a `source` string stored in the database. The current People UI does not display either the source or the calculation. Moodlets are shown in descending intensity. The seed rule takes at most five labels per fighter, in rule order, before the UI sorts them; thus a sixth eligible label can be omitted even if its intensity is high.

### Complete current label catalog

These are **all 12 labels implemented by the seed rules**, not open-ended personality types. Counts in the last column are from the local database reviewed on 25 October 2026; they describe that seed, not a permanent campaign total.

The code does not define a formal higher-level taxonomy of “mind types.” These 12 entries are all called moodlets in code/UI, but they mix conditions, emotions, social identity, role pressure, and combat reputation. The following groupings are explanatory only; they are not separate implemented categories:

- Condition/status: `Dead`, `Recovering`, `Marked by injury`.
- Emotion or social response: `Humiliated`, `Grudge`, `Scarred reputation`.
- Combat reputation: `Blooded`, `Proven killer`.
- Role/drive: `Responsibility`, `Ambition`.
- Group identity: `Crew`.
- Fallback: `Watchful`.

`Dead` is a status marker rather than a living fighter's mental state. `Crew` is persistent belonging, not a temporary mood. This mixed taxonomy is a current implementation fact, not a settled design decision.

| Label | Trigger from seeded fighter data | Intensity | Tone | Seeded fighters |
| --- | --- | ---: | --- | ---: |
| Dead | Status is `Killed`; returns this label alone. | 100 | Negative | 5 |
| Recovering | Status contains `recovery`, or Effects contains `convalescence`. | 58 | Negative | 5 |
| Marked by injury | Effects contains `hobbled`, `spinal`, `hand injury`, `eye injury`, `enfeebled`, or `head injury`. | 48 | Negative | 19 |
| Humiliated | Effects contains `humiliated`. | 62 | Negative | 5 |
| Grudge | Effects contains `bitter enmity`. | 72 | Negative | 4 |
| Scarred reputation | Effects contains `horrid scars` or `impressive scars`. | 45 | Positive | 10 |
| Proven killer | Kills are at least 5. | `min(80, 40 + 3 × kills)` | Positive | 8 |
| Blooded | Kills are 1–4. | 35 | Positive | 34 |
| Responsibility | Class is exactly `Leader`. | 55 | Negative | 7 |
| Ambition | Class is exactly `Juve`. | 45 | Positive | 14 |
| Crew | Gang is C-NINE. | 65 | Positive | 20 |
| Watchful | No other rule produced a label. | 25 | Neutral | 19 |

For example, **“Watchful · 25”** means only that none of the other seed conditions matched. Its accompanying text is “Nothing is settled. That is normal.” It does not mean the fighter has a measured watchfulness trait or that 25 is a threshold. A C-NINE fighter cannot receive this fallback because the C-NINE `Crew` rule always applies, unless the fighter is dead.

**Gravittar Beta** is the name in the current roster. The seeded roster records 5 kills and the local database contains **“Proven killer · 55”** for them: `40 + 3 × 5 = 55`. The line below it is “I know what happens when the shooting starts, and so do the others.” At 6 kills the rule gives 58; it stops increasing at 80 from 14 kills onward. The app has not established whether the killings affected the fighter's attitude in this way; that is an authored interpretation of the count.

Several rules can apply at once: a wounded leader with five kills can have injury, Proven killer, and Responsibility together. There is no mutual-exclusion model or explicit emotional conflict resolution. `Dead` is an exception that replaces all other current labels.

### When Mind changes

Moodlets are generated in `seed.py` from the fighter's status, Effects text, kills, class, and C-NINE membership, then stored in `moodlets`. The live Sheet sync updates current fighter values and writes factual changes to the campaign event ledger. It **does not rerun the moodlet rules**, expire moodlets, or generate a reaction to a new event. Consequently a current Mind badge may disagree with the current raw baseline after a Sheet update. A newly discovered fighter can appear with no generated Mind or backstory. The labels are best understood as **seed-time interpretations**, despite the section heading's present-tense wording.

## Backstory, tracker, and memory

**Backstory.** Where a C-NINE personnel entry matches a roster name or alias, the app uses that authored text. Other fighters receive template prose from class, type, XP, kill count, Effects, and status. Other gang histories use faction-specific archetype text, battle record, repeated opponents, and territory holdings. Territories get type-specific flavor plus ownership/battle facts. These are inferences, not discovered biography. The source label shown in the UI indicates authored versus mechanically inferred material, though provenance is not displayed consistently on every generated paragraph.

**Change tracker.** The initial `fighter_events` entries are baseline observations: XP, kills, advancements, Effects, and status as imported. They have no historical event date. The separate **Recorded campaign changes** list draws from the append-only event ledger, including changes detected between later Sheet snapshots. In the legacy tracker, the title “Status changed before baseline” is stronger than the evidence: the baseline proves the status, not when it changed. Read its detail as a state observation.

**Memory stream.** At seed time, each baseline observation is copied into a memory with an importance score: 4 for the general baseline, 7 for advancement or Effects, and 9 for death status. The app also copies up to three highest-intensity moodlet sentences into `reflection` memories, adds a fixed advancement thought where applicable, and a C-NINE/Voss-specific line. Those generated reflections have importance 5.5 and confidence 0.65. This is a thin rule-based summary, not yet a system that retrieves memories by recency, relevance, and importance or derives new thoughts from experience. The UI lists memory importance and source but does not explain the scoring scale.

### Exact current memory classification and scoring rules

The word “observation” currently means an imported baseline statement, not a runtime perceptual record generated from every live event. In `seed.py`, the fighter event rows and their observation memories are initialized as follows:

| Seed observation | Importance | Confidence | Date semantics |
| --- | ---: | ---: | --- |
| Baseline summary (XP, kills, status) | 4 | 1.0 | No event date; historical timing is unknown. |
| Advancement field (for example, `Cool` or `Willpower`) | 7 | 1.0 | No event date; it is known at baseline, not when it was gained. |
| Effects/injuries field | 7 | 1.0 | No event date; it is known at baseline, not when it occurred. |
| Killed status | 9 | 1.0 | No event date unless another source supplies one. |
| Recovery or Retired status | 4 | 1.0 | No event date; this is still only baseline state. |

Those numbers are hard-coded sorting weights. There is no documented calibration, normalization, cap, decay, or threshold. The database query orders memories by importance descending, then insertion ID descending. It does not calculate retrieval relevance or recency.

In the current seed, an entry is classified as `reflection` when it is one of the prewritten outputs returned by `current_thoughts`: up to three thoughts attached to the highest-intensity moodlets, a generic advancement sentence if any advancement is present, and a special line for a C-NINE fighter whose name contains `Voss`. The final list is capped at four. Each is assigned importance 5.5 and confidence 0.65. This is a labeling choice in the seed code; no synthesis from retrieved memories takes place. The migration associates legacy reflections with available baseline observations, but the links do not represent a live reasoning trace.

The engine currently has **no implemented rule** for: creating a memory from a newly detected live event; deciding whether that event is an observation or reflection; accumulating importance toward a reflection threshold; selecting evidence through recency/relevance retrieval; expiring or superseding a mood; or revising an earlier inference. The architecture documents those as intended behavior, not implemented behavior.

### `Cool` example: mechanic versus voice

Maex is listed as a Subtek in Ethernetans 2.0. The baseline advancement field contains `Cool`, alongside XP 5 and 2 kills. The current observation displays that raw field as the whole memory (`Cool`, importance 7). That preserves the mechanical token but reads like a label rather than a fighter's memory. A future presentation should keep the evidence inspectable as “Advancement recorded: Cool” and, separately, generate a clearly marked inference in an appropriate fighter voice. It must not pretend to know the moment of the advance or a specific scene that the source does not record.

### Observation/reflection rule status

There is no production rule today that classifies all campaign content as observation versus reflection. Present code behavior is:

1. The seed creates authoritative-sheet observations from baseline fighter fields and gives them the fixed scores above.
2. The seed turns selected generic moodlet strings into generated `reflection` rows, without retrieving or synthesizing their source observations at generation time.
3. Live sync records mechanical changes and their provenance in the campaign event ledger. It does not create corresponding memory rows, mood changes, or reflections.
4. The architecture target is event → affected-entity observation/stim → contextual reaction/mood → memory → evidence-linked reflection after accumulated important memories. The importance formula, reflection threshold, retrieval function, decay/lifecycle rules, and conflict resolution are not specified in code and remain design decisions.

The five narrative truth classes (mechanical fact, player-authored, canon-authored, inference, connective fiction) classify provenance/authority; they are **not** memory types. Current memory types are the two strings `observation` and `reflection`.

## User-confirmed design direction for Memory and Mind

This section records the requested target behavior. It is **not implemented yet** and does not imply approval to begin app implementation.

### Memory stream: fighter history

The Memory stream is the fighter's chronological history of meaningful things that happened to them. Each event memory should present two visibly distinct parts:

1. **Mechanical trigger / evidence block:** a short, structured statement of what the authoritative source recorded (for example, `Advancement recorded: Cool`, `Effects changed: none → Critical Injury`, `XP: 4 → 5`, or `Battle: C-NINE defeated Kły Sprawiedliwości; Takeover; Promethium Cache`). Style it as factual evidence with source/date/provenance cues and a different visual treatment from the prose.
2. **Diegetic fighter voice:** a separate prose paragraph interpreting what the event means to this fighter. It is generated narrative, not a claim about the mechanical result. Its voice should draw on authored backstory first, then a voice profile inferred from role, gang, characteristics, skills, history, and prior memories. Mechanical and narrative claims must remain distinguishable at a glance.

An entry should say whether it is an **observation** (a specific event experienced/recorded) or a **reflection** (a conclusion drawn from one or more cited memories). Each generated paragraph retains links to its source events and is marked as inference. The factual block remains reproducible even if the prose is regenerated. The stream is campaign history, not a list of current feelings; it is not limited to the two-to-four items displayed in Mind.

The fighter voice should be individualized, not a direct stat-to-stereotype mapping. Physical characteristics can inform embodied vocabulary and confidence about physical hardship; Cool/Willpower/Leadership/Intelligence, class and skills can inform how a fighter frames danger, authority, planning, or fear. Backstory, authored dialogue, gang culture, and accumulated experience should constrain or override weak signals from a single stat. A high Toughness value alone must not assert that the fighter is emotionally fearless.

### Mind: current thoughts retrieved from memory

Mind is a compact current view, normally **two to four thoughts**, retrieved from the Memory stream. It should favor recency, importance, relevance to current campaign context, and character-specific biases/personality. These are reactions the fighter is likely preoccupied with now, not permanent traits and not a second copy of the full history. Each thought should be traceable to one or more memories/events. When fewer than two supported thoughts exist, the system should avoid padding with invented generic thoughts; the exact empty/low-evidence presentation remains to be designed.

The intended retrieval pattern adapts Generative Agents: score candidate memories using recency, importance, and relevance, then apply character-specific salience/bias and select a small set. The present design does **not** yet specify the exact formulas, time decay, normalization, tie-breaking, or relevance query. Those must be explicit and tunable before being treated as implemented logic.

### Candidate campaign-event triggers for memory and active mind

Necromunda's post-battle sequence, lasting injury, experience/advancement, promotion, equipment distribution, capture, and downtime rules suggest the following event families. These are candidate narrative triggers, not a claim that all source fields are currently ingested.

| Event family | Candidate fighter memory / reaction | Evidence availability in current NCCE inputs |
| --- | --- | --- |
| Battle participation and outcome | Entering a battle; gang victory, defeat, draw, retreat/bottling; scenario objective or territory at stake. | Battle date, scenario, attacker/defender gangs, winner and territory are present. Individual attendance, draw/retreat details, objectives, and per-fighter contribution are not consistently present. |
| Combat contribution | XP for taking part, rallying, assisting recovery, causing Serious Injury or taking an enemy Out of Action; a recorded kill or notable survival. | Current fighter snapshot detects XP and Kills totals. It does not identify why XP changed or which enemy/action caused it. Do not turn an XP delta alone into a specific deed. |
| Injury and survival | Flesh wounds/lasting injuries, characteristic reductions, Critical Injury, Convalescence, Recovery, death, or repeated injury. | Current Effects, Status, and characteristic deltas are detected. Momentary Flesh Wounds and the in-battle sequence may be absent once the roster is updated. |
| Capture, rescue, and return | Captured by a named gang, rescue attempt/outcome, release, sale/disposal, or return from captivity. | Roster presence/status/notes may expose some results, but a structured capture/rescue event is not guaranteed in the current normalized snapshot. |
| Experience and identity | XP earned/spent, characteristic advancement, skill gained, promotion (for example Juve → Specialist or Specialist → Champion), Leader succession, role/type change, recruitment or retirement. | XP, stats, Skills, Advancements, Class/Type, and roster membership are diffed when represented in fighter rows. The reason or precise timing may still be unknown. |
| Weapons and equipment | Receiving, losing, replacing, transferring, or relying on a weapon or Wargear; loss of equipment on death or through roster changes. | Weapons and Wargear current fields are diffed. A source change does not always explain whether an item was bought, transferred, discarded, or lost. |
| Relationships and gang losses | Rival encounter, repeated opponent, gangmate's death/capture, rescue, leadership change, shared victory/defeat, recruitment or departure. | Gang/battle entities, fighter roster changes and some battle outcomes exist. Personal relationships, battle attendance, and who witnessed an event are not explicit. |
| Campaign position | Territory taken/lost, gang reputation/standing shifts, changed home/operations, repeated conflict over a place. | Territory ownership and gang fields are ingested; fighter-level emotional impact must remain an inference. |
| Downtime and post-battle choices | Medical treatment, work/trading, equipment assignment, recovery, promotion, recruitment, or other downtime consequence. | Some resulting state deltas are visible; the action itself is often not recorded as a structured event. |

The Core Rulebook supports these event families through its Lasting Injuries table, post-battle sequence, XP and advancement rules, equipment distribution, and capture/recovery procedures. A rulebook event should only become a fighter-specific memory when the campaign source records it or the approved inference policy supports the link. For example, an XP increase does not prove that a fighter caused a Serious Injury; XP can come from participation, objectives, rallying, assistance, or combat contributions.

### Mind-label design recommendation

The present twelve labels mix persistent identity, event consequences, social reputation, and temporary mental state. For the next design pass, treat labels as **active salience/mood tags** that help retrieve memories, not as the complete contents of Mind. Add trigger families for:

- growth/advancement and promotion;
- battle anticipation, victory, defeat, retreat, and shared loss;
- injury, recovery, critical condition, and survival;
- kills, violence, or proven combat contribution when supported;
- new/lost/replaced equipment;
- capture, escape, rescue, death, and bereavement;
- leadership/responsibility, rivalry, loyalty, and gang change;
- territory and mission consequence.

Do not create one permanent label for every mechanical field. Separate enduring identity/disposition (voice/personality profile), current emotional or bodily state (mind labels), and remembered events (Memory stream). The names, trigger conditions, lifetimes, intensities, and conflict rules for any expanded label set remain a design specification to agree before implementation.

### Battle data and fighter attribution

The current campaign battle row contains date, scenario, attacker gang, defender gang, winner, territory, and territory claimer. Munda Manager's Battle Logs view likewise shows gang participants (including attacker/defender roles) and winning gang(s). The current event model links battle events to gang entities and the territory; it has no fighter-attendance field. Individual fighter rows separately record current XP, kills, Effects, status, and other fields. Those changes may be strong post-game evidence when observed alongside a battle, but there is no explicit source key tying each changed fighter to that battle. Narrative generation must distinguish “gang took part” from “this named fighter attended”; a fighter-specific injury can support a fighter consequence, but attendance should only be asserted where the source or an approved attribution rule supports it.

**Provenance.** The design calls for five truth classes: `mechanical_fact`, `player_authored`, `canon_authored`, `inference`, and `connective_fiction`. The newer campaign ledger stores structured source IDs, locators, confidence, and links to affected entities. Some older seeded narrative rows have looser source strings, so provenance is not yet equally rigorous across all visible content. Confidence is a stored value about support for an entry, not a likelihood that a fictional thought occurred.

## Why these choices were made, and what remains unproved

1. **Story first, mechanics as evidence.** The interface leads with Chronicle and histories while keeping XP, kills, reputation, and other mechanics available for inspection. The open question is whether generated prose is compelling and specific enough to justify its priority over raw records.
2. **Deterministic factual core.** Sheet parsing, snapshot differences, identities, and event records are code-driven. This makes changes auditable and prevents fiction from silently changing a game result. Ambiguous or undated historical changes remain ambiguous or undated.
3. **Sparse event cadence.** The intended “simulation tick” is a meaningful campaign event, not every minute of fictional time. This helps avoid invented activity, but the event-to-reaction layer has not been connected yet.
4. **Authored canon has priority.** C-NINE writing is preserved and should constrain generated text. Other gangs need distinct voices from player input and play history; current faction templates are only a starting point.
5. **Simple seed rules make a demo legible.** Fixed labels and sentences let the UI demonstrate a “mind” without a language model. Their thresholds and numbers are design constants without documented playtesting or psychological meaning.
6. **Many scopes from one event.** The intended engine would let one battle affect fighters, relationships, gangs, places, and the campaign. Currently the factual event is stored, while most of those downstream updates do not occur.

## Decisions worth critiquing

- Should `Mind` show a label and arbitrary number at all? A plain-language cause such as “5 recorded kills” may communicate more than “55,” or intensity may need a defined scale.
- Should `Watchful` be a meaningful default disposition or an explicit “No specific reaction yet” state? The present label implies a personality conclusion without evidence.
- Should five kills automatically make someone feel confident, and should every fighter get the same first-person sentence? The rule currently conflates reputation, capability, and private thought.
- Should persistent conditions (scars, class, group belonging) live in the same list as temporary emotional states (humiliation, recovery)? Their lifecycles differ.
- Should a death be presented as the dead fighter's own moodlet? The current line correctly says no thoughts are generated, but its placement under Mind can still mislead.
- Should a current Sheet change immediately recalculate Mind and memories? If so, the UI needs to show when a reaction was generated, what caused it, and whether it has expired or been superseded.
- How should other gangs acquire authored voices and character variation, so C-NINE's special treatment does not leave everyone else with generic template prose?
- What evidence is required before a narrative inference becomes a stable character trait, relationship, or chronicle claim? The current rules use limited evidence and rarely show it next to the prose.

## Implementation references

- Product intent and authority: `docs/PRODUCT_VISION.md`, `AGENTS.md`, `docs/STORY_ENGINE_ARCHITECTURE.md`.
- Moodlet and narrative rules: `src/narrative.py` (`moodlets`, `current_thoughts`, backstory and downtime functions).
- Initial generation: `src/seed.py` (fighter events, memories, moodlets, reflections, and reports).
- Current-state refresh and API queries: `src/sync.py`, `src/store.py`, `src/server.py`.
- What the user sees: `web/app.js`, `web/index.html`.
- Verified implementation gaps: `docs/IMPLEMENTATION_AUDIT.md`, `docs/HANDOFF_STATUS.md`.
