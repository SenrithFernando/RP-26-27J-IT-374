# Stage 9B: current-stop GPS proximity arrival

## Scope and state

The active Trip's route_id remains immutable. A persisted current_stop_sequence points to a RouteStop in that saved version; neither the latest plan nor nearby future stops are searched. Starting a trip selects its first stop after the start action (normally the first pickup). The final vehicle-end stop can also be monitored.

POST position ingestion calls arrival processing in the same database transaction, only for a newly inserted sample that advances the vehicle's recorded-time latest position and explicitly references this ACTIVE trip. Position ingestion locks the vehicle then the trip; lifecycle/stop selection also locks the trip. Duplicate samples bypass processing. Samples at/before the current-stop selection or trip start, out-of-order samples, stale samples, accepted-but-future clock-skew samples and samples without an explicit active-trip association cannot earn dwell or arrival.

Driver states:

- Approaching: eligible fresh GPS, but no sustained entry candidate. This label does not assert measured motion toward the stop.
- Arrival candidate: entry observed, awaiting recorded-time dwell and minimum repeated observations.
- Arrived: one persisted proximity event; this latches until explicit current-stop advancement. Leaving the geofence cannot create another arrival or change the event timestamp.
- GPS unknown: missing/stale/ineligible GPS, interrupted candidate observations, inactive trip, or unavailable status. Unknown is not outside the geofence. A previously persisted event is still returned and shown, even when current GPS becomes unknown.

Proximity never confirms boarding, delivery, attendance or RFID. Trip unfinished_actions remain PENDING. Arrival does not advance the stop or finish the trip automatically.

There was no stop progress pointer in Stage 8B/9A. This stage adds an explicit manual Next stop (manual; no passenger confirmation) action after a recorded arrival. It advances exactly one stop of the saved version, with expected_stop_sequence guarding duplicate/stale requests. It does not complete a passenger action. No skip/future-stop selection or automatic rerouting was added. A new selected stop requires new observations after its selection timestamp, including colocated stops. The last stop has no next-stop action.

## Explicit configuration

New variables in backend/.env.example; actual overrides belong in backend/.env:

```dotenv
ARRIVAL_RADIUS_METRES=50
ARRIVAL_EXIT_RADIUS_METRES=75
ARRIVAL_DWELL_SECONDS=15
ARRIVAL_MIN_OBSERVATIONS=3
ARRIVAL_MAX_GAP_SECONDS=10
ARRIVAL_FRESHNESS_SECONDS=20
```

Units are metres and seconds. Exit radius must exceed entry radius, minimum observations must be at least two, and max gap cannot exceed freshness. Values must be finite and within the bounded schema ranges. Invalid settings fail backend startup. Settings are snapshotted on trip start, so changing the environment/restarting does not alter an existing trip's thresholds. Pre-migration active trips receive a first current stop at migration time; no old positions are replayed, and their settings are frozen on their first eligible ingestion.

Entry is distance <= 50 m. Before entry, the 50-75 m band cannot create a candidate. After entry, observations within <=75 m retain the candidate; >75 m resets it. This hysteresis prevents boundary chatter around 50 m. Arrival requires at least 3 eligible observations and at least 15 seconds between the first candidate and confirming GPS recorded_at timestamps, with no inter-observation gap greater than 10 seconds. Changing between simulation/device sources restarts the candidate; sources cannot combine to earn dwell.

Freshness is assessed against server UTC at processing time; recorded_at drives candidate, gap, dwell and arrived_at calculations. Timezone-aware timestamps are persisted. The event's arrived_at is the confirming observation's recorded_at, not the HTTP receipt time or a fabricated physical arrival instant. candidate_started_at is retained separately. A gap breaks continuous dwell; stale batches cannot manufacture an arrival. There is no interpolation across missing GPS. GET only projects current unknown/stale state; the next eligible observation restarts expired candidate evidence.

Arrival freshness (20 s) is deliberately stricter than Stage 9A's general position stale threshold (60 s). A displayed vehicle position can therefore still be generally fresh while arrival evidence is GPS unknown. This is not evidence that the vehicle stopped or left the geofence.

The trip_stop_arrivals table has one primary-key row per (trip_id, stop_sequence), holding candidate state and, once confirmed, a unique event_id, arrived_at and confirming_position_id. Event identity/time/source remain unchanged after arrival. The composite primary key supports bounded per-current-stop reads. The existing position indexes serve latest GPS lookup. No scan across all stops or telemetry history is used.

## Migration and API

Windows PowerShell, project root:

```powershell
.ackend.venvScriptspython.exe -m alembic -c .ackendalembic.ini upgrade head
.ackend.venvScriptspython.exe -m alembic -c .ackendalembic.ini current
```

Applied revision: 0008_stop_arrivals. No new dependencies. Downgrade deliberately requires an explicit archival plan for arrival evidence.

- Existing POST /routing/vehicles/{vehicle_id}/positions now returns arrival_detection processing outcome. Position/arrival writes commit atomically.
- GET /trips/{trip_id}/arrival returns current saved stop, four-state proximity status, reason, exact settings, age, current eligible GPS distance and dwell evidence count, candidate time and any persistent current-stop arrival event. It never runs detection or changes progress.
- POST /trips/{trip_id}/advance-stop?expected_stop_sequence=... requires ACTIVE state, a recorded current-stop arrival and a following saved stop. A replayed request conflicts rather than skipping another stop.

Existing route/lifecycle endpoints remain. Completing/cancelling still does not mark unfinished students delivered, and terminal trips ignore arrival ingestion.

## Actual checks

Focused PostgreSQL checks use isolated S9B-prefixed synthetic school/student/vehicle/trip records with controlled GPS timestamps, deterministic simulation routing and geometry disabled. They verify radius boundary/hysteresis, a nearby future stop ignored, duplicate/out-of-order samples ignored, GPS gaps/source changes resetting dwell, stale samples ignored, recorded-time dwell/minimum counts, a single immutable event despite repeated inside/outside samples, unknown versus outside, a fresh DB session reading the event, and explicit advancement preserving passenger actions with stale advance requests rejected.

The browser check uses actual timestamped HTTP samples against the local server and verifies GPS unknown -> approaching -> candidate -> arrived in Driver, immutable duplicate arrival, unchanged pending passenger actions, and manual advancement to a colocated stop beginning GPS unknown. No page errors were observed. Basemap requests were blocked in the check; Google and physical GPS hardware were not tested. Evidence: stage9b_verification.json and stage9b-arrival.png. Backend and browser sections may use distinct retained fixture trips when the backend check is rerun.

```powershell
Set-Location .ackend
$env:SAFERIDE_RUN_DB_TESTS='1'
..venvScriptspython.exe -m unittest discover -s tests -p test_arrivals.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
Set-Location ..rontend
node .scriptserify-stage9b.cjs
npm run build
```

Run the backend check first to create a fresh test trip at stop 3 before repeating the browser check. The browser check advances it to the final stop. These are opt-in synthetic fixtures; existing project vehicles are not used. Vite build passes; the separate tsc check still has the nine pre-existing unused-import/PNG-declaration errors outside this stage's files.

## Exact browser / simulation demonstration

Start the usual backend and frontend terminals. Open http://127.0.0.1:5173 -> Driver -> Route. Select vehicle_id from docs/stage9b_verification.json and Morning Pickup. This isolated fixture is ACTIVE. The arrival panel shows the selected saved-route stop and exact thresholds.

From the project root, the following sends repeated simulation coordinates at ONLY that selected stop, using real current timestamps. This demonstrates the detector, not a driven trace or passenger event:

```powershell
$demo = Get-Content .docsstage9b_verification.json | ConvertFrom-Json
$base = 'http://127.0.0.1:8000'
$tripUrl = "$base/trips/$($demo.trip_id)"
$arrival = Invoke-RestMethod "$tripUrl/arrival"
$run = [guid]::NewGuid().ToString()
1..5 | ForEach-Object {
    $sample = @{
        sample_id = "arrival-demo-$run-$_"
        trip_id = $demo.trip_id
        source = 'simulation'
        latitude = $arrival.current_stop.latitude
        longitude = $arrival.current_stop.longitude
        recorded_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json
    Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri "$base/routing/vehicles/$($demo.vehicle_id)/positions" -Body $sample
    if ($_ -lt 5) { Start-Sleep -Seconds 5 }
}
Invoke-RestMethod "$tripUrl/arrival" | ConvertTo-Json -Depth 6
```

Observe arrival candidate and then arrived. The event source is simulation. Reposting the same final $sample returns duplicate=true without another arrival. Repeated inside samples retain the original arrived_at. Stop sending observations: a candidate becomes GPS unknown after the maximum gap; general missing/stale arrival GPS becomes unknown after freshness. Durable arrival evidence remains visible. If a next stop exists, click its explicit manual button; the next stop begins unknown and requires new observations. Passenger pickup/delivery entries remain PENDING throughout.

The Stage 9A movement replay has no guaranteed dwell at stops; it must not be described as guaranteed arrival evidence. Use the explicit repeated-observation demo above or provide a timestamped simulation fixture with genuine repeated stop observations. Ctrl+C can stop the simulation loop; it does not finish the trip.

## Changed files

backend/models.py; backend/migrations/versions/0008_stop_arrivals.py; backend/arrivals.py; backend/positions.py; backend/trips.py; backend/main.py; backend/.env.example; backend/tests/test_arrivals.py.

frontend/src/services/api.ts; frontend/src/hooks/useVehiclePosition.ts; frontend/src/components/DriverStoredRoute.tsx; frontend/src/components/DriverTrip.tsx; frontend/scripts/verify-stage9b.cjs.

This document, docs/stage9b_verification.json and docs/stage9b-arrival.png.
