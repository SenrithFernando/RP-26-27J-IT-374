# Deterministic monitoring replay checkpoint — 2026-10-19

## Scope and actual evidence

Existing `positions`, `operational_geometry`, `operational_monitor`, trip lifecycle, CSV generator, terminal replay and Driver display were reused. No migration, provider call, threshold tuning, model training, account reassignment or persistent test-trip creation was performed. Existing uncommitted work was preserved.

Seven tests in `tests/test_monitoring_checkpoint.py` passed (final run: 17.773 seconds). Six tests exercise PostgreSQL through an outer transaction with savepoints, then roll back; one checks the terminal replay payload with mocked HTTP. All six generated CSV scenarios are consumed with controlled recorded/receipt times inside one of these tests. Generated CSVs use temporary directories and do not overwrite existing replay fixtures. Every sample is simulation, every test trip is registered with existing synthetic-trip provenance. No phone ingestion endpoint is used.

Two existing geometry/math tests passed; the old persistent operational integration test was deliberately skipped. It commits fixtures, leaves an ACTIVE trip and overwrites its historical report; it is not the rollback-only command below. Frontend `npm run build` passed (Vite 5.4.21, 1738 modules). TestClient emitted an existing httpx/Starlette deprecation warning; checks passed.

| Requirement | Verified result |
| --- | --- |
| On-route movement | No operational episode |
| Brief off-route noise | No sustained deviation episode |
| Sustained deviation | One simulation episode after configured persistence; repeated samples do not create another active episode |
| Return to route | One inside sample does not recover; sustained return records RECOVERED |
| Expected pickup/school/depot dwell | No unexpected-stop episode at home pickup or school/depot locations; suppression reason exposed |
| Prolonged remote stationary cluster | One unexpected-stop episode |
| GPS gap/loss | Unknown/stale; no inferred stop or recovery; candidate evidence restarts after a gap |
| Missing reported speed | Remains null; movement inferred separately from ordered coordinates, not null-to-zero conversion |
| Poor accuracy | Sample persisted with poor quality, detection ignored and sustained candidate interrupted |
| Duplicate/out-of-order | Duplicate ignored; late sample cannot advance latest or monitoring timestamp |
| Separate vehicles | Off-route vehicle gets an episode; the moving on-route vehicle does not share its state |
| Authorized simulation API | Anonymous denied; authenticated simulation accepted/idempotent; actual_device source denied on this endpoint |
| CSV replay payload | Accuracy preserved, speed null preserved, source simulation, simulation ingestion path |

The six generated scenarios are `normal_travel`, `sustained_deviation`, `recovery`, `expected_waiting`, `unexpected_stop`, `gps_loss`. Their detector results matched the intended no-event/ACTIVE/RECOVERED behavior under controlled clocks. This is not a physical moving-vehicle run or a browser-observed wall-clock replay this checkpoint.

## Small fix

`replay_positions.py` previously discarded optional CSV `accuracy_m`. It now validates and forwards it; absent accuracy remains null. The new regression test verifies the payload. Detector thresholds/algorithms were not changed.

## Settings and geometry limits

Current configured thresholds: road deviation 100 m, stop-sequence deviation 300 m, deviation persistence 20 s, recovery corridor 60% of selected threshold for 10 s; stop movement <=0.5 m/s within a 15 m cluster for 60 s; stop recovery displacement >30 m; expected-dwell radius 75 m; gap limit 10 s; freshness 20 s; at least three observations. Existing poor-accuracy threshold is read from position configuration, not replaced by a test threshold. Active trips use their stored settings.

Synthetic replay routes have **approximate_stop_sequence** geometry. No road geometry was fabricated. Existing tests cover provider-polyline provenance validation, invalid/mismatched geometry fallback and metric distances; no live Google request was made. Real road bends may leave the straight stop corridor. Road-based field behavior remains unverified.

Expected dwell is conservatively suppressed near any saved stop, including future stops; this can suppress real anomalies near those locations. Unknown accuracy is permitted but labelled unknown. Coordinate-derived low movement with null device speed is possible after repeated observations; null speed alone is never evidence of stopping. Traffic queues away from saved stops may be flagged. No field precision/recall or safety diagnosis is claimed.

Operational alerts are existing persisted `OperationalEpisode` records displayed in Driver, not missed-pickup notifications. No parent notification/SMS/push delivery is implemented or claimed for them. Existing missed-pickup notification infrastructure was left intact.

## Repeat the safe checks — Windows PowerShell

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_MONITORING_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_monitoring_checkpoint.py -v
Remove-Item Env:SAFERIDE_RUN_MONITORING_TESTS
# Do not opt into the older persistent fixture test.
Remove-Item Env:SAFERIDE_RUN_DB_TESTS -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_operational_monitor.py -v
Set-Location ..\frontend
npm run build
```

The tests use PostgreSQL but leave no replay fixtures to browse afterward. Read-only post-test check found zero `REPLAY_CHECK_%` vehicles.

## Optional real-time terminal replay and UI

An existing historical isolated simulation fixture was inspected read-only: vehicle `S9E_22abe42a_V`, trip `TRIP_6ad6b273e03b4cdabf976c43c083f390`, ACTIVE, service date **2026-10-16**. It is not VAN_01 or the phone trip. It currently has **zero assigned drivers**. No assignment was changed. Its past date means it should not be presented as today's operational plan; use it only as a clearly historical simulation fixture. A fresh UI demonstration needs an explicitly selected separate simulated vehicle/trip and authorized driver; do not substitute VAN_01.

For any deliberately selected ACTIVE simulation trip, use the existing commands below. Both scripts prompt privately for login using the authenticated synthetic-demo workspace. Use an authorized account; no credential goes in arguments. Each replay persists simulation samples/events for that selected vehicle/trip. These commands are instructions, not actions performed during this checkpoint.

Backend terminal (loopback only):

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Separate replay terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK
$replayVehicle = Read-Host 'Explicit isolated simulated vehicle ID (not VAN_01)'
$replayTrip = Read-Host 'Its ACTIVE simulation trip ID (not the physical-phone trip)'
.\backend\.venv\Scripts\python.exe .\backend\generate_operational_replays.py --vehicle-id $replayVehicle --trip-id $replayTrip --out-dir .\data\operational_replays_checkpoint
$scenario = 'normal_travel'
.\backend\.venv\Scripts\python.exe .\backend\replay_positions.py --vehicle-id $replayVehicle --trip-id $replayTrip --fixture ".\data\operational_replays_checkpoint\$scenario.csv" --speed 1 --rebase-to-now
```

Press Enter to begin and Ctrl+C to stop. Keep speed 1: compressed replay timestamps do not demonstrate the original sustained durations. Change `$scenario` to one of the six names above. Episode history remains between scenarios: use recovery deliberately or independent trips. The tool always sends simulation source to `/routing/vehicles/{vehicle_id}/positions`, never `/tracking/positions`. Do not enroll a phone sender for replay.

UI labels inspected in source (not a new browser verification):

1. Log in with Workspace **Authenticated synthetic demo** using an assigned test driver. If absent from the vehicle list, do not bypass authorization.
2. An administrator can explicitly manage this under **Access → Accounts and access → Assign vehicle or student access**. Select the intended test driver, preserve existing selected relationships, add only the isolated simulation vehicle, then **Save assignments and revoke old sessions**. This replaces the selected relationship set and revokes sessions; re-login afterward. No such change was made here.
3. Driver → **Route** → **Authorized vehicle** → selected simulation vehicle → **Service date (Asia/Colombo)** matching the route → **Morning Pickup** → **Refresh route**.
4. Under **Persistent trip lifecycle**, inspect the fixed route/trip ID. A current feasible plan with no open trip offers **Create planned trip (manual prototype)**, then **Start trip (manual prototype)**. Start requires today's service date; do not create duplicates or restart completed trips.
5. Scroll to **Preliminary route / movement events**, expand **Stored provisional thresholds**. Inspect source simulation, geometry quality, ACTIVE/RECOVERED episode IDs/times and GPS unknown after silence. Polling reads stored state; it does not generate routes.

## Physical-phone evidence preserved

Post-test read-only database query: completed phone trip remains COMPLETED; phone session remains revoked; **225 actual-device samples, 225 unique sample IDs**. No phone sample, source, trip or session was modified. Existing physical checkpoint files were not changed. This count/status check does not claim a fresh complete row-by-row evidence digest.

Still needed: moving-vehicle adult field tests against actual road geometry, independent on/off-route ground truth, expected congestion/dwell behavior, accuracy-dependent false positives, device/network gaps, foreground/background limitations and multi-device reliability. Synthetic replay is not evidence for those results or measured travel-time/ML accuracy.
