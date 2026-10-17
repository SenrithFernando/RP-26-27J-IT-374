# Stage 9D: persistent missed-pickup in-app events

## Implementation and reuse

Existing AppContext notifications, Admin Notifications and Parent overlay were inspected. AppContext stores demonstration notifications only in React. Their safety/camera/RFID/emergency demonstrations remain separate. The existing Admin Notifications page and Parent Notifications overlay now include a dedicated persisted database inbox, using the shared API fetch/error service. Stored events are never merged into an ALL-role/demo broadcast list.

When the Stage 9C expiry path changes an individual waiting outcome to MISSED, it inserts one notification in the SAME PostgreSQL transaction. This includes worker expiry, late-confirmation expiry and trip-lifecycle expiry. Failure to create the notification rolls back the MISSED transition. Picked-up/cancelled outcomes are skipped and create no missed alert. The existing worker still expires windows without browsers and after restart; no extra scheduler was introduced.

missed_pickup_notifications links trip, registered vehicle, saved route/stop, window and student outcome. The composite window/student foreign key preserves historical context even after student deactivation. Snapshot student name and a message state only that the pickup window expired without recorded confirmation; this is not independent evidence that a child physically failed to board.

Unique(trip_id, student_id, kind) and a PostgreSQL conflict-safe insert enforce one event per logical pickup, including shared-school windows. Existing trip/window locks serialize expiry; the uniqueness constraint also protects direct/concurrent duplicate insertion. One event is shared by Admin and relevant Parent, not two recipient copies. Event ID, timestamp, message and source do not change when read or repeatedly processed.

occurred_at is the effective deadline; created_at is backend processing time. Both are timezone-aware and displayed as Sri Lankan time. Sources include expiry processor and the arrival position source (simulation/actual_device/unknown), plus stored production/demo window mode. Delivery status is always in_app_event_created. No SMS, email, push adapter or delivery acknowledgement was added. No external message was sent during implementation/testing.

Stage 9C windows already MISSED before this migration are not retroactively broadcast/backfilled. Existing history is retained; new Stage 9D MISSED transitions create their event atomically. Synthetic test records are labelled and are not measured passenger journeys; controlled boundary cases in the earlier pickup suite are not physical travel observations.

## Recipient filtering and access limitation

There is no real authentication, parent account/child association or server-verified role in this prototype. The inbox selector and API recipient values are FILTERS, NOT authorization. Anyone with API access can impersonate another student or select the prototype admin inbox. Production use requires authenticated principals, server-derived role/student permissions and per-user read receipts before real student information can be protected.

Within this prototype contract:

- Admin inbox intentionally includes all stored missed-pickup events.
- Parent requires an explicit nonempty database student_id. Missing/empty parent selection is rejected, never interpreted as all students. The SQL query and unread count filter by this student before pagination/serialization.
- Parent UI initially loads no events. It asks for a known test student ID; it does not download a directory of other students, home coordinates or all notification details for client-side filtering.
- Editing the selected ID immediately hides old event details, cancels obsolete requests and requires explicit selection. Old responses cannot overwrite another recipient's view.
- A parent read-state change also includes the selected student ID. A mismatched event/student returns 404 without event details.
- The selected database recipient is clearly separate from the legacy demonstration child shown elsewhere in Parent. Reload requires explicit recipient selection again; the stored event/read state survives.

No event is broadcast to unrelated selected Parent views. This verified filtering behaviour is not a claim of production access control.

One admin_read_at and one parent_read_at are persisted per event. They are independent: Admin reading does not mark Parent read. With no user accounts, these are shared prototype Admin/student-parent read states, not separate receipts for multiple real parents/admins. Repeated mark-read retains its original read timestamp; mark-unread clears only the chosen recipient's state.

## API / UI

- GET /routing/notifications?recipient=admin
- GET /routing/notifications?recipient=parent&student_id=...
- Optional limit (1-200, default 50), before_order_id cursor; newest events first, truncation flag and next cursor. Scoped unread_count uses the same recipient filter.
- PATCH /routing/notifications/{id}/read with {"recipient":"parent","student_id":"...","read":true} or admin without student_id. Admin/student combinations are rejected instead of silently broadening scope.

Indexes cover student/order, Admin unread and student-parent unread queries. Database uniqueness is separate from UI deduplication. GET requests do not expire windows, create events, mark read automatically or run optimization.

Admin -> Notifications shows Database missed-pickup events above separately labelled other component demonstration notifications. Parent -> notification bell opens the existing overlay, where the same persisted component requires explicit database recipient selection. Each card includes student, vehicle, trip, stop/window, effective deadline, creation time, source/mode, in-app status and read/unread action. Existing navigation badges/legacy alerts remain demonstration state; the database section reports its own actual scoped unread count.

Polling is serialized every five seconds while visible, with request timeout, abort/obsolete-request protection and cleanup on recipient/page/unmount changes. API failures are shown; no mock events are substituted. Read errors do not silently mark an event read. Older-page navigation remains bounded.

## Migration and checks (Windows PowerShell)

From project root:

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
npm --prefix .\frontend run build
```

Applied head: 0011_missed_pickup_notifications. No new runtime dependencies. Existing backend/.env credentials were not printed or changed. Downgrade requires explicit archival of notification events/read states.

Focused backend check:

```powershell
Set-Location .\backend
$env:SAFERIDE_RUN_DB_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_notifications.py -v
Remove-Item Env:SAFERIDE_RUN_DB_TESTS
```

The test reuses the existing Stage 9C fixture/server/real worker, with new isolated S9D synthetic school/vehicle/student/trip records. A shared window with one picked, one cancelled and one missed student produces exactly one event. Concurrent processors for three missed students produce exactly three events (one each). It checks the raw PostgreSQL uniqueness constraint, recipient scoping, independent/idempotent read state, backend restart persistence and atomic rollback of MISSED/event creation when notification insertion fails.

With the normal local backend/frontend running:

```powershell
Set-Location ..\frontend
node .\scripts\verify-stage9d.cjs
npm run build
```

The browser check uses only those fixture notification IDs. It verifies Admin and Parent display, explicit Parent selection, independent persisted read state, reload, picked/cancelled/unrelated views showing no event, backend-scoped requests, a visible API-error fixture and no mock fallback. It changes only fixture read state. No Google or external delivery APIs are called. Basemap requests are blocked during browser testing. Evidence: stage9d_verification.json, stage9d-admin.png and stage9d-parent.png.

Frontend Vite build passes. Standalone tsc retains the nine pre-existing unused-import/PNG declaration errors outside the Stage 9D changes.


## Exact manual demonstration

1. Run the normal backend and Vite servers. Open http://127.0.0.1:5173 -> Administrator -> Notifications. Find Database missed-pickup events, not the separate component demonstration list.
2. Read docs/stage9d_verification.json for notification_id, missed_student_id, picked_up_student_id and cancelled_student_id. Locate the fixture's trip/student card. It says In-app event created and includes deadline/creation timestamps and simulation source. Mark unread/read explicitly if the tests already marked it read. Reload, choose Administrator again and reopen Notifications: event and read state persist.
3. In a separate tab choose Parent -> notification bell. In Database student ID (prototype), enter missed_student_id and click Load selected student notifications. The same event ID is visible. Reading it does not change the Admin read state (and vice versa).
4. Enter picked_up_student_id, then cancelled_student_id, applying each selection. Neither receives this missed alert. An unrelated explicit ID receives an empty inbox; no previous student's details remain on screen. Reload and reselect the missed student's ID to verify persisted read state.
5. For a fresh event, repeat the Stage 9C simulation-only pickup demonstration: new saved route/trip, confirmed current pickup arrival, confirm one student, cancel one and leave another waiting. Close the browser until the worker expires the window. Admin and that student's prototype Parent inbox receive one in-app event. Reprocessing expiry does not create another. Do not claim SMS or push delivery.

Project-root inspection commands (no credentials):

```powershell
$demo = Get-Content .\docs\stage9d_verification.json | ConvertFrom-Json
$base = 'http://127.0.0.1:8000'
Invoke-RestMethod "$base/routing/notifications?recipient=admin" | ConvertTo-Json -Depth 6
Invoke-RestMethod "$base/routing/notifications?recipient=parent&student_id=$($demo.missed_student_id)" | ConvertTo-Json -Depth 6
Invoke-RestMethod "$base/routing/notifications?recipient=parent&student_id=$($demo.picked_up_student_id)" | ConvertTo-Json -Depth 6
Invoke-RestMethod "$base/routing/notifications?recipient=parent&student_id=$($demo.cancelled_student_id)" | ConvertTo-Json -Depth 6
```

These are prototype filters, not proof of authenticated parent ownership. Do not present this endpoint as securing real parent/child accounts.

## Changed files

backend/models.py; backend/migrations/versions/0011_missed_pickup_notifications.py; backend/notifications.py; backend/pickup_windows.py (atomic MISSED hook); backend/main.py; backend/tests/test_notifications.py; backend/tests/test_pickup_windows.py (reused fixture prefix and notification router).

frontend/src/services/api.ts; frontend/src/components/PersistentNotifications.tsx; frontend/src/pages/FleetAdminPages.tsx; frontend/src/pages/ParentDashboard.tsx; frontend/scripts/verify-stage9d.cjs.

This document, docs/stage9d_verification.json, stage9d-admin.png and stage9d-parent.png. A Stage 9C integration regression also ran successfully and refreshed its existing synthetic verification report. Existing records, historical pickup outcomes and component demonstrations were preserved. No model retraining, dataset regeneration or paid-provider calls were performed.
