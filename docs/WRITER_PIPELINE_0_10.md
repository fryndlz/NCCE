# Shared narrative pipeline — NCCE 0.10.0

Design checkpoint: 2026-10-26 19:40 CET. Schema 10. Applies to all 13 writer forms, not only territories.

## Responsibilities

`writer_contract.py` selects a common runtime contract, a form brief and a relevant positive example. `WRITER_RUNTIME_CONTRACT.md` is the complete maintained runtime writing specification. The longer source documents remain design references; they are no longer concatenated into every request. The runtime specification resolves their conflicting invention rules explicitly. Examples are labelled illustrative and never imported into campaign canon.

`narrative_context.py` builds packets with separate mechanical evidence, authored background, event sequence and generated continuity. It excludes old template paragraphs, application statuses, source/compiler boilerplate and legacy-policy generated prose. Supported earlier stories remain fiction with IDs, not mechanical evidence. Up to four preceding accepted entries are included. A same-time/undated entry cannot silently become an earlier event. Fighter voice lenses use a historical snapshot where available; unknown historical traits stay absent rather than borrowing today's injury, rank or loadout. Authored background can guide voice without its incidents becoming current events.

`llm_writer.py` makes one Responses request per uncached entry. Personal memories/reflections return semantic paragraphs. Other forms also return `composition`: heading, subject, body heading, closing label, closing text and signoff. These are textual fields, never HTML. The app owns reference IDs, Imperial date conversion, provenance and evidence. Model-written metadata cannot overwrite those fields. The same contract is used for production and previews.

`world_streams.py` rebuilds sourced gang/place entries in source-time order. Hardcoded chalk/queue/notice reconstructions and faction-selected ambient plots have been removed. Historical territory ownership comes from the latest matching snapshot at/before the event, or an explicit event after-state. Before the earliest matching snapshot, ownership is unknown. The current holder is not retroactively assigned to old events. New-policy origins supply fictional continuity; old drafts remain visible as stale where applicable, but are not prompt seeds.

`writing_director.py`, `web/app.js` and `web/writing.css` render structured documents. Real dates sit in the app wrapper, with Imperial dates in the diegetic header. Generated/player-authored attribution and mechanical evidence are outside the prose. Existing authored dossier parsing and safe escaping remain in place. Gang and territory campaign accounts now have a visible section in their details instead of being generated but hidden behind their origin.

`writer_preview.py` is an editorial runner using the production writer. Its general runner accepts one to four entries of any supported form. The initial fixture uses one territory: baseline, an actual sourced contest/ownership event, fictional ambient incident, and hypothetical type change. Hypothetical entries are explicitly labelled and never inserted into campaign events, territories, memories or normal narrative streams. They are saved under `system_state` and displayed in System. The command requires `--execute`, a configured server-side key and an unused revision claim; default invocation prints only the plan. It stops on the first failed entry without spending on dependent entries. No new paid HTTP endpoint was added.

## Invention rules

| Category | Fixed | Permitted fiction |
| --- | --- | --- |
| Baseline | Authored canon; subject identity; known mechanics | Compatible formative work, built environment, customs, local history, minor characters and habits |
| Event | Who/what/when/outcome actually established; unknown causes stay unknown | Subjective reactions, everyday actions and local physical/social consequences without new game effects |
| Ambient | Established setting, knowledge boundary, historical holder | A complete small incident, with no campaign-state mutation |
| Reflection | Only cited memories; no invented new events | A particular present concern or intention connecting those experiences |
| History/report | Source sequence, participants and outcomes; no invented deployment/tactics/casualties | Context, compatible aftermath, atmosphere and situated interpretation |

Generated details can be stated naturally inside fiction because the application labels their provenance. They cannot override authored canon or prove game events. Sharing a faction does not give every subject the same personality, institution or vocabulary. First-person memories do not inherit an Administratum voice.

## Source-guide coverage

| Source requirements | Runtime/code responsibility |
| --- | --- |
| Narrative guardrails §§1–4, 9, 15, 24: source hierarchy, knowledge, battle fidelity, mechanics, revelations, retcons | Common authority rules; explicit packet layers; evidence remains outside prose; source/canon preservation tests |
| §§5–8, 11–16, 20–23, 25–26: selection, competence, character, continuity, speech, rhythm, material consequences, event isolation | Common craft rules, form briefs and positive examples; bounded historical context; fighter one-event packets |
| §§10, 17–19: appropriate forms, plausible attachment authors, added perspective | Document composition schema and common craft requirements; no forced closing joke or redundant attachment |
| Identity tags: embodiment, faction, work, authored cues, no guessed identity | Existing identity inference and explicit authored corrections; historical voice lens; common perspective rules |
| Formatting standard: semantic text, palette, frames, dates, redaction, accessibility | Existing renderer plus composition support; allowed inline marks; escaped text; no model CSS/HTML or date arithmetic |
| Territory guide: inhabited places, persistent local details, nonmechanical incidents, ownership and chronology | Same shared contract; place-specific form brief; sourced historical holder; ordered accepted continuity |
| Date specification | Python/JS date converter and wrapper; model forbidden to write dates/references |

This is an explicit runtime redesign, not a claim that the model is reading the full reference manuals. Prompt tests check that the new shared contract reaches every form. Literary quality still requires reviewing actual output; code can check structure and clear leaks, not guarantee good prose or complete factual entailment.

## Calls, cache and audit

Default model remains `gpt-6.1-sol`, reasoning effort `low`. Personal outputs retain a 650-token ceiling; documents default to 1,800 tokens including structured output/reasoning. `NCCE_WRITER_MAX_OUTPUT_TOKENS` can override the ceiling (128–4,000). Form word targets are prompts, not truncation. The default call budget remains 80; the editorial preview caps itself at four.

The local cache key includes form, exact packet, model, reasoning effort, runtime contract fingerprint and revision. Successful composition is cached with paragraphs. A failed signature is not retried within the same run; unrelated entries may proceed. No second model critic or best-of-N selection is used. Provider authentication errors stop subsequent calls. Exact identical accepted work can be reused without a paid call.

Schema 10 adds `writer_request_details` linked to schema-9 `writer_requests`: prompt hash, contract revision, effort, cached-input tokens, reasoning tokens, full request body without credentials, raw response and parsed draft. Rejected/incomplete responses remain available for server-side diagnosis; they are not published or placed in the successful cache. Both failed and successful token usage contribute to run totals. Provider-cached input is distinct from application result-cache hits. The shared static instruction prefix is eligible for provider caching, but actual cached-token counts, not eligibility, establish savings.

No raw prompt/response HTTP endpoint was added. Credentials are not part of stored request bodies. Database access remains private to the service. Very old requests cannot be reconstructed retroactively.

## Operating procedure

On the existing service, inspect the bounded plan:

```sh
python src/writer_preview.py --territory-id <existing-id>
```

An explicitly approved preview can be executed once per revision:

```sh
python src/writer_preview.py --territory-id <existing-id> --execute
```

Inspect System → Writing preview. Review the baseline for specificity and voice; verify the real event preserves facts; check that the ambient incident develops naturally and the transformation expresses a physical change without invented mechanical cause. Check that headings and remarks add meaning, examples have not contaminated campaign names, and no model/provenance language appears inside prose. Keep routine writing disabled until editorial review. Do not infer mass-regeneration approval from approving a preview.

## Limits

The writer still uses the factual event ledger, not the full raw Munda archive. Historical snapshot gaps remain explicit. Fictional continuity is bounded, not an unlimited semantic memory. Current-rule responses are eligible for continuity after technical validation; that is not an independent literary endorsement. A shared contract does not promise equal quality from every form: fighters, gangs and battles need their own small editorial checks before bulk replacement. No campaign-wide regeneration is part of this release.
