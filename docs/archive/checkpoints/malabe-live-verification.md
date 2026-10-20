# Malabe live traffic and fallback checkpoint

Live verification performed 18 October 2026 for service date 19 October 2026,
Asia/Colombo. Whole-run budget 9 HTTP requests; **5 actually made**, including
one bounded correction/recheck of the two-school smoke assertion. No keys,
credential URLs or participant coordinates are included in the report.

The current administrator-edited roster is **AM 6 / PM 7**, not the initial
8/7 seed. No attendance was reset. AM verification used explicit 06:00 departure;
PM used 13:30. Both future departure timestamps were accepted by Google. This
does not establish arbitrary forecast-date support or measured traffic accuracy.

| Check | Actual result | Saved version |
|---|---|---|
| Two-school Google matrix | Both directed cross-school pairs returned successfully | Sanitized report |
| AM, Google only, no fallback | Feasible; Google source for 8 driven legs; no mixed matrix | AM 27 |
| PM, Google only, no fallback | Feasible; Google source for 9 driven legs; no mixed matrix | PM 19 |
| Controlled Google adapter failure, ML policy | Feasible; ML prediction on all 8 driven legs; zero external requests | AM 28 |
| Same failure with isolated missing-model instance | Unavailable; no predictions, no model version, zero external requests | AM 29 |
| Injection off, normal operation | Feasible; Google on all 8 driven legs, no fallback | AM 30 |

Loaded ML version: `synthetic-xgb-v1-26c03624ed36a729`. Training is synthetic;
live Google estimates are not measured observations or training labels.

The latest saved plans are **AM 30 and PM 19, both draft**. Review before
publication; the command did not start/alter trips or publish automatically.
Five saved versions were re-read to verify persisted metadata. Exact IDs,
timestamps, school service times, source counts and errors are in
[`malabe-live-verification.json`](../../malabe-live-verification.json).

The original smoke assertion expected diagonal entries. Google returned the
two required cross-school entries and no pair errors; the assertion was too
strict. The corrected assertion checks both cross-pairs. One actual bounded
repeat succeeded; the report preserves the initial assertion and recheck.

## Implementation and limits

Existing Google Routes/XGBoost providers are reused. The Daily Plan API exposes
`live_http_budget` (0–8, default zero), `fallback_policy` (`none`, `ml`,
`ml_then_baseline`) and `force_live_failure`. Existing real-administrator-only
authorization protects these actions; there is no new public test endpoint.
Each request budget caps actual transport calls including matrix chunks. Cache
hits do not consume HTTP requests. Existing adapter timeouts, total matrix time
budget, bounded cache and provider/display restrictions remain in place.

Metadata includes requested and actual source, planned departure, estimate
timestamp, fallback policy/reasons, mixed matrix flag, per-leg sources, failure
codes, request count/budget, synthetic model version when used and test flag.
Unusable matrices now retain that metadata in failed saved plans. Missing costs
do not get zero travel time. Unreachable Google pairs remain rejected. Past
departures are rejected locally; unsupported departure HTTP errors are sanitized
without changing the requested date. Partial failures/timeouts follow the
declared policy, with mixed matrices labelled mixed, or return unavailable.

Local-provider recomputation remains available. A budgeted Google verification
becomes stale after relevant input changes and requires a fresh explicit Admin
request; its budget/test injection is not silently replayed by attendance edits.
Active/completed execution guards remain unchanged.

This is a **departure-time matrix snapshot**, not a fully time-dependent solver.
The existing map components and attribution are unchanged. This verification
does not request extra road geometry or Static Maps; Daily Plan retains its stop
sequence label without road geometry. It does not reverify the separate road-map
integration or physical GPS.

## Exact Admin browser steps

Restart FastAPI to load the updated code (Ctrl+C in its existing terminal):

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Use the one existing Vite server at http://localhost:5173. If stopped:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

1. Administrator login → **Authenticated operations** → **Daily Plan**.
2. Select **2026-10-19**; inspect the current attendance and pin confirmations.
3. Select **Google traffic estimate**. Set AM departure **06:00**, PM **13:30**.
4. Under **Administrator live traffic verification**, enter an HTTP budget of
   **4 per selected plan**; choose fallback **None** and keep test injection off.
   Four chunks can be needed for 11 unique locations; the current smaller AM
   roster required one. These actions can incur Google charges.
5. Click **Validate AM override**, then **Generate PM plan**, one at a time.
   Inspect feasibility, requested/actual sources, timestamp, budget consumption,
   school times, mixed flag and saved versions. No fallback counts as live success.
6. Choose **Loaded ML only**, set HTTP budget **0**, and enable **Controlled
   adapter failure TEST**. Click **Validate AM override**. Confirm ML source,
   model version and forced-failure reason, with zero external matrix requests.
   Recommendation search is disabled while injection is enabled.
7. Turn injection **off**, restore budget **4**, optionally select fallback
   **None**, and validate AM again. Inspect a new Google-backed version.
8. Review publication separately; test versions are not published automatically.

These UI controls were checked with intercepted requests. The actual live and
persistence verification above used an explicitly authorized local maintenance
execution, not a browser login session.

## Optional local DB-administrator maintenance command

This command uses existing private backend DB configuration, like migration/seed
tools. It is not an HTTP authentication bypass and must stay on the trusted
development machine. It intentionally saves new versions and can incur charges;
do not run it merely to read the existing report.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe verify_malabe_live.py --allow-live --request-budget 9 --service-date 2026-10-19 --am-departure 21600 --pm-departure 48600 --report ..\docs\malabe-live-verification.json
```

The missing-model phase uses a separate predictor instance pointing at a
deliberately absent bundle; it never deletes/unloads the real model or retrains.
Failure injection is recorded, and the command restores non-injected AM
generation in `finally`. If normal generation itself fails, inspect the saved
status; the command cannot promise restoration despite provider outage.

## Focused checks (no paid calls)

Results: **39 distinct backend checks passed** (11 traffic provider, 3 Google
endpoint selection, 8 departure recommendation, 10 rollback landmark/attendance,
7 rollback authorization). Seven intercepted Daily Plan UI checks passed with
no page errors. TypeScript no-emit check, production build and Git whitespace
check passed. These checks do not represent additional live Google calls.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_endpoints.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_departure_recommendation.py -v
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
Set-Location ..\frontend
node scripts/verify-daily-plan.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

Transport failures, unsupported dates and partial matrices are controlled/mocked
test evidence. Only the specifically reported Google requests were live.
