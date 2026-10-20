# Provisional registration/address geocoding checkpoint — 2026-10-20

Hasara's actual backend is disconnected. This is the existing authenticated `POST /daily-plan/import` provisional adapter, not another registration system or Hasara's production API. Existing external IDs, student/school/vehicle projections, backend geocoder, pin controls, durable planning events and saved route versions are reused. No migration is needed.

## Behaviour

- Assignment, school and vehicle records accept the existing address and optional coordinate pair. Nonblank addresses must contain at least three trimmed characters but are preserved verbatim in the raw event and current projection. Provider formatted addresses never silently replace the supplied address.
- An optional envelope `geocoding_http_budget` authorizes 0–3 configured lookup invocations for that event. Default zero preserves the existing no-paid-import behaviour. To trigger geocoding on an authorized address event, set it explicitly to 1 (or a bounded larger value for a small batch). Setup, page load and attendance events do not automatically issue paid lookups. Budget-deferred changes are reported as pending, never successful.
- A changed address, or an initial address with missing coordinates, invokes the existing configured geocoding flow when budget permits. Manual/missing-key/unsupported-provider cases return a failed lookup without invented coordinates. Geocoding provider calls time out after the existing eight seconds; at most three invocations are permitted by the import envelope.
- Partial or multiple matches are ambiguous. The first match is only an unconfirmed preview; candidate count/partial status and formatted address are retained for review. No building centroid is automatically accepted as a permitted roadside stop.
- Address-only changes clear obsolete coordinates before lookup. Failed/deferred address-only lookup leaves coordinates unknown. Explicit incoming coordinate pairs remain separate from the provider building/address suggestion and unconfirmed. Pin-only changes do not call geocoding unnecessarily.
- The raw input event and lookup outcome are stored together in existing `landmark_input_events.payload`. The original input hash remains separate from server-owned outcomes. Exact duplicate IDs/content return stored results with zero new attempts; changed content under the same ID returns 409. Existing v1 event hashes without the new optional field remain compatible. A different explicitly budgeted event may resolve a previously deferred/missing pin; unchanged resolved locations make no lookup.
- Late projection events remain ignored by the existing timestamp ordering. All record validation precedes provider calls. Unknown IDs and unauthorized users are rejected before lookup.
- Every changed location clears confirmation. Existing explicit **Save confirmed location** uses normal audited mutations and regeneration; manual corrections are not labelled successful automatic geocoding. Daily Plan shows the imported address, provider building suggestion, result/source and current confirmation independently. Prior outcomes and subsequent location-edit audit events remain in history.
- Existing dated fingerprints invalidate affected plans. Missing/unconfirmed coordinates block a current feasible plan and publication. Successful pre-trip replacements are drafts requiring review. Active/completed route/input coordinates are immutable and protected; input projection changes do not rewrite them. No GPS, observations or model artifacts are updated.

The address result lives in the event audit; the reviewed route stopping coordinate remains in the existing projection (legacy fields can still be named home_latitude/home_longitude). This is not a new first-class street-access or stopping-place model. An administrator must physically/map-review accessibility. The supplied address and reviewed stopping-point address can differ and remain auditable.

## Provisional payload

Schema: `docs/provisional-routing-contract-v1.json`. The adapter currently recognises the reviewed Malabe IDs TEST_01…TEST_08, SCH_A/SCH_B and VAN_01. It updates existing assignments; arbitrary new external registrations still return 422 until their mapping/contract is deliberately extended. Do not claim new Hasara registration ingestion is connected.

Generate an example with a fresh event ID and actual timestamp in ordinary Windows PowerShell (no credential/token involved):

```powershell
$addressEvent = @{
  schema_version = 'saferide-routing-provisional/v1'
  event_id = 'REG_ADDRESS_' + [guid]::NewGuid().ToString('N')
  occurred_at = (Get-Date).ToUniversalTime().ToString('o')
  producer = 'hasara_adapter_provisional'
  provenance = 'landmark_test'
  kind = 'assignment'
  reason = 'Explicit provisional landmark address review; Hasara disconnected'
  geocoding_http_budget = 1
  records = @(@{
    student_external_id = 'TEST_07'
    school_external_id = 'SCH_B'
    vehicle_external_id = 'VAN_01'
    active = $true
    address = 'SLIIT Malabe Campus, New Kandy Road, Malabe, Sri Lanka'
  })
}
$addressEvent | ConvertTo-Json -Depth 6 | Set-Clipboard
```

Importing this example changes the shared synthetic scenario participant's current address/pin review and affects its future school plans; it is not a read-only lookup. Use it only on the intended test scenario, or use the automated isolated tests below. Preserve the exact JSON/event ID for a duplicate test. Do not falsify timestamps or create duplicate accounts/registrations.

For a school, use kind school and its fixed school_external_id/name; for the depot use kind vehicle, vehicle_external_id VAN_01 and the capacity field required by the existing schema. Optional latitude/longitude must be supplied together, finite and in range; neither is automatically trusted as a reviewed stopping pin.

## Exact UI walkthrough

1. Restart the existing backend from `backend` with ` .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000` after stopping that terminal's old process. Keep the existing HTTPS frontend/proxy. No migration or password/account change.
2. Log in as administrator in **Authenticated operations → Daily Plan**. Pick an unexecuted service date if checking future plan effects; assignment/location updates are global and affect all relevant dated plans, not just the date selector.
3. Expand **Provisional registration/address import**. Paste the documented event into **Provisional registration event JSON**. Check the supplied address, event ID, timestamp, active assignment and explicit budget. Click **Import provisional registration/address event** once.
4. Inspect attempted/successful/ambiguous/failed/pending counts and **Location review**. An ambiguous/failed/deferred lookup is not a save failure: the changed input remains saved and affected routing is blocked/stale until review. The original address and provider suggestion are shown separately.
5. To verify idempotency, reopen the collapsed import section and submit the identical JSON. Expect duplicate feedback and zero attempts. Do not generate a new event ID for a retry of the same integration event.
6. In **Location review**, click the affected TEST_/school/depot button. Review the displayed raw incoming address and building suggestion. Correct the address/pin to an accessible permitted stopping point as needed. Use **Latitude**, **Longitude** or the draggable map pin; manual correction remains manual.
7. Check **I confirm this address and pin position are correct.** only after reviewing the vehicle stop. Click **Save confirmed location**. Inspect refreshed dated draft route versions and publication blockers. Publish only after explicit review; active-trip fixed itineraries do not change.
8. For a separate small live lookup without importing or saving: select a location, put the public landmark address in **Address**, then click **Look up address** once. This may incur one provider request. It returns an unconfirmed preview; leaving without **Save confirmed location** makes no database change. Do not click repeat or confirm a building centroid merely because the lookup succeeded.

## Actual evidence and counts

One explicit public SLIIT landmark lookup was performed through the configured existing flow: **attempted 1, successful 1, ambiguous 0, failed 0**, Google, one candidate, location_confirmed=false. No event, pin or database record was saved. Sanitized receipt: `docs/registration-geocoding-live-check.json`. This is one address lookup, not validation of accessibility or a general success rate.

Final mocked registration suite: **8 lookup invocations**, **6 successful**, **1 ambiguous**, **1 failed**. Invalid/unauthorized inputs, zero-budget changes, duplicates and resolved no-op updates made no additional invocation. These are synthetic test responses, not live success metrics. Failed and ambiguous records remain review-required.

Passed five isolated registration tests, four existing geocoder tests and fourteen existing landmark/attendance tests. The registration tests cover supplied-address preservation, initial missing pins, event hashes/idempotency, full validation before lookup, per-event budget, deferred resolution, ambiguity/no-match handling, separate supplied pin/building result, future plan invalidation and unchanged active snapshots. Database fixtures are session-private temporary tables under rollback; workers and paid providers do not run in the test process.

The nine-check intercepted Daily Plan UI script verifies import payload/event preservation, ambiguous result display and duplicate feedback without external calls. The intercepted adult-research UI check passes. TypeScript and production build pass with the existing nonfatal main-bundle-size warning. Preserved evidence remains 225 stationary GPS samples, 90 moving GPS samples and two moving-observation revisions, with both adult trips COMPLETED. No model training ran.

## Exact safe checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_REGISTRATION_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_registration_geocoding.py -v
Remove-Item Env:SAFERIDE_RUN_REGISTRATION_TESTS
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_geocoding.py -v
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Set-Location ..\frontend
# Set this to the existing frontend origin; script intercepts all API writes.
$env:SAFERIDE_UI_TEST_URL='https://YOUR_CURRENT_WIFI_IP:5173'
node scripts/verify-daily-plan.cjs
node scripts/verify-short-research.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
npx tsc --noEmit
npm run build
```

Limits: one synchronous lookup per changed record within the declared budget, no automatic retry of failed paid calls. If a process dies after an external response but before its database commit, exact-once billing cannot be guaranteed; inspect persisted event state before retrying. The bounded Daily Plan history shows latest per-entity results from the last 50 import events; full raw audit rows remain in PostgreSQL. Hasara's real backend, broader external-ID provisioning, automatic roadside-access validation and representative geocoding accuracy remain unverified/unconnected. No 95% or fleet-scale target is claimed.
