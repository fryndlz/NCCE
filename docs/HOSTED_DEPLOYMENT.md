# Hosted NCCE preview

**Current hosted service:** https://ncce-private-preview.onrender.com/

**Source repository:** https://github.com/fryndlz/NCCE (public)

**Deploy branch:** `main`

**Documentation checkpoint:** 2026-10-25 18:29:11 CET (Europe/Warsaw)

**0.6.0 rollout:** commit `e63b8ef` is live on the existing service. Render deployment `dep-dbf3oeom7kps73flj2hg` completed at 2026-10-25 18:29:06+01:00; public health returned version `0.6.0` and the protected dashboard returned 401 at 18:29:11+01:00. Full release record: `CHANGELOG.md`.

## Existing deployment

The free Render preview already exists. The owner made the GitHub repository public and authorized this hosting direction; the old instructions saying the repository is private and no service has been created are obsolete. Public source code and invite-access campaign reading are separate settings: the app still requires its shared passphrase.

The existing Python engine runs on the host and reads Krakamunda without writing the Sheet. Friends open the HTTPS link on a phone or computer. They do not install Python, create firewall rules, or run the local launcher.

`render.yaml` describes the current preview configuration:

| Setting | Value |
| --- | --- |
| Render service | `ncce-private-preview` |
| Runtime/region | Python / Frankfurt |
| Plan | free |
| Instances | 1 |
| Build | `python -m compileall -q src` |
| Start | `python src/server.py` |
| Health route | `/healthz` (the Blueprint specifies it; the inspected existing service currently uses the default TCP check) |
| Database | `/tmp/ncce-preview.db` |
| Sheet refresh | startup, every 900 seconds while running, and manual request |
| Campaign access | shared passphrase; signed session; secure cookies behind HTTPS |

The existing service displays `On Commit`, but its source is configured as a public Git repository URL rather than a linked Git provider; Render requires manual deploys for this source type. After pushing an app change, deploy the latest commit from the existing NCCE Render service, then check `/healthz` for the intended version and verify a protected campaign API returns 401 without a session. Do not create another site/service or ZIP for an iteration.

## Invite access and secrets

`NCCE_REQUIRE_AUTH=1` enables the shared passphrase gate. `NCCE_ACCESS_PASSWORD` and `NCCE_SESSION_SECRET` are host environment secrets, not repository files or campaign database content. The server rejects inadequate configured lengths. The signed HttpOnly/SameSite browser session lasts seven days; Secure is used for HTTPS. Rotating the passphrase invalidates existing sessions.

This is a shared campaign passphrase, not per-person login accounts, invitation tracking, or differentiated reader roles. Share it only with intended readers. The minimal health route and sign-in entry point are public; campaign APIs require a valid session when authentication is enabled.

## Ephemeral history limitation

The current free preview database is temporary. Render can stop/restart the instance or replace its filesystem during deployment. A missing database is reseeded from tracked baseline data, then synced to the current Sheet and regenerated. The first-live bridge can recover changes to fields already known at the seed baseline; it cannot recover every prior snapshot or every intermediate campaign event lost with the old filesystem.

The SQLite schema retains prior derived versions and factual history while that database exists. That schema property does not make `/tmp` storage durable. The hosted preview is suitable for trying the app, but its historical retention is not a production persistence guarantee. Sleeping free instances also pause the app's own background refresh; the next running startup/read refreshes state.

No paid service or persistent disk was created in this iteration. `render.production.yaml` remains an optional configuration for a later explicitly approved persistent deployment. It uses a paid single-instance web service and a 1 GB disk mounted at `/var/data`; its displayed plan and current price must be reviewed with the owner before creation. This document intentionally does not treat a historical price estimate as a current quote.

## Release verification record

At 2026-10-25 18:29:11 CET, deployment `dep-dbf3oeom7kps73flj2hg` was live on commit `e63b8ef`; public `/healthz` returned `0.6.0`, and `/api/dashboard` returned 401 without a session. All 29 deterministic checks and the disposable authenticated HTTP/live-sync smoke check passed locally. The hosted startup seeded schema 4, but no Sheet-sync completion appeared in the captured logs, so hosted sync completion and authenticated campaign content were not verified in this rollout. Mobile rendering was not inspected.

Responsive CSS is included. A full mobile visual check was blocked by the browser extension's URL-confidence access restriction; do not report mobile as verified until an actual phone or permitted mobile-browser check is completed.
