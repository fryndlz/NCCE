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
Development: Windows local preview on the campaign owner's PC.

Shared use: private hosted web app over HTTPS, protected by an invite passphrase and backed by persistent SQLite storage. The host reads the authoritative Google Sheet and syncs on startup and every 15 minutes. Friends use the same link on computer or phone; they do not run the server locally.

The local web server remains a development aid. It is not the distribution model for invited players. Current hosted implementation and deployment approval gates are documented in `docs/HOSTED_DEPLOYMENT.md`.
