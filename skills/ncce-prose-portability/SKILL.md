---
name: ncce-prose-portability
description: Source-grounded Necromunda NCCE writing: form-sensitive literary craft, independent faction/gang/individual voice, illustrative exemplars, owner-approved editorial learning and portable fresh-chat handoff.
---

# NCCE portable writing skill — runtime 2.1.0

Read `HANDOFF.md` for a fresh chat, and `PROCESS.md` for the CURRENT, tested NCCE pipeline. The canonical machine-readable literary source is `../../config/literary_profiles.v2.json`; individual identity is `../../config/voice_registry.v1.json`; mechanical/event authority always comes from the current campaign Sheet and exact writing context. Runtime literary resolution is `../../src/literary_policy.py`. These references remain separate; a literary exemplar never becomes campaign evidence.

## Every writing request

1. Identify the exact form and its contract in `../../src/writer_contract.py`. **New fighter biographies:** 1,900–2,000 characters including Markdown, hard cap 2,300; other forms have different constraints. Preserve accepted historic examples at their current lengths.
2. Read source facts, player-authored canon, accepted continuity, exact event times, and character awareness. Distinguish the facts known by a narrator from the in-world audience and document genre.
3. Resolve the actual **faction → player gang → individual** via NCCE's source-labelled `voice_layers`. An outsider attached to the host gang keeps independent voice. Palanite Enforcers is a faction; Kły Sprawiedliwości and Patrol do spraw alkoholu i broni are distinct player gangs. Unapproved Patrol voice stays neutral.
4. Apply the form's `literary_policy` block; select literary register by the actual speaking gang, audience and document purpose. For C-NINE, use archived dossiers only for records, not automatically for worker thought. For Kły, upper-rank reports attempt professionalism while pack priorities show through; internal operations are candid and individual.
5. Use at most 1–2 examples as **illustrative and non-exhaustive** craft references; never reuse anecdotes, template headers, quips, cadences or presumed events. If a form lacks exemplars, use the general form contract rather than claiming a pattern is mandatory.
6. Write one complete piece; verify source/knowledge, correct form, natural connected prose, exact full-Markdown character count when relevant, and no duplicated app-generated metadata. Diegetic service codes, Imperial dates, redactions and seals may be used when warranted.
7. Keep the saved draft **WRITING** until explicit owner approval. Recheck exact saved ID/revision/text before READY; only relay sets IMPORTED. Existing packets/prose are not rewritten when style policies change.

## Durable owner findings

When the owner establishes a durable correction, explicitly classify its scope (universal/form/genre/faction/gang/individual/workflow) and precedence. Perform a file update to the relevant canonical reference, add a dated decision record to `CHANGELOG.md`, increment `config/literary_profiles.v2.json` `policy_version` if runtime guidance changed, test, and produce a new verified portable ZIP. Report what was updated; do not claim chat memory or automatic background propagation. Unknown forms get their existing runtime fallback until the owner develops and accepts a new scoped literary convention. Latest owner instructions govern craft, not silent changes to campaign mechanics. 

For a fresh chat, supply the latest ZIP or the authenticated NCCE packet export and follow `HANDOFF.md`.
