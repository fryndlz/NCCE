# Writing waterfall and legacy replacement — NCCE 0.27.0 / schema 18

Implemented 5 November 2026. The code contract is in `writing_waterfall.py` and
`exchange_automation.py`; the Google transport is `scripts/writing_exchange/Code.gs`.
No internal writer, reviewer or RAG system is enabled.

## What counts as finished

Player/canon-authored sources remain authoritative and are not replacement
targets. An imported external-writing receipt protects that logical entry.
The previously reviewed Mara pilot is protected through its original registry.
Writing-chat output is accepted fiction, not automatically player-authored canon.

All other generated wording is legacy, including text previously marked ready,
old native/provider drafts, stale prose and nonempty placeholders. Classification
uses provenance and committed receipt records, not a model or a word blacklist.
Missing/empty slots also need writing. No unknown historical events are created.

The first poll saves each nonempty legacy projection in
`writing_legacy_inventory` before marking it stale. The old text, evidence,
dates and source links remain stored until a replacement arrives. Each request
also retains the full original projection. This prevents old generated text
from being counted as completed while preserving history and recovery data.

Gang origins remain authored-only under the owner's earlier instruction.
Post-battle addenda continue to use authored dossiers; this release does not
invent generated addendum slots. The existing 14 generated forms are covered.

## Priority and dependencies

| Phase | Forms | Required accepted support |
| --- | --- | --- |
| 0 — Baselines | Fighter biography, territory origin | Authored canon/mechanics provided in the packet; no generated prerequisites |
| 1 — Recorded events | Fighter observations, gang/place events, existing local scenes, battle reports | Own generated baseline where applicable; previous entry in the same fighter/gang/place event stream; an unambiguous territory baseline for a battle |
| 2 — Reflections | Fighter reflections | Own baseline and the explicitly cited observations |
| 3 — Current thoughts | Active fighter Mind entries | Own baseline and the selected source memory/reflection |
| 4 — Histories and downtime | Gang/place history, relationship history, downtime | Relevant completed event streams, cited/related battle reports and, for gang accounts, own fighters' reflections/current thoughts |
| 5 — Regional chronicle | Region history | Completed phase-4 accounts |

The planner finds runnable entries, then exports only the lowest runnable phase,
up to five outstanding requests including in-flight work. A held prerequisite
blocks its dependents. Independent branches may progress when no lower-phase
work is runnable. This is a dependency frontier, not an arbitrary alphabetical
queue. Within a phase, actual event timestamps order entries, with deterministic
entity/key tie-breaks; unknown dates do not become invented events.

Fighter/gang/place event streams are processed chronologically. A reflection
does not receive unwritten observations; a current thought does not use an old
machine placeholder as its completed cause. This changes writing order only:
fighter-relevant event distance, ten-event half-life, importance, causal IDs,
lifecycles and mechanical truth are unchanged.

Battle/place associations must be unambiguous before another location's baseline
is attached. Matching a territory type name alone does not authorize borrowing
fiction from a different holding.

## Context and one-time completion

At dispatch, the server includes accepted prerequisite prose in a separate
`existing_fiction` Context block, with logical IDs, dates and content hashes.
Authored background remains separate. Old generated backgrounds, prior entries
and observation prose are scrubbed from the generic legacy context; the accepted
dependency block replaces them. Existing prompt/source fields do not get promoted
into mechanical evidence.

New requests use a source-and-dependency revision. A changed prerequisite before
delivery causes HOLD, retaining the submitted draft. Observation references use
logical memory keys in the semantic fingerprint, so a new storage version of
the same observation does not manufacture a new writing need.

Baselines and rolling accounts have compilation timestamps. Those timestamps
are excluded from semantic revision checks: starting the app, a new day or a
guideline change alone cannot trigger another generation. Rolling histories can
receive one new request when factual inputs change. Static accepted entries are
protected. Source-unchanged accepted text is restored after projection rebuilds.

## Existing queue, claims and races

Schema 18 adds claim state, partial-text presence, policy version, priority rank,
dependency references and separately retained context supplements to requests.
The private relay sends protocol 2 snapshots of active/HOLD Sheet rows before
the server reprioritizes. Older relay clients do not authorize withdrawal of
unknown in-flight requests; update the bound script when deploying this release.

Unclaimed, empty PENDING requests outside the selected frontier become DEFERRED
in NCCE and DRAFT in the Sheet. Their IDs, original packets and source revisions
are retained. When eligible, the same request is reactivated; accepted continuity
is retained as a separate supplement to an existing version-1 packet.

WRITING/READY rows and rows with partially saved text are not withdrawn merely
for priority. READY deliveries are processed before polling for new requests.
A writer finishing at the exact deferral boundary can still deliver the saved
draft against its original facts; a second request is not invented for that
deferred logical slot. A duplicate/conflicting delivery cannot overwrite an
accepted entry. The Script rechecks row identity/status/text before changing it.

Writer HOLD is reflected into server HOLD, preserving the Sheet draft and
blocking automatic retries. Requests do not expire or reset on a timer.
The writer must not activate DRAFT rows or rewrite a PENDING row that already
contains prose. Those cases require recovery, not another generation.

## Visibility and limits

The relay writes a read-only **Queue status** tab showing each phase's total
derived slots, accepted count, remaining work, blocked prerequisites and retained
legacy/deferred counts. These are logical derived slots, not all authored records
or theoretical future fiction. The authenticated exchange diagnostics expose the
same plan. System prose coverage now sees retired old-ready text as earlier
drafts rather than completed prose after the first poll.

The five-entry queue and three-entry-per-writing-run limit remain. Changing the
writing policy does not modify the separate work-account hourly task. Scheduled
writing still requires actual connected-tool access in that account.

## Verification

### Operator report versus writer input (0.27.1)

`summary()` exposes all 16 `prose_progress.CATEGORIES` as `categories`, including
the two authored-only forms. Authored and total counts come from current prose
slots. Accepted counts require current exchange/pilot protection; old generated
ready labels do not qualify. To write counts unapproved derived candidates;
blocked is a subset awaiting causal prerequisites or recovery. Total slots can
include authored-only or retained non-exchange records, so do not infer remaining
work by subtracting accepted alone. The two authored-only rows say Not queued.

Apps Script renders Queue status after applying all status/export changes. Its
available-work section is an exact projection of Queue rows with a form,
PENDING status and empty writer_text_md. The full backlog is a separate explicit
16-form count table. DRAFT battle jobs are preserved in Queue for later reuse but
are absent from available work. This tab never drives eligibility or dispatch;
the server's existing dependency planner does. Writer instructions explicitly
exclude the dashboard as a source of jobs and retain the three-PENDING-per-run
limit. A dashboard refresh does not invoke a model or alter campaign sources.

Tests cover replacement of old ready prose, authored/pilot protection, baseline
gates and accepted context, source/causal dependencies, same-ID deferral,
preserved claims and partial drafts, lost-acknowledgement retry, client HOLD,
safe Script deferral, full queue draining and no requeue after forced regeneration.
All tests use disposable state and make no paid provider call. The real-history
copy test checks unchanged fighter/event/snapshot counts and phase-0-first output.
Hosted deployment and live queue reconciliation are recorded in the changelog.

## Hosted verification — 5 November 2026, 09:09 CET

Release source `4a8c3aa91eecd24c6f69edb1d6e2ebc49a24e9ac` is live. Real protocol-2 sync deferred five empty battle jobs and exported five baseline jobs, preserving both imported pilot receipts. The Queue status tab reports 1,332 remaining entries and 750 retained legacy projections. Private keys, the existing timer and authored sources were untouched. The hourly writer limit remains three; its scheduled tool access is not inferred from a successful relay run. Detailed release evidence is in HANDOFF_STATUS.md and CHANGELOG.md.
