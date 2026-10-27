# Chronicle timeline - 0.12.1

Implemented 2026-10-27. Source timestamps, source archive records, phase/participation provenance and writer policies remain unchanged. This pass updates presentation and strict battle-panel membership, with a derived playtime field; no model call or campaign-source edit is involved.

## Navigation and markers

- Ctrl + mouse wheel zooms around the pointer, from the whole filtered campaign down to a 15-minute view. Ordinary wheel scrolling remains available to the page. Zoom buttons, Earlier/Later pan controls and Full campaign provide mouse/keyboard/touch alternatives.
- Events cluster by their rendered distance, using a 30-pixel threshold and a final overlap reconciliation. Groups show their event count. Zooming re-clusters the visible events; events at the same time stay grouped. Clicking a group opens its individual records and a Zoom to this group control.
- Each gang has a stable palette colour across filtering. Event markers occupy a row above its battle bars; downtime occupies a row below them. Bar and dot hit targets do not overlap vertically. Long gang names wrap, and the full name is available on hover.
- Imperial dates use the existing NCCE calendar conversion (9.FFF.998.M41). Real-world dates use Europe/Warsaw. These appear separately on the axis, selected records and activity entries; real time remains UI/mechanical metadata.

## Battle detail membership

For an event with a valid timestamp and a gang involved in the selected battle:

1. **Battle:** timestamp is inside a complete session interval, including its start and end.
2. **Downtime:** timestamp is strictly after the selected battle's final end and strictly before that gang's next battle start, if known. Each gang uses its own next-battle boundary.
3. Events before the selected start, at/after the next start, from other gangs or without usable timing do not enter either section merely because a neighbouring-battle ID links them.

For multiple linked sessions, Battle uses the actual intervals, not the pauses between them. Missing end times do not invent a completed interval. Selecting a battle in the filter also opens its detail, so battles without positioned bars remain accessible.

Battle and Downtime are collapsible. Each contains collapsible gang groups, then fighter groups (or Gang affairs). Entries show event-type glyphs, Imperial/real dates and visually marked mechanical descriptions. Former phase prefixes are removed from the event strings.

## Record presentation and links

The battle header uses engagement-archive/cogitator metadata. Time Window separates Imperial datestamps from tabletop timing and calculated Playtime. Result is renamed Winner and links to the gang. Territory links by its unique source-to-local ID; a unique name match can serve as a UI fallback, while ambiguous names are not guessed. Cycle remains.

Window Source, Linked sessions, original battle/source JSON controls, Battle registry, Browse recorded changes and Timing and source notes are removed from this view. Internal records/provenance and genuine missing timing are retained in the API; routine candidate/proxy disclaimers are not displayed. The evidence remains mechanical, distinct from the Imperial presentation layer; no mechanical description is rewritten as generated fiction.

## Playtime

`campaign_history.window_playtime` merges overlapping complete intervals, then sums their duration in seconds. Pauses between sessions are excluded and overlapping sessions are not double-counted. `/api/history` returns `playtime_seconds` per battle. The UI displays battle duration, per-gang totals and aggregate battle-hours for the filtered battles. The campaign total counts each battle once rather than counting it once for each gang. It is aggregate battle-hours, not wall-clock campaign elapsed time or individual fighter attendance.

## Validation

Deterministic regressions cover Ctrl-wheel versus ordinary wheel, fit/reset, clustering/splitting/marker spacing, strict per-gang battle and downtime boundaries, pre-battle death exclusion, event icons, source/Imperial date separation, links, escaping and overlapping/broken-session durations. Existing archive import/classification and writing/date regressions pass. Disposable authenticated application smoke verifies live read-only sync and the added timeline fields. Hosted visual/interaction checks and release evidence are recorded in CHANGELOG.md.
