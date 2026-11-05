# Connect the writing automation — NCCE 0.26.0

**0.27.0 upgrade:** the relay is already installed. Replace its Code.gs with the current tracked version (protocol 2); keep the same private key, manifest and timer. Do not install a second trigger. Queue status documents phases; only PENDING is writable. Legacy generated text is now included in the one-time backlog.

The code is implemented, but installation and Google authorization are required
before it runs. A deployed server alone does not install a Google trigger or a
task in your other ChatGPT account. No paid model requests are made by NCCE.

## One-time relay setup (in your browser)

1. Create a random secret of at least 32 characters using your password manager.
   Do not use the NCCE login password or paste the secret into a chat or cell.
2. Open the existing [Render service](https://dashboard.render.com/web/srv-dbejolgae00c73dcjma0).
   Under **Environment**, add `NCCE_EXCHANGE_TOKEN` with that secret. Preserve all
   other variables and deploy the update. The relay routes reject every request
   when this key is absent or shorter than 32 characters.
3. Open the existing [exchange Sheet](https://docs.google.com/spreadsheets/d/1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas/edit).
   Choose **Extensions → Apps Script**. In that bound project, paste
   [Code.gs](../scripts/writing_exchange/Code.gs) into its Code.gs file and save.
   If that project already has unrelated code, add a separate file and keep
   existing functions; merge an existing onOpen menu rather than replacing it.
4. In Apps Script **Project Settings**, show the `appsscript.json` manifest.
   Merge the settings in [appsscript.json](../scripts/writing_exchange/appsscript.json):
   V8 runtime, UTC, Sheets v4 advanced service and the three listed OAuth scopes.
   Alternatively enable **Services → Google Sheets API** and preserve other
   manifest dependencies/scopes if this project already uses them.
5. In **Project Settings → Script properties**, add `NCCE_EXCHANGE_TOKEN` with
   the same secret. Never put it in the script source or exchange workbook.
6. Select `installNCCERelay` in the function dropdown and click **Run**. Complete
   Google's authorization as the exchange owner. This performs a real sync
   first, then installs exactly one five-minute trigger for this account. Do
   not install the same trigger under a second account.
7. Return to the Sheet. Queue should now have at most five actual PENDING
   requests, with complete matching Context blocks. The Mara pilot remains
   IMPORTED. Automation instructions, Automation skill and Voice identity are
   separate reference tabs. `NCCE_LAST_SUCCESS_UTC` in Script properties records
   the most recent successful relay run; Apps Script **Executions** shows errors.
8. Give the work-account writing chat the message below. Verify one real
   scheduled run before leaving it unattended. READY becomes IMPORTED only
   after NCCE returns a committed receipt. Check one new entry in NCCE.

If authorization is unavailable in a managed account, stop at that step and
report the exact permission error; do not make the workbook public. Google
installable triggers run as their creator. Connected-tool writes do not fire
ordinary edit triggers, which is why this relay uses a clock trigger.
([Google trigger documentation](https://developers.google.com/apps-script/guides/triggers/installable))

## Copy this to your existing writing chat

> We have connected the NCCE writing exchange. Open
> https://docs.google.com/spreadsheets/d/1xokVbI3kya5koTqx9IOyUly2lP22batgLlo4oBlYBas/edit
> and read **Automation instructions**, **Automation skill** and **Voice identity**.
> Keep the literary style and examples established in this conversation.
> Process one PENDING request as a test, following the complete instructions:
> claim WRITING, read all matching Context blocks, write one complete Markdown
> entry into L, save/read it back, and set READY last. Do not touch IMPORTED
> entries or receipts. READY now authorizes automatic publication of your exact
> text. Do not generate variants, review passes or replacements after errors.
> After that test, if this work account supports scheduled tasks with this
> chat's context and read/write Google Sheets tools, create **one hourly task in
> this same chat** to follow those instructions, at most three PENDING requests
> per run. Avoid duplicating a task. When there is no work, generate no fiction
> and send no routine update; notify me of completed work, HOLD/errors or a
> required action. Confirm the actual task and tools work during a scheduled
> run. If scheduling/tool access is unavailable, tell me precisely what is
> missing; do not claim it is automated.

Scheduled tasks can use existing chat context and available connected tools,
subject to plan/workspace settings. We cannot create a task in your other
account from this Codex chat, and a Sheet update does not itself wake it.
([Official scheduled-task documentation](https://learn.chatgpt.com/docs/automations))

## Daily operation and recovery

NCCE discovers existing unwritten/earlier-draft slots during relay polling. It
holds at most five outstanding packets. The chat does at most three per hourly
run. As slots import, later polling fills the queue from the remaining backlog;
afterward only eligible new campaign slots or changed rolling histories need
writing. Already-ready prose and authored material are not bulk regenerated.
Gang origins remain authored-only; addenda use the existing authored dossiers.

Use **NCCE relay → Sync now** to transfer immediately. `stopNCCERelay` removes
this account's relay trigger; pause the writing task separately. Removing the
Render token disables relay access without changing existing prose.

If a delivery or receipt fails, keep its text and ID. The relay retries that
saved delivery, not the writing. HOLD and abandoned WRITING rows need explicit
reconciliation. No automatic timeout resets a claim or requests another draft.
Never edit a sealed request/context to make a rejected delivery pass. All
accepted and rejected submissions are retained in NCCE's persistent audit.

Verification still required after installation: one real private-Sheet
round trip, one automatic Google trigger and one actual work-chat scheduled
run. Local/HTTP/mock tests cannot substitute for these account-level checks.
