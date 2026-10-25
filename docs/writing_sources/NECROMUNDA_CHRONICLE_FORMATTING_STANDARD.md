# Necromunda Campaign Chronicle Engine — Narrative Formatting Standard

**Version:** 2.0  
**Scope:** Global visual and structural rules for narrative output in a standalone Necromunda campaign chronicle application.  
**Audience:** LLM authoring agents, Codex, renderer/UI implementers, and content editors.  
**Status:** Design specification. The C-NINE chronicle is the reference implementation, not the only campaign the engine may support.

## 1. Purpose

Present campaign events as an accumulating body of in-universe records: battle reports, incident investigations, transcripts, administrative decisions, personnel dossiers, supplementary evidence, and corrupted machine output. The experience should resemble retrieving material from a dysfunctional Imperial archive rather than reading a conventional campaign diary.

**Central rule: standardize the administrative wrapper, not the underlying story.** Repetition of references, headers, labels, attachments, and termination messages is deliberate. Visual structure must make that repetition legible rather than removing it.

The application is **not a paginated word processor**. These rules describe semantic rich-text blocks and responsive screen layout. They do not require Google Docs, fixed pages, physical margins, document tabs, manual line breaks, or a specific rendering library.

## 2. Content integrity and narrative constraints

- Never change established campaign facts, outcomes, dates, names, roster identifiers, or territorial ownership to make a report read better.
- Keep the distinction between observed facts, attributed testimony, inferred explanations, and administrative conclusions.
- Preserve purposeful redactions, corruption, contradictions, and bureaucratic euphemisms.
- An Imperial recorder does not automatically understand xenos activity, psychic effects, or the player's hidden knowledge. Anomalies should emerge from evidence.
- Keep distinct institutional voices distinct. A Palanite incident report, a labour ledger, an Orlock testimony, and a machine-generated index should not sound interchangeable.
- Do not insert invented lore to fill visual space.
- C-NINE-specific names and designations belong to C-NINE content/templates, **not** the global engine defaults. For the C-NINE campaign, the canonical designation is **Geothermal Prospect Detail C-9**, shortened to **C-NINE**.

## 3. Rendering model: semantic rich text

Represent each chronicle as a structured document tree, not a string containing manual spaces or pseudo-layout. An appropriate modern implementation is a **rich-text document model** with semantic block nodes, inline marks, and embedded layout components. Examples of possible editor/rendering stacks include ProseMirror/Tiptap, Lexical, Slate, or a custom structured renderer; **none is mandated**.

### Block types

- `chronicle_section`: a cycle, downtime, or major narrative section.
- `engagement_header`: engagement type, sequence identifier, opponent.
- `incident_record`: primary incident account, metadata, and narrative.
- `metadata_group`: compact labelled fields.
- `body_paragraph`: ordinary account or narrative prose.
- `section_label`: `:: MATERIAL REVIEW ::`, `:: DISPOSITION ::`, etc.
- `disposition_panel`: formal machine-processing result.
- `addendum_panel`: self-contained administrative subrecord.
- `internal_note`: parallel institutional record; may appear alongside prose.
- `evidence_excerpt`: quoted source with a vertical rule.
- `testimony_note`: attributed marginal commentary with dashed outline.
- `transcript`: alternating speaker turns, optional timestamps and redactions.
- `attachment`: independently indexed supplementary record.
- `record_termination`: `// RECORD ENDS //` or other closing protocol.
- `scene_divider`: symbolic transition marker.
- `system_output`: indexing, retrieval, warnings, failures, progress.
- `personnel_dossier`: identity, classification, service summary, archival extracts, watermark, terminal footer.

### Inline marks

Use semantic inline marks such as `admin_label`, `important_entity`, `secondary_text`, `critical_status`, `error_or_missing`, `doctrine`, `redacted`, `source_anchor`, `speaker`, and `machine_error`. These map to colours and typographic treatments through the theme. Do not hardcode coloured spans into authored prose when a semantic mark can express the meaning.

### Minimal record schema (illustrative, not a mandatory API)

```json
{
  "type": "incident_record",
  "id": "stable-record-id",
  "metadata": [
    {"label": "Reference", "value": "..."},
    {"label": "Subject", "value": "..."},
    {"label": "Outcome", "value": "...", "tone": "neutral"}
  ],
  "blocks": [
    {"type": "body_paragraph", "content": []},
    {"type": "disposition_panel", "blocks": []}
  ],
  "termination": {"type": "record_termination", "variant": "incident_closed"}
}
```

Store stable identifiers and relationships independently of rendered position. A testimony note should reference the source passage it comments on, rather than being attached to an arbitrary screen coordinate.

## 4. Theme and semantic palette

The default theme is an Imperial cogitator archive: dark charcoal background, Courier-like monospace typography, bright green administrative controls, amber named assets, grey subordinate evidence, red critical statuses.

| Token | Role | Reference value |
|---|---|---|
| `surface.base` | Chronicle background | `#212121` |
| `text.primary` | Main prose and factual values | `#FFFFFF` |
| `text.secondary` | Archival extracts, commentary | `#999999` |
| `admin.primary` | Report structure, labels, machine output | `#00D16B` |
| `identity.primary` | Institutional/campaign identity accent | `#22C55E` |
| `entity.highlight` | Important subjects, assets, acquisitions | `#F2AD1F` |
| `personnel.highlight` | Personnel names in the reference theme | `#EAB308` |
| `status.critical` | Capture, death, fatal errors | `#EF4444` |
| `watermark.subtle` | Large subdued file identifiers | `#212C21` |

These values are **observed reference colours from C-NINE**, not proof that every campaign needs both greens or both ambers. A theme may map them to fewer tokens if their distinct semantic roles remain clear. Use `status.critical` for explicit adverse conditions, errors, and missing or unresolved information. Do not use colour alone to communicate a condition: include explicit status text.

**Semantic discipline:** white = primary record; green = administration/system; amber = named focus or ceremonial authority; grey = subordinate/uncertain evidence; red = adverse critical condition. Do not highlight every occurrence of a proper noun in prose.

## 5. Typography, rhythm, and alignment

- Default typeface: **Courier New** or a visually compatible, accessible monospace fallback.
- Default report body: approximately **11 pt / 14–15 CSS px** equivalent, **1.0 line-height relative to the chosen font only if legible**. In a browser, avoid clipping glyphs; a practical CSS `line-height` may need to be slightly greater than 1.0 even when the reference word processor reports single spacing.
- Main narrative paragraphs: compact but readable, roughly **8 pt-equivalent block gap**.
- Administrative report paragraphs: roughly **6 pt-equivalent block gap**.
- Metadata: approximately **9 pt-equivalent**, closely grouped, **0–2 pt-equivalent gap**.
- Labels and machine syntax: monospace, green, often uppercase.
- Major headings: bold, with clear hierarchy; cycle labels white and underlined in the reference design; engagement types green; named opponents amber.
- Main archival report prose may be **justified on wide layouts** as in the C-NINE reference. On narrow screens or where justification produces excessive word spacing, use left alignment. Never insert extra spaces into the underlying text to simulate justification.
- Use a consistent spacing scale (for example 4/8/12/16/24/32 px or proportional equivalents). Do not create vertical gaps with repeated empty paragraphs.

### Default spacing intents

| Element | Rhythm |
|---|---|
| Metadata fields | Very tight; read as one unit |
| Paragraphs within a report | Compact, consistent |
| Internal processing labels | Moderate gap before, small gap after |
| Attachments and record boundaries | Clearer gap than between paragraphs |
| Scene dividers | Large, deliberate separation |
| Personnel page/card | Spacious composition, not padded prose |

Exact numeric spacing belongs in theme tokens and responsive design rules, not in narrative content.

## 6. Campaign chronicle hierarchy

A typical campaign chronology contains:

1. **Cycle / campaign phase**: white, prominent, bold, often underlined (`CYCLE 2`).
2. **Engagement or event type and index**: green, bold (`HOSTILE ENGAGEMENT #2.1`).
3. **Opposing party or principal subject**: amber, bold (`x VAN SAAR GANG “ETHERNETANS 2.0”`).
4. **Primary record header**: green (`[■] ADMINISTRATUM INCIDENT RECORD`).
5. **Compact metadata group**: green labels, white values.
6. **Unframed primary narrative**: white prose.
7. **Processing blocks / attachments / testimony**: rendered according to their provenance.
8. **Explicit termination**: system-style closure, not a decorative flourish.

A cycle may contain multiple engagements, downtime records, and attached materials. Do not assume one cycle = one viewport, screen, page, or panel.

## 7. Record composition patterns

### A. Primary incident account — unframed

The main battle or incident reconstruction is a continuous reading column. It starts with a green report heading and compact metadata, followed by white prose. **Do not surround the entire narrative with a green box.** The absence of a frame is meaningful: this is the principal record, not an embedded processing object.

### B. Full-width solid green processing frame

Use a thin green rectangular border and subtly differentiated dark surface for a **disposition, material review, formal addendum, or other encapsulated administrative result**. The C-NINE reference has green section labels (`:: MATERIAL REVIEW ::`, `:: DISPOSITION ::`), grey findings, green field names, amber acquisitions and explicit closing text outside the frame. A stronger green left edge may reinforce the containment effect.

Keep the panel immediately associated with the report it resolves. It should not look like an unrelated card. Do not wrap routine body paragraphs in frames merely to fill space.

### C. Floating green-bordered internal document

A narrower solid-green panel may sit alongside primary prose when it represents a **separate institutional record commenting on the same event**, such as an internal C-9 note about a captured asset. Give it its own heading, source and fields. The main text may flow beside it on wide screens, but the inset must remain legible and spatially distinct.

On narrow screens, **stack the note after its associated paragraph** or expose it as an inline expandable evidence block. Never force a tiny sliver of justified prose beside a panel.

### D. Dashed grey marginal testimony

Use a dashed grey border for **attributed witness statements, corrections, conflicting accounts, review comments or side-channel evidence**. Speaker labels are green; testimony is grey, optionally italic. Position each note beside the precise statement it qualifies on wide screens. The notes may be asymmetrical and different heights.

### E. Selective evidence highlighting

A medium-grey highlight on a short source passage indicates an explicit connection to marginal testimony. Highlight **only the relevant words or sentence**, not whole paragraphs. Store a source-to-annotation link in the document model so the association survives responsive reflow and accessibility navigation.

### F. Embedded archival excerpt

Use a **vertical white or grey left rule**, indented slightly, for quoted source material within a larger record, including within a green processing frame. The excerpt is subordinate evidence, not another green frame. Prefer a source label and grey text.

### G. Multi-agency reconstruction

A longer investigation may combine unframed primary prose with several dashed testimony panels attributed to different institutions. The primary account remains the main reading path; marginal voices clarify or challenge specific observations. Multiple speakers may share one panel when they form a coherent exchange. Do not turn this into a magazine pull-quote layout.

### H. Transcripts and recovered recordings

Use explicit speaker identifiers, optional timestamps, interruptions, `[pause]` or corruption markers. Preserve speech order. Speaker identifiers may be bold or green, but the spoken text should remain readable as a continuous exchange. Transcript fragments can coexist with marginal review comments.

## 8. Frames, nesting, and borders

- **No frame:** primary incident account or narrative chronology.
- **Solid green frame:** encapsulated administrative result or self-contained attached document.
- **Narrow solid green frame:** parallel internal document.
- **Dashed grey frame:** attributed commentary/testimony.
- **Vertical white/grey rule:** quoted archival extract.
- **Grey inline highlight:** explicit annotation anchor.

**Never nest solid green frames inside other solid green frames.** A framed record can contain a vertical-rule excerpt. Do not add a border merely to decorate an empty region.

Border thickness, inset padding and panel background should be centralized in the theme. The source Google Doc includes several native border/shading variations; there is no single verified universal geometry. Implement a consistent application design rather than pretending those variations define exact pixels.

## 9. Administrative metadata and procedural syntax

A record's metadata should be compact and visually machine-generated:

```text
[■] ADMINISTRATUM INCIDENT RECORD
Reference: GPD-C9/SEC/01/774.M41
Subject: Territorial dispute at Toll Crossing ███████
Opposing Party: Palanite Precinct “Fangs of Justice”
Outcome: C-9 CONTROL ESTABLISHED
```

Green field labels; white field values; amber only for specifically highlighted names/assets. Do not add blank paragraphs between fields. Maintain field ordering for each record type.

Retain repetitive syntax such as `// ATTACHMENT I //`, `// RECORD ENDS //`, `// INCIDENT CLOSED :: POST-ENGAGEMENT PROCESSING //`, and `// FILE SEALED //`. Different endings signify different procedural states. Use centered attachment and separator markers sparingly but consistently.

## 10. Dividers and machine output

- A skull scene marker (`+=+=+=+=+=[ 💀 ]=+=+=+=+=+`) can signal a narrative scene transition.
- A diamond marker (`+=+=+=+=+=[ ◈ ]=+=+=+=+=+`) can separate equivalent attached archival records.
- System output uses green small monospace text, line-drawing characters, progress indicators, and occasionally corruption glyphs.
- A failed retrieval should show **partial progress**, not `100%`, followed by a concise machine-spirit exception.
- Religious language may appear as a machine procedure or doctrinal response; avoid random liturgical jokes that break the document's institutional voice.

These symbols are **theme-configurable**, not universal requirements for every Necromunda faction or campaign.

## 11. Redactions and uncertainty

Use solid blocks (`███`) or an accessible redaction component with variable apparent lengths. Redactions must correspond to plausible withheld or corrupted information, not random nouns. Preserve meaningful differences between:

- `REDACTED`: intentionally withheld.
- `UNCLASSIFIED`: no approved category.
- `UNVERIFIED`: claim not confirmed.
- `DATA CORRUPTED`: unreadable source.
- `MISSING`: absent record or subject.

Do not substitute one status for another. If an LLM generates a record, it must not reveal hidden truth in a bureaucratic document without a credible source or institutional basis.

### Errors, missing information, and adverse statuses

- Render explicit errors and missing, invalid, unresolved, or unverified information in the theme's red `status.critical` treatment. This includes machine or source-file errors, invalid references, absent records, and fields that cannot be established from available evidence.
- When an LLM-authored narrative lacks required information, express the gap **diegetically** in the voice and format of the record (for example, as a failed retrieval, an unlocated register entry, or an unresolved authority). Mark only the error or missing-information wording in red; keep surrounding narrative and administrative labels in their normal semantic colours. Do not invent a value to conceal the gap.
- For a field whose value is an adverse status, keep the label and punctuation in their normal style and mark only the status value in red. For example: `Status: Deceased`, with only `Deceased` red.
- Apply red to the smallest meaningful span. Do not colour an entire sentence, paragraph, field, or record when only a short value or error marker is exceptional.
- Preserve the distinction between adverse but known conditions (such as `Deceased`), missing data (`MISSING`), uncertainty (`UNVERIFIED`), deliberate withholding (`REDACTED`), and corrupted data (`DATA CORRUPTED`). Red styling communicates attention or severity; it does not make these states interchangeable.
- Pair red styling with explicit wording or a semantic status so the meaning remains clear without colour, including in copied or exported text.

## 12. Personnel dossiers: separate composition mode

Personnel files are deliberately sparse, individual records. The C-NINE reference uses **one person per composed page**, but the standalone app should implement this as **one dedicated dossier view/card per individual**, not as a fixed physical page requirement.

Typical dossier structure:

- Amber prominent surname/name or restricted asset designation.
- Compact green-labelled metadata (designation, labour grade, medical category, status).
- White service biography.
- One or more vertical-rule archival extracts, with green source labels and grey evidence.
- A large, faint identifier watermark in the lower region.
- Small terminal footer with record termination or indexing output.

Preserve **negative space**. Do not lengthen biographies or combine two people into one card just to occupy the viewport. On smaller screens, the footer follows the content without artificial full-screen gaps; on larger screens, a minimum-height dossier canvas can maintain the intended sparse composition.

Reference watermark patterns: `C9-MK/<fighter-id>`, `C9-AUX/<fighter-id>`, `C9-ASSOC/<fighter-id>`. These are **campaign-specific conventions**, not hardcoded engine prefixes. The suffix is a real fighter identifier and must not be fabricated.

## 13. Responsive behaviour and accessibility

- On wide displays, allow a main reading column plus a right evidence rail for marginal testimony and floating internal notes.
- On narrow displays, move annotations into inline callouts anchored to their source paragraphs, or expose them through an accessible expand/collapse interaction.
- Maintain source reading order and keyboard navigation independently of visual positioning.
- Provide textual status labels alongside colour.
- Avoid overly faint grey text for essential evidence; decorative watermarks may remain low contrast.
- Preserve copyable plain text and sensible text selection. Redactions should remain redacted when copied or exported.
- Do not depend on fixed viewport heights, pixel-perfect paragraph positions, or manual whitespace for record structure.
- If the app supports printing/export, apply a separate print stylesheet with sensible page breaks and repeated archive identifiers; do not let print constraints dictate the interactive layout.

## 14. Implementation guardrails for an LLM / Codex

1. Determine **document type** and **information provenance** before choosing a layout.
2. Generate structured content nodes with semantic roles; render them through reusable components and theme tokens.
3. Do not manually insert extra spaces, empty paragraphs or box-drawing characters to simulate a UI layout. Box-drawing characters are allowed when they are **the actual in-universe system output**.
4. Use existing record templates for standardized headers, metadata, attachment markers and terminations. Do not improvise a different shell for every record.
5. Preserve factual inputs verbatim where supplied. Any invented fictional evidence must be clearly within the scope of an authorized creative-writing task.
6. Do not collapse multiple independent records into one narrative summary merely to reduce visual repetition.
7. Use annotation anchors/references, not absolute coordinates, to connect testimony with highlighted text.
8. Prevent panel collisions, excessively narrow prose, unreadable contrast and detached annotations through responsive layout rules.
9. Do not introduce new colour roles, border types, or visual ornamentation without a documentary purpose.
10. Keep narrative content, presentation tokens, and app implementation separate so the same records can be rendered on screen and in export formats.

## 15. Quality checks

### Content
- Are events, casualties, acquisitions, identities and statuses unchanged from the authoritative campaign state?
- Is each claim attributed to a source that could plausibly know it?
- Are redactions, contradictions and uncertainty preserved?

### Visual
- Is the primary account unframed and visually dominant?
- Are green frames limited to administrative objects?
- Are dashed grey boxes used for attributed testimony rather than generic callouts?
- Do highlights correspond to actual annotation anchors?
- Are metadata and closing markers consistently styled?
- Is there a clear distinction between a dossier, an incident report and an evidence excerpt?

### Functional
- Do notes remain associated with the correct passages at narrow widths?
- Does the reading order remain coherent without sidebars?
- Can text be copied/exported without losing essential information?
- Do long reports scroll naturally, and do personnel dossiers retain intentional spaciousness?
- Are all required statuses legible without relying on colour alone?

## 16. Reference and precedence

The original C-NINE campaign log and personnel files are **visual exemplars**. The companion `CNINE_STYLE_MAP.json` records observed formatting patterns from those files, including inherited/unspecified properties; it is **reference data**, not the runtime schema and not a mandate to reproduce a Google Docs implementation.

Priority: **current task requirements → factual/source integrity → semantic document role → this global formatting standard → campaign theme customization → renderer defaults**.

**Design invariant:** the archive's repetitive machinery stays standardized; the story, evidence and contradictions are allowed to be messy.
