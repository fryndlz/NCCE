# Writer context and creative planning - NCCE 0.12.0

Implemented 2026-10-27, Europe/Warsaw. SQLite schema 12. This is application-side context assembly, not model training or a second model reviewer.

## Problem and pipeline

The reviewed Grey Mirror and Counting Seam Workshop requests supplied only a territory type, not its rulebook description. Both invented customary accounting/dispute systems and ended with legal disclaimers. Variation instructions alone provided neither the missing reference nor knowledge of previous attempts.

`facts + authored context + same-subject continuity -> verified type reference -> saved creative plan and compact repetition hints -> one writer call -> existing validation/audit/rendering`

All fourteen forms pass through `llm_writer.write`. The planner changes no event interpretation, fighter importance, Mind selection, ownership, chronology or campaign data. It does not schedule ambient incidents. Automatic writing remains paused.

## Rulebook reference records

`src/territory_reference.py` contains 26 concise paraphrased Dominion type records: function, qualitative rule significance, enhanced-boon House, edition, printed/PDF page, verification method and reference revision. They supply context, not a rules calculator or proof of benefits claimed.

Source: supplied **Necromunda: Core Rulebook (2023)**, ISBN 978-1-83779-127-9, Dominion Campaign Territories, printed pp. 173-181 (PDF pp. 174-182). All nine rendered pages were checked after text extraction. Supplied PDF SHA-256:

`4db99cde10e8819aa589af9a275c9a624614161d48b76878a0e77e9d3d69cbc7`

| Printed page | Types |
| --- | --- |
| 173 | Settlement, Old Ruins, Rogue Doc Shop, Promethium Cache |
| 174 | Wastes, Sludge Sea, Workshop, Collapsed Dome |
| 175 | Refuse Drift, Corpse Farm, Bone Shrine |
| 176 | Drinking Hole, Gambling Den |
| 177 | Needle Ways, Synth Still, Stinger Mould Sprawl |
| 178 | Narco Den, Slag Furnace, Fighting Pit, Smelting Works |
| 179 | Mine Workings, Tunnels |
| 180 | Toll Crossing, Generatorium |
| 181 | Archaeotech Device, Tech Bazaar |

Only the relevant card enters a territory/place request. Normalized aliases `Archaeotech` and `Mine Works` map to the full type. Explicit event-time type wins over a subject label; conflicting types remain unresolved. Fallbacks accept the app's baseline type-evidence field or an exact type title, never incidental prose mentions. No current-roster lookup backfills an old event.

Unknown/custom types remain unverified. Other supplied books were searched, but supplemental faction interactions are not silently merged into these 2023 base cards. Books/images are not copied into the public repository or prompts. New editions/custom rules need separately verified records. A House association does not identify the owner; access to healing or captive labour does not prove it occurred.

## Focus selection

`writer_planning.options` allows eight editorial lenses for territory baselines and ambient accounts: religious, economic, political, criminal, personal, historical, environmental and cultural. Fighter biographies and gang origins use the same set without environmental. These designer-authored lenses are inspiration, not rulebook facts or mandatory plots, and yield to authored identity and narrator knowledge.

Other forms use `recorded_event` or `recorded_sequence`. Random themes cannot displace an injury, seizure, battle or supplied history. Expression may vary within existing creative permission; tracked outcomes cannot be invented.

Automatic selection chooses the least-used compatible lens in the recent comparable-family window, with a stable hash tie-break. The free variation number rotates ties. Owners can pin an allowed lens. Planning uses no provider call. Existing activated shared/form instructions and examples remain intact; the shared runtime presentation rules explain these new context fields.

## Recent-pattern memory

The planner reads the last 80 stored footprints and last 40 successful/imported Workshop trials, using the latest owner edit where available. It orders and deduplicates them, excludes the same subject, and keeps up to 16 comparable entries. Families are place, fighter and collective. This is generation order, not in-world chronology.

`footprint` extracts titles/candidate proper names and lexical tags for accounting, disputes, legal recognition, taxation, deferred maintenance, inherited office, religion, economy, crime, environment, history and personal relationships. The closing is tagged separately. Legacy samples without a focus contribute detected theme tags to usage counts. These are approximate signals, not semantic analysis or literary grades.

Only aggregate focus/device/ending counts and up to 12 names enter the prompt. Other subjects' prose is not copied as an example or history. Unapproved drafts may warn against repetition but cannot become accepted campaign continuity. Existing `narrative_context` supplies same-subject baselines and chronologically eligible accepted earlier stories separately.

## Persistence, cache and cost

Schema 12 adds private `writer_creative_plans` and `writer_creative_footprints`. Campaign/source tables are not rewritten. Plan keys include source packet/form/identity, planner/reference revision, focus and variation. The first saved plan freezes its reference, focus and hints. Another generation cannot silently change an inspected/retried packet. Changed source facts invalidate a plan before spending.

Workshop inspection saves and displays a free plan. Generate uses that exact packet and selected instruction revisions. Existing request-key idempotency prevents duplicate paid work. Production freezes a plan on its first enabled attempt; paused refreshes reuse saved plans without creating new ones or scanning editorial history.

A successful response is retained/audited and adds a footprint without another model call. There is no critic, candidate selection, automatic retry, novelty rejection or automatic regeneration. Authored prose/owner edits stay intact. Model/effort remains Luna/medium; response allowance remains 4,000 total tokens. Compact hints add input tokens, not calls. Literary improvement still needs owner review of a deliberately generated sample; automated checks establish context delivery, not prose quality.

## Workshop use

1. Select an entry and keep/edit the usual guidance.
2. Leave focus automatic or pin an available lens. Events keep their recorded event/sequence.
3. Inspect for free: check focus, source page, exact packet and repetition hints. For a baseline/ambient entry, **Try another plan** rotates the free variation; a pinned focus stays pinned.
4. Generate once when satisfied. Editing/examples/explicit activation work as before. Inspection or activation never publishes or regenerates campaign prose.

## Validation

Offline checks cover the 26 references, missing/conflicting/historical types, legacy-pattern bootstrap, bounded same-subject exclusion, least-used selection, all-form event boundaries, stable persisted plans, exact inspected-packet delivery, one-call idempotency, source preservation, migration of owner edits/revisions and transaction integrity. Existing writer/pipeline/comparison/Workshop checks pass. HTTP checks cover auth, cross-origin denial and duplicate requests; disposable app smoke exercises read-only live sync and persisted plan inspection. Implementation verification uses no paid calls.
