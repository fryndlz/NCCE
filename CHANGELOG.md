# Changelog

Timestamps use Europe/Warsaw. The clock changed to CET (UTC+01:00) on 25 October 2026. Times below are release-record checkpoints, not invented per-file edit times.

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
