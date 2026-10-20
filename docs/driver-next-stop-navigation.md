# Driver next-stop navigation — 2026-10-19

## Implementation audit

| Capability | Actual implementation |
| --- | --- |
| Saved optimized order | Existing ordered immutable route/trip stops and authorized manual advancement |
| In-app map | Leaflet/OpenStreetMap locations and explicitly labelled stop-sequence line; conditional stored Google geometry/Static Maps display where available |
| PM v28 road geometry | Unavailable; remains unchanged, no geometry request made |
| Maneuver instructions | Not implemented in SafeRide |
| External Google Maps navigation | Added for one backend-selected current stop |
| Embedded turn-by-turn / native SDK | Not implemented or claimed |

The new link uses Google's documented universal Maps URL:
`https://www.google.com/maps/dir/?api=1&destination=LATITUDE%2CLONGITUDE&travelmode=driving&dir_action=navigate`.
Reference: https://developers.google.com/maps/documentation/urls/get-started

Only one destination is sent. No waypoints, optimize/reorder flag, credentials, route roster or fleet request is sent. Origin is omitted so Google Maps can use its device's location. Google may open navigation or a directions preview depending on platform, app and location availability. This is external navigation, not embedded instructions. Google's chosen road path between stops may differ from SafeRide's estimate; the saved stop order and provider metadata are not changed.

## Snapshot confirmation and targeting

Route and arrival serialization now expose `location_confirmed`, derived read-only from the immutable route input snapshot. The saved location ID and exact saved coordinates must match a confirmed school/home/depot location in that snapshot. Current registrations are not substituted. Old snapshots missing this proof fail closed; no coordinates are guessed and no snapshot is rewritten.

Navigation is shown only for an ACTIVE trip. The arrival response must match its trip ID, fixed route ID, stop sequence, event ID and coordinates. Both saved route and arrival stop must carry confirmation. Nonfinite/out-of-range coordinates, backend errors, wrong snapshots and missing confirmation disable navigation. The current stop is never inferred by nearest GPS point or taken from the latest planning route.

The active trip starts with its first monitored saved stop. Already being at the first school is not permission to skip it: receive actual arrival, then use the existing authorized advancement. After arrival the link for that reached stop is hidden and the UI instructs the driver to use **Next stop (manual; no passenger confirmation)**. At the final stop it permits navigation while approaching, then shows **Final saved stop reached** with an instruction to close deliberately; no wraparound or extra Next stop is added. PLANNED/COMPLETED/CANCELLED trips have no navigation control.

Clicking/copying/opening/returning from Maps does not POST, advance a stop, mark arrival, board a passenger or complete delivery. Backend arrival and advancement authorization remain unchanged. Existing visibility polling refreshes server evidence when the page returns.

## Today's two-device research usage

1. Restart FastAPI so the new read-only confirmation field is available; refresh the existing Vite page. No migration is needed for navigation.
2. Complete the existing adult authorization, research collection preparation and ACTIVE-trip/phone enrollment steps. Do not reuse the completed stationary trip. Select VAN_01, the intended service date and **Afternoon Drop-off**, then **Refresh route**.
3. In **Persistent trip lifecycle → Next stop**, verify the target name, sequence and **fixed route version**. For the intended v28 itinerary, the initial monitored stop is Boys' Model, then Horizon, then the remaining saved stops.
4. On the navigation device, use **Navigate to next stop** to open Google Maps. If the destination appears as a preview, use Google Maps' own available navigation UI; SafeRide does not embed or control those screens.
5. **Keep the tracking phone's Chrome foregrounded with the screen awake.** Opening Maps on that same phone can background Chrome and interrupt capture. Background continuity is not promised. The panel visibly recommends a second navigation device for this research journey.
6. **Copy link for navigation device** copies only the one-destination URL. Transfer/paste it on your second device using your chosen method; no SafeRide login/tracking token is in the link. No second-device login is needed merely to open that Google Maps link. Clipboard copying needs browser support/secure context; a visible message explains how to use the link menu if unavailable.
7. When physically at the stop, keep recording GPS and wait for confirmed arrival. If the tracking phone had been backgrounded, return to SafeRide, inspect sharing/GPS freshness and resume foreground capture. Gaps remain gaps; no observation is repaired or fabricated.
8. Click **Next stop (manual; no passenger confirmation)**. Confirm the displayed target changes to the next saved stop, then open/copy its new navigation link. Merely returning from Maps does not select the next destination.
9. At the depot, confirm actual arrival. The panel shows final-stop instructions. Use **Stop sharing**, then **End trip (manual prototype) → Confirm end trip**, and revoke the tracking session through existing controls. Unfinished passenger actions remain truthful; navigation confirms none of them.

Do not call a Google Maps arrival message a SafeRide GPS arrival or passenger confirmation. Do not interpret a background GPS gap as a stopped vehicle. External Google directions are estimates and are not measured training targets.

## Checks actually run

- Read-only inspection: PM route `ROUTE_596c9a9ad8ce4aee8f6a0928ed0c7073` v28 has 10/10 confirmed saved locations; road geometry remains unavailable.
- Two pure saved-confirmation tests passed: home, school, start/end depot; changed coordinates, unconfirmed and incomplete snapshots fail closed.
- Seven existing rollback authorization tests passed. A focused rerun additionally verified anonymous advancement 401, another driver's trip 403 and parent advancement 403.
- Intercepted browser test passed: latitude/longitude order (including negative and zero coordinates), one target/no waypoints, copy/open without advancement, explicit Next stop update, confirmation/error/snapshot mismatch rejection, final depot behavior, completed-trip hiding, return instruction and 320/390 px mobile layout. No page errors. The one advance was a mocked explicit user action. All nonlocal requests, including Google URLs and map tiles, were intercepted—no external navigation or paid geometry calls were made.
- `npx tsc --noEmit` and `npm run build` passed (Vite 5.4.21, 1741 modules). Existing TestClient/httpx deprecation warning remains.

Physical Android Maps app handoff, spoken guidance and GPS continuity while another app is foregrounded have **not** been verified. Use the second-device setup and perform that physical check yourself. No v28, trip, position or measured observation was modified for navigation testing.

## Exact Windows checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_saved_navigation.py -v
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
# Normal backend restart (stop its old process first):
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Separate terminal, existing frontend origin:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_UI_TEST_URL='http://localhost:5173'
node scripts/verify-driver-navigation.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
npx tsc --noEmit
npm run build
```

Use your existing HTTPS origin instead if configured. Do not start another Vite on occupied 5173. This checkpoint used a temporary loopback 5187 server and left phone HTTPS configuration untouched.

Changed: backend `route_service.py`, `arrivals.py`, `tests/test_saved_navigation.py`, `tests/test_access_control.py`; frontend `services/api.ts`, `components/DriverTrip.tsx`, new `components/DriverNavigation.tsx`, new `scripts/verify-driver-navigation.cjs`; this document. No SDK, new dependency, migration, paid provider call or native app was introduced.
