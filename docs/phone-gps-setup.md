# Actual phone capture: local HTTPS and Android Chrome

**Physical stationary test now recorded:** see the
[19 October 2026 checkpoint](physical-phone-stationary-checkpoint.md). This
supersedes the pre-test pending status below for that specific adult landmark run
only; moving/background tracking and travel-time accuracy are not established.

**Updated Malabe adult-only test path:** see
[VAN_01 adult phone test](van01-adult-phone-test.md). It adds explicit, expiring,
audited administrator approval for a specific landmark-test trip without
relabelling synthetic planning inputs. The original non-synthetic transport
policy described below remains the default for all other contexts. Historical
preflight statements in this document are superseded by that checkpoint's
current inspection; no physical-phone success is implied.

## Current verification and blockers

Implemented capture is opt-in and foreground-only. Migration
0015_phone_accuracy was applied to saferide_routing. Existing samples/history were
preserved; accuracy/session lineage on old records remains null, not fabricated.

The local preflight found **zero non-synthetic vehicles**. Existing active trips
use synthetic contexts. The existing authorization policy correctly blocks phone
enrollment in these contexts. Do not relabel fixtures, change their trip provenance
or disable authentication. An administrator must first register genuine vehicle,
school and consenting participant location inputs, assign that vehicle to the
driver, and create/start a current feasible trip from a non-synthetic saved route.
The current app does not have a complete real-school/vehicle registration UI;
this is a provisioning blocker, not a reason to reuse the synthetic seed as real.
No actual participant data or new live context was invented by this implementation.

Actual Android ingestion has **not** been verified. Local backend rollback tests
and intercepted geolocation browser tests are synthetic verification evidence.
No paid API calls, model retraining or real student edits were performed.

## Database and backend must remain private

Preflight found PostgreSQL listen_addresses='*' and listeners on 0.0.0.0/::5432.
That does not alone prove remote accessibility, but is not a loopback-only setup.
The application role is not a superuser. In pgAdmin, connect locally using your
database-administrator login and run (not using saferide_app):

```sql
ALTER SYSTEM SET listen_addresses = 'localhost';
```

Stop FastAPI first. Restart the existing PostgreSQL service from an elevated
PowerShell terminal, then verify local listeners. This changes server binding,
not application records. Do not open firewall ports 5432 or 8000.

```powershell
Restart-Service -Name postgresql-x64-17
Get-NetTCPConnection -LocalPort 5432 -State Listen | Select-Object LocalAddress,LocalPort
```

Only 127.0.0.1 and/or ::1 should be listed. In pgAdmin verify
`SHOW listen_addresses;` returns localhost. If another config source overrides it,
resolve that before making the development frontend reachable on the LAN.

Backend terminal:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Trusted local HTTPS (same private Wi-Fi)

mkcert was not found during inspection. Install it locally using Windows Package
Manager, then open a new PowerShell terminal if necessary:

```powershell
winget install --exact --id FiloSottile.mkcert
mkcert -install
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress
$phoneHost = Read-Host 'Enter this PC Wi-Fi IPv4 address shown above'
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
New-Item -ItemType Directory -Path $tlsDirectory -Force | Out-Null
mkcert -cert-file (Join-Path $tlsDirectory 'phone-cert.pem') -key-file (Join-Path $tlsDirectory 'phone-key.pem') localhost 127.0.0.1 $phoneHost
$caDirectory = mkcert -CAROOT
Copy-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') -Destination (Join-Path $tlsDirectory 'saferide-development-ca.crt')
```

Transfer **only saferide-development-ca.crt** to your own Android phone over USB.
Never transfer rootCA-key.pem or phone-key.pem. The development CA grants trust;
install only the CA you generated yourself, and remove it after local testing.
On Android: Settings → Security/Privacy → More security settings → Encryption &
credentials → Install a certificate → CA certificate. Choose the transferred .crt.
Menu names vary by Android vendor/version. Chrome must trust the certificate;
do not proceed through a certificate warning or disable secure-context checks.

Start frontend HTTPS in the same terminal holding $tlsDirectory:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$env:SAFERIDE_HTTPS_CERT = Join-Path $tlsDirectory 'phone-cert.pem'
$env:SAFERIDE_HTTPS_KEY = Join-Path $tlsDirectory 'phone-key.pem'
npm run dev
```

Stop an existing Vite instance first: strict port 5173 is preserved. HTTPS mode
binds Vite to 0.0.0.0:5173. No certificate/key is exposed through VITE_ variables
or committed. `/api` still proxies server-side to http://127.0.0.1:8000; the phone
does not need database or direct backend access. LAN clients may see frontend
source because this is a development server, not a production deployment.

If Windows blocks access, add this narrow rule in an elevated PowerShell terminal
on a trusted Private network only:

```powershell
New-NetFirewallRule -DisplayName 'SafeRide local phone HTTPS' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -Profile Private -RemoteAddress LocalSubnet
```

Open **https://YOUR_PC_WIFI_IPV4:5173** in Android Chrome, substituting the IP used
in the certificate. The phone must be on the same network, without client
isolation. The phone's localhost is the phone itself, not the Windows PC.
If the Wi-Fi IP changes, regenerate the leaf certificate for the new address.

## Actual Android verification (requires eligible real context)

1. Enable Android Location, automatic date/time and accurate location permission.
   Open the trusted HTTPS origin. Log in privately as the assigned driver and
   choose Authenticated operations. Desktop localhost login does not transfer
   to the phone's HTTPS origin.
2. Select the genuinely registered vehicle and direction. Verify ACTIVE trip ID,
   vehicle and pinned saved route version. If there is no eligible ACTIVE trip,
   stop here; a simulation credential cannot upload actual phone data.
3. Select **Enroll phone sender for active trip**, then **Start sharing**. Permit
   precise location for this site while using Chrome. The credential stays in
   memory; you do not copy it or supply vehicle/trip/source in upload bodies.
4. Wait for “Sharing — upload accepted”. Check latest captured accuracy, uploaded
   accuracy/quality, recorded timestamp, last successful upload, and fresh/stale
   status. The backend GPS card should show actual_device plus a position ID and
   tracking-session linkage. Missing speed must remain unavailable.
5. While stationary/safely walking (never operate the phone while driving), wait
   at least five seconds for another observation. Copy only the nonsecret DEVICE_
   session ID from the issued tracking-session list, then verify on Windows:

   ```powershell
   Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
   .\.venv\Scripts\python.exe verify_phone_capture.py --tracking-id DEVICE_ID_FROM_DRIVER
   ```

   It prints IDs, timestamps, accuracy/source and counts, never coordinates,
   credentials, passwords or session tokens. Confirm the displayed session/vehicle/
   trip matches the phone. Persisted lineage establishes accepted server input;
   operator confirmation establishes that this run used the physical Android phone.
6. Briefly disable phone networking while Chrome remains foreground. Captured
   observations should queue; reconnect within two minutes. Retried sample IDs
   and recorded timestamps remain unchanged. Check latest observation stays newest.
7. Select **Stop sharing**: watch and pending queue clear; no further captures are
   uploaded. This does not end the trip. Revoke the session using the issued-row
   Revoke action; old credentials receive 401. Closed-trip queues receive 409.
8. Refresh: capture does not restart automatically. Server positions/history
   persist, but in-memory credentials/queue are lost. Enroll deliberately again
   if sharing is still needed. Logout/reassignment/revocation invalidates grants.
9. Stop sharing and wait over 60 seconds: recorded sample becomes stale, never a
   “vehicle stopped” assertion. Deny site location permission and retry capture:
   permission error must be visible and no fabricated observation should appear.

Do not share screenshots with coordinates, private IDs or credentials. For
assisted verification provide only whether the test passed, DEVICE_ ID if needed,
and sanitized error/status text. No passwords/tokens are required.

## Explicit capture/quality policy and limits

### Exact assignment and button locations

Admin: Authenticated operations → Access → Manage account → select driver.local
(or another existing driver) → Authorized relationships → select the genuinely
registered vehicle → **Save assignments and revoke old sessions**. This replaces
the driver's selected vehicle relationships and revokes old sessions, so preserve
any other intended assignments in the multi-select and log the driver in again.
Do not create a duplicate driver. The underlying endpoint is
`PUT /auth/admin/accounts/{account_id}/vehicles` with `{"ids":[...]}`; the UI supplies
the authenticated request. No assign-driver CLI currently exists.

Admin Routes → select the same vehicle/direction and configure a feasible current
plan → **Generate route** if required (explicit generation, not polling). Driver
login with Authenticated operations opens **Stored route plan**, not the synthetic
DriverDashboard. Select the authorized vehicle and direction, scroll to
**Persistent trip lifecycle**, choose production pickup mode/scope as appropriate,
then **Create planned trip (manual prototype)** and **Start trip (manual prototype)**.
These call POST /trips with route_id, then POST /trips/{trip_id}/start. Existing
active-trip and saved-route checks remain enforced.

In the **Vehicle-bound tracking authorization** section above the trip controls,
select **Enroll phone sender for active trip** (POST /tracking/enroll). Only after
successful phone enrollment does **Actual phone GPS — foreground browser → Start
sharing** appear. Synthetic vehicles instead expose **Enroll simulation sender
for active trip**, with an explicit explanation that actual phone capture is
unavailable. A blank/expired/missing credential never enables an anonymous bypass.

### Accepted positions versus measured observations

The Driver GPS card and Admin Dashboard/Live Fleet display the authorized latest
sample. Accepted history exists in PostgreSQL vehicle_positions, including
accuracy_m and tracking_session_id. For a bounded recent listing without exposing
coordinates or credentials:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe verify_phone_capture.py --tracking-id DEVICE_ID_FROM_DRIVER --limit 20
```

Authorized HTTP endpoints are GET /routing/vehicles/{vehicle_id}/positions/latest
and GET /routing/vehicles/{vehicle_id}/positions?limit=20&window_seconds=3600.
The latter optionally accepts trip_id; bounds are enforced by the backend.
Use the frontend's existing authenticated API requests/Network panel or a trusted
local client. Direct browser navigation does not attach the app's bearer header
and therefore returns 401. Do not copy tokens into URLs, screenshots or logs.

GPS points are device observations, **not** automatically measured segment travel
times. There is currently no measured segment-observation table, extraction job,
observation-list GET endpoint or measured training pipeline. The existing
POST /exports/measured-observations validates user-supplied observations with a
lineage guard; it is administrator-only. The local export CLI does the same with
local database access. Neither infers duration targets from GPS automatically.

Only if you already have a separately reviewed observation JSON file containing
data_source='measured', a real duration_s, and at least two distinct position_ids
as evidence, validate/export it privately with the actual existing command:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$observationInput = Read-Host 'Full path to your existing reviewed observation JSON'
$observationOutput = Read-Host 'Different full output path in an existing private directory'
.\.venv\Scripts\python.exe export_measured_observations.py --input $observationInput --output $observationOutput
```

Do not invent targets, label synthetic observations measured, overwrite the
synthetic training CSV or retrain based on this phone feature. The lineage gate
does not establish target-extraction accuracy or physical device authenticity.

- watchPosition uses high accuracy, maximumAge=0 and 15-second acquisition timeout.
  Each sample uses the browser observation timestamp and a new crypto UUID;
  negative/unavailable speed becomes null, never zero. Capture is throttled to
  at most one observation every five recorded seconds.
- Queue is memory-only, maximum 30 samples, maximum age 120 seconds, five attempts
  per sample, exponential retry up to 30 seconds and eight-second upload timeout.
  Queue-full/expired samples are discarded and counted. No background service
  worker or durable queue is claimed. Errors/refresh never silently use simulation.
- Server rejects expired/revoked credentials, assignment/trip forgery, closed-trip
  backlog, samples predating enrollment/trip start, and >30-second future timestamps.
  Duplicate samples produce no duplicate downstream transition. Out-of-order
  samples are retained without advancing latest or proximity/anomaly processing.
- New phone samples require finite nonnegative accuracy_m. Optional backend
  GPS_POOR_ACCURACY_METRES defaults to 50 (range 1–1000). Larger-radius samples are
  persisted as poor, latest usability becomes unknown, and arrival/anomaly
  transitions and measured-data export eligibility exclude them. Old null accuracy
  remains unknown. GPS confidence is not proof of driver identity or physical GPS
  authenticity; browser inputs can be spoofed even with authenticated provenance.
- Chrome hidden-tab transitions pause capture; screen lock, battery optimization,
  OS suspension, browser closure or lost permissions can interrupt tracking.
  Foreground-browser capture is not reliable background fleet tracking. Missing
  GPS is never interpreted as stopped, and proximity never confirms passengers.

## Repeatable local checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_AUTH_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_data_provenance.py -v
Set-Location ..\frontend
node scripts/verify-phone-capture.cjs
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
```

Browser tests intercept location/upload responses; they are explicitly synthetic,
not actual phone evidence. Database security tests use rollback-only fixtures.

After local testing, stop Vite, remove the phone CA if no longer needed and remove
the optional firewall rule from an elevated PowerShell terminal:

```powershell
Remove-NetFirewallRule -DisplayName 'SafeRide local phone HTTPS'
```
