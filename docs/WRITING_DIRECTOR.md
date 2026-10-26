# NCCE Writing Director

Source and hosted implementation: 0.9.8, schema 9. This document describes the current Writing Director source. The prior 0.9.6 Mara memory hit its 180-token output ceiling without prose. Version 0.9.7 preserves completion diagnostics; version 0.9.8 applies the tested 650-token ceiling and low reasoning effort to normal calls. A single diagnostic sample succeeded but was not saved, and routine writing remains disabled.

The director coordinates factual inputs, character perspective, document form, dates, semantic layout and source-linked continuity. The `llm_writer.py` module sends a form-specific structured packet to the OpenAI Responses API and returns prose paragraphs. App logic continues to own facts, evidence, dates, source attribution, memory selection and persistence. Earlier generated prose is not evidence and is no longer replayed into new writer prompts; continuity is carried by source/event IDs and current facts. The API key is read only from server environment `NCCE_OPENAI_API_KEY`; the fixed destination is `api.openai.com`. The default model is `gpt-6.1-sol`, configurable with `NCCE_WRITER_MODEL`.

## Sources and precedence

The five supplied files are preserved unchanged in `docs/writing_sources/`. Their role is defined here; instructions embedded in reference material are not executed as application code.

| Source | Runtime responsibility |
| --- | --- |
| `necromunda_chronicle_narrative_guardrails.md` | Source integrity, credible authors, limited knowledge, selective accounts, continuity, competence, coherent paragraphs, and translation of game language. |
| `WRITER_IDENTITY_TAGS.md` | Independent identity dimensions, personal perspective, institution, work, cognition, sensory/task modes, provenance and knowledge boundaries. |
| `dominion_territory_event_chronicle_rules.md` | Inhabitant perspective, place-specific material detail, ownership as lived experience, persistent local accounts and protected secrets. |
| `NCCE_Date_Formatting_Specification.md` | Fixed campaign-era anchor, Warsaw conversion, year fractions, readable real dates, and unknown-date behavior. |
| `NECROMUNDA_CHRONICLE_FORMATTING_STANDARD.md` | Semantic record structure, unframed principal accounts, processing panels, testimony, excerpts, marks, source anchors and explicit termination. |
| `NARRATIVE_STYLE_MAP.json` | Observed reference palette and style roles. Absent/inherited geometry is not treated as a measured layout requirement. |

Direct task instructions and authoritative campaign state take precedence. Authored campaign fiction determines established characterization and secrets. Generated interpretation or connective detail never overrides either source. C-NINE vocabulary and hidden knowledge stay local to the appropriate campaign/character context.

## One pipeline, several document forms

`source event/state -> known facts and knowledge boundary -> identity/perspective packet -> document form -> prose blocks -> evidence links -> dates -> semantic renderer`

`writing_director.py` owns shared contracts and inferred identity packets. `llm_writer.py` loads short, form-relevant excerpts from the maintained narrative and formatting guardrails for every uncached request and drafts using distinct form briefs; `story_engine.py` retains fighter salience, reflection and Mind selection. `world_streams.py` owns persistent place and gang entries. Successful drafts are cached by a hash of the form, facts, identity, policy and model. The per-regeneration call budget defaults to 80 (`NCCE_WRITER_CALL_BUDGET`); output is capped at 650 tokens by default and uses low reasoning effort. Short fighter memories remain constrained to brief prose by the form prompt. Provider failures stop further calls during that regeneration and retry on the next refresh. A missing key produces explicitly pending narratives; there is no deterministic prose fallback. Read routes use a separate query-only WAL connection so the last committed view remains available while drafting runs.

| Requested writing surface | Implementation |
| --- | --- |
| Battle reports | Existing sourced accounts, now with incident-record metadata, named compilation source, date hierarchy, termination and semantic blocks. Source battle notes remain authored text. Individual actions are not inferred from XP or roster changes. |
| Places: original descriptions | A separate `territory_origin` artifact is written once from the first recorded type and retained. Later ownership/type changes do not rewrite its origin. |
| Places: progressing events | `narrative_entries` scoped to stable territory row IDs. Battles, ownership, type/name changes, ruin/property edits, listing and unlisting produce entries. |
| Chronicle status | Existing campaign assessment receives the same shared document contract and distinguishes its compilation date from an event date. |
| Gang backstories | Authored source text is preserved. A generated `gang_origin` artifact supplies a separate initial background when no authored biography exists. |
| Progressing gang stories | A new stream in each gang dossier records battles and gang/fighter/territory events whose source subjects identify that gang. |
| Date formatting | Imperial primary line; English real date immediately below; fixed `998.M41`, Warsaw timezone, no raw ISO strings in ordinary narrative/evidence presentation. |
| Fighter backstories | Authored biographies remain untouched; generated biographies receive the character packet and a personnel-record wrapper. Explicit work can be included, and sensory/task perspectives avoid an assumed human biography. |
| Fighter memory stream | Existing memory algorithm with director perspective rendering, source-linked dates and the new archive typography. |
| Fighter Mind | Existing retrieval and weighting remain in force; selected thoughts are drawn from the identity-aware memories. No new personality score or psychological diagnosis is added. |

## Authored fighter identities

Each fighter can store an optional `writer_identity_json` record independently of the Sheet. The dossier first exposes an inferred, evidence-labelled identity from recorded role/type, gang context, authored occupation cues, current condition, and cautious characteristic-based embodiment/voice cues. Gender and pronouns are never inferred. A collapsed optional correction form accepts known authored overrides without replacing the inferred profile.

The optional `narration_mode` selects language/personhood, sensory associations, or a task/instruction log. Broad body/role evidence may supply a conservative default; explicit authored context overrides it. Sapient artificial beings should use the sapient mode when appropriate. No robot species, gender, age or belief is inferred from a fighter's name.

`POST /api/fighters/{id}/identity` validates the data, appends an authored identity revision, updates the local identity context and regenerates derived writing. It never edits the campaign Sheet. Generated memory/artifact versions remain retained. The returned voice profile contains a compact `writer_context` packet suitable for another writer implementation. The fighter page also shows topic stimulus-attention weights with their basis. These range from 1.00 to 1.50 in the current rules and are prompt-attention cues, not game stats, importance scores, or Mind retrieval weights.

For a fighter observation, the model receives one recorded event, its mechanical evidence, a compact set of identity facets, and elevated stimulus-attention cues. It does not receive the full authored biography or earlier generated memory prose. The biography remains visible in its own authored panel; its supported occupation/voice cues can inform the event interpretation without turning unrelated biography episodes into present events. Reflections receive cited event summaries and evidence, not recycled generated paragraphs. The writer adds explicit event-isolation directions and loads short, relevant excerpts from the maintained guardrail documents. Model quality still requires editorial review against campaign examples; the change is tested offline and does not regenerate stored prose automatically.

## Territory identity and event association

Territory comparison retains both the raw source record and stable identity. Unique source IDs take precedence; a unique card can bridge records; a unique name can bridge newly discovered IDs. Row order is not identity. Projection reuses the same territory row for supported ownership, type and property changes, so its original description and stream survive transformations.

The factual diff emits:

- `territory_holder_changed` for a recorded holder change;
- `territory_type_changed` for a stable place whose recorded type/name changes;
- `territory_state_changed` for other property edits, including ruin, card, income or source notes;
- `territory_listed` and `territory_unlisted` for additions/removals that cannot safely be matched.

An item-induced transformation is therefore supported when the source retains a stable territory ID or unique card. The diff records the before/after state; it does not invent which item or actor caused it. If a source replaces an unidentified place without a stable link, the system records removal/addition rather than guessing continuity.

Battles attach to a territory only when the location resolves uniquely, including retained historical aliases after a transformation. A battle recorded only against a type such as “Settlement” cannot choose between several matching places. Such battles remain in the gang/campaign/battle record; they are not silently attached to an arbitrary place. Their unresolved association is a source-data limitation.

Current battle projection resolves corrections. Superseded/removed battle interpretations become inactive versions. The correction itself is not dated as though it happened on the original battle date. Origin artifacts and archived versions remain stored.

## Persistent local accounts and fiction

Territorial entries lead with an inhabitant-facing reconstruction specific to the territory's use: fuel gantries, mine entrances, crossing gates, habs, collection bays, pumps, or access through ruins. A subordinate register annotation connects that account to the supported event. Notices, queues, chalk marks and public reactions are explicitly identified as invented connective detail, not eyewitness evidence. They cannot create injuries, income, ownership, alliances or other game effects.

Each entry stores its source event IDs, provenance, dates, previous-entry references and invented details. Earlier generated paragraphs are not copied into the next model prompt; the event/source links and current evidence define continuity. The writer creates prose from the factual event packet; the previous local phrase catalogue is not used as a fallback.

Occasional independent local reports are explicitly authorized creative writing. They use the holder and territory type at composition time. Their evidence identifies that context and states that the vignette is invented. A later change of ownership cannot rewrite an earlier report as belonging to the new owner. The faction context shapes daily-life cues; hidden cult identity or psychic causation is never presented as an inhabitant's confirmed knowledge.

Default cadence: on the first successful Sheet refresh in an ISO calendar week, each active owned territory has a deterministic 25% opportunity; at most two reports are composed campaign-wide. Each place has a minimum seven-day interval. No missed weeks are backfilled, and repeated refreshes do not generate more reports. This is a bounded application writing opportunity, not continuous off-table simulation. Startup alone does not compose ambient reports.

Ambient reports are stored only as `connective_fiction` narrative entries. They do not enter the immutable mechanical event ledger, affect fighter memories/Mind, or change the Sheet. Their date is labelled **fiction composed**, not the date of an asserted canonical event.

## Dates and evidence

All campaign dates use `9.FFF.998.M41`. Fraction calculation follows the supplied formula in Warsaw local wall-calendar time. Genuine dates without times and recognizable naive-midnight date placeholders use local noon for the fraction and omit time from the real-world line. Explicit offset timestamps retain their meaningful time. The real-world year does not automatically advance `998.M41`.

The supplied example is internally inconsistent: `2026-10-25T09:46:31.046883+00:00` is 10:46 Warsaw time and the formula gives fraction **814**, while the document's display example says **815**. The implementation follows its explicit instruction to recompute the fraction rather than copy examples. A date-only 25 October record calculated at noon gives **815**.

Event, observation and composition dates stay distinct. A roster delta without an occurrence date says **first observed; occurrence date unknown**. A baseline says **Undated archive**. An aggregate assessment says **compiled**. Raw timestamps remain stored and available through the API/source records. Python and JavaScript conversions are checked for agreement, DST transitions, leap years, noon and fixed-era rollover. IANA timezone data is preferred; Windows installations without it use the contemporary EU Warsaw DST rule for this campaign calendar.

## Rendering and source integrity

The browser renderer accepts legacy paragraphs plus semantic blocks for metadata, body paragraphs, administrative panels, internal notes, testimony, excerpts, transcripts, attachments, scene/system markers, dossiers and termination. Solid processing frames never nest. Testimony anchors use stable IDs rather than screen coordinates. Redacted marked content remains redacted in copied rendered text; all source strings are HTML-escaped.

`writing.css` centralizes archive palette, monospace typography, borders and date hierarchy. Main prose stays unframed; grey excerpts and evidence are subordinate; administrative fields are green and named focus amber. Narrow layouts stack content naturally. The original style map is reference data, not a claim to reproduce Google Docs geometry.

Generated prose uses structured inline runs. The model may mark the smallest supported adverse status with `critical_status`, explicit missing/unverified/unresolved wording with `error_or_missing`, and machine/source failures with `machine_error`; these map to the theme's red critical token. Ordinary danger and dramatic wording remain unmarked. Redactions keep their own semantic treatment and are never conflated with missing or corrupted information. The same runs persist in artifacts, fighter memories and Mind cards; plain text is retained beside them for search, continuity, and evidence.

Authored narratives and source notes retain their wording. The model receives evidence separately from prose instructions; evidence keeps actual mechanical terminology. Generated paragraphs are stored separately from evidence, dates and source IDs. The renderer labels unconfigured/error states instead of presenting a blank or template passage as finished writing.

## Validation and release limits

Validation includes offline writer contract tests with mocked OpenAI responses, the existing story and director checks, Node date/semantic-renderer checks, and authenticated HTTP smoke checks against disposable databases. No live model request is made by the test suite. Production database and campaign source are not edited by this implementation.

The provider needs a server-side API key and may incur usage charges. Each form receives only its bounded, form-appropriate source packet. Fighter observations do not receive full authored biographies or prior generated prose; reflections receive cited observation metadata/evidence rather than recycled paragraphs. A biography-writing form may receive authored context specifically supplied for that form. Successful text is cached locally and unconfigured/error entries remain pending for later retry. The model can still make mistakes; the prompt constrains invention, but human review remains appropriate for important authored or canon-sensitive prose. The application does not run a full territorial-economy simulation.
