# NCCE Writing Exchange — quick user manual

**Applies to:** the private **NCCE Writing Exchange** Google Sheet and NCCE. This is not the mechanical campaign source spreadsheet. NCCE never writes rules, fighter stats, injuries or campaign outcomes via this prose pipeline.

## The short version

1. **Queue** is the normal writing inbox. Work is published only after it is saved as **READY** and the five-minute relay successfully imports it.
2. **Bulk Jobs / Bulk Items** are for a *finite, one-off* historical catch-up (for example, an existing gang that already has many recorded events).
3. **Editorial QA** lists the quality check for imported entries, the specific rule failure and the desired correction path.
4. **Editorial Drafts** holds proposed replacement text and approval state. A draft there is **not yet published**.
5. **Memory metadata** keeps source evidence, fighter identity, length and an immutable original snapshot for memories.
6. **Bulk Audit** is the event log of import and revision operations.

### A normal new story entry

NCCE exports an evidence-sealed request → the writer edits the **Queue** entry → **WRITING** → owner checks exact text → **READY** → the relay imports it → **IMPORTED** (receipt in column P).

The relay checks the exact target, source revision and original text; prose cannot legitimately invent a new event or change the mechanical game state.

### A historical backfill

Open **Historical backfill** → **Create one-off backfill** and select the gang scope. NCCE creates a finite manifest in **Bulk Items** with dependencies. The writer fills items as they become **PENDING**, sets **READY**, and the relay imports them. **Bulk Jobs** shows the aggregate state.

**COMPLETED_WITH_ERRORS** does not necessarily mean a missing story. A **SKIPPED** entry may be a duplicate already imported via the normal Queue. Check the reason/receipt before trying to fix it.

### An editorial correction — the normal path

1. Open **Editorial QA**. Its **Correction path** (column J) must say **REVISION_REQUIRED** for a known imported-prose problem. A metadata-only problem does not automatically require rewriting prose.
2. From the top spreadsheet menu choose **Historical backfill → Create corrections for all failed QA entries**.
3. Read the confirmation. The command only selects failed rows without a linked correction request; it verifies the original ID, form and import receipt against **Bulk Items**. It will not process more than 100 entries or combine different historical jobs.
4. Click **Yes**. NCCE returns per-entry **created / reused / blocked** results. New correction request IDs appear in **Editorial QA**, column M. **Bulk Audit** records the request creation.
5. The standard relay makes those new requests available in **Queue**. The writer compares each request's evidence, original text and proposed draft in **Editorial Drafts**, then saves a compliant version with correct provenance.
6. Owner reviews **the exact new text**. Only then should the corresponding Queue request change **WRITING → READY**. **READY is publication permission**.
7. After relay import, confirm **IMPORTED** and the new receipt in Queue. Update the corresponding QA/Drafts tracking. The original entry remains in the audit history.

The command can be run again. Linked items are skipped, and the backend stores idempotency markers for already-created revisions. It **does not** generate prose, automatically accept suggested drafts, or rewrite existing imported entries.

**Single correction:** select an imported row in **Bulk Items** and use **Historical backfill → Revise selected bulk memory**. For an imported row in the normal **Queue**, use **NCCE relay → Revise selected IMPORTED entry**.

## Status reference

| Status | Meaning | What to do |
| --- | --- | --- |
| **DRAFT** | Reserved placeholder / deferred publication; not necessarily a prose draft | Usually leave to relay |
| **WAITING** | Historical item has unmet prerequisites | Check prior imports / HOLD |
| **PENDING** | Available writing task | Claim and write |
| **WRITING** | Saved draft or claimed task under review | Edit or await owner |
| **READY** | Exact text is authorized for import | Let relay deliver; do not edit mid-delivery |
| **IMPORTED** | Accepted and receipted by NCCE | Leave unchanged; revise by new request |
| **HOLD** | Evidence conflict, rejected draft or manual decision needed | Read error; reconcile, never force READY |
| **SKIPPED** | Excluded from a bulk manifest, often a normal Queue duplicate | Inspect reason and original import |
| **COMPLETED_WITH_ERRORS** | Finite bulk job closed with one or more HOLD/SKIPPED | Inspect item-level reasons; not a running job |

## Which button does what?

- **NCCE relay → Sync now:** runs a single transfer to/from NCCE. No writing model is invoked.
- **NCCE relay → Install 5-minute relay:** enables the small technical transport trigger. It **is not** an hourly story-writing automation.
- **NCCE relay → Stop relay:** disables the transfer trigger (stories will stop importing automatically).
- **Historical backfill → Create one-off backfill:** starts a finite *historical* source manifest for selected gangs.
- **Historical backfill → Create corrections for all failed QA entries:** creates versioned **PENDING** correction requests for audited, failed and not-yet-linked imported bulk entries.
- **Historical backfill → Revise selected bulk memory:** one imported historical entry.
- **Historical backfill → Finalize selected job with errors:** explicit early closure; does not fix held material.

## Troubleshooting

- **No new failed entries:** QA has no unlinked `REVISION_REQUIRED` imported rows; this is not necessarily a problem.
- **No menu item:** the Google Apps Script bound project has not yet had the latest **Code.gs** and **EditorialQA.gs** installed. Saving a GitHub change alone does **not** update the bound script.
- **Blocked source / changed receipt:** do not remove IDs or overwrite originals. Inspect the current mechanical/source data and the error. Manual reconciliation may be required.
- **Queue sync error after successful batch creation:** the requests already exist in NCCE. Use **NCCE relay → Sync now** rather than creating a fresh batch.
- **HOLD for long prose:** revise to the form's exact limit and evidence rules; do not simply flip status.
- **Correction draft not appearing on site:** check owner approval, READY, relay running and the new IMPORTED receipt.
- **QA row is metadata-only:** repair the provenance and links; do not churn prose just to manufacture a new receipt.

## Installing the new menu action (maintainer)

1. Deploy backend code containing `src/server.py`'s `bulk/revise-batch` handler and `src/editorial_revision_seed.py`. The existing bearer-token authentication, anti-sync-conflict guard, imported-receipt checks and revision creation remain in force.
2. Open the **bound Google Apps Script project** that currently runs the Writing Exchange relay. Add **EditorialQA.gs** from `scripts/writing_exchange/EditorialQA.gs` as a new Script file and update the `onOpen` menu in **Code.gs** using the repository version.
3. Save, reload the Google Sheet to run `onOpen`, and verify **Historical backfill → Create corrections for all failed QA entries**.
4. Check the menu without creating unnecessary revisions: a completed audit with all 35 Slag Eaters corrections already linked should show **No new failed QA entries need correction requests**.

Do **not** put API tokens in the sheet or in GitHub. Existing Apps Script property `NCCE_EXCHANGE_TOKEN` is reused by the action.
