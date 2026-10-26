# Writer Workshop — NCCE 0.11.0

## Purpose and editorial workflow

The owner can change writing guidance directly, test one sourced entry, edit the prose and deliberately approve guidance for future writing. This changes application prompts, not model weights. Nothing learns automatically from a preference or edit.

1. Open **Writer Workshop** and find an existing fighter memory/reflection, generated biography/history/report or gang/place event. The initial selection is the preferred Mara comparison sample when available.
2. Inspect the read-only factual/context packet. Authored biography remains context, not editable campaign source.
3. Edit shared craft instructions and/or this form's instructions and style examples. The built-in and experimental candidate are available as draft presets. Each preset must be saved/activated deliberately.
4. **Save draft** and **Inspect exact next instructions** are free. Saving does not change the active policy. Inspection saves the selected draft revisions and shows the exact assembled instructions plus a rough input-token estimate; evidence is independently visible.
5. **Generate one draft** queues at most one API request, using those saved revisions and the selected source context. An exact successful result-cache hit can avoid a paid request. There is no critic, alternative generation or automatic retry. Busy writer jobs are rejected before spending. Usage and errors remain visible.
6. Alternatively, **Import selected sample for editing** copies an existing result into the workshop without any provider request.
7. Edit prose, headings and closing fields with a rendered preview. **Save edited sample** appends a permanent edit revision while preserving the original. An edited sample is a style example, not campaign canon. **Use saved edit as an example** adds it to this writing form's draft examples; it does not activate them.
8. **Activate this revision for future writing** changes only the selected shared/form policy pointer. Future writer requests use it. Existing campaign prose is not regenerated. Restore any saved revision through the same explicit action, or restore the built-in policy. Routine automatic generation remains off.

The page retains unsaved editor state while navigating within the current app tab. Save before reloading/closing. Background Sheet refresh does not replace the workshop editor. All persistent revisions, trials and edits live in the existing persistent database.

## Authority and policy assembly

Shared craft applies to all fourteen writer forms. Form guidance and examples apply only to the selected form. Source authority, allowed invention, chronology, authored precedence, output schema and app-controlled dates/provenance remain protected application requirements. The editor displays them in the assembled prompt, but they are not editable through craft fields.

`writer_workshop.active_contract(store, form)` returns no override when no shared/form policy is active, preserving the existing built-in request exactly. Once activated, the common authority/presentation sections surround the approved shared craft and form guidance/examples. `llm_writer.write` resolves this override on the normal production path; exact contract text changes the cache key and request audit. Explicit comparison/test overrides remain fixed and are not silently replaced by an active policy.

No actor/narrator is selected solely from the page's institutional heading. Editorial candidate guidance now explicitly requires a consistent author/audience and literal, physically intelligible action. The user can edit these craft choices directly. Structural checks and examples cannot guarantee literary or factual quality.

## Recorded comparison feedback

The owner judged the 0.10.1 comparison as follows:

- Territory: neither, leaning A.
- Mara: A preferred; B's note-taking description became nonsensical to the reader.
- Gang seizure: neither, leaning B; an Ethernetans self-report cannot describe its authors in third person.

The workshop shows those judgements and resolves A/B identities from the saved server audit. No rejected sample is automatically promoted, and preferring Mara A does not automatically activate a prompt or add that sample to examples. The experimental candidate file has been updated after the experiment; the exact original comparison prompts remain in the audit and are not rewritten.

## Modules and storage

| Component | Responsibility |
| --- | --- |
| `writer_workshop.py` | Policy defaults/composition, saved revisions, explicit activation, source catalogue/packets, trial preparation, one-call execution, retained edits, comparison feedback |
| `llm_writer.py` | Production policy resolution, contract-sensitive cache, one-request provider call and retained usage/request/response audit |
| `server.py` | Mandatory authenticated workshop routes, same-origin JSON edits, bounded background worker and serialization with other writer jobs |
| `web/workshop.js` | Direct editorial UI, source search, revisions/presets, exact-instructions inspection, rendered editing, example drafting, export and trial polling |
| `migrations.py` schema 11 | `workshop_revisions`, `workshop_active`, `workshop_trials`, `workshop_edits`; previous source/audit tables preserved |

Saved instruction revisions and prose-edit revisions are immutable. Active pointers are reversible and activation checks the prior active revision to catch another session's changes. Trials retain the source packet, exact instructions, model/effort, status, document and usage. A failed provider response remains in the schema-10 audit; its text is available for the selected failed trial's manual editing.

Source selection covers active artifacts and event streams plus fighter memories/reflections. Comparison samples reuse the exact factual packet saved with that request. Generated sample editing cannot replace a player-authored biography or modify source records. If context changes between selection and generation, the packet hash check requires re-selection before spending.

## Access and execution

All `/api/workshop` reads and mutations require configured application authentication and a valid passphrase session, even if the rest of a local app runs without authentication. Workshop mutations require same-origin JSON requests. The workshop shares the existing app passphrase; this release does not introduce separate owner/viewer accounts. Anyone with that passphrase has workshop access.

Provider keys never enter browser payloads. Exact workshop instructions and selected context are inspectable, but there is no arbitrary raw audit dump endpoint. Persistent drafts are stored in private workshop tables rather than the dashboard's general `system_state` export.

Generation requires an explicit click and a unique request key. The server atomically records the trial and treats repeats as status retrieval, not new work. A shared pipeline lock serializes generation with sync and other writer jobs; the per-trial budget is one. Server restart marks unfinished workshop trials as interrupted with no automatic replay. Model/effort and output limits currently use the configured production settings (`gpt-6-luna`, medium by default; personal outputs 650 tokens, documents 1,800 unless configured otherwise). The UI exposes model/effort and measured usage; saving/inspection/editing/importing use zero model calls.

## Validation and limits

Offline tests verify explicit activation/rollback, immutable revisions, active production prompt/cache changes, source/canon preservation, one-call/idempotent execution, retained failures, safe rendered edits and no-call opening/inspection. Real HTTP tests cover mandatory authentication even when app auth is off, unauthenticated denial, cross-origin denial, busy rejection and duplicate-request behavior with a mocked worker. Disposable authenticated app smoke exercises source reading, saving/import/editing, activation/restoration and normal campaign views.

No additional paid model calls are part of implementing or verifying this workshop. A user-generated sample remains a workshop result until a separate publication workflow is designed; this release deliberately provides prompt activation, not automatic campaign-prose publication. Export includes instructions, context, composition fields and edited prose as Markdown. Prompt activation influences future drafting only; it does not train a model or enable routine bulk generation.
