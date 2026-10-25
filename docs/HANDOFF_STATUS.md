# Handoff status

**Current source implementation:** NCCE 0.6.1 — Roster visibility and voice correction, SQLite schema 4

**Hosted implementation:** 0.6.0. The 0.6.1 changes are not yet deployed; see the deployment warning in `CHANGELOG.md`.

**Checkpoint:** 2026-10-25 17:32:54 CET (Europe/Warsaw)

**Rollout:** see `CHANGELOG.md` for the application commit, final hosted version, and release verification timestamps.

## Workspace and product

Continue in the existing repository. Use Git for history; do not rebuild the project or produce another versioned ZIP. Source/data authority remains in `AGENTS.md`. The Sheet is read-only, authored lore is canon, and generated narrative is inference with evidence.

The app now implements the principal story loop rather than only refreshing a roster. New campaign facts generate fighter memories, reflections, selected Mind thoughts, and regenerated reports. The runtime is local deterministic code with no external language-model dependency or generation fee. Bounded phrasing and explicit topic matching remain visible limits.

The exact current technical design, all module responsibilities, current label catalog, trigger/importance rules, voice thresholds, reflection algorithm, Mind formula, and data limitations are in `docs/CURRENT_DESIGN.md`. The earlier design critique is archived as `docs/archive/DESIGN_REVIEW_2026-10-25.md`; `docs/IMPLEMENTATION_AUDIT.md` describes the earlier build and should not be mistaken for the v0.6 implementation state.

## Implemented milestones

| Area | Current status |
| --- | --- |
| Hosted link and invite access | Existing free Render preview at https://ncce-private-preview.onrender.com/. Public GitHub source; campaign app protected by a shared passphrase. Deployed release evidence is recorded in `CHANGELOG.md`. |
| Chronicle-first navigation | Implemented. Story/history leads; raw mechanical state is inspectable evidence. People is now Fighters. |
| Durable factual/event/provenance schema | Implemented. Sources, entities, immutable snapshots/events, subjects/roles, evidence links, and correction chains. Schema 4 adds versioned story memories/artifacts. |
| Read-only Sheet sync | Implemented. Startup, 15-minute schedule, and manual refresh; source-state projection and narrative refresh follow successful reads. |
| Snapshot comparison and change tracker | Implemented. Known baseline fields can bridge to the first live read without fabricating new-stat deltas. Unknown occurrence dates stay unknown. |
| Event-to-memory/reflection/Mind | Implemented. Voiced observations and sourced reflections; documented salience/thresholds; current thoughts selected by importance, recency, relevance, and character biases. |
| Generated histories and reports | Regenerated fighter/gang/place/region histories, battle reports, downtime, and repeated-opponent relationship chronicle. Authored biographies and C-NINE canon preserved. |
| Battle correctness | Stable source IDs/fallback identities, row reorder safety, duplicate handling, current report facts, corrections/removals, and bounded inferred association of recent roster deltas. |
| Presentation and filtering | Structured prose plus visually separate evidence, safe limited emphasis, source links, current Mind traceability, search/filter controls, and responsive CSS. Desktop inspected; mobile visual verification not completed. |
| Validation | 0.6.0 had 29 deterministic checks and a disposable authenticated HTTP/live-sync smoke check. 0.6.1 adds targeted voice-leak tests and is revalidated locally; hosted release `0.6.0` remains live. See `CHANGELOG.md`. |

## Historical limits

Pre-baseline XP, kills, injuries and advancements are known states, not a dated sequence of events. A later snapshot capture time says when NCCE observed a change, not when the tabletop event occurred. A fighter disappearing from a roster is not automatically dead or retired.

Battle records identify gangs and outcomes. Individual attendance, exact reasons for XP, named injury-causing enemies, rescue participants, and detailed in-battle actions are not consistently recorded. Same-update context may support an explicitly marked inference but must not be promoted to mechanical truth. Removed/corrected outcomes are excluded from active current narratives while prior generated versions remain retained.

## C-NINE and authored lore

Use `data/lore/C-NINE Story - canonical export.txt` and its existing biography matches. Preserve names, contradictions, redactions, and deliberate ambiguity. The runtime uses a frozen export; live Google Doc synchronization is not implemented. Sheet Backstory text is preserved for other fighters and used as voice context; it does not silently replace existing C-NINE canon.

## Highest-priority follow-up work

1. Review the deployed 0.6 story loop with campaign members and refine voice variety, label lifecycles, and salience choices using actual examples. The writer currently uses bounded deterministic variants.
2. Complete a real phone/mobile visual and interaction check; responsive CSS alone is not evidence of that check.
3. Preserve campaign history beyond free-host restarts. The current free preview's filesystem is ephemeral. Any paid storage or service remains an explicit owner cost decision; no paid resource was created here.
4. Expand structured campaign inputs where needed: individual battle attendance, XP reasons, named rescue/medical actions, and explicit relationship evidence. Infer only what the sources support.
5. Consider longer-term reflection across several batches and richer relationships only after the current model's behavior is reviewed. The present system has explicit rule/topic retrieval, not embeddings or a learned personality model.

## Development behavior

Read current documents and inspect the existing implementation before continuing. Keep source records/canon intact, version derived changes, run relevant tests, and document material limits. Ask for owner input only when a decision affects desired behavior, canon, credentials/permissions, cost, or irreversible state.
