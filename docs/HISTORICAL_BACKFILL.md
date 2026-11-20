# Historical Bulk Backfill

Historical Backfill processes a finite snapshot of existing fighter memories and reflections in the private NCCE Writing Exchange. The five-minute Apps Script trigger runs the relay and the Writer. The ordinary Queue continues to use the existing owner approval process.

## Create or resume a job

- **Historical backfill → Create one-off backfill** accepts exact gang or House selectors, two inclusive ISO dates and a maximum item count. Dates refer to the UTC event date. Items without dates are excluded. If the snapshot exceeds the authorized count, creation fails before reserving any items.
- Confirm the scope and OpenAI use in the menu. The confirmation authorizes up to three draft calls and nine review calls per item, including retry attempts. The relay recovers the manifest from NCCE if the creation response or Sheet update is interrupted.
- To resume a legacy job, select its existing **ACTIVE** row in **Bulk Jobs** and choose **Resume selected autonomous job**. This authorizes writing for the selected ID and clears a configuration pause after the operator fixes its cause. Its original snapshot, item IDs and receipts remain the basis of the job. For Kły Sprawiedliwości the existing job is `5530b49f-0ad8-4e14-a3fd-669644c8f411`.
- **Bulk Reports** lists the final state, IMPORTED, SKIPPED, HOLD and unresolved counts plus a review link. Select an IMPORTED row and choose **Revise selected bulk entry** to open a new revision request in the ordinary Queue. Only the owner's approval of that exact draft may advance the revision to import.

## Processing and recovery

NCCE freezes the request ID, target, event and base context at authorization. It releases only items whose prerequisites are satisfied. Writer and independent reviewer receive the complete server packet, including facts, chronology, character and provenance, literary policy and accepted continuity, plus the full Writer instructions, Writer skill and Voice identity tabs.

The Writer saves its candidate and counters in the SQLite QA ledger. A separate model call records a verdict and justification for each of mechanics, chronology, lore, character, style, format and length. Deterministic checks enforce the heading, the name- and alias-free memory title, the 350 Unicode-character cap for a memory including Markdown, and the 60–130-word reflection body. A failed check feeds its reason back into the next rewrite. Model-based editorial judgement can still miss a defect.

The relay publishes READY after saving and verifying the reviewed text. The importer checks the stored approval against the exact draft and sealed context, then invokes the canonical import path. Same-ID replay preserves the original receipt. Legacy READY drafts awaiting import need the same review. Previously imported entries and receipts are retained.

The server stores call counters before contacting OpenAI. Provider interruptions use bounded backoff and resume from the last committed checkpoint. Missing quota, credentials, or model access pause the affected job and appear under **Bulk Jobs**. Exhausted attempts and source or prerequisite conflicts appear as HOLD with reasons. Inspect these before closing jobs manually. A normal Queue error is investigated separately from a bulk job error.

## Deploy and verify

1. Run the unit and integration tests and the one-item end-to-end fixture. It uses the real HTTP handler and SQLite with disposable state and simulated Google Sheets and OpenAI calls.
2. Deploy the tested backend to Render and verify the schema 22 backup and healthy startup. The migration appends QA checkpoints without replacing historical job or import ledgers.
3. Save `AutonomousBulkWriter.gs`, `Bulk.gs` and `Code.gs` in the existing bound Apps Script project. The checked-in files are the source of truth. Keep Sheets v4, V8 and the existing OAuth scopes. The existing trigger runs the saved project head. No separate Apps Script web-app deployment is needed.
4. Run **Check bulk writer and trigger**. It verifies the relay bearer, lists key presence without exposing the key and checks the current account's `syncNCCE` trigger. Verify a new successful timer execution in Apps Script and the job counts in the exchange.
5. Configure `NCCE_BULK_WRITER_API_KEY` securely in Script Properties for OpenAI and set `NCCE_BULK_WRITER_ENABLED=true` when ready. Defaults are GPT-4.1 mini (Writer) and GPT-4.1 (reviewer), overridable via `NCCE_BULK_WRITER_MODEL` and `NCCE_BULK_REVIEWER_MODEL`. Check both model permissions and quota with a small authorized scope before enabling a production job. The global switch alone does not authorize pre-existing jobs.
6. To pause paid generation, clear the global enabled switch or the authorized legacy job ID from `NCCE_BULK_WRITER_JOB_IDS`. Keep the database and checkpoints. Do not roll the backend back to a release that cannot open schema 22.

## Relay contract

The existing dedicated relay bearer protects the `bulk/*` routes. `create` accepts `start_date`, `end_date`, gang selectors, `owner_authorized`, `autonomous_writer_authorized` and `max_items`. `jobs` discovers active and recently finished jobs. `poll` returns prerequisite-safe packets with context hashes and versioned checkpoints. `checkpoint` compares the expected version and preserves the attempt history. `deliver` accepts only the durable approval matching the exact draft, except a replay of a previously committed import. `status`, `close`, `cancel` and `revise` use the existing job and request IDs. The signed-in application also exposes `GET /api/historical-backfill?job_id=…`.

For the existing memory-title audit, use `python scripts/audit_fighter_memory_titles.py --db /path/to/ncce.db --job-id YOUR_JOB_UUID`. The audit reads stored Markdown. Use the approved revision flow for corrections.
