# NCCE fallback access

The primary connection is now `scripts/client.py`, documented in [native operations](operations.md). The browser/snapshot options below are fallbacks, not tasks the owner must perform before each batch.

## Hosted campaign, preferred for current work

Site: `https://ncce-private-preview.onrender.com/`. Use the user's existing authenticated browser through available browser/computer-use tools. Follow their documentation/skill when required. Open a separate read-only tab if needed; do not disturb an in-progress Workshop run. Authentication stays in the browser; never extract cookies or print credentials. If login is required, let the owner log in rather than request their passphrase in chat.

Existing owner-authenticated GET routes, verified in `src/server.py` and `src/writing_rag.py` at skill creation:

- `/api/workshop/rag/subjects` → actual catalog, stable `key`, `form`, `label`.
- `/api/workshop/sample?key=URL_ENCODED_KEY` → subject packet, document, packet hash. Avoid comparison samples, especially unsealed blind cases.
- `/api/workshop/rag/preview?form=FORM&sample_key=URL_ENCODED_KEY` → `subject_packet`, active `instructions`, `active_revisions`, retrieved passages and search provenance/omissions. This is a read-only context preview, not a generation request. A free-text query without a real sample is NOT the exact subject packet.
- `/api/workshop/guidelines?scope=FORM` → active/saved/proposed guideline history; a proposal is not an active guideline.
- The Places view supplies territory browsing; inspect `src/server.py` before using any detail endpoint rather than guessing its URL.

Use browser navigation and DOM/visible page reads to inspect JSON responses or Writing context previews. Do not execute arbitrary authenticated fetches via browser evaluation, scrape private runtime state, or guess credentials. Save retrieved response data locally with URL and fetched-at UTC. The site may change: inspect route implementations if responses differ. Never change source/policy controls just to obtain a preview.

The browser preview supplies the current retrieval packet and instructions, but is not an exact historical provider request or necessarily a fully frozen creative plan. Historical provider bodies are available separately through Writing context request inspection and must be labelled historical. If direct writing needs a missing creative plan, make a labelled author plan from the verified context; do not claim the app supplied it.

At creation, origins/events/histories have catalog entries; missing scene slots may be virtual and therefore absent. Inspect the territory and existing fictional scenes before planning a draft-only scene. Derive its setting from the verified territory/origin and factual anchor, mark `place_ambient` / `connective_fiction`, and use a local draft ID, NOT an invented database entry ID. No scene slot needs creating in the app to draft privately.

## Local snapshot, optional

The repository checkout is not the production database. There was no current campaign database in this checkout when the skill was created. Do not initialize an empty database, run migrations or refresh the Sheet just to make access appear connected.

If an owner-authorized SQLite snapshot becomes available, use the bundled `scripts/context.py --repo ... --db ... catalog` / `packet --key ...` helper. It opens an EXISTING database using SQLite `mode=ro` and `query_only`, uses NCCE's own catalog/retrieval functions, and never constructs `Store()` or calls a model. This reads that snapshot only; report its age/limitations. It cannot download the hosted database or publish prose.

## Saved work and standards

Bundled helper, run by the agent using available Python (the owner need not open PowerShell):

```
python scripts/journal.py --root C:/Codex/NCCE/.native-writing append --file event.json
python scripts/journal.py --root C:/Codex/NCCE/.native-writing timeline
python scripts/journal.py --root C:/Codex/NCCE/.native-writing export --output review.md
```

`event.json` is a UTF-8 object with `id`, `kind` (`batch`, `packet`, `draft`, `feedback`, `standard`, `decision`, `exception`), `batch_id`, `subject_key`, `form` as applicable, plus useful content such as `text`, `sources`, `attempt`, `status`, `supersedes` and `reason`. Helper assigns UTC storage time and content hash. Same ID/same data is idempotent; same ID/changed data fails. Write a new event referencing the old ID to revise. Timestamps reflect actual storage, not invented historical dates. Export is newest first with wide prose paragraphs, not a narrow table.

Store source packets as `packet` events and drafts as `draft` events linked with `packet_id`. Keep revisions and verdicts append-only. Journal storage does not itself enforce a writing budget, judge prose, publish, schedule work or activate instructions: the skill's agent must honor the saved batch limit and decisions.

The reviewer bridge remains review-only; the separate native-author connection handles authoring context, batch reservations, drafts and approved publication. Do not claim a review job as an authoring shortcut, submit prose as review JSON, replay failed feedback consolidation, or start the old five-minute automation. Preferred existing JKSimmons chat ID is `01a17f57-f5bb-7782-bce0-8b3b43dd367f`.
