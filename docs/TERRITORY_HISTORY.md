# Territory identity and confirmed transformations — 0.28.0

Implemented 5 November 2026. No campaign Sheet, raw archive, saved snapshot or
current mechanical territory row is edited by this feature. Schema remains 18.

## Evidence and identity

The visible Territories/Battles tabs are current mechanical authority. MAIN!B2's
Data Dump retains older names and ownership. It exposes `created_at` but no
territory `updated_at`; creation does not date a conversion. The normal name join
can wrongly reuse a gang's default Settlement source ID for an additional
Settlement. This release adds explicit, source-cited derived identity bridges,
without rewriting those source values.

`data/lore/territory-history-confirmations.json` binds only a unique active row
matching gang ID, current type and default/non-default flag. Ambiguous/missing
matches do not resolve. These bindings currently cover:

- Ethernetans' additional Settlement: former Gambling Den, source territory
  `4e5b06e8-bf45-4fb4-835b-7bb3a9ae0dd7`. Owner confirmed fuel-rod conversion.
  Battle `85379750-5c9d-44c2-b3a8-60e51de9e6ae` supplies the source-ID bridge;
  its date is not a conversion date.
- Slag Eaters' additional Settlement: source territory
  `2c676e49-7999-42e6-963e-967ee9a4d24b`, already named Settlement in the older
  raw dump under Kly. Battle `9bbcc8a2-bdea-4682-bfff-bcd1c33b5fda` records its
  capture in The Trap, 20 October 2026. This is not a confirmed conversion.

Starting Settlements remain separate. A future transfer that no longer matches
the explicit binding needs a new supported bridge; the system does not select
another Settlement or infer identity from row position alone.

## Ledger, timeline and event stream

Full story projection calls `territory_history.apply()` before reading events.
Each explicit conversion appends one deterministic `territory_type_changed`
event under an `owner-confirmed:` key, citing a `player_authored` confirmation
source. Identity entities retain mechanical provenance; the confirmation event
has its own independent authority. Existing events are never rewritten. Changes
to an already recorded confirmation require a new correction key, not an edit to
the immutable event. Rebuilds do not duplicate the event.

The Gambling Den conversion has `occurred_at=null`, `observed_at` equal to the
recording of the owner confirmation, and explicit unknown-occurrence/unknown-
owner-at-conversion flags. Current holder identifies the gang lane, not who
owned it at an unrecorded historical instant. Before/after type states do not
invent historical ownership. No unit's recruitment, injury or event clock is
advanced by this territory fact.

The shared timeline reads this event through `territory_ledger`. Its dot appears
at confirmation time and the detail explicitly says actual event time unknown.
The event is labelled owner-confirmed history and links to the place. Both
backend phase classification and frontend battle/downtime grouping exclude this
undated conversion from battle windows and downtime intervals. It is not a new
conversion occurring on 5 November. Usual Imperial/real-date wrapper formatting
continues to apply to the recorded timestamp.

World streams resolve the stable source bridge and Gambling Den alias to the
same additional Settlement and create a separate pending `place_event` slot.
Its diegetic text is written by the external chat under the existing waterfall;
no provider is called by this code. The type-change event is not a second place.

## Origin-writing exception

Candidate context for this specific origin includes `origin_history_exception`:
establish the former Gambling Den identity and briefly acknowledge conversion
to the present Settlement by an isotropic fuel rod. Its separate conversion
event remains in the history stream. Dates, casualties, battle attribution and
owner at conversion are not invented. Confirmation/source language stays in
the UI/evidence layer. Other place origins keep their normal static-baseline
boundary. Explicit history is source-labelled separately from mechanics in the
exported packet. User-authored prose is not replaced.

## Owner-paused request amendment

The owner paused request `9220a6eb-d32f-4f00-a2fd-c33b32979a68` while it was
WRITING. Only this manifest-authorized request can receive the amendment.
`amend_paused_origin()` requires matching logical target, server PENDING state,
client PENDING/WRITING, and source equality after removing only the newly added
history/exception fields. READY/imported/held work is not amended. Other source
changes keep the normal fail-closed HOLD behavior.

The original packet, target, revision and reason are retained in
`target_json.brief_history`. The new context/revision are returned as a private
relay amendment. Apps Script writes the complete corrected Context first,
rechecks ID/status/old revision/saved prose, then updates only source_revision
in Queue. It never resets WRITING or edits Markdown. Repeating the amendment is
idempotent. If the writer races to READY on the old revision, its draft remains
saved and requires reconciliation; it is not silently published or regenerated.
The writer must reread matching Context before resuming the paused entry.

## Verification

Disposable-state tests cover unique/non-default resolution, no source-row edits,
single immutable event, unknown dates, no fake Orlock conversion, timeline lane
and place links, persistent world-stream slot, origin exception scope, audited
same-ID amendment and acceptance of its revised delivery. Real Apps Script mock
tests verify preservation of partial Markdown and WRITING status while updating
Context/revision. Frontend tests exclude undated confirmations from battle and
downtime panels. Startup/live-source HTTP smoke verifies compatibility with
normal mechanical entity registration.
