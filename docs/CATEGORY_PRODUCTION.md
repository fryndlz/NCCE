# Category population and automatic writing

Owner decisions recorded 3 November 2026. Implemented in the development branch; live verification is tracked in HANDOFF_STATUS.md.

## Two independent controls

- **Populate category** is an explicitly authorized one-off backlog action. It does not enable ongoing generation or change the automatic-writing toggle.
- **Automatically populate new entries** is a separate, persisted on/off toggle per category. Enabling it authorizes event-driven processing of newly eligible records after successful campaign sync. Disabling it prevents further requests from starting; an already in-flight request may complete and its result must remain saved.
- Neither control should silently replace authored or existing finished writing. A relevant source correction is distinct from a new entry and requires its own explicit handling.

## Bounded reviewer-guided rewrites while automatic writing is on

The owner explicitly permits JKSimmons to request entry-level JuniorWriter rewrites during automatic production when the prose is below the category's quality target. This is separate from Workshop category-prompt experiments.

- Maximum **five total writer attempts per entry**, counting the initial draft. This is the implementation interpretation of the owner's five-attempt safety net; it is not five rewrites after the initial draft.
- JKSimmons reviews the initial draft and each subsequent draft. Stop early when a valid draft meets the quality target; otherwise supply concrete reviewer feedback for the next attempt.
- After attempt five has been reviewed, publish the highest-rated valid draft across the entry's attempts and finish that entry. Mark a below-target fallback honestly; never imply that it passed the quality target. On an equal score, retain the earlier valid candidate to make selection deterministic.
- The attempt ceiling is durable across queue deliveries, restarts, toggle cycles and reconnects. No duplicate delivery, source re-check or reviewer instruction can reset it. A review is not another writer attempt.
- Validate factual fidelity, required format and source authority before a draft is eligible for fallback publication. If no draft is valid, preserve any existing prose, leave the record pending and surface the failure.
- Context defects, permission needs, provider/credit errors and uncertain in-flight requests do not become literary rewrite loops. Stop and surface the specific problem; retain drafts, scores, request audit and spending history. No uncertain request is automatically replayed.
- The owner has not yet specified whether the one-off Populate category action should also use the five-attempt reviewer loop. The permission above explicitly applies while automatic writing is enabled; do not silently give the one-off action a five-call-per-entry allowance.
- Show the attempt count, reviewer status, best candidate and reason for stopping in the app. Separate the five-attempt ceiling from the category's overall authorized spending allowance.

## Existing listener

The local `codex_event_listener.py` already forwards actual queued jobs to the dedicated JKSimmons and StoryTechMan chats. It is a transport, not the per-category automatic-writing policy. Reuse it where appropriate, retaining job identity and no-idle-model-call behavior; do not re-enable the old five-minute model automation.

The 31 October recovery showed a delivery limitation: a CLI-queued message waited until the unloaded JKSimmons chat was opened. The production panel distinguishes queued/claimed/reviewing and links directly to JKSimmons to release a pending message; `sent` alone is not proof that a native reviewer turn started. Keep the connected desktop running and the reviewer chat loaded while listening. This is not a cloud-only reviewer service. Empty listener waits make no model calls.

## Implementation and operation

The Workshop has one category selector, a free backlog preview, a bounded one-off action, a separate automatic-writing checkbox and explicit writing-allowance grants. Listening starts off for every category. Enabling baselines existing records; those remain the responsibility of Populate category. Remaining allowance persists across toggles and restarts and never replenishes automatically. Each draft consumes one conservative authorized call slot, including a cached result or an uncertain request; no token-price estimate is represented as a spending guarantee. Codex reviews additionally consume the owner's Codex allowance.

Production jobs use stable subject/event identity, not regenerated artifact row IDs. Successful campaign sync discovers new eligible records. A writer worker handles bounded generation/publication stages under the existing global pipeline lock, then releases it while waiting for the native review. Review completion, explicit owner decisions and connection heartbeats kick already queued work; there is no model timer or model call on page access. Confirmed source changes or failed/uncertain requests halt that entry with its draft/assessment audit intact. The app provides the StoryTechMan chat link for investigation; it does not silently authorize a repair or deployment.

The policy pins shared/category instructions at first enablement. Retrieval and creative planning use the shared NCCE pipeline; each entry freezes its packet across rewrites. This implementation intentionally does not overwrite previously completed or authored prose, invent new event records, reset attempts when toggled, or silently re-review an uncertain native claim. The one-off action uses at most one writer call per pending entry and explicitly discloses that it does not add reviewer calls.

## Territory categories on the frontend and scene creation

Places have separate Description, History, Events, Scenes and Battles tabs. Description uses the place origin; History exposes the chronological history directly, including a clear pending state if unwritten. Events contain generated accounts of recorded changes. Scenes contain only connective fiction and are explicitly labelled as invented, with no tabletop effects. Scene prose never becomes a mechanical ledger event.

For the one-off Territory scenes action, a read-only preview offers one missing baseline scene per active territory that has no active scene. Only confirmation creates the pending scene slots; one writer call per authorized slot uses the shared context pipeline. Existing scenes remain preserved.

For scene listening, enablement baselines current factual territory entries. After a successful sync, each newly recorded territory entry can create one pending scene, keyed by stable territory/entry identity; corrections to an existing version and quiet repeated refreshes do not produce another scene. Scene slots are created without provider calls, then use the same bounded native-review production queue and five-draft ceiling. Disabling/re-enabling does not backfill events that appeared while off. Existing policies receive an initial trigger baseline at upgrade, preventing unintended historical backfill. The old weekly automatic ambient-generation path is retired from campaign regeneration; listening does not require the general automatic-writer flag.
