# NCCE 0.28.3 — current technical design

## 0.28.3 — Visible territory local names

The Local designation line is a distinct 18px uppercase Courier heading, with
stronger contrast and spacing. Classification remains small machine-print
metadata. Capitalization is display-only; source text and writing requests do
not change. This applies to both imported Markdown and retained report blocks.

## 0.28.2 — Corrected territory metadata and notice removal

Imported Markdown metadata recognizes plain labels, `**Label:** value` and
`**Label**: value`. Territory designation/classification paragraphs are handled
in both authored-record and legacy record-body wrappers and receive the same
section-label class as machine-print headings. Obsolete writer notices are
removed from all territory record layers, including Data & sources, rather
than moved there. Underlying audit/status/prose/source data is retained.

## 0.28.1 — Territory report presentation

Historical 0.28.1 behavior (notice routing superseded by 0.28.2):
Territory Description opens directly on its report, without the generic
"What this place is" introduction. Technical writing notices from territory
report panels are collected under Data & sources. Designation/classification
metadata uses the same small Courier print scale, colour and letter spacing as
the paper's section labels. This applies to imported Markdown field rows and
matching metadata paragraphs in retained structured documents. Source wording,
stored prose, request seals, writing jobs, timeline and campaign data are not
changed. Other entity record layouts retain their existing notices.

## 0.28.0 — Confirmed territory transformations

Implemented 5 November 2026. Source-cited, owner-confirmed history supplements
preserve the former Gambling Den identity of Ethernetans' additional Settlement.
One undated conversion enters the ledger, place stream and gang timeline, with
confirmation time distinguished from occurrence time. It cannot be assigned to
a battle/downtime window. A holding-specific origin exception supplies the
writer with its former identity and conversion. Slag Eaters' second Settlement
is bridged to its documented capture from Kly, not fabricated as a conversion.
Starting Settlements remain distinct. The owner-paused origin request can get
one audited same-ID brief amendment without losing a draft or resetting its
claim. No source/roster edits, model calls, schema or fighter cognitive changes.
Exact implemented rules and limitations: [Territory history](TERRITORY_HISTORY.md).

## 0.27.1 — Explicit operator queue report

Implemented 5 November 2026, 09:31 CET / 08:31 UTC. Queue status is an operator
dashboard, not a writer input. After reconciling deliveries, holds, deferrals and
exports, the relay lists only actual PENDING rows with no saved text as available
work. The separate backlog table exposes every one of the 16 prose forms, its
stage, form ID, authored count, accepted count, remaining derived slots and
blocked subset. Gang origins and post-battle addenda are explicitly authored-only.
Deferred battle reports remain DRAFT in the ledger, preserving IDs and history.
The writer reads Queue and matching Context; it does not choose waterfall phases
or treat backlog counts as jobs. Priority rules, schema 18, five-job buffer and
three-entry work-chat run limit are unchanged. See WRITING_WATERFALL.md for the
counter definitions and the separation between report and scheduler.

## 0.27.0 — Dependency waterfall and one-time legacy replacement

Implemented 5 November 2026, schema 18. All unapproved generated prose and placeholders are eligible for one replacement, including old ready drafts. Authored sources and imported writing-chat outputs stay protected. The queue now follows baselines → chronological events → cited reflections → current thoughts → histories/downtime/relationships → regional chronicle, with explicit causal prerequisites and accepted-fiction Context blocks. See [Writing waterfall](WRITING_WATERFALL.md) for the exact policy, source fingerprints, claim/defer protocol and limitations.

Legacy projections are saved before their ready labels become stale. The five-entry buffer remains; unclaimed jobs can be deferred as DRAFT with their original IDs/packets preserved, while WRITING/READY/partial output remains protected. The Google relay reports claims and writes Queue status phase counts. Compilation times and storage-version changes do not manufacture new writing needs; a full-cycle regression proves no rewriting after refresh. Core campaign data, authored lore, timeline and fighter event-clock mechanics are unchanged. No model/API generation is restored. Deployment/actual queue verification follows.


**First unattended external delivery verified — 5 November 2026, 02:13 CET / 01:13 UTC:** writer completed request 1b450960-7035-4478-8dc9-9317c371b989 (battle_report, existing battle 14, Smash & Grab — Wastes), marked READY at 01:07:22.233 UTC. The 01:07:12 timer had already finished, so the next real time-driven syncNCCE run at 01:12:12 imported it automatically; execution completed in 7.733 seconds. Server commit time 2026-11-05T01:12:14.210791+00:00; Sheet row 11 is IMPORTED with receipt exchange:1b450960-7035-4478-8dc9-9317c371b989:46e8c7860ce980d3. Compared all 771 Markdown characters, note and writer timestamp against the frozen pre-import readback: unchanged. Receipt independently recomputed from the canonical delivery payload matches exactly. Text SHA-256: 1434e5835b438a8b7358a2a21a6d3d645ffc9e7bb7f1c4c84cd42eb0dd6daa81. The outbox refilled with request 1a2a8197-9302-493c-9259-2be522e85b32 (Asset Seizure — Drinking Hole), keeping the five-request cap. Real returned Markdown passes existing safe renderer heading/bold/paragraph checks. No rewrite, new model call or direct source edit by Codex. Hosted signed-in visual/API inspection was not completed: this IAB session is signed out; automatic approval review rejected privileged Render shell access, and no bypass was attempted. Verification uses the committed server-derived receipt, exact Sheet readbacks and actual successful unattended execution, not a claim of a signed-in UI view. Next: owner can inspect Battles → Smash & Grab — Wastes and ask the existing work writing chat to create one supported hourly task (max three PENDING entries/run). That separate writing schedule remains unverified/uncreated here.


**Google relay connected — 5 November 2026, 02:04 CET / 01:04 UTC:** owner reports saving the same private key in Google Script properties and Render. Render deploy dep-dblt9i6417fc73bg7f20 is live on source 240672d0683b6c64eb39b8837efb66010f5a46fc. Keys were not read. Google authorization completed; onOpen and then the verified installNCCERelay selection completed. Installer ran 02:02:21–02:02:42 CET. Actual private-Sheet export succeeded: five PENDING battle_report requests at Queue rows 7–11, each with all three supplied Context blocks. Mara remains IMPORTED with its original receipt/time. Trigger UI shows exactly one syncNCCE time-based trigger; edit view confirms every five minutes, then cancelled without changes. Timer installed; first unattended run not yet observed. This demonstrates live key compatibility, Google Sheets service/API access, native table/context export and trigger installation. No paid writing, generated output, authoritative source edit or source-data mutation. Next: existing work writing chat processes ONE pending entry, sets READY last; verify the real relay delivery/receipt/site rendering, then confirm a supported hourly schedule in that separate chat. Do not mark the writing chat scheduled or a new delivery tested yet.


## 0.26.0 — Private external writing automation

Implemented 5 November 2026; schema 17. The server adapter and Google relay code are implemented and locally tested. Google Script installation/authorization, relay key configuration, a real private-Sheet round trip and the separate work-chat schedule are NOT activated by a code deployment. See WRITING_AUTOMATION_SETUP.md for installation and the exact work-chat message.

`exchange_automation.py` discovers existing unwritten or earlier-draft slots, seals a UUID request to its logical target, evidence, source chronology and identity context, and stores the complete original projection and frozen packet. At most five PENDING packets exist. One canonical request is kept per event/baseline slot; rolling gang/place/region/relationship/downtime histories may get another request only for a changed source seal. Ready prose and authored material are excluded; gang origins remain authored-only and post-battle addenda currently have authored source dossiers only. The 14 supported generated forms use four existing target stores: story_artifacts, story_memories, fighter_thoughts and narrative_entries. No new fictitious event slots are invented.

The private Google Apps Script polls at five-minute intervals using a dedicated bearer token (NCCE_EXCHANGE_TOKEN, minimum 32 characters) held in Render environment and Script properties. Without it the relay routes fail closed. POST /api/writing-exchange/relay/poll exports packets and guidance; /deliver accepts READY text by existing request ID/revision, not caller-supplied routing. Standard app login alone does not authorize these routes. Payloads are bounded to 100,000 bytes and text to 30,000 characters. The authenticated read-only exchange endpoint exposes status/receipts and last relay contact. Retired Workshop/provider/reviewer/RAG routes remain 410.

The relay writes complete Context blocks before publishing PENDING, grows native tables, preserves source-directory footers and the accepted Mara pilot, writes literal text (no formula interpretation), and never resets WRITING/READY/HOLD or replaces existing output. Interrupted publication of its own DRAFT can be completed. Work-chat instructions claim one row, create one entry, read it back, set READY last and process at most three entries per run. READY explicitly authorizes exact-text import as inference/connective fiction; it does not promote the text to player-authored canon. Full identity/embodiment/faction guidance is included alongside the cognitive writing skill.

Import validates the current exact slot/source seal, refuses authored or already-completed targets, keeps conflicting/stale-source deliveries on HOLD, and retains all submissions with deterministic hashes and receipts. A successful transaction changes derived prose/status and the story revision used by frontend refresh only. It does not alter fighters, factual events, snapshots, memory dates, salience, causes, lifecycles or event-clock positions. Original prose/projection is retained in the request audit. A single verified pre-automation SQLite backup is reused rather than making a full database backup per entry. Source-unchanged accepted wording is reapplied after startup/sync projection rebuild. Full Markdown remains in the audit and uses the existing safe record renderer; source/evidence/provenance remain outside the literary body.

Receipt loss resends the saved output and reuses its committed receipt, with no new generation. Source changes before delivery hold the request; the relay propagates HOLD without deleting a draft. DB failure returns no success; the saved Sheet draft remains available for retry. There is no autonomous literary reviewer, API model, quality veto, regeneration loop or paid provider transport. Authored battle reports/biographies and source documents remain authoritative.

The clock/cognition algorithms are unchanged: fighter-relevant event distance, ten-event half-life, no wall-clock decay or fixed expiry. Imported prose does not advance that clock. The work-account ordinary chat must separately demonstrate supported scheduled-tool access; NCCE/Apps Script cannot directly wake a Project chat.

Historical implementation notes below describe their respective releases; the 0.26.0 section above supersedes earlier statements that general transport is unimplemented.


**Implementation:** 0.25.0. **SQLite schema:** 16. This is the current specification, not a list of desired future features. Historical behavior is in Git and CHANGELOG.md. Hosted source/version and verification are recorded in the changelog; an implementation entry is not proof of live deployment.

## Accepted external prose import (0.25.0)

The owner accepted Mara's READY exchange entry as written and authorized import/deployment. `writing_exchange.py` imports reviewed delivery bundles from data/writing-exchange/accepted after startup regeneration and after successful live Sheet sync. This bounded adapter supports existing inferred fighter observation memories only. It does not poll Google Sheets, trigger the work chat, call a model, publish other categories or reopen removed writing controls.

Each bundle retains the frozen request/context, SHA-256 source revision, exact Markdown, owner acceptance and an explicit binding to the existing cognitive event/memory key. Validation checks the exact archive UUID, fighter/gang UUIDs, description/time, subject mapping, supplied authored Sheet context, ledger event/type/payload/subject, and one active inferred observation with the expected evidence. Existing authored biographies are untouched, including a preserved canonical biography when the supplied Sheet context is stored separately. Missing, ambiguous, changed, authored or conflicting targets are held; no second experience is created. The pilot explicitly maps activity b7ddeca9-8326-47e6-8df6-6963d35fda35 to memory key 38fba6a8283370d510ec4c0649dd1513, verified in the persistent local history.

Schema 16 adds external_prose_deliveries: full packet/binding/raw-text retention, imported/held disposition, reason, target IDs, import time and stable receipt. Unique constraints permit one imported delivery per request and target memory slot. Identical re-import returns the original receipt; conflicting drafts remain retained as held. Under the Store lock, a verified consistent backup precedes the first import and the active-version switch/new memory/audit are one transaction. Failed writes roll back the active-version change before retaining the held delivery. Import rejects an already-open caller transaction.

Only the target's earlier prose version is deactivated; it remains in history. The new version uses the exact accepted text, ready status and existing safe renderer. Import does not change fighter/biography data, snapshots, factual events, original memory date/basis, importance, causal IDs, Mind rows or fighter-clock positions. The archive timestamp remains in the sealed packet rather than replacing the original first-observation date. Regeneration reuses imported text by fighter/logical-memory key through _retained_writer_content, without provider work or a new clock step.

GET /api/writing-exchange is authenticated and read-only, exposing receipt/target/disposition metadata. No HTTP import endpoint is added. Compact server logs support deployment verification. The coordinator may mark the exchange row IMPORTED only after verifying the committed hosted receipt; READY alone is not publication. Automatic Sheet export/polling/acknowledgement, other 15 forms and work-chat triggering remain unimplemented.

Validation: six new importer checks, all 16 Python scripts and seven JS suites pass. A disposable copy of actual persistent campaign history imports exactly one existing Mara injury observation and survives forced regeneration with exact text, unchanged authored biography and unchanged event clock. Authenticated HTTP/live-Sheet smoke checks cover version/schema and protected receipt access. Hosted verification is recorded separately after deployment.

Hosted verification on 5 November 2026, 00:55 CET confirms 0.25.0/schema-upgrade backup and the pilot import/reuse receipt in actual service logs. Public health and protected audit access were checked. The exchange row is now IMPORTED with exact hosted receipt/time and unchanged accepted body. Signed-in hosted visual verification was blocked by Chrome automation failure; local renderer regressions and production import logs are the evidence available. Detailed source/deploy/receipt IDs are in CHANGELOG.md.

The separate [native exchange Sheet](https://docs.google.com/spreadsheets/d/1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas/edit) has Queue, Context, Forms, Guide, Writer instructions and Writer skill. Its 20 preallocated request IDs are work identities, not fighters or a call allowance. The work chat's access was confirmed by the owner, and Mara's returned entry was accepted. [Writing exchange](WRITING_EXCHANGE.md) describes the transport, source packet and recovery contract. The remaining live automation is not implemented.

The owner approved fighter-relevant logical time, a half-life of **10 relevant events**, **one step per distinct meaningful change**, and **no fixed expiry**. Calendar-based cognitive decay in 0.16.0 is superseded. The detailed specification, worked examples, paper comparison and executable verification map are in [Fighter event clock](FIGHTER_EVENT_CLOCK.md).

The portable [Writer skill](../skills/ncce-campaign-writing/SKILL.md) describes all 16 prose forms and the implemented cognitive rules. It delegates state/selection to NCCE and preserves the existing chat's literary style; adding the briefing does not restart work or generate prose. Detailed identity/embodiment/faction guidance remains in WRITER_IDENTITY_TAGS.md; the portable skill currently summarizes it rather than including that full document.

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
| `llm_writer.py` | Passive compatibility adapter for stored prose/rich text. No transport, cache replay, RAG, enabled provider or generation. |
| `writing_retirement.py` | Verified one-time backup, queue cancellation, disabled category policies, private retired-state filtering and durable retirement audit. |
| `writer_contract.py` | Preserved historical formatting/form reference, not an executing writer. |
| `territory_reference.py` | Preserved verified Dominion type reference data. No retrieval or literary planning worker. |
| `world_streams.py` | Source-linked gang/place event accounts and separately marked connective fiction. |
| `authored_archive.py` | Read-only source-bounded The Prospect and The Deep Answers excerpts. |
| `seed.py`, `narrative.py` | Initial compatibility seed and legacy templates. Legacy moodlets are not current Mind. |
| `server.py`, `access.py` | HTTP API, same-origin/auth gates, retired-route tombstones, startup/manual/scheduled read-only sync. |
| `web/app.js`, `web/writing.js`, `web/archivum.js` | Dossiers, evidence, timeline, date layers and archival navigation. |

## 3. Runtime and persistence

Startup opens or seeds the workspace DB, verifies a consistent backup before any schema upgrade, and applies migrations through schema 15. Before derived-state preparation, retirement creates a consistent integrity-checked backup beside the configured DB, cancels unfinished legacy writing/review/study jobs and disables category policies in one transaction. A durable marker makes this step idempotent. No prose/source rows are deleted. If backup verification fails, startup fails before retirement changes are committed. Startup, scheduled (normally 15-minute) and manual refreshes then use the same read-only Sheet pipeline. The scheduling interval does not advance cognition.

Snapshots retain original input. Events retain stable identity, subjects, source/occurrence/observation dates and correction links. Missing fighters stay in historical storage; disappearance is not death. Current projections update mechanics and authored inputs. Regeneration is fingerprinted/idempotent; an unchanged import does not create observations or event-steps. Code/context changes may version derived records, but rewriting prose adds no steps.

`story_memories` stores active and superseded observations/reflections with causes and citations. `story_artifacts` stores generated documents. `fighter_thoughts` stores separate current prose, source memory/factual causes, inspectable generation context, writer status and lifecycle. Old `expires_at` values are compatibility data only and are ignored/cleared on refresh. Historical `fighter_events`, `memories`, `moodlets` remain; API `legacy_moodlets` labels the seeded rows, while `moodlets` aliases the current `mind` list.

All prose generation is disabled in code, regardless of old environment variables. Missing prose has status `paused`; factual observations and current-thought candidates still form from meaningful events. Existing prose and authored content are retained; accepted memory content/rich text/status and document provenance remain available. Historical request, draft and review tables remain inert for offline audit. The app exposes no writer inspection, mutation or spending controls.

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

## 9. Writing system removed

The owner retired Writer Workshop, Writing context/RAG, JKSimmons, StoryTechMan, native authorship, comparison/optimization and category production/population. Their source modules, browser bundles, helper scripts, local launchers and dedicated skill are removed. No reviewer or technical worker is dispatched. No provider request can be made by the compatibility adapter; neither a stored key nor `NCCE_AUTO_WRITE_ENABLED` can restore it.

Legacy `/api/workshop`, `/api/reviewer-bridge`, `/api/native-author`, `/api/writer-runs`, `/api/writer-diagnostic`, `/api/territory-writer-runs` and fighter `write-check` operations return **410 Gone**, including requests bearing an old token. Old Workshop/context browser bookmarks fall back to Chronicle. Prior private state is excluded from dashboard responses. Auth/session and read-only Sheet sync remain.

Retirement audit revision 2 cancels only queued/running/claimed/started/in-progress table jobs. Ready/imported/succeeded historical rows remain intact. If revision 1 already ran, revision 2 verifies its same-directory backup and restores only terminal audit status/error preimages bearing the exact retirement cancellation reason; it never requeues work or modifies prose. This repair is idempotent and records its count in the durable retirement marker.

No replacement writer is implemented. Preserved reference/guardrail documents and historical audit tables are data, not an active RAG pipeline. Historical specifications are labelled retired. No API secret is transmitted or used; this code change does not revoke keys in the provider's account.

## 10. Other campaign narratives and interface

Gang baselines read only explicit Sheet GANG BACKSTORY, never GANG NOTES/tactics or a Google Doc story. A present empty section clears it; an omitted section retains or recovers the last Sheet-authored copy. Missing baselines are not automatically generated. Archive displays The Prospect and The Deep Answers as source-bounded collapsible stories. Formatting changes presentation only; the full export and personnel canon remain intact.

Gang/place event streams, histories, battle/downtime/relationship reports retain separate source evidence and generated provenance. Battle reports use current recorded scenario/parties/result/territory and safe explicitly labelled associations, never inventing named mechanics or attendance. Recurring gang-pair chronicles are not individual social bonds. Authored notes remain attributed sources.

The Chronicle timeline reads MUNDA activity/battles/sessions independently, joins sessions by exact battle ID, groups bounded Battle/Downtime activity and supports filters, zoom, clustering and Ctrl-drag. Complete session unions determine engagement duration. Dates/durations are display/history data, not cognitive decay. Detailed archive events are not yet automatically converted into all fighter observations; pre-baseline experience coverage is incomplete and this clock cannot reconstruct missing facts.

Navigation: Chronicle, Gangs, Fighters, Places, Battles, Archive, System. Dossiers separate authored/generated narrative from mechanical evidence. Imperial dates are display projections; source timestamps remain in data. Search/filtering and retrieval explanations remain available. Shared-passphrase auth protects campaign APIs; identity corrections retain their same-origin check. Separate viewer/editor accounts are not implemented.

## 11. White-paper alignment and implementation limits

North star: Park et al., [Generative Agents](../../generative-agents.pdf), §4.1–4.3, PDF pp.8–11. Persistent sourced experience, weighted retrieval and cited reflections are implemented. Event-distance recency and no fixed expiry are owner-approved adaptations. The paper uses last-access time, model-rated importance, embedding similarity, recursive insights and stored hierarchical action plans; NCCE uses causal event positions, rule salience/topic relevance and batch reflections. Autonomous daily planning/dialogue, semantic retrieval, recursive/cross-batch reflection and emergent individualized social simulation are not implemented. Literary planning must not be presented as those features.

The clock measures available supported experiences, not an exhaustive record of all campaign history. Unknown timing/attendance remains unknown. Current guideline activation changes future calls, not old prose or model weights. No claims of literary quality follow from mocked transport tests. API schema/version, enabled writing and live deployment are verified separately in release records.

## 12. Verification contract

Every approved numerical rule has executable coverage: `test_fighter_event_clock.py` covers 10-step half-life, idle-time invariance, fighter scope, duplicates, corrections, distinct same-import changes, derived-entry exclusion and formation anchors. `test_fighter_mind.py` covers independent prose, ready-only display, persistence/reuse, resolution, no calendar expiry, stable biographies. Retirement tests cover queue cancellation, verified backup, idempotence, no provider transport, retained prose and dead legacy endpoints. Core/auth/UI suites cover source integrity and rendering. Disposable authenticated HTTP checks exercise the actual app with read-only live Sheet input and no paid writer work.

Hosted verification and commits are in CHANGELOG.md and HANDOFF_STATUS.md. This design describes source behavior; a release is called live only after Render and workload verification. Future changes must update this document and the executable contract, not merely add an amendment over a contradictory old rule.

## Frontend presentation — 3 November 2026

The archival sidebar, index/preview navigation, document/source layers, neutral
stamps and responsive behaviour are
specified in [Archival frontend](FRONTEND_ARCHIVUM.md). This is presentation only:
the event engine, authority hierarchy and protected timeline implementation are
unchanged. The linked document lists exact ownership boundaries and verification.

### Entity section navigation — revision of 3 November 2026

The earlier single-document entity preview is superseded by dedicated baseline,
Timeline and related-record sections. Fighters additionally separate Memory from
Mind. See [Record navigation](RECORD_NAVIGATION.md) for the implemented section
map, data boundaries, chronology, refresh/keyboard behaviour and verification.


## System: prose categories and coverage — 4 November 2026

`prose_progress.py` computes a read-only inventory, served by authenticated `GET /api/prose-progress` only when System is opened. It never reads Workshop trials, reserves work, changes data or invokes a writer. System groups the 15 retained prose categories by Fighters, Gangs, Places, Campaign and Relationships. Archive is a separate two-story collection.

Each row has two native accessible progress bars: **Completed** counts non-empty authored content or published `ready` prose; **Written** also counts published `stale` earlier drafts. Breakdown shows authored, ready, earlier drafts and unwritten. This measures stored coverage/status, not literary quality or word count. Empty text, header-only documents, paused/error placeholders and unpublished audit drafts do not count as written. Zero slots display 0 / 0 and “No entries yet,” never 100%.

Denominators: one biography per fighter in a currently active gang (including remembered/unlisted fighters), one gang backstory/history/current downtime account per active gang, one origin/history per active place, one report per active battle, and one campaign-wide regional chronicle when the campaign exists. Memory/reflection totals use current active logical memory keys; thought totals use active thought rows. Event/scenes totals use existing active logical narrative entry keys, and relationship histories use active artifacts for pairs of current gangs. No future event/scene quotas are invented; open-ended rows say “Existing entries only.” Latest active versions count once. Gang backstories follow the actual UI authority rule: explicit Sheet backstory first, otherwise an existing published native origin; legacy seeded/generated gang baseline text is excluded. Fighter authored backstories supersede generated biography documents.

The endpoint and UI are reporting only. All 0.23.0 retirement restrictions remain in force. No schema changes, new writing controls, timeline changes or provider calls are introduced. Tests: `test_prose_progress.py`, `test_prose_progress_ui.cjs`, existing authenticated HTTP and core regression scripts.


## Authored battle reports — 4 November 2026

`authored_battles.py` treats non-empty current `Battles · Notes` text as the player-authored primary battle account. `story_engine.document_for` resolves that current source before any generated artifact, so APIs and pages do not wait for a new writing pass or derived-state rebuild. Regeneration preserves its `player_authored` class, ready status and verbatim `authored_text`/body; `_artifact` no longer overwrites supplied authored provenance with inference. The same precedence drives System coverage, including authored reports even when the previous generated artifact is empty/paused. No model is used.

A source edit is reflected immediately. Explicitly clearing a report suppresses its old authored projection; regeneration does not retain it as if it were a generated current draft. Historical artifact versions remain available in the database. This changes only the derived narrative projection, never source Notes, battle results or the mechanical event ledger. Mechanical evidence is separately labelled `mechanical_fact`, not reclassified by the authored narrative's authority.

Battle pages render the primary account once, labelled Player-authored, instead of nesting it as supplementary notes under an empty Generated inference heading. The shared source-preserving authored renderer presents protocol headers, section labels, existing metadata, paragraphs, redactions, termination lines and repeated uppercase speaker labels as distinct semantic elements. Empty source turns remain empty; no missing replies, extra metadata or prose are invented. Paper styling uses dark text on a light background; the old dark source-note panel is removed from the authored battle path. Source wording and authored timestamps are not rewritten.

Live-source verification found five non-empty authored battle Notes fields across 26 current battles (Sheet rows 7, 8, 13, 18, 27), including the Joint Precinct Incident Review shown by the owner. A disposable read-only-source sync verifies all five exact source texts and five authored coverage credits. Other retained generated reports still count separately according to their stored status. Tests cover source precedence, exact text, persistence, API/count parity, edits/clearing, version retention, formatting structure, empty turns, escaping and paper-theme contrast.


## C-NINE battle dossiers, post-battle category and fighter timeline — 4 November 2026

`campaign_authored.py` reads the reviewed `data/imports/c-nine-engagement-dossiers.json` import of the current public Google Doc. It contains only five source-bounded engagement reports and their Post-Engagement Records, not personnel dossiers or Archive stories. Each exact excerpt has a verified SHA-256, source URL, export hash, capture time, engagement heading and source line. Runtime lookup requires the exact battle source key plus scenario, attacker, defender and territory guards; it never guesses based on a repeated territory name or the Doc's reused reference numbers. Startup registers the canon source. This is deterministic authored-content display, not a RAG/writer pipeline. The reviewed snapshot is versioned; subsequent Google Doc edits require a new reviewed import, while Sheet sync remains automatic.

Five mappings: 1.1 Toll Crossing, 2.1 Mine Workings, 2.2 Promethium Cache, 3.1 Old Ruins, 3.2 Sludge Sea. Source Notes remain primary. Missing reports backfill from the Doc as `canon_authored`; existing Notes are preserved, with a separately attributed additional Doc account. Mechanical results, dates and roster state are not amended to agree with prose. With the inspected live Sheet, coverage is seven authored reports among 26 battles (five Notes plus two Doc backfills); other existing generated reports on the persistent service remain separately counted.

Every battle record now has Battle report, Post-battle addenda and Data & sources tabs. The addenda tab carries the exact Post-Engagement Record and its attachments, formatted by the source-preserving authored renderer. There are five imported packets, with attachment counts 2, 3, 4, 4 and 2. The source's dossier 3.2 declares three attachments but only includes two numbered attachments; this discrepancy is preserved, not repaired by invention. No post-battle records are fabricated for other battles. The category `post_battle_addendum` raises the System prose inventory to **16** categories. Its denominator is one dossier slot per active battle, not one slot per attachment: currently five authored packets / 26 battles. Archive remains a separate collection.

`fighter_timeline.py` adds existing mechanical fighter-ledger changes to the same normalized timeline input as the raw C-NINE gang archive. It reads event subjects, resolves an unambiguous fighter within its own gang, excludes superseded facts, and emits stable event/subject identities once despite duplicate subject roles. It does not create archive records, source facts, memories, cognitive ticks or inferred prose. All gangs' already tracked fighter changes are eligible. Individual and gang history APIs share this combined timeline; fighter views suppress a duplicate tracked-ledger section when the same source event is already represented.

Known `occurred_at` is used where available. Otherwise the dot is placed at `observed_at` with an explicit first-observed/actual-time-unknown label and the original source-event/snapshot pointers. A snapshot observation cannot support inferred battle attendance. Period grouping uses these displayed record times and each gang's own battle windows; recording-time grouping does not establish that the underlying event happened in battle. Zoom, clustering, lane colours, drag and engagement-duration calculations retain their existing behavior. This does not recover unexported Munda Manager historical logs: the raw archive still supplies only the C-NINE gang log, and non-C-NINE history is limited to facts NCCE actually tracked. Uniquely unresolved identities are not attached to a guessed fighter.

Tests: `test_campaign_authored.py`, `test_battle_addenda_ui.cjs`, `test_fighter_timeline.py`, existing source-authority/cognition/history/UI suites and authenticated HTTP/live-Sheet smoke. No model calls or source edits.
