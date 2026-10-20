# Driver saved-duration summary — 2026-10-19

## Cause established before changes

Read-only inspection of `RouteVersion.result`, stored `RouteStop` rows and `serialize_version` found saved totals present and mapped under the correct field names. The frontend header gated all four totals behind `current`, which additionally requires `execution_status === 'pre_trip'`, current roster/freshness and a non-past date. This discarded valid saved estimates on historical/completed/pinned trip snapshots. `/routes/published` can also legitimately return no published planning route while returning a saved trip; the header previously ignored the trip snapshot.

The fix displays authorized saved values, independently of whether the plan is currently eligible to start another trip. Start/publication/freshness rules are unchanged. No API, database, stored route, completed trip or active manifest was rewritten or regenerated.

## Shared display and accounting

`PlannedRouteDurations` is reused by Admin Daily Plan, Driver summary and fixed-trip itinerary. All values have explicit seconds (`s`). Null, missing, invalid and negative values are Unknown, never substituted with constants or reconstructed totals. Genuine zero waiting displays `0 s`. Incomplete snapshots have a short explanation.

The summary identifies route ID, version, direction, date and context. An ACTIVE trip matching the selected direction/date takes precedence and is labelled fixed active trip plan. Otherwise the published selection is shown, with a matching stored trip as fallback when no planning route is available. An active trip of another direction/date remains separately visible in the lifecycle panel; its durations are not substituted for the selected plan. Failed route retrieval clears summary values. Saved durations are planned provider estimates, not actual elapsed trip time.

Total is driving + planned service + planned waiting, from saved departure through final-stop service completion. AM includes 600 seconds at the final school and has no depot-return leg. PM includes the final depot journey; recorded depot service is zero. School service is once per grouped visit: AM 600 seconds, PM 900 seconds. Operational pickup windows overlap the planned PM boarding service; 900 seconds is not added a second time. Duration accounting is collapsed by default.

Inspected actual saved VAN_01 snapshots (planning estimates, not measured travel times):

| Snapshot | Driving s | Service s | Waiting s | Total s | Endpoint |
| --- | ---: | ---: | ---: | ---: | --- |
| AM v39, `ROUTE_14dd3b2c6fbc4ec5a2136f94115a0209` | 1067 | 2160 | 0 | 3227 | Final school; terminal service 600 s |
| PM v28, `ROUTE_596c9a9ad8ce4aee8f6a0928ed0c7073` | 1187 | 2640 | 0 | 3827 | Depot; last driving leg 209 s, terminal service 0 s |

Stored stop sums match those totals. Group services are `[600,600]` AM and `[900,900]` PM. These are the inspected snapshots, not a promise that future route versions retain the same estimates.

## Mobile layout

The old tall non-scrolling route header and fixed `100vh - 4rem` driver wrapper did not account for the authenticated header/disclaimer. The real Driver workspace now uses a bounded dynamic viewport with flex sizing; the compact route header/footer do not shrink, and summaries/tracking/trip/GPS content scroll in the remaining main area. Route and refresh diagnostics are collapsed. The existing design/colors and unrelated demonstrations are retained.

## Checks actually run

- `tsc --noEmit`: passed.
- `npm run build`: passed, Vite 5.4.21, 1739 modules.
- Future-dated rollback API test: 1 passed. AM/PM Admin/Driver IDs, versions, totals, zero waiting, terminal service and pinned ACTIVE AM versus selected PM were verified.
- Pure nonzero-cost accounting tests: 2 passed. AM no hidden depot cost and terminal service included; PM return included, grouped services exactly 900 each, no doubled window.
- Browser intercepted UI: 7 scenarios passed at 320x568 and 390x844, zero mutations/page errors. Completed AM fallback, ACTIVE PM pinned version, legacy missing fields, historical saved plan, other-direction trip, no route, backend error. Layout bounds/horizontal overflow checked and mobile screenshot visually inspected. These are synthetic UI fixtures, not a newly authenticated physical-phone run.
- Whitespace and Python compilation checks passed.

The older full `test_landmark_daily.py` database suite was attempted: eight fixed-2026-10-19 generation cases hit the legitimate 409 completed-execution guard now that the physical-phone AM trip exists. The guard was not disabled and the old trip was not modified. The new API test uses 2099-10-21 within a rollback transaction to avoid that conflict. The older broad suite is not claimed as passing on this database. TestClient also reports its existing Starlette/httpx deprecation warning.

## Exact focused Windows checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_driver_duration_snapshot.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
$env:PYTHONPATH='tests'
.\.venv\Scripts\python.exe -m unittest test_landmark_daily.OpenEndCostTests -v
Remove-Item Env:PYTHONPATH

Set-Location ..\frontend
npx tsc --noEmit
npm run build
```

Browser regression script needs the existing Vite server. In a separate terminal, use `npm run dev` only if it is not already running. Set the actual origin (including HTTPS if configured):

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_UI_TEST_URL='http://localhost:5173'
node scripts/verify-driver-durations.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
```

This checkpoint used a temporary loopback Vite server on port 5187; existing port 5173/phone configuration was untouched. The UI script intercepts API calls and blocks nonlocal external requests; it does not log in to actual accounts or mutate records.

## Browser verification with saved data

1. Administrator → **Daily Plan** → **Service date** `2026-10-19`. Inspect AM and PM **Saved planned durations**, route ID and version. Do not generate or publish merely to test this display.
2. In a separate tab log in as the driver assigned to VAN_01, Workspace **Authenticated operations**. Use **Authorized vehicle**, **Service date (Asia/Colombo)** `2026-10-19`, **Morning Pickup**, **Refresh route**. The authenticated Driver already opens Stored route plan; synthetic Driver dashboard uses **Route** to open it.
3. Check **Saved planned durations**. AM's completed fixed trip can supply its saved estimates even without a current published pre-trip route. For the inspected AM v39, expect 1067 s / 2160 s / 0 s / 3227 s. The context must identify the completed trip rather than imply a new current plan.
4. Select **Afternoon Drop-off**, then **Refresh route**. Compare the displayed route ID/version with Admin's published PM version. If it is still v28, expect 1187 s / 2640 s / 0 s / 3827 s. If the plan is draft/unpublished, the API correctly withholds it; no mock totals are substituted. A matching saved trip may still provide its fixed plan, labelled accordingly.
5. Expand **Duration accounting** to inspect terminal service and endpoint policy. Expand **Published route details and diagnostics** for publication/provider/freshness information.
6. Inspect **Persistent trip lifecycle → Fixed trip route**. If an active trip uses a different version from the current published plan, compare its separate **Fixed trip itinerary and estimates** with Admin's same saved version, not the latest draft.
7. On a narrow phone viewport scroll to **Vehicle position**, **Persistent trip lifecycle** and tracking controls. Header/footer should not obscure them. No trip action, GPS sharing, enrollment or replay is needed for this check.

## Files changed for this task

Frontend: `components/PlannedRouteDurations.tsx` (new), `DriverStoredRoute.tsx`, `DriverTrip.tsx`, `pages/AuthenticatedApp.tsx`, `pages/DailyPlan.tsx`, `services/api.ts`, `scripts/verify-driver-durations.cjs` (new).

Backend tests only: `tests/test_landmark_daily.py`, `tests/test_driver_duration_snapshot.py` (new). Documentation: this file. No backend application logic/configuration, migrations, credentials, datasets or ML artifacts changed.
