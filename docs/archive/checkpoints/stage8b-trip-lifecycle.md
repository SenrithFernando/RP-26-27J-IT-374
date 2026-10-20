# Stage 8B: persistent prototype trips

A Trip references one immutable RouteVersion ID. States are PLANNED -> ACTIVE -> COMPLETED; PLANNED or ACTIVE can deliberately become CANCELLED with a nonblank reason. Terminal trips cannot reopen. Creation and repeated transitions are idempotent. The database has partial unique indexes for one ACTIVE trip per vehicle (across directions) and one open trip per route. The shared planning transaction lock serializes lifecycle and planning changes. No GET creates trips or runs optimization.

Create/start requires a feasible, current, latest saved pre-trip route and matching roster. Creation rejects past Sri Lankan service dates; start requires today's service date. Future plans may be created but cannot start early. These manual prototype controls do not validate actual departure or arrival observations.

Starting reuses the existing execution protection. Admin generation and automatic planning cannot replace the active route snapshot; student changes can still save and leave planning stale/deferred. Another direction may be planned independently, but cannot start on the same vehicle until its active trip ends/cancels. The legacy planning-lock endpoint remains for unmanaged snapshots, and refuses to bypass persisted trips. Existing same-day completed-route generation protection remains. Active cancellation closes its snapshot and permits generating a new version; it never reopens/rewrites that snapshot.

All lifecycle timestamps use PostgreSQL timestamptz. Driver formats times with Asia/Colombo. It reads its persisted trip on refresh and in the existing visible-page polling loop. Active trips remain visible even while another planning direction is selected. Without an active trip, the latest trip for the selected direction is shown. The trip itinerary/map/estimates are separate from the latest plan. Source labels and the stop-sequence map remain unchanged.

Pickup/delivery actions are snapshotted as PENDING at trip creation. This stage does not record passenger events. Ending/cancelling preserves every unfinished action; COMPLETED means lifecycle closed, not all students delivered. Manual controls are explicitly not RFID or GPS evidence. No active-trip rerouting was added.

## Migration (Windows PowerShell, project root)

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
```

Expected revision: `0006_trip_lifecycle`. Applied locally. No additional runtime dependencies. Credentials remain in backend/.env. Downgrade deliberately refuses to discard trip history or rewrite cancelled snapshots.

## Run (separate terminals)

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location .\frontend
npm run dev
```

## Focused checks

```powershell
Set-Location .\backend
$env:SAFERIDE_RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_trip_lifecycle.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
```

This opt-in check creates only new S8B-prefixed synthetic schools/vehicles/students/routes/trips and retains evidence. It uses deterministic simulation with road geometry disabled. It tests the HTTP endpoints with an isolated server, including a genuine server-process restart, independent DB sessions, concurrent cross-direction starts, direct enforcement of the active-vehicle unique index, stale/infeasible/past-plan rejection, terminal transitions, roster-change snapshot protection, legacy-lock protection, and preservation of unfinished actions. It does not call Google or run unrelated pending-event recovery. No extra TestClient dependency is required.

After the focused check, with normal frontend/backend running:

```powershell
Set-Location ..\frontend
node .\scripts\verify-stage8b.cjs
npm run build
```

The browser script uses the new fixture named in docs/stage8b_verification.json, creates/starts/ends its trip, checks reload and direction selection, and writes actual evidence and a screenshot. Rerun the backend check first to create a fresh fixture before repeating browser mutation tests. Existing Playwright installation is used. The separate TypeScript check still reports nine pre-existing errors outside this stage's changed files (unused imports and the PNG module declaration); Vite production build passes.

## Browser verification

1. Open http://127.0.0.1:5173. Administrator -> Routes. Select S4_VAN_A, Morning Pickup, today's Sri Lankan service date, and Simulation. Generate route. Note route ID/version. Use a vehicle without an active legacy execution lock; never clear a real trip just to make a demo work.
2. In a separate tab choose Driver -> Route. Select the same database vehicle/direction. Compare the latest plan ID/version/stops.
3. Click Create planned trip (manual prototype). State is PLANNED; note trip ID and fixed route ID/version. Click Start trip (manual prototype). State becomes ACTIVE.
4. Reload the browser and reopen Driver -> Route, selecting that vehicle. The same ACTIVE trip, timestamps and fixed route remain. Switch direction: the active trip still points to its original direction/version. The planning selection is separate.
5. Attempt to generate that active direction in Admin: expect a conflict, no trip-route replacement. Attempt another trip start for that vehicle: expect conflict (the automated HTTP test also races morning and afternoon starts).
6. End trip, then Confirm end trip. State becomes COMPLETED; unfinished pickup/delivery actions remain PENDING. Reload and verify persistence. No students are declared delivered.
7. On a fresh current route, create a PLANNED trip and choose Cancel trip deliberately. An empty reason cannot submit. Enter a reason and confirm; CANCELLED and its timestamp/reason persist. Active cancellation is also verified by the integration test.

## API

- POST /trips {"route_id":"..."}
- GET /trips/current?vehicle_id=...&direction=morning (direction optional; any active vehicle trip takes priority)
- GET /trips/{trip_id}
- POST /trips/{trip_id}/start
- POST /trips/{trip_id}/complete
- POST /trips/{trip_id}/cancel {"reason":"..."}

## Changed files

backend/models.py, backend/migrations/versions/0006_trip_lifecycle.py, backend/trips.py, backend/main.py, backend/planning_state.py, backend/planning_api.py; frontend/src/services/api.ts, frontend/src/hooks/useStoredDriverRoute.ts, frontend/src/components/DriverStoredRoute.tsx, frontend/src/components/DriverTrip.tsx; backend/tests/test_trip_lifecycle.py; frontend/scripts/verify-stage8b.cjs; this document and generated stage8b_verification.json / stage8b-driver.png evidence.
