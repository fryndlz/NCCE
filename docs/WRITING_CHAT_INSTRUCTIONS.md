# Instructions for the existing writing chat

Keep your existing Project instructions, examples and established literary voice. This document explains how to receive campaign evidence and return finished prose to NCCE. It does not replace your writing style or train a model.

## First message / capability check

The owner will supply the writing exchange Google Sheet URL or upload the workbook. Tell the owner whether you can actually read it and update individual cells with your available tools. Read Guide, Forms and the first request_id in Queue and repeat that ID to demonstrate access. Do not write prose or change any status during this check. If you cannot access the Sheet, say so and use the manual handoff below. Never imply that a link alone gives you access.

## When the owner says to write a request

1. Process only the named request_id, or the explicitly authorized number of PENDING requests. Ignore DRAFT, WRITING, READY, IMPORTED and HOLD. Do not generate multiple candidates. Do not call other writing models or create a reviewer chain.
2. Read that Queue row and every Context row whose context_id exactly matches. Keep request_id, form, entity_type, entity_key, entry_key, context_id, source_revision, event time and Imperial date unchanged. IDs are routing metadata, never part of fiction.
3. Verify that the evidence is sufficient and output is blank. If text already exists, preserve it and ask the owner how to resume. Missing/ambiguous identity, unavailable essential rules, unknown event order or contradictory evidence means HOLD, with a specific writer_note. Never fix a missing ID by inventing one or matching a similar name.
4. If editing the Sheet is possible, change only this row's status from PENDING to WRITING and reread before continuing. This is a single-writer workflow; do not run several chats on the same queue.
5. Write one finished entry using your existing literary skill, its requested form and the context below. No alternative drafts or self-review output are requested. Complete in-world headings/metadata/sign-off where appropriate; do not make the owner fill separate composition fields.
6. Save the full entry as Markdown in writer_text_md (column L), a delivery note if needed in M, and a verified UTC completion time in N when available. If the current time is unavailable, leave N empty rather than guess. Set READY last, after saving. Reread the ID, full saved prose and status. Never claim success without confirmation.
7. If saving fails, return the entire text in the manual delivery object. Preserve it. Do not regenerate it merely because transmission failed. Explain the problem outside the prose.

Keep individual cells below 30,000 characters for workbook compatibility. If the completed document exceeds that, preserve it as a UTF-8 text/Markdown file and return HOLD with the file reference. Never cut prose to fit a cell or omit part of it silently.

## Evidence and literary boundaries

- Mechanics are facts; relevant player-authored lore is canon. Both constrain generated fiction. Previously generated text is continuity only, not independent factual evidence.
- Do not rewrite or replace authored text unless the owner explicitly requests an edit of that text. gang_origin is currently authored-only and must not be generated.
- A baseline describes the entity's established background. An event entry develops a particular dated occurrence against that background. Reflections connect supplied memories; current thoughts react to the supplied current cause. These are distinct forms.
- Use events in their supplied historical order and the state/owner/identity at that point. Do not fold a whole backlog into one simultaneous experience. Unknown dates remain unknown. First observed is not necessarily occurred.
- Real-world dates, UUIDs, provenance labels, confidence and before/after mechanics belong outside fiction. Use the supplied Imperial date for in-world metadata if appropriate. Do not invent a conversion or call something a documented fact because it was generated.
- Use a gang's own lore, properties and people. C-NINE's institutional/industrial vocabulary is specific to C-NINE. The selected in-world author and viewpoint must remain coherent; an internal gang report cannot describe its own authors as uninvolved outsiders without a reason.
- When authorized, invent concrete fictional connective detail that fits the form and facts. An ambient incident has no mechanical impact. Do not invent recorded casualties, ownership changes, participants or battle outcomes unsupported by the packet. Do not translate a numerical advance into a bare label such as "Cool" or a sentence about a database update.
- Return the complete finished document, not a list of facts, writing advice, a critique or a provenance explanation. Blank lines separate paragraphs. Markdown headings, bold field labels and transcript turns are allowed. No active HTML, scripts or fenced code around the prose. Technical notes go in writer_note only.

These are delivery/evidence rules. Use the literary judgement, examples and instruction history of this conversation for the actual prose. Do not import old NCCE prompts or assume the style should be universally bureaucratic.

## If direct Sheet editing is unavailable

The owner supplies one Queue row and its matching Context rows, by attachment or pasted packet. Return one JSON object containing the fields below, copying every identifier exactly. Put the complete finished Markdown in writer_text_md. An ordinary JSON code block is acceptable for this transport object; the prose inside it is not itself fenced. The owner/coordinator transfers it into the matching existing row.

```json
{
  "request_id": "COPY EXACTLY FROM REQUEST",
  "source_revision": "COPY EXACTLY FROM REQUEST",
  "status": "READY",
  "writer_text_md": "COMPLETE FINISHED MARKDOWN",
  "writer_note": "",
  "completed_at_utc": ""
}
```

For a blocked request return status HOLD, a specific writer_note and an empty writer_text_md if nothing was written. If prose already exists, preserve it in full. The uppercase strings in this illustration are placeholders only; never submit them as real IDs or prose.

You must never set imported_at_utc, import_receipt or IMPORTED. READY means the draft has been delivered; it does not mean NCCE has published it. There is no background integration or schedule attached to this workbook yet.

## Suggested first instruction from the owner

"Use the attached NCCE exchange instructions with this Sheet: [paste URL]. First perform the capability check only. Do not generate anything yet. Keep using the writing style and examples we have established in this Project."

After a real request has been prepared and changed to PENDING:

"Write exactly request [paste request_id]. One finished entry only. Save the result to that row if you have verified write access; otherwise return the manual delivery object. Do not process the rest of the queue."
