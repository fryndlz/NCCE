# Handoff status

**Response limit fix — 2026-10-27:** Palanite Precinct Workshop trial hit the old 1,800 total response-token cap and returned truncated JSON (`incomplete: max_output_tokens`). Default/configured allowance is now 4,000 tokens including reasoning and prose for every form; the old personal 650-token sub-limit is removed. Luna/medium and one call per trial remain unchanged. Do not automatically retry the failed trial or overwrite owner edits.

**Writer configuration — 2026-10-26:** owner explicitly requested `gpt-6-luna` / `medium` instead of Sol / low. Source defaults and Render configuration match that selection. Do not run a comparison or regenerate prose as part of changing this setting. Historical model/effort references below describe their original runs.

**0.11.0 verified checkpoint — 2026-10-26 21:58:56 CET:** Writer Workshop is live at source `9eb029d`, schema 11. Mandatory authenticated/same-origin editing, one-call idempotent trials, immutable revisions/edits, source-backed samples, exact prompt inspection and explicit future-policy activation/rollback are implemented. Tests and disposable application smoke pass. Hosted UI import/restoration of Mara A and exact original prompt inspection were verified. Provider request count remained 108 before/after rollout; no policy was activated, automatic writing remains off, and Mara's authored biography matches the pre-workshop backup. See `WRITER_WORKSHOP.md` and `../CHANGELOG.md`.

The owner has now reviewed all three comparison pairs: territory neither (lean A), Mara A, gang neither (lean B, but narration mismatched an internal report). Comparison identities may be revealed; no prompt or rejected sample should be automatically promoted. Workshop feedback resolves actual identities from the private saved audit.

**0.10.1 checkpoint — 2026-10-26 21:27 CET:** the owner approved a six-call blinded comparison after rejecting the earlier pilot for vague suggestion, inconsequential detail and loss of the shrine's identity. Source `1e2ccbe` is live. Three matched cases (Bone Shrine event, Mara Kel injury memory, Ethernetans gang event) each have A/B outputs in **System → Writing comparison**. All six calls succeeded: 13,674 input / 1,299 output tokens, 47 reasoning tokens, zero cached input, no retries. Server audit confirms only instructions differ within each pair. Await the owner's A/B/neither judgement before revealing assignment or promoting the candidate. The current production contract is still v6; automatic writing remains off. See `WRITER_COMPARISON_0_10_1.md` and `../CHANGELOG.md`.

**0.10.0 checkpoint — 2026-10-26 20:55 CET:** shared runtime writing contract across all fourteen forms, positive examples, explicit creative permission, historical context, structured composition, retained responses and usage, and separate four-entry editorial preview. See `WRITER_PIPELINE_0_10.md`. Existing and new offline tests and authenticated live-Sheet HTTP smoke pass. Routine writing remains disabled. Source `e5b26ec` is live; four Bone Shrine previews completed with 8,809 input / 1,249 output tokens, 1,613 cached input tokens, no failures or retries. View System → Writing preview. The entries are not published campaign history. Literary approval remains pending; do not infer bulk-generation approval from this test. Full deployment, request and editorial evidence is in `../CHANGELOG.md`.

**Current source implementation:** NCCE 0.11.0 — direct Writer Workshop and shared narrative pipeline, SQLite schema 11

**Hosted implementation:** 0.11.0 / schema 11 on Render Starter with a 1 GB persistent disk mounted at `/var/data`; database path `/var/data/ncce-preview.db`. Latest pre-release backup: `/var/data/pre-workshop-0.11.0.db` (39,137,280 bytes). Earlier pre-0.10.0 backup remains.

**Checkpoint:** 2026-10-26 12:54 CET (Europe/Warsaw)

**Territory writing pass:** NCCE 0.9.12 is live on Render (deploy `dep-dbfjq40m7kps739cg2vg`, commit `3ed4168`, live at 12:45:07 CET). The explicitly authorized one-time pass completed 66 targets across 24 active territories: 48 origin/history documents and 18 territory event accounts. All 66 provider requests succeeded; 0 failed, 0 cache hits, 1,599,283 input tokens and 10,306 output tokens; budget was 80. Mechanical Sheet records and authored campaign content were not edited. Three connective-fiction entries were outside the plan and remain unchanged (2 status `error`, 1 `missing`); these were not model request failures. Bone Shrine was checked in the hosted UI: its origin and sourced event account rendered, though “the compiled returns put…” still sounds like compiler/source attribution and shows the remaining prose-quality limitation. No repeat generation was made. Routine writing remains disabled.

**Writer enforcement update:** 0.9.11 source code now includes the complete narrative guardrails, identity tags, formatting standard and date-format specification in every uncached prompt; place writing also includes the complete territory-event rules. Fighter memories/reflections receive no automatic C-NINE archive-voice override. A deterministic voice/meta-language gate rejects known bad forms before cache storage and allows unrelated entries to continue without a second attempt. Failed replacements retain prior prose as stale. Cache keys include exact contract content. No provider calls or campaign-data edits were made for this update. Deployed to Render at 2026-10-26 11:56:48 CET; routine writer calls remain disabled.

**Previous hosted implementation:** 0.9.10 / schema 9 was live on Render until 11:56:48 CET. Deploy `dep-dbfi9m1srm7s73f3ckf0` completed at 2026-10-26 11:02:36 CET for commit `cf08239`. The authorized medium-effort Mara sample completed five successful requests (7,725 input / 1,761 output tokens); five of thirteen generated memory entries were replaced and eight prior entries, including reflection, were retained as stale. Authored biography and other fighters' records were untouched.

**Rollout:** see `CHANGELOG.md` for the application commit, final hosted version, and release verification timestamps.

## Writing Director source update

Read [WRITING_DIRECTOR.md](WRITING_DIRECTOR.md) for the integrated system and exact implementation limits. Five reference documents are preserved in `docs/writing_sources/`; the guardrail and identity documents have added event-isolation rules. Places and Gangs expose persistent progressing stories. The OpenAI-backed writer drafts from factual packets and scoped context; fighter observations no longer receive the full biography or earlier generated prose. Provider credentials are server-side; no-key or provider errors are visible rather than template prose. Mechanical evidence, dates and attribution remain app-controlled.

The original hosted Mara-only check completed once: 13 successful provider requests (12 fighter memories, one reflection), 18,090 input tokens, 5,171 output tokens. The separate 0.9.6 review used 1,551 input / 180 output tokens and returned no prose. The 0.9.7 one-call diagnostic succeeded using 1,139 input / 218 output tokens (112 reasoning); that sample was not saved. The 0.9.9 Mara regeneration completed 13 successful requests and is visible in-app. The one 0.9.10 medium-effort Mara-only run completed with five requests; routine writer calls remain disabled.

## Workspace and product

Continue in the existing repository. Use Git for history; do not rebuild the project or produce another versioned ZIP. Source/data authority remains in `AGENTS.md`. The Sheet is read-only, authored lore is canon, and generated narrative is inference with evidence.

The app implements the principal story loop: campaign facts generate fighter memories, reflections, selected Mind thoughts, and reports. Narrative generation requires `NCCE_OPENAI_API_KEY`; `NCCE_WRITER_MODEL` defaults to `gpt-6.1-sol`. Per-event mechanical facts remain separate from diegetic writing; the writer receives compact inferred identity and stimulus-attention context. The 0.9.5 profile exposes facet provenance, stimulus weights and optional authored corrections. Runs are fighter-scoped, preserve authored biography and retain older drafts when a call budget prevents replacement. The one authorized medium-effort Mara-only run completed with five requests. Routine writer calls remain disabled.

The exact current technical design, module responsibilities, current labels, trigger/importance rules, voice thresholds, reflection algorithm, Mind formula and limits are in `docs/CURRENT_DESIGN.md`. The earlier design critique is archived as `docs/archive/DESIGN_REVIEW_2026-10-25.md`; `docs/IMPLEMENTATION_AUDIT.md` describes an earlier build.

## Campaign History source update

NCCE 0.9.0 reads `MUNDA_ACTIVITY_RAW`, `MUNDA_BATTLES_RAW`, and `MUNDA_SESSIONS_RAW` from the existing read-only Krakamunda workbook fetch. SQLite schema 8 preserves original records, source locators, timestamps, versions, import runs, and conflicting payloads. Sessions join only by their exact `campaign_battle_id`; no fuzzy date/scenario matching is used.

The Chronicle now has a per-gang timeline, clickable campaign battle registry, source JSON details, and gang/fighter/place/battle/event-type/phase/date filters. Fighter dossiers show archive activity that can be matched to them. Session created/updated times are explicitly candidate proxies rather than verified gameplay boundaries. Activity timestamps say when changes were recorded. Positive XP gains can support a sourced, marked participation inference; they do not prove attendance. XP loss, ally participation, session gaps, overlaps, incomplete data and absent evidence remain unknown or flagged.

This feature does not alter the Sheet, Apps Script, current roster, authored lore, or model-writing rules. The writer does not yet consume the archive timeline. Hosted app release 0.9.1 is live.

## Implemented milestones

| Area | Current status |
| --- | --- |
| Hosted link and invite access | Existing Render preview at https://ncce-private-preview.onrender.com/. Public GitHub source; campaign app protected by a shared passphrase. Starter compute and persistent disk cost about $7.25/month. Deployed release evidence is recorded in `CHANGELOG.md`. |
| Chronicle-first navigation | Implemented. Story/history leads; raw mechanical state is inspectable evidence. People is now Fighters. |
| Durable factual/event/provenance schema | Implemented. Sources, entities, immutable snapshots/events, subjects/roles, evidence links, correction chains, versioned writing output, campaign archive history, and per-request writer ledger. Source and hosted schema 9. |
| Read-only Sheet sync | Implemented. Startup, 15-minute schedule, and manual refresh; source-state projection and narrative refresh follow successful reads. Raw archive tabs are imported into their own versioned local ledger. |
| Campaign history | Source implementation complete. Exact battle/session links, candidate session-time windows, per-gang downtime sequence, archive provenance, conflict/orphan warnings, fighter history and Chronicle Gantt timeline. Participation remains an explicit inference. |
| Snapshot comparison and change tracker | Implemented. Known baseline fields can bridge to the first live read without fabricating new-stat deltas. Unknown occurrence dates stay unknown. |
| Event-to-memory/reflection/Mind | Implemented. Model-drafted observations and sourced reflections when configured; documented salience/thresholds; current thoughts selected by importance, recency, relevance, and character biases. |
| Inferred fighter identity and stimulus attention | 0.9.5 source implementation. Role/type, faction, authored work cues, current condition, supported characteristics/voice traits and bounded topic weights expose provenance in the dossier. No guessed gender/pronouns. |
| Writer event separation and guardrail loading | 0.9.11 source implementation. One-event memory packet, no full biography/old prose, cited reflection inputs, complete applicable writing-contract documents, cache invalidation by contract content, and a deterministic diegetic/meta-language rejection gate. Provider errors and rejected drafts remain visible; no automatic retry is made for a rejected entry in the same run. |
| Generated histories and reports | Regenerated fighter/gang/place/region histories, battle reports, downtime, and repeated-opponent relationship chronicle. Authored biographies and C-NINE canon preserved. |
| Battle correctness | Stable source IDs/fallback identities, row reorder safety, duplicate handling, current report facts, corrections/removals, and bounded inferred association of recent roster deltas. |
| Presentation and filtering | Structured prose plus visually separate evidence, safe limited emphasis, source links, current Mind traceability, search/filter controls, and responsive CSS. Desktop inspected; mobile visual verification not completed. |
| Validation | Writer tests, one-use regeneration UI contract, Python compilation, Node JS syntax and `git diff --check` passed for 0.9.9. The hosted Mara regeneration was run and inspected. Loopback HTTP smoke cannot open sockets in this sandbox. |

## Historical limits

Pre-baseline XP, kills, injuries and advancements are known states, not a dated sequence of events. A later snapshot capture time says when NCCE observed a change, not when the tabletop event occurred. A fighter disappearing from a roster is not automatically dead or retired.

Battle records identify gangs and outcomes. Individual attendance, exact reasons for XP, named injury-causing enemies, rescue participants, and detailed in-battle actions are not consistently recorded. Same-update context may support an explicitly marked inference but must not be promoted to mechanical truth. Removed/corrected outcomes are excluded from active current narratives while prior generated versions remain retained.

## C-NINE and authored lore

Use `data/lore/C-NINE Story - canonical export.txt` and its existing biography matches. Preserve names, contradictions, redactions, and deliberate ambiguity. The runtime uses a frozen export; live Google Doc synchronization is not implemented. Sheet Backstory text is preserved for other fighters and used as voice context; it does not silently replace existing C-NINE canon.

## Highest-priority follow-up work

1. Let the owner refine writing through the Workshop. Comparison feedback is recorded and prompt identities are revealed there. No overall winning prompt was selected; Mara A (current prompt) is imported as an editable sample with zero calls. Save/activate only deliberate owner-approved guidance/examples. The older four-entry pilot was rejected. Routine writing remains disabled. The model writer does not yet consume Munda Manager archive chronology.
2. Complete a real phone/mobile visual and interaction check; responsive CSS alone is not evidence of that check.
3. Add a safe SQLite export/backup workflow. The database now survives service restarts and deploys on a persistent disk, but the app does not yet offer an application-consistent backup download or offsite retention.
4. Expand structured campaign inputs where needed: individual battle attendance, XP reasons, named rescue/medical actions, and explicit relationship evidence. Current XP-based attendance remains inferred; the writer does not yet consume raw archive chronology.
5. Consider longer-term reflection across several batches and richer relationships only after the writer's behavior is reviewed. The present system has explicit rule/topic retrieval, not embeddings or a learned personality model.

## Development behavior

Read current documents and inspect the existing implementation before continuing. Keep source records/canon intact, version derived changes, run relevant tests, and document material limits. Ask for owner input only when a decision affects desired behavior, canon, credentials/permissions, cost, or irreversible state.
