# Malabe morning departure recommendations

## Follow-up audit and completion

The current solver/search already enforced the required dated roster, capacity 20 scenario, all pickups before grouped school deliveries, optimizer-selected orders, 06:00 floor, both preferred 07:05 targets and hard 07:15 deadlines. Each grouped visit has 600 seconds of service (finishing by 07:25 at the latest under the hard arrival constraint); each home pickup has 120 seconds. Terminal school service is counted once and the virtual sink has no depot-return duration or distance. No backend operational rule needed changing.

Completed missing frontend details: the recommendation request now forwards the selected declared fallback policy; results explicitly separate **Recommended departure** from **Selected saved departure**. Overrides say that no recommendation was calculated. Failed/incomplete results no longer imply a latest feasible minute was established. Both schools' service arrival/departure, duration breakdown, provider, estimate timestamp and collapsed assumptions continue to use the saved backend result.

New controlled-cost boundary regression: with four synthetic participants, six driven arcs of 570 seconds, the latest hard-feasible departure is exactly 06:00, labelled reduced_buffer. Driving is 3,420 s, service 1,680 s, waiting 0 s, total 5,100 s; the last school arrives 07:15 and finishes service 07:25. At 571 seconds per arc no feasible minute is found. These are synthetic solver checks, not measured Malabe durations.

Current checks: nine departure tests, fourteen landmark/attendance tests and three isolated adult-research tests pass; eight intercepted Daily Plan UI checks pass with no page errors, including declared fallback forwarding and unavailable-selection display. TypeScript and the frontend build pass; Vite retains the nonfatal main-bundle size warning. Database fixture isolation was corrected: tests use session-private PostgreSQL temporary tables under an outer rollback, rather than inheriting real completed VAN_01 plans. No database CREATE privilege, migration or history edits are required. Research tests use a test-only planning clock to avoid midnight rollover; the computer clock and production date/start rules are untouched.

Read-only evidence preservation check: stationary adult trip remains COMPLETED with 225 samples; moving adult trip remains COMPLETED with 90 samples and two observation revisions. No paid requests, operational generation, real attendance edits, retraining or evidence writes were performed by this audit.

For a manual planning demonstration, choose an unexecuted service date with explicitly recorded attendance. Historical 2026-10-19 school execution guards may correctly return 409; do not reset completed trips to demonstrate recommendations. Keep Google budget zero and choose Deterministic simulation for a no-paid-call test. **Recommend AM departure** saves a draft; **AM departure → Validate AM override** saves a separately revalidated draft. Compare both school times and the explicit recommended/selected fields. A recommendation superseded by an override is retained on its original immutable route version, not silently carried forward as a new recommendation.

Implemented on the existing authenticated Daily Plan pipeline. No migration,
model training, account reassignment or active-trip modification is required.

## Search and provenance

`POST /daily-plan/generate` accepts `departure_mode: "recommend"` for morning.
The saved route version includes `departure_recommendation`, its assumptions,
estimate timestamp, input fingerprint, per-school service arrival/departure,
provider metadata and search budgets. The selected departure is stored as the
route's actual departure and in request settings. GET remains read-only.

The search is exhaustive **at one-minute resolution**, descending from 07:05
to 06:00 with both school arrival bounds set to 07:05. It does not use a
monotonicity/FIFO assumption or calculate backwards from only the final school.
If that pass finds no solution, it searches 07:15 to 06:00 against the hard
07:15 bounds. A found hard-only solution is explicitly `reduced_buffer`.
No additional ten-minute buffer is subtracted. Both schools retain 600 seconds
of group service, home pickups 120 seconds, capacity/load and order constraints.
The last school's service is included in total duration; no depot return exists.

This is the latest feasible **minute found by bounded heuristic solves**, not a
proof of the latest feasible second or globally optimal stop order. Each solve
has a 250 ms limit and stops at its first feasible solution. A failed solve is
not a mathematical infeasibility certificate. Completed unsuccessful scans say
`no_feasible_departure_found`; exhaustion says `search_incomplete`, with no
recommended departure. Neither may be published as a feasible plan.

Budgets: at most 142 solves, 76 distinct candidate matrices for local providers,
30 seconds checked between operations; the last bounded solve may add up to
250 ms. Preferred/hard passes reuse identical-departure matrices. Each distinct
candidate is estimated at its own departure time. ML features use that time;
simulation/historical baseline can legitimately return unchanged durations.
All arc costs are precomputed outside OR-Tools callbacks. The selected matrix
still applies its departure-time snapshot to the entire route: **not a fully
time-dependent solver**. Total duration includes driving, service and waiting.

Google search defaults to **zero**, requiring an explicit budget 1–4. That cap
applies both to candidate matrix invocations and actual HTTP requests across
all adapter chunks; cache hits do not consume HTTP requests. A matrix with 11
unique locations can require four HTTP chunks. No geometry request is added by
recommendation mode. Timeout/budget/missing-key failures preserve existing
explicit ML fallback/source labels; fallback is not Google success. A small
Google budget will commonly yield an incomplete search rather than a latest
recommendation. No paid Google request was made in checkpoint verification.

## Changes and invalidation

The existing dated fingerprint makes old recommendations stale after relevant
attendance, assignment or location changes. A locally estimated recommendation
is recomputed through existing backend orchestration after the first explicit
recommendation has been generated. Historical route/input snapshots remain
immutable. Google recommendation inputs become stale and require another
explicit budgeted administrator request; attendance edits do not initiate a
paid recommendation search. The UI labels stale results.

`departure_mode: "override"` re-solves the administrator's supplied time using
a fresh estimate for that time. The override is not a recommendation, and an
invalid result cannot be published. Ordinary legacy `fixed` generation remains
compatible. Authentication, date-specific attendance and execution guards are
unchanged; an active/completed manifest cannot be replaced by this search.

## Windows startup and browser verification

Restart the existing backend terminal with Ctrl+C, then:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep one frontend server running; do not start a second on port 5173:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

1. Open http://localhost:5173, log in as your administrator in **Authenticated
   operations**, and select **Daily Plan**.
2. Select 2026-10-19 (or a date with explicitly saved attendance). Confirm VAN_01
   capacity 20, SCH_A Horizon/SCH_B Boys' Model, initial AM 8 / PM 7, TEST_03 PM=no.
   Confirmed pins are required; no coordinates are invented.
3. Choose **Deterministic simulation** initially. Click **Recommend AM departure**.
   Read the saved route version, recommended departure, preferred/hard status,
   provider badge, estimate timestamp, totals and both schools' arrival/service
   departure times. Expand assumptions to inspect limits.
4. Enter an administrator time in **AM departure**, then click **Validate AM
   override**. Try 07:15: the pickup/service constraints should prevent a feasible
   route; inspect the saved failure. Then recommend again to restore a feasible
   pre-trip version when possible. This saves real planning versions deliberately.
5. To test dated recomputation, change one AM attendance decision, enter a reason
   and **Save dated attendance**. Compare the new version/fingerprint and actual
   recommendation. Restore attendance explicitly afterward. Do not expect a
   forced positive improvement. PM eligibility/policy review remains separate.
6. Google is optional and potentially billable: recommendation is disabled until
   an explicit nonzero HTTP budget is entered. Local verification does not require
   this. Never count ML fallback as a successful live test.
7. An active-trip guard returns 409 rather than replacing its pinned version.
   Do not start a real trip merely to test this; automated tests use rollback data.

## Checks and actual controlled outcomes

Checkpoint results: 42 distinct backend checks passed (8 recommendation,
10 landmark/attendance, 7 authorization, 9 traffic-provider, 8 legacy solver).
The recommendation persistence test was additionally rerun after adding active
morning-trip protection assertions and passed. Six intercepted Daily Plan UI
checks passed with no page errors. TypeScript and the frontend build passed.
Database tests use rollback-only synthetic data; UI mutations are intercepted.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_departure_recommendation.py -v
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dual_route_solver.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
```

From `frontend` with its development server running:

```powershell
node scripts/verify-daily-plan.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

Controlled costs are synthetic test evidence, not Malabe travel measurements:
four participants and zero driving yield latest preferred 06:47, 1,680 seconds
service/total. Directed uniform 500-second test arcs yield reduced-buffer 06:07;
700-second arcs yield no feasible minute found. Rollback scenario tests with
eight colocated synthetic pickups yield 06:39; removing one AM participant
recomputes 06:41 and preserves the old snapshot. These values must not be shown
as real-world Malabe recommendations. Actual landmark recommendations depend
on the current confirmed pins and selected estimates.

Physical GPS, live Google and measured real-world ML accuracy are not verified
by these checks. Existing synthetic model artifacts are unchanged.
