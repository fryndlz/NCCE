# Six-call editorial comparison — 0.10.1

The owner approved six calls on 26 October 2026, after rejecting the 0.10.0 pilot. The reported failures were vague suggestion in place of an evocative picture, narrative space devoted to inconsequential details, and a Bone Shrine reduced to a passage/bridge safety problem.

## Hypothesis

The current writer's emphasis on concrete everyday detail is insufficient. It needs to select details for significance, proportion and the subject's primary identity. The candidate teaches those choices through a revised common craft section, short annotated failures and examples of developed consequences. It applies to all fourteen forms. It is experimental and does not replace the production contract.

Authority, permitted invention, authored precedence, chronology and presentation requirements are identical between versions. Model, effort, schema and per-form output cap are held constant. The candidate reuses the approved illustrative territory demonstrations and supplies different personal/collective examples. This tests the editorial instruction package as a whole; it cannot identify the effect of each individual sentence or example.

## Cases and controls

`writer_comparison.py` builds three source-backed cases: a territory contest, Mara Kel's critical-injury memory, and the recorded winning/claiming gang's account of the contest. Ledger events or an exact immutable battle snapshot supply evidence. Historical voice inference, identity/stimulus attention and authored background use the production packet builders. Prior generated pilot prose is excluded so the bridge story does not dictate either version. Unknown historical ownership stays unknown.

Each case produces two fresh requests with byte-equivalent serialized packets. Only `instructions` differs. A run identifier is shared within each pair to avoid accidentally reusing earlier result-cache entries. Each output is retained; there are no model graders, replacement attempts or winner selection. Technical errors remain errors and are audited. Independent cases continue unless the provider's auth failure has stopped the writer. Six is a hard maximum, not a promise to retry until six successes.

A/B placement is randomly assigned separately for each case. System → Writing comparison presents both versions and shared evidence without revealing prompt identity. Assignment can later be resolved from the private request audit's subject key and contract revision. No assignment state is included in the dashboard. The reviewer should compare each pair separately; A does not necessarily identify the same prompt across pairs.

## Review criteria

1. Can the reader picture a specific place, experience or gang life?
2. Do selected details reveal character, culture, stakes or consequences?
3. Does the subject retain its primary identity and purpose?
4. Does the entry develop rather than repeat a prop/routine or append vague menace?
5. Is voice natural and appropriate to this subject?
6. Does the entry preserve supplied facts, chronology and authored material?

Ask for a preferred version, neither, or tie for each case, with one or two decisive reasons. Do not publish or promote a prompt based on technical success. Three pairs are an editorial diagnostic, not a statistically reliable quality benchmark.

## Persistence and operation

`writer_candidate.py` constructs the experimental contract from unchanged production authority/presentation plus `writing_sources/WRITER_EDITORIAL_CANDIDATE.md`. `llm_writer.write` accepts an internal prompt override; exact contract text participates in the cache hash and the audit retains the real prompt and experiment revision. The default call path remains unchanged.

`writer_comparison.py` is a server-side command. It saves only comparison documents and usage in `system_state`, with a one-use atomic claim under `writer_comparison:editorial-selection-v1:claimed`. Source records, canon, normal memories and published narrative streams are untouched. No new paid HTTP endpoint is exposed. Automatic writing remains disabled.

```sh
python src/writer_comparison.py --territory-id 19
python src/writer_comparison.py --territory-id 19 --execute
```

The first command prints the plan without calls. The second executes the approved bounded experiment once with the server-side key. Provider usage, including failures, cached input and reasoning tokens, uses the existing schema-10 ledger.

The hosted experiment completed at 2026-10-26 21:23:56 CET with six successful calls, 13,674 input / 1,299 output tokens, 47 reasoning tokens and no cached input. The exact saved API bodies differ only in instructions within each pair. All results are displayed for blind owner review; no winning prompt has been selected. See CHANGELOG.md for run/deploy identifiers and preservation checks.
