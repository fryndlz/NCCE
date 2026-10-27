# NCCE 0.12.3 — current technical design

**Source release:** 0.12.3, Sheet-authored gang baselines and separate authored story archive. **Schema:** 12.

[Timeline 0.12.2](TIMELINE_0_12_2.md) adds two-axis Ctrl-drag with stable pointer capture, filtered engagement counts/time on gang lanes, linked participants, separated mission identity, Cycle-first metadata, neutral real-world timing and the independent hosted duration audit. Recorded campaign windows and existing writer policies remain unchanged.

[Timeline 0.12.1](TIMELINE_0_12_1.md) specifies zoom, screen-distance clustering, gang colours, separate bar/marker rows, strict activity intervals, nested collapsible groups, source/Imperial date layers and merged-session playtime. This supersedes the older timeline presentation description below; source provenance and participation inference rules remain unchanged.
**Checkpoint:** 2026-10-27 20:40 CET. Hosted deployment evidence is recorded in CHANGELOG.md and HANDOFF_STATUS.md.

[Writer creative planning](WRITER_CREATIVE_PLANNING.md) specifies the new shared modules and exact rules: 26 verified 2023 Core Rulebook territory cards, least-used compatible focus selection for baselines/ambient writing, event/sequence anchoring for other forms, frozen inspectable plans and compact heuristic recent-pattern memory. Plans/footprints are private derived data; they cannot establish facts or replace same-subject continuity. Workshop focus selection is free and pinnable. Saved instructions/edits remain intact; one provider call per draft, no automatic regeneration. Luna/medium and a 4,000-token total response allowance remain configured.

## Gang baselines and authored Archive — 0.12.3

`GANG BACKSTORY` in each gang tab is the sole gang baseline source. `GANG NOTES` remains bookkeeping/context and is never substituted. `snapshot.parse_gang_tab` preserves the authored text; `Store.project_snapshot` refreshes the derived gang backstory and marks it player-authored. An explicitly present empty section clears that projection. If the entire section is omitted by a rebuilt export, retain the last observed Sheet-authored text; recover it from immutable snapshots after a lost projection/restart. Never recover generated or Google Doc baseline text. Gang reads hide legacy seeded/generated baselines even before refresh. Seed and story regeneration do not generate missing gang origins. Existing generated event/history accounts remain a separate layer; historical artifacts and full authored source documents are retained.

`authored_archive.stories` exposes two read-only, source-located excerpts through authenticated `/api/archive`: The Prospect (up to Cycle 1) and The Deep Answers (up to the following Downtime). No source document is rewritten. Archive shows each as a closed-by-default native disclosure. The authored renderer maps paragraphs, administrative headings/fields, scene separators and termination syntax to existing semantic styles; escapes HTML and preserves original wording, language, redactions and authored dates. No LLM rephrasing, invented metadata, translation or provider calls are involved. The full combined document remains accessible through the existing lore API; personnel dossiers remain in fighter records. Schema remains 12.

## 0. Current writing implementation

[Writer Workshop](WRITER_WORKSHOP.md) exposes shared/form instructions, style examples, exact request inspection, a one-call source-backed trial, rendered prose editing, immutable edit/revision history and explicit activation/rollback for future writing. All workshop endpoints require configured passphrase authentication; mutation also requires same-origin JSON. Samples and edits are private derived artifacts, never campaign source/canon. The existing shared app passphrase is also the workshop permission boundary; separate owner/viewer roles are not implemented. No new model requests are made by opening, saving, inspecting, importing or editing. Automatic writing remains disabled.

Schema 11 adds `workshop_revisions`, `workshop_active`, `workshop_trials` and `workshop_edits`. Active instructions are resolved by the production writer and participate in the exact-contract cache hash. Saved drafts do not affect production until explicitly activated. Request keys prevent duplicate paid work; provider calls share the existing writer pipeline lock and have a one-call budget. A restart marks unfinished trials interrupted, with no replay. The technical and editorial limits are specified in `WRITER_WORKSHOP.md`.

The [six-call editorial comparison](WRITER_COMPARISON_0_10_1.md) adds a candidate general craft specification alongside the current contract. Three independently shuffled A/B pairs use identical factual/context inputs and fixed model/effort/output settings. The candidate is not active for routine campaign writing. Results are saved separately in System; all prompts/responses and costs remain in the server-side audit. There is no paid comparison HTTP endpoint or automatic replacement of campaign prose.

[Shared narrative pipeline](WRITER_PIPELINE_0_10.md) specifies the current writer for all fourteen forms. It supersedes the historical writer-release discussion later in this document. `writer_contract.py` provides a coherent common policy and form-specific examples; `narrative_context.py` separates authored material, factual events and accepted fictional continuity; `llm_writer.py` drafts semantic prose and document composition in one call; `writer_preview.py` runs bounded editorial tests without publishing to campaign state.

Historical fighter voice context comes from available snapshots. Territory events use historical ownership or explicitly unknown ownership. Old template plots and previous-policy generated prose do not feed new prompts. Composition includes heading, subject, body heading, closing label/text and signoff; reference IDs and Imperial dates remain app-controlled. Real dates and provenance remain outside the fictional document. Authored material is preserved.

Schema 10 adds writer request details retaining exact credential-free prompts, raw responses, parsed drafts, effort and cache/reasoning token counts, including failures. These diagnostics are server-side. All forms default to a 4,000-token response ceiling including reasoning and visible prose; form briefs still control the requested prose length. Default model/effort is gpt-6-luna/medium. There is no best-of-N generation or paid critic. Duplicate failures are suppressed within a run. Routine writing remains disabled and the first four-entry territory preview is separate from campaign history.

The numerical cognition, import, source-authority and timeline rules below remain unchanged. Historical release verification belongs to CHANGELOG.md; source tests are not a claim of literary quality.

## 1. Product and authority

NCCE turns a tabletop campaign into a persistent chronicle of fighters, gangs, places, and their consequences. It reads mechanical records and derives narrative from them. It does not adjudicate Necromunda rules, calculate legal advancement purchases, or change a roster on the source system.

Sources and authority:

| Source | Use and authority |
| --- | --- |
| Krakamunda Google Sheet | Authoritative mechanical state. Read-only XLSX export, on startup, every 15 minutes while the service is running, and on manual refresh. |
| Player-authored Backstory fields in the Sheet | Authored fighter text where supplied. Preserved in place and used as voice context. Fighter Notes remain inspectable source notes. |
| C-NINE Story export | Frozen authored campaign canon used for matched C-NINE biographies and its administrative/industrial voice. Existing C-NINE canon takes priority over a replacement Sheet biography. The current app does not automatically fetch changes to the live Google Doc. |
| Necromunda reference material | Informs which campaign changes are meaningful and their interpretation. The Sheet remains authoritative about what occurred. Current rules authority is NecroRAW; bundled books provide reference context. |
| Generated memories and reports | Derived inference. They retain source pointers and do not become mechanical fact or authored canon. |

The five provenance classes are `mechanical_fact`, `player_authored`, `canon_authored`, `inference`, and `connective_fiction`. They describe authority and origin. They are distinct from the two memory types, `observation` and `reflection`.

Mechanical source: https://docs.google.com/spreadsheets/d/1Ofh1kDys_xp4a-idPc1NA2I1GCqndbVGjxenatezh00/edit
C-NINE authored source: https://docs.google.com/document/d/1vAajSzxjaKXjAQ571gcTeM5ocqSVccUS1pljDR_Ysk4/edit
Rules reference: https://www.necroraw.com.ru/

## 2. Module map

| Module or area | Current responsibility |
| --- | --- |
| `src/access.py` | Shared-passphrase access configuration, signing key derivation, and seven-day signed session tokens. |
| `src/google_sheets.py` | Read-only workbook download; normalizes the current Sheet snapshot and imports the three archive tabs without any Sheet write capability. |
| `src/campaign_history.py` | Typed raw-tab parsing, immutable source normalization, exact battle/session joins, candidate-window classification, participation evidence and timing warnings. |
| `src/snapshot.py` | Standard-library XLSX/XML parsing, normalized gang/fighter/territory/battle records, source-ID joins from the MAIN Data Dump, stable battle keys and duplicate handling. |
| `src/models.py` | Dataclasses documenting the principal snapshot/entity shapes. The running pipeline also uses dictionaries. |
| `src/diff.py` | Pure comparison of normalized snapshots. Produces factual event drafts, subjects, source locators, and before/after payloads. Matches battle identities without treating row insertion as a new history. |
| `src/sync.py` | Source registry, snapshot persistence, seed-to-live bridge, immutable factual event ingestion, current-state projection, then story regeneration. |
| `src/store.py` | SQLite access and migrations; source/entity/event APIs; current-state projection; authored biography preservation; dashboard and detail response assembly. Attaches narrative documents, memory history, selected Mind thoughts, and derived archive timelines. |
| `src/migrations.py` | Schema versions 1–9, legacy provenance backfill, immutable-record protections, current membership flags, versioned story tables, Munda Manager archive imports, and writer request ledger. |
| `src/story_engine.py` | Event classification/importance, memory creation, bounded shared gang events, reflection batches, narrative revisioning, source links, and current Mind retrieval. Owns the numerical rules listed below. |
| `src/story_prose.py` | Identity/fact extraction and compatibility helpers. Its legacy phrase helpers are not presented as finished production prose. |
| `src/llm_writer.py` | Production OpenAI Responses API drafts, structured outputs, provider bounds, status, cache, and per-request usage telemetry. The key remains server-side. |
| `src/writing_director.py`, `src/world_streams.py` | Form-specific writing packets, provenance/format constraints, dates, continuity, and versioned Gang/Place narratives. |
| `src/narrative.py` | Legacy deterministic templates retained for initial seed compatibility. The active v0.6 story layer supersedes the old seeded moodlets and narrative text. |
| `src/seed.py` | Creates a missing database from tracked baseline data and the C-NINE export. Refuses to overwrite an existing database. |
| `src/baseline_data.py`, `data/fighters.json` | Historical seed data. They do not override a subsequent live Sheet read. |
| `data/lore/` | Frozen C-NINE authored source files. |
| `src/server.py` | HTTP/static assets, authenticated JSON API (`/api/history`), startup story generation, serialized background refresh, health/status, and manual refresh. |
| `web/app.js` | Narrative/evidence rendering; Chronicle campaign timeline and battle registry; event/battle detail panels; fighter history/Mind; search/filtering; refresh of the visible view when source/story state changes. |
| `web/index.html`, `web/style.css`, `web/login.html` | App shell, responsive dossier presentation, and passphrase page. |
| Windows launcher and `scripts/` | Existing local startup and initialization entry points. |
| `tests/test_core.py` | Persistence, sessions, parsers, immutable ledger, snapshots, migration, and sync coverage. |
| `tests/test_battle_identity.py` | Stable source/fallback battle identities, row insertion/reordering, corrections, duplicate ambiguity, and raw-dump source-ID joining. |
| `tests/test_campaign_history.py` | Raw-tab parser and provenance, timestamp conversion, exact joins, versioned idempotent imports, conflicts, candidate-window phase classification, overlap/gap ambiguity, XP/ally participation limits. |
| `tests/test_campaign_history_ui.cjs` | Chronicle timeline rendering, battle drilldown, filter controls, session-window caveat, and fighter activity detail. |
| `tests/test_story_engine.py` | Event-to-memory/Mind behavior, first-live bridge, source links, idempotency, regeneration, canon preservation, and corrected/removed battle behavior. |
| `tests/smoke_server.py` | Opt-in authenticated HTTP integration check using a disposable fresh database and a read-only live Sheet refresh. |

The writing integration uses the OpenAI Responses API when the server-side key is configured; the writer and selection rules run on the host. The campaign archive parser and timeline are deterministic and do not invoke the model. There is no continuous off-table life simulation. In 0.9.2, routine refreshes do not make provider calls unless `NCCE_AUTO_WRITE_ENABLED=1`; the dedicated Mara pilot runs only her narrative generation and enforces a single persistent use with a 13-call maximum.

## 3. Runtime sequence

1. Open or seed the existing database and apply migrations through schema 9.
2. Generate any missing or stale derived story revision from the database already available. This allows the app to work before its first live refresh succeeds.
3. Fetch the live workbook and normalize it into a snapshot. Retain the source capture time and deduplicate unchanged content.
4. When a legacy seed snapshot lacks the current snapshot shape, build a one-time comparison bridge from fields the seed really knew. Newly available statistics are treated as baseline values, rather than reported as improvements from missing data.
5. Compare consecutive compatible snapshots and append factual events. Save explicit occurrence dates only when supplied by the source. A capture timestamp describes when NCCE observed the change.
6. Project current gangs, fighters, territories, battles, equipment/stat fields, and authored biography fields into current-state tables. Missing roster entries remain in history with `listed_in_source=0`; absence alone does not mean death or retirement.
7. Regenerate derived story views under the store lock. Mechanical rows, authored lore, immutable snapshots, and factual events remain authoritative. Update narrative projections and retain inactive previous generated versions.
8. The API exposes current narrative documents and history. Mind is selected from those memories using the current request time.

A content fingerprint includes source state, relevant authored biographies, factual event IDs, generation version, and story code. Repeating the same sync/generation with unchanged inputs is idempotent. `force=True` permits deliberate regeneration. A changed semantic memory or artifact input obtains a new ID; previous generated rows remain inactive rather than being silently erased.

## 4. Storage and record lifecycle

The existing current-state tables (`gangs`, `fighters`, `territories`, `battles`, `regions`, and `downtime_reports`) remain projections consumed by the UI. Schema 4 adds full `mechanics_json` and `voice_profile_json` to fighters, and `source_battle_key` to battles.

The factual foundation retains sources, stable entities, immutable snapshots, immutable campaign events, event subjects with roles, and narrative evidence links. Corrections append events and can refer to the event they supersede. They do not edit the prior event.

`story_memories` stores versioned observations/reflections: fighter, stable source key, narrative content, salience, dates, tags, separate mechanical evidence, event IDs, cited memory IDs, source ID, inference confidence, baseline flag, generation version, and active flag. `story_artifacts` stores versioned semantic narrative documents by scope/key, input hash, generated time, and active flag. Legacy `fighter_events`, `memories`, and `moodlets` remain for migration/source audit; the primary v0.6 Memory and Mind views use `story_memories`.

Narrative artifacts have a title and blocks (`heading`, `paragraph`, `quote`, and supported renderer list/record blocks), evidence, provenance, generated/version metadata, and source links. Existing plain-text narrative columns are refreshed as compatibility projections of these documents.

## 5. What creates a memory

An **observation** interprets a specific recorded event or a clearly labeled state known at baseline. It combines a first-person diegetic paragraph with a separate mechanical evidence block. The paragraph is inference; the evidence states what the source recorded. A terminal death entry uses an archival personnel voice and the dead have no current Mind.

A **reflection** synthesizes themes from several cited observations in a batch. It retains those observation IDs and their factual event pointers. The same paragraph cannot be promoted into canon simply because it is a reflection.

Current automatic input coverage includes XP, kills, skills/advancements, Effects and status, weapons/Wargear, characteristics, Class/Type, roster additions/removals, battle results, territory ownership, and shared gang reputation/alignment changes. Mechanical deltas have their own event records even when they do not meet the story layer's salience threshold for reflection.

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

## 6. Shared events and attribution

Current personal events affect their named fighter. A recorded gang battle outcome, territory change, reputation change, or alignment change can create shared context for active, non-retired members. Gangmate death/capture can create shared news for others in the same gang; the prose does not claim a personal relationship or that they witnessed it.

A battle outcome is resolved against the current active battle record and its correction chain. Superseded/removed outcomes are not replayed as current true victory memories. Their generated versions remain available as inactive history. Where a later roll contradicts an earlier captured/dead status, the shared social memory is marked `history_only`, retains the amended evidence, and is excluded from Mind.

The current Sheet battle data plus Munda Manager archive identifies documented campaign battles, participating gangs, and some individual activity. It still does not provide a complete fighter deployment list. A positive XP delta inside a candidate session window may support inferred participation; it does not identify whether XP came from combat, objectives, rallying, assistance, or another rule. XP decreases do not imply participation. Explicit ally markers suppress XP-only participation inference. A named injury does not identify its attacker. These details are not invented as mechanics.

## 7. Fighter voice rules

The voice profile is explainable metadata, not a diagnosis. Authored biography vocabulary takes priority as context. When personal text is absent, faction, role, type, characteristics, and recorded kill history supply the profile; skills/advancement events also have specific phrasing. Generated biographies describe the same evidence and remain inference rather than supplying newly invented canon.

Register selection is C-NINE crew, Van Saar technical, Palanite/Enforcer precinct, Ironhead/Squat charter, Orlock road, or general underhive. Beast/organism types use sensory phrasing. C-NINE retains its administrative/industrial conventions without forcing other gangs into that style.

Authored role hints select workshop/practical, medical/clinical, survey/measured, or attentive/inward vocabulary. The rule uses explicit word matches such as maintenance/repair/workshop, chirurgeon/medicae, survey/prospect/drill, and psyker/listening designations. It does not infer an unwritten historical occupation as fact.

The fighter dossier exposes inferred identity facets with `value`, `source`, and `basis`: recorded class/type, current gang/affiliation, explicit occupation cues from authored backstory, current status/effects, and limited characteristic cues. Player-authored identity overrides remain separately persisted. The original authored backstory remains in its own panel and is never rewritten. The full biography is not sent with each event prompt. Unknown gender/pronouns, lineage, upbringing, relationships, belief and private motive remain unknown unless a source explicitly supplies them. See [Writer identity and perspective rules for Minds and Memory Streams](WRITER_IDENTITY_TAGS.md).

### Stimulus attention weights

The same fighter profile exposes topic attention weights for injury, recovery, growth, advancement, kills, battle, victory, defeat, equipment, weapon, belonging, grief, territory, return and identity. Each begins at `1.00`. Supported voice tendencies add `0.15` to mapped topics; a matching active condition or role adds `0.30`; weights cap at `1.50`. The dossier displays each topic and its basis. The writer receives only the highest up to five topics above baseline. These values guide narrative attention only: they do not alter mechanical state, event importance, reflection thresholds, or Mind selection. A separate formula governs Mind below.

### Event-isolated fighter writing

An observation prompt contains the one event title/evidence, compact identity facets and elevated stimulus weights. It excludes full backstory and prior generated prose, and explicitly prohibits treating them as additional events. The task is one concrete fighter reaction to the recorded change, using relevant identity as a lens. Reflections receive no recycled prose; they receive only cited observation titles, tags, salience and evidence. Other generated documents receive source/event-ID continuity references, not previous generated paragraphs. Each uncached request receives the complete narrative guardrails, identity tags, formatting standard and date specification; place writing also receives the complete territory-event rules. The style-map JSON informs the renderer and is not sent as prose direction. A deterministic gate requires first-person fighter memories/reflections and rejects known record-reporting/mechanical phrases before caching. A rejected result consumes one attempt but never triggers a second call in the same pass; it leaves the prior successful draft visible as stale and does not block unrelated entries. Cache signatures include the exact contract contents. All forms use the configured output cap (650 by default) and low reasoning effort. The brief still constrains short fighter memories and reflections to concise prose. Policy/code changes invalidate matching cache drafts; disabled startup refreshes retain older drafts and label them stale rather than blanking them.

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

Phrase choices are deterministic from fighter identity and event/topic. Role/biography vocabulary and trait-specific formulations take priority over a general faction formulation. The current writer uses an authored set of bounded variants; it does not learn arbitrary new speech patterns or create freeform dialogue.

## 8. Reflection algorithm

Reflection is generated per fighter and event **batch**, normally the target snapshot ID. Legacy undated baseline records are grouped as baseline, not assigned an invented historical sequence.

1. Start with observation memories in the batch whose importance is at least **4**.
2. Require at least **two** candidates and a combined importance of at least **12**.
3. Sort by descending importance, with stable memory key as the tie-breaker; cite at most **four**.
4. Generate a thematic synthesis using their content/tags (for example injury plus growth, loss, equipment plus learning, or victory/defeat).
5. Set reflection importance to `min(10, round(mean(cited importance) + 0.5, 1))` and confidence to **0.60**.
6. Retain the cited observation IDs, union of factual event IDs, and union of mechanical evidence. Occurrence time remains unknown for the synthesis; observation time is the latest of its cited observations.

No reflection is generated for a currently deceased fighter. The algorithm uses local rule-based synthesis. It does not use embeddings or an LLM. The current threshold is batch-based; it does not yet accumulate a long-running psychological budget across otherwise separate quiet snapshots.

## 9. Mind retrieval

Mind is a current selection from the Memory stream, normally **two to four supported thoughts**. It can contain fewer when evidence is sparse, and contains zero for a deceased fighter. The app does not pad it with unsupported generic thoughts.

Selection score:

`0.40 × (importance / 10) + 0.30 × recency + 0.25 × relevance + 0.05 × character_bias`

The terms are:

- **Recency:** `2 ^ (-age_in_days / 14)`. Future dates have age zero. Unknown dates use age 180 days. An undated baseline memory is additionally capped at recency 0.15 so regeneration does not make an old baseline event newly recent.
- **Relevance:** 1.0 for overlap with active condition/role tags; 0.65 for battle/equipment/promotion/advancement/return concerns; 0.25 otherwise. A return memory is 1.0 when the current status is Active. Closed bodily concerns are filtered or reduced as below.
- **Character bias:** 1.0 for a preferred voice-profile topic, otherwise 0.5 for a current active concern, otherwise 0.0. The small weight makes it a tie-influencing preference, rather than a substitute for importance and recency.

Active conditions are derived from current Effects/Status (critical, injury, recovery/convalescence, captivity, humiliation, enmity/grudge, scars). Juves/Prospects add a growth concern; Leaders/Champions add responsibility and belonging.

Trait preferences are explicit:

| Trait/register | Preferred topics |
| --- | --- |
| practical | equipment, weapon, return |
| clinical | injury, recovery, grief |
| responsible | belonging, grief, outcome, promotion |
| aspiring | growth, advancement, promotion |
| enduring | injury, recovery, return |
| physical | equipment, weapon, growth |
| analytical | skill, advancement, equipment |
| resolute | grudge, return, growth |
| blooded | kills, battle |
| measured | territory, equipment |
| inward | reflection, identity |
| C-NINE crew register | belonging |

Death and `history_only` memories never enter Mind. A critical concern is excluded once the fighter no longer has Critical Injury. Recovery is excluded when closed, except a return thought. General injury concerns yield when no relevant current injury/scar/grudge/humiliation remains. Personal captivity is excluded when it ends; shared gang captivity news can remain a belonging concern until superseded. The historical memories remain in the stream.

Rank by descending selection score, then stable memory key. Select at most four, with no duplicate primary label and no overlapping event evidence. This prevents a reflection and its source event from occupying two Mind slots. Each selected thought retains the memory ID, component scores, and a link back to the Memory stream. The first recognized ordered tag chooses its display label.

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

## 10. Narrative regeneration and battle reports

Every source/code revision regenerates all mechanically inferred fighter biographies, non-authored gang histories, territory histories, regional chronicle, battle reports, current downtime reports, event memories/reflections, and repeated-opponent relationship chronicles. Authored biographies and C-NINE lore stay authored; regeneration reads them as context. Previous derived versions are retained with `active=0` when their semantic result changes. Relationship chronicles currently group gang pairs with at least two recorded encounters; they cite those battles and do not establish individual personal bonds.

Battle reports are multi-section documents grounded in the current scenario, date, parties, winner, territory/claimant, faction context, and safely associated roster deltas. Reports never reuse an old account just because the new battle occupies its former Sheet row. Authored battle Notes are preserved in a separately labeled `recorded_notes` field rather than rewritten as generated narrative.

Battle identity prefers a stable source battle-log ID from the visible row or an unambiguous MAIN Data Dump join. Without a source ID, a normalized date/scenario/party fingerprint identifies the encounter; winner, territory and Notes remain correctable content. Duplicate fallback encounters retain content/occurrence discriminators instead of collapsing. Ambiguous edits can produce removal/addition rather than a false correction. Legacy snapshots can acquire source IDs without replaying the battle. Limited identity repair matches an unambiguous correction; a row number alone is a locator, not identity.

A report may describe individual roster changes as **accompanying returns** only when explicitly linked, or when a recent battle and the changes share a non-baseline snapshot transition. This weaker batch association also requires a recorded battle date within one calendar day of observation. It is suppressed if that import contains another battle for the same gang. The evidence says the causal link is inferred. Baseline injuries are not assigned to old battles; no named shot, kill, deployment, treatment procedure, or precise sequence is invented from a stat delta.

Downtime uses current listed recovery/captive conditions, retained historical dead, the latest available gang result, and recent nonbaseline memory topics. It does not invent real-time work schedules or off-table events. Strategic place/gang prose interprets ownership, roster and battle history but does not change it.

## 11. Interface, evidence, and filtering

Primary navigation is Chronicle, Gangs, **Fighters**, Places, Battles, Archive, and System. The previous People label has been replaced. Story appears first; mechanical records remain inspectable.

Every generated narrative view pairs prose with a visibly distinct mechanical evidence block. The Memory stream distinguishes observations/reflections, source dates, salience, source-event/memory references, and generated inference. Mind displays selected thoughts, their source-memory links, and expandable retrieval reasons. Voice-profile evidence is inspectable. Raw campaign changes are formatted into readable field transitions rather than displayed as a wall of JSON.

Semantic report blocks support headings, paragraphs, quotations, lists and record fragments. Limited `**bold**` and `*italic*` are supported after source text is HTML-escaped; arbitrary source HTML is not executed. Authored text preserves paragraph/line breaks. There is no WYSIWYG editing interface in v0.6.

The C-NINE-authored fighter dossier renderer recognizes the document's semantic sections: nameplate, designation and labour/medical fields, audit heading/body, quoted line, archive reference, and explicit termination mark. These are rendered as separate visual blocks instead of flattening all authored text into a generated prose paragraph. Authored biography content is always retained ahead of mechanically inferred biography. The one-fighter pilot is restricted to Mara Kel's authored C-NINE record; it drafts her pending memories/reflection only and does not regenerate any fighter biography or campaign-level narrative.

| View | Search and filters |
| --- | --- |
| Fighters | Text search across name/type/class/gang/backstory/Effects; gang, status, role, and listed/unlisted filters. |
| Gangs | Text search and faction filter. |
| Places | Text search and owner-gang filter. |
| Battles | Text search and gang filter. |

Filters retain their values in browser session storage, show result counts, support clearing, and show an explicit no-results state. Returning from a detail view restores the selected filters. Gang detail links can open that gang's filtered fighter view.

Responsive CSS collapses the fighter split layout, moves Mind above history on narrow screens, adapts filter controls, and wraps evidence. Desktop browser behavior has been inspected. Mobile CSS exists; a full mobile visual check was blocked by the current browser extension's URL-access restriction, so mobile visual verification is **not claimed** at this documentation checkpoint.

## 12. Service and API behavior

The existing Python HTTP/JSON API remains the presentation boundary. It supplies session/login/logout, health/status, dashboard, events, gang/fighter/territory/lore details, and manual sync. Fighter responses include generated memories, selected Mind, voice profile, and biography document. Dashboard/detail payloads attach the relevant narrative artifacts.

The server schedules one Sheet sync at startup and every `NCCE_SYNC_INTERVAL_SECONDS` (default 900, minimum 60), plus manual refresh. Concurrent refresh requests are guarded. A failed source read keeps available local records and reports the sync failure. The UI polls status periodically and refreshes narrative views when the story revision/state changes. Routine syncs keep narrative derivation and cache reuse available but suppress new provider calls unless `NCCE_AUTO_WRITE_ENABLED=1`. The Mara pilot endpoint is authenticated, same-origin, fighter-restricted, persistently one-use, and capped at 13 API calls. Its status response includes each provider request ID and response ID, writing form, subject, model, status, timestamps, token counts, and bounded provider error.

Hosted access uses a shared passphrase and signed HttpOnly/SameSite session cookie; the service can mark it Secure behind HTTPS. This is invite access by shared secret, not per-person accounts or an invitation administration system. Public `/healthz` is a minimal service check; campaign APIs require a session when authentication is enabled.

## 13. Known limits and next design work

- Prose is drafted through the OpenAI Responses API from structured source packets, identity context and continuity. The API key is server-only. A missing key or provider error is shown as pending/error; no phrase catalogue fallback is presented as finished writing. Event classification, evidence, memory selection, dates and game facts remain local deterministic logic. Topic-based relevance remains explicit, not embedding-based.
- The input lacks complete per-fighter battle attendance and event-by-event battle actions. XP does not identify its reason; snapshot time does not identify when an undated injury occurred.
- Baseline cannot reconstruct exact earlier fighter chronology. The first-live bridge preserves this distinction while retaining changes to previously known seed fields.
- Reflection is per batch. It does not yet accumulate salience across several low-event batches or use a continuously changing relationship model.
- Shared death/capture reactions are bounded by gang membership, not known personal relationships. Individual alliances, grudges against a named attacker, rescuer identity, and witnessed deeds need explicit source information before being asserted as fact.
- Equipment deltas show changed possession, not necessarily purchase, gift, theft, loss, or who transferred it. Role deltas show recorded categories, not a rules decision by NCCE.
- The rules suggest meaningful future triggers such as rallying, assistance, scenario objectives, bottling/retreat, medical outcomes, rescue attempts, and precise captive disposition. These do not become specific memories merely because a rulebook contains them; the campaign source must expose them.
- The C-NINE Google Doc is currently a frozen export source in the runtime, not a live document-sync integration.
- The hosted SQLite file now lives on a Render persistent disk and survives ordinary restarts and deploys. The disk is single-instance storage; deployments briefly stop the service. The application still lacks an application-consistent SQLite export/offsite backup flow. Do not treat a filesystem snapshot as a database backup. If the disk is lost, only campaign facts present in tracked baseline and current Sheet can be reconstructed; intermediate event history cannot.

## 14. Validation and deployment checkpoint

The 0.9.9 writer tests, one-use run UI contract, JS syntax check, Python compilation and `git diff --check` passed. The 0.9.9 hosted deploy completed at 10:47:59 CET. Mara's authorized run generated 13 new outputs and the profile was inspected after completion; authored biography remained unchanged.

Hosted release `0.9.9` (`4baef9f`) is live at https://ncce-private-preview.onrender.com/. Routine writer calls remain disabled. The screenshot's 96 API requests were shown with All API sources, projects and keys selected, so they cannot all be attributed to NCCE. Mara's earlier 13-call pilot used 13 calls; the 0.9.6 review failed at the 180 output-token ceiling; a one-call 0.9.7 sample demonstrated the 0.9.8 settings; and the authorized 0.9.9 Mara regeneration completed with 13 successes. A prior deployment record documents a successful 80-draft NCCE batch, but schema 8 had no request-level IDs; exact historical request-to-output mapping is unavailable. Deployment details and the remaining backup limitation are in `CHANGELOG.md`.

## 15. Campaign history archive and timeline

The source workbook contains three separate raw archive tabs: `MUNDA_ACTIVITY_RAW` (`gang_logs`), `MUNDA_BATTLES_RAW` (`campaign_battles`), and `MUNDA_SESSIONS_RAW` (`battle_sessions`). They are fetched through the existing read-only XLSX integration. No Apps Script or Sheet write was added. Current state remains sourced from the existing campaign/gang tabs; archives are historical evidence.

`campaign_history.py` retains typed values, original timestamp text, UTC instants when an explicit timezone exists, complete Raw JSON, spreadsheet row/tab locators, payload/version hashes, and parse issues. Blank trailing rows are ignored. Activity IDs are append-only. Mutable battle/session records retain each `(source table, record ID, version hash)`; the latest version is selected by valid `Archived At`. Reimports are idempotent. Same-key/different-payload collisions are stored separately and shown as warnings. Archive time is never used as event time.

The battle registry starts with documented `campaign_battles` records. A session links only through exact `battle_sessions.campaign_battle_id = campaign_battles.id`; there is no date/scenario fuzzy join. Orphan sessions and battles without sessions stay visible. Multiple sessions remain individually inspectable. Current source data is not rewritten.

`gang_logs.created_at` is the activity's recorded time. For a completed linked session, `created_at` and `updated_at` form a **candidate session-time proxy**, not a confirmed gameplay start/end. The chart and detail view label this caveat. Session statuses that are scheduled, pre-battle, in progress, cancelled, or abandoned do not get a completed end. Missing or timezone-naive timestamps remain unavailable. Activity is classified per gang: inside one candidate session, between candidate battle windows, after the latest window, before the first window, in an unresolved gap between sessions of one battle, ambiguous across overlapping sessions, unassigned when no gang window exists, or unavailable when time is missing. No campaign-wide serial order is imposed.

The fighter activity endpoint uses stable source UUIDs and resolves a display name from the current roster when possible; deleted/renamed fighters remain in the archive with source identity and description-derived name hints. A positive XP increase recorded inside a candidate window for a participating gang is presented as **inferred** participation, not a factual deployment record. Explicit participation reasons improve the inference label. An XP decrease is not evidence of participation. Explicitly marked ally participants are excluded from XP-only inference. No XP evidence means participation remains unknown; other activity may corroborate but does not prove presence.

The Chronicle timeline has per-gang lanes, separate linked session bars, change markers, candidate downtime gaps, a searchable/filterable battle registry, and source detail panels. Filters cover gang, fighter, place, battle, event type, phase and time range. Hover/focus reveals event or session metadata; clicking a battle or event opens its detail and original JSON. Fighter dossiers include matched archive activity with phase, confidence and source. The display keeps documented source facts, time-based inference, ambiguity and missing data distinct.

This feature changes neither generated report prose nor current-state mechanics. It gives later writers a structured chronology source but does not yet incorporate archive records into the model writer's narrative packets.
