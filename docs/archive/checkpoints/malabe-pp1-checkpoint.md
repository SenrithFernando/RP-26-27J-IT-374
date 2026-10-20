# Malabe landmark field test checkpoint

This is an isolated research scenario, **not Hasara's existing API**. School
assignments and attendance are demonstration decisions. Participant locations are
public landmark test destinations, not registered student homes or measured
student journeys. Imported/manual boarding outcomes are labelled test evidence,
never manufactured RFID/card events. There is no claim of physical GPS or
actual-data ML accuracy.

## Setup and run (Windows PowerShell)

Existing backend/.venv is reused. Stop the existing backend with Ctrl+C before
restarting updated code. No account password or assignment is changed by setup.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe setup_malabe.py
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Separate frontend terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

The new migration heads are 0016_landmark_daily_plan and
0017_grouped_pickup_outcomes. They add scenario/daily projections and allow many
individual outcomes at one grouped visit. They do not delete/relabel historical
records. Do not downgrade after creating grouped visits: the old one-outcome-per-
stop constraint cannot represent that history.

Setup is repeatable and insert-only. Internal IDs are MALABE_PP1_VAN_01,
MALABE_PP1_SCH_A/SCH_B and MALABE_PP1_TEST_01..08; external IDs are VAN_01,
SCH_A/SCH_B and TEST_01..08. The MALABE_PP1 scenario explicitly selects only its
eight registered IDs. Historical seeded vehicles/students cannot enter by query
accident or unknown import IDs. Existing accounts retain their assignments.

Initial date: 2026-10-19, Asia/Colombo. Initial confirmed attendance count: AM 8,
PM 7. TEST_03 is PM=no. All morning boarding evidence initially remains unknown.
Other dates do not inherit attendance; absent entries are unknown.

## Initial actual state

The real scenario is saved, but its plans are blocked by unconfirmed locations.
Only SCH_B has supplied coordinates (6.903543, 79.957162), and these are explicitly
unconfirmed. No depot, SCH_A or participant coordinates were guessed. The saved
initial read is [malabe-initial-plan.json](../../malabe-initial-plan.json); its blocked
route IDs/statuses are actual stored reads, not claimed successful optimization.
Setup never makes geocoding or other paid requests.

## Click-by-click review and planning

1. Open http://localhost:5173. Log in privately as admin.local, workspace
   **Authenticated operations**. Choose **Daily Plan** in Admin navigation.
   If setup was not run, select **Set up isolated Malabe scenario**.
2. Keep/edit Service date. Confirm VAN_01 capacity 20, AM 8 / PM 7 on the default
   date, SCH_A Horizon College International and SCH_B Boys' Model College.
   A different date starts with unknown attendance and cannot publish.
3. In Location review select Depot, both schools and each TEST participant.
   Original supplied addresses are retained separately, including ambiguous text.
   **Look up address** is an explicit administrator action that may incur Google
   charges. Review results; no failed lookup invents coordinates. Correct the pin
   manually if needed. Check **I confirm this address and pin position are correct**
   and select **Save confirmed location**. Depot review saves both configured depot
   endpoint fields. Registration imports containing changed address/coordinates
   clear confirmation and never issue automatic geocoding requests.
4. Review AM/PM attendance, enter the recorded reason and select **Save dated
   attendance**. Unknown must be explicitly resolved; active assignment is not
   attendance. A save can succeed while routing stays blocked/infeasible; that
   distinction is displayed. Dated edits regenerate affected pre-trip plans via
   the existing durable recovery orchestration, preserving active manifests.
5. For morning outcomes use **unknown**, **boarded**, or **no_show** and select
   **Record manual morning test evidence**. These are labelled manual test events,
   not card reads. Missing integration data never becomes no_show. Confirmed
   no_show excludes PM and causes applicable PM pre-trip regeneration.
6. Afternoon-only policy remains **Unresolved**. If AM=no and PM=yes, explicitly
   choose a test-only allow/deny decision with a recorded reason before publication.
   This is not a production policy. A confirmed morning no-show still excludes PM.
7. Choose an estimate provider, AM departure (at/after 06:00), and PM departure
   (at/after 13:30). Select **Generate AM plan** and **Generate PM plan**. Simulation
   is the explicit default. ML uses the existing synthetic-trained model. Google
   generation is an explicit paid-provider action; no live result is claimed here.
8. Inspect saved route/version, provenance, errors, stop order, arrival/service/
   departure, load and driving/service/wait/total durations. Technical input and
   review details are collapsed. Maps without road geometry retain the stop-
   sequence label; landmark markers do not claim student-home identity.
9. Publish AM when feasible/current and attendance is resolved. For PM, unknown
   morning evidence can remain in a provisional draft, but publication requires
   the explicit **reviewed unresolved morning evidence** checkbox and recorded
   reason. This review never creates boarding events. New versions require new
   publication/review; stale versions cannot create/start trips.
10. Existing trip APIs/controls are reused. If deliberately testing execution,
    explicitly assign the scenario vehicle through Admin **Access**, preserving
    any other intended assignments, then sign in again as the assigned driver.
    Setup does not do this for you. Only a published/current feasible saved plan
    can create/start a trip; start still requires today's Sri Lankan date. Do not
    change the system clock to start a future/past dated trip.

## Routing rules

- AM: depot start, all dated AM pickups (120 seconds each) before any school
  delivery; one grouped visit per school (600 seconds). School order and pickup
  order are chosen by the solver. Hard arrival <=07:15 and service finish <07:30.
  Preferred at/before 07:05 is a soft upper-bound buffer target; a miss is reported
  explicitly, never compensated by relaxing the hard bound. AM ends after the last
  school service. The virtual open sink contributes zero distance/driving and is
  not displayed; there is no depot-return leg/cost.
- PM: independently filtered PM roster; start is the SCH_B grouped boarding stop
  itself, not an extra colocated start. SCH_A collection follows before any home
  deliveries. Each school has 900 seconds planned boarding; each landmark delivery
  has 120 seconds. End is depot. Load is enforced throughout; since everyone boards
  before deliveries, peak load equals the selected roster count in this policy.
- The operational 900-second school pickup window overlaps planned boarding,
  rather than adding a second 15-minute optimizer service. It opens once at
  max(confirmed arrival, 13:30), never before release. Confirmed early arrival is
  retained; the existing worker opens the scheduled window at release, including
  after restart. Each participant retains an individual outcome in the shared
  school window. Arrival is proximity, not passenger confirmation.
- Existing expiry/notification logic is reused. TEST_03 has no PM pickup outcome
  or alert eligibility. The existing notification decision also suppresses PM
  alerts for an explicitly changed PM=no or confirmed morning no-show, even if an
  active manifest is retained. History and already-created events are not erased.
- Provider costs are precomputed and validated before OR-Tools callbacks; limits
  remain bounded. This is a departure-snapshot estimate, not a fully time-dependent
  solver, proven global optimum, or measured route performance.

## Provisional adapter contract

Machine-readable version: [provisional-routing-contract-v1.json](../../provisional-routing-contract-v1.json).
Endpoint: authenticated administrator real-workspace POST /daily-plan/import.
Hasara does not need to implement this exact format; it is our current adapter
boundary, to be mapped when Hasara's actual format becomes available.

Every envelope requires schema_version='saferide-routing-provisional/v1', a unique
event_id, timezone-aware occurred_at, producer (manual_test or
hasara_adapter_provisional), provenance='landmark_test', reason and records.
Unknown fields, unknown participant IDs, conflicting event-ID reuse, reversed
school mapping and implausibly future timestamps are rejected. Repeated identical
event IDs do not generate duplicate versions. Older projection updates cannot
overwrite newer ones. Imported coordinates remain unconfirmed until pin review.

| kind | Record fields |
|---|---|
| vehicle | vehicle_external_id=VAN_01, capacity 1..20; optional address/paired coordinates for depot |
| school | school_external_id, correct name; optional address/paired coordinates; fixed start/hard/preferred/release/service/window times |
| assignment | student_external_id, school_external_id, vehicle_external_id=VAN_01, active; optional participant address/paired coordinates |
| attendance | student_external_id, service_date, am and pm: yes/no/unknown |
| boarding | AM: student_external_id, service_date, direction=morning, outcome: boarded/no_show/unknown. PM manual-test extension: trip_id, direction=afternoon, outcome=boarded, optional resolves_event_id; see boarding-window-verification.md. |
| policy | afternoon_only: unresolved/allow/deny, explicitly test-scoped |

Boarding v1 imports morning test evidence only. Afternoon manual confirmations
reuse the existing authorized trip pickup controls/endpoints; no external card
integration is asserted. Public event payload examples are represented by the
schema and UI submissions; no fake card events are seeded.

New endpoints: POST /daily-plan/setup, GET /daily-plan?service_date=YYYY-MM-DD,
POST /daily-plan/import, POST /daily-plan/generate and POST /daily-plan/publish.
All require an administrator in Authenticated operations. Existing route/trip/
position/notification APIs and authentication remain available and protected.

## Verification commands

Actual checkpoint results: 9 landmark rollback tests, 7 authorization rollback
tests and 20 pure solver/provider/endpoint tests passed. Four Daily Plan browser
checks and nine existing operations browser scenarios passed using intercepted
responses; TypeScript and npm run build passed. See
[malabe-checkpoint-verification.json](../../malabe-checkpoint-verification.json).

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS = '1'
$env:SAFERIDE_RUN_AUTH_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dual_route_solver.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_endpoints.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
Set-Location ..\frontend
node scripts/verify-daily-plan.cjs
node scripts/verify-operations-cleanup.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

Scenario integration tests use confirmed **synthetic rollback-only coordinates**,
not the real scenario's unknown landmarks. They cover initial mapping/counts,
grouped order/load/time, nonzero open-end cost, explicit soft-buffer miss, hard
failure, unconfirmed pins/unknown attendance, dated immutable snapshots, import
authentication/idempotence, no-show versus unknown, generic pin-review replan,
published-trip protection, shared release/window worker processing, and PM=false
notification suppression. Actual Android/live Google/real-data ML accuracy is not
tested in this checkpoint. The frontend check intercepts mutations and external
requests; its starting fixture is the actual unconfirmed scenario read.

## Changed modules in this checkpoint

New backend: landmark.py, landmark_solver.py, setup_malabe.py, migrations 0016 and
0017, tests/test_landmark_daily.py. Extended: models.py, route_service.py,
route_schemas.py, route_api.py, planning_state.py, planning_orchestration.py,
trips.py, pickup_windows.py, pickup_worker.py, notifications.py, auth.py, main.py.
Frontend: new pages/DailyPlan.tsx and scripts/verify-daily-plan.cjs; extended
AuthenticatedApp.tsx, LocationPicker.tsx, RouteMap.tsx, TrafficDetails.tsx and
services/api.ts. Documentation: this guide, schema and actual initial-plan read.

Remaining blockers: administrator confirmation of all landmark/depot/school pins;
resolution of ambiguous supplied addresses and any dated unknown attendance;
explicit PM boarding review; Hasara's real contract/integration. No actual landmark
route distances/ETAs are claimed before those inputs are confirmed. No accounts
were recreated, no existing assignments silently changed, no historical records
deleted, no Neon migration and no model retraining occurred.
