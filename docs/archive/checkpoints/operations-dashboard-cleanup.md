# Authenticated operations dashboard cleanup

The real workspace uses authorized backend responses. It does not render the
legacy AdminDashboard, LiveFleetMap, DriverDashboard or ParentDashboard component
demonstrations. Those remain behind Authenticated synthetic demo. The authenticated
header identifies the workspace, and unrelated cabin/camera/RFID/emergency features
are marked Not connected. Demo countdown effects stop outside the demo workspace;
context state remounts on account/workspace changes.

## Data contracts and limitations

- Admin Dashboard and Live Fleet reuse authorized vehicle listing, latest saved
  route/planning state, current trip, and latest vehicle position services. Only
  the selected vehicle is polled. No GET triggers generation.
- Latest planning route ID/version is separate from the active trip's pinned
  route ID/version. Historical/planned/completed trips are not called active.
- Simulation positions are labelled synthetic, and actual-device position is
  unavailable when only a simulation sample exists. Device samples are reported
  device input, not independent verification. Recorded/received timestamps use
  Asia/Colombo. Position age advances from the recorded timestamp using the
  browser clock; the server stale flag is never downgraded. Current speed is
  unavailable for stale samples. Missing GPS never implies stopped.
- Saved ETAs and driving/service/waiting/total durations are planning estimates.
  Google labels say traffic-aware estimate. XGBoost labels retain synthetic
  training provenance; neither is measured journey time. Fallback reasons remain
  visible. No live navigation ETA is connected.
- Driver uses the same position-status component. Arrival is displayed as a
  current-stop workflow only for ACTIVE trips. Persisted trip/window/anomaly
  history queries remain available separately for saved trips. Pickup remaining
  times still come from server windows.
- Parent retains the existing limited, linked-student summary/inbox permissions.
  Summary now includes registration input_source; live position, speed, route/trip
  information and countdowns are explicitly unavailable. No broader vehicle/GPS
  access was granted. This is a remaining product capability, not mocked data.
- Notifications show persistent trip, saved route ID/version, window, student,
  timestamps, source and read state. In-app creation is not SMS/push delivery.
- Backend/read/login failures clear unavailable data or show an explicit error.
  Read/login requests have a 12-second bound. Mutations allow 120 seconds; a
  timeout does not cancel server work or establish whether a save succeeded.
  Refresh before retrying a mutation.

No migrations or history rewrites are required. No existing records were deleted
or edited by this cleanup. Parent summary and notification response additions are
read-only; normal server startup retains its existing worker lifecycle.

## Verification

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_AUTH_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS

Set-Location ..\frontend
node scripts/verify-operations-cleanup.cjs
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
```

The browser script checks nine intercepted UI scenarios: Admin backend failure,
empty vehicles, no route/trip/GPS, saved planning versus pinned trip versions with
stale simulated GPS; Driver no trip/GPS and failure; Parent permitted synthetic
summary/empty inbox and failure; explicit demo-workspace separation. Responses are test fixtures, not real backend
observations. External requests are blocked; no paid calls or production sessions
are used. Backend security tests use isolated rollback-only fixtures and exercise
authorization plus the added parent provenance/notification version fields.

## Manual browser verification

1. Restart FastAPI for the additive response fields, then run the frontend:

   ```powershell
   Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
   .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
   # Separate terminal
   Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
   npm run dev
   ```

2. Open http://localhost:5173; sign in privately as admin.local, Authenticated
   operations. Inspect Dashboard and Live Fleet. Select an authorized vehicle and
   direction. Compare latest planning and saved trip IDs/versions. Existing
   historical records are labelled, not replaced or regenerated.
3. Select a vehicle with no position if available: position/speed/live ETA must
   be unavailable. With simulated GPS, check its synthetic label. With stale GPS,
   inspect recorded timestamps and historical-speed wording.
4. In Routes inspect saved provider badges/fallback reasons. No saved result must
   display unavailable values. Generation is a separate explicit user action.
5. Open Notifications: empty inbox is an empty state; existing events include
   route version. Do not change read state unless deliberately testing it.
6. Use separate browser profiles for driver.local and parent.local. Driver must
   see only assigned vehicles; Parent only linked students. Parent's disconnected
   live tracking fields are explicitly unavailable. Teammate features are Not
   connected in every operational role.
7. To simulate failure without stopping workers, use DevTools Network request
   blocking for `*/api/routing/*` and `*/api/routes/*`, then reload. Verify errors
   replace data, not demo students/speeds/ETAs. Remove blocking after checking.
8. Log out and choose Authenticated synthetic demo at login. Confirm the separate
   labelled demonstration workspace remains available. No authentication bypass
   was introduced.
