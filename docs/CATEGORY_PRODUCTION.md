# Category population and automatic writing

Owner decisions recorded 3 November 2026. These are requirements for the unfinished production feature, not a claim that it is deployed.

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

The 31 October recovery showed a delivery limitation: a CLI-queued message waited until the unloaded JKSimmons chat was opened. Production readiness requires an honest delivery status and a dependable wake-up/recovery path; `sent` alone is not proof that a native reviewer turn started.
