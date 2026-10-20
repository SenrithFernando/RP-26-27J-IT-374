# Supplied UI update merge — 20 October 2026

Followed `saferide-ui-update/APPLY_WITH_CODEX.md` and `manifest.json`.
`git apply --check` failed against newer local files, so the patch was not forced.
Baseline/updated/current three-way comparisons merged clean hunks and identified
six files for manual reconciliation. No Git reset, clean, checkout, commit or push.

Merged the package's 12 target files, including new `SaveNotice` and `uiFormat`
helpers. `AuthenticatedApp.tsx` was not edited: its newer sidebar and separate
Research & Testing workspace are byte-for-byte unchanged from pre-merge. The
three-stage Daily Plan, Colombo-today default, research-only forms, primary Driver
actions and trip-scoped GPS filtering were retained. The Daily Plan and Driver
pages were not replaced with the older supplied snapshots.

## Visible changes

- Live Tracking uses the supplied map/filters/stat cards and compact GPS/plan
  summary. Active trips show their fixed route's direction; switching directions
  is disabled while that route is displayed. No previous journey is presented as
  live when there is no active trip. Trip/vehicle binding is checked in the UI
  before forwarding a GPS sample; stale/poor samples have no Live Tracking marker.
- Shared GPS cards show freshness, local last update, rounded accuracy and km/h.
  Missing speed remains Unavailable. Simulation/poor-accuracy labels remain,
  and raw IDs/coordinates/receipt-time dumps are removed from that card.
- Successful publication uses the green **Route published** status with **Your
  review has been saved. The published plan is available to the assigned driver.**
  It appears only after a successful HTTP response. Date changes clear old notices;
  rejected publication does not show success. Saved-input/planning-blocked notices
  remain amber. Daily AM/PM counts use the supplied readable summary cards.
- Saved durations use shared minutes/hours formatting, version/date and a planned
  time label. Missing stays Unavailable. The Duration accounting disclosure is
  removed; saved seconds, constraints and snapshot contents are unchanged.
- Redundant technical/raw JSON, publication diagnostics, refresh diagnostics,
  import-audit, stored-threshold and historical-comparison panels are removed as
  requested. Trip route and unconfirmed passenger actions are named sections.
  Per-vehicle/direction outcomes and errors remain. School schedule editors remain
  reachable in Research & Testing → Routes as a named section.
- Research GPS boundary selectors, interval/review editors, model evaluation,
  provisional imports, manual evidence and controlled-failure forms remain in
  their current research workspace. Paid opt-in budgets remain explicit and zero
  by default; loading a page never generates a plan or requests a Google image.

## Actual verification

Passed TypeScript no-emit, production build and `git diff --check`. Vite retains
its existing >500kB bundle warning. No dependencies or package manifests changed.

Twelve intercepted browser suites passed: the new merge suite, authenticated
presentation, Daily Plan, operations cleanup, driver boundary, navigation,
durations, workspace usability, short research, ML evaluation, road display and
phone capture. Assertions were updated for intentional label/card/section changes,
retaining checks of persisted state, unknown values and original request payloads.

The new merge suite covers planned preview/no historical GPS, active fixed PM
route and trip-scoped GPS, stale timestamps, poor accuracy, missing speed,
cross-trip sample suppression, missing route, route error, empty directory,
1366px/390px overflow, no writes/provider requests on page load, delayed publication
acknowledgement, rejected publication, and amber input-saved/planning-blocked state.
Publication responses and all data are intercepted synthetic fixtures; this is
not a new publication in the operational database or a real-provider verification.

Desktop and 390px screenshots of Live Tracking and publication success were
rendered and visually inspected. Map tiles are intentionally blocked in the test
browser; markers/sequence, attribution and tile-error fallback remain visible.
Screenshots are in ignored `frontend/node_modules/.cache/ui-update-*` files.

All 124 protected backend/configuration/model files and the authenticated shell
matched their pre-merge SHA-256 values. No backend process/API mutation, migration,
seed, training, real login, actual GPS ingestion or paid request was performed.
Database evidence was not accessed or changed. The existing uncommitted work,
unrelated authentication reports and supplied update package remain intact.

## Repeat locally

In a separate PowerShell terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
.\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5187
```

In the frontend check terminal:

```powershell
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-ui-update-merge.cjs
node scripts/verify-authenticated-presentation.cjs
node scripts/verify-daily-plan.cjs
node scripts/verify-operations-cleanup.cjs
node scripts/verify-driver-boundary.cjs
node scripts/verify-driver-navigation.cjs
node scripts/verify-driver-durations.cjs
node scripts/verify-workspace-usability.cjs
node scripts/verify-short-research.cjs
node scripts/verify-ml-evaluation.cjs
node scripts/verify-road-display.cjs
node scripts/verify-phone-capture.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

For manual inspection use the existing authenticated application: **Live Tracking**
for active/planned map states, **Daily Plan** for counts and review/publication,
and **Research & Testing** for retained research forms. Inspect completed Driver
trips through **Trip route**. Do not publish/start/change real records solely to
test appearance. Physical phone navigation, Hasara integration and live Google
behavior were not reverified by this merge.
