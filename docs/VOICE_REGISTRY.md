# NCCE voice registry — faction / gang / individual

Canonical file: `config/voice_registry.v1.json` (versioned in Git). Resolver: `src/voice_layers.py`; operator CLI: `scripts/voice_registry_cli.py`. This policy is editorial **style guidance**, not an authoritative mechanics or chronology layer. The authoritative campaign roster is the Krakamunda Sheet; player-authored fighter Backstories and authored campaign documents take precedence over generated prose.

## Current coverage

**Approved gang-specific profiles:** The Slag Eaters (House Orlock), Geothermal Prospect Detail C-9 / C-NINE (Genestealer Cults), Kły Sprawiedliwości (Palanite Enforcers), Ethernetans 2.0 (House Van Saar), Helmaeth Expeditionary Force (Ironhead Squat Prospectors). Supporting externally-affiliated registers: House Helmawr's Palanite Household Companions, House Ran Lo's Auditing Conclave, Peregrine's Due, independent retainers. The current source registry includes named individuals only where an accepted biography or player-authored text substantiates a personal cue.

**Excluded until owner supplies and approves its own authored local identity:** Patrol do spraw alkoholu i broni. It receives a neutral fallback: no imported Kły precinct register, no personal invention, no gang tags. Its recorded faction remains visible separately. The incoming gang is therefore safe to add before profile authoring.

## Composition and priority

For each fighter_memory, fighter_reflection and fighter_mind:
1. Establish event/cause, chronology and firsthand/hearsay awareness from NCCE evidence.
2. Apply the known **faction** world's subject matter, never a mandatory personality.
3. Apply the registered **gang** literary register, provided `review_status=approved`. Do not substitute another gang merely because both share a faction.
4. Apply the **individual** voice from accepted/player-authored background, not automatically from class, cost, stats or current injuries. If absent, use the role as context without invented traits.
5. For a documented **external attachment**, override the hosting gang's faction/register (e.g. Dredd 2D and Dredd 3D remain House Helmawr, not Van Saar; House Ran Lo attaches to Helmaeth; C-NINE's Peregrine's Due crew are not C-NINE brood labour).

Language and register are an editorial layer, never evidence that a battle happened or that a fighter knows a secret. The personal C-NINE memory voice is ordinary worksite speech; the corrupted Labour Administratum printout style is for dossiers and archival documents, not mandatory personal thought. **Kły Sprawiedliwości's public precinct narrative must not leak its GM-only account** into generic writer packets or rank-and-file thoughts. Characters may know only what player-authored source confirms they know by the episode's time. A Purestrain, familiar, Cyberachnid, or similarly nonhuman mind is not assigned human first-person speech without source support.

## Source and provenance rules

Each faction/gang/individual record carries `tags`, `source`, `provenance`, `register`/`lens` and optional `review_status`. Player-authored lore and established mechanical facts are not equated with narrative interpretation. `review_status=pending_editorial` is neutral; its register and tags are not passed to the writer as active voice. External mappings and canonical C-NINE aliases are explicit JSON entries. The resolver accepts missing gang and missing individual data, falling back to empty stylistic tags. The writer packet gets its `voice_layers` block separately from mechanical evidence, source event IDs, chronology and accepted-fiction context; its provenance is `style_guidance`.

**Display during editorial review:** source cause/observation/event ID, mechanical facts, accepted authored background or prior prose (with distinction), any known voice tags and their origin, connective invention, exact text and character count, status. The provisional fighter-memory length is approximately 350–400 characters including Markdown; reflections and Mind thoughts keep separate form lengths.

## Add a new gang without changing Python

Start with its actual known name, faction and a citable authored source. Do not apply a sibling gang's accent.

```bash
python scripts/voice_registry_cli.py validate
python scripts/voice_registry_cli.py list
python scripts/voice_registry_cli.py register --gang "Patrol do spraw alkoholu i broni" --faction "Palanite Enforcers" --source "Owner-authored Patrol notes, [exact file/revision]"
```

Registration creates a **pending_editorial** empty profile (no new personality tags) and removes it from the excluded-list placeholder. The existing system continues operating on neutral fallback. When the owner approves a local writing profile:

```bash
python scripts/voice_registry_cli.py approve --gang "Patrol do spraw alkoholu i broni" --register "Owner-approved short cultural/voice instruction" --tags precinct,example --source "Owner-reviewed version of Patrol lore"
python scripts/voice_registry_cli.py add-fighter --gang "Patrol do spraw alkoholu i broni" --fighter "Verified roster name" --register "Source-grounded personal voice" --tags specific_trait --source "Accepted fighter Backstory [exact source]"
```

Review the Git diff, run `python -m unittest discover -s tests -p 'test_voice_layers.py'` and other project tests, merge and deploy. This is a **code/data deployment**, not a campaign refresh. The app never edits this registry in response to a roster arrival or public source content. Do not auto-approve new gangs, or copy a Kły profile into Patrol.

Existing WRITING/READY/IMPORTED request text, request IDs and source revisions are immutable through a profile update. Already prepared request packets carry their original sealed context. Only future prepared fighter packets receive the deployed registry. Changes to editorial tags do **not** create new mechanical events or force rewriting accepted prose.

## Source notes for the newly registered gangs

- **C-NINE:** player-authored GANG BACKSTORY and personnel Backstory entries in Krakamunda; *The Prospect* in the C-NINE canonical story document; Geothermal Prospect Detail C-9 / Crew / Prospect vocabulary. Individual examples include Jarek Voss, Garrick Voss, Daven Holt, Breaker B-01, Drenn, Griz, K-117, R-204, Mara, Rook, Renn. Outsider Veyne's *Peregrine's Due* group, Kroot/Ork crew, and Dr. Krail have separate lenses. No illicit spill of gang-wide psychic knowledge.
- **Kły Sprawiedliwości:** Krakamunda player-authored GANG BACKSTORY (its public section only), and accepted Tomas biography in NCCE Writing Exchange row 71. Public formal unit discipline, wolf totems, Poison Sea Prefecture and procedural extremity provide culture, **not** universal internal belief. The source's explicitly labelled GM-only section must not appear in default writer context.
- **Slag Eaters / Ethernetans / Helmaeth:** accepted NCCE biographies and previously owner-approved three-layer model; unchanged in substance, migrated to the versioned source file.


## Automatic roster discovery and editorial review (added 9 Nov 2026)

The deployed application now scans **new active gangs and newly rostered fighters** at startup and after every successful Krakamunda refresh. It does not call a language model or infer private beliefs: it deterministically extracts short, exact evidence excerpts and conservative *topic cues* from player-authored gang/fighter Backstory text. If a fighter has no authored Backstory, it checks the approved fighter-biography slot. An absent source produces `awaiting_source`; it is never approved by default.

Persistent review queue: additive `voice_proposals` and `voice_proposal_audit` tables in NCCE's SQLite DB (not the campaign Sheet). Open **Voice review** from the campaign sidebar, or visit `/voice-review.html` when signed into NCCE. The panel displays name, source kind, original source link/locator, verbatim evidence, and editable proposed tags and register. Each decision is explicit: **Approve** or **Reject**. A real source fingerprint is checked at review time and again when the approved profile is used in a writer packet. If the Backstory or source provenance changes, the next scan revokes approval and presents a fresh proposal. The earlier decision remains auditable. Newly approved overlays are included in **future** sealed writing packets only; they never rewrite previously accepted fiction, held writer requests, stats, memories, event scores or campaign canon.

These suggestions are *not* model-generated character analysis. The excerpt and tags establish evidence-bound topics; the owner refines diction, temperament and priority during review. A generic tag does not prove a personality. Existing hand-authored `writer_identity_json` fields remain the strongest explicit individual guidance. Hardcoded previously accepted profiles in the versioned JSON take precedence over new auto-extractions. A documented external attachment always wins over the host-gang voice. Only the Patrol's **own** new sourced profile can activate its gang styling; Kły's profile cannot be inherited. Before approval, the Patrol uses neutral faction/gang/individual styling; when its profile is approved, its generic Enforcer faction frame returns without borrowing Kły's specific register.

Endpoint contracts (authenticated with the application's session):
- `GET /api/voice-proposals?status=pending|awaiting_source|approved|rejected|all`: list exact source excerpts, source locators, tags, status and fingerprint.
- `POST /api/voice-proposals/review`: JSON `{"proposal_key":"fighter:123","source_hash":"...","decision":"approved","tags":["survey_and_routes"],"register":"Source-grounded individual voice description"}`, or `decision:"rejected"`. Requests must be same-origin and source-fingerprint matched.
- `src/voice_proposals.py`: discovery, durable audit, exact-source stale protection and forward-only overlays.

The JSON registry and CLI remain useful for authoring/deploying stable, curated profiles. The SQLite review path supplements them with live onboarding **without an application code change or new deployment for every fighter**. The proposal data lives alongside the application's persistent DB; back up that DB alongside any other campaign state.
