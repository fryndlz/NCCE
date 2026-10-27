# Hive cogitator frontend

Local implementation of approved concept C: physical machine, readable software. The second pass restores the approved composition rather than stretching modular hardware around a conventional page.

## Construction

- `web/reliquary.css` loads after the earlier `machine.css` foundation and semantic-document styles.
- `cogitator-plate-v2.png` is an image-tool edit of the approved original C. It preserves the weathered brand plate, connected control rail, pointed arches, hooded statue, candles, cables, instruments and ghosted hive skyline. Record content was removed from the artwork. On desktop, the complete plate keeps its original 1586:990 proportions, without stretching individual hardware pieces.
- Live text, buttons and disclosures occupy the original glass apertures. Long records scroll within the apertures. Biography, Mind and evidence scroll positions survive a normal data refresh. Background art does not supply campaign facts or fighter portraits.
- The original seven connected navigation modules have real labels and sequential counters. System remains accessible through the lower-right diagnostics plaque. On mobile, CSS sprites reuse the weathered nameplate and individual navigation housings while the content stacks.
- `glass-v2.png` supplies the lower-width glass texture, using proportional sizing. `parchment.png` supplies the torn paper, faint hive illustration and wax seal with repeating edge slices. Software draft-status notices stay outside the physical document surface. All record text remains selectable and escaped.
- Current typography uses bundled Grenze semibold headings and Crimson Text prose, with their OFL licenses alongside them. The earlier IM Fell font is preserved for design history. Explicit prose selectors prevent the prototype viewer from substituting its system sans-serif.
- `generation-prompts-v2.json` preserves the exact built-in image generation prompts and font source. Earlier asset prompts and assets remain available for design history.

## Fighter dossier

The left framed screen contains identity, a short biography excerpt, an expandable complete biography, and the numbered memory stream. The right contains separately framed Mind and evidence modules. Writer maintenance remains available under a disclosure.

The latest memory starts open. Opening another closes the earlier one using a native named details group. Every expanded memory receives the parchment surface; closed memories stay on glass. Evidence and provenance remain available on glass below the paper. Thought links open their target memory before navigating to it. Refresh preserves disclosure state, including closed sections. No invented portrait or identity is attached to a fighter.

The shell is shared by the other sections; their existing controls and content continue to work in the left retrieval aperture. On narrow screens, navigation wraps to four columns and dossier screens stack. The desktop composition switches to proportional sprites and a reading layout below 1000px rather than shrinking its text to illegibility.

## Scope

Presentation and client-side disclosure behavior only. Campaign state, authored canon, generation contracts, provider settings and synchronization logic are not changed. No automatic generation is introduced. This change has not been deployed.

## Review

### Real application branch preview

The `codex/cogitator-frontend` branch is based on main's NCCE 0.13.0 release. Run `python scripts/run_cogitator_preview.py`, then open `http://127.0.0.1:8877/`. The server stays in the foreground until stopped. It creates an isolated SQLite backup of the local campaign database on first launch and uses the normal read-only Sheet synchronization. Existing preview data is retained on subsequent launches. No production database is modified.

This launcher binds only to loopback and grants a local browser session automatically. It disables model credentials and automatic writing; Workshop edits affect the preview database only. The hosted application and main branch are unchanged.

The actual application now fills the secondary screen and register from campaign records across the section tabs. Fighter dossiers retain their own Mind/evidence panels. Chrome verification used real HTTP responses, visited all eight sections, opened Mara Kel's dossier, inspected the 0.13.0 Workshop, and checked widths of 1280, 1024, 736 and 390 pixels. No JavaScript errors or horizontal overflow were found. Live Sheet synchronization succeeded with 6 gangs, 92 fighters, 24 territories and 26 battles. Local screenshots and the health report are under `output/cogitator-preview/`.

### Fifth-pass panel correction

The utility controls are compact and contained within the lower-right illustrated plaque again; no prototype footer or toolbar consumes height below the desktop machine. Internal panels now have semi-transparent green fills, and neutral navigation faces receive a pale green material tint while the active key remains brass. Browser checks confirm the utility bounds, translucency, green key tint and unchanged navigation/record interactions.

### Fourth-pass refinements

- Navigation labels and counters are part of a two-state artwork atlas. Accessible names remain in HTML, without any live type projecting over the metal faceplates.
- All green-screen content frames use transparent backgrounds. Semantic labels, metadata, testimony outlines, processing rules and inline marks follow the existing Narrative Formatting Standard; prose and canon are unchanged.
- Reload, diagnostics and prototype notices are in a readable utility strip below the machine. The illustrated plaque and footer plate are clear.
- Glass apertures stop before the statue framing; native scrollbars are hidden while wheel, touch and keyboard navigation remain available. Headings and context labels wrap within the viewport.
- A transparent eight-frame GIF supplies very light static on desktop and mobile screens. Tab selection triggers a brief subdued loading distortion. Static and distortion stop under reduced-motion settings.
- The prototype retains the newer authored Archive disclosures and existing timeline interactions from the current source. Its archived snapshot is read-only, and local Workshop edits remain isolated.

### Third-pass refinements

- Selected navigation has an actual textured brass key (`selected-key-v3.png`), instead of a translucent yellow rectangle. The asset prompt and font sources are preserved in `generation-prompts-v3.json`.
- Breadcrumbs are live HTML outside every scroll aperture. The home control masks the baked placeholder glyph, and the chevron has its own layout space. Record-parent breadcrumbs navigate back to their index. Cross-section record links also update the selected tab.
- Scroll apertures begin below the breadcrumb and clip their own content. The title and subtitle fit within the drawn title cartouche; long fighter names receive a proportional display size.
- Open memory documents place the Imperial date beside the title in the paper header. Real dates, provenance and software status messages remain on glass. Closed memories retain their date/title summary.
- Four independently phased CSS flames and amber light blooms align to the source candles. The Mind header has a decorative signal trace. Both respect reduced-motion preferences and do not change campaign data or claim to be physiological telemetry.
- Browser geometry checks confirm a clear gap beneath the breadcrumb, non-overlapping home/chevron controls, stable breadcrumbs while a pane scrolls, and dates inside the paper header. Existing UI tests, all eight sections, source links, local Workshop edits and mobile overflow checks pass.

Existing writing, campaign-history and Workshop UI contracts pass. Browser review uses production HTML/CSS/JavaScript and captured GET responses from a disposable local database, because this environment blocks browser access to loopback. Screens and controls are checked at desktop and narrow widths; this is not a substitute for a deployed HTTP check. Review screenshots are under `output/machine-review/`; `fighter-desktop-v2.png` is the current composition.
