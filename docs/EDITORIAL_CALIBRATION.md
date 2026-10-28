# Controlled writing experiments and reviewer calibration

Development source 0.18.0, 29 October 2026. Schema remains 15. This replaces score-based qualification for new Workshop studies. It does not activate new production instructions or regenerate campaign prose.

## What changed

The owner rejected both Palanite drafts and preferred the Luna draft for Mine Workings and Bone Shrine. The independent reviewer instead preferred Sol on all three and accepted Palanite A at 8/10. The problem is demonstrably reviewer alignment as well as the writing setup. More favourable model scores are not evidence that the owner will like the result.

`data/editorial/owner-contract.json` records the owner's actual feedback, the unchanged historical drafts, explicit editorial rules and short tone anchors from the supplied Core Rulebook. Source identity is SHA-256 verified; printed pages 175 and 179 were checked against rendered PDF pages 176 and 180. Anchors are style references, not campaign facts or evidence of an exact voice match. Historical examples receive **zero** fresh calibration credit. The contract applies directness/clarity without imposing an institutional narrator on personal prose.

The Workshop displays standards and calibration in a collapsed reference near the bottom, above guideline history. The category's current calibration message is also visible beside the study controls. An editable candidate brief and hypothesis are available before authorizing an experiment. Territory candidates keep the territory's role central and permit an empty closing rather than requiring an administrative afterthought. Other forms preserve their built-in viewpoint and factual limits. Candidate prompts are private revisions; active policies are unchanged.

## A complete controlled round

1. Freeze the current active shared/form pair as the baseline, and select a concrete candidate and hypothesis. Identical instruction arms are rejected before calls.
2. For each of two distinct source entries, generate one baseline and one candidate draft. Randomize A/B assignment independently per entry. Model, reasoning, limits and the complete provider input packet match between arms; instructions differ. Actual request audit tests verify identical input strings.
3. One independent Codex review per entry judges both drafts against the owner contract, without the arm mapping. It explicitly checks subject, clarity, register and closing; marks each acceptable or rejected; selects A/B/tie/neither; and explains the change, target problem, observed effect and regressions. Numerical scores remain advisory. Review two receives review one and consolidates reusable category guidance across entries. Later jobs receive previously sealed owner corrections and their drafts, never current hidden owner labels.
4. A candidate must be acceptable and preferred or tied against the baseline on both entries. A high score cannot compensate for a failed owner check or a losing comparison. Failing experiments save inactive general instructions for the next fresh test. Individual drafts are never rewritten.
5. An uncalibrated reviewer pauses the run after a complete round. The owner sees prose and records a blind preference, separate acceptance choices and optional explanation before the assessment and A/B identities are revealed. Choices are immutable and idempotent. The normal UI/API view withholds the review and mapping until that pair's vote. This is an editorial blinding workflow, not a security boundary against an owner deliberately inspecting private audit/history endpoints.

The owner can finish, inspect findings, request an investigation, or resume remaining previously authorized rounds. Once the allowance is used, continuing requires another explicit whole-round grant. Four writer requests plus two Codex reviews cover a round, including validation. No idle model polling, automatic retries, model/provider switch, or extra synthesis call is added. Invalid responses, failed requests and stops preserve consumed reservations and do not replay.

## Prospective agreement gate

Calibration is per prose category and bound to a fingerprint of the owner contract, reviewer thread, rubric and protocol. Initial thresholds are engineering defaults, not statistical proof of literary reliability:

- At least three fresh owner-labelled pairs.
- At least 80% exact A/B/tie/neither agreement in the latest ten eligible pairs.
- At least one correctly rejected **neither** pair.
- No unresolved false acceptance of a strong rejection. Such a failure immediately revokes trust and resets eligible evidence to the subsequent pairs; old successes cannot hide it.

Duplicate source packets do not earn fresh evidence, even across studies. Contract/rubric/thread changes invalidate prior qualification. Evidence is kept in append-only `system_state` verdict records with review hash, sealed timestamps, form, source deduplication key and private mapping. Existing schema is sufficient. Later owner corrections become training feedback only after their independent verdicts were sealed; an already judged source cannot be recycled as a fresh holdout.

No category is advertised as calibrated at installation. The three historical examples are already exposed training material. Real prospective agreement still needs owner-labelled fresh comparisons, and the rejection check may require additional examples if no new pair merits rejection. Different examples and longer observation remain necessary before treating this small gate as strong reliability evidence. Changes to the native reviewer's model/settings are not detectable automatically unless the thread/rubric/contract fingerprint changes; changing those requires a new calibration contract/version.

## Validation and activation

A passing candidate is frozen for a separate complete round on fresh source entries. Its prompt and editorial reminders stay unchanged. Activation rechecks calibration, contract/reviewer fingerprint, environment, active policy pointers, source hashes, the exact candidate revision and the owner's blind acceptance/non-loss on every validation pair. Approval commits only the exact tested shared/form pair. A later critical miss blocks an otherwise ready study. Legacy score-based studies retain their history but cannot qualify for activation through the study endpoint.

The historical guideline library remains an explicit **manual owner override** for selecting an exact old version or proposal, including rollback. Its confirmation explains that this is not calibrated study approval. No model can use the owner-authenticated activation routes, authorize spending or promote its own proposal. Manual selection remains separate from study qualification.

## StoryTechMan and ordinary allowance pauses

Existing evidence-backed context/technical/permission escalation remains immediate, even on entry one. Writing pauses and a read-only investigation is queued. The app presents findings, proposed changes, questions and validation plan. Approval permits development/tests; separate approval of the tested report permits release. A released systemic repair requires a new category study. Ordinary allowance completion remains a continue/finish/investigate choice and never automatically dispatches StoryTechMan or claims API credits ran out.

## Verification and release scope

Offline tests use disposable databases and fake writer/reviewer outputs. They cover actual provider request serialization, blinding/reveal, immutability, duplicate evidence, prospective calibration, stale contracts, strong-rejection revocation, fresh unchanged validation, exact activation, bounded reservations, legacy safety, authenticated HTTP controls, owner cross-origin protection, UI rendering and existing technical handoffs. No real writer/reviewer calls, active policy changes or campaign-source edits are required to validate the implementation. Actual literary calibration is a separate observed result, not something mocked tests can certify.

Relevant modules: `editorial_quality.py`, `workshop_experiments.py`, `workshop_optimizer.py`, `codex_review_queue.py`, `workshop.js` and `writing_activity.js`. Tests: `test_editorial_quality.py`, existing Workshop/bridge/HTTP suites and the Workshop/activity JavaScript suites.
