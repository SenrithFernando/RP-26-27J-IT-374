# VAN_01: authorized adult landmark phone GPS test

**Recorded physical checkpoint:** the operator-confirmed stationary Android run
on 19 October 2026 has 225 persisted unique actual-device samples; session revoked
and trip completed. See [stationary phone checkpoint](physical-phone-stationary-checkpoint.md)
for current evidence and strict limitations. Earlier pending statements below
describe pre-test setup history, not the outcome of this specific run.

**HTTPS follow-up inspection:** the active physical Wi-Fi interface 21 has IPv4
`10.123.106.157` (DHCP; recheck if network changes). PostgreSQL is now bound only
to 127.0.0.1/::1. mkcert v1.4.4 is available as `C:\Tools\mkcert.exe` after
correcting its accidental `.exe.exe` filename. The CA directory is
`C:\Users\MSI\AppData\Local\mkcert`; expected server certificate/key files have
not yet been generated. Wi-Fi remains Public. Use the numbered commands in
[current phone HTTPS setup](phone-https-setup-current.md). Older network/tool
findings below are the initial checkpoint history, not current binding status.

## Status and exact blockers

**Physical Android ingestion is pending.** Inspection found zero phone tracking
sessions and zero actual-device positions. No synthetic GPS was submitted as
physical evidence. `driver.local` is now assigned to `MALABE_PP1_VAN_01`; no
assignment was changed here. No ACTIVE trip was found for this vehicle.

Default scenario date is 2026-10-19. Use the actual local test day; there is no
future-trip start bypass or PC-clock change. If testing on a different day, dated
attendance must be explicitly supplied/reviewed for that day, not copied silently.
Consent and physical phone permission remain actions for the adult operator.

mkcert is not installed. Windows Wi-Fi profile is **Public**. PostgreSQL reports
`listen_addresses=*`, with IPv4 0.0.0.0 and IPv6 :: listeners on 5432. FastAPI
currently listens only on 127.0.0.1:8000. Windows firewall profiles are enabled;
no enabled inbound rule named PostgreSQL/SafeRide was found, but rules under other
names and PostgreSQL host access rules were not conclusively assessed. The
application DB role is not a superuser and cannot read `pg_hba_file_rules`.

Therefore remote database access is **not proven**, but PostgreSQL is not private
by binding alone. No network setting was changed. Restrict its binding before
making the web entry point reachable. Do not forward ports in a router, expose
5432/8000 or disable authentication/firewall. Use your own trusted Wi-Fi, not a
public/campus network for this local deployment.

## 1. Make PostgreSQL loopback-only

Stop FastAPI with Ctrl+C. In pgAdmin use your **local database-administrator
connection**, not saferide_app. Run:

```sql
SHOW listen_addresses;
ALTER SYSTEM SET listen_addresses = 'localhost';
```

In elevated Windows PowerShell:

```powershell
Restart-Service -Name postgresql-x64-17
Get-NetTCPConnection -LocalPort 5432 -State Listen | Select-Object LocalAddress,LocalPort
```

Only 127.0.0.1 and/or ::1 should appear. Reconnect pgAdmin and verify:

```sql
SHOW listen_addresses;
```

It must return localhost. This is a server binding change, not a database-record
change. If another local application depends on remote PostgreSQL access, resolve
that with its owner before applying it. No database admin password is needed in
chat, source, command arguments or logs.

## 2. Create trusted local HTTPS

Use the existing Vite HTTPS + `/api` proxy. Install mkcert using Windows Package
Manager and open a fresh PowerShell if PATH needs updating:

```powershell
winget install --exact --id FiloSottile.mkcert
mkcert -install
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress
$phoneHost = Read-Host 'Enter this PC trusted Wi-Fi IPv4 address from the list'
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
New-Item -ItemType Directory -Path $tlsDirectory -Force | Out-Null
mkcert -cert-file (Join-Path $tlsDirectory 'phone-cert.pem') -key-file (Join-Path $tlsDirectory 'phone-key.pem') localhost 127.0.0.1 $phoneHost
$caDirectory = mkcert -CAROOT
Copy-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') -Destination (Join-Path $tlsDirectory 'saferide-development-ca.crt')
```

Transfer **only** `saferide-development-ca.crt` to your own Android phone over
USB. Never transfer either private key. Install it under Android Settings →
Security/Privacy → Encryption & credentials / Install a certificate → CA
certificate (names vary by phone). This is a browser test, not a native app.
Chrome must trust the resulting HTTPS page without a certificate warning. Do
not disable secure-context checks or send keys to a public tunnel. Remove the
development CA from the phone after testing.

mkcert's authoritative [mobile-device/root-CA guidance](https://github.com/FiloSottile/mkcert#mobile-devices)
explains the separate root-certificate installation and private-key restriction.

If this is your **own trusted network**, mark it Private in Windows settings or
use this elevated PowerShell command. Do not do this for untrusted public Wi-Fi:

```powershell
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private
$phoneAddress = Read-Host 'Enter the Android phone Wi-Fi IPv4 address'
$pcAddress = Read-Host 'Enter this PC Wi-Fi IPv4 address used in the certificate'
New-NetFirewallRule -DisplayName 'SafeRide adult phone HTTPS only' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -LocalAddress $pcAddress -RemoteAddress $phoneAddress -Profile Private
```

This rule allows only that phone to port 5173 on the PC's Wi-Fi interface. Inspect
any existing broad Node/Vite rules separately; this narrow rule does not revoke
other rules. Do not add database/backend rules.

## 3. Start backend and the single HTTPS frontend

Backend terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

No new migration or model training is needed for adult-test approval: existing
trip JSON and immutable landmark input-event auditing are reused.

Stop the old Vite terminal with Ctrl+C first (port 5173 is strict). In a separate
PowerShell terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$phoneHost = Read-Host 'Enter this PC Wi-Fi IPv4 address used in the certificate'
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
$env:SAFERIDE_HTTPS_HOST = $phoneHost
$env:SAFERIDE_HTTPS_CERT = Join-Path $tlsDirectory 'phone-cert.pem'
$env:SAFERIDE_HTTPS_KEY = Join-Path $tlsDirectory 'phone-key.pem'
npm run dev
```

The new optional `SAFERIDE_HTTPS_HOST` binds HTTPS Vite only to that IP. Phone →
HTTPS 5173 → existing `/api` proxy → loopback FastAPI 8000 → local PostgreSQL.
The phone never needs direct backend/database access. This remains a development
server: static application code is visible, while operations require existing
authentication. It is not production hosting or continuous background tracking.

## 4. Prepare a consenting adult trip explicitly

1. On PC open `https://PC_WIFI_IPV4:5173` and log in as administrator in
   **Authenticated operations**. Do not share login passwords/tokens.
2. **Access** → choose existing `driver.local` → confirm `MALABE_PP1_VAN_01` is
   selected. If changing relationships, preserve all intended selections and
   click **Save assignments and revoke old sessions**. Re-login afterward. This
   is the existing assignment interface; there is no assign-driver CLI.
3. **Daily Plan** → actual test date → explicitly review AM/PM attendance,
   confirmed landmark pins and a feasible route. Prefer simulation estimates
   for a no-cost capture test; the GPS source is independent of travel estimates.
   Publish the reviewed direction. Do not manufacture card or boarding events.
4. In Driver, select authorized VAN_01, the same date/direction and published
   route. In **Persistent trip lifecycle**, choose **production** duration mode,
   then **Create planned trip (manual prototype)**. Record its nonsecret TRIP_ ID.
   If there is already an active trip, use/review that explicitly; never replace it.
5. Admin → **Access** → **Adult landmark phone test authorization**. Enter that
   TRIP_ ID and a reason. Confirm consenting adults only, no student passengers
   and no measured student-trip labels. Click **Authorize adult landmark phone
   test**. Approval is audited, route/trip-bound, valid only for today's open
   Malabe trip, expires within two hours and does not change planning provenance.
6. Driver → **Refresh route**. Start the planned trip using **Start trip (manual
   prototype)** when actually ready. Start requires today's Sri Lankan date.

Existing API commands behind these controls (all authenticated):
`PUT /auth/admin/accounts/{account_id}/vehicles`, `POST /trips` with saved
`route_id`, `POST /tracking/adult-field-test` with `trip_id`, `reason`,
`adults_only_confirmed:true`, and `POST /trips/{trip_id}/start`.
Only Admin may approve adult tests. Assignment/start/enrollment remain separate.

## 5. Physical Android Chrome checklist

- [ ] Android Location and automatic date/time are enabled. PC/phone are on the
      same trusted Wi-Fi; the URL certificate is trusted.
- [ ] Open `https://PC_WIFI_IPV4:5173` in Android Chrome, not phone localhost.
- [ ] Login privately as assigned driver in **Authenticated operations**.
- [ ] Select VAN_01 and actual service date/direction. Confirm ACTIVE trip ID and
      pinned route version. The adult-test approval banner must be visible.
- [ ] In **Vehicle-bound tracking authorization**, click **Enroll phone sender
      for active trip**. This calls `POST /tracking/enroll` with kind phone and
      checks assignment/trip/approval. A simulation enrollment is not phone GPS.
- [ ] In **Actual phone GPS — foreground browser**, click **Start sharing**.
      Grant precise location permission in Chrome while using the site. Start
      sharing does not itself create/start a trip or confirm a pickup.
- [ ] Keep Chrome visible and screen awake; wait for **Sharing — upload accepted**.
      Check recorded time, last successful upload, accuracy/quality and freshness.
      Speed may legitimately be null/unavailable. Never operate while driving;
      use a stationary or safely walking adult/operator.
- [ ] Copy only the public DEVICE_ session ID (not the tracking credential) and
      run the read-only command below on PC. Confirm actual_device, matching
      vehicle/trip/session, distinct sample IDs, recorded/received times and
      accuracy. Both physical operator confirmation and stored evidence are
      required; source tagging alone does not attest a genuine sensor.
- [ ] With Chrome foreground, briefly disable phone networking, then reconnect
      within two minutes. Retries keep sample IDs/recorded times. Check unique
      persisted IDs/latest ordering; receipt time must not replace recorded time.
      Duplicate suppression is already verified by rollback tests; do not forge
      coordinates or manually create actual-device samples to demonstrate it.
- [ ] Click **Stop sharing**: watch/queue clear, no new samples should appear.
      One request already committed before stopping can remain in history. Stop
      sharing does not revoke its credential or end the trip automatically.
- [ ] Click **Revoke** on the issued DEVICE_ row. Expired/revoked authorization
      rejects uploads; logout/reassignment also revokes authorization. After
      re-enrollment, consent is still limited by the adult-trip approval expiry.
- [ ] Wait over 60 seconds after the last sample; confirm stale/unknown rather
      than "vehicle stopped". Poor accuracy (>50 m by current default) is labelled
      poor/unknown and ignored for arrival/anomaly transitions.
- [ ] Refresh does not restart capture. Denied permission displays an error and
      creates no position. Closing/locking/hiding Chrome can pause collection;
      foreground browser tracking is not reliable background GPS.
- [ ] End/cancel the test lifecycle explicitly; do not claim students were
      delivered. Closed-trip queued samples receive 409 without changing live state.

Read-only accepted-sample verification (coordinates/credentials omitted):

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$trackingId = Read-Host 'Enter the DEVICE_ ID shown in Driver (not its credential)'
.\.venv\Scripts\python.exe verify_phone_capture.py --tracking-id $trackingId --limit 10
```

Actual coordinates/accuracy/speed/timestamps are stored by existing ingestion;
the backend derives vehicle/trip/source from the scoped credential. Unknown
speed remains null. Adult landmark samples remain excluded by the shared
measured-student-observation export/metrics provenance gate. They are not a
training dataset and do not establish measured student travel durations. Any
arrival/window/anomaly decisions during this adult run remain landmark-test
demonstrations, not observed student boarding/delivery.

After testing, remove the temporary firewall rule in elevated PowerShell:

```powershell
Remove-NetFirewallRule -DisplayName 'SafeRide adult phone HTTPS only'
```

Remove only your development CA from Android when finished. Leave PostgreSQL
loopback-only. Never delete trip/position history to clean up a test.

## Available checks, not physical-phone evidence

Checkpoint results: 7 authorization tests and 12 landmark/attendance/trip tests
passed, including the new audited adult-phone exception and export exclusion.
The new test was also run separately and passed (not an extra distinct test).
Five mocked phone-browser capture checks and four intercepted driver-boundary
checks passed. TypeScript and the frontend production build passed. No physical
phone or live external API was used by those checks.

Backend tests use synthetic positions inside rollback transactions, including
explicit approval, duplicate approval, no approval/driver approval denial,
phone binding, nullable speed, unique retry, out-of-order handling, forged IDs,
revocation and measured-student-export exclusion. Browser tests mock geolocation.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_LANDMARK_TESTS='1'
$env:SAFERIDE_RUN_AUTH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_landmark_daily.py -v
Remove-Item Env:SAFERIDE_RUN_LANDMARK_TESTS
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
Set-Location ..\frontend
node scripts/verify-phone-capture.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

**Do not mark physical ingestion complete until accepted samples exist and the
operator confirms the physical Android run.** Report the DEVICE_ ID and sanitized
status/error only; never passwords, credentials or private coordinates.
