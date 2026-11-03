# Record navigation — revised 3 November 2026

## Current organization

The sidebar and searchable entity index remain. The selected record has a
persistent identity heading and its own section navigation, not one long document.
Only one record section is shown at a time.

| Record | Sections |
| --- | --- |
| Gang | Backstory · Timeline · Fighters · Holdings · Data & sources |
| Fighter | Backstory · Timeline · Memory · Mind · Data & sources |
| Place | Description · Timeline · Battles · Data & sources |

Backstory/Description opens first for a newly selected record. It contains only
the existing static baseline prose, with the parchment treatment and archive
stamp. Nothing in Timeline, Memory or Mind is appended to this baseline.
No backstory or historical prose is generated or rewritten by navigation.

## Evolving history

Timeline is an entity-local chronological event list, newest recorded/occurrence
time first. Rows show the existing Imperial and real dates, a type label and a
short title; opening a row reveals its account or mechanical details. Unknown
occurrence dates remain unknown; first-observed dates are not recast as known
occurrence dates. Narrative and factual rows retain their distinct labels.

- A gang's Timeline contains its existing local narrative entries and imported
  gang activity. If imported activity is unavailable, its recorded battles are
  used as the factual fallback. Existing aggregate campaign/downtime accounts
  live in a separate expandable section inside Timeline, not Backstory.
- A fighter's Timeline contains imported fighter-specific activity, falling back
  to tracked campaign changes when necessary. Additional tracked changes remain
  separately available when imported activity is present.
- A place's Timeline contains its existing local narrative entries and related
  recorded battles. Its Battles section provides direct access to battle reports.
  This uses the existing place/battle association; it does not invent ownership
  history or infer an otherwise unknown event.

The source streams are not rewritten or silently merged into a single new fact.
Different records of an incident can coexist with their existing provenance.
Per-event evidence is kept with that entry in a Recorded basis & sources
disclosure, outside its prose surface. It is not detached into an unlabelled heap.

## Fighter cognition

Memory contains the existing voiced observations and reflections, newest first.
Baseline memories are in a separate disclosure explicitly labelled as background
known at the beginning, not newly dated incidents. Observation/reflection labels,
importance details and evidence remain accessible.

Mind contains only existing ready current thoughts/moodlets, plus honest pending
or empty-state messages. It does not copy memories, invent filler thoughts or
change cognition rules. A thought's memory link selects Memory and opens any
containing baseline disclosure before scrolling to the cited entry.

Data & sources contains current mechanical state, baseline provenance, inferred
voice/identity and stimulus weights, existing known-detail correction controls,
source records and existing diagnostics. These are not part of the backstory or
current-thought prose.

## Navigation behaviour

- Section controls wait for initial campaign data before becoming usable, preventing
  early navigation from reading an unloaded roster.
- Section labels include available counts. Mind's count is ready thoughts;
  awaiting-writing counts remain explicit within Mind.
- The selected section survives ordinary data refreshes for the same entity.
  A different entity opens on its baseline. Identity/status stays visible above
  the sections; the selected fighter index status updates with the record.
- Arrow keys cycle all section tabs; Home/End select the first/last. Narrow
  screens allow the local tab strip to scroll without making the page overflow.
- Cross-record detail views retain a return-to-index control. Gang Fighters and
  Holdings sections keep the existing fighter/place links and search action.
- Battles, authored Archive reading, Writer Workshop and Writing context keep
  the prior pass's presentation; this revision is scoped to entity organization.

## Boundaries and checks

The main Chronicle timeline's renderer/control source remains byte-for-byte
unchanged: SHA256
`5a9a12d0d35e316dd28a3fef723ed3c2fb289479c4b9948dc28d7600a573931f`.
No engine/schema, campaign/canon, writer policy, model request or inference-rule
change is included. The unrelated unfinished category-population work is excluded.

`tests/test_record_sections_ui.cjs` checks section separation, unchanged authored
background, chronology, sourced dates, baseline memory grouping and thought links.
Existing archival, semantic writing, campaign timeline, Workshop and activity
contracts pass. The disposable authenticated browser confirms section switching,
refresh retention, a clearly labelled test thought's memory link, gang roster and
holdings navigation, place sections, no console errors and 390px layout bounds.
The test thought exists only in the disposable preview database; it was not
written to production or generated by a model.

Source complete: 3 November 2026, 11:24 CET. Hosted verification pending.
