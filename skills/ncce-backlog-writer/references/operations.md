# Native operations: run these yourself

Python: `C:/Users/Blazej/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
CLIENT: `C:/Users/Blazej/.codex/skills/ncce-backlog-writer/scripts/client.py`.
Commands below abbreviate those paths as `python CLIENT`; execute them yourself, not via instructions to the owner. Existing private credentials are loaded automatically from `C:/Codex/NCCE/.codex-review-bridge/config.json`; never print them. Calls use only the dedicated `/api/native-author/` connection, never reviewer claims or an external writer API.

## Discover and recover

```
python CLIENT batches
python CLIENT catalog
python CLIENT context --key RECORD_KEY
python CLIENT status --id BATCH_OR_DRAFT_ID
```

Each successful call saves its COMPLETE response privately under `C:/Codex/NCCE/.native-writing/response-UUID.json`, returning a small manifest with path/hash/sections. Read relevant sections with bounded pages:

```
python CLIENT read --file RESPONSE_PATH --sha256 RESPONSE_HASH --section /context/packet --offset 0
```

Follow next_offset until complete=true. Pointers include /subjects, /forms, /targets, /attempts, /context/instructions, /context/reviewer_standards, /document, /checks. A context-only response has /packet instead of /context/packet. Never assess incomplete/truncated context. Responses identify hashes and exact server draft/batch IDs.

## Reserve, write, save

```
python CLIENT start --forms territory_origin place_event place_ambient territory_history --keys KEY1 KEY2 --max-drafts 4 --request-key STABLE_BATCH_REQUEST_ID
python CLIENT prepare --batch-id BATCH_ID --key KEY1 --request-key STABLE_ATTEMPT_REQUEST_ID
python CLIENT save --draft-id DRAFT_ID --file OUTPUT_FILE
```

Choose actual catalog keys. Omit --forms for all 15; omit --keys for eligible records across those forms, still bounded by max-drafts. Missing-only default. --replace-generated requires owner authorization. Without --key, prepare selects the next unattempted target in dependency/date order. Choose explicit --key for bounded revisions.

Prepare reserves BEFORE generation, freezing source context. Repeat the SAME request key to recover the SAME reservation, never use another key after uncertainty. A second reservation while one is unresolved is blocked. If interrupted before saving, inspect retained output and state; do not assume no generation occurred. Five reservations per entry and overall max-drafts persist across restarts. Neither helper calls nor saving renews allowance.

For a known failed/invalid attempt, retain its raw output locally and close the reservation with `python CLIENT abandon --draft-id ID --reason "Specific failure"`. Abandonment keeps its packet and consumes its attempt permanently; it never refunds allowance. Then reserve a new bounded revision. Do not abandon an uncertain interrupted attempt without investigation/owner direction. Already saved/published drafts cannot be abandoned or overwritten.

OUTPUT_FILE is private UTF-8 JSON with exactly output and checks:

```json
{
  "output": {
    "paragraphs": [{"runs": [{"text": "The actual narrative paragraph.", "marks": []}]}],
    "composition": {"heading": "", "subject": "", "body_heading": "", "closing_label": "", "closing": "", "signoff": ""}
  },
  "checks": {
    "source_fidelity": "Specific source checks and relevant IDs.",
    "chronology": "Time and continuity checks; tentative draft dependencies identified separately.",
    "viewpoint": "Narrator/form/length checks.",
    "repetition": "Batch mechanisms and endings checked.",
    "uncertainty": "Specific remaining uncertainty or none identified."
  }
}
```

Omit composition for fighter_memory, fighter_reflection, fighter_mind. For documentary forms use actual supplied format, not these empty demonstration values. Paragraphs may be strings; run marks use the existing writer schema, not HTML. Notes are author's assertions, not independent validation. Server gates formatting/meta-language/provenance/freshness, not literary merit or factual reasoning. Saving is idempotent for identical content; changes need another reserved attempt. After network uncertainty inspect status, do not regenerate.

## Publication, only within owner approval

```
python CLIENT publish --draft-id DRAFT_ID --confirm-publish EXACT_PUBLISH_HASH
```

Hash comes from saved draft status/manifest. Match it to approved prose or an explicit publication scope. A self-score, saved draft or skill installation is not approval. Repeating publication of the same approved draft is idempotent. Changed source/continuity/guidelines rejects publication while retaining draft. Refresh context and reserve a bounded revision; never weaken the check.

Only derived targets change. Generated artifact predecessors remain versioned; entry/memory/thought preimages remain in the immutable native draft audit. Scenes create no mechanical event. Authored content is protected. No guideline activation, listener change or model request occurs.

## Feedback and stop

Use installed scripts/journal.py to append feedback/standard events with scope, form, draft IDs and reason. Mark superseded rules by ID. Read relevant non-superseded standards before the next draft; they are guidance, not facts.

```
python JOURNAL --root C:/Codex/NCCE/.native-writing append --file EVENT_JSON
python JOURNAL --root C:/Codex/NCCE/.native-writing timeline
python JOURNAL --root C:/Codex/NCCE/.native-writing standards --form FORM
python CLIENT stop --batch-id BATCH_ID
```

Stop blocks new reservations, while allowing already-reserved output to be saved. Publication still needs approval. A new batch requires authorized scope, not automatic renewal. Review events remain separate; checkpoint authoring rather than returning prose through reviewer complete. If native access is unavailable, never fall back to paid JuniorWriter; use [access fallback](ncce-access.md) honestly or report the blocker.

Use standards --form before drafting: it selects current shared/category rules and excludes superseded IDs. Keep a rule's form explicit when it is category-specific. Local standards take effect for subsequent native drafts without altering app guideline pointers.
