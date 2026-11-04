# External writing exchange — framework 1

Prepared 2026-11-04, 14:56 UTC / 15:56 CET. This describes the delivered workbook contract, not a deployed NCCE integration. NCCE remains 0.24.0 with its internal writer disabled.

**Native import verified 4 November 2026, 19:16 CET / 18:16 UTC:** [NCCE Writing Exchange](https://docs.google.com/spreadsheets/d/1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas/edit) is now in the connected account's ChatGPT folder. All 20 reserved IDs match the local manifest exactly and remain blank DRAFT requests. All 16 forms, three native tables, frozen queue identifiers, dropdown column options and formulas survived conversion. Native table dropdown types were set explicitly and the queue's imported text-status conditional formatting was repaired. Writer instructions were added as a fifth tab, preserving all 13 source instruction blocks exactly. All five tabs were visually inspected in Google Sheets at 100% zoom. The workbook is private to its owner; access from the separate work account has not been tested or granted. No actual writing, context export or app import was started.

## Purpose and current boundary

The owner's existing ChatGPT Project conversation supplies the prose. A separate Google Sheet carries requests, frozen context and returned Markdown. The existing conversation's literary instructions and examples remain its style authority. This framework does not train a model, recreate the removed Workshop/RAG/reviewer pipeline or invoke a provider.

The verified native Sheet is the working queue; the local XLSX is its original preparation artifact. There is no automatic export, polling, webhook, app import, scheduling or new publication controller. A READY row does not yet appear in the app. Those are subsequent integration work.

## Workbook

- **Queue:** one intended prose entry per row. Twenty preallocated UUID request IDs start in DRAFT with no campaign requests or paid work queued. Sort whole rows, never a single column. Filters and frozen identifiers support navigation.
- **Context:** several labelled evidence blocks may share a context_id. Source provenance, event time and IDs stay outside literary output. Source URLs supplied here are a directory, not proof their contents were fetched.
- **Forms:** all 16 current System prose categories. This list is descriptive, not permission to generate every category. Gang backstories remain authored-only.
- **Guide:** owner workflow, status definitions and field dictionary.
- **Writer instructions:** the complete existing-chat delivery instructions, copied into the native Sheet so they can be read without a local file. The Google Sheet Guide now points here instead of asking the owner to upload the workbook.

Queue columns:

| Column | Field | Owner and meaning |
| --- | --- | --- |
| A | request_id | Coordinator. Immutable UUID, already supplied for 20 rows. Never use row number as identity. |
| B | status | DRAFT, PENDING, WRITING, READY, IMPORTED or HOLD. Writer may only claim PENDING to WRITING, then READY or HOLD. |
| C | form | Coordinator. Exact Forms key. |
| D | entity_type | Coordinator. fighter, gang, territory, battle, campaign or relationship. |
| E | entity_key | Coordinator. Stable source identity; display name alone is not identity. |
| F | entry_key | Coordinator. Stable logical slot, such as a source event UUID, biography or a particular history revision. |
| G | title | Coordinator. Human-readable request title; not necessarily the diegetic heading. |
| H | context_id | Coordinator. Joins all matching Context rows. |
| I | source_revision | Coordinator. Frozen packet version. Any evidence change creates a new revision and request; never silently edit work in progress. |
| J | event_at_utc | Coordinator. ISO 8601 UTC text, or blank if unknown/baseline. This is occurrence time, not scrape time. |
| K | imperial_date | Coordinator. Exact NCCE-converted date or blank. Writer must not invent/convert it independently. |
| L | writer_text_md | Writer. Complete display-ready Markdown, including optional in-world headings, metadata and sign-off. Blank lines separate paragraphs. |
| M | writer_note | Writer. Delivery issue or concise note; never mixed into prose. |
| N | completed_at_utc | Writer. Actual completion timestamp with UTC offset/Z; never guessed. |
| O | imported_at_utc | Future importer only. Actual committed import time; blank today. |
| P | import_receipt | Future importer only. Durable app record/revision acknowledgement; blank today. |

Protocol timestamps are deliberately ISO text to preserve offsets across Excel/Google Sheets conversion. They are not spreadsheet serial dates or local timezone guesses. No calendar arithmetic is done in the workbook.

## Identities and revisions

Request UUIDs identify work, not fighters or events. Do not reuse a consumed request ID, even if a row is cleared. Preallocated blank rows may be populated once; beyond twenty rows a coordinator must mint fresh UUIDs and extend table/validation/count ranges. A copied workbook is a backup of the same queue, not an independent queue to process concurrently. Until an exporter is implemented, Codex can prepare real packets; the owner is not expected to invent IDs or manually assemble technical source context.

entity_key must use a verified source UUID/composite identity exported by NCCE. Numeric database IDs, mutable names and sheet row numbers cannot be trusted across installations. If a source has no immutable ID, the exporter must establish a persisted exact mapping before requesting prose. Neither chat nor future importer should fuzzy-match names. entry_key identifies the intended logical narrative slot separately from request_id. No placeholders should be put into PENDING.

context_id identifies a frozen packet. source_revision is an explicit version (for example packet-0001-v1), not a claim that a cryptographic checksum has been calculated. A future exporter should compute a canonical packet hash. The production importer must match the request's immutable tuple (form, entity_type, entity_key, entry_key, source_revision), reject duplicate/conflicting IDs and confirm that the target is still appropriate.

## Context packet

For each real request supply separate Context rows for:

1. Brief: required form, speaker/author and POV, creative scope and target entry. Tell the writer whether this is baseline, historical event, current thought or synthesis.
2. Mechanical facts: exact known changes, participants/outcome, before/after values, event IDs and occurrence times. First-observed time must be labelled as such, not silently treated as occurrence.
3. Authored canon: relevant character/gang/place text, attributed to its author/source; scoped to that entity. Authored text supersedes generated inference.
4. Rules: relevant verified rulebook description with book/edition/page or source URL. An unvisited link is not a fetched rules excerpt. If a requested rule is unavailable, HOLD rather than fabricate it.
5. Chronology: earlier relevant events, territory owner at the event, pre/post battle boundaries and any explicit uncertainty. Never combine all historic changes into the present. Do not borrow future injuries/rank/ownership.
6. Existing fiction: relevant accepted generated continuity, explicitly inference/connective_fiction. This is not mechanical evidence or authored canon.
7. Optional character context: inferred identity, voice, relationships, stims and current conditions, with their provenance. No global C-NINE diction for unrelated gangs.

Required sections depend on the form. A baseline can have unknown event dates; a historical event must have a supplied time/order and source event identity, or remain HOLD. Reflection cites its supporting memories; current thoughts use the engine-selected current cause, not the writer's new expiry/retrieval policy. The fighter's logical event clock and cognition stay in NCCE.

The source directory in the workbook provides the known Krakamunda and C-NINE URLs. It does not contain a downloaded campaign packet or rulebook excerpts. No authoritative source was changed.

Keep each cell below 30,000 characters for a safe XLSX round trip. Split long source context across additional rows with the same context_id. An oversized finished entry must be preserved in a separate UTF-8 file with a delivery note/HOLD, not truncated to fit a cell.

## State transitions and one delivery per entry

Coordinator prepares DRAFT and a complete context packet, checks no authored/accepted text would be overwritten, then changes it to PENDING. In the pilot, ask the writer to process exactly one specified request ID.

One writer only: read PENDING, verify immutable inputs and no saved output, set WRITING, then write once. Persist the entire output in L and set READY last. If tools cannot update cells, return the exact delivery object described in WRITING_CHAT_INSTRUCTIONS.md for manual transfer. Do not claim a sheet update succeeded without rereading it.

On missing evidence, ambiguous target, unavailable tools or interruption, leave preserved output intact and use HOLD with an explanation. A partially completed/uncertain WRITING request must be inspected and resumed using existing text; it is never blindly regenerated. There is no automatic retry, second candidate or reviewer selection. Explicit owner-requested revision is new work, preserving the previous output.

READY means written and saved, not published, approved as canon or guaranteed stylistic quality. IMPORTED is reserved for a successful future database transaction with receipt. The chat cannot set it. HOLD may retain a complete draft for recovery; it must not become a text-disposal mechanism.

## Future importer acceptance contract (not implemented)

- Resolve exact target and source revision; block stale, ambiguous, duplicate or missing identities.
- Treat generated output as inference (or connective_fiction for ambient scenes). A chat writing it into Sheets does not make it player_authored/canon_authored.
- Preserve authored records. Do not merge fiction into source mechanics or overwrite authored text.
- Preserve the full original Markdown and returned metadata before parsing. Formatting only; no secondary writer or silent prose edits.
- Sanitize Markdown/links for display without changing source text; metadata/provenance/real dates stay in the app wrapper. No raw active HTML/scripts.
- Store request_id, source revision, source event IDs, provenance and imported artifact revision atomically. Re-importing the same request is a no-op returning the same receipt; conflicting content for that ID is quarantined intact.
- Mark IMPORTED only after commit. If acknowledgement fails, repeat the import/receipt check, not the generation.

## Using the native Sheet

The import is complete; use the native URL above and keep it separate from Krakamunda. No sharing settings were changed. If the work account cannot read it, the owner will need to grant that specific account access. Keep one working copy; do not import the XLSX again to create another queue.

Give the native Sheet URL to the existing Project chat and ask it to read Writer instructions, starting with the capability check only. Test whether that chat can read and write the Sheet; its tool availability and workspace policy have not been verified. If it cannot, attach the workbook/context and use the manual JSON return path. Do not ask it to pretend it has edited Google Sheets.

Next integration milestone is an authenticated NCCE exporter/importer and one real request end-to-end. Until then, no timer or whole-roster job is enabled.

## Build and verification

`scripts/build_writing_exchange.mjs` builds the workbook offline with the approved artifact-tool runtime. Provide its output directory as the optional first argument; that directory needs a node_modules junction to the approved runtime packages. The output directory's manifest preserves reserved IDs across reruns. A fresh output directory creates a separate workbook identity. Do not run two copies as independent queues sharing the same manifest.

The builder reads the 16 current category definitions from prose_progress.py, verifies 20 unique request UUIDs, tests PENDING/READY/IMPORTED counts, restores all rows to blank DRAFT, scans formula errors and exports visual previews. Exported XLSX structure is separately inspected for category parity, statuses, validations, tables and frozen panes. Native conversion and this connected account's read/write access were verified as recorded above. The separate work chat's capabilities remain untested.
