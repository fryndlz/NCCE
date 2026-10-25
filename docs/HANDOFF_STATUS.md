# Handoff status

**Current source implementation:** NCCE 0.8.1 — Model-backed Writing Director, SQLite schema 7 (not deployed)

**Hosted implementation:** 0.6.1 on Render Starter with a 1 GB persistent disk mounted at `/var/data`; database path `/var/data/ncce-preview.db`.

**Checkpoint:** 2026-10-25 22:30 CET (Europe/Warsaw)

**Rollout:** see `CHANGELOG.md` for the application commit, final hosted version, and release verification timestamps.

## Writing Director source update

Read [WRITING_DIRECTOR.md](WRITING_DIRECTOR.md) for the integrated system and exact implementation limits. Five user-supplied source documents are preserved in `docs/writing_sources/`. Places and Gangs expose persistent progressing stories. The OpenAI-backed writer now drafts all generated prose from factual packets, identity context, and relevant continuity. Provider credentials are server-side; no-key or provider errors are visible as pending/error rather than template prose. Mechanical evidence, dates and attribution remain app-controlled.

Local validation: 43 Python checks, Node renderer/date contracts, and the authenticated disposable HTTP/live-sync smoke pass. Read-only WAL snapshots keep the prior committed campaign visible during model drafting. The synthetic preview shows the explicit pending state because this workspace has no API key. The hosted source and persistent database have not been modified for this change.

## Workspace and product

Continue in the existing repository. Use Git for history; do not rebuild the project or produce another versioned ZIP. Source/data authority remains in `AGENTS.md`. The Sheet is read-only, authored lore is canon, and generated narrative is inference with evidence.

The app now implements the principal story loop rather than only refreshing a roster. New campaign facts generate fighter memories, reflections, selected Mind thoughts, and regenerated reports. Narrative generation requires `NCCE_OPENAI_API_KEY`; `NCCE_WRITER_MODEL` defaults to `gpt-6.1-sol`. Relevant campaign facts, fighter identity tags, authored context and prior generated prose are sent to OpenAI for drafting, as authorized by the user. Successful outputs are cached locally; the writer has a configurable per-refresh call budget.

The exact current technical design, module responsibilities, current labels, trigger/importance rules, voice thresholds, reflection algorithm, Mind formula and limits are in `docs/CURRENT_DESIGN.md`. The earlier design critique is archived as `docs/archive/DESIGN_REVIEW_2026-10-25.md`; `docs/IMPLEMENTATION_AUDIT.md` describes an earlier build.

## Implemented milestones

| Area | Current status |
| --- | --- |
| Hosted link and invite access | Existing Render preview at https://ncce-private-preview.onrender.com/. Public GitHub source; campaign app protected by a shared passphrase. Starter compute and persistent disk cost about $7.25/month. Deployed release evidence is recorded in `CHANGELOG.md`. |
| Chronicle-first navigation | Implemented. Story/history leads; raw mechanical state is inspectable evidence. People is now Fighters. |
| Durable factual/event/provenance schema | Implemented. Sources, entities, immutable snapshots/events, subjects/roles, evidence links, and correction chains. Schema 6 adds versioned writing output cache and status. |
| Read-only Sheet sync | Implemented. Startup, 15-minute schedule, and manual refresh; source-state projection and narrative refresh follow successful reads. |
| Snapshot comparison and change tracker | Implemented. Known baseline fields can bridge to the first live read without fabricating new-stat deltas. Unknown occurrence dates stay unknown. |
| Event-to-memory/reflection/Mind | Implemented. Model-drafted observations and sourced reflections when configured; documented salience/thresholds; current thoughts selected by importance, recency, relevance, and character biases. |
| Generated histories and reports | Regenerated fighter/gang/place/region histories, battle reports, downtime, and repeated-opponent relationship chronicle. Authored biographies and C-NINE canon preserved. |
| Battle correctness | Stable source IDs/fallback identities, row reorder safety, duplicate handling, current report facts, corrections/removals, and bounded inferred association of recent roster deltas. |
| Presentation and filtering | Structured prose plus visually separate evidence, safe limited emphasis, source links, current Mind traceability, search/filter controls, and responsive CSS. Desktop inspected; mobile visual verification not completed. |
| Validation | Hosted 0.6.1 had 31 deterministic checks. Source 0.8.0 passed the expanded Python and Node checks plus a disposable authenticated HTTP/live-sync smoke check. Source 0.8.1 adds semantic red-status runs; validation is pending. Hosted health remains 0.6.1; the 0.8.0 commit is pushed but Render has not started its deploy. See `CHANGELOG.md`. |

## Historical limits

Pre-baseline XP, kills, injuries and advancements are known states, not a dated sequence of events. A later snapshot capture time says when NCCE observed a change, not when the tabletop event occurred. A fighter disappearing from a roster is not automatically dead or retired.

Battle records identify gangs and outcomes. Individual attendance, exact reasons for XP, named injury-causing enemies, rescue participants, and detailed in-battle actions are not consistently recorded. Same-update context may support an explicitly marked inference but must not be promoted to mechanical truth. Removed/corrected outcomes are excluded from active current narratives while prior generated versions remain retained.

## C-NINE and authored lore

Use `data/lore/C-NINE Story - canonical export.txt` and its existing biography matches. Preserve names, contradictions, redactions, and deliberate ambiguity. The runtime uses a frozen export; live Google Doc synchronization is not implemented. Sheet Backstory text is preserved for other fighters and used as voice context; it does not silently replace existing C-NINE canon.

## Highest-priority follow-up work

1. Confirm the Render API key is saved, deploy 0.8.1, then review live model-drafted prose with campaign members and refine voice variety, label lifecycles, and salience choices. Current local environment has no key, so output is explicitly pending and no real provider quality evaluation has occurred.
2. Complete a real phone/mobile visual and interaction check; responsive CSS alone is not evidence of that check.
3. Add a safe SQLite export/backup workflow. The database now survives service restarts and deploys on a persistent disk, but the app does not yet offer an application-consistent backup download or offsite retention.
4. Expand structured campaign inputs where needed: individual battle attendance, XP reasons, named rescue/medical actions, and explicit relationship evidence. Infer only what the sources support.
5. Consider longer-term reflection across several batches and richer relationships only after the writer's behavior is reviewed. The present system has explicit rule/topic retrieval, not embeddings or a learned personality model.

## Development behavior

Read current documents and inspect the existing implementation before continuing. Keep source records/canon intact, version derived changes, run relevant tests, and document material limits. Ask for owner input only when a decision affects desired behavior, canon, credentials/permissions, cost, or irreversible state.
