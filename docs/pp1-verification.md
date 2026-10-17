# PP1 routing verification ? 16 October 2026

## Scope and evidence

Inspected the existing backend models, solver, persistence, planning orchestration, trip/position/arrival/pickup/notification/operational code, ML artifacts and tests; frontend proxy, API helper, route view and Driver polling. No real student records were changed. Database checks insert uniquely prefixed synthetic fixtures; fixtures remain for inspection. Google adapter tests use mocked transport or forced failure, not paid calls. The training CSV and model artifacts were unchanged; tests regenerated synthetic GPS replay fixtures only. No retraining occurred.

The full backend suite and audit browser results are linked below. A passing synthetic test establishes the stated invariant under those inputs; it does not establish real-world accuracy or production readiness. Earlier stage JSON files can contain retained browser evidence from earlier runs; their browser sections are historical unless identified as the new PP1 run.

| Capability | Implemented | Verified behaviour in this audit | Simulation / remaining limit |
|---|---|---|---|
| 1. Student persistence | Yes: SQLAlchemy/PostgreSQL student API | `test_auto_planning`: create/edit/deactivate/transfer saved, independent DB reader, durable failed-routing save | Synthetic records; Students browser form not freshly exercised in this audit |
| 2. Independent directions | Yes | `test_dual_route_solver`, `test_route_storage`: separate matrices, independent stored routes; PP1 browser selects both | Deterministic simulated travel costs; no morning reversal |
| 3. Multi-school pickup/delivery | Yes | Exactly one pickup/delivery per active student, correct home/school, strict precedence even at zero duration | Synthetic two-school cases; not operational school validation |
| 4. Assignments/capacity/time | Yes | Fixed assignments, onboard load bounds with roster larger than capacity, school deadlines/finish, impossible windows and missing coordinates rejected | Bounded heuristic solve, no proof of global optimum; configurable service and computed waiting separate |
| 5. Roster regeneration | Yes: backend owned | Add/edit/deactivate trigger both directions; idempotent mutation and reads do not add versions; failures keep saved student and invalidate plan | Pre-trip only; pending recovery worker single-process prototype |
| 6. Transfer both vehicles | Yes | Transfer reports four plans, updates old/new morning/afternoon; old roster removed | No automatic reassignment to make an infeasible roster feasible |
| 7. Driver saved route/version | Yes | New separate-tab PP1 browser run matches IDs, versions and all 14 actions; sees newer version; zero Driver write requests | Role/vehicle choice is prototype access, not authorization |
| 8. Active trip pinned | Yes | `test_trip_lifecycle`: duplicate/concurrent starts, database uniqueness, new-session/process restart, regeneration guard and immutable route snapshot | No active-trip rerouting; ending does not confirm unfinished deliveries |
| 9. Actual XGBoost routing | Yes | ML matrix entries equal actual loaded model predictions; forced-live-failure route solve uses loaded model. Two new saved ML routes generated successfully | Model trained entirely on synthetic targets; unfamiliar segment IDs use explicit unknown encoding |
| 10. Honest unavailability/fallback | Yes | Missing artifact returns 503; forced failure, timeout/quota/partial matrix mocked tests; explicit baseline/unavailable and mixed per-leg sources | Live Google traffic and Google road image fetching NOT verified |
| 11. GPS positions/replay/stale | Yes | Coordinates/speed/IDs/timestamps validation, duplicate/order/history bounds, fresh/stale/unknown, process restart; real CLI sent eight simulated samples | No actual-device field verification; synthetic stop-sequence trace, not road driving |
| 12. Arrival dwell/deduplication | Yes | Current-stop-only, radius/hysteresis, count/dwell, gaps/source changes, duplicate/late rejection, one persistent event | Controlled GPS clock; proximity never confirms boarding/delivery |
| 13. Pickup deadline persistence | Yes | Refresh and repeated arrival do not extend; real worker expiry with no browser; overdue restart recovery; exact-boundary and race checks | Production 900 seconds; accelerated demo explicitly marked. School scope provisional |
| 14. Unique missed notification | Yes | One persistent event despite repeated/concurrent expiry; database uniqueness; transaction rollback; scoped parent queries/read persistence | In-app event only. Recipient selection is not authenticated access control |
| 15. Deviation limitations | Yes | Metre distance math; two deviation episodes/one unexpected stop; recovery, expected waiting, GPS loss and duplicate suppression | Approximate stop-sequence geometry tested. No validated precision/recall, crash inference or real-road accuracy |

## Actual runs

- [Backend log](pp1-backend-checks.txt) and [run metadata](pp1-test-run.json): 43 tests passed, zero failures/errors/skips, 88.492 seconds, process exit 0, PostgreSQL opt-in enabled; final run includes the freshness correction.
- [New Admin/Driver browser evidence](pp1-browser-verification.json), [screenshot](pp1-driver.png): real separate tabs plus explicitly injected browser-only error/obsolete-response/visibility fixtures. No browser errors, no Driver writes. OSM tiles deliberately blocked in automation; visual tile availability was not tested.
- `node ./node_modules/typescript/bin/tsc --noEmit --incremental false`: exit 0 after correcting nine existing type-check issues.
- `npm run build`: exit 0; Vite 5.4.21, 1,728 modules. Vite build itself does not type-check.
- Alembic read-only `current`: `0012_operational_episodes (head)`; no new migration required.
- [Replay output](pp1-replay-check.txt): eight accepted simulation samples, all advanced latest, no duplicates, exit 0. Uses only the newly created S9E fixture; full scenario transitions are verified in controlled-clock integration tests, not all replayed through the real-time CLI.

Additional saved forced-failure demonstration: [fallback evidence](pp1-fallback-verification.json), route `ROUTE_62699ac77bb94a45bdc7f01de88a670d`, companion PP1 vehicle, feasible with `ml_prediction` and an explicit no-external-request reason. [Live read check](pp1-live-read-check.json) confirms the frontend proxy and backend return the same saved route/version and the running backend has loaded the model.

## ML evidence and actual metrics

`backend/ml/artifacts/current.json` selects `synthetic-xgb-v1-26c03624ed36a729`; JSON model, preprocessing, baseline and metrics checksums load successfully. Saved final-test predictions were recomputed from existing artifacts, without fitting anything, and matched every stored aggregate metric ([recomputation](pp1-ml-verification.json)).

| Evaluation | Samples | XGBoost MAE s (min) | XGBoost RMSE s | Baseline MAE s (min) | Baseline RMSE s |
|---|---:|---:|---:|---:|---:|
| Walk-forward aggregate, stored training report | 1,000 | 29.8573259894 (0.4976220998) | 57.8400722399 | 75.6677400757 (1.2611290013) | 134.6735641630 |
| Untouched final block, recomputed from saved model | 500 | 28.0125118595 (0.4668751977) | 49.8985170563 | 57.0866695984 (0.9514444933) | 111.9039038155 |

2,000 synthetic observations / 400 trips; development 1,500 / 300 trips, final 500 / 100 trips. Development 2026-07-06 05:43:42 through 2026-08-14 16:40:39 +05:30; final 2026-08-17 05:42:52 through 2026-08-28 16:36:09 +05:30. Four expanding weekly evaluation folds use 500/750/1,000/1,250 training rows and 250 evaluation rows each. Whole trips remain together; training-only categorical vocabularies and historical averages; fixed hyperparameters, no final-test tuning. Only the saved final model was re-evaluated now; walk-forward models were not retrained.

Feature schema `travel-segment-v1`: numeric approximate haversine distance_m, fractional Sri Lankan hour, Monday-zero day_of_week, weather_flag and weather_missing; categorical origin_id, destination_id and directed segment_id. Unknown categories are all-zero one-hot; missing weather uses -1 plus its indicator. Target is log synthetic duration_s, inverted with exp. Baseline is training segment mean with global mean for unseen segments. No target, future arrival or observed duration is a prediction feature. Synthetic durations have time/segment/weather/noise effects; they are not measured actual travel times.

**This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.** The observed baseline comparison is specific to this dataset; it is not a promise or proposal target validation.

## Defects fixed and files changed

- `backend/seed_routing_demo.py`: optional prefix retains existing repeatable seed behaviour and permits isolated fixtures.
- `backend/tests/test_route_storage.py`: unique PP1 fixture IDs instead of modifying fixed S4 demo routes.
- `backend/planning_state.py`: previous Sri Lankan service date cannot be current, even with matching roster. Today's/future plans remain eligible; execution locks remain enforced.
- `backend/tests/test_driver_route_read.py`: past/today/future freshness regression coverage.
- `backend/tests/test_positions.py` and `docs/stage9a_verification.json`: replaced obsolete ?arrival not implemented? evidence text with the correct fixture-specific scope.
- Frontend unused React imports removed in App, Sidebar, index, AdminDashboard, IncidentMonitoring, LiveFleetPage, RoleSelection; unused MapPin removed in AdminDashboard. `frontend/src/vite-env.d.ts` supplies existing PNG/Vite types. No visual redesign.
- `frontend/scripts/verify-pp1.cjs`: isolated-copy browser verification using the new PP1 demo records, not existing S4 records.
- Three PP1 reports, machine-readable PP1 records/metrics/browser/test evidence, logs and screenshot added. Stage integration tests also update their existing stage JSON evidence and synthetic replay fixtures.

## Remaining evidence boundaries

Live Google credentials were reported unconfigured in the generated ML route metadata. No paid API was invoked. Adapter timeout/quota/geometry success cases are mock contracts, not provider certification. The provider-road-geometry label checks stored provenance/structure, not surveyed physical road correctness. The PP1 solver uses a departure-time matrix snapshot, not a fully time-dependent algorithm. Straight-line distances and stop-sequence rendering remain approximate without road geometry.

No real authentication, device integration, delivered SMS/push or operational safety accuracy is demonstrated. Unrelated cabin/camera/RFID/emergency panels and fixed dashboard summaries remain proposal demonstrations. Active routing/trip/pickup state is in the database-backed Driver Route view; delivery confirmation is still pending. Missing GPS is unknown, never proof of a stopped vehicle. Local workers assume one backend process. No official completion percentage is assigned.

## Exact Windows verification commands

PowerShell, project root:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic current
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
Set-Location ..\frontend
node .\node_modules\typescript\bin\tsc --noEmit --incremental false
npm run build
node .\scripts\verify-pp1.cjs
```

The browser command requires backend :8000 and frontend :5173 already running and the prepared PP1 demo vehicle still pre-trip. It generates simulation routes for that fixture only; do not use it against a selected real vehicle. Database suite deliberately retains new synthetic records. Credentials stay in backend/.env and are not included here.
