# Stage 5 — automatic pre-trip re-optimization

Student writes now commit their registration change and durable pending markers before running backend planning. Add, edit, activation/deactivation, soft removal and transfer regenerate morning and afternoon independently. Transfers affect both registered vehicles. School location/schedule and vehicle depot edits also invalidate and regenerate affected plans. An identical write records an unchanged event without incrementing the roster or generating route versions.

## Run on Windows PowerShell

From the repository root, with the existing local `backend/.env` credentials:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal, from the repository root:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Vite retains its strict port and `/api` proxy. No package dependencies were added for Stage 5. Migration `0005_auto_planning` was applied locally; it preserves existing registrations and route versions. Passwords remain local and `.env` remains ignored.

## Browser verification

1. Choose **Administrator → Students**. Click **Add Student**. Select an existing database school and vehicle, enter a name, address and valid home coordinates, select the correct input provenance, and explicitly confirm the pin. For synthetic testing, reuse a confirmed synthetic student's coordinates and select **Simulated input**. Click **Save student** once.
2. Wait for the backend response. A successful registration closes the form. Expand each vehicle/direction in the saved notice to inspect the event, roster revision, route version, timestamp, solver runtime, constraints and actual before/after values. A routing failure says **Student saved; routing failed**; it does not undo registration. An API save failure keeps the form open with **Student save failed**.
3. Open **Routes**, select that vehicle and inspect **Morning Pickup** and **Afternoon Drop-off**. These are stored backend results. Reloading the page or clicking **Reload stored route** only reads data and must not create versions. The current roster revision and current/history status are shown. An invalid/stale plan has unavailable metrics and no working itinerary; markers then show confirmed locations only.
4. Return to **Students**. Edit the home's coordinates/address or school, confirm the location again, and save. Transfer the student to a different vehicle: the outcome must contain both directions for both vehicles. Deactivate the student: the next pre-trip plans exclude them, while their registration remains stored.
5. To test a constraint failure using synthetic records, note the original school schedule, then open **Routes → School schedules (Asia/Colombo)**. Set that school's morning deadline earlier than the morning departure (for example `00:00:00`) and save. The schedule must persist and morning planning must report a failure, with its constraint explanation. Afternoon is solved independently. Restore the original schedule and save to regenerate. This deliberately affects every registered vehicle serving that school; use synthetic school records.
6. Restart FastAPI, reload Students/Routes, and confirm the saved registration, roster revision, event and stored route version remain. GETs do not solve. Historical metrics and stops remain in PostgreSQL but are never presented as current after an invalidation.

No route change or positive savings is guaranteed. Signed deltas are **after minus before**; zero and increases are displayed. If either result lacks metrics, its delta is unavailable.

## Commands for checks

From `backend`:

```powershell
$env:SAFERIDE_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
.\.venv\Scripts\python.exe -m pip check
```

The opt-in DB tests retain explicitly synthetic `S5_*` schools/vehicles, inactive test students and immutable route/event history. They do not delete user records. Dedicated synthetic execution snapshots remain locked to verify protection. The existing storage tests also use the insert-only `S4_*` fixtures and generate real stored simulation results. Run checks sequentially rather than editing those same fixtures in a browser simultaneously.

From `frontend`:

```powershell
npm run build
npx tsc --noEmit
node scripts/verify-stage5.cjs
```

The optional browser script requires Playwright and its Chromium browser, which are available in this local environment. It requires the two development servers and existing `S4_*` fixtures; create those, if absent, using `backend/.venv/Scripts/python.exe backend/seed_routing_demo.py` from the repository root. It adds an explicitly synthetic distant home, verifies saved-but-infeasible feedback and hidden stale routes, simulates a rejected API write, corrects the location, checks both directions, and deactivates the test registration. It blocks external map tile requests; tile availability is not part of this check.

## Stored state and recovery

- `vehicles.roster_version` identifies the current input revision. It increments once per affected vehicle for an actual change, including location/schedule changes.
- `routing_events` stores the trigger, payload fingerprint, optional idempotency key, affected revisions, saved record snapshot, actual before results, generation status, completion timestamp and per-direction outcomes.
- `route_versions` stores immutable attempt versions with roster revision, trigger reference/type, generation timestamp, solver runtime/result and execution status. Infeasible attempts contain no invented route metrics or stops.
- `route_plan_states` records each vehicle/direction's pending/current/failed/deferred status, revision, current attempt, settings, errors, generation timestamp, runtime and actual comparison. Committing the input also clears its old current-route reference.

API mutations return the normal saved record plus `save_status: "saved"` and `routing`. The frontend awaits this response and then refreshes server data. The same `Idempotency-Key` and payload replay the same saved event; reusing a key for different data returns 409. A unique event/vehicle/direction constraint plus PostgreSQL advisory transaction locking prevents multiple workers or retries from creating duplicate versions. GETs have no generation side effects.

The mutation normally completes planning synchronously. If a process stops after the save commit, a backend recovery worker retries durable pending events at startup and every five seconds. A superseded event cannot replace a newer revision. Unexpected generation failures keep the input saved, mark the plan stale/error, and support **Retry routing only**. A successful direction is reused during retry rather than versioned again. Expected constraint failures are retained as completed failed attempts; fix the input/settings to request a new attempt.

Previous saved per-direction generation settings are reused. Initial settings come from backend `PLANNING_*` variables in `.env.example`; expired service dates advance to the local planning date. Unknown school bell times are never invented. Each solver invocation remains bounded by its configured time limit. This research implementation uses a single advisory lock to serialize planning writes, so multi-vehicle changes can take several bounded solves; it is not a high-throughput job queue.

Read-only status APIs:

```text
GET /routing/events/{event_id}
GET /routing/plans/{vehicle_id}/{morning|afternoon}
GET /routes/latest?vehicle_id=...&direction=...
POST /routing/events/{event_id}/retry
```

Existing route and student endpoints remain available. `DELETE /routing/students/{id}` is a soft removal preserving history.

## Pre-trip execution boundary

`PATCH /routes/{route_id}/planning-lock` accepts `{"execution_status":"active"}` for a current feasible pre-trip plan, then `{"execution_status":"completed"}` for an active snapshot. This is a minimal planning guard, not a trip execution/boarding workflow. Completed snapshots cannot be reopened with this endpoint. Use it to identify actual backend execution snapshots; the separate legacy driver/demo trip flags are simulations and are not automatically interpreted as database execution state.

Automatic and manual pre-trip generation refuse to alter an active direction. A completed same-date snapshot is also protected; a later service date may receive a new pre-trip plan. Mutations still save and report `deferred_active` or `deferred_completed`. Stored execution stops and any completed-stop details are never rewritten or reset. There is no active-trip reordering in this stage.

## Verification recorded on 2026-10-15

All 15 backend tests passed with PostgreSQL enabled. Additional focused reruns verified that retrying a failed morning direction reuses the already successful afternoon version. Checks cover add, edit/school destination, old/new transfer vehicles, deactivate/remove, unchanged writes, idempotent replay/read-only fetching, impossible deadlines, saved solver errors, durable pending recovery, stale suppression, and active/completed snapshot protection. A temporary backend was stopped and restarted; stored route `ROUTE_4aacb26413fd4b47baaeab6302de5da9` version 27, roster 5, and all its stops survived unchanged. No API regeneration was requested for that restart check.

The browser test created synthetic student `STU_8530a697c25d487f8a56c43c4df146dc`, saved an infeasible distant location, corrected it successfully, displayed both directions, and deactivated it. It reported zero browser runtime errors. Later verification runs create separate synthetic registrations and retain their history.

One actual unchanged-result event (restoring a synthetic fixture's name) produced:

| Direction | Version before → after | Approximate distance before → after | Simulated driving before → after | Total duration before → after |
|---|---|---|---|---|
| Morning | 23 → 24 | 14,452 → 14,452 m | 2,414 → 2,414 s | 2,774 → 2,774 s |
| Afternoon | 11 → 12 | 14,543 → 14,543 m | 2,914 → 2,914 s | 5,531 → 5,531 s |

Both itinerary comparisons were unchanged and all five metric deltas were zero. These are stored deterministic simulation results on synthetic inputs, not measured road journeys, live traffic, ML predictions or proof of a global optimum. The map still labels its straight stop connection **Stop sequence — not a road route**.

`npm run build`, Alembic schema check and `pip check` passed. The separate `npx tsc --noEmit` check reports nine existing issues: unused React imports in App, Sidebar, index, AdminDashboard, IncidentMonitoring, LiveFleetPage and RoleSelection; unused MapPin in AdminDashboard; and missing PNG module declarations for BrandLogo. It reports no new Stage 5 type errors. No PostgreSQL, package or external provider blocker prevented this stage.

## Files changed

- Backend persistence/orchestration: `models.py`, `migrations/versions/0005_auto_planning.py`, `planning_state.py`, `planning_orchestration.py`, `planning_worker.py`, `planning_api.py`, `persistence.py`, `locations.py`, `route_api.py`, `route_service.py`, `route_schemas.py`, `route_solver.py`, `main.py`, `.env.example`.
- Frontend API and server-driven refresh: `src/services/api.ts`, `src/contexts/AppContext.tsx`, `src/pages/StudentsPage.tsx`, `src/pages/RouteOptimization.tsx`, `src/components/RoutingOutcomeNotice.tsx`, `src/pages/DemoControlCenter.tsx` (registration link replaces obsolete mock quick-add).
- Verification/documentation: `backend/tests/test_auto_planning.py`, `frontend/scripts/verify-stage5.cjs`, this document.

The existing visual layout and Leaflet map are retained. Safety, camera, RFID, emergency functionality and ML training remain outside this stage.
