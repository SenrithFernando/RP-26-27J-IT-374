# Provisional driver plan retrieval contract v1

Status: **API-ready; Hasara's app is not connected.** This is our provisional
boundary, not a claim about Hasara's existing API/mobile implementation.
No new account system, mobile app, database migration or optimizer was added.

## Endpoints reused and completed

- `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`: existing opaque bearer
  sessions; keep tokens private, never in URLs, logs, fixtures or documentation.
- `GET /routing/vehicles`: existing authorized vehicle list.
- **`GET /routes/published?vehicle_id=...&service_date=YYYY-MM-DD&direction=morning|afternoon`**:
  new read-only publication envelope over existing Daily Plan and route storage.
- `GET /routes/latest`: unchanged Admin/latest-generated contract. Latest can be
  draft; it must not be substituted for a published plan by Hasara's driver app.
- Existing `/trips`, `/trips/current`, `/trips/{trip_id}` and start/complete/cancel
  actions remain unchanged. Trip create/start still enforce current publication,
  vehicle permission and Sri Lankan service-date rules.

Use `/api` before these paths through Vite; use bare paths against port 8000.
Wire direction values are `morning` and `afternoon`, corresponding to AM/PM.
Use backend internal vehicle ID `MALABE_PP1_VAN_01` for external `VAN_01`.

## Authentication and response semantics

Every retrieval requires an unexpired login and object-level vehicle assignment.
Administrators may inspect; a driver may inspect only assigned vehicles. Parents,
unassigned drivers and anonymous clients cannot retrieve the vehicle's manifest.
Published-route and trip snapshots also pass existing route-level demo/provenance
checks. No client-supplied driver ID is accepted as authorization.

Required query: vehicle, service date, direction. Invalid query returns 422;
anonymous returns 401; an existing unauthorized vehicle returns 403. A mismatched
publication pointer returns 409. A valid authorized query with no published plan
returns 200, a null `published_route`, and an explicit publication status.

Envelope version: `saferide-driver-plan-provisional/v1`. Fields:

| Field | Meaning |
|---|---|
| `vehicle_id`, `service_date`, `direction`, `timezone` | Requested planning selection; timezone Asia/Colombo |
| `publication_status` | `published`, `draft`, `stale`, or `not_published`; no draft substitution |
| `published_route` | Existing serialized saved route, or null |
| `trip` | Existing serialized active trip for vehicle, otherwise latest school trip for requested date/direction, or null |
| `integration_status`, `note` | Provisional boundary and snapshot distinction |

An active trip is returned even when another date/direction is selected: its own
`trip.route.service_date`, direction, ID/version and pinned itinerary stay
explicit. Do not relabel its AM route as the selected PM plan. Its `trip.route`
is authoritative during execution, **not** the latest planning route. GET does
not solve, generate versions, change publication or modify trip state.

`published_route` is the same serialization used by Admin Daily Plan. It carries
route ID/version, ordered `stops`, grouped school `student_ids`/`student_names`,
student/school IDs, coordinates, ISO ETA/service departure, per-stop service and
waiting seconds, load, selected departure, all duration totals, provider source,
fallback reasons, model version, freshness and immutable input provenance.
All timestamps have offsets; display using Asia/Colombo. Integers are seconds or
metres as named. Grouped school visits must remain one ordered stop, not one
duplicate visit per participant.

`departure` / `departure_seconds` are the selected plan departure.
`departure_recommendation.recommended_departure_seconds` is the saved recommended
minute when that version was generated in recommendation mode. An override or
legacy fixed version may have no recommendation: show unavailable, never infer
one or fetch/solve a new recommendation automatically. Override validation status
remains explicit. Recommendations retain bounded-search/snapshot assumptions.

Stale dated inputs suppress the published planning itinerary. Active/completed
execution status can make `is_current` false for pre-trip purposes; an active
trip's saved manifest remains available independently. A newly generated draft
supersedes the Daily Plan pointer, so an earlier published plan is not silently
presented as the current publication.

Only the isolated Malabe Daily Plan currently has this publication lifecycle.
Other vehicles without a Daily Plan publication return `not_published`; the old
latest-route endpoint remains available for their existing Admin flows.

## Sanitized examples

These are schema examples with identifiers redacted, not invented optimization
results. ETAs, coordinates, durations and complete stops are intentionally omitted
here. The rollback verification compares actual complete serialized stops.

```http
GET /api/routes/published?vehicle_id=MALABE_PP1_VAN_01&service_date=2026-10-19&direction=morning
Authorization: Bearer <private session token supplied at runtime>
```

Valid unpublished response example:

```json
{
  "contract_version": "saferide-driver-plan-provisional/v1",
  "vehicle_id": "MALABE_PP1_VAN_01",
  "service_date": "2026-10-19",
  "direction": "morning",
  "timezone": "Asia/Colombo",
  "publication_status": "draft",
  "published_route": null,
  "trip": null,
  "integration_status": "API-ready; Hasara app not connected",
  "note": "Published planning route and active trip route are separate saved snapshots. GET does not optimize."
}
```

Published response excerpt (omitted fields are not literally returned as absent):

```json
{
  "publication_status": "published",
  "published_route": {
    "route_id": "<saved route ID, identical to Admin>",
    "version": "<saved integer version, identical to Admin>",
    "stops": "<complete ordered saved stop array, identical to Admin>",
    "departure_recommendation": "<saved object or null/absent>",
    "provider_source": "<saved actual source/fallback/model metadata>"
  },
  "trip": "<existing pinned trip object or null>"
}
```

## Exact Windows startup and authenticated verification

Restart the existing backend terminal (Ctrl+C first):

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep one Vite server running. If stopped:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

1. Admin login → **Authenticated operations** → **Daily Plan** → date 2026-10-19.
   Review attendance, confirmed pins and feasibility. Generate only when needed.
2. Publish the reviewed AM and PM plans separately. Resolve publication blockers
   and explicitly review unresolved morning evidence as required for PM.
   Record each route ID/version and stop order shown by Admin.
3. Admin → **Access**: select existing `driver.local`. Add
   `MALABE_PP1_VAN_01` to its vehicle assignments, preserving any intended existing
   selections. Save explicitly. Assignment changes revoke sessions; log in again.
   No assignment was silently changed by this checkpoint.
4. In a separate browser tab, log in as that driver using its private password.
   Select authorized `MALABE_PP1_VAN_01`, service date **2026-10-19**, and Morning.
   Confirm published route ID/version, school groups, stops, departure, ETA/service
   duration and source match Admin. Switch Afternoon and compare its own version.
5. Use **Refresh route**; otherwise polling runs every 15 seconds only while the
   page is visible. Hidden/unmounted/changed selections cancel obsolete requests.
   A draft/stale/no-plan result must not display a mock/current itinerary.
6. A different driver without that assignment must receive 403 when requesting
   the same URL. Do not reassign real accounts merely to test denial; the rollback
   test below creates temporary isolated driver identities and checks this.
7. Active trips show a separate fixed itinerary. Do not alter the PC date or start
   a future-date real trip just to test it; rollback tests patch the date only in
   test memory and verify a pinned AM manifest while the PM publication changes.

Historical inspection at the earlier checkpoint (superseded by the dated audit below): `driver.local` was active but assigned only
to `PP1_DEMO_0c1effd6_VAN_A`; current Malabe AM/PM publications are drafts. Thus
real-account browser publication/assignment verification remains an explicit
administrator step. No existing account or operational record was changed.

Rollback authenticated test-client checks (no paid calls, no persistent fixture
accounts/assignments, no worker lifespan):

Checkpoint results: **11 landmark/attendance/publication tests and 7 authorization
tests passed**. Four intercepted driver-boundary UI checks and nine existing
operations UI scenarios passed. TypeScript no-emit and production build passed.
The focused new boundary test was also run separately and passed; do not count
that repeat as an additional distinct test. No paid API calls were made.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
Set-Location ..\frontend
node scripts/verify-driver-boundary.cjs
node scripts/verify-operations-cleanup.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

The added boundary test verifies anonymous 401, unassigned driver/parent 403,
assigned driver AM/PM equality with Admin, grouped schools, duration accounting,
draft/unknown-date/stale suppression and active-trip pinning after PM regeneration.
It patches generation to raise during GET checks. It uses synthetic rollback
locations and temporary authenticated sessions; this is API behavior verification,
not a completed connection to Hasara's app or a physical driver journey.


## Administrator?Driver parity checkpoint ? 2026-10-20

Read-only database inspection found `driver.local` active and assigned to
`MALABE_PP1_VAN_01`. On 2026-10-21 PM is published: route
`ROUTE_1c68037325d544b59876c094f289d337`, version 63, nine stops;
driving/service/waiting/total are 1166/2520/0/3686 seconds.
AM version 80 (`ROUTE_dbf128fbfa044db5a18017ef95b35110`) is a **draft**,
not published driver instructions. These are saved estimates, not measured trips.
The 19 October planning pointers are stale/locked-completed; completed manifests
are history, not current pre-trip instructions. No existing publication or trip
was changed by this checkpoint.

A regression reproduced a 403 when a cancelled research journey was selected
as the school trip for the same vehicle/date/direction. The school retrieval
query now excludes non-active research trips. Any active vehicle trip still
appears separately with its fixed route snapshot, even across selected directions.
Closed research itineraries remain accessible through the research workflow.

### Exact browser comparison

1. Administrator ? **Authenticated operations** ? **Daily Plan**; select
   **2026-10-21**. Record the PM route ID/version, ordered actions, every ETA,
   school service intervals, saved planned duration breakdown and source.
2. In a separate browser profile/private window, log in as assigned
   `driver.local` with its private password. Select **Published school plans**,
   vehicle `MALABE_PP1_VAN_01`, **Service date (Asia/Colombo)** 2026-10-21,
   then **Afternoon Drop-off** and **Refresh route**.
3. Expand **Published route details and diagnostics**. Compare PM v63 and its
   stops/ETAs/durations with Admin. Both use the same persisted serializer.
   Counts and versions can change after a deliberate later administrator save.
4. Select **Morning Pickup**: the present draft must show no current published
   morning route. To compare a published AM, explicitly review and use Admin's
   **Publish reviewed AM plan** first. This audit did not publish it.
5. Do not start this future-dated trip merely for verification. Isolated tests
   cover active-trip pinning. An actual active trip displays its own **Fixed trip
   route** and **Fixed trip itinerary and estimates** independently of the selected
   planning route. A newer draft/publication must not change that fixed snapshot.
6. On an authorized active trip, **Navigate to next stop** targets only the
   confirmed current saved occurrence. **Copy link for navigation device** permits
   a second device while Chrome keeps foreground GPS. Neither advances the trip.
   Following confirmed arrival use **Next stop (manual; no passenger confirmation)**.
   At final arrival there is no further target; close deliberately with
   **End trip (manual prototype)** / **Confirm end trip** when appropriate.
   Do not create passenger evidence merely to demonstrate navigation.

### Sanitized contract examples

Authenticated request (existing private bearer session, omitted here):

```http
GET /api/routes/published?vehicle_id=MALABE_PP1_VAN_01&service_date=2026-10-21&direction=afternoon
```

Saved PM response subset from inspection (not an authenticated live capture):

```json
{"publication_status":"published","published_route":{"route_id":"ROUTE_1c68037325d544b59876c094f289d337","version":63,"direction":"afternoon","service_date":"2026-10-21","driving_seconds":1166,"service_seconds":2520,"waiting_seconds":0,"total_duration_seconds":3686}}
```

Draft response subset:

```json
{"publication_status":"draft","published_route":null}
```

The full response includes ordered stops with coordinates, ETA/service seconds,
selected departure, recommendation when saved, provider metadata and the separate
pinned `trip` snapshot. No credentials or coordinates are included in these examples.
GET does not start a trip, advance a stop, solve, publish or request Google.

### Reproduce local checks (Windows PowerShell)

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
$env:SAFERIDE_RUN_SHORT_RESEARCH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_short_research_route.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_saved_navigation.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_driver_duration_snapshot.py -v
Set-Location ..\frontend
npm run build
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
```

Intercepted browser tests use a separate local Vite process. In a separate terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npx vite --host 127.0.0.1 --port 5187
```

Then in the frontend test terminal:

```powershell
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-driver-boundary.cjs
node scripts/verify-driver-navigation.cjs
node scripts/verify-driver-durations.cjs
```

Browser responses are intercepted synthetic fixtures, not physical navigation
or Google evidence. Mobile checks cover 320?568 and 390?844 layout and navigation
states. Hasara's mobile app remains disconnected; this boundary is **API-ready**.


Checkpoint results: **27 backend tests passed** (14 landmark, 7 authorization,
3 short-research, 2 saved-navigation, 1 duration-snapshot). The boundary regression
failed with 403 before the query fix and passed afterward. Published AM/PM parity
checks guard both generation and Google HTTP transport against invocation during
retrieval. Three intercepted browser suites passed: publication/error boundaries,
next-stop/final-stop navigation, and seven duration/layout states. TypeScript
no-emit and `npm run build` passed. Vite retains a nonfatal >500 kB chunk warning;
Starlette reports an existing httpx deprecation warning.

Read-only preservation check: the stationary trip remains COMPLETED with 225
samples; the moving research trip remains COMPLETED with 90 samples. The current
21 October AM draft and PM published pointers are unchanged. No paid calls,
operational mutations, future real-trip starts, model changes or physical phone
verification occurred. Browser tests establish responsive layout and link
behavior, not Android Google Maps handoff or connection to Hasara's app.
