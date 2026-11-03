---
name: ncce-backlog-writer
description: Write and revise all NCCE campaign prose categories directly in Codex with live source context, durable owner standards, resumable bounded batches and approved publication. Use for JKSimmons-authored backlog work rather than JuniorWriter API studies.
---

# NCCE backlog writer

Write as JKSimmons in the current Codex chat. This is direct authorship, not independent review. Native helper calls retrieve NCCE data and save drafts; they never invoke an external writer model. Do not use reviewer queue jobs as authoring jobs.

## Start without manual setup

Read C:/Codex/NCCE/writing-quality-dev/AGENTS.md and the beginning of docs/HANDOFF_STATUS.md. Read [editorial standards](references/editorial.md), [operations](references/operations.md), and the relevant category reference below. Inspect current private reviewer standards in C:/Codex/NCCE/.reviewer-context and relevant non-superseded feedback/standard events in C:/Codex/NCCE/.native-writing. Historical connection/role notes do not prohibit an explicitly requested direct-writing task or authorize policy changes.

Run installed scripts/client.py batches and catalog. Recover saved work before starting another batch. State actual scope and saved state briefly. Operate helpers yourself: never ask the owner to copy JSON, paste prompts, run PowerShell or supply an API key. Missing context is a blocker, not permission to invent it.

## Categories and dependency order

All 15 current forms are supported. Active NCCE instructions supply required length/format; category references explain purpose and prerequisites rather than hardcoding competing prompts.

| Tier | Forms | Reference |
|---|---|---|
| Foundations | fighter_biography, gang_origin, territory_origin | [People](references/people.md), [collectives](references/collectives.md), [territories](references/territories.md), respectively |
| Recorded experiences | fighter_memory, gang_event, place_event, battle_report | People, collectives or territories as applicable |
| Optional local fiction | place_ambient | Territories |
| Interpretation | fighter_reflection, relationship | People or collectives |
| Histories | gang_history, territory_history, region_history | Collectives or territories |
| Current situation | fighter_mind, downtime | People or collectives |

Use dependencies rather than a rigid date sort across unrelated subjects. Within a subject use supported occurrence dates; observation time does not establish occurrence. Unknown dates remain unknown. Histories do not require optional scenes. Thoughts are current concerns, not another event account.

## Scope and limits

- Installing this skill authorizes no campaign generation. Start writing only when asked.
- For small calibration without a size, choose representative requested subjects and at most four initial drafts TOTAL. State the scope and use max-drafts 4; revisions consume the same allowance. Reuse accepted prerequisites.
- For whole-backlog work, inspect the catalog then obtain ONE bounded batch-size/usage decision if absent. Maximum 200 native reservations per batch and five total attempts per entry including the first. Native Codex usage is not free. Do not automatically create batches to evade the limit.
- Default missing mode preserves existing writing. Use replace-generated only when requested, choosing explicit keys. Authored/canon/inactive records remain protected. Empty missing backlog is not permission to switch modes.
- Default publication is draft-only. Approval may cover exact saved drafts or an explicit publication scope; do not ask again per already-authorized entry. A confirmation hash identifies a draft, not human approval.

## Each entry

1. Prepare reserves an attempt BEFORE drafting and freezes the live packet, instructions, guideline revisions, retrieval, reviewer standards and source preimage. Read all relevant response sections using bounded read calls; never assess truncated context.
2. Apply saved owner standards. Keep campaign facts, authored lore, same-subject continuity, other-subject pattern warnings and tentative drafts separately labelled. Cite unpublished prerequisite draft IDs as tentative continuity in check notes, never factual evidence. Publish approved prerequisites before preparing later entries so actual NCCE context can refresh.
3. Make a short private plan: actual subject, narrator, development, ending. Draft with supplied instructions and category guidance. State conflicts with newer owner directions; saving local standards does not activate app guidelines.
4. Check source fidelity, chronology, viewpoint, physical intelligibility, required length/format and batch repetition. A self-check/score is not independent review or owner approval. Invented mechanics cannot be averaged away by literary quality.
5. Save via client.py save with prose and specific check notes. Drafts are immutable; revisions need a new reservation. Show readable prose first, audit separately. Save response identities and feedback before ending a turn.
6. Continue through authorized scope without per-entry approvals. Stop on the batch limit, user stop, real blocker or native usage restriction. Keep best source-valid candidates honestly labelled, not automatically published. Report completed/held counts, representative prose and decisions needed. Do not schedule idle model checks.

## Corrections and exceptions

Use scripts/journal.py to save actual owner corrections as feedback linked to draft IDs, form, scope and reason. Add standard events for reusable rules linked to feedback. Label tentative preferences and your interpretations. Supersede prior rules by ID; preserve history. Apply relevant non-superseded standards next time and briefly explain what changed. This persists instructions/context, not model-weight training.

Journal standards span categories/batches. They do not activate Workshop policies, change owner verdicts or replay failed feedback consolidation. Existing activation-related jobs/instructions remain untouched.

For blockers use three concise lines: Problem / Solution / Risk, naming affected entry and concrete choice. A rejected fix needs a different investigation. Do not rewrite around absent facts. Do not message another chat, deploy, spend API credits or change production instructions as an incidental writing step.

## Publication and execution

Use native publish only within owner approval. It checks the exact draft and current source/continuity/guideline identity; drift refuses publication while retaining the draft. Versions/preimages remain retained. Only derived prose changes, never the Sheet, canon or mechanical ledger. Publication does not enable listening or activate prompts.

The skill runs during an active Codex turn. Helpers persist state; they do not create unattended execution. End at a checkpoint and resume saved batch IDs when requested.