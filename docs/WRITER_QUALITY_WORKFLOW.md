# JuniorWriter / JKSimmons / StoryTechMan development prototype

## Primary workflow: improve the actual NCCE writing setup

The development branch now includes **Writer Workshop → Improve NCCE's writing setup** in the NCCE web application. This supersedes the detached Writing Lab as the main workflow. The goal is reusable improvements to NCCE's prompts and context delivery, not repeatedly polishing standalone samples. Source is `0.13.0-dev`, schema 13; this is not deployed to the hosted app.

Select the prose form and starting sample in Workshop, choose a maximum of 1–3 rounds, then **Improve this prose form**. The confirmation covers both writing and reviewer requests. Each round uses two independent real source packets with two JuniorWriter drafts per packet, followed by one JKSimmons review per pair: at most **4 writing + 2 reviewer calls per round**, or **12 + 6** for three rounds. Independent contexts are identified by full source-packet hashes; two comparison variants of the same packet do not count. A form without two independent sourced samples cannot start. Nothing generates merely by opening the Workshop.

The loop uses the exact NCCE `writer_workshop.preview`, creative planning, protected contract assembly, `llm_writer.write` and its audit/validation. Drafts stay in private Workshop tables within the app database. A writing-only shortfall produces a saved, inactive replacement form brief for the next round. The final review in a round sees prior reviews from the other sample and is asked to integrate reusable lessons, without copying names/facts/metaphors into instructions. The selected shared draft and examples stay frozen. Context/technical/permission issues, invalid reviewer output, provider failures, changed source evidence or exhausted budgets stop the run. No automatic context/code repair or paid retry occurs. **Stop after current request** is available during execution. Restarts mark unfinished runs for investigation rather than replaying them.

Both drafts on both source packets must reach at least 8 overall and on every criterion, with no blocking issue. Passing moves to a human review of the reports, drafts and exact tested instructions. **Approve tested setup for future NCCE writing** atomically activates the exact shared/form pair that was tested, provided active pointers and source context have not changed. This affects the normal production writer's future prompts and cache keys. **Reject this setup** leaves active policies unchanged. Existing campaign prose, authored lore and Sheet records are not replaced. No bulk-fill behavior is enabled by approval.

The automated reviewer is a separate API role using the existing server key. Its default model/effort are the configured writer's model/effort; `NCCE_REVIEWER_MODEL` and `NCCE_REVIEWER_REASONING_EFFORT` can select a separate reviewer. This does not inherit a ChatGPT session: the reviewer receives the explicit recovered rubric, saved NCCE editorial feedback, protected contract, exact context, both outputs and prior sample reviews. The original chat's missing replies/images remain unavailable. A complete reviewer request/response/usage/error audit is kept in `workshop_review_requests`; no credentials are included. The structured response format follows the [official OpenAI Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

Two contexts are representative checks, not statistical proof of consistency across all subjects or fourteen prose forms. Reviewer scores are model judgments, not human approval. Source/pipeline findings remain explicit StoryTechMan handoffs to the development agent/human; no arbitrary repair tools are given to the reviewer. The full report in Workshop retains context, instructions, drafts, judgments and the event ledger so the issue can be investigated without reconstructing the manual experiment.

Schema 13 adds private `workshop_optimization_runs` and `workshop_review_requests`; it does not change campaign-source schemas. Routes reuse mandatory Workshop authentication, same-origin JSON edits and the shared pipeline lock. Idempotent request keys prevent duplicate run launches. Before activation, both active pointers are checked in an immediate SQLite transaction. Offline tests verify that a revised candidate actually reaches subsequent normal NCCE generation after human approval, along with budget, failure, cancellation, restart, source preservation, two-context coverage and stale-promotion checks.

## Earlier local prototypes

This opt-in local prototype has a native desktop GUI and a command-line interface. It reuses NCCE's writer and context pipeline. It does not run from the server, alter the hosted app, activate Workshop policies or publish prose. No new SDK or account connection is required. Python's standard library is sufficient.

## Open the GUI

Double-click **`C:\Codex\NCCE\OPEN WRITING LAB.vbs`**. The development checkout also includes its own `OPEN WRITING LAB.vbs`. The launcher uses the existing Codex Python runtime and opens a native window without a terminal. The development checkout now lives at `C:\Codex\NCCE\writing-quality-dev` on the same branch.

On first opening, it creates a consistent private campaign copy at `C:\Codex\NCCE\.writing-quality-run` and selects the forms with available sourced samples. Missing forms remain visible as a coverage warning. Opening the window and inspecting context make zero provider calls. This is a fresh run; the earlier command-line run remains preserved in its original private folder. Use **Open run** to open another completed quality snapshot.

Select a prose form on the left. Read **Context & instructions** before generation. Enter an API key in the masked field (memory only), then click **Generate two drafts** and confirm the two paid requests. Drafts appear side by side; **Export for reviewer** and **Import review** handle the existing manual JKSimmons handoff. **Approve this form**, **Reject this form**, and **Resolve stop** are enabled only at the corresponding workflow gate. **Save report** retains the complete run. No bulk generation or publication control is provided. Keep the window open while work is in progress.

## Project and connection

The registered NCCE project is `C:\Codex\NCCE`. The actual Git repository is nested at `C:\Codex\NCCE\MCCE-PROJECT-CONTEXT\MCCE-personal-codex-handoff`, remote `https://github.com/fryndlz/NCCE.git`. Base commit for this prototype: `fbdef2a`. The isolated branch is `dev/writing-quality-workflow`. Existing unfinished frontend work in the original checkout is preserved.

The local repository and campaign SQLite database are accessible from this machine; there is no need to reconnect GitHub to inspect or develop. Paid JuniorWriter execution requires the existing server-side `NCCE_OPENAI_API_KEY` in the local operator process, with `NCCE_WRITER_MODEL` / `NCCE_WRITER_REASONING_EFFORT` selecting the existing configuration. Secrets are never exported in review bundles. The hosted Render environment and its newer database are separate: no hosted credentials or database were downloaded. A consistent hosted backup would be needed to review hosted-only edits/context. Do not copy a live database file without SQLite backup support.

## Existing generation and context

`Sheet snapshot -> diff -> event ledger -> observations/stims -> memories/reactions/reflections -> documents/event streams -> llm_writer.write -> Responses API -> validation/cache/audit`.

- `writer_workshop.sample/catalog/preview`: select a sourced sample and inspect exact context/instructions.
- `narrative_context`: event-time identity/ownership, authored background, bounded same-subject continuity and provenance separation. The writer does not yet consume raw Munda Manager archive chronology.
- `writer_contract`, `docs/writing_sources/WRITER_RUNTIME_CONTRACT.md`: protected authority/presentation sections, shared craft, fourteen form briefs, illustrative examples.
- `writer_workshop.active`: selected active shared/form revisions from the database; this prototype uses them, without activating changes.
- `writer_planning`: free frozen creative plans, verified territory-type references, bounded repetition hints. Hints are not campaign evidence.
- `territory_reference`, `WRITER_IDENTITY_TAGS.md` and source documents: reference/identity constraints. Canonical C-NINE background comes from the frozen local lore export; live Google Doc sync is not implemented.
- `llm_writer`, `writer_workshop.execute`: one-request execution, voice/format validation, request/response audit, usage and exact contract-sensitive cache.

The referenced Writing Reviewer conversation exposes workflow requirements but not its full assistant reviews or attached image content. Its missing context cannot be assigned to a model implicitly. JKSimmons uses a versioned rubric in `src/writer_quality.py`, current protected contracts and saved NCCE editorial lessons: concrete consequences, physically intelligible actions, consistent narrator/audience and preserved place identity. A reviewer score is subjective, not a quality guarantee.

## Roles and gates

| Role | Implemented behavior |
| --- | --- |
| JuniorWriter | Existing OpenAI writer, at most two requests per human-granted pair. Exact source/policy/plan/model/effort/token allowance are frozen. Each alternative has a unique editorial marker; factual context and creative plan are otherwise identical. |
| JKSimmons | Exportable review bundle containing both outputs, exact contract/context, rubric, hash and JSON template. A reviewer fills the template; importing it validates both scores and issues. No additional reviewer API calls are wired in this prototype. |
| StoryTechMan | Immediate persisted escalation and technical handoff with audit/events. It cannot edit code, context, credentials or budget automatically. Its report is a procedural report, not a claim that a third model ran. |
| Human | Grants each pair, resolves escalations with an attributed note, and explicitly approves/disapproves qualified forms. These are trusted local operator actions; `--actor` is attribution, not authentication. |

Both drafts must score at least **8 overall and in every rubric criterion**, with no blocking writing issue. Any context/technical/permission issue pauses the entire run regardless of score. A writing-only shortfall retains feedback and awaits a fresh two-call grant. Bounded feedback enters the next pair as labelled editorial context; it cannot grant calls or activate a policy. Default cap: three pairs per form (configurable at initialization, 1–10). Exhaustion requires human reassessment and a separately initialized run; resolving an escalation cannot reset the counter.

Provider errors, missing credentials and changed configuration stop before any further request. If candidate A fails, candidate B is not requested. No automatic retry/refill. Usage and failed outputs remain in the snapshot's existing writer audit. Calls are counted conservatively as two reserved opportunities even after an uncertain interruption; never replay that pair. An incomplete `running` state stops work until a human checks the audit and resolves it. The CLI holds an exclusive run-directory lock across provider operations; do not call the underlying module concurrently outside that interface. After a hard crash, verify no operator process is running before manually removing `operator.lock`, then use `resolve`; this does not replay the old pair.

Qualified forms wait for human approval. Disapproval stops that form for discussion/new planning. Approval records only sample-quality acceptance. There is **no bulk-fill or publication command**; an approved form may later support a separately reviewed bulk plan with explicit targets and spending cap. Passing one sample pair per form is a prototype acceptance sample, not coverage of all events or subjects.

## Operator walkthrough

Run from the development checkout. `python` below means a working Python 3 executable. Use an absolute private run directory outside Git; it contains campaign context and audit data. Initialization uses SQLite's read-only-source backup API, including committed WAL data, then migrates only the copied database. The original campaign database is never opened with `Store` or modified by this tool.

```powershell
python scripts/writer_quality.py --run-dir C:\private\ncce-quality init --campaign-db C:\path\to\chronicle.db --forms fighter_memory,place_event
python scripts/writer_quality.py --run-dir C:\private\ncce-quality catalog
python scripts/writer_quality.py --run-dir C:\private\ncce-quality inspect --form fighter_memory
```

Omit `--forms` to require all fourteen forms; initialization refuses missing sourced forms instead of silently omitting them. Use `--samples selections.json` to select explicit Workshop sample keys (`{"fighter_memory":"memory:..."}`); otherwise the first catalogue sample for each selected form is used. Inspect that choice before granting. A failed initialization leaves a private partial directory for inspection; use a fresh directory after correcting the selection. It cannot be operated on unless initialization completed.

After actual human authorization for paid generation:

```powershell
python scripts/writer_quality.py --run-dir C:\private\ncce-quality grant --form fighter_memory --actor Blazej
python scripts/writer_quality.py --run-dir C:\private\ncce-quality run-pair --form fighter_memory --allow-paid
python scripts/writer_quality.py --run-dir C:\private\ncce-quality review-bundle --form fighter_memory > review-bundle.json
```

Give the complete bundle to the reviewer. Save its filled `template` as a JSON object in `review.json`; keep the exact round/hash, supply all scores, issues, summary and craft suggestions. Copy an issue from `issue_schema` when needed. The reviewer cannot authorize the next pair. Then:

```powershell
python scripts/writer_quality.py --run-dir C:\private\ncce-quality review --form fighter_memory --file review.json
python scripts/writer_quality.py --run-dir C:\private\ncce-quality status
python scripts/writer_quality.py --run-dir C:\private\ncce-quality approve --form fighter_memory --actor Blazej --note "I approve these samples"
# Or disapprove with a note. For a technical stop, investigate first, then:
python scripts/writer_quality.py --run-dir C:\private\ncce-quality resolve --form fighter_memory --actor Blazej --note "What was investigated and decided"
```

The status report retains every candidate, usage, reviewer assessment, event and human decision. `all_selected_forms_at_target` is separate from `all_fourteen_forms_selected`; a narrowed run cannot claim complete coverage. Review bundles and reports may contain private campaign content: keep them out of commits/public source.

## Validation and local readiness

Offline tests cover real Workshop integration with a mocked provider, pair/context identity, exactly two maximum requests, preserved mechanics/memories/active policies, invalid/stale/incomplete reviews, finite score validation, all non-writing issue categories, low-score retries requiring fresh grants, quota failures, crash recovery, configuration/credential stops, round caps, human approval/disapproval, consistent WAL snapshots and exclusive CLI locks. Existing Workshop/pipeline/planner tests and disposable authenticated HTTP checks are also run. No paid calls are required for verification.

On 2026-10-27 the local `chronicle.db` offered sourced samples for **13 of 14** forms. `place_ambient` was absent; the separate `writer-preview.db` had a test ambient sample but lacks `relationship`. Do not mix a test sample into the live campaign qualification silently. A private copied 13-form run was initialized and all thirteen packets inspected, with **zero grants and zero provider calls**. Ambient coverage needs an explicitly selected real sample or a separately declared test scope. This is local readiness, not a hosted database audit or an 8/10 writing claim.
