# Changelog

Timestamps use Europe/Warsaw. The clock changed to CET (UTC+01:00) on 25 October 2026. Times below are release-record checkpoints, not invented per-file edit times.

## 0.9.9 — one authorized Mara regeneration

**Implementation checkpoint:** 2026-10-26 10:50 CET (Europe/Warsaw)

- Added a server-enforced, persistent one-time Mara regeneration after the earlier one-use review and diagnostic. The endpoint allows only Mara's authored C-NINE fighter record and caps the run at 13 provider calls. No other fighter, place, gang, or battle report can be processed by this run.
- Bumped the writer formatting revision so prior cached drafts cannot satisfy this regeneration. The run used the 0.9.8 production settings: `gpt-6.1-sol`, low reasoning effort, 650-token output ceiling.
- **2026-10-26 10:47:59 CET — deployed:** Render deploy `dep-dbfi38qvcj2c7388cls0` is live for commit `4baef9f` (NCCE 0.9.9/schema 9).
- **2026-10-26 10:49 CET — Mara run completed:** 13 successful provider requests, 0 failed, 0 cached; 20,818 input tokens and 2,446 output tokens. New generated memories and reflection are visible on Mara's profile. Her player-authored C-NINE biography was preserved; no other records were processed.
- Editorial review: the revised entries respond to the injury, Recovery status, work as a maintenance fitter, and recorded gang outcomes. Several still repeat the same return-to-work concern; the reflection uses record-oriented phrasing. This is a successful technical regeneration, but the prose still needs editorial refinement. No further calls were made.
- Validation: writer and UI contracts, JS syntax, Python compilation and `git diff --check` passed. Routine full-roster writing remains disabled.

## 0.9.8 — give reasoning models room to return prose

**Implementation checkpoint:** 2026-10-26 10:38 CET (Europe/Warsaw)

- Applied the settings validated by the 0.9.7 diagnostic to normal writer requests: low reasoning effort and a 650-token output ceiling (the configured default). The writer still receives a short-memory brief of 1–3 sentences / 35–110 words, so this raises the safety budget, not the intended prose length.
- The prior 180-token cap had been consumed exactly by reasoning/output tokens before the API yielded visible prose. OpenAI's documentation confirms reasoning tokens count against `max_output_tokens` and that an incomplete response can contain no visible output. The 0.9.7 probe completed under the new settings: 218 total output tokens, of which 112 were reasoning.
- **2026-10-26 10:37:17 CET — deployed:** Render deploy `dep-dbfhu78u01pc73bbnu5g` is live for commit `5dfb96a` (NCCE 0.9.8/schema 9). No campaign writer run or additional provider request was made after this change; the already completed one-call probe is the validation sample.
- Writer suite, diagnostic-response contract, UI contract, JavaScript syntax, Python compilation and `git diff --check` passed.
- This change does not regenerate existing narratives automatically. The single diagnostic control is exhausted; routine and full-roster generation remain disabled.

## 0.9.7 — expose writer completion diagnostics

**Implementation checkpoint:** 2026-10-26 10:35 CET (Europe/Warsaw)

- The previous Mara memory request used exactly its 180-token output ceiling and returned no visible prose. The adapter had discarded response completion status, incomplete reason, output item types, and reasoning-token count, reducing this to a generic “no prose” error.
- Added response diagnostics for completion status, incomplete reason, output item types, and reasoning tokens. Incomplete responses now report their actual reason instead of looking like an empty successful response.
- Added one authenticated, persistent one-call diagnostic for Mara's Critical Injury → Recovery memory. It uses the same structured NCCE writer instructions and guardrails, a 650-token output allowance and low reasoning effort. It returns a sample and metadata to the profile but does not update the campaign, memory stream, or narrative cache. The diagnostic is now consumed.
- **2026-10-26 10:33:53 CET — deployed:** Render deploy `dep-dbfhslavcj2c7387ilhg` is live for commit `3643d1e` (NCCE 0.9.7/schema 9).
- **2026-10-26 10:34 CET — provider diagnostic completed:** 1 request succeeded: 1,139 input tokens, 218 output tokens including 112 reasoning tokens; response status `completed`, with `output_text`. The sample was displayed but not saved to Mara's records. This strongly supports the output-ceiling diagnosis, but because this probe also lowered reasoning effort, it does not prove which of those two changes was decisive. No further provider call was made.
- Writer tests, diagnostic incomplete-response contract, writing UI contract, JS syntax check, Python compilation and `git diff --check` passed. Routine/full-roster writer calls remain disabled.

## 0.9.6 — scoped revised Mara writer review

**Implementation checkpoint:** 2026-10-26 09:28 CET (Europe/Warsaw)

- Added one server-enforced, persistent retry slot for the explicitly authorized Mara-only prose review. The endpoint permits only Mara's authored C-NINE record, allows at most 13 model requests, and disables itself after this attempt. No full-roster or campaign-report generation was enabled.
- **2026-10-26 09:28:14 CET — deployed:** Render deploy `dep-dbfgu7e7bikc73dh1nb0` is live for commit `96fa191` (NCCE 0.9.6/schema 9). The hosted app was reloaded and Mara's profile showed the single-use review control.
- **2026-10-26 09:30 CET — authorized review completed:** 1 provider request attempted; 0 successful, 1 failed, 0 cached; 1,551 input and 180 output tokens. The ledger reports `Writing provider returned no prose`. No usable draft was generated; existing authored and generated content was not replaced by this failed response. No other fighters, places, gangs, or campaign reports were processed. The retry slot is consumed; no further provider call was made.
- The metered output-token count does not mean the model returned usable prose. The provider request was accepted far enough to incur token usage, but the application received no prose field. The request ledger preserves this failure. A cause beyond the recorded empty-prose result is not established from the application response.
- Documentation reflects the live version and the failed single-fighter review. Routine writer generation remains disabled.

## 0.9.5 — inferred fighter context and event-isolated writing

**Implementation checkpoint:** 2026-10-26 02:07 CET (Europe/Warsaw)

- Added evidence-labelled inferred fighter identity facets to the profile, drawing only on roster role/type, gang/faction, explicit authored occupation cues, current condition, and bounded characteristic/voice cues. Gender, pronouns, lineage, upbringing, relationships, beliefs and motives remain unknown unless explicitly sourced. Optional authored corrections stay separate from inference.
- Added per-topic stimulus-attention weights (1.00 baseline; +0.15 for supported voice tendencies; +0.30 for a matching active condition/role; cap 1.50), with basis visible in the dossier and prompt. These weights do not alter mechanical state, memory importance, reflection thresholds or Mind selection.
- Isolated fighter observations to one event and its evidence. Full biographies and previous generated prose no longer enter every fighter-memory call. Reflections receive cited observation metadata/evidence instead of repeated model prose. Added explicit directions against unrelated backstory recap, provenance/meta commentary and generic AI phrasing.
- The model now receives bounded excerpts from the maintained narrative guardrails, identity rules and formatting standard. Short observations are capped at 180 output tokens, reflections at 300. Writer prompt revision changes invalidate cache matches.
- Prevented disabled startup refreshes from blanking previously generated writing after a prompt update. Existing text remains visible as `stale` with an explanation until an authorized writer run revises it; routine writer generation remains disabled.
- Investigated usage screenshots: the displayed $1.69 / 353,466 tokens / 259 requests aggregate all API sources, projects and keys and cannot be assigned to NCCE. The exact hosted Mara ledger records 13 successes, 18,090 input and 5,171 output tokens (about 1,390 input tokens per request). Likely avoidable input included repeated authored biography and prior fighter memories; related gang/place/report calls also reused generated prose. The historical 80-draft batch predates per-request ledgering, so its exact usage cannot be reconstructed. The screenshot alone cannot establish how many calls or tokens came from NCCE. Local runtime request ledger contains no additional requests. No new provider requests or campaign narrative regeneration were performed for 0.9.5.
- Added offline tests for identity/stim provenance, guardrail loading, event isolation, token caps and stale-draft retention. All documented offline suites and syntax checks passed; local HTTP smoke remains blocked by sandbox loopback socket permissions.
- **2026-10-26 02:07:09 CET — deployed and verified:** Render deploy `dep-dbfaf5o473hc73ceckg0` is live for commit `a392079` (0.9.5/schema 9). The app reloaded successfully, completed its scheduled Sheet sync, and Mara's dossier visibly displayed inferred identity facets and stimulus-attention weights. Her earlier 13-call writer pilot and all existing prose remain unchanged/stale. No provider request or campaign narrative regeneration occurred during this release.

## 0.9.4 — repair persisted writer-run endpoint

**Implementation checkpoint:** 2026-10-26 01:36 CET (Europe/Warsaw)

- Render logs showed `/api/writer-runs/<id>` raising `UnboundLocalError` when the endpoint referenced `llm_writer`: a redundant import inside `/api/health` made Python treat the module name as local throughout `do_GET`.
- Removed the route-local import; the module is imported once at server startup. This lets the persisted Mara run endpoint compute the request ledger without changing or regenerating campaign content.
- Added a UI contract guard against reintroducing the local import and updated the disposable smoke check's expected app version.
- No provider requests or campaign writes were made for this fix. Full-roster writing remains disabled.
- **Validation:** all seven Python suites, Python compilation, Node writing/timeline contracts, `node --check web/app.js`, and `git diff --check` pass. The local HTTP smoke could not bind loopback in this sandbox (`WinError 10013`).
- **2026-10-26 01:35:22 CET — deployed:** Render reports commit `5927c38` live as deploy `dep-dbfa08vavr4c73dbu5ug`.
- **2026-10-26 01:36 CET — verified:** hosted health reports app `0.9.4`, schema 9, and successful Sheet sync. The authenticated persisted-run endpoint returns Mara's 13 request rows (13 succeeded, 0 failed; 18,090 input and 5,171 output tokens); her profile now shows the completed run summary and expandable request/response IDs after reload. No writer calls were made during this fix or deploy.

## 0.9.3 — persistent Mara results and request progress

**Implementation checkpoint:** 2026-10-26 01:32 CET (Europe/Warsaw)

- Preserved the request ledger as collapsed semantic markup after Mara's result refresh; the previous UI flattened the ledger into a wall of wrapped text.
- Shows attempted calls from the active writer run while SQLite is still committing the generated records, instead of showing a misleading zero until completion.
- Added an authenticated read-only endpoint and profile hydration so Mara's one-time pilot result, ledger and generated prose summary remain visible after reload or service restart.
- Updated the one-time test contract and current design/handoff documentation. No provider calls were made by this source-only UI change.
- **Source validation:** all seven Python suites passed (core, battle identity, campaign history, 15 story-engine checks, voice, Writing Director, and writer); Python compilation; Node writing and campaign-timeline UI contracts; `node --check web/app.js`; `git diff --check`. The local HTTP smoke was blocked by sandbox loopback restrictions (`WinError 10013`).
- **2026-10-26 01:31:27 CET — deployed:** Render reports commit `4e3b428` live as deploy `dep-dbf9u5fb9u1s73c5bbkg`. Hosted `/api/health` confirms NCCE 0.9.3, schema 9, persistent DB `/var/data/ncce-preview.db`, and configured `gpt-6.1-sol` writer. No writer calls were triggered by deployment.
- **2026-10-26 01:32 CET — verified after reload:** Mara Kel's profile loads the persisted 13-entry memory stream, the completed reflection, and the disabled one-time pilot control. Her authored dossier is visibly labeled `player-authored / C-NINE story` and remains separate from generated writing. No second pilot was run.
- The hosted pilot produced 13 successful provider requests, not 96. The screenshot's 96 total calls were filtered to all API sources, projects, and keys, so it does not identify NCCE requests. The 0.9.1 record documents an earlier 80-draft NCCE batch; schema 8 had no request-level IDs, so exact historical call-to-output mapping is unavailable. The new ledger records request/response IDs, forms, outcomes, and token counts for future calls.

## 0.9.2 — authored dossier rendering and Mara writer pilot

**Implementation checkpoint:** 2026-10-26 01:15 CET (Europe/Warsaw)

- Preserved Mara Kel's authored C-NINE dossier as semantic document sections (nameplate, role/medical fields, audit heading/body, quotation, archive reference, and termination mark) rather than flattening it into generated prose. Authored content continues to take precedence over inference.
- Added a one-time, authenticated Mara-only writer check. It drafts only her pending memories/reflection, never her authored biography or campaign-level reports, and enforces a maximum of 13 provider calls. The one-use flag persists in the SQLite database across service restarts.
- Disabled new provider calls in routine Sheet refreshes by default during this pilot. Re-enable full-roster writing with `NCCE_AUTO_WRITE_ENABLED=1` only after the pilot is reviewed and that broader scope is approved. Existing successful prompt-cache entries can still be reused without a provider call.
- Added schema 9 `writer_requests` ledger with provider request ID, response ID, subject, form, model, timestamps, outcome, token counts and bounded error details. The Mara result panel can expand the ledger to show exactly what each provider call wrote and its usage.
- Corrected story fingerprint stability so per-run identifiers do not cause every sync to appear changed.
- Validation before hosted deployment: Python compilation, core suite, writer suite, all 15 story-engine checks, Node writing UI contracts and `git diff --check` passed. The local HTTP smoke was blocked by sandbox loopback networking (`WinError 10013`).
- No authoritative Sheet data, mechanical campaign facts, authored source files or canon were modified.
- **2026-10-26 01:21:24 CET — deployed:** Render reports commit `6863632` live as deploy `dep-dbf9pjfb9u1s73c4s5o0`. Hosted health confirms app `0.9.2`, SQLite schema 9, persistent database, and configured `gpt-6.1-sol` writer.
- **2026-10-26 01:24 CET — Mara-only test completed:** 13 successful calls (12 `fighter_memory`, 1 `fighter_reflection`), 18,090 input tokens, 5,171 output tokens, 0 failed calls and 0 cache hits. The app generated only Mara's pending memories/reflection; her player-authored C-NINE dossier remained untouched. The output and request/response IDs were visible in her profile.
- The usage screenshot's 96 total calls were filtered to all API sources, all projects, and all keys, so it does not identify NCCE requests. The 0.9.1 release record documents one 80-draft successful batch; the older hosted schema had no per-call request ledger, so exact historical call-to-output mapping is unavailable. New requests are traceable by API request and response ID.

## 0.9.1 — Writer integration repair

**Implementation checkpoint:** 2026-10-26 00:44+01:00 (Europe/Warsaw)

- Fixed the OpenAI Responses structured-output schema rejection by removing unsupported `uniqueItems`; returned marks continue to be deduplicated and validated by NCCE.
- Provider HTTP errors now expose bounded structured details to help distinguish invalid requests from missing credentials, while redacting the configured API key.
- Call-budget exhaustion now leaves remaining narratives explicitly pending for the next refresh instead of labeling them as provider errors.
- Confirmed the hosted writer is configured for `gpt-6.1-sol`; its first successful post-fix refresh completed 80 requests and committed the result. Further pending narratives continue on subsequent refreshes using the successful result cache.
- Validation: all six focused writer tests passed; Python compilation and `git diff --check` passed. Full baseline suites passed on the preceding 0.9.0 source.
- No campaign Sheet, Apps Script, authored lore, or mechanical source data was changed.
- **2026-10-26 00:46:24+01:00 — deployed:** Render reports commit `e110408` live. Health confirms app `0.9.1`, schema 8, and the OpenAI writer configured as `gpt-6.1-sol`. The first repaired refresh completed and committed 80 successful drafts; a subsequent cache-aware batch is currently processing.

## 0.9.0 — Munda Manager campaign history timeline (deployed in 0.9.1)

**Implementation checkpoint:** 2026-10-26 00:18:12+01:00 (Europe/Warsaw)

- Added read-only import for `MUNDA_ACTIVITY_RAW`, `MUNDA_BATTLES_RAW`, and `MUNDA_SESSIONS_RAW` through the existing workbook fetch. The authoritative campaign Sheet and Apps Script were not modified.
- Added schema 8 for append-only activity records, versioned battle/session records, raw source rows, import runs, and conflicting-payload reports. Repeat reads are idempotent; earlier versions and original JSON/timestamp strings remain inspectable.
- Built the battle registry using only `battle_sessions.campaign_battle_id` exact joins. Missing sessions, orphan sessions, invalid timestamps, same-battle session gaps, and overlapping gang windows are retained and marked for review.
- Session `created_at`/`updated_at` values are labeled candidate timing proxies; activity `created_at` is treated as the time Munda Manager recorded the change. Neither establishes literal play time.
- Added gang-scoped event classification and separate XP-based participation inference. Positive fighter XP changes inside an involved gang's candidate session window may infer attendance; non-positive XP, explicitly marked allies, ambiguous windows, and absent evidence do not establish attendance.
- Added a Chronicle SVG timeline with separate linked-session spans, a battle registry, event/battle detail panels, source JSON, and filters for gang, fighter, place, battle, event type, phase and date. Fighter dossiers now show matching historical activity.
- Story-writing behavior and lore were not changed; archive chronology is not yet included in model-writer packets or generated battle prose.
- **2026-10-26 00:18:12+01:00 — validation passed:** all 49 Python checks across core, battle identity, story engine, voice, Writing Director, model writer, and campaign history; Node renderer/date and campaign timeline drilldown contracts; `node --check web/app.js`; Python compile checks; and `git diff --check`.
- The disposable application initialized its schema and started listening at `127.0.0.1:8765`. Requests from the current sandbox were denied by Windows loopback socket permissions, so HTTP/API and authenticated live-sync smoke verification could not be completed. The hosted app was not deployed or modified.

## 0.8.1 — Semantic red-status formatting (source only, not deployed)

- Updated writer output from plain paragraph strings to structured inline runs with constrained semantic marks.
- Applied the supplied formatting standard: smallest-span red styling for evidenced adverse statuses, missing/unverified information, and explicit machine/source errors; redaction remains semantically distinct.
- Preserved marked runs in narrative artifacts, fighter memories and Mind while retaining plain text for continuity, search and evidence.
- Added schema 7 and renderer coverage for `critical_status`, `error_or_missing` and `machine_error`.
- Validation: pending for this iteration. No live model call or production database change.

## 0.8.0 — Model-backed Writing Director (source only, not deployed)

- Replaced visible deterministic phrase assembly with OpenAI Responses API drafting for fighter memories/reflections/biographies, gang and place origins/streams, battle reports, downtime, relationships, and campaign history.
- Added form-specific briefs and structured fact/identity/knowledge/continuity packets. Mechanical evidence, dates, attribution, mind selection and source IDs remain controlled by app logic.
- Added server-only `NCCE_OPENAI_API_KEY`, fixed OpenAI API destination, configurable `NCCE_WRITER_MODEL` (default `gpt-6.1-sol`), output/time/call bounds, circuit-breaker behavior, and persistent success cache in schema 6.
- Missing credentials or provider failures are explicitly shown as pending/error; the old phrase catalog is not displayed as fallback prose. Provider errors retry at a later refresh.
- Added offline mocked-provider contract checks. No live campaign data was sent during implementation; no production database was migrated and no hosted deployment was made.
- The user explicitly authorized sending relevant factual campaign records, identity tags, authored context and continuity to OpenAI API for writing. Configure the secret in the existing Render service manually before deploying; `sync: false` does not prompt for secrets during updates to an existing Blueprint.

## 0.7.0 — Writing Director (source only, not deployed)

- Ingested the five supplied writing/style/date/territory specifications as preserved reference files and integrated them with the identity rules in `docs/WRITING_DIRECTOR.md`.
- Added a shared director for document forms, attribution, character context, date conversion, semantic archive wrappers and limited generated game-term translation.
- Added schema-5 persistent Places/Gangs streams, historical entry versions, continuity references and authored fighter-identity revisions. Added a dossier editor for identity context.
- Extended territory diffs and projection to cover stable transformations, ownership, ruin and arbitrary recorded property changes; retain original descriptions independently of progressing events.
- Added bounded owner-aware ambient fiction: a weekly 25% opportunity per territory, maximum two reports campaign-wide, minimum seven days between reports for a place, with no backfill or mechanical effects.
- Added Imperial/real-world date stacks with Warsaw conversion, fixed `998.M41`, unknown-date semantics and a deterministic formula. The supplied 10:46 example computes to fraction 814; date-only noon computes to 815.
- Added semantic block rendering, copy-safe redaction marks, archival palette, responsive layouts and date/renderer contracts. Authored biographies remain visible even if an older generated artifact exists.
- Validation: existing 31 Python checks plus six director integration checks; Node date/render contracts; syntax/compile checks; authenticated HTTP smoke against a disposable database with read-only Sheet sync; desktop synthetic preview. No production database or Sheet writes.
- Historical note: this release initially used local phrase assembly. Version 0.8.0 replaces visible generated prose with model drafting. Ambiguous territory names still require a stronger source identity before a battle can be assigned to one place. See the director document for limits and source interpretation.

## 0.6.1 — Roster visibility and voice correction

**Implementation checkpoint:** 2026-10-25 19:19:33+01:00 (Europe/Warsaw; source, tests, and database comparison)

- Current authoritative Sheet export contains **92 fighters**, including Mara Kel with Recovery and Critical Injury. Its active gang roster names match the tracked seed roster name-for-name; the local schema-4 database also contains Mara as listed. The evidence does not support a Sheet/parser/database deletion.
- Removed filter restoration from browser `sessionStorage`: a stale search/gang/status filter could silently hide fighters across page reloads. Filters still work within the current page session. Fighter results now show `shown of total` when filtered, so a narrowed view is visible.
- Separated a memory's event title into a blue mechanical-trigger label and removed the repeated “Generated fighter voice · inference” footer. Mechanical evidence remains separate from the fighter's words.
- Corrected Palanite recovery, battle-outcome, kill and role phrases that called the precinct a “detail,” importing C-NINE-specific vocabulary. Added a regression check that confines the C-NINE register to C-NINE and rejects this phrase leakage.
- Bumped the engine/prose version to `0.6.1` / `story-0.6.1`; the engine will regenerate derived narratives when this build starts.
- The broader voice/format rewrite remains a design step: preserve the C-NINE form for C-NINE, derive another gang's voice from that gang's own authored material and supported campaign evidence, and keep all engine/source provenance outside the diegetic passage. The current deterministic writer cannot infer undocumented relationships or replace faction-source research.
- The hosted app uses a single Starter web instance and a 1 GB persistent disk. `render.yaml` now records the plan, disk mount, and `NCCE_DB_PATH` so tracked infrastructure matches the service.
- **2026-10-25 21:04:40+01:00 — Render upgraded the existing service from Free to Starter** (`0.5c-512mb`).
- **2026-10-25 21:05:17+01:00 — Render attached a 1 GB persistent disk** at `/var/data`; deployment `dep-dbf61vcs728c73e82eh0` completed at 21:08:11+01:00.
- **2026-10-25 21:08:11+01:00 — `NCCE_DB_PATH` changed to `/var/data/ncce-preview.db`.** Deployment `dep-dbf62uebs3rs73chu30g` went live at 21:08:51+01:00 on commit `4816751`. Startup logs confirm SQLite initialized at the mounted path; public `/healthz` returned `{"ok": true, "version": "0.6.1"}`.
- **2026-10-25 21:13:27+01:00 — persistence check passed.** A follow-up deployment of configuration commit `0768221` completed; the new startup did not seed a fresh story database, so the existing `/var/data` database was retained. Public `/healthz` returned HTTP 200 with version `0.6.1` after the brief disk-backed deploy interruption.
- The prior `/tmp` database was not exported during cutover. The mounted database was freshly seeded from the tracked baseline; the existing source data remains authoritative and is read-only. This loses any intermediate history that existed only in the volatile database. The user accepted this cutover risk.
- Render's current listed rate implies about **$7.25/month** on the Hobby workspace ($7 Starter compute + $0.25 for 1 GB provisioned disk), before taxes or other usage.
- Authenticated hosted content and a successful live Sheet sync were not independently verified in Render logs. The 15-minute sync scheduler launched; the live Sheet/API content was not changed by the setup.
- Render disk snapshots are not an application-consistent SQLite backup. An authenticated SQLite online-backup/export path and offsite backup routine remain the next storage milestone.

### Validation record

**2026-10-25 19:19:33+01:00 — local verification recorded:** all **31 deterministic checks passed**: 8 core, 6 battle identity, 15 story engine, and 2 voice-register checks. `tests/smoke_server.py` also passed against a disposable local server and read-only live Sheet sync. Python compile checks, JavaScript syntax check, and `git diff --check` passed. The smoke server uses a temporary database; the tracked campaign source and ignored local runtime database were not changed.

## 0.6.0 — Campaign Minds

**Implementation checkpoint:** 2026-10-25 17:32:54+01:00

**Database schema:** 4

**Generation identifier:** `story-0.6.0`

**Release status:** implementation verified locally and live on the existing hosted preview.

### Implemented

- Connected live Sheet changes to fighter observations, voiced memory history, thresholded reflections, and current Mind retrieval. Mara's Critical Injury and Recovery now have generated reactions with their mechanical evidence, rather than leaving the old seed-time mind untouched.
- Replaced bare advancement terms such as Maex's `Cool` with a diegetic fighter-voice paragraph and a separate factual block such as `Advancement recorded: Cool`.
- Added explainable voice profiles using authored biography hints, gang register, role, and explicit mechanical tendencies. C-NINE uses its authored administrative/industrial vocabulary; other gangs have distinct faction registers.
- Expanded reaction coverage for XP, kills, skills/advancements, bodily conditions/status, weapons/Wargear, characteristic and role changes, recruitment/unlisting, shared gang outcomes, territory changes, gang reputation/alignment, and gangmate death/capture news.
- Replaced the fixed twelve seed-time Mind badges with retrieved thoughts and 28 current topic labels. Select up to four supported thoughts using documented importance, recency, relevance, and voice/context biases. Closed conditions remain historical memories while yielding in current Mind; deceased fighters have no Mind or newly generated posthumous reflection.
- Added schema-4 `story_memories` and `story_artifacts` with separate mechanical evidence, source event/observation pointers, generation versions, and retained inactive prior generated versions. Authored lore, mechanical facts, snapshots, and immutable factual events are preserved.
- Added a first-live comparison bridge so a fresh hosted database can discover changes to known baseline XP/status/Effects without inventing improvements to statistics that the old seed never recorded.
- Regenerated mechanically inferred fighter/gang/place/region histories, battle and downtime documents, and repeated-opponent relationship chronicles. Authored fighter Backstory fields are ingested from the Sheet; existing C-NINE canon remains authoritative.
- Repaired battle identity: source log IDs are preferred; fallback encounter fingerprints, duplicate handling, and correction matching replace row number as identity. Adding a newest battle no longer causes every shifted old row to inherit the wrong prose.
- Rebuilt battle reports from current battle facts, scenario/territory/faction context, and safely associated roster changes. Preserved authored battle Notes separately. Corrected and removed outcomes do not remain active false victory memories.
- Bounded individual roster-change attribution: same-snapshot context is labeled inference, baseline injuries are excluded, recently dated association is required, and multiple same-gang games in an import suppress ambiguous attribution. The source still does not supply a complete fighter deployment list or reasons for each XP gain.
- Reworked story presentation into structured headings, paragraphs, quotations, dossiers, and visually distinct mechanical evidence. Added safe limited bold/italic support, source references, salience explanations, source-memory links, and retrieval reasons.
- Renamed People to Fighters. Added search and filters for Fighters (gang/status/role/listing), Gangs (faction), Places (owner), and Battles (gang), with result counts, no-results state, clearing, and filter restoration.
- Added responsive styles for narrow layouts. Desktop browser behavior and Mara's rendered dossier were inspected. Full mobile visual verification was blocked by the browser extension's URL-confidence access restriction and is not claimed.
- Replaced the current technical design document with the actual module/rule/score specification and preserved the previous review under `docs/archive/DESIGN_REVIEW_2026-10-25.md`. Updated handoff, story architecture, and hosted deployment notes.

### Validation record

**2026-10-25 17:38:44+01:00 — local verification recorded:** all **29 deterministic checks passed**: 8 core, 6 battle-identity, and 15 story-engine tests. They cover first-live bridging, source references, voiced advancements, critical injury and recovery, equipment/promotion, no posthumous Mind, repeat-generation idempotency, authored/mechanical preservation, source identity, correction/removal, and social-memory evidence.

The opt-in `tests/smoke_server.py` check also passed against a disposable authenticated fresh server and a read-only live Sheet sync: startup, login/logout, HttpOnly cookie, 401 protection, schema 4, report blocks, Mara's critical Mind, and Maex's voiced memory.

### Version-control and deployment record

- Repository: https://github.com/fryndlz/NCCE (public code repository, as authorized by the owner).
- Existing invite-access preview: https://ncce-private-preview.onrender.com/.
- Target branch: `main`.
- **2026-10-25 17:38:39+01:00 — application commit `e63b8ef` created and pushed to `main`.**
- **2026-10-25 18:28:27+01:00 — Render deployment `dep-dbf3oeom7kps73flj2hg` started for commit `e63b8ef` in workspace NCCE.** The service's `On Commit` setting did not deploy this push because its source is configured as a public Git repository URL; Render's deployment documentation says such services require a manual deploy. The user confirmed the NCCE workspace; the existing service was deployed without creating a second service or paid resource.
- **2026-10-25 18:29:06+01:00 — Render marked the deployment live.** At 18:29:11+01:00, public `GET /healthz` returned HTTP 200 and `{"ok": true, "version": "0.6.0"}`. The unauthenticated `/api/dashboard` returned HTTP 401, confirming campaign APIs remain gated. Render logs show schema-4 story-engine seeding on startup.
- Source deployment documentation: [Render deploys](https://render.com/docs/deploys) states that public Git repository URL services require manual deployment; [Render health checks](https://render.com/docs/health-checks) explains the default TCP check and HTTP checks.
- Hosted verification used only the public health route and unauthenticated protected-route status. Authenticated hosted campaign content was not inspected; the disposable local HTTP/live-sync smoke test verified that path.
- The startup log confirms the hosted story engine seeded its schema-4 database, but no Sheet-sync completion line appeared in the captured deployment logs. Therefore hosted live-Sheet refresh completion is **not independently verified** in this release record; the local read-only live-sync smoke test passed.
- No paid Render service or persistent disk was created for this iteration. The existing free preview still has ephemeral storage.

### Current limits

The runtime writer is deterministic local code; it does not call an LLM or charge for generation. Prose uses bounded variants and can repeat between similar profiles. Retrieval uses explicit topics rather than embeddings. Reflection is batch-based, social propagation is gang-level, and complete per-fighter attendance/action attribution depends on source information not currently provided. Free-host restarts can discard derived event history that is not recoverable from baseline/current state.
