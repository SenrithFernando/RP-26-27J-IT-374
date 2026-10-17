# Stage 3: confirmed locations and Leaflet maps

## Behavior

React remains version 18.3.1. Before installation, `npm view react-leaflet@4.2.1 peerDependencies --json` returned React/React DOM `^18.0.0` and Leaflet `^1.9.0`. Installed pinned Leaflet 1.9.4, React Leaflet 4.2.1 and @types/leaflet 1.9.21. `npm ls` confirmed compatible peers.

`RouteMap` is reusable for route display and registration previews. It supports home, school, vehicle start/end markers; ordered marker numbers; escaped React popups; automatic bounds; loading and tile/API errors. Leaflet is lazy loaded. OpenStreetMap attribution remains visible. OSM provides basemap tiles only; it is not the routing, traffic or geocoding provider.

The route line is labeled **Stop sequence — not a road route**. It joins confirmed coordinates in backend stop order, with no road geometry, traffic lookup, distance calculation or new ETA calculation. It is withheld when an ordered stop lacks a confirmed coordinate. New homes can appear as location markers without belonging to the prototype optimized sequence. Selecting a vehicle without a prototype result shows locations only.

Existing unknown locations remain null/unconfirmed. No coordinates were invented for them. Registration requires an address, valid coordinate pair and explicit location confirmation. Address edits, coordinate edits, map clicks, pin dragging and new geocoding results clear confirmation. Manual input and manual corrections are labeled separately from Google results. Map popups separate record provenance from location provenance; a successful Google result is live provider location input, not an ML prediction or measured travel observation.

## Commands

Backend (PowerShell):

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Reuse the running updated server if already on port 8000. Migration `0003_confirmed_locations` has been applied locally; rerunning upgrade is safe. No automatic migration or seeding occurs on startup.

Frontend (separate terminal):

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm.cmd install
npm.cmd ls react react-dom leaflet react-leaflet
npm.cmd run build
npm.cmd run dev -- --host 127.0.0.1
```

## Optional Google geocoding

Edit `backend/.env` locally; do not expose or commit it. Add these values only if using Google:

```dotenv
GEOCODING_PROVIDER=google
GOOGLE_GEOCODING_API_KEY='enter your backend key locally'
```

Enable the Google Geocoding API for that key and configure access/billing in your Google project. Restart the backend after changing configuration. `GEOCODING_PROVIDER=auto` selects Google only when a key exists; otherwise it uses manual mode. `GEOCODING_PROVIDER=manual` explicitly disables provider calls. The supported providers are currently manual and Google.

Only the backend calls Google. The browser posts an address to `/api/routing/geocode`; it never receives the key. Do not set a `VITE_` variable containing provider credentials. Failed, denied, malformed and zero-result responses do not return placeholder coordinates. The UI allows manual entry/map correction regardless of lookup failure. A returned address match still requires confirmation; partial matches are labeled for review. Lookup requests are canceled/ignored after newer edits or unmount.

## Browser test: add and see a new marker

1. Open `http://127.0.0.1:5173` and choose **Administrator > Students**.
2. Click **Add Student**. Enter a clearly synthetic name. Select **Stage 3 synthetic test school (SCHOOL_STAGE3_TEST)** and **VAN_STAGE2_TEST** to use the retained test fixtures, or choose your intended database records.
3. Choose **Simulated input** for the test. Enter address `Synthetic test home, Colombo` and coordinates latitude `6.9271`, longitude `79.8612`.
4. Without a Google key, **Look up address** shows a configuration message. It does not claim a match or invent a coordinate. The manual fields and map remain usable.
5. Drag the preview pin to correct it. Its coordinates update. Check **I confirm this address and pin position are correct.** Save. Without confirmation the form stays open with validation feedback.
6. Go to **Routes**, select **VAN_STAGE2_TEST** in **Map vehicle**, and locate the new home marker. Click it to see the saved address, coordinates, manual method and provenance. It is explicitly not part of the prototype optimized sequence.
7. Refresh the browser, reopen Administrator > Routes and select the same map vehicle. The persisted marker remains. Inactive students are excluded from the route map.
8. Click **Configure map locations** to set a school's location or a vehicle's start/end. Select the target, enter an address and coordinates, review/drag the pin, confirm, then **Save confirmed location**. This updates PostgreSQL and refreshes map bounds. Use explicitly simulated coordinates only for synthetic records.
9. For the current VAN_01 prototype sequence, confirm the three seed homes through Students, SCHOOL_01 through Configure map locations, and VAN_01's start/end. Once every selected-direction stop is confirmed, its numbered markers and sequence polyline appear. No road route is claimed.
10. Test errors with DevTools Network Offline: tile/data errors are visible. Manual coordinates remain available, and a failed save does not close the form. Restore connectivity and retry.

Existing seed students now require an address and confirmation when edited. Their IDs and home IDs are preserved. The seed remains insert-only and does not claim locations have been confirmed.

## API additions

- `POST /routing/geocode`: `{ "address": "..." }`; provider result is unconfirmed. Manual/no-key returns a useful 503 without coordinates.
- `PUT /routing/schools/{id}/location`.
- `PUT /routing/vehicles/{id}/locations/start` or `/end`.
- `GET /routing/map-locations/{vehicle_id}?direction=morning|afternoon`: confirmed active homes, schools and vehicle endpoints, plus missing-location names.

Location writes require `address`, `latitude`, `longitude`, `location_confirmed: true`, and `location_method` (`manual`, `google`, or `manual_correction`). Student create/edit additionally requires `home_address`, `location_confirmed: true`, and the optional/default-manual `location_method` alongside Stage 2 fields. The backend independently validates ranges and confirmation. No new road routing, traffic provider, ML model or automatic re-optimization was added; existing prototype route endpoints remain operational.

## Files

- Backend: `models.py`, `persistence.py`, `main.py`, `.env.example`; new `geocoding.py`, `locations.py`, `migrations/versions/0003_confirmed_locations.py`, `tests/test_geocoding.py`.
- Frontend: `package.json`, `package-lock.json`, `services/api.ts`, `pages/StudentsPage.tsx`, `pages/RouteOptimization.tsx`; new `components/RouteMap.tsx`, `MapLoader.tsx`, `LocationPicker.tsx`, `RouteLocations.tsx`.

## Verification and limits

- Migration applied; Alembic detected no model/schema drift. Dependency consistency checks passed.
- Four backend tests passed: provider success, failure/invalid result handling, no-key configuration and confirmation validation. Provider responses in adapter tests were synthetic; no live Google request was made because no backend Google key is configured.
- Real browser/database test registered `STU_65a7116e79d240bbbc57afd2f47718fc` after a manual drag and confirmation. Its saved manual coordinates are latitude `6.9265121`, longitude `79.8622370`, address `Synthetic test home, Colombo`. Independent PostgreSQL reads confirmed the data and confirmation.
- Retained synthetic school `SCHOOL_STAGE3_TEST` and confirmed synthetic start/end locations on existing synthetic vehicle `VAN_STAGE2_TEST`. Four actual database marker types appeared together. Original seed locations were not changed.
- Both direction marker numbers, sequence polyline, automatic bounds, missing-location behavior and map errors were checked with intercepted synthetic point responses; those point fixtures were not saved. Automated tests stubbed tiles to avoid automated OSM tile fetching. Live OSM tile availability is not claimed by these checks.
- UI checks covered confirmation invalidation after dragging/editing, no-key fallback without invented coordinates, manual correction labels and ignoring stale geocoding responses. Synthetic Google UI responses were canceled without saving.
- Production build passed; Leaflet is a separate lazy chunk. Full TypeScript checking still reports the existing unused-import/PNG-declaration errors elsewhere, with no errors in changed files.
- npm install reported 18 audit findings (3 moderate, 15 high) across the dependency tree. Broad dependency upgrades were not part of this stage.

Sources: [React Leaflet v4 setup](https://react-leaflet.js.org/docs/v4/start-setup/), [Google Geocoding requests](https://developers.google.com/maps/documentation/geocoding/guides-v3/requests-geocoding), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).
