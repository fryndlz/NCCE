# Application shape

## Product
A local web application backed by a background service.

Normal use requires no terminal and no direct interaction with Python.

### Browser dashboard
The user opens a localhost address and can inspect:
- campaign overview and power shifts
- chronological battle feed
- each gang's mechanical and narrative history
- fighter histories and emerging characters
- gang-to-gang relationships and rivalries
- territories and contested locations
- generated battle reports
- campaign-level chronicle
- automation health / last successful sync

### Background service
Runs independently of the dashboard and:
1. polls the authoritative Google Sheet read-only
2. stores immutable snapshots
3. detects new battles and structured state changes
4. creates factual event records
5. updates narrative memory through an LLM
6. publishes reports to Google Docs
7. optionally calls local ComfyUI for picts

### Storage
Start with local JSON snapshots and event files because they are transparent and easy to audit.
Move to SQLite when the UI/history queries justify it. SQLite remains a single local file.

### Deployment
Phase 1: Windows local application on the campaign owner's PC.
Later, if multiple players need access, the same backend can be hosted and the UI can become a normal private web app without changing the factual/narrative architecture.
