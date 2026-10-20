# Boarding evidence and PM school windows checkpoint

Scope: isolated synthetic test trips, existing provisional import adapter,
pickup state machine, school windows, worker and unique in-app notification
table. **Hasara card and parent delivery systems are not connected.** No actual
card scan, student boarding or parent-channel delivery was fabricated.

The completed physical-phone morning trip was not reused. Its 225-sample
non-coordinate metadata digest still matches the saved stationary checkpoint;
the session remains revoked and the trip remains COMPLETED. Test arrivals are
explicitly simulation fixtures on new rollback-only afternoon trips dated
2099-10-19. The computer clock and operational window duration were not changed.

## Existing behavior and missing pieces completed

- SCH_A remains Horizon College International; SCH_B Boys' Model College.
- Initial PM roster is seven, independently of AM. TEST_03 has PM=false, no PM
  pickup outcome and no missed-PM alert.
- Existing AM `boarded` / `no_show` / `unknown` import and pre-trip regeneration
  are reused. Confirmed no-show removes PM eligibility before departure; unknown
  remains unknown. AM=false does **not** overwrite PM=yes. An afternoon-only
  case remains eligible provisionally and requires the existing explicit policy
  review before publication; no production policy was invented.
- Existing shared PM windows remain **900 seconds per school**, with individual
  outcomes. Start is `max(confirmed arrival, 13:30 school release)`. An early
  arrival is retained; the existing worker opens it at release without needing
  a new GPS event. Repeated arrivals/worker calls never extend its deadline.
- Planned boarding service and the exception window overlap. In the controlled
  first-school test, both end at 13:45 from 13:30; no second 15-minute wait is added.
- Added afternoon manual test evidence to the **existing `kind=boarding` adapter**,
  not a second event table/endpoint. It operates on existing PickupOutcome and
  PickupTransition records and records the immutable LandmarkInputEvent envelope.
- Newly generated alert wording is **boarding unconfirmed at the deadline**, not
  a verified no-show or delivery failure. Legacy state/kind names MISSED and
  missed_pickup remain for compatibility. Earlier notifications are not rewritten.

## PM event contract and authorization

`POST /daily-plan/import` remains real-administrator-only. This checkpoint adds
an additive PM record variant to provisional v1. The generated schema is updated
in `provisional-routing-contract-v1.json`; it is not Hasara's existing API.
Exactly one PM record per event, producer `manual_test`, provenance `landmark_test`:

```json
{
  "schema_version": "saferide-routing-provisional/v1",
  "event_id": "<unique stable test event ID>",
  "occurred_at": "<observed ISO timestamp including +05:30 or Z>",
  "producer": "manual_test",
  "provenance": "landmark_test",
  "kind": "boarding",
  "reason": "Explicit isolated manual test; no card system connected",
  "records": [{
    "student_external_id": "TEST_05",
    "service_date": "<selected date YYYY-MM-DD>",
    "direction": "afternoon",
    "trip_id": "<isolated ACTIVE PM trip ID>",
    "outcome": "boarded",
    "resolves_event_id": null
  }]
}
```

Existing unique event-ID hashing makes an identical retry idempotent; reusing an
ID with different content returns 409. Receipt time comes from the backend after
locks; observed time remains separate. Date/trip/scenario and saved-manifest
participant membership are validated. A PM=false participant absent from the
manifest is rejected. Morning, closed and unrelated trips are rejected before
creating any event. Driver/parent submission is 403; anonymous is 401. The
existing assigned-driver **Confirm pickup (manual prototype)** action remains a
separate compatibility action with server lock-time semantics, not a card event.

## Deadline and delayed-evidence policy (provisional)

The valid boarding event interval is **started_at <= occurred_at < deadline_at**.
At exactly deadline, the event is not on time. Confirmation arriving before the
deadline changes the existing WAITING outcome to PICKED_UP, recording the event
time as picked_up_at and receipt time in audit. Server locks arbitrate races.

If valid pre-deadline evidence arrives after expiry:

1. Preserve the immutable event and effective/receipt timestamps.
2. Leave MISSED and the single original alert intact; return
   `delayed_evidence_pending_admin_review`. Do not trust a backdated manual input
   as an automatic reversal.
3. Admin may submit a **new unique event ID**, current review timestamp and
   `resolves_event_id` referencing the original same-trip/student PM event.
4. Explicit review may transition MISSED → PICKED_UP with the original event
   time, preserving the earlier MISSED transition and alert. Alert serialization
   reports `resolved_delayed_manual_test_evidence` and resolution receipt time.

Evidence at/after deadline is stored as `after_deadline_recorded_not_confirmed`;
it cannot become an on-time pickup through this review path. Cancelled outcomes
and closed trips cannot be reopened. Post-trip corrections/card reconciliation
remain a supervisor-policy gap; they are not silently applied. Manual test
evidence never establishes RFID/card authenticity or student delivery.

`GET /trips/{trip_id}/pickup-history` exposes the existing transition audit with
effective_at, recorded_at, action_source and reason containing the test event ID.
The original envelope/actor/receipt remains in LandmarkInputEvent. There is no
new notification system or destructive alert deletion.

## Alert generation versus delivery

The existing unique constraint `(trip_id, student_id, kind)` and locked outcome
transition enforce one persisted alert per applicable pickup. Expiry repeats do
not create duplicates. Picked-up/cancelled/PM=false participants do not receive
missed alerts. Alert metadata now distinguishes:

- `generation_status: in_app_event_created`
- existing `delivery_status: in_app_event_created` (historical API compatibility)
- `parent_channel_status: unavailable_hasara_not_connected`
- resolution status/time, without deleting the original event.

Admin/authorized prototype Parent can read their scoped in-app records. This is
not SMS, push, Hasara parent-app delivery or proof a parent read an alert. Existing
read/unread controls apply only to the local in-app event.

## Fast indoor demonstration: controlled clocks, no browser/real records needed

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_BOARDING_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_boarding_checkpoint.py -v
Remove-Item Env:SAFERIDE_RUN_BOARDING_TESTS
```

The five tests demonstrate real database-backed behavior in outer rollback
transactions: synthetic confirmed arrival 13:20, still no window at 13:29,
open once 13:30/deadline 13:45, boarding TEST_05 before expiry, cancellation of
TEST_06, then exactly one alert each for TEST_07/08. TEST_03 receives none. A
separate trip exercises delayed evidence at 13:46 about a 13:35 boarding, and
explicit review at 13:47, retaining one original alert. Another checks exact
deadline, and another no-show/unknown/AM-false eligibility and PM route version
recomputation. Worker calls use fresh sessions, without a browser or UI polling.

All transactions roll back, including temporary accounts, arrivals, routes,
events and notifications. Test clocks are injected in code only; 900-second
operational windows and the PC clock are unchanged. There is no GUI time-travel
or manual "confirm arrival" button to invent. The fast test's transient records
cannot be browsed afterward because they are deliberately not committed.

## Exact navigation for an explicitly provisioned isolated UI test trip

Use only a **different ACTIVE afternoon test trip**, never the completed physical
morning trip. No persistent UI-demo trip was created by this checkpoint. For a
live-clock UI demo, normal release/arrival and the full 15 minutes still apply.

1. Admin login → **Authenticated operations** → **Daily Plan** → selected date.
   Review **Dated attendance and manual test evidence**; TEST_03 PM=no.
   Set Morning test evidence selectors as appropriate and click **Record manual
   morning test evidence**. Missing evidence stays unknown; this is not card input.
2. Generate/review/publish a separate PM plan as needed using existing **Generate
   PM plan** / **Publish reviewed PM plan**. Do not overwrite an active manifest.
3. Assigned Driver → select vehicle/date → **Afternoon Drop-off** → **Persistent
   trip lifecycle** → select **Production - 15 minutes** and **Shared contiguous
   school visit** → **Create planned trip (manual prototype)** → **Start trip (manual
   prototype)**. Start is today-only. Use this new isolated PM trip ID.
4. Confirmed arrival must come through the existing authorized position/arrival
   flow. There is no new arrival button. Before 13:30 an early confirmed arrival
   cannot expire a school window. In Driver → **Pickup exception windows**, inspect
   **PRODUCTION - 15 minutes / Shared school visit**, Started and Deadline.
5. Admin → **Daily Plan** → **Manual PM boarding test evidence**. Fill **Isolated
   PM trip ID**, Participant, **Unique test event ID**, observed ISO time with
   offset and **Recorded reason** in the section above. Click **Record manual PM
   boarding test event**. An identical retry keeps the same ID/time/body.
6. For delayed review, retain the original event ID. Click **New test event ID**,
   enter current review timestamp, put the original ID in **Resolve earlier
   evidence event ID (optional; explicit Admin review)**, explain the review in
   Recorded reason and click **Record manual PM boarding test event** again.
7. Driver → **Refresh route** → **Pickup exception windows** shows each outcome.
   The existing **Confirm pickup (manual prototype)** / **Cancel pickup** actions
   are valid only when their server flags permit them.
8. Admin → **Notifications** → **Database missed-pickup events** → **Refresh
   in-app events**. Inspect generation, unavailable Hasara delivery and resolution
   separately. Parent login sees only linked students, not a recipient bypass.

## Validation and changed files

Actual checkpoint results: **5 controlled-clock boarding tests and 7 authorization
tests passed**; **8 intercepted Daily Plan checks and 9 existing operations UI
scenarios passed**. TypeScript and `npm run build` passed. These are isolated
synthetic/rollback or intercepted checks, not actual card/parent delivery evidence.

New: `backend/boarding_evidence.py`, `backend/tests/test_boarding_checkpoint.py`,
this guide. Updated: landmark import validation/event clock, pickup effective
timestamp, notification wording/metadata, DailyPlan test form, pickup/notification
display/types, provisional JSON schema and intercepted UI verification scripts.
No migration, card adapter fabrication, new worker or notification table.

No-cost checks:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
Set-Location ..\frontend
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

For intercepted UI checks, use an existing frontend origin or a separate local
test server. A phone HTTPS server need not be stopped. In a new ordinary terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_HTTPS_CERT=$null
$env:SAFERIDE_HTTPS_KEY=$null
$env:SAFERIDE_HTTPS_HOST=$null
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5187 --strictPort
```

In another terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-daily-plan.cjs
node scripts/verify-operations-cleanup.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
```

Stop only that temporary port-5187 server with Ctrl+C afterward.

Remaining gaps: real Hasara contract/card integration, real parent-channel
delivery, supervisor approval of provisional rules, closed-trip evidence
correction policy, and an actual live-clock end-to-end school boarding run.
Controlled-clock success does not establish any of those real-world behaviors.
