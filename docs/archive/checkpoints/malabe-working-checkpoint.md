# Malabe working checkpoint — 18 October 2026

Branch: `feature/routing-pp1-clean`. Local checkpoint only; no push.

## Scenario verified

Read-only PostgreSQL inspection confirmed the following current records for
service date **2026-10-19**, timezone **Asia/Colombo**:

- External vehicle VAN_01 (`MALABE_PP1_VAN_01`), usable capacity 20.
- SCH_A: Horizon College International. SCH_B: Boys' Model College.
- Confirmed attendance: AM 8, PM 7; TEST_03 AM=yes, PM=no.
- Morning: feasible, version 16, published,
  `ROUTE_9e9e39bf94dd4939b5043bf4dbc92488`.
- Afternoon: feasible, version 17, draft,
  `ROUTE_24111e0f80b247de9ffe65b7cf6c6d1b`.

These IDs and versions describe the inspection instant, not permanent latest
values. Database contents are not included in the commit. The user reports
successful manual Steps 1–7, including dated attendance and route version updates.
Automated rollback tests independently cover dated regeneration and immutable
snapshots. They do not repeat the user's live UI mutations.

`malabe-initial-plan.json` and `malabe-checkpoint-verification.json` are historical
initial-setup evidence, when locations were unconfirmed. They are not the current
operational state. The former remains the intentionally blocked UI test fixture.

## Checks rerun for this checkpoint

- Landmark/attendance/grouped routing: 9 passed, rollback-only PostgreSQL tests.
- Authorization/device/object scope: 7 passed, rollback-only tests.
- Existing dual-route solver: 8 passed.
- Traffic provider and ML fallback: 9 passed, external transport mocked.
- Google endpoint selection: 3 passed, external transport mocked.
- Daily Plan intercepted browser checks: 4 passed; no real mutations.
- TypeScript no-emit check and `npm run build`: passed (Vite 5.4.21).

Run from `backend` in Windows PowerShell:

```powershell
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dual_route_solver.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_endpoints.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
```

From `frontend`, with the existing development server running:

```powershell
node scripts/verify-daily-plan.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

## Commit scope and exclusions

Includes the isolated scenario, provisional import contract, grouped solver,
dated attendance/snapshot/publication orchestration, shared pickup outcomes,
Daily Plan UI/tests and their previously uncommitted authentication and shared
operations dependencies. Authentication, object scoping, tracking models and
imported UI components are required to load the current application. Their
inclusion does not establish physical-phone verification.

Unrelated replay-generator edits, local configuration edits, older audit reports
and auxiliary verification scripts remain outside this checkpoint. Existing
uncommitted work is preserved. No database migration, paid API call, dataset
regeneration or model training was performed during verification.

Git ignore checks cover `.env`, virtual environments, `node_modules`, build output,
private-data directories, private datasets and private keys. No ignored files were
already tracked. Credential-pattern scanning found no matches in tracked/index
content; this is a focused check, not a guarantee against every secret format.

The scenario uses landmark test locations, demonstration assignments and test
attendance. No physical GPS ingestion or measured real-world ML accuracy is
claimed. Provider tests use simulation/mocked transport; they do not verify live
Google service access. Hasara's actual integration remains unconnected.
