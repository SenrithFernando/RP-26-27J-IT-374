# Automatic pre-trip update checkpoint — 2026-10-20

Reuses existing durable RoutingEvent processing, provisional daily import, dated input fingerprints, route versions, publication and trip execution guards. No migration, new orchestration system, paid provider call, real attendance mutation or research/GPS edit was required.

## Changes

- All automatic Malabe regeneration with saved Google provider settings now defers to an explicit administrator request. Previously the deferral condition could miss legacy fixed-departure Google settings without a live budget. Such a plan becomes stale; it is not silently labelled live/current.
- Generic registration/update/transfer into the isolated Malabe vehicle rejects participants outside its explicit scenario manifest. Previously a generic new registration could save successfully but never enter the closed dated scenario roster. Known scenario participants remain editable/transferable; reactivation is supported. Adding entirely new external participants requires extending the reviewed scenario contract; it is not silently inferred from active registrations.
- Daily Plan explicitly explains that replacements require administrator review/publication and warns when the saved plan is not current. Corrected corrupted separator/arrow display text found by the intercepted UI test.
- Added four rollback-only checkpoint tests and made the existing fixed-date scenario fixture's planning date deterministic. All database fixtures use session-private PostgreSQL temporary tables. Production clocks, start rules and execution guards are unchanged.

## Verified backend results

Four new tests and fourteen existing landmark/attendance tests passed, plus three isolated adult-research regressions.

Eight intercepted Daily Plan UI checks and the intercepted adult-research preparation/reuse check passed without page errors. TypeScript and the frontend production build passed; the existing nonfatal main-bundle size warning remains. Early failed UI runs exposed the corrupted separators; the final fresh-page run passed after correction.

| Requirement | Evidence |
|---|---|
| Correct dated AM update | Removing TEST_03 AM attendance creates a new seven-person AM version; a separate dated AM plan retains its ID. |
| PM independence | TEST_03 already has PM=false, so that AM change leaves PM version unchanged. A separate PM-only change leaves AM version unchanged. AM changes can legitimately affect PM review/policy where morning evidence or afternoon-only policy is relevant. |
| Assignment additions/removals | Deactivate/reactivate a known scenario assignment: AM/PM counts 8/7 → 7/6 → 8/7. General test-vehicle add/removal regenerates both directions and serves the exact assigned roster. |
| Transfer | Known scenario participant transfers to an isolated second vehicle. Both vehicle IDs occur in results, with AM/PM plans for each. Old vehicle counts become 7/6; receiving vehicle serves the transferred participant exactly once in each direction. |
| Idempotency | Duplicate provisional event and duplicate transfer request key create no new route versions. |
| Recommendation invalidation | Changed AM inputs produce a different saved recommendation fingerprint; the superseded route is not current. Previous route/input snapshots remain immutable. |
| Failed generation | Capacity reduced to seven persists despite eight confirmed AM participants. AM returns infeasible with publication blocked and full attendance evidence retained; no student is dropped to manufacture feasibility. |
| Active manifests | Existing tests verify active route ID/input snapshot and passenger manifest stay pinned, direct generation returns 409 and changed planning state requires later pre-trip review. |
| Route constraints | Existing independent AM/PM tests and solver post-validation enforce exact coverage/load, all AM homes before grouped school deliveries, both PM school pickups before homes, no AM depot return and one boarding-service period per school. |
| Publication | A changed feasible plan is a new draft with reset review. The previously published version cannot remain a current published driver itinerary. Explicit **Publish reviewed AM plan** / **Publish reviewed PM plan** is required. Deferred/failing plans are stale or infeasible with blockers. |

The general legacy routing endpoints do not invent a school publication audit. The explicit dated publication contract described here belongs to the Malabe Daily Plan workflow.

Read-only post-test preservation: stationary adult trip remains COMPLETED with 225 samples; moving adult trip remains COMPLETED with 90 samples and two observation revisions. These fixtures never enter the operational schema. No real account reassignment or registration occurred.

## Exact Windows checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_PRETRIP_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_pretrip_checkpoint.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
$env:SAFERIDE_RUN_SHORT_RESEARCH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_short_research_route.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_PRETRIP_TESTS
Remove-Item Env:SAFERIDE_RUN_SHORT_RESEARCH_TESTS
Set-Location ..\frontend
npx tsc --noEmit
npm run build
```

Intercepted browser checks (no operational mutations) use the existing UI scripts with `SAFERIDE_UI_TEST_URL` set to the running frontend origin. The agent used a temporary loopback server on port 5187; it does not replace the phone HTTPS server.

## Manual UI verification

These clicks deliberately save test inputs/versions. Use an unexecuted date and synthetic test records only; do not mutate the completed 2026-10-19 trips or transfer a real account's vehicle assignment.

1. Restart the existing backend to load the validation/deferral fixes (Ctrl+C in its terminal, then ` .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000` from backend). Keep the existing frontend server, proxy and private database configuration.
2. Log in as administrator → **Daily Plan** → **Service date**. On the intended unexecuted date explicitly record AM/PM attendance, enter **Recorded reason**, then **Save dated attendance**. Unknown attendance on another date remains unknown.
3. Choose **Estimate provider → Deterministic simulation**; keep Google budgets zero. Use **Recommend AM departure** and **Generate PM plan** to establish a baseline. Record route IDs/versions, rosters and publication states. This is simulation, not measured traffic.
4. For a morning-only participant with PM=no (TEST_03 initially), change **AM attendance** yes→no, retaining PM=no, and click **Save dated attendance**. Check AM count/version/recommendation changes, PM version stays the same, replacement AM is draft, and a different service date is untouched.
5. Change only another participant's PM yes→no and save. AM version should stay the same; PM count/version changes. Restore attendance explicitly if desired. Do not mark unknown morning evidence as no-show merely to complete a demo.
6. In **Students**, locate a synthetic scenario participant. **Deactivate → Deactivate student** then **Reactivate → Reactivate student** exercises assignment removal/add-back. Return to Daily Plan and refresh the page after each successful save; check both affected dated plans and review status. The separate account/driver assignment is not changed.
7. For a transfer demonstration use only an existing separate synthetic test vehicle: **Students → Transfer → Vehicle → Save transfer**. Inspect both old and destination vehicle plans. Do not create or reassign vehicles/accounts merely to imitate the automated fixture. If no suitable test vehicle exists, use the isolated automated test instead.
8. Review the replacement stops/times and enter a reason before **Publish reviewed AM plan** or **Publish reviewed PM plan**. PM may require explicit unresolved-evidence review; unknown is not no-show. Driver receives the replacement only after publication. An active Driver trip continues showing its **Fixed trip itinerary and estimates** from its pinned version.

Capacity failure, duplicate event IDs and legacy Google deferral are exercised safely by automated fixtures; no failure/clock manipulation or paid request is necessary in the operational UI. Results establish small-scenario correctness checks, not fleet-scale throughput or field accuracy targets.
