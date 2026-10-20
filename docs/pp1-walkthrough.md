# PP1 walkthrough

1. Sign in as an administrator. Overview shows authorized saved-plan/trip availability. The five working navigation entries are Overview, Daily Plan, Live Fleet, Notifications, Settings; teammate entries are disabled.
2. Open Daily Plan. Confirm date (today in Asia/Colombo by default), vehicle and AM/PM counts. Review attendance and save only deliberate changes. Prepare routes using simulation or experimental synthetic-trained ML for a free demonstration. Google actions require explicit budgets.
3. Review school ETAs, service, total planned minutes, actual source and blockers. Publish each direction explicitly. Drafts are not driver instructions.
4. In a separate authorized Driver session select the same service date/direction and assigned vehicle. Compare published version and ordered stops. Create planned trip and Start trip remain separate. Do not start future-dated or expired trips.
5. For an eligible active trip, map/GPS/current stop use its fixed snapshot. Navigate to next stop opens external Google Maps for its confirmed pin. Opening it never advances the trip. After eligible arrival use Next stop (manual; no passenger confirmation). Final arrival has no next destination; End trip does not confirm passenger delivery.
6. Live Fleet shows GPS only for the matching active trip. No GPS is unknown, not stopped. Notifications separate event generation from channel delivery. Settings → Administrator tools exposes research/review/test controls only when opened.

At 390px, verify scrolling without header overlap, vehicle/date/departure, next stop and GPS freshness. External Maps can background Chrome; use a second navigation device for foreground research capture. Physical Android handoff is not established by browser automation.

## Isolated checks

In frontend, start a separate test Vite server if port 5187 is free:

```powershell
.\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5187
```

In another frontend terminal:

```powershell
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-authenticated-presentation.cjs
node scripts/verify-driver-navigation.cjs
node scripts/verify-daily-plan.cjs
node scripts/verify-workspace-usability.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

These UI scripts intercept responses; they do not mutate records or prove live permissions. Historical backend and field reports remain in the archive. The [archive index](archive/index.md) lists every moved file.

## Consolidation verification ? 20 October 2026

Fresh checks: 7 rollback-only backend authorization tests and 2 saved-snapshot navigation tests passed. Existing authentication report output was suppressed so historical/untracked reports were not overwritten. Intercepted UI checks passed for authenticated presentation (5 states), fleet/publication (9 fleet states plus publication), dated attendance/planning, observation review, driver boundary, durations (7 states), operational cleanup (9 states), ML disclosure and short adult research. TypeScript and production build passed; Vite retains the existing bundle-size warning.

Rendered desktop 1366px and phone 390px Administrator/Driver screens were inspected; additional navigation/duration checks cover 320px. External requests were intercepted, including tiles: screenshots establish layout/markers, not live provider availability. No paid requests, phone samples, retraining or new field evidence were produced.

The next-stop investigation found an advance-response discard (up to the 2-second polling delay) and insufficient current-stop binding of arrival events in the UI. Both are corrected; regression checks include immediate targeting, a stale prior-stop poll, wrong-stop arrival evidence, coordinate ordering, no link-triggered advancement and final-stop behavior. Android's actual external-app handoff is still unverified by these checks.

Read-only VAN_01 inspection found two PLANNED trips and zero ACTIVE trips. Navigation is intentionally unavailable until an authorized trip is ACTIVE and has a confirmed saved current stop. No trip was started/cancelled or bypassed. Completed historical trips remain preserved.

All 46 moved Markdown files are enumerated with old/new paths in archive/index.md. No frontend source/assets were deleted because runtime/reference tracing found no safely unused candidates. Backend/data/model files are unchanged. Existing untracked authentication reports and saferide-ui-update remain preserved. No commit was created.
