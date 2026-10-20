# PP1 routing workspace usability checkpoint — 2026-10-20

Frontend-only changes. Existing backend permissions, planning, thresholds, trip
transitions and provenance rules are unchanged. No database records, GPS evidence,
model artifacts or training labels were modified. No paid provider calls were made.

## Demonstrated gaps fixed

- Evaluation Review / correct populated a collapsed editor without opening or
  focusing it. It now opens, scrolls to and focuses the selected observation;
  boundaries, intervals and dataset are restored, with prior revisions retained.
- Dwell evidence required raw JSON. Structured start/end (offset timestamps),
  kind and reason fields now feed the same API payload. Raw JSON remains under
  Advanced. Invalid structured intervals show a local error, not a made-up duration.
- Submission guards now synchronously block rapid repeated clicks in Daily Plan,
  trip actions and Evaluation. Pending/success/error feedback stays visible;
  failed review saves retain the selected editor. These UI guards do not replace
  backend idempotency or authorize any new action.
- Driver vehicle/date/planning version/publication and trip state/fixed version
  are visible outside diagnostics. Create planned trip and Start trip remain
  separate actions. Completed trips retain Fixed trip itinerary and estimates.
- Driver footer incorrectly said navigation was disconnected. It now distinguishes
  external next-stop navigation from unimplemented embedded turn-by-turn.
- At 320px the Daily Plan estimate-provider dropdown widened the document to
  328px. Its label/control now stay within the viewport. Attendance remains a
  locally scrollable table, without widening the whole page.
- Daily Plan now outlines attendance → location → recommendation/generation →
  review → publication, warns about unsaved attendance, explains disabled live
  recommendation prerequisites and no longer describes every SCH_B pin as pending.

Notifications already separate Alert generation and Hasara parent-channel
delivery. This was retained; no delivery success is inferred from an in-app event
or read state. Actual source badges and synthetic-trained ML limitations remain.

## Laptop walkthrough

Use existing private credentials. Backend in terminal A:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep one frontend instance on port 5173. If none is running, terminal B:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

1. Administrator → **Daily Plan**. Select the service date. Confirm vehicle,
   capacity and independent AM/PM counts. Edit attendance; the unsaved-attendance
   warning must appear. Use **Save dated attendance**, waiting for success.
2. Review **Location review**. With a free provider selected, use **Recommend AM
   departure**, or **Validate AM override** for an explicit selected time. PM uses
   **Generate PM plan**. Review saved route ID/version, actual provider, departure,
   grouped stops and duration totals before **Publish reviewed AM plan** /
   **Publish reviewed PM plan**. Publication blockers remain beside each plan.
   Google controls remain explicit opt-in; this walkthrough requires no paid call.
3. In a separate browser profile log in as the assigned driver. Select **Published
   school plans**, authorized vehicle, matching date and **Morning Pickup** or
   **Afternoon Drop-off**. Use **Refresh route**. Compare the prominent route
   version with Admin; an AM draft is not published instructions.
4. On an eligible current-date plan only, **Create planned trip (manual prototype)**
   creates PLANNED, not ACTIVE. Inspect **Fixed trip itinerary and estimates**,
   then **Start trip (manual prototype)** when backend time/authorization rules
   permit. Do not start future trips or reuse completed physical-test trips.
5. Under **Vehicle-bound tracking authorization**, follow the displayed ACTIVE
   trip / adult approval / separate research operator prerequisites. Use **Enroll
   phone sender for active trip**, then **Start sharing** where authorized. The
   actual phone capture control owns permission/upload messages. Missing GPS and
   speed remain unknown. Do not create synthetic evidence to exercise controls.
6. On an active trip use **Navigate to next stop** or **Copy link for navigation
   device**. Opening a link does not advance. After confirmed arrival use **Next
   stop (manual; no passenger confirmation)**. At final arrival close deliberately
   with **End trip (manual prototype)** → **Confirm end trip**. Fixed itinerary
   remains available afterward; closure does not confirm passenger delivery.
7. Admin → **Notifications**. Compare **Alert generation** with **Hasara
   parent-channel delivery**, event/deadline timestamps and read state. Disconnected
   delivery is not delivered. Do not expire or alter real windows for this demo.
8. Evaluation is available on **Daily Plan** and the separate **Adult research**
   page. Enter an existing research trip ID → **Refresh evaluation** → **Review /
   correct segment**. The selected observation editor must open and receive focus.
   Inspect restored sequence/boundary IDs. Add observed intervals using **Interval
   start**, **Interval end**, **Interval kind**, **Interval reason** → **Add observed
   interval**; inspect raw JSON only under **Advanced**. Choose **Review decision**,
   provide **Research review reason**, then **Save review revision** only if you
   intend an audited review change. Otherwise **Cancel review**. **Download reviewed
   research export** exports backend-eligible reviewed records only; no automatic
   acceptance or retraining occurs. Keep downloaded private JSON outside Git.
9. For a new isolated adult journey use **Adult research**, never school attendance
   edits to relax school rules. Existing collection preparation precedes capture;
   candidate creation follows capture and boundary review. Stationary samples are
   not moving-segment labels. Geofence targets remain separate from centroid-model
   targets. Existing adult authorization/driver/operator separation still applies.

## Phone layout walkthrough

Use the already configured trusted HTTPS phone origin and `/api` proxy described
in `phone-https-setup-current.md`; do not reuse a historical IP after reconnecting
the hotspot. In PowerShell inspect the **Wi-Fi** entry's IPv4/default gateway:

```powershell
Get-NetIPConfiguration | Select-Object InterfaceAlias,IPv4Address,IPv4DefaultGateway
```

If the Wi-Fi IP changed, renew the certificate and scoped frontend firewall rule
using the existing setup guide. Do not expose FastAPI or PostgreSQL. With the
matching existing certificate, start the single HTTPS frontend in terminal B:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$phoneHost = Read-Host 'Current laptop Wi-Fi IPv4 shown above'
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
$env:SAFERIDE_HTTPS_HOST = $phoneHost
$env:SAFERIDE_HTTPS_CERT = Join-Path $tlsDirectory 'phone-cert.pem'
$env:SAFERIDE_HTTPS_KEY = Join-Path $tlsDirectory 'phone-key.pem'
npm run dev
```

On Android Chrome open `https://<that-laptop-Wi-Fi-IP>:5173`, never phone localhost.
Log in, repeat steps 3 and 8 read-only. Confirm the header/footer do not cover the
scrolling route/trip/GPS content, the summary wraps, and review opens the editor.
For navigation use a second device: opening Maps can background Chrome and interrupt
foreground tracking. This checkpoint did not verify physical Android handoff or GPS.

## Automated verification

Seven intercepted browser suites passed: driver boundary, navigation, durations,
Daily Plan, short research, operations cleanup (nine states), and the new workspace
usability suite. The latter checks review focus, interval validation, rapid double
submission, error retention, export and 1366/320/390px layout. The operations test's
old expected `Google traffic-aware estimate` label was updated to the existing
`Google Maps traffic-aware estimate`; no provider behavior changed.

TypeScript no-emit and frontend production build passed. Existing >500kB Vite
chunk warning remains. UI responses were intercepted synthetic fixtures, including
exports and save requests. This is UI verification, not a new backend/field test.

In a separate frontend terminal start a local test server:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npx vite --host 127.0.0.1 --port 5187
```

Run in the frontend test terminal:

```powershell
$env:SAFERIDE_UI_TEST_URL='http://127.0.0.1:5187'
node scripts/verify-workspace-usability.cjs
node scripts/verify-driver-boundary.cjs
node scripts/verify-driver-navigation.cjs
node scripts/verify-driver-durations.cjs
node scripts/verify-daily-plan.cjs
node scripts/verify-short-research.cjs
node scripts/verify-operations-cleanup.cjs
.\node_modules\.bin\tsc.cmd --noEmit --incremental false
npm run build
```

No new app, dashboard, authentication system or backend endpoints were introduced.
Prior unrelated uncommitted authentication reports are preserved.
