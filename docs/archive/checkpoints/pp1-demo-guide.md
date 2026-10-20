# PP1 five-minute demo

## Start locally (two PowerShell windows)

Backend:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

Open `http://localhost:5173`. Check `http://127.0.0.1:8000/health` and `http://localhost:5173/api/health` if localhost refuses connection. PostgreSQL must be running and backend/.env configured locally. Do not run duplicate servers on occupied ports. No migration needed for this audit: database is at `0012_operational_episodes`. No Google call is needed.

## Prepared synthetic records

Vehicle **PP1_DEMO_0c1effd6_VAN_A**, capacity 2, six assigned students across two schools. Companion vehicle **PP1_DEMO_0c1effd6_VAN_B**, six students. Schools **PP1_DEMO_0c1effd6_SCHOOL_A** and **PP1_DEMO_0c1effd6_SCHOOL_B**. Students **PP1_DEMO_0c1effd6_STUDENT_01** through **12**, confirmed manual synthetic home coordinates. These are isolated new audit records, not real children. No one was reassigned to fit capacity.

Actual browser run: morning version 3 / `ROUTE_d24d86fa116d4b99bc240a51ff8c43bb`; afternoon version 2 / `ROUTE_2c5bb211ed78452d88c4c03aa7fde88e`, 14 actions each including depots. Versions change when generating again. The prior saved ML morning/afternoon version 1 had driving estimates 2,631 / 2,319 seconds; these were predictions, not measured journey times. The browser subsequently generated simulation versions; use each currently displayed source label rather than those prior numbers.

## Timed browser walkthrough

1. **0:00?0:45 ? Persistent roster.** Choose Administrator ? Students. Find the PP1 synthetic students above; show school, assigned vehicle and confirmed home coordinates. Explain that edits save through FastAPI/PostgreSQL and trigger pre-trip morning/afternoon planning. Keep real records untouched.
2. **0:45?1:45 ? Independent plans.** Administrator ? Routes; select **PP1_DEMO_0c1effd6_VAN_A** using `Route vehicle`. Select Morning Pickup, today's Service date, departure 06:00, Duration provider simulation, Traffic scenario Normal simulation; click Generate route. Show ordered pickup/delivery actions, onboard capacity, ID/version and separate driving/service/waiting/total values. Switch Afternoon Drop-off, use 12:30, generate independently; show school waiting and destinations. The line is ?Stop sequence ? not a road route?.
3. **1:45?2:45 ? Driver synchronization.** Open a second tab, choose Driver ? Route. Under prototype access select the same `Driver test vehicle` and direction. Compare route ID/version and actions with Admin. Keep Driver visible; regenerate Morning in Admin, then return to Driver and wait up to 15 seconds or click Refresh route. Verify the new version; Driver does not optimize on reads.
4. **2:45?3:30 ? Actual inference and honest fallback.** In Admin select Duration provider ML, generate and show `ml_prediction`, model version and synthetic-training warning. To demonstrate live failure, select Google, FIRST check **Force live adapter failure (local demonstration; makes no external call)**, choose fallback ML only, then generate. Show fallback reason and ML source. Never click Google generation without the forced-failure checkbox during this demo. No positive savings are promised.
5. **3:30?4:15 ? Pinned trip.** In Driver refresh the selected plan. Select Simulation-only demo pickup mode if desired, create planned trip using the labelled manual prototype button, then Start trip. Refresh the page; show the same trip ID, saved route version, state and unfinished actions. Admin regeneration for that active direction must be blocked; it must not replace the trip snapshot. Do not end it as proof of delivery. This creates a trip for the synthetic vehicle only.
6. **4:15?5:00 ? Persistent exceptions and limitations.** In Admin ? Notifications show the existing Stage 9D in-app missed event below; in Parent notifications explicitly enter its student ID and show context. An unrelated picked-up/cancelled ID has no matching missed event. Explain production pickup windows are 15 minutes, demo mode is explicit, backend expiry runs without a browser, and operational alerts from stop-sequence geometry are approximate. Show the verification report rather than waiting 15 minutes live.

## Existing notification demonstration records

- Student recipient: `S9D_9f7336fb_P0`
- Notification: `NOTICE_156f96db6410414bafa8942c22eafe0b`, trip `TRIP_a8b7fdb316b440e49e862f21ccbe2a9a`, vehicle `S9D_9f7336fb_V`
- Picked-up control: `S9D_9f7336fb_P2`; cancelled control: `S9D_9f7336fb_P1`

Select only these synthetic recipients. In-app event creation is not SMS/push delivery. Parent/role selection is prototype filtering, not real authenticated authorization. Reading may mark the test event read; refresh preserves it.

## Optional terminal GPS replay (outside the five-minute core)

The most recent test suite left active synthetic replay vehicle `S9E_22abe42a_V`, trip `TRIP_6ad6b273e03b4cdabf976c43c083f390`. Use only this explicit pair, not a real vehicle. To use a different newly created demo trip, copy its actual IDs and generate a matching fixture first.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$demoVehicle = 'S9E_22abe42a_V'
$demoTrip = 'TRIP_6ad6b273e03b4cdabf976c43c083f390'
.\.venv\Scripts\python.exe generate_operational_replays.py --vehicle-id $demoVehicle --trip-id $demoTrip --out-dir ..\data\pp1_replays
.\.venv\Scripts\python.exe replay_positions.py --vehicle-id $demoVehicle --trip-id $demoTrip --fixture ..\data\pp1_replays\normal_travel.csv --speed 1 --rebase-to-now
```

Press Enter to start, Ctrl+C to stop. In Driver select that vehicle and direction, observe the marker, GPS source/timestamp and later stale state. Normal replay takes about 14 seconds; repeated runs get new sample IDs. Synthetic movement follows stored sequence geometry, not a driven road trace. Speed 1 preserves dwell thresholds. Available additional CSVs: sustained_deviation, recovery, expected_waiting, unexpected_stop, gps_loss. GPS loss is a deliberate timestamp gap, never a stopped-vehicle assertion. Independent scenarios may share episode history; use the test suite for controlled exact assertions.

## Repeatable checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
Set-Location ..\frontend
node .\node_modules\typescript\bin\tsc --noEmit --incremental false
npm run build
node .\scripts\verify-pp1.cjs
```

The browser check uses the prepared PP1 vehicle and generates simulation plans. Run it before creating an active trip for that vehicle. Database checks retain fresh synthetic fixtures and update stage evidence/replay manifests, so obtain the newest replay IDs from `docs/stage9e_verification.json` after rerunning. Model training/data generation are unnecessary.

## 90-second supervisor update

?I have connected the routing component from the React interface through FastAPI to PostgreSQL. Morning and afternoon are solved independently for each vehicle's registered roster, including multiple schools, pickup-before-delivery, capacity and school time windows. Student changes regenerate both directions, and transfers update both vehicles. Driver reads the same saved route versions, while an active trip stays pinned to its own snapshot.

The audit passed 43 backend tests, the TypeScript check and frontend build. A real two-tab Admin/Driver test matched saved versions and stops. GPS ingestion, arrival dwell, persistent pickup deadlines, restart expiry and one-event missed notifications were tested with isolated synthetic fixtures.

XGBoost really supplies travel-time matrices. Its held-out synthetic test MAE is 28.01 seconds versus 57.09 for the historical baseline. This is a synthetic-data pipeline; real-world accuracy has not been established. Paid live Google traffic and road rendering were not verified. Authentication, real GPS-device trials, delivery confirmation and field validation remain. Deviation on stop-sequence geometry is explicitly approximate, and unrelated RFID/camera panels are still proposal demonstrations.?
