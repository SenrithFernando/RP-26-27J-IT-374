# Stage 4: database-backed multi-school dual routes

## Behavior and model

POST /routes/generate reads the selected vehicle's PostgreSQL roster. PP1 vehicle assignments remain fixed: the solver neither reassigns nor drops active students. Generate morning and afternoon separately; each builds its own nodes and matrix. Afternoon is not a reversal of morning.

Each active student has mandatory pickup and delivery actions: home to assigned school in the morning, assigned school to home in the afternoon. The load dimension bounds onboard passengers between zero and capacity. Total roster size is not used as the capacity model. Deliveries release capacity, so a six-student roster can be feasible on a capacity-two vehicle. Schools may be visited repeatedly.

A separate unit-increment order dimension enforces pickup strictly before delivery even for colocated, zero-duration actions. Both events are restricted to the single registered vehicle. An independent post-solve audit checks coverage, destinations, sequence, load, school windows and time accounting before persistence.

Morning school delivery service must start by the school's arrival deadline. Afternoon pickup service cannot start before school finish. Physical arrival can be earlier, with waiting before service. Each stop returns arrival, service-start ETA and departure. Service duration applies per student action.

Both directions start and end at the configured vehicle endpoints. Routing arithmetic uses integer seconds and metres. Departure and school times are seconds after midnight in Asia/Colombo on the requested service date; ISO timestamps include the offset and next-day dates when applicable. Departure, service durations, maximum route duration, solver limit and simulation speed are configurable.

Missing or unconfirmed coordinates and unknown school schedules are reported; neither coordinates nor bell times are invented. Existing route endpoints remain unchanged.

## Provider and solution status

TravelTimeProvider.precompute builds the full dynamic cost matrices before OR-Tools callbacks are registered. Callbacks only index arrays and event demands/service times. Wrong matrix shapes, non-integer/negative costs, missing provenance and unreachable pairs represented by None are rejected. Unreachable pairs are never changed to zero cost. Colocated points can legitimately cost zero.

The first provider is deterministic simulation: Haversine straight-line metres divided by configured speed. Defaults are 6 m/s morning and 5 m/s afternoon. Distances are approximate and driving durations are simulated. Service is configured; waiting is calculated. Solver runtime is measured performance, not an observed trip duration. No road, live traffic or ML provider was added.

The solver limit defaults to 2 seconds and is restricted to 1–10 seconds. The objective combines driving-plus-service arc cost and elapsed route duration, in seconds. A feasible heuristic result is not claimed to be a proven global optimum. The Leaflet polyline remains labeled “Stop sequence — not a road route”; OSM supplies basemap tiles only.

Feasibility statuses are feasible, invalid_input, invalid_provider_input, infeasible, timeout, or no_solution_found. The last status does not imply proven infeasibility. Failed generation versions have no stop rows and null distance/duration totals, rather than fabricated zero metrics. Input validation before a solver run has null solver runtime. The prototype explicitly rejects rosters exceeding 200 active students instead of serving only a subset.

## Persistence and API

Migration 0004 adds nullable school bell times, route_versions and route_stops. Generation saves input/settings snapshots, summary results and ordered stop details atomically. Versions increase independently per vehicle/direction. Vehicle, registration and school rows are locked during the bounded solve; inactive registrations are locked too, preventing reactivation from changing the captured roster mid-generation. Generation never changes registered assignments.

GET /routes/latest?vehicle_id=...&direction=... reads the highest stored version and its stop rows. It does not fetch provider costs or run the solver. It returns the latest attempt even if that attempt failed, without substituting an older feasible result. Historical route locations and ETAs remain snapshots after registration changes; generate a new version to apply edits.

POST /routes/generate accepts vehicle_id, direction, departure_seconds, optional service_date, pickup_service_seconds, delivery_service_seconds, max_route_seconds, solver_time_limit_seconds, provider (simulation only), and optional simulation_speed_mps (0.01–50).

Responses include route ID/version, vehicle, direction, date/departure/timezone, roster count/capacity, feasibility/errors, distance_metres, driving_seconds, service_seconds, waiting_seconds, total_duration_seconds, solver_runtime_seconds, solver_status, provider_source, assignment policy and request settings. Stops include actions, student/school references, physical location IDs, coordinates/address/provenance, arrival/ETA/departure, incoming driving/distance, service/waiting and before/after load.

PUT /routing/schools/{school_id}/schedule accepts morning_deadline_seconds and afternoon_finish_seconds, each an integer from 0 through 86399. Unknown school returns 404. Unknown generation vehicle returns 404; malformed generation bodies return 422 without creating a version. Valid requests whose constraints cannot produce an itinerary are stored as failed versions with an explicit status.

## Exact Windows PowerShell commands

Backend terminal:

    cd C:\Users\MSI\Desktop\Safe_Ride_LK\backend
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m alembic upgrade head
    .\.venv\Scripts\python.exe -m alembic check
    .\.venv\Scripts\python.exe seed_routing_demo.py
    .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

Reuse the existing updated backend if already running. Credentials stay in ignored backend/.env. No external API key is needed for simulation.

The optional insert-only demo seed creates S4_SCHOOL_A/B, capacity-two S4_VAN_A/B, and S4_STUDENT_01 through 12. Each vehicle has six students attending both schools. Coordinates, confirmations and schedules are explicit synthetic test inputs. Reruns preserve existing IDs and edits, without deleting, moving or overwriting registrations. The previous seed.py command is unchanged.

Frontend terminal:

    cd C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
    npm.cmd install
    npm.cmd run build
    npm.cmd run dev -- --host 127.0.0.1

Generate the two directions independently (server defaults the service date to today in Asia/Colombo):

    $morningBody = @{
        vehicle_id = 'S4_VAN_A'
        direction = 'morning'
        departure_seconds = 21600
        pickup_service_seconds = 30
        delivery_service_seconds = 30
        max_route_seconds = 21600
        solver_time_limit_seconds = 2
        provider = 'simulation'
    } | ConvertTo-Json
    $morning = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/routes/generate -ContentType 'application/json' -Body $morningBody

    $afternoonBody = @{
        vehicle_id = 'S4_VAN_A'
        direction = 'afternoon'
        departure_seconds = 45000
        solver_time_limit_seconds = 2
        provider = 'simulation'
    } | ConvertTo-Json
    $afternoon = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/routes/generate -ContentType 'application/json' -Body $afternoonBody
    $afternoon.stops | Format-Table sequence,action,student_id,school_id,location_id,eta,load_before,load_after

    $latest = Invoke-RestMethod 'http://127.0.0.1:8000/routes/latest?vehicle_id=S4_VAN_A&direction=morning'
    if ($latest.route_id -ne $morning.route_id) { throw 'Stored route ID differs' }

Pure tests do not require a database connection; the storage test is opt-in. To run all 13 checks against the configured PostgreSQL database:

    cd C:\Users\MSI\Desktop\Safe_Ride_LK\backend
    $env:SAFERIDE_RUN_DB_TESTS = '1'
    try {
        .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    } finally {
        Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
    }

The integration test ensures S4 fixtures exist, creates additional route versions, preserves assignments, checks a failed version, then leaves a feasible latest morning route. Fixture edits are preserved by the seed and can affect test feasibility.

## Browser verification

1. Open http://127.0.0.1:5173 → Administrator → Routes. Select S4_VAN_A and Morning Pickup. Loading stored results must not create a new version.
2. Set departure 06:00:00, pickup/delivery service 30 seconds, maximum route 21600 seconds, solver limit 2 seconds and simulation speed 6 m/s. Click Generate route.
3. Inspect the version, six assigned students and capacity two. A feasible fresh fixture has 14 rows: start, twelve student actions, end. Check each pickup precedes its delivery, destinations match assigned schools, and loads stay 0–2.
4. Click grouped school pins to see every colocated action, sequence and ETA. No coordinates are shifted to separate markers. The line is a stop sequence, not road geometry.
5. Switch to Afternoon Drop-off, use departure 12:30:00 and speed 5 m/s, then generate. School pickups must start no earlier than 13:00 for A and 13:30 for B in the synthetic fixtures. Deliveries must be at the corresponding homes. Inspect driving, service and waiting separately.
6. Repeat with S4_VAN_B. Generation must leave all student registrations unchanged. Each direction is solved independently.
7. Open School schedules (Asia/Colombo). Save edited times, then generate a new version to use them. Saving schedules alone does not solve. Blank bell times are unknown and block affected routes.
8. Generate S4_VAN_A morning with departure 23:00:00. Expect an infeasible stored attempt, no stops and unavailable totals. Restore 06:00:00 and generate another version.
9. The original VAN_01 currently has missing/unconfirmed locations and schedules; generation reports them explicitly. Configure homes in Students, school/vehicle positions through Configure map locations, and bell times before expecting a route.
10. Refresh/reselect a vehicle and direction, or click Reload stored route. Restart FastAPI without reseeding and repeat: stored route IDs, versions and stops must remain. Switching selectors during generation does not cancel the server operation, but its old response must not overwrite the new view.
11. Use DevTools Offline/request blocking to verify read and generation errors. No mock itinerary should appear; generation settings remain available for retry.

Read-only pgAdmin queries:

    SELECT id, vehicle_id, direction, version, feasibility_status, created_at
    FROM route_versions ORDER BY created_at DESC, version DESC;
    SELECT route_id, sequence, action, student_id, location_id, eta_seconds
    FROM route_stops ORDER BY route_id, sequence;
    SELECT id, vehicle_id, school_id, active FROM students
    WHERE id LIKE 'S4_STUDENT_%' ORDER BY id;

## Checks completed

- All 13 backend tests passed with PostgreSQL enabled. Alembic found no model/schema drift; dependency consistency passed.
- Checked both-direction coverage and destinations, capacity reuse with roster larger than capacity, zero-time precedence, load bounds, afternoon waiting, impossible deadlines, missing coordinates/schedules, wrong assignments, unreachable/invalid matrices, bounded limit validation, and post-solve rejection of corrupt results.
- Persisted both vehicles/directions with ordered stop rows and increasing versions. Latest was read with solver and provider methods patched to fail if invoked, proving it is retrieval-only.
- Separate backend processes before/after a controlled restart returned identical stored route/stops/timings/version. GET latest created no new versions; the existing backend on 8000 was left running.
- Browser generation, backend-derived summaries/actions, grouped school popups, schedule saves, empty/error states, failure statuses and refresh persistence passed. Delayed GET and POST responses could not overwrite a newer selector choice. Network errors retained settings and did not substitute mock results.
- Browser tests intercepted map tiles to avoid automated traffic to public OSM tile servers. No live routing/traffic or ML metrics were fabricated.
- Production frontend build passed. The full TypeScript check still reports the existing unused-import and PNG declaration errors elsewhere, with no errors in changed files.
- Legacy /routes/morning, /routes/afternoon, /students, /vehicle and /health remain operational. The working Routes page uses the new database endpoints.

## Changed files

New backend: routing_domain.py, travel_time.py, route_solver.py, route_schemas.py, route_service.py, route_api.py, migrations/versions/0004_persistent_routes.py, seed_routing_demo.py, tests/test_dual_route_solver.py and tests/test_route_storage.py.

Updated backend: models.py, persistence.py and main.py. optimizer.py remains unchanged for legacy endpoints.

Updated frontend: services/api.ts, pages/RouteOptimization.tsx, pages/StudentsPage.tsx, components/RouteMap.tsx and components/RouteLocations.tsx. Existing Leaflet loading and confirmed-location forms are reused.

Reference: [OR-Tools RoutingModel API](https://or-tools.github.io/docs/python/classortools_1_1constraint__solver_1_1pywrapcp_1_1RoutingModel.html).
