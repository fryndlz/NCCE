# NCCE 0.17.0 — current technical design

**Implementation:** 0.17.0. **SQLite schema:** 15. This is the current specification, not a list of desired future features. Historical behavior is in Git and CHANGELOG.md. Hosted source/version and verification are recorded in the changelog; an implementation entry is not proof of live deployment.

The owner approved fighter-relevant logical time, a half-life of **10 relevant events**, **one step per distinct meaningful change**, and **no fixed expiry**. Calendar-based cognitive decay in 0.16.0 is superseded. The detailed specification, worked examples, paper comparison and executable verification map are in [Fighter event clock](FIGHTER_EVENT_CLOCK.md).

## 1. Product and authority

NCCE is an event-driven campaign story engine, not a replacement roster manager or a continuous daily-life simulator. Its loop is Sheet snapshot → factual changes → sourced observations → reflections and current thoughts → campaign narratives. Tabletop mechanics remain authoritative; fiction cannot change them.

Authority: the read-only Krakamunda Google Sheet for mechanics; authored fighter/Sheet backstories and the frozen canonical C-NINE export for their relevant authored context; verified rules/reference context where explicitly supplied; generated narrative last. The five provenance classes are `mechanical_fact`, `player_authored`, `canon_authored`, `inference`, `connective_fiction`. Observation/reflection are memory types, not provenance classes.

C-NINE is Geothermal Prospect Detail C-9. Its vocabulary is scoped to its context, not applied universally to other gangs. Individual attendance, injury mechanisms, named attacks and hidden motives cannot be invented as recorded facts.

## 2. Module map

| Module | Responsibility |
| --- | --- |
| `google_sheets.py`, `snapshot.py` | Read-only workbook fetch, XLSX parsing, current-state normalization and explicit authored sections. |
| `sync.py`, `diff.py` | Immutable snapshots, deduplication, factual deltas, correction/removal chains, current projections. |
| `store.py`, `migrations.py` | Persistent SQLite, read-only readers, APIs, authority/evidence links, migrations and verified pre-upgrade backup. |
| `campaign_history.py` | Versioned Munda Manager archive records, exact battle/session joins and derived timeline intervals. |
| `story_engine.py` | Supported memory triggers and importance, shared news, reflection batches, versioned artifacts and cause retrieval. |
| `fighter_event_clock.py` | Canonical fighter-relevant event sequence, correction deduplication, formation positions and event-distance recency. |
| `fighter_mind.py` | Separate current-thought prose, causes, ranking/families, persistence and resolution/supersession. |
| `story_prose.py`, `writing_director.py` | Rule-based identity/voice evidence, stimulus weights, dates and semantic document presentation. These helpers are not the live prose provider. |
| `narrative_context.py` | Authored/accepted context, historical roster boundary, source-backed document packets and chronology. |
| `llm_writer.py`, `writer_contract.py` | Responses-provider calls, common/form instructions, active Workshop policy, objective validation, cache, budgets, usage and exact request/response audit. |
| `writer_planning.py`, `territory_reference.py` | Free source/context planning, verified Dominion type references, pinned plans and compact repetition hints. This is literary planning, not autonomous fighter action planning. |
| `writer_workshop.py`, `workshop_optimizer.py`, `workshop_guidelines.py` | Source samples, one-call trials, immutable edits/revisions, category studies, fresh-context validation and explicit owner activation. |
| `codex_review_queue.py`, `workshop_interventions.py` | Actual JKSimmons/StoryTechMan job handoffs, saved assessments, scoped investigation/repair/release gates. |
| `world_streams.py` | Source-linked gang/place event accounts and separately marked connective fiction. |
| `authored_archive.py` | Read-only source-bounded The Prospect and The Deep Answers excerpts. |
| `seed.py`, `narrative.py` | Initial compatibility seed and legacy templates. Legacy moodlets are not current Mind. |
| `server.py`, `access.py` | HTTP API, same-origin/auth gates, single writer lock, startup/manual/scheduled read-only sync. |
| `web/app.js`, `web/writing.js`, `web/workshop.js`, `web/writing_activity.js` | Dossiers, evidence, timeline, date layers, Workshop controls and saved workflow activity. |

## 3. Runtime and persistence

Startup opens or seeds the workspace DB, verifies a consistent backup before any schema upgrade, and applies migrations through schema 15. It prepares derived state without paid startup generation when a provider is configured. Startup, scheduled (normally 15-minute) and manual refreshes then use the same read-only Sheet pipeline. The scheduling interval does not advance cognition.

Snapshots retain original input. Events retain stable identity, subjects, source/occurrence/observation dates and correction links. Missing fighters stay in historical storage; disappearance is not death. Current projections update mechanics and authored inputs. Regeneration is fingerprinted/idempotent; an unchanged import does not create observations or event-steps. Code/context changes may version derived records, but rewriting prose adds no steps.

`story_memories` stores active and superseded observations/reflections with causes and citations. `story_artifacts` stores generated documents. `fighter_thoughts` stores separate current prose, source memory/factual causes, inspectable generation context, writer status and lifecycle. Old `expires_at` values are compatibility data only and are ignored/cleared on refresh. Historical `fighter_events`, `memories`, `moodlets` remain; API `legacy_moodlets` labels the seeded rows, while `moodlets` aliases the current `mind` list.

Ordinary automatic writing remains paused. Supported causes/candidates can exist with pending/error prose. Dossier reads never call the provider. Exact paid requests/responses and usage are retained independently of the current source packet. Ready thoughts and completed generated biographies are retained across ordinary refresh/policy changes; authored content is protected. This release authorizes no bulk generation or policy activation.

## 4. Biography, observations and reflection

Biography establishes stable formative identity. Authored text wins. An unfinished generated baseline uses the earliest available roster/voice; a completed generated biography is not rewritten because XP, rank or injuries change. Those developments belong in observations/reflections. A separate explicitly authorized replacement would be a distinct operation.

An observation interprets one supported event, or an explicitly undated baseline state. Its first-person prose is inference; mechanical evidence and provenance are separate. Direct changes and bounded shared gang news create observations even when the writer is paused. Authored background is supplied as a voice/prior-life lens, never replayed as a current incident. Historical roster context is used where available to avoid borrowing future conditions. Accepted generated background can supply fictional continuity, never mechanical proof.

### Base event rules

Importance is narrative salience on a **0–10 scale**. It is a design weight used for reflection and selection, not a Necromunda characteristic, probability, or psychological measurement. The current rule table is:

| Event type | Base importance | Initial topic tags |
| --- | ---: | --- |
| `baseline` | 4 | identity |
| `advancement` | 7 | advancement, growth |
| `effect` | 7 | injury |
| `status` | 6 | status |
| `fighter_xp_changed` | 4 | growth, experience |
| `fighter_kills_changed` | 7 | violence, kills |
| `fighter_advancement_changed` | 7 | advancement, growth |
| `fighter_skills_changed` | 7 | skill, growth |
| `fighter_effects_changed` | 7 | injury |
| `fighter_status_changed` | 6 | status |
| `fighter_weapons_changed` | 6 | equipment, weapon |
| `fighter_wargear_changed` | 5 | equipment |
| `fighter_stat_changed` | 6 | growth |
| `fighter_recruited` | 6 | belonging, recruitment |
| `fighter_unlisted` | 3 | roster |
| `gang_battle_outcome` | 6 | battle, outcome |
| `gangmate_loss` | 9 | grief, belonging |
| `gangmate_captured` | 8 | captivity, belonging |
| `territory_holder_changed` | 6 | territory, outcome |
| `combat_record` | 6 | violence, kills |
| `gang_reputation_changed` | 6 | reputation, belonging |
| `gang_alignment_changed` | 8 | allegiance, belonging |

`baseline`, `advancement`, `effect`, and `status` also bridge legacy seed observations. `combat_record` is a supported rule/writer category; baseline kills currently also appear in the baseline evidence summary, rather than being automatically expanded into a separately dated kill event. Unknown classifier event types default to importance 4 with a campaign tag, but automatic direct-fighter generation is limited to event types in this rule table.

### Classification overrides

- `Critical Injury` in the new value/detail sets importance **9**, a Critical injury title, and `critical`/`injury` tags.
- A status of `Killed` or `Dead` sets importance **10** and the `death` tag.
- A Class or Type change uses importance **8** with `promotion`, `growth`, and `responsibility`. The actual before/after role stays in evidence; a type change is not rules validation that the change was a legal promotion.
- A Cost change uses importance **2** and `roster`, so it is recorded without dominating reflections.
- A Status change to Active with a previous value gets a return-to-duty title and `return`/`recovery` tags.
- An XP decrease is described as an experience-balance decrease. It is not automatically called a loss of knowledge or assumed to be spent on a particular advancement.
- Recovery/Convalescence, Captured, Humiliated, Bitter Enmity, scars, and retirement terms add the corresponding concern tags. Other injury terms add `injury`.
- Gang outcome memories add `victory` or `defeat` according to the recorded winner; no recorded winner leaves a battle concern. A group result is shared news and does not establish that each member attended.

Observation narrative confidence is currently the fixed design value **0.65**. Factual event confidence remains separate. The number describes support for an interpretation, not the likelihood that the fighter literally said its generated words.

### History and dates

Memory is shown with recent recorded changes first and baseline state explicitly labeled “Known at baseline · date unknown.” For later fighter changes, `observed_at` records the snapshot in which they were found, and `occurred_at` remains null unless a source supplies an actual date. A battle's recorded date is used for the battle, not copied onto undated injuries or advancements merely because they might be related.

Legacy seed observations and the earliest live fighter state remain the basis of baseline evidence. Current XP cannot silently drift into a historical baseline statement when the latest roster changes. The first live comparison bridge compares only known old fields; fields never present in the seed cannot manufacture stat-change memories.

## 5. Shared events and voice

Direct fighter changes are personal causes. Gang results, territory/reputation/alignment and bounded gangmate death/capture news can be shared causes; they do not prove attendance or witnessing. Corrected/removed outcomes resolve against current active factual records. Amended social news marked `history_only` is excluded from current concerns but remains an experience in the event clock. Baseline states do not become a fabricated recruitment/advancement timeline.

Explicit authored identity/voice corrections are separate persisted inputs. Unknown species, gender/pronouns, upbringing, private beliefs and relationships are not guessed from names. Faction, role, supported authored cues and mechanics provide explainable tendencies, not diagnoses or universal stereotypes. Generic faction context is heuristic; general fighter-specific rulebook retrieval is not implemented.

Mechanical tendencies add the following traits:

| Input | Inferred voice trait |
| --- | --- |
| Leader or Champion | responsible |
| Juve or Prospect | aspiring |
| Toughness at least 4, or Wounds at least 2 | enduring |
| Strength at least 4 | physical |
| Intelligence from 1 through 5 | analytical |
| Cool from 1 through 5 | composed |
| Willpower from 1 through 5 | resolute |
| At least 5 recorded kills | blooded |

For the relevant characteristics, lower target numbers mean better values; the rules above use the recorded target value. Other characteristics have event-specific advancement/reduction prose even when they do not add a persistent profile trait. Endurance is not treated as proof of emotional fearlessness. A strength trait supplies an embodied frame of reference without claiming a personality is determined by a stat.

Stimulus attention starts at 1.00 per topic, adds 0.15 per supported mapped tendency and 0.30 for a matching current condition/role, capped at 1.50. The writer receives up to five elevated topics. These guide attention only; they do not change mechanics, event importance or retrieval weights. Source facets and their basis remain inspectable in fighter profiles.

## 6. Reflection algorithm

Reflection is generated per fighter and observation batch (normally target snapshot). Require at least two observations, each importance >=4, with total >=12; cite up to four sorted by importance and stable key. Reflection importance is `min(10, round(mean(cited importance)+0.5,1))`, confidence 0.60. The model receives cited facts/tags/dates and ready observation prose only; stale paragraphs are not positive examples. Citation IDs and event/evidence unions persist.

Reflection prose is model-generated when enabled, not produced by a local phrase table. Production and Workshop use `reflection_observations` and the same multi-observation packet; a reflection is not assigned a misleading first source event. No new reflection for a deceased fighter. Formation position is the latest cited causal event; generating/rewording it later does not reset recency. Reflections do not increment the factual clock.

The current trigger is batch-based. Cross-batch accumulation, question-driven semantic retrieval and recursive reflection-on-reflection trees from the paper are not implemented.

## 7. Logical recency and relevance

One distinct supported factual change relevant to this fighter is one step. Clock input is the factual causes of that fighter's nonbaseline observation memories, including historical resolved experiences. It is not all campaign activity. Direct/shared versions of the same event and correction chains count once. One battle producing injury, XP and a gang result can therefore add three steps. Unrelated gang activity, refreshes, prose calls, drafts, reflections and app access add zero.

Dates establish factual order, using occurrence where known and first observation otherwise; unknown/tied order has a stable identifier tie-break. No duration is measured. Baseline formation is position zero. An observation is anchored to its causal event; reflections and thought causes use the latest cited event position. Derived writing timestamps are audit timestamps, not psychological time. Repairing factual chronology may repair positions; it is not an extra experience.

`distance = head - formation_position`

`recency = 2 ** (-distance / 10)`

Selection score remains `0.40*(importance/10) + 0.30*recency + 0.25*relevance + 0.05*character_bias`. Ten subsequent relevant changes halve the recency term; ten idle years change nothing. Reads do not reinforce recency. This creation/cause-based choice is the owner's event-driven adaptation, not the paper's last-access-hours implementation.

Relevance is 1.0 for current condition/role overlap, 0.65 for battle/equipment/promotion/advancement/return topics, 0.25 otherwise; an Active return is 1.0. Character bias is 1.0 for preferred profile topics, otherwise 0.5 for an active concern, otherwise zero. Preferred topics use the explicit mapping in `select_mind` (e.g. practical→equipment/weapon/return; analytical→skill/advancement/equipment; responsible→belonging/grief/outcome/promotion). No embeddings or semantic-query similarity are used.

## 8. Current Mind

Rank causes deterministically, suppress duplicate primary labels and overlapping factual evidence. Exclude death/history-only from concerns, resolved bodily/captivity concerns and unsupported baseline/unanchored causes. Distinguish a concern losing selection (`superseded`) from a changed underlying condition/death (`resolved`). No fixed day/count expiry exists. Important old concerns may remain or return if still relevant.

At most four candidates survive, one per family: condition, battle, grief, equipment, progress, return, social. Battle/equipment use the newest eligible event-position cause; this prevents an old victory/defeat pair filling the current view. The condition family unifies overlapping bodily concerns. Candidate prose is a separate first-person current thought of one or two sentences, target 12–40 words, not a copied memory or a new incident. Ready wording is reused for the same cause/current-condition/identity key.

Only ready, nonempty current-thought prose appears in cards. `mind_status` reports pending/error/candidate counts; pending prose never fills a visible thought slot. Each thought links to its source memory/events and exposes score components, formation position and subsequent relevant event count. There may be fewer than four or no ready thoughts; there is no generic filler. Deceased fighters have none. Memories remain in history after a concern resolves or is displaced.

### Complete current label catalog

These are the **28 implemented topic labels**. They are retrieval/display labels, not mutually exclusive personality types. Death is a historical status, not a Mind label.

| Internal tag | Display label | Internal tag | Display label |
| --- | --- | --- | --- |
| critical | Critical injury | injury | Living with injury |
| recovery | Recovering | return | Back on duty |
| captivity | Captivity | grief | Loss |
| growth | Progress | advancement | Advancement |
| skill | A new skill | promotion | New responsibility |
| equipment | Equipment | weapon | A changed loadout |
| victory | Victory | defeat | Defeat |
| battle | The gang's last battle | territory | Ground held and lost |
| kills | The cost of violence | belonging | The gang |
| identity | A place in the gang | humiliation | Humiliation |
| grudge | A grudge | scars | Scars |
| reflection | Looking back | roster | An uncertain place |
| retirement | Leaving the line | status | Current condition |
| reputation | The gang's name | allegiance | Allegiance |

## 9. Writing and Workshop

Fifteen forms include biography, observation (`fighter_memory`), reflection and current thought (`fighter_mind`) as distinct categories. Authored biographies are read-only sources rather than generated replacement samples. Mind samples inspect the stored current source packet before the shared planning pass; reflection samples reconstruct the same cited-observation structure as production. Exact original model prompts are in the request audit, not inferred from a later updated source packet.

JuniorWriter receives active common/form instructions and current source context. JKSimmons receives exact candidate instructions/context/drafts, preceding assessments and the versioned cognitive policy. StoryTechMan job packets include that policy and its role instructs it to read current handoff/design documentation. These are future-job delivery guarantees, not claims that persistent chats were proactively notified or have acknowledged a release.

Shared/form revisions, owner edits and activation pointers persist separately. Category studies test two distinct contexts with fresh drafts, then fresh-entry validation; the real Codex JKSimmons reviews through the configured bridge. Context/technical/permission issues stop the writing loop and enter scoped owner-approved investigation/repair/release. Activation requires owner action. Environment fingerprints include cognition modules so an old study cannot resume across a changed design. No language-model training or automatic policy promotion occurs.

The writer is configured Luna/medium with a 4,000 total response-token allowance; runtime configuration is authoritative. One ordinary entry attempt has no automatic critique/variant loop. Missing credentials/budget, failures and stale retained prose are explicit; paid output/usage is audited even if validation rejects publication. Workshop category studies have their separately authorized multi-draft limits. Cosmetic agent banter is not evidence of model reasoning or progress.

## 10. Other campaign narratives and interface

Gang baselines read only explicit Sheet GANG BACKSTORY, never GANG NOTES/tactics or a Google Doc story. A present empty section clears it; an omitted section retains or recovers the last Sheet-authored copy. Missing baselines are not automatically generated. Archive displays The Prospect and The Deep Answers as source-bounded collapsible stories. Formatting changes presentation only; the full export and personnel canon remain intact.

Gang/place event streams, histories, battle/downtime/relationship reports retain separate source evidence and generated provenance. Battle reports use current recorded scenario/parties/result/territory and safe explicitly labelled associations, never inventing named mechanics or attendance. Recurring gang-pair chronicles are not individual social bonds. Authored notes remain attributed sources.

The Chronicle timeline reads MUNDA activity/battles/sessions independently, joins sessions by exact battle ID, groups bounded Battle/Downtime activity and supports filters, zoom, clustering and Ctrl-drag. Complete session unions determine engagement duration. Dates/durations are display/history data, not cognitive decay. Detailed archive events are not yet automatically converted into all fighter observations; pre-baseline experience coverage is incomplete and this clock cannot reconstruct missing facts.

Navigation: Chronicle, Gangs, Fighters, Places, Battles, Archive, Writer Workshop, System. Dossiers separate authored/generated narrative from mechanical evidence. Imperial dates are display projections; source timestamps remain in data. Search/filtering and retrieval explanations remain available. Shared-passphrase auth protects campaign/Workshop APIs; mutations require same-origin JSON and writer-pipeline gates. Separate viewer/editor accounts are not implemented.

## 11. White-paper alignment and implementation limits

North star: Park et al., [Generative Agents](../../generative-agents.pdf), §4.1–4.3, PDF pp.8–11. Persistent sourced experience, weighted retrieval and cited reflections are implemented. Event-distance recency and no fixed expiry are owner-approved adaptations. The paper uses last-access time, model-rated importance, embedding similarity, recursive insights and stored hierarchical action plans; NCCE uses causal event positions, rule salience/topic relevance and batch reflections. Autonomous daily planning/dialogue, semantic retrieval, recursive/cross-batch reflection and emergent individualized social simulation are not implemented. Literary planning must not be presented as those features.

The clock measures available supported experiences, not an exhaustive record of all campaign history. Unknown timing/attendance remains unknown. Current guideline activation changes future calls, not old prose or model weights. No claims of literary quality follow from mocked transport tests. API schema/version, enabled writing and live deployment are verified separately in release records.

## 12. Verification contract

Every approved numerical rule has executable coverage: `test_fighter_event_clock.py` covers 10-step half-life, idle-time invariance, fighter scope, duplicates, corrections, distinct same-import changes, derived-entry exclusion and formation anchors. `test_fighter_mind.py` covers independent prose, ready-only display, persistence/reuse, resolution, no calendar expiry, stable biographies and production/Workshop reflection context. Existing writer/planner/optimizer/bridge/auth/UI suites cover budgets, source integrity, owner gates and rendering. Disposable authenticated HTTP checks exercise the actual app with read-only live Sheet input and no paid writer work.

Hosted verification and commits are in CHANGELOG.md and HANDOFF_STATUS.md. This design describes source behavior; a release is called live only after Render and workload verification. Future changes must update this document and the executable contract, not merely add an amendment over a contradictory old rule.
