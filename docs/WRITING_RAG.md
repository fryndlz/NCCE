# Writing context and retrieval (RAG)

Owner request, 29 October 2026: build retrieval for NCCE writing with full browser visibility and control. No blind A/B experiment or new literary acceptance workflow is part of this feature.

## Research and implementation choice

The architecture follows [Lewis et al., Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401): retrieve external passages, retain provenance and supply the selected context to the generator. The paper trains a dense neural retriever and generator. This implementation **does not reproduce that training, dense embeddings, RAG-token marginalisation or semantic vector search**. It deliberately uses a deterministic local BM25 passage retriever over the small NCCE corpus, with no extra model calls, embedding costs, external index service or credentials. The GUI names the method explicitly. Lexical retrieval can miss synonyms; owners can inspect real queries and prioritise relevant sources.

[Microsoft's RAG design guide](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide) discusses chunking, metadata enrichment, full-text/vector/hybrid choices and inspection of pipeline stages. NCCE applies versioned documents, overlapping bounded passages, category/entity filtering before ranking, deterministic relevance scores, duplicate suppression, context budgets, source retirement, immutable input records and explicit no-hit behaviour. Functional tests exercise these invariants; they do not claim improved literary quality.

## Browser controls

Open **Writing context** in the main navigation, or `/#retrieval` on the authenticated preview.

- Source library: inspect full text, provenance, scope, locator, version and exact indexed passages. Include/exclude and prioritise sources. Prioritisation respects category/entity filters and context budgets.
- Owner documents: add/edit notes, illustrative examples and general references; paste text or import `.txt`/`.md` files. Maximum 60,000 Unicode characters per owner document and 100 owner documents. Previous versions remain inspectable; saving earlier contents restores them for future requests. Authoritative imported sources are read-only.
- Pipeline settings: enable/disable optional retrieval, adjust passage count, context character budget, passage size/overlap and relevance threshold. Required writing instructions and the authoritative subject packet remain supplied. Examples embedded in the explicit writing instructions are controlled in Workshop; the library controls retrieved copies.
- Preview: select a real subject or enter a manual query. See current required instructions, subject packet, selected passages, scores/matched terms, source versions, exclusions and budget decisions. Preview performs no model call and changes no data.
- What the writer received: browse requests, inspect the exact saved instructions, complete input packet, model/schema/limits, actual token usage and frozen retrieval audit; export JSON. Old inputs are never reconstructed with today's sources. Unsealed controlled comparisons remain hidden until the owner verdict on that pair.

## Source authority and freshness

Maintained tone examples and type-specific style demonstrations are illustrative. Imported C-NINE authored lore remains read-only canon and is restricted to its named subjects; undated authored lore is excluded from event/history forms to prevent importing later incidents into earlier accounts. Current mechanical facts remain in the normal authoritative packet, not a fuzzy search result. Unverified general references cannot establish campaign events.

Only fully judged studies with completed feedback consolidation contribute owner corrections and labelled draft pairs. Preference and each draft's publication acceptance remain separate metadata in every selected example passage. Rejected drafts never become canon or positive examples by implication. Current mandatory guidelines supersede older feedback; raw source text cannot override the instructions. Retrieval text and authority boundaries remain distinct from those instructions. These measures reduce contamination risk; they do not guarantee a model will never misuse a passage.

Sources refresh on application startup, completed feedback and explicit Refresh imports. Stable source IDs retain owner selection controls, content hashes identify immutable versions, and sources absent from current imports retire from retrieval while retaining their audit history. No scheduled/model-driven indexing was added.

## Integration and storage

`writing_rag.py` uses the existing durable `system_state` store with separate namespaces for sources, immutable versions, settings/control history, current import membership and frozen search audits. No schema migration or external service is required. Planner keys include the corpus/settings revision. Context is frozen in the shared planner before an A/B pair, so both arms receive identical retrieved inputs. All production/Workshop writing paths use the common writer hook. An old prepared packet is rejected before spending if the corpus/settings changed; the owner must inspect a fresh preview.

Only the selected passages and provenance go into the model packet. The full selection/exclusion audit stays local and is referenced by immutable snapshot hash. Existing `writer_request_details.prompt_json` records the actual serialized provider body without authorization headers. The GUI reads that body, rather than guessing from today's data. Failed provider attempts retain existing auditing; a cache hit is not represented as a new provider call. Legacy requests lacking an audit say so.

RAG routes reuse Workshop authentication, same-origin checks and the writer-busy guard. Reads use read-only database connections. Changes require version/revision comparisons to reject stale edits. Source/campaign/canon originals are never edited. Paired-study blinding and existing bounded writing allowances remain in effect.

## Verification

`test_writing_rag.py` covers actual serialized provider requests with fake transport; source scope/authority, no hits, owner pins/exclusions, chunk offsets/dedup/budgets, immutable source versions, stale configuration and spending rejection, disabled retrieval, retired imports, completed-feedback labels, blind history protection and undated canon isolation. Existing writing/planning/calibration/native bridge regressions remain applicable.

`smoke_rag_ui.py` uses an authenticated disposable database and Chrome, blocks external browser traffic and simulates the single audited provider response. It exercises real-subject/manual previews, owner source editing, escaping, exclusion, settings/off switch, immutable request inspection, export, navigation, mobile bounds, auth/origin/busy gates and read-only previews. No live writing or model calls are needed to verify the feature.
