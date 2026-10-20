# Google traffic and road-display checkpoint — 2026-10-20

## Scope and actual live results

Explicit user-authorized local maintenance check with a hard whole-check budget of **8 HTTP requests**. Actual usage: **8**. No loops/retries beyond the existing bounded matrix chunks, no calls on page load, no database mutations, no new dated attendance, draft/publication or trip. Live results are sanitized in `docs/google-road-live-check.json`; no coordinates, encoded path, keys, credentials, image content or secret-containing URLs are recorded.

The current confirmed **2026-10-19** school attendance and confirmed locations were read for temporary in-memory solves. Provider departure timestamps were explicitly **2026-10-21 06:00 and 13:30 Asia/Colombo**. These are forecast test timestamps, not a claim that attendance is confirmed for 21 October. No production date was silently changed. Historical routes and all adult evidence remain untouched.

| Phase | Actual result | HTTP requests |
|---|---|---:|
| Two-school traffic matrix | Both directed school pairs returned; Google success, no errors | 1 |
| Temporary AM solve | Feasible, eight participants, Google-only estimates, no fallback or mixed matrix | 4 |
| Temporary PM solve | Feasible, seven participants, Google-only estimates, no fallback or mixed matrix | 1 |
| Controlled adapter failure | Feasible AM using loaded XGBoost `synthetic-xgb-v1-26c03624ed36a729`; labelled ml_prediction, not Google | 0 |
| Controlled failure + separate missing-model instance | Unavailable, no route and no fabricated prediction | 0 |
| Ordered AM road geometry | Available; saved input order unchanged, optimizeWaypointOrder=false | 1 |
| Google Static Maps image | Success, valid PNG signature, 150,999 bytes | 1 |

Missing-model testing used a separate predictor instance. The real model was not unloaded, changed or retrained. Failure injection was local to test provider objects, not persisted in planning records or application configuration. The subsequent live geometry/image calls succeeded. No post-injection live matrix retry was made.

Partial matrices, timeouts, quotas, unsupported departure errors and unreachable pairs were verified with mocked transports; these were not observed failures in the real calls above. Unreachable pairs stay unavailable rather than being made reachable by ML. Partial availability can yield mixed source matrices, with per-leg fallback labels. Missing ML uses only the declared policy (ML-only becomes unavailable; explicit ML-then-baseline may use the synthetic baseline).

## Missing pieces completed

- Daily Plan accepts an opt-in **Request ordered Google road geometry within the selected plan budget** checkbox. Default is false; recommendation searches do not add geometry. Matrix chunks and optional geometry share the existing 0–8 request cap. Saved live_http_requests now includes the geometry attempt, rather than only the earlier matrix count.
- For 11 distinct locations allow four matrix chunks plus one geometry request if wanted. A smaller budget may produce available traffic but unavailable geometry; it never silently increases the budget.
- Google road images require **Load Google road map (up to 1 image request)**. Page load, remount and polling no longer initiate a Static Maps image request. The image request has its own explicit one-image action and existing bounded backend cache/timeout; it is outside the route-generation budget and labelled as such.
- Existing authenticated map-image endpoint and provider-compatible Google Static Maps display are reused. Credentials stay backend-only; frontend receives an authorized image blob. Live GPS/confirmed-point popups remain in a separate panel. Google road geometry is not overlaid on OpenStreetMap.

## Four distinct capabilities

1. **Optimized order:** Python/OR-Tools saved stop sequence with grouped schools. Google geometry receives those ordered stops with waypoint optimization disabled; it does not replace the order or matrix durations.
2. **Road display:** ordered Google road polyline displayed on a Google map with supplied attribution retained. It is a planned display, not a moving turn-by-turn navigator. When unavailable, the Leaflet view says **Stop sequence — not a road route**.
3. **External navigation:** **Navigate to next stop** opens the existing Google Maps directions URL for one confirmed coordinate. SafeRide only advances through its authorized explicit Next stop action. Opening Maps may background Chrome; a second navigation device is recommended while the capture phone stays foregrounded.
4. **Embedded turn-by-turn:** not implemented; no SDK or maneuver-instruction engine was added.

The solver uses one departure-time traffic matrix snapshot for all arcs; it is not fully time-dependent. Forecast estimates are not measured observations or training labels. Existing provider-retention/licensing requirements still need deployment review; this checkpoint is not a blanket compliance/production-readiness claim and does not rewrite historical snapshots.

Official references checked: [Routes API policies](https://developers.google.com/maps/documentation/routes/policies), [Compute Route Matrix](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix), [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started). Google Maps attribution is retained; no real Google polyline/image was stored in this report.

## Exact administrator browser actions

1. Restart the existing FastAPI process to load the new optional field; do not start another process on occupied port 8000. From backend: ` .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`. Keep the existing Vite HTTPS origin/proxy. No migration or account change is needed.
2. Log in as administrator → **Daily Plan** → select an unexecuted **Service date** with future departure times. Explicitly record that date's test attendance and review locations; do not copy yesterday's attendance implicitly or modify completed research trips.
3. Choose **Estimate provider → Google traffic estimate (may incur charges)**. Set AM departure 06:00 and PM departure 13:30 only when those exact timestamps are future. Unsupported/past dates are reported, never silently shifted. Existing school deadlines remain unchanged.
4. In **Administrator live traffic verification**, turn **Controlled adapter failure TEST** OFF. Choose **Declared fallback → None** for an unambiguous Google-only check. Set **HTTP budget per selected plan** to 5 for AM with geometry. Check **Request ordered Google road geometry within the selected plan budget**. Click **Validate AM override** once. This saves one new draft, not a publication or trip.
5. Inspect requested versus actual source, estimate timestamp, selected departure, mixed sources, HTTP requests and fallback reasons. A feasible Google estimate must say google_live / Google Maps traffic-aware estimate; ML is not Google success.
6. Generate PM separately with **Generate PM plan**, using a chosen small budget. The observed PM test needed one matrix request; geometry may need one additional request. Actual chunks depend on current distinct locations, so inspect consumption rather than assuming a constant cost.
7. If geometry is available and Static Maps configured, click **Load Google road map (up to 1 image request)** once. This is a separate potentially billable display action. Do not obscure/crop supplied Google attribution. Otherwise retain the explicitly labelled stop-sequence display.
8. To demonstrate fallback without another matrix call, choose **Loaded ML only**, enable **Controlled adapter failure TEST**, set matrix budget zero, and generate one selected draft. Inspect TEST label, ml_prediction, model version and forced failure reason. Turn TEST OFF afterward; normal live generation requires an explicit nonzero budget again. Do not remove model artifacts to imitate missing ML; automated tests use a separate instance.
9. Review and explicitly publish only when appropriate. Driver retrieves that saved published route version, never solves on GET. Its **Navigate to next stop** preserves the saved order; opening the link is not arrival or advancement. Active trips retain their fixed versions regardless of later drafts.

## Checks and limits

Passed: 25 backend tests (12 traffic-provider, four endpoint/opt-in, two saved-navigation and seven authorization regressions); intercepted Daily Plan, road-display and 320/390px Driver navigation scripts. Road-display checks verify no automatic image request, one explicit authorized fetch, mobile blob-image rendering and no extra fetch on page reload. Browser images are synthetic intercepted fixtures; the separate real HTTP check above verifies Google PNG retrieval, not a physical-phone visual/navigation handoff. TypeScript and frontend build pass with the existing nonfatal main-bundle-size warning. Read-only post-check evidence remains 225 stationary samples, 90 moving samples and two moving-observation revisions, with both trips COMPLETED.

No live retry is needed to reproduce automated checks:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_endpoints.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_saved_navigation.py -v
Set-Location ..\frontend
# Use the existing frontend origin; intercepted scripts make no Google calls.
$env:SAFERIDE_UI_TEST_URL='https://YOUR_CURRENT_WIFI_IP:5173'
node scripts/verify-daily-plan.cjs
node scripts/verify-road-display.cjs
node scripts/verify-driver-navigation.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
npx tsc --noEmit
npm run build
```

Do not execute the older `verify_malabe_live.py` casually: it deliberately saves new versions and issues paid calls when explicitly enabled. It was not used in this read-only live solve check. The default state remains no live calls until an authorized explicit action. This checkpoint does not establish moving-GPS accuracy, model real-world accuracy or fleet-scale performance.
