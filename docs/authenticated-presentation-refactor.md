# Authenticated routing presentation checkpoint — 20 October 2026

Frontend presentation/navigation only. The original demo dashboards, role selector
and synthetic context remain behind the existing authenticated simulation mode.
They were inspected for colours, cards, spacing and icons; their mock counts and
profiles were not copied into authenticated operations. Existing uncommitted
usability changes and unrelated authentication reports were preserved.

## Administrator navigation

- **Daily Plan** is the initial page. Its date comes from the existing
  `localPlanningDate()` helper (Asia/Colombo). Changing it performs a GET only;
  it neither copies attendance nor submits input changes.
- **Live Tracking** reuses OperationsFleet. There is no duplicate Dashboard /
  Live Fleet destination.
- **Alerts** reuses the authorized persistent inbox. In-app alert generation,
  external delivery status and read state stay distinct.
- **Setup** contains **Access** and **Students**, using existing components and
  server permissions. Adult phone approval is now **Setup → Access**.
- **Research & Testing** is separate: **Adult research**, **School test tools**,
  **Evaluation**, and the existing **Routes** inspection page.

Daily Plan has three anchored stages: **1. Review attendance**, **2. Prepare
routes**, **3. Review and publish**. Generation/override buttons are in preparation;
saved AM/PM versions, stop order, clocks, minute totals, actual source, fallback
and blockers remain in review. Raw route IDs and provider accounting are collapsed.
Unknown durations stay unknown; zero waiting is 0 min. Minute display rounds to
one decimal while saved seconds remain unchanged (terminal service accounting is
still available). No client recomputation of feasibility was introduced.

Everyday planning does not render JSON imports, manual boarding event forms,
forced-failure injection or evaluation panels. Use **Research & Testing → School
test tools** for the first three, **Evaluation** for model/observation review.
Google request budgets still default to zero. Explicit **Google request approval
and limits** and **Recommendation request budget** disclosures authorize bounded
requests; selecting Google or loading a page does not issue provider requests.
No billing/authorization checks were removed to simplify the UI.

## Driver order and behavior

Vehicle/date/direction context, publication and fixed-trip state/version stay
visible. **Change vehicle, date or direction** expands selectors; only authorized
backend vehicles are offered. A compact next-stop name and actual source appear
with the context. The existing trip component retains separate persisted actions:

1. No open trip/current feasible publication: **Create planned trip (manual
   prototype)**. Pickup policy settings are available in a disclosure; defaults
   and server validation are unchanged.
2. PLANNED: **Start trip (manual prototype)** is the primary action. Creation is
   not offered again while an open trip is present. Start is still subject to
   backend service date/time, freshness, publication and assignment checks.
3. ACTIVE: saved map, **Navigate to next stop**, confirmed-arrival **Next stop
   (manual; no passenger confirmation)**, and GPS sharing remain within the trip
   area. End trip is secondary during travel and emphasized at confirmed final
   arrival; explicit confirmation is still required.
4. COMPLETED/CANCELLED: **Fixed trip itinerary and estimates** remains accessible;
   navigation does not restart. Trip identity/history is available in a disclosure.

GPS status/enrollment stays beside trip controls. Revoked sessions, raw identifiers,
arrival diagnostics and operational histories are collapsed. Research-operator
capture controls are not offered to a mismatched driver; the existing server
operator authorization remains authoritative. External navigation is not embedded
turn-by-turn and opening Maps never advances a trip. Foreground-capture limitations
remain visible in the navigation area.

Driver GPS is now displayed only when all of these match: ACTIVE persisted trip,
position trip ID, selected vehicle ID, and no GPS/trip request error. Vehicle-wide
history returned for another/closed trip is suppressed from the marker, status and
navigation panel; unavailable is shown instead. This is a presentation filter,
not a change to stored GPS or evidence provenance. The active trip's saved route
remains independent of the latest selected planning direction/date.

## Verification

Eleven intercepted UI suites passed: authenticated presentation (new), driver boundary,
navigation, durations, Daily Plan, short research, workspace usability, operations
cleanup, ML evaluation, Google road display and phone-capture component. Tests were updated to navigate the
new disclosures/destinations, retaining their previous behavioral assertions.
The presentation suite covers five Admin/Driver states, matching AM/PM saved route/order,
today's local date, date changes without writes, source labels, cross-trip GPS
suppression, no page-load paid action and laptop/390px layout.

Seven existing isolated backend authorization checks passed, including anonymous,
parent-object scope, vehicle/trip forgery, protected exports, tracking expiry and
revocation. Fixture changes are rolled back; operational records are not edited.
TypeScript and production build passed. Vite's existing >500kB chunk warning and
Starlette's existing httpx deprecation warning remain.

Rendered synthetic Admin/Driver screenshots were inspected at 1366×900 and 390×844;
320px Driver layout is also covered by existing checks. Screenshots are under the
ignored `frontend/node_modules/.cache/presentation-*` paths, not evidence exports.
External map requests are intercepted in tests: blank tiles/error messages there
exercise graceful degradation, not live provider verification. No paid APIs,
retraining, seed, migration, physical GPS or actual mobile integration was performed.

## Exact manual walkthrough

Use the existing running backend and single Vite server; authenticate privately.

1. Admin login → **Daily Plan**. Confirm today's Colombo date. Choose the intended
   service date explicitly; inspect that date's unknown/confirmed attendance.
2. Stage 1: edit and **Save dated attendance** if an intentional change is needed.
   Stage 2: **Review stopping locations**; choose estimate provider and time.
   Use **Recommend AM departure**, **Validate AM override** or **Generate PM plan**.
   For no-cost testing use simulation/loaded ML. Paid Google requires explicit
   positive limits; no paid requests are required to verify this refactor.
3. Stage 3: review saved AM/PM version, source, timings, grouped stops and blockers;
   publish only a deliberately reviewed eligible plan using **Publish reviewed AM
   plan** / **Publish reviewed PM plan**. Do not publish or change evidence just to
   test appearance.
4. Driver in a separate browser profile → **Change vehicle, date or direction** →
   choose the same vehicle/date and **Morning Pickup** / **Afternoon Drop-off** →
   **Refresh route**. Compare publication/version/stop order with Admin.
5. Inspect existing trip actions and **Fixed trip itinerary and estimates**.
   Do not start future-dated trips. Actual capture still requires the authorized
   active trip and sender; research capture requires its separate operator.
6. Admin → **Live Tracking** for authorized positions; **Alerts** for generation
   versus delivery; **Setup → Access** for assignments/adult-test authorization.
7. Admin → **Research & Testing → Evaluation** for observation review/export or
   synthetic model metrics; **Adult research** for adult-only journey preparation;
   **School test tools** for provisional imports and controlled failure tests.

On Android Chrome use the already trusted HTTPS laptop origin and existing `/api`
proxy. Never phone localhost. At 390px confirm all five navigation destinations
are reachable, trip controls scroll without header/footer overlap, and unknown GPS
does not become a stopped marker. Use a second device for external navigation if
the tracking phone must keep Chrome foregrounded. Physical handoff is not verified
by desktop responsive tests.

## Reproduce checks (Windows PowerShell)

Separate frontend terminal for intercepted UI checks:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npx vite --host 127.0.0.1 --port 5187
```

Test terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-authenticated-presentation.cjs
node scripts/verify-driver-boundary.cjs
node scripts/verify-driver-navigation.cjs
node scripts/verify-driver-durations.cjs
node scripts/verify-daily-plan.cjs
node scripts/verify-short-research.cjs
node scripts/verify-workspace-usability.cjs
node scripts/verify-operations-cleanup.cjs
node scripts/verify-ml-evaluation.cjs
node scripts/verify-road-display.cjs
node scripts/verify-phone-capture.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
Set-Location ..\backend
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
```

No backend implementation files changed. The model, constraints, APIs, published
records, trip snapshots and physical/research evidence are preserved. Hasara's
app remains disconnected; the boundary remains API-ready.

The credentialed browser harness was updated for Setup / Access navigation but was
not rerun; authorization was verified by the seven isolated backend checks instead.
The phone-capture suite uses mocked geolocation/uploads, never actual-device evidence.
