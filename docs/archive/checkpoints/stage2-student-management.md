# Stage 2: PostgreSQL Students page

## Scope and changed files

- `backend/models.py`: nullable home coordinates for legacy students; active flag; coordinate range and paired-value constraints.
- `backend/migrations/versions/0002_student_management.py`: additive migration; no deletion or invented coordinates. Existing records default to active.
- `backend/persistence.py`: reuse existing reads; add validated create, edit, status and transfer writes. Every successful write commits to PostgreSQL. Invalid school/vehicle references receive 422; unknown students receive 404. Database errors remain sanitized.
- `frontend/src/services/api.ts`: extend the existing fetch helper with write options and typed student/school/vehicle operations.
- `frontend/src/pages/StudentsPage.tsx`: retain table, filters, colors, rounded panels, modal and profile-drawer style; use only database routing records. No demo fallback or fabricated trip history for these students.

Legacy `/students`, `/vehicle`, `/routes/morning`, and `/routes/afternoon` still use prototype sample inputs. This stage does not connect student changes to optimization, demo dashboards, safety, RFID, camera or emergency functions. The shared demo context remains separate. No ML is executed.

## Commands (Windows PowerShell)

Backend terminal:

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If port 8000 is already serving the updated backend, reuse that process. Otherwise stop the old process in its terminal before restarting. Existing credentials are read from `backend/.env`; do not print or commit it. If the database is empty, run `seed.py` before starting Uvicorn. Seed IDs are preserved on reruns.

Frontend terminal:

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm.cmd run dev -- --host 127.0.0.1
```

Production build:

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm.cmd run build
```

## Browser verification

1. Open `http://127.0.0.1:5173`, choose **Administrator**, then **Students**. Rows and school/vehicle filters come from `/api/routing/*`. There is no mock fallback.
2. Click **Add Student**. Enter a synthetic name, select the database school and vehicle, choose **Simulated input**, and enter latitude `6.9271`, longitude `79.8612`. Click **Save student**. The form closes only after the server returns success.
3. Find that row and click **Edit**. Change its name and coordinates, then save. Existing seed students have unknown coordinates; supply both before saving an edit.
4. Click **Transfer**, choose `VAN_STAGE2_TEST`, and click **Save transfer**. This simulated vehicle was added to exercise transfer between two database vehicles; choose another available vehicle if appropriate.
5. Click **Deactivate**, then **Deactivate student**. The row remains with status **Inactive**. Use the status filter to inspect inactive students. **Reactivate** reverses the status without deleting the record.
6. Click **View profile** to inspect persisted IDs, coordinates, provenance and status. No trip observations or ML predictions are invented.
7. Refresh, choose **Administrator > Students** again, and verify the changes. Restart the backend without rerunning the seed, refresh again, and confirm the record remains.
8. Validation: open Add or Edit and try latitude `91`, longitude `181`, or a missing name. Saving is blocked. The backend independently rejects invalid coordinates, missing/blank fields and unknown school/vehicle IDs.
9. Save error: open an Edit form, change the name, set DevTools **Network > Offline**, then save. The form and typed values remain, with an error. Restore **No throttling**, then save again successfully.
10. Load error: set DevTools Network Offline, navigate to **Routes**, then back to **Students**. The page displays an error and no mock rows. Restore connectivity and click **Retry loading**.

## New write endpoints

| Method | Path | Body |
| --- | --- | --- |
| POST | `/routing/students` | name, school_id, vehicle_id, home_latitude, home_longitude, input_source |
| PUT | `/routing/students/{id}` | Same required fields; preserves student ID, home ID and active status |
| PATCH | `/routing/students/{id}/status` | `{"active": false}` or `true` |
| PATCH | `/routing/students/{id}/vehicle` | `{"vehicle_id": "VAN_01"}` |

New students receive server-generated IDs. Valid input sources are `simulated`, `live_provider`, and `measured`; select the actual provenance. Entering coordinates does not create a measured travel observation or a prediction.

## Checks completed

- Applied migration `0002_student_management`; Alembic detected no model/schema drift.
- Real browser writes: create, edit, transfer, deactivate; verified after refresh.
- Restarted a separate verification backend on port 8001; the same record survived and matched an independent SQLAlchemy/PostgreSQL session. The user's backend on 8000 was left running.
- API rejection of out-of-range/null coordinates, blank names, unknown school/vehicle IDs, invalid status type, and nonexistent students; invalid requests did not change records.
- Reactivation followed by deactivation of the synthetic test record.
- Browser validation, pending-save state, failed-save retention, load-failure without mock fallback, and retry. Failures were simulated through browser request interception; successful writes used the real API.
- Both legacy route endpoints still returned their simulated prototype routes.
- `npm.cmd run build` passed.
- Full TypeScript check still reports existing unused imports and the missing PNG module declaration elsewhere; no errors were reported in the changed files.

Test data retained: simulated vehicle `VAN_STAGE2_TEST` (capacity 8) and one inactive student `STU_dd196c68a8f34844b75e1411b9c74c40`, assigned to that vehicle and `SCHOOL_01`. Original seed students were not modified. No records were deleted.
