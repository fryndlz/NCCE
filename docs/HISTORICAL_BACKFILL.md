# NCCE Historical Backfill (one-off, owner-authorized)

**Status:** implementation in draft PR; not an active live feature until merged, deployed, and the optional Google Apps Script file is installed. Normal Writing Exchange remains the default.

## Why this exists

An existing gang may be connected to NCCE after many mechanical events have already been recorded. This creates a finite *historical prose backlog*, not a second way to write newly occurring campaign events.

Only an explicitly authorised historical backfill job may skip individual approval. Ordinary Queue requests still require individual owner approval.

## Isolation architecture

- Existing **Queue** and **Context**: unchanged headers, existing five-in-flight limit, normal `PENDING → WRITING → READY → IMPORTED` flow and normal manual approval.
- **Bulk Jobs**: one row per finite job, scope, counts, status, errors and closure.
- **Bulk Items**: an entire frozen manifest, one immutable request UUID per target. Initially `WAITING` in the Sheet, then `PENDING/WRITING/READY/IMPORTED/HOLD` as released. The bulk writer edits *only these rows*.
- **Bulk Context**: source packet, existing fighter biography, identity/voice layers, source evidence and permissible continuity. Context is written **before** a bulk item becomes `PENDING`.
- **Bulk Audit**: append-only transport attempt/correction log; SQLite is the authoritative ledger.

The new SQLite tables `historical_backfill_jobs` and `historical_backfill_items` are separate from the ordinary `writing_exchange_requests` table.

**Normal importer convergence:** At delivery, the bulk writer's exact accepted text is bridged to a hidden canonical `writing_exchange_requests` row and handed to the existing `exchange_automation.deliver()` validator. That validator retains source checks, immutable target binding, idempotent receipt, original-projection evidence, and source-safe prose-only updates.

The normal queue's `prepare()` and `outbox()` exclude active reserved targets and hidden bulk bridge requests. The bridge cannot create a visible duplicate Queue item. A successful bulk import, however, *is* a normal accepted import from NCCE's point of view, so all existing projection retention continues to work.

## Job creation and snapshot

An owner explicitly creates a job using exact gang names or faction/House selectors. Examples:

- `gang:C-NINE` if that is the exact NCCE roster gang name
- `gang:Kły Sprawiedliwości`
- `house:House Orlock` if that is the stored `gang_type`

The server resolves those selectors to precise **gang IDs** and freezes that finite set. Only already-existing unapproved `fighter_memory` and `fighter_reflection` slots belonging to those gangs are considered. No new events, memories, mechanic observations or roster rows are created. Approved/player-authored entries are excluded.

For each selected slot, the job stores:
- immutable `request_id`, `target_key`, gang/fighter binding and ordering
- original projection and semantic source seal
- frozen base source/identity/voice packet and context fingerprint
- a durable status and later source revision, exact delivered Markdown, error, receipt and import time

Existing normal-Queue claims are recorded as `SKIPPED`, not overwritten. A gang may belong to only one active job. Different gangs may have independent jobs.

The full manifest is visible immediately in **Bulk Items**, even when an entry is `WAITING` for its chronological prerequisites. Releasing packets computes dependency continuity from already accepted predecessors; these accepted texts supplement—but never replace—the frozen source evidence.

## Authoring & automatic approval

An owner may authorize autonomous acceptance **for one finite job**. This is not a property of the writer's style skill, nor a standing authorisation for future Queue items.

Writers must use accepted prose and individual voice guidelines; House Orlock's many approved fighter voices should be consulted, not only *Damaged Freight*. Fighter memories and reflections have a hard 350-character limit **including Markdown**.

A bulk writer saves the complete Markdown in `Bulk Items.writer_text_md` (column L), optionally a note (M), and marks the saved item `READY` (column B). It must re-check exact request ID, source revision, event evidence, status, title and character limit before marking READY. The relay delivers saved text without rewriting it.

A normal five-minute NCCE relay tick performs its normal Queue work **first**, then invokes the optional bulk sync in a protected try/catch. A bulk transport error cannot abort the already-finished normal exchange. No bulk tab exists until the owner explicitly sets it up; jobs do not run merely because the app starts.

NCCE itself never calls a language model. A connected writer/Work execution must process the Bulk Items in batches; the relay handles only delivery, imports and receipts.

## Error handling and correction

| Failure | Behavior |
|---|---|
| Snapshot source or approved source context changes | `HOLD`; original snapshot and exact draft retained |
| Invalid or overlength draft | Rejected before bridge; writer corrects the existing Bulk Items row |
| Conflicting normal request or earlier import | `HOLD`; no target overwritten |
| Failed/ambiguous import | `HOLD`, reason and saved Markdown retained |
| Relay crashes after backend import but before Sheet receipt | Same ID/text may be resent; original receipt returned, no duplicate |
| Historical text imports but user wants editorial revision | Select `IMPORTED` Bulk Items row and use **Revise selected bulk memory**; original remains unchanged and NCCE creates a **new ordinary Queue correction request** under the existing `revision_of`/receipt/text-hash checks. The correction requires manual owner approval |

**Identity invariant:** an imported memory keeps its logical target and existing original import ID; a subsequent correction gets a new request ID. Revision requests never change campaign mechanics and never silently inherit the one-off bulk job's auto-approval.

The job normally closes only when all entries are imported, held or skipped. An explicit **Finalize selected job with errors** owner action may first mark unresolved, unclaimed WAITING items HOLD with preserved reasons; active WRITING claims block forced closure. It closes `COMPLETED` or `COMPLETED_WITH_ERRORS`, which expires its authorisation. Blocked prerequisite items require intervention, not silent acceptance.

## Deployment / rollback

1. Review the GitHub PR and pass both old and new regressions.
2. Back up the NCCE database. Schema 21 is forward-only and does not mutate existing Queue content.
3. Deploy to disposable staging first and create a three-memory job.
4. Test source mismatch, a duplicate delivery, a correct import, normal Queue intake during the job, and a manual revision of an imported bulk item.
5. Only then merge/deploy to production, and add `scripts/writing_exchange/Bulk.gs` to the bound Google Apps Script project alongside the updated `Code.gs`.
6. The new menu creates Bulk tabs and requests an explicit finite job. Leave the hourly ChatGPT fast-track paused.

**Rollback without data loss:** Stop issuing bulk requests; use `cancel` on an active job (this releases its target reservations but never unimports successful entries). Do not delete ledger rows or undo imported prose without an explicit versioned correction. Old Queue relay and its existing source data remain in place.

## Private relay API

Existing `NCCE_EXCHANGE_TOKEN` bearer authentication is required; these endpoints do not respond to ordinary unauthenticated application requests.

| Endpoint | Input | Result |
|---|---|---|
| `bulk/create` | `{owner_authorized:true, gang_ids?:[], gang_names?:[], house_types?:[]}` | Finite gang-ID snapshot and job UUID |
| `bulk/status` | `{job_id}` | Full immutable target manifest and item statuses |
| `bulk/poll` | `{job_id,limit:1..50}` | Prerequisite-safe sealed source packets |
| `bulk/deliver` | `{job_id,request_id,source_revision,status:"READY",writer_text_md,...}` | Canonical import receipt or HOLD |
| `bulk/revise` | `{job_id,request_id,expected_receipt}` | New ordinary Queue revision request |
| `bulk/close` | `{job_id}` | Finite completion, if no pending work |
| `bulk/cancel` | `{job_id}` | Cancel uncompleted reservation without undoing prior imports |

The signed-in application also provides read-only `GET /api/historical-backfill?job_id=...`.

## Limitations to verify before activation

- A historical source correction during a job deliberately requires reconciliation; the writer must not quietly replace the original snapshot.
- The first implementation supports **fighter memories/reflections only**, not gang reports, battle reports, place events or biographies.
- New campaign events after the job's authorization are **not** included in its snapshot. They use the normal Exchange or a new explicitly authorized backfill.
- The job's automatic import depends on the normal NCCE five-minute relay and an external bulk writer. It cannot make ChatGPT write 700 memories unattended by itself.
- A `HOLD` caused by conflicting source data must be resolved before a new job or normal retry can safely import that target. Never delete or recycle IDs to force a retry.
