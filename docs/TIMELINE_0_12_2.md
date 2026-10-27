# Timeline navigation and engagement records - 0.12.2

2026-10-27, Europe/Warsaw. Extends [0.12.1](TIMELINE_0_12_1.md); no source-data, writer-policy or schema change.

## Ctrl-drag

Holding Ctrl and dragging with the primary mouse button navigates horizontally through the time range and vertically through gang lanes. Vertical navigation uses a scrollable chart capped at 70vh. Horizontal movement is converted from rendered plot pixels to a time offset and clamped to campaign bounds. At full-campaign zoom, all dates already fit; zoom in to pan horizontally.

Pointer capture is on the stable timeline root rather than the SVG children replaced during redraw. Vertical scroll is retained across redraws. A four-pixel threshold distinguishes dragging from incidental movement. Release, cancellation, lost capture or releasing Ctrl ends navigation. A completed drag cannot accidentally open an event/battle underneath; ordinary clicks and Ctrl-wheel zoom remain available.

## Lane labels and battle record

- Gang labels show engagement count on the battle-bar line, with summed engagement time below it. Totals follow the existing filters, not the current zoom crop.
- Overview, hover text and battle duration use **engagement time** instead of playtime/played.
- Mission designation is visually separated from the linked participant gang names. Both attacker and defender link to their gang records; source participant IDs are used where available.
- Cycle is the first metadata row. Time Window retains separate Imperial and real-world dates; the real date and duration use normal text colour without the timezone caption or framed panel. Conversion still uses Europe/Warsaw.
- Activity heading is **+++ RECORDED EVENTS // CHRONOLOGICAL INDEX +++**. Existing strict Battle/Downtime membership and collapsible groups remain.

## Duration audit

The hosted archive was independently recomputed from all complete session intervals and compared battle-by-battle with `playtime_seconds`: zero mismatches. At the audit, 26 battles contained 23 timed engagements, totalling 346,949 whole seconds, displayed as **96h 22m**. Three battles without complete timing do not contribute duration. Each battle counts once in the campaign total; each gang sums only its own engagements. Overlapping sessions are merged and pauses excluded, as in 0.12.1.

This matches the stored timing windows. Two stored windows span about 24h 36m and 18h 16m and are included as recorded; no silent clipping or source correction was performed. The total is aggregate engagement-hours, not individual fighter attendance or a stopwatch measurement independent of the archive.

## Verification

Regression checks exercise combined horizontal/vertical Ctrl-drag, retained scroll position, pointer release and click suppression, ordinary clicks, zoom, participant links, Cycle order, event heading, neutral time-window markup and the existing chronological/duration checks. Existing application smoke runs with a disposable database and read-only live Sheet sync. No paid writer calls are part of this release.
