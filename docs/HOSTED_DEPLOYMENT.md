# Private hosted NCCE

## Goal

Open the campaign chronicle at one HTTPS link from a phone or computer. The host runs the existing Python engine and reads the authoritative Krakamunda Sheet without writing to it. The free preview uses temporary storage; the later paid production option keeps NCCE's derived database on persistent storage. Invited readers enter a shared passphrase; no one installs Python or opens a local firewall port.

## Free preview

`render.yaml` creates a free Render preview in Frankfurt with:

- the private GitHub repository as the deploy source
- HTTPS and a service health check at `/healthz`
- a temporary SQLite database at `/tmp/ncce-preview.db`
- server-side read-only Sheet refresh at startup and every 15 minutes
- generated passphrase and session-signing secrets
- one service instance

The preview costs $0 on Render's free service. Free services sleep after 15 minutes without visits and can take about a minute to wake. Their filesystem is temporary: after a restart or redeploy, NCCE reseeds its baseline and syncs the current Sheet. This is for trying the app, not for keeping a durable campaign event history.

## Invite access

Render generates an access passphrase and a separate signing secret. The server stores neither in the repository or SQLite. Give the passphrase only to invited people. Their browser keeps a signed, HTTP-only session cookie for seven days. Rotating the passphrase invalidates every existing session; the first version uses one shared passphrase rather than individual accounts.

Only the minimal `/healthz` check and the sign-in page are public. Campaign APIs and app assets require a valid session. The HTTPS proxy marks session cookies `Secure`.

## Persistent version, only if the preview is worth keeping

`render.production.yaml` describes the persistent version. It uses Render's paid `0.5c-512mb` web plan and a 1 GB persistent disk. Render currently lists the service at $7/month and disk storage at $0.25/GB/month; expected base cost is about **$7.25/month**, before bandwidth overages or future price changes. The Hobby workspace includes 5 GB monthly bandwidth, then lists $0.15/GB. Do not create this service until the owner chooses to keep the preview and approves the displayed price.

The persistent database starts from the tracked baseline and live Sheet sync; it does not import the local ignored `data/chronicle.db`. It is a single-instance design, suitable for a small campaign group but not high availability.

Pricing: https://render.com/pricing
Persistent disk behavior: https://render.com/docs/disks
Web service and HTTPS behavior: https://render.com/docs/web-services
Blueprint configuration: https://render.com/docs/blueprint-spec

## Preview steps (not yet performed)

1. Connect the existing private `fryndlz/NCCE` GitHub repository to a Render account. Render needs access to build and deploy that private repo.
2. Create a Blueprint from the default `render.yaml`; this is the free preview. Review the resource selection before creation.
3. Copy the generated passphrase from Render's service environment settings and share it only with invited readers.
4. Open the generated `onrender.com` HTTPS URL on desktop and phone; verify login, campaign display, `/healthz`, and live Sheet refresh.

The free preview has not been created. No Render account, service, GitHub integration, payment method, or credential is stored in this repository.
