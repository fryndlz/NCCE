# Story Engine Architecture — implemented in NCCE 0.9

**Schema:** 8. **Current app release:** `0.9.1`, with story generation still `story-0.8.1`. The writer uses OpenAI Responses structured output, rejects malformed prose locally, preserves successful outputs in a persistent cache, and marks quota-limited remaining outputs pending for the next refresh. Hosted generation remains `story-0.8.1`.

The detailed current implementation, constants, and complete catalogs are specified in `CURRENT_DESIGN.md`. This document describes the runtime boundaries and data flow.

## 1. Source boundary

`google_sheets.py` fetches the authoritative campaign workbook as read-only XLSX. `snapshot.py` normalizes current gang, fighter, territory and battle state, including equipment/stat fields and authored Backstory/Notes. Source-ID joins from the MAIN Data Dump are used only when unambiguous; visible workbook values remain authoritative. `campaign_history.py` independently parses the three Munda Manager raw archive tabs; archive evidence never changes the current roster or Sheet.

The app never writes the Sheet. C-NINE authored canon comes from the frozen local export; automatic synchronization of the live Google Doc is outside this release.

## 2. Immutable factual history and current projection

`sync.py` stores deduplicated snapshots and `diff.py` produces deterministic factual event drafts. Events have source/snapshot locators, stable IDs/idempotency keys, subjects with roles, and explicit provenance. Source dates are retained; undated changes have observation time only.

A first-live bridge compares seed fields that actually existed and treats newly exposed stats as baseline rather than invented improvements. `store.py` refreshes current-state projections while retaining fighter history and preserving authored biographies.

Battle identity uses source log IDs when available. A normalized encounter fingerprint and duplicate discriminators are fallback identities. Row numbers locate source cells; they do not define an encounter. Corrections/removals append events and update active projections. Current stories resolve against the active battle and its correction chain.

## 3. Observation and stim interpretation

`story_engine.py` translates meaningful direct fighter changes and bounded shared gang events into observations. Each observation stores:

- a diegetic paragraph drafted by `llm_writer.py` and marked inference, or a visible pending state if no key is configured;
- separate mechanical evidence;
- source event IDs and source authority;
- importance on a 0–10 narrative-salience scale;
- occurrence/observation dates, topic tags, baseline status, and generation version.

The writer supports injury/status, recovery/return, experience, advancement/skills, kills, loadout, role/characteristics, recruitment/unlisting, gang outcomes, territory, reputation/alignment, and shared death/capture news. Shared news is not personal witnessing or proof of deployment. XP alone does not reveal its cause.

## 4. Voice context

Authored backstory and gang conventions constrain the voice. Explicit role/vocabulary hints and mechanical thresholds add explainable profile traits. High Toughness/Strength can inform embodied perspective without proving fearlessness or a particular temperament. The profile and its evidence are inspectable.

Narrative prose is drafted through the OpenAI Responses API when the server key is configured. Source parsing, factual outcomes, salience, IDs and persistence remain deterministic. Generated prose is cached by its structured form/fact/context packet. Missing credentials or provider errors are visible and never silently fall back to the old bounded phrase variants.

## 5. Memory, reflection, and revision

Memory history is chronological rather than a list of current mood badges. Unknown baseline dates remain unknown. Schema-4 `story_memories` keeps current and superseded generated versions, while the immutable factual ledger remains intact.

Reflection is batch-based: at least two observations of importance 4 or above, with combined importance at least 12. Cite up to four highest-salience observations; reflection importance is their mean plus 0.5, capped at 10. Confidence 0.60 is a design constant distinct from factual confidence. Source observation/event IDs and the evidence union remain attached. Deceased fighters receive no new reflections or current thoughts.

Regeneration fingerprints source state, authored context, event IDs and story code/version. An unchanged input is idempotent. Changed semantic narratives create new IDs and deactivate earlier generated versions. Authored lore and mechanical facts are not rewritten by inference.

## 6. Current Mind retrieval

Mind displays up to four supported memories/reflections as current preoccupations. The selection score is:

`0.40 × normalized importance + 0.30 × recency + 0.25 × current relevance + 0.05 × character bias`

Recency has a 14-day half-life; unknown dates and undated baseline entries are penalized. Relevance uses current conditions and role. Voice traits supply explicit topic preferences. Duplicate primary labels and overlapping event evidence are suppressed; closed critical/recovery/captivity concerns yield to the current condition. `history_only` amended social news stays in history but is excluded from Mind. Every thought links to its source memory and exposes component scores.

The complete 28-label mapping and exact rules are in `CURRENT_DESIGN.md`.

## 7. Narrative artifacts

The engine regenerates mechanically inferred fighter/gang/place/region histories, multi-section battle reports, current downtime documents, and repeated-opponent relationship chronicles. Artifacts store semantic blocks, evidence, source links, inference class, generated time, and version. Authored battle Notes remain a separately labeled source record.

Battle reports can use recent roster deltas as accompanying returns only under bounded same-snapshot inference, or an explicit link. Baseline injuries, ambiguous multiple games in one import, unsupported named attacks, and exact unseen action sequences are not presented as facts.

Downtime is event/state-driven fiction between games. There is no simulation of meaningless continuous daily life. Repeated opponents can form a sourced gang relationship chronicle; the system does not yet model individualized social bonds.

## 8. Campaign chronology and presentation

Schema 8 retains Munda Manager activity, documented battles and sessions as raw/versioned archive records. Sessions join battles only by `campaign_battle_id`; unresolved sessions, missing session windows, archive conflicts and parsing issues remain visible. `Created At` and `Updated At` are candidate time-window proxies, not confirmed game start/end facts. Activity classification is per gang and has explicit confidence/ambiguity states. Positive fighter XP increases inside an involved gang's candidate session window may support an inferred participation. XP loss, ally attendance and unsupported deployments remain unknown. `/api/history` serves the derived registry/timeline, and fighter details attach matching fighter-specific entries.

The Chronicle renders a Gantt-style timeline with one lane per gang, separate session spans, campaign activity markers, a battle registry, filters, and expandable original source records. This archive does not currently feed the model writer or change the generated battle reports.

## 9. Presentation and service

The existing HTTP/JSON API separates engine from browser. The browser renders narrative and mechanical evidence distinctly, supports structured/limited rich text, and provides Fighters/Gangs/Places/Battles searching and filtering. The browser is the current client; another client can consume the same factual/narrative API.

Startup, scheduled and manual Sheet refreshes run through the same pipeline. Shared-passphrase hosted access protects campaign APIs. Hosted SQLite now resides on the service's 1 GB persistent disk at `/var/data/ncce-preview.db`, so it survives normal restarts and deployments. The disk is single-instance storage, and an application-consistent SQLite export/offsite backup workflow remains unimplemented.
