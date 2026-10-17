# Stage 8A — database-backed driver route view

The Driver **Route** panel now reads stored Stage 7 plans from FastAPI. It does not use the cabin demo's `BUS-01`, fixed distance/ETA, mock stop list, completed-stop flags or deviation alerts. The surrounding cabin, RFID, pickup, call and emergency demonstrations retain their existing behavior and are labelled as demonstrations. Selecting a routing test vehicle does not reassign that demo vehicle or its students.

## Browser verification

Use two separate browser tabs at **http://127.0.0.1:5173**. Role and vehicle selection are explicitly prototype access; this is not driver authentication/authorization.

1. **Admin tab:** choose **Administrator → Routes → S4_VAN_A → Morning Pickup**. Wait for the route to finish loading. Choose **Deterministic simulated traffic → Normal simulation** for a local check that needs no paid API. Set the service date to today or a future date, leave a suitable departure and school schedules, and click **Generate route**. Note its route ID and version.
2. **Driver tab:** choose **Driver → Route**. The panel initially asks for an explicit database vehicle; it never silently selects `BUS-01`. Under **Test vehicle (prototype)** choose **S4_VAN_A**, then **Morning Pickup**.
3. Compare the Driver **Route ID**, **Version**, action order, names and ETAs with the Admin result. There are start/end actions plus separate pickup and delivery actions. The existing synthetic S4 fixture has six students and 14 actions per direction, capacity two, and two schools.
4. In Admin, generate the morning plan again. Return to the Driver tab: visibility resumption requests the latest plan immediately. If Driver stays visible, it checks every **15 seconds after the previous request finishes**. Its ID/version must change to the new Admin result without a Driver generation request. **Refresh route** performs an immediate GET-only check.
5. In Admin choose **Afternoon Drop-off** and generate independently. In Driver choose **Afternoon Drop-off** and compare that ID/version and its school-pickup/home-delivery order. Switching directions does not reverse or overwrite the other stored route.
6. Inspect separate **Driving**, **Service**, **Waiting**, **Total duration**, distance provenance, source badge, model/fallback details and planned per-action ETA. School/student names come from that route version's input snapshot; subsequent directory renames cannot silently relabel an older snapshot.
7. Scroll the panel to its map and actions. It reuses the Admin map components and adapter. Without road geometry it still says **Stop sequence — not a road route**. A loaded tile map is not live traffic or live GPS. The existing optional Google-road-image path is reused if configured and returned by the backend; no Google credentials are added for this stage.
8. Close the panel with **Back to driver dashboard**. Its polling and requests stop. The separately labelled cabin/boarding demonstrations remain available.

**No route** tells the driver to generate it in Admin. Stale, infeasible, unavailable, mismatched, active/completed non-current snapshots, past-date plans and unverified freshness do not show a working itinerary or current duration/distance estimates. Historical ID/version metadata may remain visible with a non-current label and the server's constraint reasons. API errors do not substitute mock data. A selected vehicle missing from the database directory is marked unavailable rather than replaced.

The driver also checks service dates in Asia/Colombo: a past-date plan is labelled historical even if the existing backend roster-freshness flag says current. This is a Driver presentation guard; it does not change the backend's existing freshness semantics or the Admin view.

## Run/check commands

The development servers are already running in the verification environment. If stopped, from the repository root in separate PowerShell terminals:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

No migration, seeding, retraining, dependency installation or credential change is required. If FastAPI is running without reload, restart it to expose the additive snapshot-name fields.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_driver_route_read.py -v
```

From `frontend`, with the servers and existing S4 fixtures available:

```powershell
node scripts/verify-stage8a.cjs
npm run build
node ./node_modules/typescript/bin/tsc --noEmit --incremental false
```

The optional browser check uses the local Playwright installation. It intentionally creates three stored route versions through the actual Admin form: morning, regenerated morning and afternoon. It never saves student changes. The Driver tab is monitored for write requests. Error/stale/infeasible/date scenarios are injected browser-only fixtures, not invented successful optimization results and not persisted plan changes.

## Implementation

- Existing services are reused: `fetchVehicles`, `fetchLatestRoute`, `fetchPlanStatus`; existing endpoints remain `GET /routing/vehicles`, `GET /routes/latest` and `GET /routing/plans/{vehicle}/{direction}`.
- The existing route serializer additionally returns nullable `student_name` and `school_name` inside each stop, derived from `input_snapshot`. No new endpoint/table is introduced. The stored JSON stop rows themselves are not mutated by reads.
- The route panel has independent vehicle/direction state, retained while navigating back to the cabin demo. It never modifies the mock `driverVehicleId`, mock route state, execution locks or stop progress.
- `useStoredDriverRoute` serializes reads using one recursive timer. It aborts obsolete requests on refresh, selection change, page hiding and unmount, and uses a request-sequence guard so delayed responses cannot overwrite a newer selection. It has a 12-second request deadline. The next automatic check is scheduled only after the previous check completes; there is no overlapping polling loop.
- Hidden pages pause polling and cancel their in-flight read. Visible pages resume with an immediate check. Closing the route panel removes the visibility listener and all route timers/controllers.
- A current itinerary requires a feasible stored route, matching roster revision and plan route ID, both server freshness flags, a non-past service date and pre-trip execution state. Failure to verify plan freshness hides its working itinerary. A transient mismatch between the two GET responses is conservative until the next check.
- No driver component/hook imports or calls `generateStoredRoute`, the legacy `/routes/{direction}` solver endpoint, retry-event POSTs, or execution/registration mutations.
- `TrafficRouteMap`, source badges and the existing Leaflet map are reused. `routePoints` is extracted unchanged from Admin into a shared presentation adapter.

The driver displays planned onboard load and ETA as planning values; it does not infer a current destination or completed pickup from the mock boarding state. The old routing panel's fake **Live** badge and navigation-start toast are removed. There is no GPS tracking, navigation execution or pickup persistence in Stage 8A.

## Recorded verification

The executed two-tab verification on 2026-10-16 produced:

| Actual Admin result | Route ID | Version |
|---|---|---:|
| First morning | `ROUTE_aa8546a7ba03414db3fecebe7e8ad7e7` | 51 |
| Regenerated morning received by Driver | `ROUTE_dc2756787d2f451a91378d9321eb48d3` | 52 |
| Independent afternoon | `ROUTE_82bd182c20c84d448634911e95b73dba` | 22 |

Driver ID/version and all 14 ordered action IDs matched in both directions. The Driver tab issued **zero write requests** and reported **zero browser runtime errors**. GET refreshes did not create another morning version. The browser checks also passed for:

- backend HTTP 503, no-route HTTP 404, stale plan, infeasible plan and past-date UI fixtures;
- a delayed obsolete morning response after changing to afternoon;
- hidden-page polling suspension, visible-page resumption, 15-second polling and cleanup after closing the view.

The serializer unit check passed: snapshot names are returned without mutating stop JSON, committing records or invoking the solver. `npm run build` passed. The separate TypeScript check still reports the nine pre-existing unused React/MapPin imports and PNG module declaration issues documented in Stage 5; it reports no new Stage 8A errors.

`stage8a_verification.json` contains the executed browser evidence and `stage8a-driver.png` shows the driver panel. Later verification runs intentionally create their own newer Admin versions; they do not overwrite route history. The latest verification report identifies those versions.

## Changed files

- `frontend/src/pages/DriverDashboard.tsx`: replaces only the routing overlay, adds independent prototype route selection and a cabin-demo label.
- `frontend/src/components/DriverStoredRoute.tsx`: stored-plan controls, freshness/errors, separate metrics, map, ordered actions, snapshot names and sources.
- `frontend/src/hooks/useStoredDriverRoute.ts`: visible-page GET polling, manual refresh, cancellation, request guard and cleanup.
- `frontend/src/services/routePresentation.ts`: shared stored-action map adapter and local planning date helper.
- `frontend/src/pages/RouteOptimization.tsx`: uses the extracted map adapter; generation behavior is unchanged.
- `frontend/src/services/api.ts`: additive typed optional snapshot-name fields.
- `backend/route_service.py`: additive snapshot-name serialization on the existing route response.
- `backend/tests/test_driver_route_read.py`, `frontend/scripts/verify-stage8a.cjs`: focused serializer and two-tab browser verification.
- This guide, `stage8a_verification.json`, `stage8a-driver.png`.

Stage 8A ends at a read-only driver planning view. Unrelated component demonstrations are preserved.
