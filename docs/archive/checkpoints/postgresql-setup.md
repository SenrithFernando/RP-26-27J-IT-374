# Local PostgreSQL persistence

The legacy `/students`, `/vehicle`, and `/routes/{direction}` endpoints retain their sample-data contracts. New `/routing/schools`, `/routing/vehicles`, `/routing/students`, and `/routing/health` endpoints use PostgreSQL. Database records do not yet alter route optimization or frontend demo state.

## Create the application login in pgAdmin

1. Connect to your local PostgreSQL server as its administrator (usually `postgres`).
2. Expand the server, right-click **Login/Group Roles**, select **Create > Login/Group Role**.
3. General: name `saferide_app`.
4. Definition: enter your chosen password locally.
5. Privileges: enable **Can login**. Leave Superuser, Create roles, Create databases, Replication, and Bypass RLS disabled. Save.
6. Right-click **Databases > saferide_routing > Query Tool**. Confirm the active database is `saferide_routing`, and execute as the administrator:

```sql
ALTER DATABASE saferide_routing OWNER TO saferide_app;
GRANT CONNECT ON DATABASE saferide_routing TO saferide_app;
GRANT USAGE, CREATE ON SCHEMA public TO saferide_app;
```

This assigns ownership of this project database and lets migrations create objects in `public`. Run migrations as `saferide_app`; it then owns the created tables. No server-wide administrator rights are needed for the app.

## Credentials

`backend/.env` is ignored and was created only if absent. Edit it locally; do not paste the password into chat or a terminal command. `.env.example` contains only configuration defaults and an empty password.

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=saferide_routing
DB_USER=saferide_app
DB_PASSWORD='your local password'
```

Enter the actual password, not a percent-encoded URL value. Single-quoted dotenv values preserve spaces and `#`; interpolation is disabled so `${...}` stays literal. Within single quotes, escape a literal quote as `\'` and a literal backslash as `\\`. Process environment variables take priority over `.env`. Restart the backend after changing credentials. Database URLs and passwords must never be logged.

## Install, migrate, and seed (PowerShell)

```powershell
cd C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
notepad .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Stop any existing backend on port 8000 before launching the updated one. Migrations are explicit; startup does not create tables or seed data. Repeating the seed inserts missing IDs without overwriting existing records. A fresh database gets one school, one vehicle, and three students, all labeled `simulated`. Home IDs are prototype identifiers, not measured coordinates. There are no ML predictions or measured travel observations in this seed.

## Verify persistence through a restart

In another PowerShell terminal:

```powershell
$before = Invoke-RestMethod http://127.0.0.1:8000/routing/students
$before | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:8000/routing/schools
Invoke-RestMethod http://127.0.0.1:8000/routing/vehicles
Invoke-RestMethod http://127.0.0.1:8000/routing/health
```

Stop Uvicorn using Ctrl+C in its terminal, then start it again using the same command. Do **not** run the seed again. Back in the verification terminal:

```powershell
$after = Invoke-RestMethod http://127.0.0.1:8000/routing/students
if (($before | ConvertTo-Json -Depth 5 -Compress) -ne ($after | ConvertTo-Json -Depth 5 -Compress)) { throw 'Records changed across restart' }
'Persistence restart comparison passed'
Invoke-RestMethod http://127.0.0.1:8000/routes/morning
Invoke-RestMethod http://127.0.0.1:8000/routes/afternoon
```

For direct database verification, pgAdmin Query Tool on `saferide_routing`:

```sql
SELECT current_database(), current_user;
SELECT * FROM alembic_version;
SELECT * FROM public.schools ORDER BY id;
SELECT * FROM public.vehicles ORDER BY id;
SELECT * FROM public.students ORDER BY id;
SELECT tablename, tableowner FROM pg_tables
WHERE schemaname = 'public' AND tablename IN ('schools', 'vehicles', 'students', 'alembic_version');
```

Browser: open `http://127.0.0.1:8000/docs`, expand **Persistent routing records**, execute all four GET endpoints. Missing credentials, unavailable PostgreSQL, or missing tables return a sanitized 503 on persistence endpoints; legacy routes remain independent.

## Troubleshooting

- Missing packages: rerun the install command with the backend virtual environment.
- Missing DB_PASSWORD: enter it in `backend/.env` locally.
- Password authentication failure: check role login, role password, and `.env` locally.
- Permission denied for schema public: run the grants above as administrator in the correct database.
- Missing relation: run `alembic upgrade head` against the same configured database.
- Never use `alembic downgrade base` to verify persistence: it removes these tables and records.
