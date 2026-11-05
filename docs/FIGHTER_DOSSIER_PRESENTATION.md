# Fighter dossier presentation — 0.28.6

**0.28.6 C-NINE printout exception:** fighter gang membership, independent of UUID
availability, enables full-width 11px Courier machine-print styling for Emperor
Protects, Filed under ... Archive, Further correspondence, No further action /
inspection required, The Day draws near, and the authored corrupted `no fURTHer
ActIOoon REerquide`. Preserve exact wording and case. These lines close any
indented section. Thought for the Shift and its following quoted motto (across
blank lines if needed) form one unindented machine-print block; it may wrap
naturally on small screens. A motto already on the same line stays there.
Other gangs, and Thought for the Voyage, retain their existing presentation.
Source text is not edited, and no model call is involved.

Implemented 5 November 2026. This specification supersedes the Orik-only
formatting exception and older Google-Doc biography imports.

## Biography authority

The fighter's `Backstory` field exported from Munda Manager through Krakamunda
is the only source of an authored fighter biography. Import its exact text;
formatting does not rewrite words or add adjacent dossiers. A nonempty source
always supersedes the previous generated or C-NINE Doc projection.

`fighter_backstories.reconcile` runs after projection and before story
regeneration/startup. It repairs persisted databases using `mechanics_json`,
without waiting for the next successful remote refresh. The old seed's
`c9_record` extraction and its alias list have been removed. The previous
projection's text/source are preserved once in `provenance_sources` audit
metadata under `retired:fighter-backstory:<hash>`. No source file is edited.

An explicitly empty Backstory clears a previous MM-authored biography. An
omitted field preserves the last MM-authored biography. A legacy Doc/canon
biography is retired even if no MM biography exists. Existing generated or
accepted external prose remains available when no authored MM text exists.
No new generation is requested by this change. Archive stories and documented
battle reports/addenda continue to use their separately registered sources.

## Presentation

`fighterBackstory` selects MM-authored text before generated documents. The
shared `authoredDossier` parser handles authored text, external Markdown, and
the textual content of retained structured biography documents. Stored source
text and structured documents are unchanged.

- No redundant Backstory introductory sentence.
- Surname/name dossier headings use uppercase 13px Courier with letter spacing.
- Metadata label/value pairs remain a grid; labels are uppercase. Preserve
  each subject's own labels, not a universal C-NINE labour classification.
- Body prose uses the existing paper's 17px Georgia and 1.8 line spacing.
- Incident, commendation, requisition, annotation, attachment and similar
  headings use uppercase 11px Courier. Each opens its own section, indented
  exactly 18px. The next heading closes the previous section, without nesting
  another level. Blank lines end paragraphs, not the enclosing section.
- Dividers/addenda/termination lines close an active section and return to
  the full-width level. Quoted testimony retains italic blockquote styling.
- Source labels, provenance and mechanical evidence stay in the app's source
  layer; the parser adds no fictional claims, dates, jobs or classifications.
- Text is escaped before limited inline formatting. Structured redactions stay
  redacted. No arbitrary source HTML is executed.

## Printed identifier

Each available identifier is a single centered `<gang>-MK/<suffix>` below the
dossier. It is app-rendered metadata, not text inserted into the authored source.
Old source watermark lines are replaced in presentation, not used as identity.

`personnel.identity` accepts a valid UUID from explicit MM `Fighter ID`,
`fighter_id` or `source_fighter_id` fields. Otherwise it uses an unambiguous
UUID from the imported MM activity archive, joined by exact normalized gang ID
and fighter name. Multiple different UUID candidates produce no code. A local
integer ID, a redacted identifier or an old Doc watermark is never a substitute.

Suffix: last four UUID **characters**, retaining source case. Prefix: lowercase
representative gang letters. Current mappings: C-NINE `c9` (owner exception),
Slag Eaters `se`, Kły Sprawiedliwości `ks`, Ethernetans `et`, Helmaeth `he`,
Patrol do spraw alkoholu i broni `pa`. New gangs use the first letters of two
meaningful words, or the first two letters of a single word. Common connector
words are ignored. Unknown/ambiguous IDs leave the printed code blank; Data &
sources explains that the UUID is unavailable.

Live export check on 5 November: 92 fighters, 21 MM-authored biographies,
15 verifiable UUID codes. Most current roster rows do not expose a UUID;
completing those codes requires additional upstream ID data. This release does
not change the authoritative workbook or scraper to obtain it.

## Palette

The active visual rule is muted paper and ink, inspired by Papers, Please.
No monitor/neon green. Paper metadata remains olive/grey ink; machine/error
lines use rust `#88614c`; marked errors use plum `#865b70`. Dark-surface
administration/identity use muted `#b8ba94` / `#c3b891`; dark system lines use
`#bb987c`. The historical Google Docs colour inventory is reference evidence,
not the app's current palette. Timeline geometry and gang colours are unchanged.

## Verification and limits

Source regressions cover MM overriding contaminated Doc text, exact whitespace,
missing/empty fields, audit idempotence and retained generated prose. Identifier
tests cover UUID suffix/case and missing IDs. Frontend regressions cover Orik,
bounded Jarek-style sections, metadata, quotations, external biographies,
escaping/redactions and removal of the former neon colour declarations.

The live export's It That Spoke Backstory matches the repaired projection
exactly and contains neither Marcella's appended dossier nor the Doc's retrieval
animation. All 20 Python / 10 JS suites and authenticated/live-source HTTP smoke
pass. No signed-in browser visual verification is claimed: browser access is
disabled in this environment. Deployment status is recorded in HANDOFF_STATUS
and CHANGELOG. No provider calls, source writes or schema changes.
