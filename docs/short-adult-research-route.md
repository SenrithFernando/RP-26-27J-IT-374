# Isolated adult A → B → C → A research route

Implemented 2026-10-19. This prepares a reviewed fixed itinerary, not an optimized school plan. No real short route/trip/pin or measured observation was created by implementation or tests. Supplied coordinates remain absent until the operator confirms them. No Google request or model training was performed.

## Separation from school operations

Reuses RouteVersion/RouteStop, trip lifecycle, authorization, scoped phone sessions, arrival detector, monitoring, navigation and observation collection. Research versions have explicit `research_journey` metadata and separate retrieval; school latest/published route retrieval and planning-state writes exclude them. School deadlines, attendance, assignments, service/window rules and historical snapshots are not modified. Research creates no student roster, passenger actions, pickup windows/outcomes or missed-pickup notifications.

The database's legacy direction field remains `afternoon` for schema compatibility; the UI labels it **Adult research**, and `/research-routes/current` retrieves it separately. It is not published as an afternoon school plan. Version numbers share the vehicle's existing unique namespace; existing school version IDs/values are unchanged. Starting/closing research does not replace the school RoutePlanState. Active trip/vehicle conflicts remain enforced.

Migration `0019_research_unknown_eta` makes `route_stops.eta_seconds` nullable. Existing values are untouched. Research stores unknown ETAs as NULL, not copied departure timestamps. Driving/waiting/total estimates remain unknown; no travel-time provider is called. Research has zero planned passenger service. The supplied order is fixed; no optimum or road route is claimed.

## Supplied locations preserved

- A: **SALT EduWay — reviewed research stopping point**. Place address: **SALT EduWay, 488/2 Lake Road, Averihena, Hokandara, South, Battaramulla 10118**. Separately supplied stopping-point address: **25 Wewa Rd, Sri Jayawardenepura Kotte 10115**. Both are preserved verbatim in the reviewed input snapshot. They may differ; neither is silently equated with the other.
- B: **CEB Battaramulla landmark**. **CEB Battaramulla 132/33KV Grid, WX66+P9G, Wewa Rd, Sri Jayawardenepura Kotte 10115**. Review a permitted public roadside point **outside the electrical facility**. A lookup/building centroid is not confirmation of a permissible vehicle stop.
- C: **The Best "B" bakery**. **The Best "B", WX47+GPP, Malabe**. Review an accessible stopping point.

Supplied texts stay read-only above the existing lookup/pin controls. Optional **Look up address** is explicit and may call the configured backend provider; setup never calls it automatically. Lookup suggestion/method and reviewed address are kept separately from supplied text. Manual map review and explicit accessible/public-stop attestations are required even after lookup. These attestations are not independent permission or survey verification.

Named latitude/longitude fields validate ranges and finite values; review the map to catch swaps that are numerically valid in both ranges. Adjacent A–B, B–C and C–A must each be farther apart than twice the configured arrival exit radius (currently **more than 150 m**). No coordinates are guessed or seeded.

A uses one stable location ID but **two distinct stop occurrences/event IDs**, 1 and 4. All four ordered stops are saved, including the explicit C→A return. Initial A is monitored first. Arrival and Next stop processing is occurrence-specific; initial A does not create a final-A arrival. Existing thresholds (50 m entry, 75 m exit, 15 s dwell, three observations, max gap 10 s, freshness 20 s) are unchanged.

## Operator and driver

Select an existing active assigned driver and a **different existing administrator** as phone operator. No account, profile or assignment is created/reset. Distinct account IDs and an explicit declaration record that they are separate people while moving; the system cannot independently establish physical identity.

The selected driver retains scoped trip/navigation/advance controls. Only the selected administrator/operator may enroll/capture phone GPS for the research trip, and this binding is checked on uploads. Driver/parent/demo access restrictions remain; a different assigned driver does not gain access to the selected research driver's route. Adult approval is still a separate explicit administrator action, valid for today's trip and bounded to two hours. Research never falls back to a simulation sender; legacy simulation/replay ingestion is refused for a research trip. Separate simulation trips continue to work.

Travel mode has **no default**. Select driving, walking or bicycling explicitly; the Maps link uses that selection. Non-driving research can record GPS, but cannot be accepted as a vehicle travel-time label through the current reviewed extractor. No speed, weather, ETAs or predictions are manufactured.

## Exact setup order and actual UI labels

1. Restart the backend after the migration and refresh Vite. Log in to **Authenticated operations** as administrator. Open **Adult research** in the top navigation.
2. Set **Research service date** (initial 2026-10-19) and **Research departure (Asia/Colombo)** (initial 18:00). Both are editable. Save requires a future departure. If preparation finishes later, choose a later real time/date; do not backdate starts or change the computer clock. Actual start is recorded by the backend. If an unstarted plan is over ten minutes late at start, save a new reviewed version with a later departure. Never retime an ACTIVE trip.
3. Choose **Research travel mode**, **Assigned research driver** (existing `driver.local` when appropriate), and **Separate phone operator (existing administrator)**. Confirm **I confirm the operator and driver are separate people while moving** and **Consenting adults only; no student transport**.
4. For each **Research stopping point A/B/C**, inspect supplied texts. Optionally click **Look up address**, then correct the pin using the existing preview/draggable pin or explicit **Latitude/Longitude** fields. Check **I confirm this address and pin position are correct**, then the additional **I manually reviewed this accessible, permitted public stopping point** checkbox (B explicitly says outside the electrical facility). Fill **Stopping-point review note**. Editing an address/pin clears confirmation and the public-stop attestation. A is confirmed once and reused only for the final return coordinate.
5. Enter **Research route review reason**, click **Save reviewed research route**. This saves an immutable reviewed version; it does not create/start a trip or accept an observation. Identical preparation retries reuse the same unstarted version. Server-side validation repeats all checks.
6. Click **Open research driver/operator view**. It opens the existing Driver component with **Route workspace → Isolated adult research route** and the selected date/vehicle. An assigned driver can also select this workspace in their normal Driver view. Click **Create planned trip (manual prototype)** once, or locate the existing matching PLANNED trip. No school pickup-mode choices/windows apply to research.
7. Record its Trip ID. Administrator **Access → Adult landmark phone test authorization**: enter this research Trip ID, record an adults-only research reason, confirm consent, click **Authorize adult landmark phone test**. Do this shortly before capture so the two-hour authorization covers the intended journey.
8. Administrator **Adult research → Evaluation — reviewed travel-time collection → Prepare collection and review boundaries**: enter the Trip ID, select **Moving adult landmark research**, consent/reason, then **Prepare collection for planned trip**, while still PLANNED. No automatic collection or label acceptance occurs.
9. In the shared research Driver/operator view, use **Start trip (manual prototype)** shortly before physically leaving so initial-A observations are available. No automatic start is performed. Only today's plan may start, with actual server time and no other active trip for the vehicle.
10. On the selected separate operator's tracking phone, log in as that administrator, open **Adult research → Open research driver/operator view**, and **Enroll phone sender for active trip → Start sharing**. The driver's account is deliberately not the research capture operator. Check **Last successful backend upload**, upload/GPS age, accuracy and source. A browser capture message alone does not prove an accepted upload. Existing HTTPS/proxy configuration is required.
11. At initial A, wait for actual fresh GPS arrival/dwell. Use **Next stop (manual; no passenger confirmation)** to select B. Follow B, C, then final A using the same action after each actual arrival. **Navigate to next stop** and **Copy link for navigation device** use the selected mode/confirmed occurrence and never advance the trip. Keep the tracking phone's Chrome foregrounded/screen awake; use a second navigation device for Maps. Do not operate the phone while driving.
12. At final A, wait for fresh arrival specific to occurrence 4. Then **Stop sharing → End trip (manual prototype) → Confirm end trip → Revoke**. No student action is implied. Review segments **1→2, 2→3, 3→4** in the existing Evaluation controls later. Never use initial A as final-return evidence. GPS gaps, unknown/poor accuracy and interruptions remain flags; no automatic acceptance occurs.

If departure/pins must change before starting, save a new reviewed version. An older PLANNED trip remains historical and cannot start against the newer research version; cancel it deliberately through existing controls and create the trip for the new version. Do not edit/start the old stationary or interrupted school-route trips.

## Field checklist

- Confirm the actual A stopping point against both supplied addresses.
- Confirm B is a permitted roadside stop outside the facility and C is accessible.
- Confirm A/B/C pins and all three adjacent separations; choose actual mode.
- Select assigned driver and separate administrator/operator, consent and review notes.
- Future departure, correct local date, latest reviewed research route/version.
- PLANNED trip → adult approval → collection preparation → explicit start → operator phone enrollment/sharing.
- Fresh accepted uploads and acceptable accuracy before leaving initial A; not merely “sample captured”.
- Initial A arrival → explicit Next stop → B → C → final A occurrence.
- Foreground tracking phone; second navigation device; no mock boarding/card events.
- Explicit closure/revocation, then manual segment review; preserve rejected/pending evidence.

The live navigation panel groups current occurrence/index, confirmed destination/link, last backend-accepted upload and age, recorded GPS age, accuracy, distance, arrival/observation status and specific prerequisite/error. Position requests are scoped to the selected trip so an older trip's successful upload is not presented as the new research journey's upload.

## Tests and verification evidence

Rollback-only short-route tests passed: required mode and distinct people, coordinate/public/manual confirmation validation, separation, past-time rejection, immutable/idempotent preparation, distinct A occurrences, no passenger actions/windows, operator-only enrollment, simulation enrollment refusal, parent denial, explicit advancement, terminal-trip protection and school planning-state/latest isolation.

Seven existing authorization regressions, eight observation/review/provenance API tests and two saved-navigation tests passed. Intercepted mobile preparation UI passed: actual Admin navigation, both A addresses, blank initial pins/mode, explicit confirmations, three submitted pins, no automatic geocoding/start/observations. Navigation UI regressions passed at 320/390 px: targeting/order, copy/open without advancement, failures/unknown pins, final stop and mobile layout. These use synthetic rollback/intercepted fixtures, not physical evidence. No real short research version remains after tests.

TypeScript and frontend build passed. Vite reports a nonfatal main-chunk >500 kB advisory; no build failure. Existing TestClient/httpx deprecation warning remains. No physical moving test, road geometry verification, navigation handoff accuracy or real-world ML accuracy is claimed.

Read-only preservation check: earlier stationary trip remains COMPLETED with **225 samples**, interrupted trip remains COMPLETED with **54 samples**, and no short research RouteVersion was persisted by tests. School PM v28 remains saved; it is currently stale following the earlier completed execution and has not been republished or rewritten by this feature.

## Windows commands

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Migration applied locally: **0019_research_unknown_eta**. Stop/restart an old backend process to load the new routes; keep PostgreSQL/FastAPI private. Existing phone HTTPS/Vite setup is unchanged. Only start `npm run dev` if Vite is not already running on 5173.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_SHORT_RESEARCH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_short_research_route.py -v
Remove-Item Env:SAFERIDE_RUN_SHORT_RESEARCH_TESTS
Set-Location ..\frontend
npx tsc --noEmit
npm run build
$env:SAFERIDE_UI_TEST_URL='http://localhost:5173' # use the actual existing HTTPS origin if configured
node scripts/verify-short-research.cjs
node scripts/verify-driver-navigation.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
```

New endpoints: admin POST `/research-routes`, admin GET `/research-routes/template`; real scoped driver/admin GET `/research-routes/current?vehicle_id=...&service_date=...`. Preparation requires mode, people/consent, date/departure/reason and three reviewed pins. Trip, approval, collection, phone upload and advancement endpoints are reused.

### Rescheduling an unused, late PLANNED research trip

The saved departure cannot be edited in place. Keep the original route and cancel its unused trip deliberately; save a new reviewed version with a future Colombo departure. Do not backdate or change the clock.

1. Admin → **Adult research** → select **Research service date** → **Reuse saved research review for selected date**. This GET restores confirmed A/B/C pins, review notes, travel mode, driver/operator and consent selections without a server mutation. It reports the current trip ID/state. Check that these remain valid.
2. **Open research driver/operator view** → verify the old trip ID is PLANNED → **Cancel trip deliberately** → **Cancellation reason** (record that a later departure will supersede this unused trip and name its route/version) → **Confirm cancellation**. Never cancel an active/completed evidence trip as a rescheduling shortcut.
3. Return to Adult research, reuse the saved review if needed, change **Research departure (Asia/Colombo)** to a future time, retain/review the restored information, then **Save reviewed research route**. Record the replacement route ID/version. The old immutable review remains available in history.
4. **Open research driver/operator view** → verify the new route/version → **Create planned trip (manual prototype)**. Record the NEW trip ID. Do not click Start yet.
5. **Access** → **Adult landmark phone test authorization** → enter the NEW trip ID, reason and adult consent → **Authorize adult landmark phone test**. The old two-hour trip/route-bound grant is not transferable.
6. Adult research → evaluation controls → **Research trip ID** (NEW ID) → **Prepare collection and review boundaries** → **Moving adult landmark research**, consent and reason → **Prepare collection for planned trip**. Collection preparation is trip-specific and must be renewed; old samples/observations are not moved.
7. When physically ready and within the permitted start time, explicitly use **Start trip (manual prototype)**; the selected separate operator then enrolls a NEW phone tracking session for this active trip. Old tracking credentials must not be reused. No start/enrollment happens as part of reloading or saving a review.

Read-only inspection on 2026-10-19 found route v30 `RROUTE_9087bb7e07074caabdbad2da10e4588a`, departure 19:00 Colombo, trip `TRIP_c5f8ac99621446ef8bf0664362082653` PLANNED with no start, positions, arrivals, observations or tracking sessions. No replacement research version and no active VAN_01 trip existed at inspection. Its existing moving-adult collection and approval remain historical and are not copied. No real trip was cancelled/created/started by this checkpoint. Recheck current state before following these actions.

Main changes: new `backend/research_routes.py`, migration `0019_research_unknown_eta.py`, `test_short_research_route.py`, frontend `pages/AdultResearch.tsx`, `scripts/verify-short-research.cjs`; updated existing route freshness/serialization, trips, arrivals, authorization/tracking, observation mode gate, authenticated navigation, shared Driver/GPS/navigation/map types and display. No new account system, provider, SDK, dataset or trained model was added.
