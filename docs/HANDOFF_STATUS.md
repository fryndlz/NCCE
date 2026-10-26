# Handoff status

**Current source implementation:** NCCE 0.9.4 — fixed authenticated persisted writer-run retrieval, SQLite schema 9

**Hosted implementation:** 0.9.3 on Render Starter with a 1 GB persistent disk mounted at `/var/data`; database path `/var/data/ncce-preview.db`. A 0.9.4 endpoint fix is in progress after Render logs exposed a local-import scoping error.

**Checkpoint:** 2026-10-26 01:35 CET (Europe/Warsaw)

**Deployment:** 0.9.3 / schema 9 is live on Render. Deploy `dep-dbf9u5fb9u1s73c5bbkg` completed at 2026-10-26 01:31:27 CET for commit `4e3b428`. The Mara profile loads, but the 0.9.3 persisted-run endpoint raised `UnboundLocalError`; see 0.9.4 changelog entry for the fix and redeployment status.

**Rollout:** see `CHANGELOG.md` for the application commit, final hosted version, and release verification timestamps.

## Writing Director source update

Read [WRITING_DIRECTOR.md](WRITING_DIRECTOR.md) for the integrated system and exact implementation limits. Five user-supplied source documents are preserved in `docs/writing_sources/`. Places and Gangs expose persistent progressing stories. The OpenAI-backed writer now drafts all generated prose from factual packets, identity context, and relevant continuity. Provider credentials are server-side; no-key or provider errors are visible as pending/error rather than template prose. Mechanical evidence, dates and attribution remain app-controlled.

The hosted Mara-only check completed once: 13 successful provider requests (12 fighter memories, one reflection), 18,090 input tokens, 5,171 output tokens, zero failed/cache-hit drafts. It generated content only for Mara; authored biography remained unchanged, and no other fighter or campaign narrative was regenerated. 0.9.3 displays persisted outputs but its run-summary endpoint failed due to an import scoping bug; 0.9.4 moves that import to module scope. Routine writer calls remain disabled; do not run full-roster writing before the user reviews Mara's output.

## Workspace and product

Continue in the existing repository. Use Git for history; do not rebuild the project or produce another versioned ZIP. Source/data authority remains in `AGENTS.md`. The Sheet is read-only, authored lore is canon, and generated narrative is inference with evidence.

The app implements the principal story loop: campaign facts generate fighter memories, reflections, selected Mind thoughts, and regenerated reports. Narrative generation requires `NCCE_OPENAI_API_KEY`; `NCCE_WRITER_MODEL` defaults to `gpt-6.1-sol`. Relevant campaign facts, fighter identity tags, authored context and prior generated prose are sent to OpenAI for drafting, as authorized by the user. Successful outputs are cached locally; the writer has a per-run call budget. Version 0.9.2 renders Mara's authored C-NINE dossier as semantic sections, preserves her authored content over inference, and records per-request identifiers/token counts. The Mara pilot completed in 13 calls and is retrievable after reload. Routine syncs cannot make new model calls until full-roster writing is explicitly enabled.

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
| Generated histories and reports | Regenerated fighter/gang/place/region histories, battle reports, downtime, and repeated-opponent relationship chronicle. Authored biographies and C-NINE canon preserved. |
| Battle correctness | Stable source IDs/fallback identities, row reorder safety, duplicate handling, current report facts, corrections/removals, and bounded inferred association of recent roster deltas. |
| Presentation and filtering | Structured prose plus visually separate evidence, safe limited emphasis, source links, current Mind traceability, search/filter controls, and responsive CSS. Desktop inspected; mobile visual verification not completed. |
| Validation | 0.9.2 hosted Mara run: 13/13 provider calls succeeded; live app output inspected. 0.9.3 UI/persistence fix passes local Python and Node checks; deployment check remains. HTTP smoke cannot open loopback sockets in this sandbox. |

## Historical limits

Pre-baseline XP, kills, injuries and advancements are known states, not a dated sequence of events. A later snapshot capture time says when NCCE observed a change, not when the tabletop event occurred. A fighter disappearing from a roster is not automatically dead or retired.

Battle records identify gangs and outcomes. Individual attendance, exact reasons for XP, named injury-causing enemies, rescue participants, and detailed in-battle actions are not consistently recorded. Same-update context may support an explicitly marked inference but must not be promoted to mechanical truth. Removed/corrected outcomes are excluded from active current narratives while prior generated versions remain retained.

## C-NINE and authored lore

Use `data/lore/C-NINE Story - canonical export.txt` and its existing biography matches. Preserve names, contradictions, redactions, and deliberate ambiguity. The runtime uses a frozen export; live Google Doc synchronization is not implemented. Sheet Backstory text is preserved for other fighters and used as voice context; it does not silently replace existing C-NINE canon.

## Highest-priority follow-up work

1. Review generated prose against the approved style references as outputs fill through scheduled refreshes; the model writer does not yet consume Munda Manager archive chronology.
2. Complete a real phone/mobile visual and interaction check; responsive CSS alone is not evidence of that check.
3. Add a safe SQLite export/backup workflow. The database now survives service restarts and deploys on a persistent disk, but the app does not yet offer an application-consistent backup download or offsite retention.
4. Expand structured campaign inputs where needed: individual battle attendance, XP reasons, named rescue/medical actions, and explicit relationship evidence. Current XP-based attendance remains inferred; the writer does not yet consume raw archive chronology.
5. Consider longer-term reflection across several batches and richer relationships only after the writer's behavior is reviewed. The present system has explicit rule/topic retrieval, not embeddings or a learned personality model.

## Development behavior

Read current documents and inspect the existing implementation before continuing. Keep source records/canon intact, version derived changes, run relevant tests, and document material limits. Ask for owner input only when a decision affects desired behavior, canon, credentials/permissions, cost, or irreversible state.
