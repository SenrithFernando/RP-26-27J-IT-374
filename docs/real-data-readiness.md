# SafeRide-LK: real-data readiness audit

> Authentication follow-up, 18 October 2026: mandatory login, account/object permissions and scoped tracking authorization are now implemented; migration head is 0014_authentication. The findings below remain a historical pre-authentication snapshot. See [current authentication, private setup and verification](authentication-and-device-access.md). This does not establish phone measurement accuracy or production readiness.

> Follow-up, 17 October 2026: the five fixture positions identified below were subsequently corrected with append-only audits; migration head is now 0013_fixture_provenance. Counts and test totals in this audit describe its original pre-correction snapshot. See [provenance correction, current counts and regression checks](provenance-correction.md). No model retraining occurred.

**17 October 2026, Asia/Colombo.** This is an implementation/evidence audit, not a production-readiness certification. No completion percentage is assigned. Simulation remains useful and was preserved.

## Scope and fresh evidence

Inspected backend code, migration revisions 0001?0012, configuration example/loaders, frontend consumers, model artifacts, tests and stage/PP1 documentation. Actual credential values were not printed. No application features, configuration, training data or model artifacts were changed. No existing trip records were modified, replayed or transitioned.

- **35 tests passed, eight database-mutating tests skipped, zero failures/errors** (43 discovered). Socket connections were blocked during discovery/execution, preventing paid external calls. [Summary](real-data-readiness-checks.json), [log](real-data-readiness-checks.txt).
- **TypeScript check and npm run build passed**, exit 0; Vite transformed 1,728 modules.
- Read-only PostgreSQL transaction and Alembic current agree on **0012_operational_episodes (head)**. No migrations, seed or workers ran.
- Loaded the existing XGBoost JSON bundle with checksum validation. Training CSV hash matches saved metrics; final-test predictions and baseline metrics recomputed without fitting match the stored report.
- Inspected main.app OpenAPI in-process without starting lifespan, which would run expiry/planning workers. There are **49 API operations, no security schemes and no operation security requirements**.

[Read-only inventory](real-data-readiness-inventory.json) records endpoints, source counts, safe credential-presence booleans and actual metrics. [Previous PP1 audit](pp1-verification.md) records 43 passing tests with isolated database fixtures and a two-tab Admin/Driver check on 16 October. Those database/browser results are **historical evidence**, not fresh integration checks today.

## Implemented features and evidence boundaries

| Area | Implementation found | Verified now / remaining boundary |
|---|---|---|
| Authentication | No login/session/device authentication or server-side principal/ownership enforcement found; React role selection and prototype vehicle/student selectors | OpenAPI security absent. Parent filtering is not authorization. Real-user rollout blocker |
| Persistent students and planning | PostgreSQL students/schools/vehicles, confirmed locations, deactivate/transfer; durable roster revisions/events; automatic both-direction regeneration, both vehicles on transfer | Schema and source inventory read-only today; historical database tests cover save/idempotency/failure/transfer. No mutation today |
| Route constraints | Independent morning home?school and afternoon school?home, mandatory pickup/delivery per active student, fixed vehicle, capacity, school times, start/end, service/departure/horizon settings | Fresh pure tests cover coverage, correct destinations, load bounds with roster greater than capacity, zero-duration precedence, impossible deadlines/missing coordinates/unreachable costs. Matrices precomputed before callbacks; bounded solver, no proven global optimum |
| Driver route view | Database vehicle selector, latest stored route/version/freshness/actions/names/coordinates/ETAs, separate driving/service/wait/total and map | Serializer/date-freshness tests passed. Code cancels obsolete requests, cleans up, polls visible page every 15 s. Prior browser version/stops matching verified; main Driver screen still demo |
| Trips | Persistent PLANNED?ACTIVE?COMPLETED/CANCELLED; saved route FK pins version, aware timestamps/Sri Lankan display, unique active vehicle | Schema/code and historical duplicate/race/restart/pinning tests. No transitions today. End does not confirm delivery; no active rerouting |
| Positions | Ingestion/latest/bounded history, aware recorded/received time, coordinates/speed/vehicle/trip validation, deduplication, ordered latest, indexes, source and age/stale | Schema/read-only counts inspected; prior DB/restart tests. No actual phone sender or field trial established |
| Arrival | Current stop of active trip only, entry/exit hysteresis, dwell/count/gap/freshness, GPS-recorded time, one persistent event and manual next stop | Fresh settings/count checks; historical boundary/gap/dedup DB tests. Proximity is not pickup/delivery confirmation |
| Pickup windows | Arrival-triggered durable deadline, 900 s production; explicit simulation_demo timing; individual outcomes, provisional shared school visits, backend expiry worker/restart recovery | Fresh grouping tests; historical expiry/restart/race evidence. Policy explicitly supervisor_confirmed=False; no worker started now |
| Notifications | MISSED plus persistent in-app event in same transaction; DB uniqueness, student filter and separate read state | Code/constraints plus historical concurrency/restart/scoping tests. No SMS/push; no authenticated parent ownership |
| Deviation/stop | Pinned route, metre point-to-polyline, sustained ordered fresh samples, episodes/recovery, expected dwell exclusion | Fresh math/geometry tests; historical six-scenario integration. Stop-sequence geometry approximate; no accuracy/precision/recall/crash claims |
| ML/fallback | Actual XGBoost predictions form duration matrix; synthetic historical baseline/unavailable, per-leg source/mixed labels, directed simulation scenarios | Fresh inference equality, missing-model 503, forced-failure solve, mocked timeout/quota/partial matrix/unreachable and same-matrix comparison tests. No paid live success verified |

## Classification of inputs and outputs

Measured, live provider estimate, ML prediction, synthetic and mocked are distinct. Administrative/configured state is identified separately: calling a database timestamp or solver ETA a measured road journey would be false. A supplied source label is a declaration, not evidence.

| Input/output | Classification and current evidence |
|---|---|
| Student/school/vehicle records, confirmed home/depot/school coordinates | Supports declared measured/live-provider/synthetic via measured/live_provider/simulated. **Current: 83 schools, 88 vehicles, 192 students, all tagged simulated.** Manual pin acceptance is not surveyed accuracy; method is separately manual/google/manual_correction |
| Google geocoding | Live provider location estimate only on actual success; mocked in tests. Manual correction is manual, never successful automatic geocoding |
| Capacity, bell/departure/service times, geofence/scope/dwell settings | Operator configuration, not measured travel or ML output. Current fixture settings synthetic. Actual deployment requires verified schedules/capacity and approved policy |
| Position coordinates/speed/recorded_at | Measured only with actual device provenance; otherwise synthetic replay/test input. **659 simulation rows; five actual_device-tagged rows, all on S9B synthetic fixture vehicles.** No physical phone measurements established. Unknown speed stays null |
| received_at, action/read/creation timestamps, solver runtime | Measured system processing metadata, not measured driving or proof of passenger events. Controlled-clock tests mock timestamps |
| GPS age/fresh/stale/unknown | Derived from submitted time and server clock; inherits trust/source. Missing/stale GPS is unknown movement, not stopped |
| Simulation costs/scenarios | Synthetic haversine approximate distances and simulated durations; scenarios selectively change directed edges/corridors |
| Google traffic matrix and road geometry | Live provider estimates only after actual response; success/failure fixtures are mocked here. Routes and Static Maps keys absent; no live success verified |
| Weather flag | User-supplied planning feature or synthetic dataset input, with explicit missing encoding; no actual weather observation/forecast provider |
| Training duration_s and CSV rows | Synthetic: 2,000 observations/400 trips, nonlinear time/segment/weather/noise recipe. Not measured actual travel. Test regeneration only in memory |
| XGBoost durations | ML predictions trained on synthetic data, not measurements or live traffic. Unknown IDs/missing weather explicitly handled |
| Historical-average baseline | Statistical estimate from synthetic training targets, segment mean/global unseen fallback; not real measured historical performance or XGBoost inference |
| Stop order, loads, driving ETA/distance | Solver-derived plan from labelled costs, not observed arrivals; mixed per-leg provenance retained. Approximate distance stays approximate |
| Service/wait/total and comparisons | Configured service plus computed waiting and estimated driving. Alternatives repriced under same matrix; not measured savings or guaranteed improvement |
| OSM tiles/stop-sequence line | Display/cartographic context, not traffic/routing observations. Sequence line is approximate connecting geometry. Provider geometry is not independently surveyed road proof |
| Arrival/deviation/unexpected stop | Derived from underlying GPS: synthetic under tests/replay, measurement-derived only after valid real-device input. Not boarding confirmation or crash diagnosis |
| Trip state/manual pickup | Recorded manual prototype assertion/state, not RFID verification. Persistent delivery confirmation unavailable |
| MISSED/in-app notification | Deadline-derived ?no recorded confirmation?, not proof of physical absence. Inherits trip/GPS mode; only in-app event created, no SMS/push |
| UI boarding/history/camera/calls/emergency/counters/animations | Mocked UI state and synthetic constants, not authoritative real observations |
| Error/unavailable output | Absence of an estimate with reason, not a fabricated zero/prediction. Routing follows explicit requested fallback or unavailable |

## Reachable application paths still using demonstration constants

There is no complete production-mode boundary. Disabling the demo toggle does not replace these data sources with server records.

| Path | Current demonstration dependency |
|---|---|
| frontend/src/contexts/AppContext.tsx | MOCK_VEHICLES/STUDENTS/crew, BUS-01, ST001, MORNING_STOPS; fixed route 28.4 km and 78/81/79 min; seeded notification. React-only startTrip/endTrip; endTrip claims ?All students accounted for? without persistent proof |
| frontend/src/pages/DriverDashboard.tsx outside Route | Mock roster/cabin/pickupWindow. simulateScan, markMissed, confirmDropOff and calls update local state/notifications, not persistent passenger APIs |
| frontend/src/pages/ParentDashboard.tsx; components/TripHistoryPanel.tsx; data/tripHistory.ts | Fixed child/mock vehicle/boarding, generated history and in-memory notifications. Embedded PersistentNotifications is separately API-backed |
| frontend/src/pages/LiveFleetPage.tsx | Timed percentage-position BUS-01/VAN-02 animation, mocked speed/routeState. Already says Simulated GPS feed; not the real Driver Route marker |
| AdminDashboard.tsx, FleetAdminPages.tsx, Sidebar/Header | Overview/fleet/crew/demo summaries/badges read mock context; Students/Routes/persistent inbox separately use API |
| DemoControlCenter.tsx, safety/emergency/responder views | Explicit simulated RFID, impact, calls, missed pickup, camera/emergency actions. Preserve demos; do not present as field evidence |
| backend/main.py, optimizer.py, sample_data.py | Compatibility GET /students, /vehicle, /routes/{direction} reads fixed sample data. Legacy route GET optimizes; new GET latest only retrieves stored data |
| backend/route_schemas.py, planning_orchestration.py | Default provider is simulation. A new vehicle/direction defaults to simulation/settings; reused settings can retain forced failure/demo choices. Actual coordinates do not automatically enable live costs |

The working StudentsPage, RouteOptimization, DriverStoredRoute/DriverTrip, shared RouteMap and persistent notification card use backend results without silently substituting mock routes on failure. Preserve simulation but separate its authority from actual operations.

## Defects/blockers before actual-input use

1. **Access control absent.** Unauthenticated callers can read/mutate child locations, trips, positions and notifications, choose recipient/vehicle/source and potentially trigger billable providers. Add server-authenticated principals, device binding, per-role actions and parent/driver ownership first.
2. **Phone capture/upload absent.** No watchPosition/getCurrentPosition integration, ingest service, explicit capture lifecycle, device identity or durable queue. Current frontend only fetches positions. No accuracy_m/session/device schema; extra fields are rejected.
3. **Provenance/quality untrusted.** measured/actual_device are caller claims. No accuracy/clock-quality evidence or implausible-jump filtering. Duplicate/order validation is not source authentication.
4. **Sources can compete.** Global latest orders both simulation and actual-device samples across trips for one vehicle. A later replay/future sample can mask real input. Candidate resets on source change do not isolate feeds. Keep simulations on separate fixture vehicles and gate sources on actual trips.
5. **Future/freshness mismatch.** Positions accept up to 30 s future, clamp negative age to zero and return fresh; arrival/operational processing rejects future observations. Add explicit clock-skew/ineligible status. Position stale is 60 s; arrival/ops freshness 20 s and maximum gap 10 s default?different meanings, not interchangeable guarantees.
6. **No measured segment target pipeline.** Raw GPS is not supervised driving duration. No segment observation model/import API exists. Trainer only accepts synthetic CSV rows; predictor/baseline loaders require synthetic version/source metadata. Relabelling the current CSV is invalid.
7. **Estimates remain unvalidated.** Synthetic-trained inference can accept real inputs but real-world accuracy is unknown. Haversine is not road distance; no live Google configuration/verification. Departure-time matrix snapshot is not fully time-dependent; bounded solver is not proof of optimum.
8. **Policy/workflow incomplete.** Pickup policy provisional, advancement manual, persistent delivery confirmation absent. Ending a persistent trip retains unfinished history. simulation_demo trips refuse actual-device positions; use a new production-mode trip, never alter historical settings to bypass this.
9. **Phone/deployment gap.** Development proxy is not production HTTPS deployment. Phone localhost is the phone, not the PC. No native/background GPS guarantee, production scheduler supervision or offline upload exists. Starting main:app runs workers and may expire existing due windows; it is not a read-only check.
10. **Field calibration/privacy pending.** Sequence geometry can flag legitimate road detours; exclusion around any expected stop can suppress real anomalies. No field accuracy validation. Consent, access, retention/backup and logging need decisions; bounded history queries do not implement data retention.

## Model artifacts and actual metrics

Version **synthetic-xgb-v1-26c03624ed36a729**, JSON model with checksum-validated preprocessing/baseline/metrics. Feature schema travel-segment-v1: approximate haversine distance_m, Sri Lankan fractional hour, Monday-zero day_of_week, weather_flag/weather_missing, origin/destination/directed segment categorical features. Unknown categories use zero one-hot; missing weather explicit; log-duration target inverted with exp. No target/observed arrival features.

2,000 synthetic rows/400 trips. Development 1,500/300 trips, 6 July?14 August 2026; held-out final 500/100 trips, 17?28 August 2026 (+05:30). Four weekly expanding folds; whole trips kept together, training-only preprocessing and averages, fixed parameters/no final-test tuning. Walk-forward remains saved evidence; no fitting today.

| Saved final block, recomputed now | MAE seconds | MAE minutes | RMSE seconds | RMSE minutes |
|---|---:|---:|---:|---:|
| XGBoost | 28.012511859487336 | 0.4668751976581223 | 49.89851705630116 | 0.8316419509383527 |
| Historical synthetic baseline | 57.08666959838096 | 0.9514444933063493 | 111.90390381547041 | 1.8650650635911736 |

**This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.** Missing-model and fallback checks passed fresh; mocked live success is not provider verification.

## Exact current endpoints

Backend base http://127.0.0.1:8000. Development frontend http://localhost:5173 prefixes /api, stripped by Vite. /docs, /redoc and /openapi.json are documentation routes in addition to these 49 operations:

| Method | Path |
|---|---|
| GET | `/routing/health` |
| GET | `/routing/schools` |
| GET | `/routing/vehicles` |
| GET | `/routing/students` |
| POST | `/routing/students` |
| PUT | `/routing/students/{student_id}` |
| DELETE | `/routing/students/{student_id}` |
| PATCH | `/routing/students/{student_id}/status` |
| PATCH | `/routing/students/{student_id}/vehicle` |
| POST | `/routing/geocode` |
| PUT | `/routing/schools/{school_id}/location` |
| PUT | `/routing/vehicles/{vehicle_id}/locations/{position}` |
| GET | `/routing/map-locations/{vehicle_id}` |
| GET | `/traffic/status` |
| POST | `/routes/generate` |
| GET | `/routes/latest` |
| PUT | `/routing/schools/{school_id}/schedule` |
| GET | `/routing/events/{event_id}` |
| POST | `/routing/events/{event_id}/retry` |
| GET | `/routing/plans/{vehicle_id}/{direction}` |
| PATCH | `/routes/{route_id}/planning-lock` |
| GET | `/ml/status` |
| POST | `/ml/predict` |
| GET | `/routes/{route_id}/map-image` |
| GET | `/trips/current` |
| GET | `/trips/{trip_id}` |
| POST | `/trips` |
| POST | `/trips/{trip_id}/start` |
| POST | `/trips/{trip_id}/complete` |
| POST | `/trips/{trip_id}/cancel` |
| POST | `/routing/vehicles/{vehicle_id}/positions` |
| GET | `/routing/vehicles/{vehicle_id}/positions` |
| GET | `/routing/vehicles/{vehicle_id}/positions/latest` |
| GET | `/trips/{trip_id}/arrival` |
| POST | `/trips/{trip_id}/advance-stop` |
| GET | `/pickup-policy` |
| GET | `/trips/{trip_id}/pickup-windows` |
| POST | `/trips/{trip_id}/pickups/{student_id}/confirm` |
| POST | `/trips/{trip_id}/pickups/{student_id}/cancel` |
| GET | `/trips/{trip_id}/pickup-history` |
| GET | `/routing/notifications` |
| PATCH | `/routing/notifications/{notification_id}/read` |
| GET | `/trips/{trip_id}/operational-events` |
| GET | `/pickup-worker/status` |
| GET | `/` |
| GET | `/health` |
| GET | `/students` |
| GET | `/vehicle` |
| GET | `/routes/{direction}` |

Query contracts: `/routes/latest?vehicle_id=...&direction=morning|afternoon`; `/trips/current?vehicle_id=...&direction=...`; positions optionally `trip_id`, history `limit=1..500`/`window_seconds=1..604800`; notifications `recipient=admin|parent`, parent requires `student_id`, limit 1..200/`before_order_id`; pickup history limit 1..500/`after_order_id`; operational events limit 1..200.

GET latest/arrival/windows/events does not optimize or create a GPS transition. GET map-image may call paid Static Maps when configured; geocode and Google generation may also be billable. None were called here.

Position POST contract example, **not submitted**:

```json
{
  "sample_id": "stable-device-session-sample-id",
  "trip_id": "EXPLICIT_ACTIVE_PRODUCTION_TRIP_ID",
  "source": "actual_device",
  "latitude": 6.9271,
  "longitude": 79.8612,
  "speed_mps": null,
  "recorded_at": "2026-10-17T08:00:00+05:30"
}
```

Numbers/time illustrate syntax, not observed GPS. Real senders must use callback coordinates/time, stable IDs across retries and null unknown speed. Include the matching ACTIVE trip for arrival/operational processing; vehicle-only uploads just update tracking. Device authentication is currently absent.

## Exact Windows commands

### Focused checks without database mutations or external connections

PowerShell; credentials stay in backend/.env. These commands do not seed, upgrade, replay or start workers.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m alembic current
$env:SAFERIDE_RUN_DB_TESTS = '0'
@'
import os, socket, unittest, sys
from unittest.mock import patch
os.environ['SAFERIDE_RUN_DB_TESTS'] = '0'
def blocked(*args, **kwargs):
    raise AssertionError('Network disabled for readiness audit')
with patch.object(socket.socket, 'connect', blocked), patch('socket.create_connection', blocked):
    suite = unittest.defaultTestLoader.discover('tests')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'@ | .\.venv\Scripts\python.exe
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
Set-Location ..\frontend
node .\node_modules\typescript\bin\tsc --noEmit --incremental false
npm run build
```

Expected here: 43 discovered, 35 passed/eight skipped; TypeScript/build exit 0. Do not enable integration tests on a live operational database: they create/mutate fixture trips and start expiry processing. Use a separate test database and inspect the harness first.

If servers already run, these reads are non-billable:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/routing/health
Invoke-RestMethod http://127.0.0.1:8000/ml/status
Invoke-RestMethod http://127.0.0.1:8000/traffic/status
Invoke-RestMethod http://localhost:5173/api/health
```

Normal local operation, **not executed during this audit**:

```powershell
# Startup resumes workers and may change due operational state.
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# Separate frontend terminal:
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

No upgrade, seed, training or paid-provider command is needed. SQLAlchemy URL.create and disabled dotenv interpolation handle special-character passwords; .env is ignored. Routes/Static Maps keys are absent; traffic HTTP timeout is 4 seconds. No credential values are included.

## Smallest changes for actual phone GPS

1. **Keep existing position/trip endpoints and simulation.** Add an authenticated upload principal/device-to-vehicle binding; enforce vehicle/trip ownership and derive allowed source on the backend. Add matching driver/parent read permissions and route-generation authorization before real records are exposed.
2. Add a foreground capture component to the existing Driver Route view and a typed ingest service. Explicit Start/Stop, authorized vehicle and ACTIVE production trip; `watchPosition` with high accuracy, visible permission/upload errors and `clearWatch` cleanup. Preserve callback timestamp and stable session/sample IDs across retries. Do not regenerate or replace the active route.
3. Add an additive position migration/schema for `accuracy_m`, device/session identity and quality/clock status. Flag poor accuracy, implausible jumps and future clock skew; resolve latest freshness discrepancy. Unknown speed stays null. Reuse existing validation, deduplication and transactional event processors.
4. Serve UI and `/api` through the same phone-reachable **HTTPS origin**, with an intentional reverse proxy/certificate. A phone cannot use PC localhost, and ordinary LAN HTTP is not a reliable secure-context geolocation setup. Keep React/Vite; no Next.js migration is needed. Continuous screen-locked/background GPS needs a suitable native/background collector; a foreground browser does not guarantee it.
5. Use a bounded retry queue preserving recorded time and IDs. Late offline samples remain history and cannot establish fresh dwell. Show age/gaps. Aim for genuinely new readings under the snapshotted max gap (10 seconds default), e.g. 2–5 seconds when available; do not resend cached readings with invented fresh timestamps.
6. Field-test a new consented test vehicle/production-mode trip with actual confirmed locations, not an existing demo trip. Check clock skew/accuracy, duplicates/order/reconnect, GPS loss, backgrounding, dwell boundaries and persistence. Keep replay on separate synthetic vehicles/trips so simulated samples cannot override actual latest positions.

## Smallest changes for measured travel observations

1. Add an append-only segment-observation model/migration and import/derivation command. Store observation ID, trip/pinned route version, stable origin/destination IDs, departure/arrival timestamps, driving duration, distance **and method**, source, quality, contributing position IDs and extraction/schema version. Retain rejection reasons and raw evidence.
2. Extract from good ordered actual-device traces with explicit segment boundaries; separate driving from service/waiting/GPS gaps. Arrival alone does not establish departure or every service boundary: add recorded departure/quality rules first. Never use provider/model ETA as a measured target or label haversine displacement measured road distance.
3. Preserve `travel_times_synthetic.csv` and the existing synthetic bundle. Add a distinct versioned measured-data import/train path rather than bypassing synthetic-only guards. Group chronological validation by whole trip; training-only preprocessing/baseline; untouched latest final block and real sample/quality counts. Do not retrain before genuine observations exist.
4. Keep feature meaning consistent. Current `distance_m` is approximate haversine; supplying measured road distance to this unchanged model would change schema semantics. Retain that approximation explicitly or introduce a separately versioned road-distance model. Weather must be time-available real input or explicit missing, never fabricated historical weather.
5. Extend predictor/baseline artifact loaders and labels for a separately validated measured-trained version while preserving synthetic models and fallback. Outputs remain **ML predictions**, even when training targets are measured. Establish independent held-out and field metrics before claiming real accuracy.

These are proposed incremental changes, not features added by this audit. The repository demonstrates persistent routing and operational state with a tested synthetic pipeline; actual phone provenance, approved policy, access control and field accuracy still need implementation/evidence.
