# Private hosted NCCE

## Goal

Open the campaign chronicle at one HTTPS link from a phone or computer. The host runs the existing Python engine, reads the authoritative Krakamunda Sheet without writing to it, and keeps NCCE's derived database on persistent storage. Invited readers enter a shared passphrase; no one installs Python or opens a local firewall port.

## Prepared deployment

`render.yaml` describes one Render web service in Frankfurt with:

- the private GitHub repository as the deploy source
- HTTPS and a service health check at `/healthz`
- one persistent 1 GB disk at `/var/data` for SQLite
- server-side read-only Sheet refresh at startup and every 15 minutes
- generated passphrase and session-signing secrets
- one service instance, as required by this SQLite-on-disk design

If `/var/data/chronicle.db` does not exist, NCCE seeds it from the tracked baseline and canonical C-NINE source files, then starts the live Sheet sync. It never writes to the Google Sheet. The local `data/chronicle.db` remains excluded from Git and is not automatically copied to hosting; it is derived runtime state. The hosted ledger begins with the seeded baseline and records subsequent live changes.

## Invite access

Render generates an access passphrase and a separate signing secret. The server stores neither in the repository or SQLite. Give the passphrase only to invited people. Their browser keeps a signed, HTTP-only session cookie for seven days. Rotating the passphrase invalidates every existing session; the first version uses one shared passphrase rather than individual accounts.

Only the minimal `/healthz` check and the sign-in page are public. Campaign APIs and app assets require a valid session. The HTTPS proxy marks session cookies `Secure`.

## Cost and limits

This configuration uses Render's paid `0.5c-512mb` web plan and a 1 GB persistent disk. Render currently lists the service at $7/month and disk storage at $0.25/GB/month; expected base cost is about **$7.25/month**, before bandwidth overages or any future plan changes. The Hobby workspace includes 5 GB monthly bandwidth, then lists $0.15/GB. Confirm the dashboard's displayed total before creating the service.

Render's free web service has an ephemeral filesystem and spins down when idle; a persistent disk is available only with a paid web service. The paid disk is single-instance and disables zero-downtime deploys. This is acceptable for a small private campaign group but is not a high-availability setup.

Pricing: https://render.com/pricing
Persistent disk behavior: https://render.com/docs/disks
Web service and HTTPS behavior: https://render.com/docs/web-services
Blueprint configuration: https://render.com/docs/blueprint-spec

## Deployment steps (not yet performed)

1. Connect the existing private `fryndlz/NCCE` GitHub repository to a Render account.
2. Create a new Blueprint from the repository's `render.yaml` and review the paid resource total.
3. Create the service only after the owner approves the displayed charge and GitHub repository access.
4. Copy the generated passphrase from Render's service environment settings and share it with invited readers.
5. Open the generated `onrender.com` HTTPS URL on desktop and phone; verify login, campaign display, `/healthz`, and live Sheet refresh.

The service has not been created and no account or payment credentials are stored in this repository.
