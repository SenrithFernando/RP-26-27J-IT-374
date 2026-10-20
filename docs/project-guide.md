# Project guide — independent reviewer setup

Inspected 20 October 2026 on `feature/routing-pp1-clean`, starting from commit `e6880d9`. These instructions provision the **reviewer's separate local database**. They do not restore the author's accounts, sessions, saved trips, reviewed pins, GPS samples or observations. Do not copy `.env`, browser authentication storage, certificates, virtual environments, `node_modules`, private exports or database backups from the author's laptop.

## First-run checklist

1. Obtain this branch/reviewed source and install the prerequisites below.
2. Create your own PostgreSQL login and `saferide_routing_review` database.
3. Install dependencies, copy the configuration example, and enter your own DB password locally.
4. Verify the destination, migrate, and run the insert-only synthetic seed.
5. Bootstrap locked local accounts; activate each through hidden password prompts.
6. Start FastAPI and Vite; log in at `http://localhost:5173/`.
7. For School Daily Plan, initialize Malabe separately and review its attendance/locations. No existing published plan is included.
8. Check ML availability; see the **known artifact line-ending blocker** below. Google and phone HTTPS are optional follow-ups.

## Prerequisites and supported baseline

The tested Windows stack is **64-bit CPython 3.14.2, Node 24.13.0, npm 11.6.2**, with Vite 5.4.21/React 18 from the lockfile. Use Python 3.14 and Node 24 to match this baseline. PostgreSQL 17 is the local project baseline; pgAdmin is the documented administration interface. PostGIS, Docker and a hosted database are not required.

The repository does not declare a complete Python/Node support matrix or pin every backend dependency. Vite's installed package accepts Node `^18.0.0 || >=20.0.0`, but that is not proof of project-wide support for every such version. Python 3.10/3.11 are unsuitable for the current ML requirements: [XGBoost 3.4.1 requires Python >=3.12](https://pypi.org/project/xgboost/3.4.1/); [scikit-learn 1.9.1 metadata](https://pypi.org/project/scikit-learn/1.9.1/) also identifies its supported interpreters. Other OS/interpreter combinations have not received a clean installation test here.

Locally loaded backend versions include FastAPI 0.143.1, Uvicorn 0.54.0, OR-Tools 9.15.6755, SQLAlchemy 2.0.54, psycopg 3.3.6, XGBoost 3.4.1, NumPy 2.5.4 and scikit-learn 1.9.1. `requirements.txt` contains ranges/unpinned entries, not a reproducible backend lockfile.

## 1. Obtain a separate source checkout

Use the repository URL supplied for the review; no remote publication is performed by this guide. If that branch/commit has not been shared, the reviewer cannot fetch it yet. In a directory where you want a new checkout:

```powershell
$repositoryUrl = Read-Host 'Reviewer repository URL, without embedded credentials'
git clone --config core.autocrlf=true --branch feature/routing-pp1-clean $repositoryUrl Safe_Ride_LK
Set-Location .\Safe_Ride_LK
$reviewRoot = (Get-Location).Path
git status --short
```

`core.autocrlf=true` is a **current ML bundle workaround**, not a general Git preference: the checksum metadata expects CRLF in three JSON artifacts. This checkout conversion was reproduced successfully in a temporary directory. A raw LF checkout or GitHub ZIP can load as **ML unavailable**. Do not normalize/re-save artifact JSON, edit checksums or retrain to hide this problem. The model portability limitation needs a separate canonical-artifact fix for an unrestricted cross-platform release. Simulation does not depend on the model.

If you already have a source archive, use a new review folder. Do not reset or overwrite an existing working tree to change line endings. Obtain the complete reviewed bundle/check-out if its model check fails.

## 2. Create the reviewer's PostgreSQL database

In pgAdmin, connect to **your own local PostgreSQL server** as its database administrator:

1. **Login/Group Roles → Create → Login/Group Role**: name `saferide_reviewer_app`.
2. **Definition**: enter a new password privately. **Privileges**: enable **Can login**; leave superuser, create roles, create databases, replication and bypass RLS disabled.
3. **Databases → Create → Database**: name `saferide_routing_review`, owner `saferide_reviewer_app`.
4. Open Query Tool on **saferide_routing_review**, as the database administrator, and execute:

```sql
GRANT CONNECT ON DATABASE saferide_routing_review TO saferide_reviewer_app;
GRANT USAGE, CREATE ON SCHEMA public TO saferide_reviewer_app;
```

The application login owns only this review database; running Alembic as it makes it owner of the created objects. Keep PostgreSQL bound to localhost and keep port 5432 private. Do not restore the author's database or point the review configuration at it.

## 3. Install from existing manifests

From the new checkout root, in PowerShell:

```powershell
py -3.14 --version
node --version
npm --version
py -3.14 -m venv backend\.venv
Set-Location .\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

For optional backend tests, install `requirements-dev.txt` instead; it includes the runtime requirements and httpx. No training or database commands run as part of these pip commands. Do not copy an existing virtual environment.

From the checkout's `frontend` directory:

```powershell
npm ci
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

Use `npm ci` with the committed `package-lock.json`; do not replace it with a newly resolved lockfile. npm/pip need package-registry access. The current environment's dependency check and frontend build pass; a fresh backend resolver check failed locally, as described under verification limits.

## 4. Configure the review database and migrate

From `backend`, create `.env` **only if absent**, then edit it privately:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad.exe .env
```

Use these nonsecret settings, enter your own `DB_PASSWORD`, and leave Google keys empty initially:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=saferide_routing_review
DB_USER=saferide_reviewer_app
DB_PASSWORD=
GEOCODING_PROVIDER=manual
GOOGLE_GEOCODING_API_KEY=
GOOGLE_ROUTES_API_KEY=
GOOGLE_STATIC_MAPS_API_KEY=
```

The blank password is an instruction to fill it privately, not a working password. `backend/.env.example` has empty secret values and useful nonsecret defaults; no credentials are supplied. Keep its remaining planning/arrival/window settings unless deliberately testing another policy. Scenario-specific Malabe service times override generic planning defaults.

`database.py` resolves `.env` next to itself, disables dotenv interpolation and uses `SQLAlchemy.URL.create`. Enter the actual password without URL-encoding it. For spaces, `#`, `$`, `%`, `@` or `:` use a single-quoted dotenv value; escape a literal quote as `\'` and backslash as `\\`. Do not build a connection URL yourself. Process `DB_*` variables take precedence over `.env`; inspect any conflicts privately, never dump the whole environment.

Before any migration/seed/account operation, verify the **review** destination without printing a connection string:

```powershell
.\.venv\Scripts\python.exe -c "from database import database_url; u=database_url(); assert u.database=='saferide_routing_review' and u.username=='saferide_reviewer_app' and u.host in ('localhost','127.0.0.1'); print('Reviewer database destination verified.')"
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Expected repository head: **0019_research_unknown_eta**. `upgrade head` changes the review schema; `heads` inspects migration files and `current` reads the configured DB. Migrations do not create web login passwords. Do not use downgrade/reset/reseed as a diagnostic.

## 5. Seed synthetic demonstration records and bootstrap accounts

From `backend`, after migration and destination verification:

```powershell
.\.venv\Scripts\python.exe seed_routing_demo.py
.\.venv\Scripts\python.exe seed_routing_demo.py
.\.venv\Scripts\python.exe manage_accounts.py prepare-local --vehicle-id S4_VAN_A --student-id S4_STUDENT_01
.\.venv\Scripts\python.exe manage_accounts.py activate-initial admin.local
.\.venv\Scripts\python.exe manage_accounts.py activate-initial driver.local
.\.venv\Scripts\python.exe manage_accounts.py activate-initial parent.local
```

These commands **write only to the configured review database**. `seed_routing_demo.py` inserts two schools, two vehicles and 12 synthetic students with fixed `S4_` IDs; both vehicles have students at both schools. Its capacity-two multi-school fixture is separate from Malabe's capacity-20 scenario. Reruns insert missing IDs without duplicating, overwriting or deleting existing records. They do not automatically generate saved routes or accounts.

`prepare-local` creates absent `admin.local`, `driver.local`, `parent.local` accounts **locked with no usable password**, assigning the driver to `S4_VAN_A` and parent to `S4_STUDENT_01`. Existing accounts/relationships are preserved. Each `activate-initial` requires an interactive terminal and two hidden password prompts (12–1024 characters); it refuses an initialized account. Choose your own distinct passwords; never put them in argv, `.env`, documentation or screenshots. These are new accounts in the review DB, not the author's credentials.

For an additional explicitly assigned synthetic driver, the existing alternative is:

```powershell
.\.venv\Scripts\python.exe manage_accounts.py create-test reviewer.driver --role driver --vehicle-id S4_VAN_B
```

It also uses hidden prompts and refuses an existing username. `cli_auth.py` is a hidden-prompt **demo-session helper for scripts**, not an administrator-creation command. Avoid `set-password` during first run: it resets an existing account and revokes sessions; `activate-initial` is the non-reset workflow.

Database login, application account, driver/vehicle assignment and tracking enrollment are distinct. The SQL login permits application persistence; web roles determine API access; a driver needs an assigned vehicle; phone uploads additionally need a scoped, revocable credential bound to an eligible active trip.

## 6. Start and use the application

In terminal A, from the review checkout's `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In terminal B, from its `frontend`:

```powershell
npm run dev
```

Open **http://localhost:5173/**. Workspace: **Authenticated operations**. Sign in as `admin.local` with the password you entered. In another browser profile/private window, use `driver.local`. Same-profile tabs share session storage only according to browser tab behavior; use separate profiles/windows to avoid confusing accounts. Neither user role nor vehicle permission is granted by a demo role selector.

Vite is loopback-only on port 5173 with `strictPort`; `/api` proxies to **http://127.0.0.1:8000**, stripping `/api`. Frontend requests use that same origin; no frontend database credentials or Google keys are needed. `npm run build` verifies assets; it is not a production deployment instruction.

Public `http://127.0.0.1:8000/` checks HTTP responsiveness, not DB correctness. Protected endpoints such as `/ml/status` and `/routing/vehicles` require a valid login; a direct anonymous 401 is expected. Use the authenticated UI rather than pasting bearer tokens into commands.

Startup loads ML once and starts planning-recovery/pickup-expiry workers. Those workers can update pending plans/windows in their configured database. Use a **single local backend process**, only against the review DB. Startup does not run migrations, seed accounts or issue fleet-wide Google calls on page load.

Administrator: **Overview, Daily Plan, Live Fleet, Notifications, Settings**. Unrelated teammate entries are disabled. Research/evaluation/editors remain at **Settings → Administrator tools**; the separate authenticated demo workspace retains synthetic proposal demonstrations.

## 7. Optional Malabe School Daily Plan setup

The synthetic `S4_` seed does not initialize the scenario-specific Daily Plan. From `backend`, this existing insert-only command initializes it separately, without geocoding or changing account assignments:

```powershell
.\.venv\Scripts\python.exe setup_malabe.py
```

It creates `MALABE_PP1_VAN_01` (external `VAN_01`, capacity 20), SCH_A Horizon and SCH_B Boys' Model, eight landmark participants and dated test attendance for **2026-10-19**: AM 8 / PM 7; TEST_03 is morning only. It preserves existing scenario records on repeat. It does **not** include the author's reviewed destination pins or published plans. School B's built-in public-landmark coordinate is explicitly user-supplied/pending confirmation; the other required pins remain unresolved.

1. In Admin → **Daily Plan**, choose a suitable service date. Dates other than the initial date have **unknown attendance**, not copied decisions. **Edit attendance** explicitly, record a reason, then **Save dated attendance**.
2. **Review locations**: use your own reviewed public landmark stopping pins. Preserve supplied addresses, confirm accessible stopping points, and **Save confirmed location**. Without keys use manual coordinates/pin correction. Do not import the author's student/home or physical-GPS records.
3. **Prepare routes**: select **Simulation** or **Experimental ML** only after the model check succeeds. **Recommend AM departure** or **Validate AM override**, then **Generate PM plan**. Review each card and **Open AM route / Open PM route** before **Publish reviewed AM/PM plan**. Resolve actual attendance/location/blocker messages; explicitly review unknown morning evidence for provisional PM publication.
4. In Admin → **Settings → Access → Manage account**, select `driver.local`. In **Authorized relationships**, explicitly select `MALABE_PP1_VAN_01` (and any other intended vehicle), then **Save assignments and revoke old sessions**. This replaces that account's assignment list and revokes its sessions. No CLI silently transfers the driver from S4 to Malabe. Log the driver in again.
5. Driver → **Choose route**: select the assigned vehicle, same date and AM/PM, then **Use selected route**. Compare the published version/itinerary with Admin. Retrieval does not solve a new route. **Prepare trip → Create planned trip** and **Start trip** remain separate writes; a trip is not needed just to inspect a published itinerary.

School rules and start-time restrictions remain enforced. An old/future-dated trip cannot be started just for review; if today's departure allowance has passed, inspect plans without starting, or use the existing separately reviewed adult-research workflow. Never alter the clock, relax school deadlines or manufacture boarding/GPS evidence.

## ML bundle: available, with a portability limitation

Git contains six JSON files: `backend/ml/artifacts/current.json` and the `baseline.json`, `metadata.json`, `metrics.json`, `model.json`, `preprocessing.json` files under **synthetic-xgb-v1-26c03624ed36a729/**. The XGBoost model is a real Git blob, not a missing binary or LFS pointer. The current working bundle loads; checks confirm a finite positive prediction for unknown IDs/missing weather, load-once behavior and honest unavailable status for a temporary missing bundle. The metrics match `docs/ml_metrics.json`.

Training source is **synthetic**, 2,000 observations (1,500 development, 500 untouched final test; 400 synthetic trips). No real-world accuracy is established. Geofence-exit-to-entry research observations are a separate target; neither the author's 225 stationary samples nor 90 moving samples are required/copied for installation.

**Known blocker:** raw Git LF contents fail the byte checksums of `baseline.json`, `preprocessing.json` and `metrics.json`. Reconstructing a CRLF checkout from the exact Git blobs passes the existing loader. The Git clone command above enables that workaround. This is not a universally portable verified bundle yet; do not claim an LF/archive install has loaded the model without checking it.

From `backend`, this check loads existing files only, without DB access, generation, training or paid requests:

```powershell
.\.venv\Scripts\python.exe -c "from ml.predictor import TravelTimePredictor; s=TravelTimePredictor().load(); print({k:s[k] for k in ('available','model_version','training_data_source','reason')})"
```

After startup: Admin → **Settings → Administrator tools → Evaluation** shows the authenticated model status/metrics. If unavailable, preserve the error and use simulation; ML requests must remain unavailable or follow an explicitly declared permitted fallback. Obtain the complete matching bundle from the reviewed source revision if files are missing. **Do not run `train_model.py` or `generate_synthetic_data.py` as installation steps**, invent model files, bypass checksums or replace targets.

> This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.

## Optional Google configuration

Without keys: authentication, persistence, synthetic fixtures, manual pin review, simulated routing, loaded experimental ML, saved versions and permitted trip/notification/review controls work locally. OpenStreetMap basemap tiles need internet but no Google key; if tiles fail, markers/stop sequence and the error remain. A stop-connecting polyline is **not a road route**.

For live Google functions, the reviewer must use **their own Google Cloud project, enabled APIs, credentials, restrictions, billing and quota**. Enter keys only in the reviewer's ignored `backend/.env`, then restart FastAPI:

| Variable | Enabled service | Trigger / cost |
|---|---|---|
| `GOOGLE_GEOCODING_API_KEY` and `GEOCODING_PROVIDER=auto` or `google` | Geocoding API | Explicit address lookup or authorized registration import with positive `geocoding_http_budget`. Can bill. Suggested building point still needs stopping-pin review. |
| `GOOGLE_ROUTES_API_KEY` | Routes API | Explicit Google plan/recommendation generation with a positive approved budget; optional ordered road geometry. Can bill. Future-date support is provider-limited. |
| `GOOGLE_STATIC_MAPS_API_KEY` | Maps Static API | Separate **Load Google road map** action for supported saved road geometry; can bill. Not requested on page load. |

These requests originate on the backend, not the phone/browser. Configure API restrictions for the correct services and server-origin restrictions appropriate to your connection; a browser-referrer-only key is not a substitute for a server key. Do not paste keys into frontend files or URLs. Budgets bound application HTTP requests, **not** a monetary allowance; provider billing can be per matrix element. Fallback to ML/simulation/baseline is not a successful live Google verification and must keep its actual source label. No paid smoke test was executed for this setup guide.

External **Navigate to next stop** is a supported Google Maps handoff to one confirmed saved destination. It does not require enabling our Routes/Static Maps adapters, reorder saved stops or advance a trip; it is not embedded turn-by-turn and does not guarantee the same road path.

## Optional Android HTTPS — after localhost works

Skip this entire section for an initial laptop-only review. Use your own trusted Wi-Fi/hotspot and CA; do not copy the author's certificates, private keys or historical IP/interface values from archived reports.

1. Identify the reviewer's physical adapter and its current IPv4; do not choose a virtual adapter:

```powershell
Get-NetAdapter -Physical | Select-Object Name,InterfaceIndex,Status,MediaType
$wifiAlias = Read-Host 'Name of the connected physical Wi-Fi adapter shown above'
Get-NetIPConfiguration -InterfaceAlias $wifiAlias
$phoneHost = Read-Host 'Current laptop Wi-Fi IPv4 shown above'
```

2. Install mkcert on the reviewer's laptop. Set `$mkcert` to its actual executable (`Get-Command mkcert.exe` if on PATH; otherwise its installed full path). Run **`& $mkcert -install`** with elevation when Windows requests trust installation. Then generate new server files outside the repository:

```powershell
$mkcert = (Get-Command mkcert.exe -ErrorAction Stop).Source
# If mkcert is not on PATH, instead assign its installed full path to $mkcert.
& $mkcert -install
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
New-Item -ItemType Directory -Force -Path $tlsDirectory | Out-Null
& $mkcert -cert-file (Join-Path $tlsDirectory 'phone-cert.pem') -key-file (Join-Path $tlsDirectory 'phone-key.pem') $phoneHost localhost 127.0.0.1 ::1
$caDirectory = (& $mkcert -CAROOT).Trim()
Copy-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') -Destination (Join-Path $tlsDirectory 'saferide-review-ca.crt')
```

Transfer **only that public CA certificate** to the reviewer's Android phone and install it as a user **CA certificate** in Android security settings. Never transfer `rootCA-key.pem` or the server key; never put TLS files in `frontend/public` or source. Chrome must trust the final origin without a certificate warning.

3. In an **Administrator PowerShell**, re-enter the detected values (variables do not transfer between terminals). On the trusted **Private** connection only:

```powershell
$wifiAlias = Read-Host 'Verified physical Wi-Fi adapter name'
$phoneHost = Read-Host 'Verified laptop Wi-Fi IPv4'
$phoneAddress = Read-Host 'Verified Android hotspot/Wi-Fi IPv4'
Get-NetConnectionProfile -InterfaceAlias $wifiAlias
New-NetFirewallRule -DisplayName 'SafeRide reviewer HTTPS' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -LocalAddress $phoneHost -RemoteAddress $phoneAddress -InterfaceAlias $wifiAlias -Profile Private
```

Check for an existing named rule first; do not create duplicate or broader rules. Do not mark an untrusted network Private, disable the firewall, open 5432/8000 or configure port forwarding. The hotspot phone can sometimes block access to its connected laptop; reaching the certified IP is a prerequisite, not guaranteed by a firewall rule.

4. Keep FastAPI bound to `127.0.0.1:8000` and PostgreSQL to localhost. Stop the existing Vite process before starting this one, from `frontend` in the ordinary terminal containing `$phoneHost`/`$tlsDirectory`:

```powershell
$env:SAFERIDE_HTTPS_HOST = $phoneHost
$env:SAFERIDE_HTTPS_CERT = Join-Path $tlsDirectory 'phone-cert.pem'
$env:SAFERIDE_HTTPS_KEY = Join-Path $tlsDirectory 'phone-key.pem'
npm run dev
```

Open `https://<current-laptop-Wi-Fi-IP>:5173` on the phone, **not** the phone's localhost. The existing `/api` proxy preserves one HTTPS origin for login and API calls. Hotspot reconnection can change the laptop IP; re-detect it, regenerate the certificate and update the narrow firewall rule. Do not disable certificate/authorization checks.

5. A permitted physical test additionally requires the assigned driver, an eligible trip, adult research approval where required, and explicit **GPS controls → Enroll phone sender for active trip → Start sharing**. Reviewers must create their own approved test, not reuse the author's completed trips. Research operator/driver selections remain distinct. Use **Stop sharing** and **Manage GPS sessions → Revoke** deliberately. Foreground Chrome tracking can pause when Maps opens; use a second navigation device. No physical verification is implied by installing HTTPS.

## Verification commands and side effects

| Check / action | Database / model / network effect |
|---|---|
| `python --version`, `node --version`, `pip check`, `alembic heads`, model-load check above | No DB writes or paid calls; model is read only. |
| `npm ci`, pip install, optional browser install | Install local packages/downloads; no app DB records or Google calls. |
| `tsc --noEmit`, `npm run build` | No DB writes; build writes ignored `frontend/dist`. Existing chunk-size warning is non-fatal. |
| `alembic current` | Reads configured DB; no migration. |
| `alembic upgrade head` | Changes configured schema; run only after the review destination assertion. |
| Seed/setup/account/assignment commands | Insert/update the review DB; activation/assignment can revoke sessions. |
| FastAPI startup | Background recovery/expiry workers may update pending review records. No implicit seed/retraining. |
| UI attendance/location saves, generation, publication, trip/GPS/pickup actions | Persist review records. Google generation/geocoding can bill when explicitly configured/approved. |
| Intercepted UI scripts listed below | Synthetic browser fixtures only; no live DB/Google requests. They do not prove physical capture or live integration. |
| Opt-in DB test suites, replay, `verify_pipeline.py`, `verify_traffic.py`, full test discovery | Not part of first run: some write fixtures/events/reports or perform generation/training. Inspect each first; never run indiscriminately against the author's DB. |

From `backend`, optional focused checks after installing `requirements-dev.txt` (read existing model/data, no training or DB writes):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_saved_navigation
.\.venv\Scripts\python.exe -m unittest tests.test_ml_pipeline.GeneratedArtifactTests.test_real_json_model_unknown_ids_and_load_once tests.test_ml_pipeline.GeneratedArtifactTests.test_saved_final_metrics_reproduce_without_training
```

Playwright is **not declared** in the frontend dependency manifest/lockfile, despite existing UI scripts using it. It was available locally as 1.58.1. For these optional checks, explicitly install it in the reviewer's frontend without changing manifests:

```powershell
npm install --no-save --package-lock=false playwright@1.58.1
.\node_modules\.bin\playwright.cmd install chromium
.\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5187
```

In another `frontend` terminal:

```powershell
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-workspace-cards.cjs
node scripts/verify-driver-navigation.cjs
```

These scripts intercept API responses and require neither a running backend nor real account credentials. Stop the test Vite server afterward. A later `npm ci` removes unlisted packages, so reinstall optional Playwright if needed. Do not use actual account passwords in test environment variables or run the credentialed auth harness as a first-run smoke test.

## Troubleshooting and verification limits

- **Port 5173 in use:** reuse the existing frontend or stop its own terminal with Ctrl+C. Strict-port failure is intentional; do not launch duplicate servers. Port 8000 must likewise have only the intended local backend.
- **Backend refused/timed out:** check terminal startup errors and `http://127.0.0.1:8000/`, PostgreSQL service, correct venv and migrations. Do not merely increase timeouts or reset accounts.
- **Wrong database/password/schema permissions:** check the nonsecret destination assertion, pgAdmin role login/ownership and `.env` privately. Never print connection URLs. Existing process env values can override `.env`.
- **Invalid credentials/lockout:** confirm `activate-initial` completed and workspace is Authenticated operations. Five failed attempts can cause a 15-minute account lock. Do not repeatedly guess or automatically reset initialized accounts; CLI `--help` documents deliberate local administration.
- **No Daily Plan/driver route:** S4 seed and Malabe are separate. Run the intended setup, choose the correct date, resolve attendance/pins, explicitly publish and assign the driver. There are no shipped saved route/trip records. Drivers never receive an unpublished draft as instructions.
- **Cannot start trip:** check service date, current feasible publication and departure allowance. Viewing a plan is not authorization to start it. Preserve the rules and choose an eligible separate test; do not backdate starts.
- **ML unavailable/checksum mismatch:** see the CRLF Git-checkout limitation above. Missing/corrupt/dependency errors must remain unavailable; don't invent predictions or silently retrain.
- **Missing `Asia/Colombo` timezone on Windows:** ensure the dependencies installed successfully; if tzdata is missing, install `tzdata` into the review venv and recheck `ZoneInfo('Asia/Colombo')`. Do not change the clock.
- **Map tiles missing:** check internet/tile availability. Missing tiles are not evidence of missing saved stops. Stop-sequence lines are not road directions.
- **Hasara integration:** registrations/assignments/attendance/boarding use the authenticated provisional adapter; her actual backend/card/parent-driver app and external notification delivery are disconnected unless independently connected. Manual test actions are not card scans; in-app event creation is not SMS/push delivery. See the existing [integration contract](integration-contract.md).

**Fresh-install limitations found during this documentation checkpoint:** npm's temporary clean-directory dry-run passed without installing dependencies or changing manifests; the installed backend passes `pip check`; TypeScript/build and four focused saved-navigation/artifact tests pass (including reproduction of saved final metrics without training). Existing artifact inference also passes. A fresh pip resolver dry-run returned “No matching distribution found for fastapi” from this shell; a separate diagnostic timed out. The reason for that resolver failure was not established, and a full clean backend install was not completed. Verify the reviewer's registry/network/proxy access rather than concluding the package does not exist. Required XGBoost/scikit-learn releases are present in official PyPI metadata linked above. Backend dependencies are not fully locked, Playwright is optional/unlisted, LF artifact portability is blocked, and a second-laptop database/bootstrap/phone setup has not been executed here.

No current accounts, passwords, historical evidence, model contents or database configuration were changed to verify this guide. Source alone does not back up PostgreSQL. The archived [private-backup procedure](archive/checkpoints/local-checkpoint-and-backup.md) is for the owner's private evidence protection, **not** a reviewer installation step. Historical reports may contain obsolete commands, dates or interfaces; use this guide for first run.
