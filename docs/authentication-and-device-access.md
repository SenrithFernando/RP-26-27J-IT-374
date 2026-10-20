# Authentication and vehicle-bound tracking — 18 October 2026

Authentication is mandatory for operational APIs. There is no AUTH_DISABLED switch, public demo bypass, default password, cookie fallback or trust in a role chosen by the browser. Simulation is preserved as an explicit authenticated workspace and ingestion mode. This does not establish physical GPS authenticity, production deployment readiness or field accuracy.

## Login/session strategy

- Argon2id via maintained `argon2-cffi` PasswordHasher; random salts and rehash check after successful verification. Minimum 12 characters for new/reset passwords, maximum 1,024. Passwords/hashes are never returned by account endpoints.
- Server-side opaque random 256-bit bearer tokens. PostgreSQL stores SHA-256 token digests, account, workspace, aware creation/expiry/revocation timestamps. Login expiry is eight hours; no refresh-token persistence or sliding extension.
- Browser token is per-tab `sessionStorage`, never localStorage, cookies or URLs. API calls explicitly set Authorization and omit cookies. Refresh revalidates with /auth/me. Logout revokes that login plus every tracking credential it issued. Administrator account-wide revocation/password reset/disable/reassignment invalidates all affected login/tracking sessions.
- No authentication cookies are used, so no ambient-cookie CSRF mechanism is required. Cross-origin bearer acquisition is not enabled with permissive CORS. Login requires JSON; no token is accepted in a URL or cookie. HTTPS is mandatory outside local development. Tokens in sessionStorage remain readable by XSS: trusted scripts, HTTPS and careful deployment remain required; this is not an XSS-proof credential store.
- Five bad attempts lock an account for 15 minutes; unknown/incorrect/inactive login responses are generic. A bounded per-process/IP limiter allows 20 attempts/minute. Use a shared external limiter for multi-process deployment. Password reset through the private CLI clears lockout and revokes sessions.
- Sensitive responses are no-store/nosniff with no-referrer. Validation errors omit submitted input, preventing password values from being reflected in validation responses. No credentials are written to logs or committed files.
- A failed logout request is shown as an error; the UI does not falsely claim server revocation. Retry once connectivity is restored. Normal confirmed logout is verified below.

References: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html), [FastAPI bearer security](https://fastapi.tiangolo.com/tutorial/security/first-steps/). Bearer tokens here are opaque server sessions, not JWTs or a claimed OAuth authorization server.

## Relationships and object-level policy

| Account | Permitted operational access |
|---|---|
| Administrator | Transport registration/location/schedule mutations, route generation, all project routes/trips, account/relationship management, scoped tracking enrollment/revocation and protected measured-evidence export |
| Driver | Current assigned vehicle directory/roster/schools, saved routes, GPS history/latest and that vehicle's trip create/start/end/cancel, arrivals/pickups/history/operational events; tracking enrollment only for an authorized active trip |
| Parent | Only linked student registration/summary, that student's schools and own in-app notification read state. No full shared route, vehicle GPS history, other student's context, account admin, tracking or exports |

Account role and current DriverVehicle/ParentStudent relationships are read from PostgreSQL on every request; browser IDs never grant authority. Route IDs resolve to their vehicle, trip IDs to their pinned saved route, notification IDs to their student, and tracking IDs to their issuer/vehicle. Collection queries are scoped as well as individual objects. New otherwise-unclassified operations default to administrator access in the central policy; review policy whenever adding routes.

Global `authorize` dependency is installed on the actual `main.app`; HTTP tests use that app, not an unprotected substitute. Internal solver/worker functions remain trusted backend operations. Local CLI tools use OS/database administrator authority; possession of backend/.env/database access is outside HTTP authentication boundaries.

## Real versus demo frontend

Every visitor first logs in. **Authenticated operations** uses the server account role: Admin Routes/Students/Notifications/Access, authorized Driver saved-route/trip view, or linked Parent summary/inbox. It does not render the old simulated cabin/Parent tracking/overview panels as real operational data.

**Authenticated synthetic demo** keeps the existing role-selector and component demonstrations with an always-visible demo/account header. Changing a demonstration interface does not change backend account permissions. Demo sessions cannot read real vehicle/route snapshots, use measured export/account administration, perform real geocoding or call live Google traffic/map images. Simulated provider scenarios and explicitly forced live-failure ML fallback remain available. Actual coordinates do not automatically enable live-provider inputs.

Authorization failure shows an error or login; it never substitutes a mock successful route or enters demo mode. Existing private map images now fetch with an authorization header and render from a revocable blob URL, not a token URL.

## Tracking/device sessions

1. Authorized Driver/Admin enrolls an active vehicle/trip with kind phone or simulation. Kind phone requires real workspace, non-synthetic vehicle/saved input context and no synthetic-trip registration/accelerated demo. Simulation requires a simulated vehicle.
2. Server issues a separate random scoped credential, returned once. Stored record binds issuer login, account via login, vehicle, trip, kind, label, expiry and revocation. Expiry is the earlier of two hours or the issuer login's expiry. Raw credential is not stored server-side.
3. Every upload rechecks account/session state, current assignment, credential expiry/revocation, vehicle/trip binding and active state under account→login→vehicle→trip locks. Password/reassignment/revocation operations use compatible locks. The source and IDs are derived from this record, not supplied by the browser.
4. Upload body permits only sample_id, recorded_at, latitude, longitude and optional speed_mps. Supplying vehicle_id, trip_id, driver_id or source is rejected as extra input. Tracking credentials cannot authenticate to normal account/history endpoints; user login credentials cannot upload to the scoped tracking endpoint.
5. Queued samples from closed/inactive trips receive **409** and create no position or live state change. Samples predating enrollment or trip start receive **422**. Expired/revoked credentials receive **401**; lost assignment receives 401/403. Never rebind an old queue to a new trip or invent a new recorded timestamp. There is no closed-trip archival upload endpoint in this task.

Existing position validation/deduplication, aware timestamps, ordered-latest handling and arrival/operational processing are reused. Authorized actual-device source describes the credential channel, not proof that coordinates came from uncompromised physical hardware. Accuracy/clock quality and native/background collection remain separate work.

The Driver tracking panel can enroll/revoke a sender and privately copy its masked one-time credential. Enrollment itself does not collect GPS. `frontend/src/services/tracking.ts` provides a separate typed upload helper; it intentionally does not use the login-token API helper. No automatic phone geolocation/background collector was added by this authorization task.

Legacy POST `/routing/vehicles/{vehicle_id}/positions` is now **authenticated simulation only**, with assigned/admin vehicle checks and active-trip checks when associated. It never accepts actual_device. Existing replay tools prompt privately for login and preserve simulation source; they do not accept passwords in command arguments/environment. Real ingestion uses only `/tracking/positions`.

## New/current authentication endpoints

All paths are backend-relative; the frontend prefixes /api through the existing Vite proxy.

| Method | Path | Access |
|---|---|---|
| POST | /auth/login | Public JSON credentials + explicit mode real/demo |
| GET | /auth/me | Valid login; own role, relationships, mode and expiry |
| POST | /auth/logout | Revoke current login and its issued tracking sessions |
| GET/POST | /auth/admin/accounts | Administrator, real workspace; no hashes returned |
| PUT | /auth/admin/accounts/{id}/vehicles | Administrator; replace driver assignments, revoke prior sessions |
| PUT | /auth/admin/accounts/{id}/students | Administrator; replace parent links, revoke prior sessions |
| POST | /auth/admin/accounts/{id}/revoke | Administrator; revoke all account login/tracking sessions |
| GET | /parent/students/{student_id} | Linked parent or authorized Driver/Admin; minimal permitted summary |
| POST | /tracking/enroll | Authorized Driver/Admin; matching ACTIVE vehicle/trip |
| POST | /tracking/positions | Scoped tracking bearer only; no client ID/source fields |
| GET | /auth/tracking | Driver/Admin; own currently permitted tracking metadata, never token/hash |
| POST | /tracking/{id}/revoke | Issuer Driver with current assignment, or authorized Admin |
| POST | /exports/measured-observations | Administrator real workspace plus existing measured-lineage guard |

Existing routes/trips/GPS/history/arrivals/pickups/notifications/ML/location endpoints are preserved with authorization. Root/health and JSON login are the only public application operations; schema/documentation remains discoverable. Old compatibility /students, /vehicle and /routes/{direction} is administrator demo-only. GET latest remains retrieval only.

## Local accounts: created locked, activate privately

Migration **0014_authentication** is already applied locally. The following accounts were created without usable password hashes; **none can log in until you set its password**:

| Username | Role / existing synthetic relationship |
|---|---|
| admin.local | Administrator |
| driver.local | Driver → PP1_DEMO_0c1effd6_VAN_A |
| parent.local | Parent → PP1_DEMO_0c1effd6_STUDENT_01 |

No password was invented, printed, committed or placed in .env. Run these directly in your PowerShell terminal; getpass hides password entry. Do not pipe passwords, paste them into chat, or add them as command arguments:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe manage_accounts.py set-password admin.local
.\.venv\Scripts\python.exe manage_accounts.py set-password driver.local
.\.venv\Scripts\python.exe manage_accounts.py set-password parent.local
```

Each asks for a new password and confirmation privately (12+ characters), enables that account and revokes its old sessions. To disable an account:

```powershell
.\.venv\Scripts\python.exe manage_accounts.py disable driver.local
```

Repeatable preparation on this local database preserves existing accounts/links/passwords:

```powershell
.\.venv\Scripts\python.exe manage_accounts.py prepare-local --vehicle-id PP1_DEMO_0c1effd6_VAN_A --student-id PP1_DEMO_0c1effd6_STUDENT_01
```

The preparation command requires the named records already exist and are simulated; it does not seed/change transport records or overwrite existing credentials. Initial administrator bootstrap is intentionally a local database-administrator action, not a public registration endpoint.

## Exact local run and browser verification

Restart the existing backend rather than launching a second process on occupied port 8000. Normal startup resumes existing planning/expiry workers, independently of login; this is not a read-only audit operation.

```powershell
# Backend terminal
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# Separate frontend terminal
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

1. Open http://localhost:5173. Confirm login appears and no unauthenticated role selector is offered. Use one consistent origin; local tokens are per tab/origin.
2. Enter admin.local and your privately chosen password; select Authenticated operations. Routes/Students/Notifications/Access are available, not the demonstration role selector. Choose the synthetic PP1 vehicle, today's service date and simulation provider for route testing. A past plan stays historical; an active trip's pinned route is not replaced by generation.
3. Open a separate private browser window and log in as driver.local. Only its assigned vehicle appears. Check saved route/trip version. Start only a current feasible plan; existing trip guards remain. The tracking panel offers a **simulation** credential for this synthetic vehicle, never phone actual-device source.
4. Open another isolated browser profile/window as parent.local. Only STUDENT_01 appears. Summary/inbox use server-linked identity, not the old hardcoded demonstration child.
5. Admin → Access: create driver.b.local/parent.b.local with passwords entered privately in the password field. Assign Driver B to PP1_DEMO_0c1effd6_VAN_B; link Parent B to STUDENT_02. Save assignments; affected account must log in again. No password/hash appears in account listings.
6. Driver A requesting Driver B's /routes/latest or /routing/vehicles/{B}/positions must get 403. Parent A requesting /parent/students/{STUDENT_02}, its inbox or notification read state must get 403. Parent/Driver measured export requests get 403; anonymous requests get 401.
7. Enroll a tracking session only for the selected ACTIVE trip. Keep the private credential out of screenshots, URLs and logs. For this synthetic demo, any uploaded source is server-derived simulation. Actual phone credentials require separately registered non-synthetic context and real workspace.
8. Revoke the tracking row; further uploads return 401. Enroll again, then logout: old credential returns 401. Admin reassigning Driver A revokes its login/tracking sessions; refresh requires login. End the trip deliberately; a queued upload to its old credential returns 409 without inserting a position or resetting live state.
9. Login with Authenticated synthetic demo explicitly to use component demonstrations/role selection. Invalid credentials/session must show an error/login, never silently enter demo.

Real credentials are never passed to verification scripts. The exact negative scenarios above are automated with ephemeral rollback fixtures in the checks below; physical phone collection/live Google was not verified.

## Automated checks and actual evidence

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:SAFERIDE_RUN_DB_TESTS = '0'
$env:SAFERIDE_RUN_AUTH_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:\SAFERIDE_RUN_AUTH_TESTS
.\.venv\Scripts\python.exe verify_auth_browser.py
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
Set-Location ..\frontend
node .\node_modules\typescript\bin\tsc --noEmit --incremental false
npm run build
```

- **Six HTTP security test groups passed** using actual main.app with all DB changes inside rollback-only transactions. Tested anonymous access; parent cross-student and forged notification read; driver vehicle/trip/history/map/export boundaries; forged vehicle/trip/driver/source upload fields; proper server-derived phone source; credential and login expiry; revocation/logout/reassignment; closed queues; authenticated simulation; Argon2id/lockout and redacted validation. No fixture account, student, vehicle, trip or position is retained. [Evidence](auth-verification.json).
- **Browser check passed**: anonymous login, scoped Driver/Parent selectors, denied cross-object reads, session refresh, Admin Access UI, explicit demo-only scope and no invalid-token demo fallback. No page errors. The harness forwards UI requests to an actual main.app HTTP server with rollback DB fixtures, not mocked authorization. No production workers or paid provider calls. [Evidence](auth-browser-verification.json).
- Network-blocked non-mutating regression discovery passed 40 tests; database/security groups skipped in that separate run. [Evidence](auth-regression-checks.json), [log](auth-regression-checks.txt). Security groups are independently exercised above, not counted as skipped verification.
- TypeScript and frontend build passed. Live local :8000 checks observed health 200, anonymous /auth/me and /routing/students 401; frontend proxy /api/auth/me also 401.
- The test stack currently emits a Starlette compatibility deprecation notice for httpx; checks pass. This is a development-test dependency warning, not a hidden authentication fallback.

Existing historical browser scripts that click roles without login now correctly fail at login. Existing focused router-only test servers are not evidence of HTTP authorization; the new checks deliberately use the protected production app.

The old position/pickup router-only loopback test servers have an explicitly named internal domain-test context so their domain serialization/query tests still work with request-scoped filters. That helper lives only under tests, is never imported by main.app, and is not a runtime setting or authentication-failure fallback. It must not be deployed as an application entry point.

## Files and deployment limits

Backend: models plus migration 0014; auth.py, account_admin.py, tracking.py, exports_api.py and manage_accounts.py; main app global policy/security responses; scoped persistence/notification queries; privately authenticated replay tooling/cli_auth.py; dependencies and rollback security/browser checks.

Frontend: AuthContext, session/API/tracking services, AuthenticatedApp shell/login/scoped Parent, AccountAccess and TrackingAuthorization; protected Driver view and notification controls; authorized map-image loading; App wrapper and browser regression script.

This completes application authentication/authorization in scope. It does not add MFA, email/password recovery, hardware attestation, real GPS capture/background guarantees, measured model training, provider verification, TLS hosting or a multi-process rate-limit/deployment system. Configure HTTPS/reverse proxy, secret handling, process supervision and operational access/retention before exposing real student data. Current model and synthetic datasets were not retrained/regenerated.
