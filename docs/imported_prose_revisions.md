# Revising imported NCCE prose

The exchange is append-only for **requests and receipts**, but a corrected approved
version can replace the **same logical prose slot** after separate owner approval.

## Installation

1. Deploy the version of NCCE containing SQLite schema **19**. The existing
   pre-upgrade database backup is created automatically before migration.
2. Update the **bound Apps Script** for the Writing Exchange spreadsheet from
   `scripts/writing_exchange/Code.gs` (merge other custom script files; do not
   overwrite unrelated code). Authorize its original Sheets/URL Fetch scopes
   if Google prompts you.
3. Verify the existing five-minute relay and a normal import round trip.

GitHub updates to `Code.gs` **do not automatically update the Google Apps Script
project**. Do not try to create a revision from the Sheet before both components
are installed. The server endpoint requires the existing private relay bearer
token and cannot be invoked from an unauthenticated browser.

## Owner workflow

1. In the Writing Exchange spreadsheet, select the original **IMPORTED** row
   (the original receipt must be present).
2. Choose **NCCE relay → Revise selected IMPORTED entry**; confirm the prompt.
3. The server checks the original imported receipt, verifies that it is the
   latest accepted version for that logical target, checks source identity and
   the exact current prose, then creates a **new sealed PENDING request**.
4. The relay's normal Sync appends the new row and its frozen Context. The
   original IMPORTED row and receipt remain unchanged.
5. Writer reads that new PENDING request's Context, including
   `revision_baseline`. It claims WRITING, revises the text, and leaves it
   WRITING. Existing normal editorial approval and memory-generation metadata
   obligations still apply. The user approves the **exact** new prose.
6. Mark **only the new correction row** READY. The relay delivers it using
   the standard authenticated endpoint. The server verifies the previous
   accepted receipt, full original text hash, current target and source seal,
   and rejects if another edit/revision intervened.
7. The server updates only the original logical prose target, records the new
   request and receipt in the audit, and the relay marks the new row IMPORTED.
8. To revise again, start from the **latest** imported correction row, never
   from the oldest receipt.

## Safety invariants

- **No duplicate narrative slot:** correction updates the original target
  `story_memories`, `fighter_thoughts`, `story_artifacts`, or
  `narrative_entries`; it does not add a second story record.
- **Immutable audit:** previous imported request text and receipt are retained.
  Each revision has its own UUID, source revision, parent request, base receipt,
  text fingerprint, approval and import receipt.
- **Optimistic concurrency:** stale parent receipt, changed text, authored
  provenance, ambiguous target, or changed underlying mechanical evidence
  fails closed. Rejections preserve the draft as HOLD, with an error.
- **Rebuild persistence:** `restore()` reapplies the imported chain in
  insertion order, leaving the latest accepted version displayed.
- **No automatic regeneration:** an error never silently manufactures new
  writing or reopens old IMPORTED rows.
- **Character caps:** corrected `fighter_memory` ≤350 and corrected
  `fighter_biography` ≤2300, counting all Markdown and newline characters.
- **Scope:** this does not revise the source campaign mechanics, owner-authored
  canon, roster classification, or imported legacy pilot entries outside the
  current `writing_exchange_requests` audit.

## Recovery

If a correction is HOLD, **do not edit its request ID, source revision,
import receipt, or the original IMPORTED row**. Read the error and reconcile
the conflicting source/prose change. If the latest imported receipt is missing
or the active prose differs, the server will not create a correction request.
The audit and unchanged original remain the recovery anchor.

If the relay server is updated but the Apps Script has not been updated,
ordinary imports continue to function; the revision menu simply will not be
available yet.

## Validation

CI runs the exchange end-to-end tests, multiple successive corrections,
original-slot identity, biography correction, failed compare-and-swap,
import receipt replay, rebuild/restart retention, source protection,
writing-waterfall tests and JavaScript parse checks. Before a production
rollout, verify an authenticated Sheet → server → Sheet correction on a
noncritical imported entry and compare the visible NCCE record before and
after a live refresh.
