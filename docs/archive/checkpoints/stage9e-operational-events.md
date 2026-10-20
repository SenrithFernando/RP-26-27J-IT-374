# Stage 9E: preliminary deviation and unexpected-stop episodes

## Scope and geometry provenance

The ACTIVE trip's immutable saved route is used, never the latest planning version. Existing timestamped position ingestion, trip lifecycle, pickup waiting and Driver polling/map components are reused. No automatic rerouting or new notification broadcast was added. These are operational anomalies, not crash, emergency or safety diagnoses. Accuracy and proposal precision/recall targets have NOT been validated.

Stored Google encoded road geometry is accepted only when status/provider provenance matches google_routes, bounded decoding succeeds, coordinates are valid, endpoints match the saved route within 100 m and every saved stop lies within 100 m of the decoded line. The quality is provider_road_geometry: stored provider provenance/shape checked, NOT independently verified physical road accuracy. No live Google request was made or verified here. Unknown/malformed/mismatched provider geometry falls back with a reason.

Fallback quality is approximate_stop_sequence, with source stop_sequence. Its straight segments are not driven roads. Deviation from them is approximate and may flag perfectly legitimate road detours. Driver explicitly labels this quality and displays the source, reason and selected threshold. Missing usable geometry disables deviation calculation; low-movement monitoring can still use saved stop locations.

Point-to-polyline distance is the minimum clamped point-to-segment distance in metres using a local equirectangular metric projection centred on the GPS point (Earth radius 6,371,000 m). Degenerate segments and endpoints are handled. This local Sri Lankan research calculation is not an ellipsoidal survey or a validated worldwide detector. Basemap tiles are not a routing/traffic source.

## Explicit provisional settings

backend/.env.example adds:

```dotenv
OPS_ROAD_DEVIATION_METRES=100
OPS_SEQUENCE_DEVIATION_METRES=300
OPS_DEVIATION_SECONDS=20
OPS_RECOVERY_SECONDS=10
OPS_STOP_SECONDS=60
OPS_LOW_MOVEMENT_MPS=0.5
OPS_STOP_RADIUS_METRES=15
OPS_STOP_RECOVERY_METRES=30
OPS_EXPECTED_DWELL_RADIUS_METRES=75
OPS_MAX_GAP_SECONDS=10
OPS_FRESHNESS_SECONDS=20
OPS_MIN_OBSERVATIONS=3
```

Actual overrides belong in backend/.env. All numeric thresholds are finite/bounded, gap cannot exceed freshness and stop recovery distance must exceed stationary radius. Invalid settings fail startup. Settings and geometry are snapshotted when a trip starts; changes do not silently alter an active trip. Pre-9E ACTIVE trips lazily initialize on their first fresh eligible observation, without backfilling old GPS episodes. Recovery corridor is 60% of the geometry-specific deviation threshold (60 m road / 180 m stop sequence with defaults).

## Fresh ordered evidence and episodes

Only newly inserted samples that advance the vehicle's recorded-time latest position and explicitly reference its ACTIVE trip are processed. Samples before trip start, duplicate/out-of-order observations, stale batches and accepted-but-future clock-skew samples do not earn duration or transitions. Candidate/count/anchor/last-point state is persisted, alongside raw GPS history. The detector uses a bounded streaming history summary rather than unbounded queries over all GPS rows.

Every sustained/recovery interval uses GPS recorded_at, not HTTP receipt time. Freshness is assessed at processing time. Gaps greater than max_gap or source changes clear candidate/recovery evidence; they do not close an existing episode. A fresh repeated run is required after a gap. Missing GPS returns unknown, never stopped, outside, recovered or a crash. GET reads do not create episodes.

Deviation: outside the selected threshold continuously for the configured duration and minimum count creates one ACTIVE episode. Single excursions reset when back inside. An active episode remains latched through boundary jitter; sustained return inside the smaller recovery corridor creates RECOVERED with GPS recovery time/source/position. Repeated outside observations create no second alert. After recovery a later sustained excursion can open another numbered episode.

Unexpected stop: consecutive eligible GPS coordinates must show derived step speed <=0.5 m/s while staying within a 15 m anchor cluster for 60 s and >=3 observations by default. Reported speed_mps is NOT trusted as stop proof: moving positions with reported zero speed do not qualify. Slow drift beyond the anchor radius resets the candidate.

Expected dwell is conservatively excluded within 75 m of saved pickup, delivery/school or depot locations. A physically nearby active pickup window is labelled known waiting; a remote open pickup window cannot excuse an off-route stationary cluster elsewhere. Stored planned waiting is also labelled when the nearby GPS recorded time falls between the saved arrival and service-start ETA. This location exclusion includes planned future stop locations to reduce false operational alerts; it does NOT start future arrival/pickup processing or confirm any passenger action. Unmodelled traffic-light/congestion/manual waiting away from these zones may still be flagged; no validated discrimination is claimed.

An active unexpected-stop episode recovers after sustained displacement >30 m from its original cluster, or sustained reclassification into an expected-dwell context, for the configured recovery duration/count. The latter is explicitly recorded as expected-dwell reclassification, not claimed vehicle motion. The original episode's timestamp/source remain unchanged. Trip completion/cancellation closes still-active episodes as CLOSED with a server timestamp and reason; it does not claim GPS recovery.

PostgreSQL unique constraints enforce numbered episode identity and at most one ACTIVE episode per trip/kind. Existing vehicle/trip locking serializes ingestion; operational state and episode writes commit in the same transaction as the GPS sample. No one-alert-per-sample spam or new safety notification channel was introduced. Episode records retain start, confirmation, processing, recovery/closure times, sources, thresholds, saved route and confirming/recovery positions. Restart/new sessions preserve candidates and episodes.

## Display and API

GET /trips/{trip_id}/operational-events?limit=50 returns up to 200 persisted episodes, freshness, source, geometry quality/reason, selected thresholds, last eligible distance, GPS-derived movement and waiting suppression. Older records stay persisted if the response is truncated. GET never analyzes an unordered batch or optimizes a route.

Driver -> Route -> selected vehicle/direction -> Preliminary route / movement events shows the same backend evidence. It distinguishes approximate stop-sequence deviation, operational low movement, ACTIVE/RECOVERED/CLOSED, source and Sri Lankan timestamps. Thresholds are expandable. Polling/abort/visibility/unmount cleanup reuses the existing GPS loop. Existing cabin/RFID/emergency demonstrations remain separate. Prototype role/vehicle selection is not authentication.

## Migration and focused checks (Windows PowerShell)

Project root:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
npm --prefix .\frontend run build
```

Applied head: 0012_operational_episodes. No new runtime dependencies or provider credentials. No paid API calls or ML retraining.

```powershell
Set-Location .\backend
$env:SAFERIDE_RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_operational_monitor.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
```

Three focused checks passed: metric segment/endpoint/degenerate cases; encoded geometry provenance/shape/fallback; isolated PostgreSQL episodes with controlled GPS timestamps. They cover normal movement with reported speed zero, sustained deviation/recovery, duplicate/late samples, one active episode per kind, low movement, expected pickup/known waiting suppression, GPS loss, gaps, second episodes after recovery, PostgreSQL uniqueness, new-session persistence and closure distinct from recovery. These are synthetic development checks, not measured real-world accuracy. Vite build passes; standalone tsc retains the nine pre-existing unused-import/PNG declaration errors outside these files.

Evidence: docs/stage9e_verification.json. The focused test retains its cancelled historical test trip and creates a NEW isolated ACTIVE replay trip on the same synthetic vehicle. Manifest and six CSVs are generated by running Python, not invented evaluation artifacts.


## Replay scenarios

The generated data/operational_replays/manifest.json links the exact synthetic vehicle, ACTIVE trip and saved route. Every CSV row is source=simulation and has an aware timestamp. Speeds are unknown/null rather than invented device measurements. Movement follows the selected saved geometry where appropriate; stop-sequence-based movement is explicitly synthetic, not a driven road trace.

| CSV | Default development scenario | Expected interpretation |
| --- | --- | --- |
| normal_travel.csv | 8 samples over 14 s, roughly 5 m/s on one saved segment | No new anomaly; reported speed is not used as proof |
| sustained_deviation.csv | 13 off-route samples over 24 s | One sustained approximate deviation episode |
| recovery.csv | 21 samples over 40 s: off-route then sustained return | Original episode recovers, not a second alert per sample |
| expected_waiting.csv | 33 repeated pickup-location samples over 64 s | Expected stop/known pickup waiting suppresses unexpected stop |
| unexpected_stop.csv | 33 low-movement samples over 64 s at a route point clear of stop geofences | One operational low-movement episode, not a crash |
| gps_loss.csv | 16 moving samples over 60 s with a 32-second gap containing NO rows | GPS unknown during gap; no inferred stop/recovery |

Counts/durations adapt if thresholds are configured differently; read the actual generated manifest. A stationary deviation long enough to exceed the stop threshold can independently trigger both types. Expected-wait suppression is conservative, not validated accuracy. Scenarios share durable episode history when run on the same trip: use recovery/new fresh evidence deliberately, or create a new trip for independent demonstrations. GPS loss after an active unexpected stop must leave that event unresolved. A later relocation beyond the stored stop recovery radius must itself persist long enough to record recovery.

Project-root PowerShell (normal servers running):

```powershell
$demo = Get-Content .\data\operational_replays\manifest.json | ConvertFrom-Json
$scenario = 'normal_travel'
.\backend\.venv\Scripts\python.exe .\backend\replay_positions.py --vehicle-id $demo.vehicle_id --trip-id $demo.trip_id --fixture ".\data\operational_replays\$scenario.csv" --speed 1 --rebase-to-now
```

Press Enter to start and Ctrl+C to stop. Choose any of the six exact scenario names above without .csv. Keep --speed 1 for the stored sustained-time thresholds: accelerated wall-clock/rebased playback compresses recorded time and may correctly fail to create an episode. No claim of a 60-second stop should be made from an accelerated trace that did not provide that evidence.

To regenerate scenarios for another explicitly selected ACTIVE synthetic trip:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\generate_operational_replays.py --vehicle-id $demo.vehicle_id --trip-id $demo.trip_id --out-dir .\data\operational_replays
```

The generator verifies vehicle/trip selection and uses its stored route/settings. It refuses to invent an unexpected-stop scenario if the route has no corridor point outside all expected-stop geofences; select a suitable longer synthetic route. It never calls Google. Replaying never updates unrelated vehicles or resets trip state.

Browser: http://127.0.0.1:5173 -> Driver -> Route -> vehicle from manifest -> Morning Pickup. Expand Preliminary route / movement events thresholds. Run normal travel, sustained deviation and recovery; observe persisted ACTIVE then RECOVERED IDs. Expected waiting must show its suppression reason. Unexpected stop must be labelled operational. During GPS loss the status becomes unknown while prior episode history remains. The current stop/map still uses the trip's saved route, and road geometry is never inferred from map tiles. Prototype vehicle/role selection is not authentication.

API inspection:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/trips/$($demo.trip_id)/operational-events" | ConvertTo-Json -Depth 8
```

## Changed files

backend/models.py; migrations/versions/0012_operational_episodes.py; operational_geometry.py; operational_monitor.py; positions.py; trips.py; main.py; .env.example; generate_operational_replays.py; tests/test_operational_monitor.py.

frontend/src/services/api.ts; hooks/useVehiclePosition.ts; components/DriverStoredRoute.tsx, DriverTrip.tsx and DriverOperationalEvents.tsx.

data/operational_replays/ six generated CSVs and manifest.json; docs/stage9e_verification.json and this document. Existing routing/ML datasets and artifacts were not regenerated. No precision/recall, validated accuracy, real hardware verification or crash/safety diagnosis is claimed.

Focused real-time smoke check: the generated normal_travel.csv was replayed at speed 1 through the actual local ingestion API. All eight simulation samples advanced latest, zero episodes were produced, and subsequent silence returned GPS unknown without inferring a stop. Driver source/geometry/threshold rendering had no page errors; screenshot: docs/stage9e-driver.png. Other scenarios were exercised using controlled-clock PostgreSQL checks, not claimed as real-world journeys.
