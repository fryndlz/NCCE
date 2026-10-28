# Fighter-relevant event clock — NCCE 0.17.0

## Approved design

Owner decisions: relevance/resolution with **no fixed expiry**; **10 subsequent relevant events per recency half-life**; **each distinct meaningful change is one step**. No wall-clock cognitive decay and no recency reinforcement just for opening a dossier. These rules supersede 0.16.0's calendar half-life and 7/14/28-day expiry.

Implementation: `src/fighter_event_clock.py`, `story_engine.select_mind`, `fighter_mind.py`. Schema remains 15; logical time is derived from persistent factual causes rather than a new mutable timer. Dates remain source evidence, ordering keys, UI metadata and operational/audit timestamps. Runtime refresh/auth/reviewer timeouts still use ordinary time; psychological salience does not.

## What advances the clock

For one fighter, collect the unique factual event identities supporting that fighter's current-version, nonbaseline **observation** memories. This includes meaningful historical experiences even when a concern is marked `history_only` or later resolves. It includes supported direct changes and the shared gang news the story engine actually supplies. It excludes other fighters' private experiences, unrelated gangs' events and unsupported bookkeeping. Supported categories and importance rules are listed in CURRENT_DESIGN.md.

An injury, XP change and shared battle result are three distinct changes, even if observed in one import. Two observations citing the same underlying event count once. A reflection or thought citing three changes does not add a fourth. App reads, unchanged syncs, provider calls, regenerated prose/IDs and writing-policy edits add no steps. Resolved experiences remain history, not erased mental time.

Correction identity follows `campaign_events.supersedes_event_id` to the original root. A corrected result replaces the same experience; it is not another battle or clock tick. An invalid correction cycle has a deterministic root. Source data is never rewritten. Correcting/removing an erroneous fact or backfilling historical chronology may rebuild positions/distances; this is a factual repair, not elapsed time or a new fictional experience.

Coverage is explicitly limited to available supported observation causes. The separate MUNDA archive is not yet wholly converted into fighter observations. This feature cannot recover unseen pre-baseline changes or establish attendance. Shared results are shared knowledge, not proof of witnessing.

## Ordering and formation

1. Use a supported occurrence timestamp where known; otherwise use the original event's first observation timestamp. A correction's later import time cannot refresh the original unknown-time event.
2. Dates order events only; never subtract them to compute psychological age. Missing/tied order falls back to a stable canonical event ID. The tie-break is bookkeeping, not an assertion of causal ordering.
3. Assign each distinct relevant fact a position from 1 to N. Baseline is position 0.
4. Observation formation is its causal event position. A reflection is anchored to the latest cited causal observation/event; current-thought causes use the same anchor. Writing a retrospective interpretation later does not move its simulated formation to the API request date. Derived mental entries add no independent factual clock steps.
5. Read `distance = N - formation_position`. Regeneration does not reset formation. A fighter's clock is independent of another fighter's.

Examples: with A, B, C at positions 1, 2, 3, A has distance 2 and C distance 0. If nothing happens for ten years, these distances remain unchanged. If ten more fighter-relevant changes follow C, C's distance becomes 10. A reflection citing A and C anchors at 3 without creating position 4. Duplicate imports of C and a correction of C do not create position 4 either.

## Retrieval formula

`recency = 2 ** (-subsequent_relevant_events / 10)`

`score = 0.40*(importance/10) + 0.30*recency + 0.25*relevance + 0.05*character_bias`

| Subsequent relevant changes | Recency term |
| --- | --- |
| 0 | 1.0 |
| 10 | 0.5 |
| 20 | 0.25 |

Importance remains fixed rule-based narrative salience; relevance/current-condition filtering and profile preferences remain separate. Unknown baseline dates no longer receive a fabricated 180-day age or a calendar penalty. Baseline position is zero, and baseline/unanchored causes are still excluded from current-thought drafting.

The `at` compatibility argument in retrieval/thought helpers has no cognitive effect. API request time cannot change scores, candidates or the displayed Mind. There is no fixed expiry count, minimum-score deletion or event-based equivalent of the former day limits. An old important concern may still rank highly if relevant.

## Thought lifecycle and costs

Current thought prose remains separate from memories. At most four candidates survive ranking, evidence/label deduplication and one-per-family selection. Battle/equipment families use their newest eligible **event position**, not elapsed age. Current conditions resolve through supported status/effect changes or death. Losing selection for relevance/identity/context is `superseded`, rather than claiming the underlying condition was cured. A relevant stored ready thought can reappear without another model call.

Legacy `expires_at` columns/old values are ignored; active refresh clears them. The old `expired` historical rows remain audit history and may be reactivated when their supported cause is eligible. No stored paid prose is deleted. Current candidate context carries `fixed_expiry=false` and event-clock metadata instead of time-to-live. Exact original paid requests remain unchanged in the request audit; current source packets are not represented as immutable copies of those old requests.

Ordinary automatic writing remains paused. New/changed source context may create pending thoughts but makes no paid call. No full-roster regeneration, policy activation, model training or authoritative campaign edit is part of this release.

## API, Workshop and agent contract

Fighter API: `event_clock` reports basis/version/head/half-life. Each observation/reflection exposes formation position, subsequent relevant events and recency. Current thoughts expose the same clock plus score details. `mind_policy` says `recency_basis=fighter_relevant_events`, `recency_half_life_events=10`, `fixed_expiry=false`; the former day-based policy fields are removed. The existing “Why this is on their mind” view displays the integer event-distance fields alongside the other scores.

JuniorWriter's common instructions and fighter packets describe the approved chronology. JKSimmons review jobs and StoryTechMan intervention jobs receive the versioned structured `cognitive_design` policy, also available in source packets. Their role documents point to the current design. This guarantees delivery on future jobs, not persistent-chat acknowledgement, and starts no agent/model work merely to announce a release.

Workshop source samples use current stored cause/context packets before shared literary planning. Event metadata is refreshed on campaign refresh; exact originally paid prompts remain in the request audit. Generation environment fingerprints include the event clock, thought lifecycle and story engine, so an old category study cannot silently continue across a cognition change. Owner revisions/active pointers are not changed.

## North star and deliberate adaptations

Reference: Park et al., [Generative Agents: Interactive Simulacra of Human Behavior](../../generative-agents.pdf), §4.1–4.3, PDF pp.8–11. This is a source comparison, not a claim of complete paper compliance.

| Paper mechanism | NCCE implementation / gap |
| --- | --- |
| Persistent observations and retrieved reflections | Persistent sourced/versioned observations, cited reflections and separate current thoughts. |
| Recency since last retrieval, decaying over simulated game hours | **Owner-approved adaptation:** distance from causal formation measured in subsequent fighter-relevant facts. Access does not reinforce recency. |
| Importance rated by a model | Rule-based 0–10 salience, not an extra model request. |
| Query-conditioned embedding similarity | Current condition/topic/profile rules; semantic-query retrieval is not implemented. |
| Weighted recency/importance/relevance | Implemented with documented 0.30/0.40/0.25 weights and 0.05 character bias, not the paper's equal weights/min-max scaling. |
| Recursive reflections, retrieved questions, cross-time synthesis | Current reflection remains batch-based, threshold 12, at most four cited observations. Recursive/cross-batch reflection is not implemented. |
| Stored hierarchical plans and reactive actions/dialogue | Not implemented. NCCE intentionally progresses on campaign events, not simulated breakfasts/daily schedules. Literary planning is a different module. |
| Separate short moodlets with fixed lifetime | Not prescribed by the paper. NCCE supplies its own short current-thought presentation; no fixed lifetime remains. |

## Executable verification map

| Contract | Regression |
| --- | --- |
| Exactly 10 subsequent facts halve recency; request date irrelevant | `test_ten_subsequent_relevant_changes_halve_recency` |
| Duplicates, rewrites, reflections/thoughts, baseline and other fighters do not tick | `test_reimports_rewrites_derived_thoughts_and_foreign_events_do_not_tick` |
| Distinct changes within one import count separately; stable ordering | `test_individual_changes_count_even_when_imported_together` |
| Reflection formation derives from citations, not prose timestamp | `test_reflection_formation_is_latest_cited_cause_not_generation_time` |
| Corrections resolve to one identity; unrelated ledger rows do not tick | `test_corrections_are_one_underlying_event_and_unrelated_ledger_rows_do_not_tick` |
| Malformed correction cycles retain a stable identity in either input order | `test_malformed_correction_cycle_is_order_independent` |
| No calendar expiry; new fact changes distance without forcing prose rewrite | `test_no_fixed_expiry_and_clock_advances_only_with_another_relevant_fact` |
| Writer, reviewer and technical intervention jobs receive the same policy | `test_three_roles_receive_the_same_versioned_cognitive_policy` |
| Independent prose/persistence/ready-only display and condition resolution | `tests/test_fighter_mind.py` |
| Actual authenticated application/Workshop packets and event policy | `tests/smoke_server.py`, Workshop/bridge HTTP and unit suites |

Release/source verification belongs in CHANGELOG.md and HANDOFF_STATUS.md. A mocked model proves mechanics and transport, not literary quality. Future design changes must update both this contract and its executable checks.
