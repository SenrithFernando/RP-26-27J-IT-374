# Stage 9A: persisted vehicle positions and GPS replay

Existing confirmed vehicle depot fields remain planning inputs. No position ingestion or arrival detector existed. The new vehicle_positions table stores telemetry separately from vehicle depots, trips, route versions and unfinished passenger actions. It does not change lifecycle or emit arrival/pickup/delivery events.

## API

- POST /routing/vehicles/{vehicle_id}/positions
- GET /routing/vehicles/{vehicle_id}/positions/latest?trip_id=... (optional trip filter)
- GET /routing/vehicles/{vehicle_id}/positions?trip_id=...&limit=100&window_seconds=3600

POST body example (use an existing vehicle/trip and an actual aware timestamp):

```json
{"sample_id":"client-stable-sample-identity","trip_id":"TRIP_...","source":"simulation","latitude":6.9,"longitude":79.9,"speed_mps":null,"recorded_at":"2026-10-16T18:00:00+05:30"}
```

Trip association is optional for ingestion, mandatory for the replay CLI. If supplied, it must exist and belong to that vehicle. Positions can be stored for historical/terminal trips without changing their state; replaying such a trip is a telemetry demonstration, not trip execution. Actual-device ingestion accepts reported device input but no real GPS hardware has been verified in this stage.

Coordinates and speed must be finite, speed nonnegative (or null for unknown). recorded_at must be timezone-aware; received_at is the server's aware receipt timestamp. More than 30 seconds into the server's future is rejected with 422. This fixed tolerance is a clock-skew allowance, not permission to upload future traces.

Unique indexes cover vehicle/source/sample ID and vehicle/recorded timestamp. Repeated identical samples (including a new sample ID at the same timestamp) return duplicate=true, advances_latest=false. Reusing an identity or timestamp with different content returns 409. A per-vehicle row lock serializes ingestion. Out-of-order samples are retained, return advances_latest=false, and cannot roll back the latest position. Latest means greatest recorded_at, never received_at. No downstream events are emitted; arrival detection is explicitly not implemented.

Latest returns position=null, age_seconds=null, status=unknown when absent. A sample older than 60 seconds is stale. Negative age within clock-skew tolerance is clamped to zero. movement_state remains unknown; missing/stale GPS is never interpreted as stopped. A reported zero speed is only a source-labelled sample value, not arrival evidence.

History is newest first, at most 500 results plus a bounded truncation probe, within a maximum seven-day window. Default is 100 samples within one hour. Composite vehicle/recorded-time and trip/recorded-time indexes support latest and history queries. No unbounded history/count query is exposed.

## Migration / build (Windows PowerShell, project root)

```powershell
.ackend.venvScriptspython.exe -m alembic -c .ackendalembic.ini upgrade head
.ackend.venvScriptspython.exe -m alembic -c .ackendalembic.ini current
npm --prefix .rontend run build
```

Applied revision: 0007_vehicle_positions. No new runtime dependencies. Credentials remain in backend/.env.

## Start servers in separate terminals

```powershell
Set-Location .ackend
..venvScriptspython.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
Set-Location .rontend
npm run dev
```

## Exact replay demonstration (project root)

The saved selection in docs/stage9a_demo_selection.json identifies the isolated synthetic vehicle and persisted trip used for verification. This trip is already COMPLETED. Position replay preserves that state and its unfinished actions.

```powershell
$demo = Get-Content .docsstage9a_demo_selection.json | ConvertFrom-Json
.ackend.venvScriptspython.exe .ackend
eplay_positions.py --vehicle-id $demo.vehicle_id --trip-id $demo.trip_id --fixture .datagps_replay_synthetic.csv --speed 5 --rebase-to-now
```

Press Enter to start, Ctrl+C to stop. Every sample is forced to source=simulation, regardless of CSV contents. Only the explicitly selected vehicle is updated; trip ownership is checked before ingestion. The CLI prints actual sample counts, duplicate status and whether the sample advanced latest. Stopping does not complete/cancel the trip or remove stored samples.

The timestamped CSV has 31 synthetic samples interpolated from the selected saved trip's stop sequence. It is not road geometry or a driven road trace. Its speed is unknown/null rather than invented. The replay script created the CSV using:

```powershell
.ackend.venvScriptspython.exe .ackend
eplay_positions.py --vehicle-id $demo.vehicle_id --trip-id $demo.trip_id --fixture .datagps_replay_synthetic.csv --make-fixture
```

Use your own vehicle/trip IDs explicitly to generate another fixture. CSV columns: recorded_at, latitude, longitude, speed_mps, source, description. The CLI checks timezone-aware timestamps, monotonic fixture order, finite valid values and a 10,000-row cap before posting anything.

Without --rebase-to-now, original recorded timestamps are preserved and old fixtures display stale. With --rebase-to-now, recorded timestamps use a current simulation timeline scaled by --speed so accelerated replay does not post implausibly future timestamps. Speeds in an imported fixture are reported fixture inputs, not measurements derived by this tool. Each invocation uses a new sample identity namespace; retries within a run can reuse the same payload safely.

## Browser verification

1. Open http://127.0.0.1:5173 -> Driver -> Route.
2. Select the exact vehicle_id in docs/stage9a_demo_selection.json and Afternoon Drop-off. The persisted trip stays COMPLETED; do not restart it to demonstrate telemetry.
3. Expand Fixed trip itinerary and estimates. Run the replay command and press Enter.
4. The red vehicle marker follows backend samples. Vehicle GPS status shows Sri Lankan recorded/received time, simulation source, age, coordinates, and unknown speed. The map retains its stop-sequence label.
5. Zoom manually during replay: position changes preserve zoom. Changing route/vehicle may legitimately fit new fixed stop bounds.
6. Stop replay. Once the last sample is over 60 seconds old, status becomes stale; it is not shown as a stopped vehicle. Closing Driver route stops position polling. Hidden pages pause polling and resume on visibility.

API verification:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/routing/vehicles/$($demo.vehicle_id)/positions/latest" | ConvertTo-Json -Depth 5
Invoke-RestMethod "http://127.0.0.1:8000/routing/vehicles/$($demo.vehicle_id)/positions?limit=5&window_seconds=3600" | ConvertTo-Json -Depth 5
```

## Checks / evidence

```powershell
Set-Location .ackend
$env:SAFERIDE_RUN_DB_TESTS='1'
..venvScriptspython.exe -m unittest discover -s tests -p test_positions.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
Set-Location ..rontend
node .scriptserify-stage9a.cjs
npm run build
```

The backend check creates a new S9A-prefixed vehicle and isolated sample records; it does not alter existing route/student/trip state. It checks unknown/stale/fresh responses, duplicate identity/timestamp deduplication, conflicting duplicates, out-of-order latest stability, finite/range/speed/time/source/ID validation, bounded history, aware timestamps and persistence across a focused backend process restart. No arrival detector is claimed or tested.

The browser check runs the real replay script against the normal API, verifies moving backend markers, unchanged manual viewport, an unrelated vehicle's latest position remaining unchanged, polling cleanup on unmount and no page errors. Existing Playwright installation is used. It blocks basemap tile requests; it does not verify external tile availability. No Google calls are made. Actual outputs are in docs/stage9a_verification.json and screenshot stage9a-driver.png.

The separate TypeScript check retains the nine pre-existing unused-import/PNG-declaration errors outside this stage's modified files. Vite build passes.

## Changed files

backend/models.py; backend/main.py; backend/positions.py; backend/migrations/versions/0007_vehicle_positions.py; backend/replay_positions.py; backend/tests/test_positions.py.

frontend/src/services/api.ts; frontend/src/hooks/useVehiclePosition.ts; frontend/src/components/RouteMap.tsx; TrafficDetails.tsx; DriverStoredRoute.tsx; DriverTrip.tsx; frontend/scripts/verify-stage9a.cjs.

data/gps_replay_synthetic.csv; docs/stage9a_demo_selection.json; docs/stage9a_verification.json; docs/stage9a-driver.png; this document.

No automatic rerouting, arrival detection, passenger completion, RFID or hardware integration was added.
