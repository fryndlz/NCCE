# NCCE 0.8.1 — current technical design

**Source release:** 0.8.1, model-backed Writing Director (not yet deployed)

**Hosted release:** 0.6.1 on Render Starter, one instance, with a 1 GB persistent disk mounted at `/var/data`. SQLite database path: `/var/data/ncce-preview.db`.

**Schema:** SQLite version 6

**Documentation checkpoint:** 2026-10-25 22:30 CET (Europe/Warsaw, UTC+01:00)

**Release verification:** hosted `/healthz` returned HTTP 200 and version `0.6.1` after redeploy. The app reused its database on `/var/data` without a fresh-seed log. The 31 deterministic checks and local authenticated HTTP/live-sync smoke passed before this infrastructure-only change. See `CHANGELOG.md` for deployment evidence.

This document describes implemented behavior. It is the technical specification of the current app, including its constants and limitations. The previous v0.5 review is preserved in `docs/archive/DESIGN_REVIEW_2026-10-25.md`.

## 0. Writing Director additions

The current writing contract and implementation are described in [WRITING_DIRECTOR.md](WRITING_DIRECTOR.md). The imported specifications are preserved in `docs/writing_sources/`; the identity taxonomy is in [WRITER_IDENTITY_TAGS.md](WRITER_IDENTITY_TAGS.md).

Version 0.8 adds `llm_writer.py` (OpenAI Responses API drafts, structured outputs, caching and request bounds) to the 0.7 director. `writing_director.py` handles document forms, authored perspective packets, dates and guardrails; `world_streams.py` handles versioned gang/place entries and bounded ambient fiction; `writing.js` handles browser calendar rules; `writing.css` styles the semantic archive. Schema 7 adds a persistent model-result cache, writer status, and semantic inline marks for narrative red-status styling to the schema-5 identity revisions, narrative streams and raw territory-state retention. Original place/gang descriptions are kept separately from progressing stories. Territory diffs cover ownership, transformations, other fields and listing changes. The fighter numerical rules below remain in force.

Current local validation: 37 Python checks, the Node date/semantic-renderer contract check, and a disposable authenticated HTTP/live-sync check pass. Hosted 0.6.1 verification below is historical deployment evidence, not a claim that this source release has been deployed.

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
| `src/google_sheets.py` | Read-only workbook download at the source boundary. No Sheet write capability. |
| `src/snapshot.py` | Standard-library XLSX/XML parsing, normalized gang/fighter/territory/battle records, source-ID joins from the MAIN Data Dump, stable battle keys and duplicate handling. |
| `src/models.py` | Dataclasses documenting the principal snapshot/entity shapes. The running pipeline also uses dictionaries. |
| `src/diff.py` | Pure comparison of normalized snapshots. Produces factual event drafts, subjects, source locators, and before/after payloads. Matches battle identities without treating row insertion as a new history. |
| `src/sync.py` | Source registry, snapshot persistence, seed-to-live bridge, immutable factual event ingestion, current-state projection, then story regeneration. |
| `src/store.py` | SQLite access and migrations; source/entity/event APIs; current-state projection; authored biography preservation; dashboard and detail response assembly. Attaches narrative documents, memory history, and selected Mind thoughts. |
| `src/migrations.py` | Schema versions 1–4, legacy provenance backfill, immutable-record protections, current membership flags, and versioned story tables. |
| `src/story_engine.py` | Event classification/importance, memory creation, bounded shared gang events, reflection batches, narrative revisioning, source links, and current Mind retrieval. Owns the numerical rules listed below. |
| `src/story_prose.py` | Deterministic local writer. Builds voice profiles, first-person event interpretations, thematic reflections, generated biographies/histories, battle documents, and downtime documents. Owns phrase and style rules. |
| `src/narrative.py` | Legacy deterministic templates retained for initial seed compatibility. The active v0.6 story layer supersedes the old seeded moodlets and narrative text. |
| `src/seed.py` | Creates a missing database from tracked baseline data and the C-NINE export. Refuses to overwrite an existing database. |
| `src/baseline_data.py`, `data/fighters.json` | Historical seed data. They do not override a subsequent live Sheet read. |
| `data/lore/` | Frozen C-NINE authored source files. |
| `src/server.py` | HTTP/static assets, authenticated JSON API, startup story generation, serialized background refresh, health/status, and manual refresh. |
| `web/app.js` | Narrative/evidence rendering; navigation; fighter history/Mind; search/filtering; refresh of the visible view when source/story state changes. |
| `web/index.html`, `web/style.css`, `web/login.html` | App shell, responsive dossier presentation, and passphrase page. |
| Windows launcher and `scripts/` | Existing local startup and initialization entry points. |
| `tests/test_core.py` | Persistence, sessions, parsers, immutable ledger, snapshots, migration, and sync coverage. |
| `tests/test_battle_identity.py` | Stable source/fallback battle identities, row insertion/reordering, corrections, duplicate ambiguity, and raw-dump source-ID joining. |
| `tests/test_story_engine.py` | Event-to-memory/Mind behavior, first-live bridge, source links, idempotency, regeneration, canon preservation, and corrected/removed battle behavior. |
| `tests/smoke_server.py` | Opt-in authenticated HTTP integration check using a disposable fresh database and a read-only live Sheet refresh. |

There is no external language-model dependency, embedding service, API key, generation charge, or continuous off-table life simulation in v0.6. The writer and selection rules run locally on the host. The prose is constrained and can repeat between fighters with similar profiles; it is not equivalent to open-ended model composition.

## 3. Runtime sequence

1. Open or seed the existing database and apply migrations to schema 4.
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

Munda Manager/Sheet battle data identifies participating gangs. The current input does not provide a complete fighter deployment list. A fighter's XP delta does not explain whether it came from participation, objectives, rallying, assistance, or combat. A named injury does not identify its attacker. These details are not invented as mechanics.

## 7. Fighter voice rules

The voice profile is explainable metadata, not a diagnosis. Authored biography vocabulary takes priority as context. When personal text is absent, faction, role, type, characteristics, and recorded kill history supply the profile; skills/advancement events also have specific phrasing. Generated biographies describe the same evidence and remain inference rather than supplying newly invented canon.

Register selection is C-NINE crew, Van Saar technical, Palanite/Enforcer precinct, Ironhead/Squat charter, Orlock road, or general underhive. Beast/organism types use sensory phrasing. C-NINE retains its administrative/industrial conventions without forcing other gangs into that style.

Authored role hints select workshop/practical, medical/clinical, survey/measured, or attentive/inward vocabulary. The rule uses explicit word matches such as maintenance/repair/workshop, chirurgeon/medicae, survey/prospect/drill, and psyker/listening designations. It does not infer an unwritten historical occupation as fact.

Voice profiles expose normalized explicit identity tags and identity fields when supplied directly to the writer. The runtime roster projection does not yet persist these as first-class authored fields. Gender and pronouns are never guessed. The broader perspective/tag rules, including rules-derived context boundaries, 40k/Necromunda coverage, and implementation plan, are in [Writer identity and perspective rules for Minds and Memory Streams](WRITER_IDENTITY_TAGS.md). Identity tags are descriptive context; they do not affect the numerical story engine.

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

The server schedules one Sheet sync at startup and every `NCCE_SYNC_INTERVAL_SECONDS` (default 900, minimum 60), plus manual refresh. Concurrent refresh requests are guarded. A failed source read keeps available local records and reports the sync failure. The UI polls status periodically and refreshes narrative views when the story revision/state changes.

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

The current deterministic test suite has **31 passing checks**: 8 core, 6 battle identity, 15 story tests, and 2 voice-register checks, verified at 2026-10-25 19:19:33 CET. Checks cover Mara's Critical Injury reaching memory and Mind, Maex's voiced Cool advancement with separate evidence, recovery closure, equipment/promotion events, dead-fighter Mind exclusion, repeat-sync/generation idempotency, authored/mechanical preservation, first-live comparison, battle reorder/correction/removal behavior, social-memory evidence, and keeping Palanite precinct vocabulary separate from C-NINE's register.

The opt-in `tests/smoke_server.py` integration check also passed with a disposable authenticated fresh server and a read-only live Sheet sync: startup, login/logout, HttpOnly cookie, protected-route 401 responses, schema 4, semantic report blocks, Mara's critical Mind, and Maex's voiced memory. Hosted verification for `0.6.1` confirmed public health version and that startup initialized SQLite under `/var/data`. The successful live Sheet sync has not yet been independently confirmed in hosted logs.

Release `0.6.1` (`4816751`) is live at https://ncce-private-preview.onrender.com/. Render's public health route returned version `0.6.1` after the storage change. Deployment details and remaining backup limitation are in `CHANGELOG.md`.
