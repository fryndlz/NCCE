# Actual Codex reviewer connection

**Current design (2026-10-28): event-driven native chat.** The five-minute model-check automation is PAUSED. `scripts/codex_event_listener.py` waits on the narrow authenticated `events` endpoint with ordinary HTTPS long-polling. Empty waits make no Codex CLI/model calls. When NCCE queues a review after generating a draft pair, the listener sends exactly one trusted job-ID notification using the installed CLI's documented `codex queue --thread ... --message ...`. A real CLI delivery to the existing desktop chat was verified before implementation. JKSimmons claims only that job, reviews with its actual conversation and saved standards, returns its assessment, then ends. See [CODEX_CHAT_REVIEWER.md](CODEX_CHAT_REVIEWER.md).

Private notification journals are written BEFORE invoking the queue command, so duplicate events, process restarts and uncertain CLI responses never automatically dispatch another turn. A failed/uncertain listener stops and marks the connection unavailable for human investigation. Credentials/leases are never passed in CLI arguments or printed. This is a hidden local process launched by `C:\Codex\NCCE\START JKSIMMONS.vbs`; no login task or system service is installed. Keep this computer, the listener and Codex open. The listener's fresh heartbeat preserves the existing pre-spending connection gate; it does not authorize writing calls or activate policies. Event waits release the shared database lock between reads so owner requests and review callbacks remain available. No external reviewer API fallback exists.

The sections below describe earlier designs and verification history; their five-minute schedule and old launcher instructions are superseded by the event listener above.

**Current transport: native reviewer chat (verified 2026-10-27).** The failed independent stdio design below is retained as history. The existing desktop-owned chat now runs the queue helper itself; it does not try to resume its thread in another process. Follow [CODEX_CHAT_REVIEWER.md](CODEX_CHAT_REVIEWER.md). An ACTIVE heartbeat automation targets this exact chat every five minutes and applies the current conversation plus private owner standards. Unlike the former companion's idle network polling, native scheduled checks consume Codex usage even when the queue is empty. Keep the computer and Codex open. The old START JKSIMMONS.vbs now explains this change instead of launching the conflicting companion.

Live native diagnostic: `connection-check-7f8e01fec4ee0c3a3342-b30181225109`, completed by actual thread `01a17f57-f5bb-7782-bce0-8b3b43dd367f`, native turn `01a17f8e-9202-7d20-a4ca-ae62f477947a`. Server-accepted scores: 7.5 and 1. No JuniorWriter calls or policy activation. A new explicit diagnostic attempt preserves the old failed record; queued/running/completed checks cannot silently be retried. Native heartbeat TTL is the declared five-minute poll interval plus one minute; the independent transport keeps its shorter TTL. Transport credentials/leases stay private in the helper, and results remain lease-bound and immutable.

## Earlier independent stdio prototype

NCCE 0.14.0 replaces the optimizer's external reviewer API call with a scoped queue for the existing **JKSimmons — NCCE Writing Reviewer** Codex chat (`01a17f57-f5bb-7782-bce0-8b3b43dd367f`). JuniorWriter still uses the existing writing provider. There is no reviewer API fallback.

## Transport and context

A local Python companion polls authenticated review endpoints on the hosted NCCE app. Idle polling makes no model turns. When a review job exists, it uses the installed Codex CLI's documented stdio app-server transport, resumes the actual saved chat, and starts a structured-output review turn. It preserves the chat's model settings; no model override or external provider key is supplied. The packet includes exact prompts/context, both drafts, preceding reviews, the rubric and current private reviewer guidance/feedback. The persistent Codex conversation contributes the owner's corrections and prior discussion.

The companion creates a fresh transport for each job so it reads the current saved conversation. It refuses a review if the last saved turn is still active. Avoid sending a simultaneous manual turn while the reviewer head is working; the local read/start boundary cannot atomically lock a separate desktop client. Human input/tool-approval requests, quotas, interrupted turns, malformed reviews or lost transport pause the job rather than retrying the model.

This uses Codex account usage. It is not local model inference and does not bypass Codex limits.

## Narrow credentials and lifecycle

The private token authenticates only heartbeat, job claim, actual-turn start, completion/failure and a single synthetic connection check. It cannot activate policies, modify canon, run arbitrary commands, or obtain a general owner session. It is stored outside Git in `C:\Codex\NCCE\.codex-review-bridge\config.json`, protected for the owner and SYSTEM, and presented only over HTTPS. Render stores only its SHA-256 verifier in `NCCE_REVIEW_BRIDGE_TOKEN_SHA256`; the verifier is not itself accepted as a credential. The random token has 48 bytes of entropy and is never printed or passed through tool output. The verifier is merged into the service environment without replacing existing secrets. `NCCE_CODEX_REVIEWER_THREAD_ID` binds jobs to the intended chat.

Schema 14 adds `codex_review_bridge` and `codex_review_jobs`. A job receives a random lease. Results must match the worker, lease and recorded Codex turn. Accepted results are immutable/idempotent and retain thread/turn identities. Claimed/uncertain jobs are never automatically re-leased. A local journal is persisted before dispatch so a crash cannot silently replay a review. The connection-check fixture can be queued once per thread and makes no JuniorWriter requests or policy changes.

The optimizer runs on its own database connection while waiting. This lets completion and stop requests reach the server without a long-held shared-store lock. Cancelling a run cancels its queued/active review; the companion observes cancellation and requests a Codex interrupt. A restart cancels unfinished jobs for human investigation. Offline companions block new spending at run creation; an offline bridge during a run pauses it after a grace period. There is no silent fallthrough to the former API reviewer.

## Running locally

Double-click `C:\Codex\NCCE\START JKSIMMONS.vbs`. It starts the companion without a terminal. Keep this computer on while review jobs are pending. The Workshop shows the last heartbeat and offers **Check Codex connection**. A single-instance file lock prevents duplicate local companions; this is not an installed system service or an unrequested login/startup task.

Do not commit the private config, journals, logs or reviewer feedback. Logs omit tokens, prompts, drafts and model responses. Only new authorized jobs start Codex turns; opening the Workshop, polling and idle heartbeats do not.

## Presentation stays separate

The stern, theatrical critic, anxious JuniorWriter and Mechanicus supervisor are optional presentation skins. Heads switch between neutral, working, talking, angry, sad and pleased expressions according to persisted activity and reviewed results. The working light appears only after the actual Codex turn is acknowledged. Waiting for transport is shown separately. Team handoffs show actual phase events; banter is labelled presentation-only and can be disabled. These renderers do not mutate scores, call budgets, writer instructions or approval rules. The reviewer's private PERSONA.md likewise requires clear factual grading independent of its conversational voice.

## Verification

Offline checks cover scoped authentication, wrong thread/lease denial, real-turn identity, immutable completion, waiting versus working states, cancellation, no replay, changed guidance, no API fallback, and presentation immutability. A synthetic connection check should be verified against the actual Codex chat before claiming that the live queue is connected. It validates transport and structured assessment only, not literary calibration or broad quality consistency.

## Live verification result — 2026-10-27

Deployment `dep-dbgi931srm7s73ek5geg` is live from `4ef4842`; health reports 0.14.0. Startup verified `/var/data/pre-schema-13-to-14-20261027T222452866071Z.db`. The authenticated Workshop displays the three new portraits, optional banter and graph.

The one-time diagnostic `connection-check-7f8e01fec4ee0c3a3342` FAILED before any model turn: `thread/resume` returned “already has an active writer” because the desktop app owns the actual reviewer chat. Desktop status was idle; idle does not release server ownership. Its process uses stdio, and the documented daemon proxy could not reach a managed daemon. Do not bypass the lock, kill the desktop process, archive the chat, silently fork another reviewer or advertise this as connected. A supported shared transport or a different owner-approved interaction design is still required.

Readiness now requires a completed actual-thread diagnostic in addition to a fresh heartbeat. The UI exposes the bounded diagnostic error and disables automatic improvement while it is unresolved. The diagnostic is not automatically retried. No JuniorWriter call or Codex model review occurred, and no production guidance was activated. The existing manual Writer Workshop remains available.

## Event transport live verification — 2026-10-28

Source `9a77762`, deployment `dep-dbgiul7lk1mc73c1sm40`, app 0.14.1. The listener remained active with an empty queue and the native chat retained turn `01a17f9d-a7ef-76f3-bf6d-7d2dccc7784d`; no idle model turn was created. A new explicitly authorized synthetic diagnostic `connection-check-7f8e01fec4ee0c3a3342-85a2d30190aa` then triggered a single journaled `codex queue` notification. The actual reviewer chat processed only that job in native turn `01a17fa2-d816-7f61-aaee-a07d7a971215`; NCCE accepted its validated result, scores 7.5 and 1. This repeated fixture verifies transport, not fresh literary calibration. Zero JuniorWriter calls and no policy activation/canon edits. The five-minute automation remains PAUSED. Authenticated hosted Workshop displays the connected state and the event-driven usage explanation. The listener is already running as a hidden process; the user can restart it with START JKSIMMONS.vbs after reboot. No startup service was installed.
