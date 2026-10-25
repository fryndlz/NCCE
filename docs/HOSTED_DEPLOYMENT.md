# Hosted NCCE preview

**Current hosted service:** https://ncce-private-preview.onrender.com/

**Source repository:** https://github.com/fryndlz/NCCE (public)

**Deploy branch:** `main`

**Documentation checkpoint:** 2026-10-25 21:13 CET (Europe/Warsaw)

**0.6.1 rollout:** commit `4816751` is live on the existing service. The service was upgraded to Starter, attached to a 1 GB disk, and configured to store SQLite at `/var/data/ncce-preview.db`. Follow-up commit `0768221` was redeployed to confirm persistence: the app started without seeding a new story database, and public health returned HTTP 200/version `0.6.1`. Full release record: `CHANGELOG.md`.

## Existing deployment

The Render preview already exists. The owner made the GitHub repository public and authorized this hosting direction; the old instructions saying the repository is private and no service has been created are obsolete. Public source code and invite-access campaign reading are separate settings: the app still requires its shared passphrase.

The existing Python engine runs on the host and reads Krakamunda without writing the Sheet. Friends open the HTTPS link on a phone or computer. They do not install Python, create firewall rules, or run the local launcher.

`render.yaml` describes the current preview configuration:

| Setting | Value |
| --- | --- |
| Render service | `ncce-private-preview` |
| Runtime/region | Python / Frankfurt |
| Plan | Starter (`0.5c-512mb`) |
| Instances | 1 |
| Build | `python -m compileall -q src` |
| Start | `python src/server.py` |
| Health route | `/healthz` (the Blueprint specifies it; the inspected existing service currently uses the default TCP check) |
| Persistent disk | 1 GB, mounted at `/var/data` |
| Database | `/var/data/ncce-preview.db` (`NCCE_DB_PATH`) |
| Sheet refresh | startup, every 900 seconds while running, and manual request |
| Campaign access | shared passphrase; signed session; secure cookies behind HTTPS |

The existing service displays `On Commit`, but its source is configured as a public Git repository URL rather than a linked Git provider; Render requires manual deploys for this source type. After pushing an app change, deploy the latest commit from the existing NCCE Render service, then check `/healthz` for the intended version and verify a protected campaign API returns 401 without a session. Do not create another site/service or ZIP for an iteration.

## Invite access and secrets

`NCCE_REQUIRE_AUTH=1` enables the shared passphrase gate. `NCCE_ACCESS_PASSWORD` and `NCCE_SESSION_SECRET` are host environment secrets, not repository files or campaign database content. The server rejects inadequate configured lengths. The signed HttpOnly/SameSite browser session lasts seven days; Secure is used for HTTPS. Rotating the passphrase invalidates existing sessions.

This is a shared campaign passphrase, not per-person login accounts, invitation tracking, or differentiated reader roles. Share it only with intended readers. The minimal health route and sign-in entry point are public; campaign APIs require a valid session when authentication is enabled.

## Persistent storage and remaining backup limitation

The service now stores SQLite on its attached persistent disk, so routine restarts and deployments retain the database. The service remains a single instance; deploying briefly interrupts access. The previous `/tmp` database was not exported during migration. The new disk database was seeded from tracked baseline data and will sync from the current Sheet. This cannot recreate every intermediate snapshot/event that existed only in the old volatile database.

The SQLite schema retains prior derived versions and factual history while the database exists. The app does not yet have an application-consistent SQLite export or offsite backup mechanism. Render disk snapshots are not a substitute for a database-native SQLite backup. A manual or automated SQLite online-backup export should be the next storage task.

Current estimated recurring cost is about $7.25/month on the Hobby workspace: $7/month for Starter compute plus $0.25/month for the provisioned 1 GB disk. Verify current billing in Render; usage and tax may affect the invoice.

## Release verification record

At 2026-10-25 21:08:51 CET, deployment `dep-dbf62uebs3rs73chu30g` was live on commit `4816751`; startup logs recorded `Seeded story engine /var/data/ncce-preview.db`, confirming the configured database path is on the mounted disk. At 21:13:27, a follow-up deploy of `0768221` completed without a fresh-seed log, confirming the mounted database survived redeployment; public `/healthz` returned HTTP 200 and `0.6.1`. The host launched its 15-minute sync scheduler, but a successful hosted Sheet sync was not independently confirmed in captured logs. Local validation remains 31 deterministic checks plus the authenticated HTTP/live-sync smoke check. Authenticated hosted data and phone rendering were not inspected.

Responsive CSS is included. A full mobile visual check was blocked by the browser extension's URL-confidence access restriction; do not report mobile as verified until an actual phone or permitted mobile-browser check is completed.
