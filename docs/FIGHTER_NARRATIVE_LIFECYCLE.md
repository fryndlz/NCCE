# Fighter narrative loop — NCCE 0.17.0

Schema 15. Current cognition uses the owner-approved [fighter event clock](FIGHTER_EVENT_CLOCK.md): 10 relevant changes per recency half-life, each distinct meaningful change one step, no fixed expiry. This specification supersedes the calendar rules introduced in 0.16.0.

## Four responsibilities

1. Biography establishes the particular person and stable formative background. Authored material always wins. Completed generated biography artifacts are retained across routine campaign and formatting changes. Unfinished baselines use the earliest available roster and its voice context; later XP, injuries and rank changes belong to memories.
2. Observations describe one supported experience from the fighter's perspective. Mechanics, importance and provenance remain separate. Gang outcomes are shared knowledge, not proof of attendance. For dated battle outcomes, the actual recorded battle date supplies the derived memory occurrence date instead of its import date; the source ledger is unchanged.
3. Reflections interpret connections between cited observations without inventing another incident. Existing batch eligibility remains two observations of importance >=4 and summed importance >=12, citing at most four. Production and Workshop use the same observation packet helper, with IDs, dates, facts, tags and ready prose only. Reflections no longer inherit an instruction to narrate one event, or a misleading first source event. This release does not implement an unbounded long-term reflection simulation.
4. Mind contains independently written current thoughts, one or two first-person sentences (12–40 words), not copied historical prose. Identity, authored background, attention weights, current condition and cited facts inform the thought. No invented incidents or mechanical outcomes. One call per missing thought when writing is explicitly enabled; no critic/variant calls in campaign generation.

## Current-thought causes and lifetime

`fighter_mind.py` ranks factual memory causes with the existing importance/recency/relevance/bias calculation. Baseline and unanchored causes are excluded. At most four candidates are selected, with one per reaction family. Battle/equipment families use their newest eligible cause; one current condition reaction replaces simultaneous critical/recovery repetitions. A source observation need not already have prose: its recorded evidence is sufficient, and stale historical wording is never fed as a positive thought example.

No fixed calendar or event-count expiry exists. Subsequent fighter-relevant events reduce recency; current relevance and explicit resolution determine selection. Formation is anchored to causal event position, not prose-generation or app-access time. Dates only order facts and serve UI/audit purposes. Deceased fighters have no current thoughts. Refresh persists active/resolved/superseded states; old expiry metadata is ignored and cleared. See the event-clock document for exact rules and paper deviations.

Cause keys include factual evidence/event IDs, current condition, authored background and explicit identity corrections, but exclude polling time and historical prose. Ready thoughts are reused rather than regenerated on every sync or policy edit. A changed cause/condition creates another version. Current source packets are inspectable; original paid prompts remain separately sealed in the request audit. Source memory links are updated when the same cause receives a new memory version.

## Persistence and API/UI

Schema 15 adds only the derived `fighter_thoughts` table and index. Every thought retains its source memory, factual event IDs/evidence, frozen packet, writer status, lifecycle and creation/end audit times; the legacy expiry column has no cognitive effect. Existing source/canon/Workshop policy tables are untouched. Startup's verified consistent pre-upgrade SQLite backup runs before the migration.

`/api/fighters/:id` returns ready, nonempty independent prose in `mind`, plus `mind_status` with pending/error/candidate counts. Empty, pending, failed or stale prose cannot occupy a visible thought card. The UI shows awaiting-writing status without repeating historical paragraphs. `moodlets` aliases the new current thoughts; old seeded rows remain in the DB and are explicitly exposed as `legacy_moodlets`, not current psychology. Each visible thought retains its trace-to-memory link and retrieval score explanation.

Reading dossiers never invokes the writer. Startup/manual/scheduled refreshes prepare derived candidates; ordinary automatic writing remains disabled. With it paused, this release creates pending candidates but spends no tokens. Existing historical prose is retained in the memory stream. No one-time full-roster regeneration is authorized by this release.

## Writing Workshop

The fifteenth form, `fighter_mind` / **Fighter current thoughts**, appears in category studies, guideline references/activation, source catalog, exact packet inspection, one-call draft generation, saved edits and Codex reviewer studies. `mind:<id>` samples use the exact frozen production packet; app-clock waiting cannot expire samples. Production uses the same active-contract resolver as every other form. Two independent source contexts remain required for a category study; no automatic activation occurs.

Biography, observation and reflection retain their separate categories. Authored biographies cannot become replacement draft targets. Reflection source selection now packages cited observations identically in production and Workshop. Owner-authored guidance/revisions remain unchanged; new form defaults do not activate a proposed policy for another form. Workshop output remains a private test, not automatically published campaign prose.

## Verification

Mocked regressions cover independent prose and reuse, pending suppression, read-only persistence, condition resolution/death and event-distance invariance, newest outcome, stable biographies, battle dates, exact reflection packet parity and Mind Workshop selection. Existing story, writer, planner, optimizer, bridge, guideline, frontend and authenticated disposable HTTP suites remain required. No live literary quality claim follows from mocked generation; owner review of a paid sample remains separate.


## Historical 0.16.0 release verification (not current timing rules)

Verified live 2026-10-28 16:08:58 CET: source `e5ec697`, deployment `dep-dbh0vjei0phs73aei7n0`, app 0.16.0 / schema 15. Startup verified consistent backup `/var/data/pre-schema-14-to-15-20261028T150832415224Z.db`. Hosted health/sync are healthy; writer calls 0. Mara’s 853-character authored biography is byte-for-byte unchanged; four independent thoughts await writing, with no stale/full-memory paragraphs shown as thoughts. Legacy moodlets remain separately exposed. Workshop lists 15 forms including Fighter current thoughts, with 162 current-thought source samples; Mara’s packet contains current state and cause links without copied old Mind prose. The browser DOM confirms the selectable current-thought study and the dossier pending state. No paid study, production policy activation or bulk regeneration was performed.

All 20 offline Python regression files and all four JavaScript UI suites pass, including the new lifecycle checks. Authenticated disposable live-Sheet smoke and Workshop HTTP gates pass. Model calls were mocked in writing tests. A real new literary sample has not been generated or judged as part of this release.
