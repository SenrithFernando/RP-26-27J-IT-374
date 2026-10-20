# Stage 9C: persistent pickup exception windows

## Policy and scope

No supervisor-confirmed pickup scope policy was found in the inspected documentation/code. The old main DriverDashboard/AppContext pickup timer is a React-only demonstration; it remains separate. Use Driver -> Route for the persistent research workflow.

Provisional configurable policy: morning home pickups use per_stop. Afternoon pickups default to per_school, with per_stop available. A shared visit is a contiguous run of pickup actions at the same saved school ID and coordinates. A delivery/non-pickup action, another school/location, or a later return starts a different visit. Students in one visit share a deadline but retain individual outcomes. Morning shared-school scope is rejected because those pickups are at individual homes. Scope/mode are chosen at trip creation and immutable thereafter.

Production is always 900 seconds (15 minutes), enforced in code and PostgreSQL. These execution exception windows do not change optimizer service durations, waiting calculations, stop order or route costs.

Explicit simulation_demo mode requires a simulated vehicle and simulation-only GPS; actual-device samples associated with an accelerated trip are rejected. Production mode can also use simulation input for tests: mode describes duration, not hardware verification.

backend/.env.example additions (actual overrides belong in backend/.env):

```dotenv
PICKUP_MORNING_SCOPE=per_stop
PICKUP_AFTERNOON_SCOPE=per_school
PICKUP_DEMO_DURATION_SECONDS=30
PICKUP_WORKER_INTERVAL_SECONDS=1
```

Demo duration is bounded 5-120 s, interval 0.2-30 s; invalid configuration fails startup. Configuration is snapshotted per new trip. Existing pre-9C trips remain readable and are not retrofitted with invented historical deadlines; Driver explains that a fresh trip is required.

## State and deadline semantics

Windows and individual outcomes use SCHEDULED, ARRIVED, WAITING, PICKED_UP, MISSED, CANCELLED.

- Trip creation schedules applicable pickup visits and student outcomes. Delivery actions create no pickup windows.
- Only confirmed Stage 9B arrival at the ACTIVE trip's current applicable pickup opens its window. started_at is the confirming GPS recorded timestamp; deadline_at adds the stored duration. ARRIVED and immediate WAITING are separate durable audit transitions at the same effective instant, not an artificial UI delay.
- Duplicate/repeated arrivals and GET requests never replace started_at or extend deadline_at. One shared-school arrival opens all unresolved outcomes in that visit, not a window per student.
- Manual driver prototype confirmation changes one waiting student to PICKED_UP. This is not RFID evidence. A reasoned cancellation changes only that student's outcome. Pickup never confirms delivery.
- At/after deadline, unresolved waiting outcomes become MISSED. Prior picked/cancelled outcomes are retained. The aggregate window is PICKED_UP if all picked, MISSED if any missed, otherwise CANCELLED for a terminal mixed picked/cancelled visit. Individual outcomes remain authoritative.
- Explicit trip completion/cancellation first expires due outcomes, then cancels remaining unresolved pickups. Scheduled visits with no arrival never expire on their own. Previous picked/missed/cancelled history remains; deliveries remain unverified.

Manual confirmation uses PostgreSQL clock_timestamp() after acquiring locks: strictly before deadline accepts; at/after deadline expires unresolved outcomes and returns 409. Browser click/request start time cannot override this. Expiry is committed even when the late confirmation is rejected. Repeating an already successful pickup is idempotent and retains its original time, including after deadline; MISSED/CANCELLED cannot be reopened into late pickup here.

All writes share Trip -> Window -> Outcome lock order (GPS additionally holds its vehicle lock). Arrival/window writes commit atomically. Unique visit/student/stop constraints prevent duplicates. Audit records preserve from/to, aware effective_at and recorded_at, action source and reason. A PostgreSQL identity order_id orders simultaneous ARRIVED/WAITING transitions. Missed student effective_at is the deadline; recorded_at records actual worker/recovery processing. No history is deleted. Closed windows return zero remaining seconds, while the original deadline stays in history.

The immutable trip action snapshot remains intact. Serialization removes confirmed pickups from the unresolved list and projects MISSED/CANCELLED pickup exceptions. Delivery actions remain PENDING; no persistent delivery confirmation was added.

## Worker and local deployment

FastAPI lifespan starts one dedicated expiry thread with an immediate first scan, then polling and bounded batches of 100 due WAITING windows. It runs without browsers/GET requests. Each window is locked, rechecked and committed independently. Repeated processing and concurrent confirmation/expiry are idempotent. Shutdown signals an Event and joins the pickup/planning threads. Uncommitted work rolls back; restart processes overdue rows using their original deadlines.

Expiry latency is interval plus backlog/DB latency. Reads during that delay show remaining_seconds=0 and expiry_pending=true and disable confirmation. GET never starts, extends or expires a window. Worker errors retain pending work; GET /pickup-worker/status exposes process-local running state, heartbeat, actual expired count and sanitized error class without credentials/SQL.

Assumption: one local FastAPI process (default --workers 1), one scheduler, local PostgreSQL and a synchronized server clock; Vite runs separately. Reload replaces the backend process but not durable deadlines. DB locking handles duplicate attempts, but distributed scheduler/leader election, multi-worker deployment and cross-process status aggregation are outside this stage. Do not add a browser-owned expiry timer or another scheduler for the local demo.

## APIs

- GET /pickup-policy
- POST /trips additionally accepts pickup_mode=production|simulation_demo and pickup_scope=per_stop|per_school. Existing route_id-only calls default to production.
- GET /trips/{id}/pickup-windows: server_now, stored settings, deadlines, sampled remaining time and per-student states, timestamps, sources and action flags.
- POST /trips/{id}/pickups/{student_id}/confirm (manual prototype).
- POST /trips/{id}/pickups/{student_id}/cancel with a nonblank reason.
- GET /trips/{id}/pickup-history?limit=100&after_order_id=0: bounded ordered audit, max 500 with continuation cursor.
- GET /pickup-worker/status.

Driver reuses its serialized visible-page polling loop and cleans up requests/timers. It displays production/demo mode, shared scope, deadlines, server sample time/remaining seconds and individual terminal outcomes. Invalid actions are disabled from server flags; cutoff races receive authoritative backend validation. Errors are visible and no mock fallback is used.

## Migration / startup / checks

Project-root Windows PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
npm --prefix .\frontend run build
```

Applied: 0009_pickup_windows and 0010_pickup_audit_order (head). No new runtime dependencies. Downgrade requires an archival plan. Credentials were not changed.

Separate terminals:

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location .\frontend
npm run dev
```

Repeatable test/demo (normal servers running for browser check):

```powershell
Set-Location .\backend
$env:SAFERIDE_RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pickup_windows.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
Set-Location ..\frontend
node .\scripts\verify-stage9c.cjs
npm run build
```

Backend checks create isolated S9C synthetic records and run a real worker in a dedicated server process, with explicit 5-second demo mode. Production 900 s is checked separately. Tests cover shared grouping/return visits, per-stop alternative, arrival-only start, refresh/duplicates, confirmation idempotence, expiry without browser, backend restart overdue recovery, duplicate expiry, strict before/exact cutoff, confirmation/expiry race, individual history, lifecycle cancellation, separate delivery and unchanged optimizer waiting. Exact cutoff tests use controlled timestamps on isolated fixtures, not measured journeys.

The browser check cancels only its previous S9C test trip while preserving history, generates a new simulation route, and selects the normal server's explicit 30-second demo/shared scope in Driver. Real timestamped simulation observations confirm arrival. It checks an API-error fixture/retry, manual pickup/cancel, ALL browser pages closed during expiry, reconnect without deadline reset, disabled invalid actions, all six states in audit and three still-unconfirmed deliveries. No Google/hardware verification; basemap requests are blocked for the check.

Evidence: stage9c_verification.json and stage9c-pickups.png. Backend/browser sections may use different retained fixture trips after reruns. Vite build passes. Separate tsc retains nine pre-existing unused-import/PNG declaration errors outside these changes.


## Manual demonstration

1. Open http://127.0.0.1:5173 -> Driver -> Route. Select vehicle_id from docs/stage9c_verification.json and Afternoon Drop-off. Prior test outcomes may already be terminal. To start a fresh demonstration, deliberately Cancel trip with a reason; do not erase history or change an unrelated trip.
2. Admin -> Routes: same synthetic S9C vehicle/direction, today's Sri Lankan date, Simulation, Generate route. Cancellation permits a new saved version; it does not rewrite the old one.
3. Driver -> Route: select Simulation-only demo and Shared contiguous school visit; Create planned trip, Start trip. Note ID. Initially all students are SCHEDULED, with no deadline and confirmation disabled.
4. Send the repeated simulation positions below at ONLY that current pickup. Confirmed arrival opens one shared school deadline.
5. Manually confirm one pickup, cancel another with a reason, leave the third. Refresh/reconnect without resetting the deadline. Close the browser entirely; reopen after expiry and observe PICKED_UP, CANCELLED and MISSED. All deliveries remain pending. Check audit and worker status.
6. To show production, create a fresh trip with Production selected: it is the full 900 seconds. An accelerated simulation does not prove a real 15-minute physical wait.

Project-root PowerShell, after starting the new demo trip:

```powershell
$demo = Get-Content .\docs\stage9c_verification.json | ConvertFrom-Json
$base = 'http://127.0.0.1:8000'
$trip = (Invoke-RestMethod "$base/trips/current?vehicle_id=$($demo.vehicle_id)").trip
$arrival = Invoke-RestMethod "$base/trips/$($trip.trip_id)/arrival"
$run = [guid]::NewGuid().ToString()
1..5 | ForEach-Object {
    $sample = @{
        sample_id = "pickup-demo-$run-$_"
        trip_id = $trip.trip_id
        source = 'simulation'
        latitude = $arrival.current_stop.latitude
        longitude = $arrival.current_stop.longitude
        recorded_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json
    Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri "$base/routing/vehicles/$($trip.vehicle_id)/positions" -Body $sample
    if ($_ -lt 5) { Start-Sleep -Seconds 5 }
}
Invoke-RestMethod "$base/trips/$($trip.trip_id)/pickup-windows" | ConvertTo-Json -Depth 7
Invoke-RestMethod "$base/trips/$($trip.trip_id)/pickup-history" | ConvertTo-Json -Depth 7
Invoke-RestMethod "$base/pickup-worker/status" | ConvertTo-Json
```

This is stationary synthetic observation input, not a driven trace or RFID. Ctrl+C stops it without ending a trip. Default arrival thresholds still require 15 s dwell, >=3 observations and <=10 s gaps; if customized, satisfy the thresholds shown by Driver. The Stage 9A movement replay does not guarantee stop dwell or pickup-window activation.

## Changed files

backend/models.py; migrations/versions/0009_pickup_windows.py and 0010_pickup_audit_order.py; pickup_windows.py; pickup_worker.py; trips.py; arrivals.py; positions.py; main.py; .env.example; tests/test_pickup_windows.py; tests/test_trip_lifecycle.py (explicit cancelled pickup expectation on lifecycle close).

frontend/src/services/api.ts; hooks/useVehiclePosition.ts; components/DriverStoredRoute.tsx, DriverTrip.tsx and DriverPickupWindows.tsx; scripts/verify-stage9c.cjs.

This document, stage9c_verification.json and stage9c-pickups.png. Synthetic fixtures/outcomes and prior history are retained. No solver files, credentials, datasets or ML artifacts were replaced.

The existing Stage 8B trip lifecycle integration regression also passed with the explicit Stage 9C cancellation policy; its previous saved report was preserved.
