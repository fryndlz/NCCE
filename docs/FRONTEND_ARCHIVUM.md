# Archival frontend — 3 November 2026

## Scope and source of the design

The owner's sidebar mockup and the visual/navigation structure at
https://krakaumunda-archiwum-c9.blazej-augustynek.chatgpt.site/
are presentation references only. No prose, campaign records, invented dates,
territory names or other content were imported from that site.

The pass changes only browser presentation. Engine version and SQLite schema
are unchanged. Writer calls, authorisation, generation budgets, stored policies,
authored text, campaign data and source ingestion are unchanged.

## Implemented navigation

- Persistent numbered left sidebar: Chronicle, Gangs, Fighters, Places, Battles,
  Archive, Writer Workshop, Writing context and System. The active section is
  visible and marked with `aria-current`.
- Below 820px the sidebar becomes an expandable section menu. Selecting a section
  closes the menu. There is a keyboard-accessible skip link.
- Gangs, Fighters, Places and Battles keep their existing search/filter behaviour.
  Results form a scrollable record index beside a persistent document preview.
  Battle labels include mission, territory where known and the existing Imperial
  date conversion. The index highlights the selected record.
- The same index/preview presentation exposes the two existing authored Archive
  stories. Their source wording and collapsible story disclosures are retained.
- Selecting a record changes the preview rather than discarding the index.
  Cross-section detail links remain available, with section/back navigation.
- Writer Workshop and Writing context retain their full existing controls and
  workflow. A generated local desk index provides jumps to the current section
  headings; it is rebuilt with the existing page, without additional requests.

## Document and visual layers

`web/archivum.css` supplies muted green panels, restrained brass accents, serif
reading text and parchment documents. `web/archivum.js` supplies the record index,
document frame, tabs, sidebar menu and desk index. `web/app.js` still owns the
existing API requests, filters and record bodies.

Each preview has a document identifier, Narrative record / Data & sources tabs,
a parchment metadata line, a neutral NCCE archive-copy stamp and termination
mark. These are application presentation, not newly authored campaign canon.
Unknown dates remain undated; no timestamps are invented. Where available,
existing Imperial dates appear on the document and real dates in the source/UI
layer. A generic archive stamp does not attribute other gangs' records to C-NINE.

The narrative body retains existing authored/semantic rendering. Mechanical
basis, profile/identity tools, source disclosures and writing diagnostics move
into Data & sources. Pending-writing notices stay outside the parchment body.
No evidence text is rewritten or deleted. Tabs support arrow keys and Home/End.
Current thoughts, memories and record links remain accessible.

## Timeline boundary

The entire code range `historyDate` through the end of timeline loading, before
`selectControl`, is byte-for-byte unchanged from the pre-pass source. Its SHA256
is `5a9a12d0d35e316dd28a3fef723ed3c2fb289479c4b9948dc28d7600a573931f`.
Timeline-specific CSS and the existing semantic stylesheets are unchanged.
The new record/desk theme is scoped away from `#app[data-view="chronicle"]`.
The surrounding sidebar changes available width, as any app shell does; timeline
zoom, Ctrl-drag, clusters, dates, gang colours, intervals and detail rendering
continue to use the existing implementation.

## Verification

- Existing timeline, writing renderer, Workshop, activity and finished-study
  contracts pass. The finished-study check uses the committed Workshop source:
  an unrelated, already unfinished population feature remains outside this pass.
- New `tests/test_archivum_ui.cjs` covers escaped record fields, preserved prose,
  separate source panels, date/stamp markup, accessible navigation and absence
  of network/provider calls in the presentation module.
- Disposable authenticated browser preview: fighter search and Mara selection;
  source/narrative switching with keyboard; battle preview and date separation;
  both authored Archive entries and collapsible prose; committed Workshop desk
  navigation; Writing context desk navigation. No page errors in the clean preview.
- Phone breakpoint checked at 390px: menu opens/closes, selection works and record
  documents fit without horizontal overflow. Desktop record/source views also fit.
- All preview data is disposable. No paid generation or production source/policy
  edit was used to verify the frontend.

## Release

Source completed 3 November 2026, 10:36 CET. Verified live 3 November 2026, 10:38:03 CET: source `d87d428`, deployment `dep-dbkqmd3bc2fs7386h9h0` (automatic new-commit deployment). Hosted health confirms engine 0.20.1/schema 15/sync ok/zero writer calls. Authenticated hosted checks confirm sidebar, record index/preview, authored C-NINE Sheet prose, separate data/source tab, both Archive stories and disclosure, and both writing-desk section indexes. Mara’s 853-character authored biography is unchanged. Timeline still reports 26 engagements / 276 events / 96h 22m; its source block and styles were not edited. No page overflow observed. Live screenshot retained in output/archivum-live-2026-11-03.png (top portion: output/archivum-live-preview.png).
