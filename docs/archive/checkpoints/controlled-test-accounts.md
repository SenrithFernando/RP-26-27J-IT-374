# Controlled synthetic account setup

Run directly in Windows PowerShell, not through a pipe. Passwords are entered
twice through hidden terminal prompts (12–1024 characters).

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe manage_accounts.py activate-initial driver.local
.\.venv\Scripts\python.exe manage_accounts.py activate-initial parent.local
.\.venv\Scripts\python.exe manage_accounts.py create-test parent.b.local --role parent --student-id PP1_DEMO_0c1effd6_STUDENT_07
```

Existing inspected relationships:

| Account | Role | Synthetic relationship |
|---|---|---|
| driver.local | driver | PP1_DEMO_0c1effd6_VAN_A |
| parent.local | parent A | PP1_DEMO_0c1effd6_STUDENT_01 |
| parent.b.local | parent B, created by command | PP1_DEMO_0c1effd6_STUDENT_07, on VAN_B |

Initial activation refuses any initialized account; it does not reset passwords.
Creation refuses duplicate usernames. Existing assignments are preserved.
New accounts permit Authenticated operations (demo_only=false); linked transport
records remain synthetic. No credentials are stored in this document.

Open http://localhost:5173 in separate browser profiles/private windows for each
account and choose Authenticated operations. Driver must see only VAN_A. Parent A
must see STUDENT_01 only; parent B must see STUDENT_07 only. Each must log in with
the password entered in their terminal prompt. A new tab alone is not necessarily
an isolated browser session.

For object-level checks use the browser Network panel's Edit and Resend feature
(if supported), without copying or sharing authorization headers. Under parent A,
change `/api/parent/students/PP1_DEMO_0c1effd6_STUDENT_01` to STUDENT_07: expect
403. Reverse under parent B. Under driver, change vehicle_id on the existing
`/api/routes/latest` or `/api/trips/current` request to
PP1_DEMO_0c1effd6_VAN_B: expect 403. Change the vehicle segment of a position
history request to VAN_B: expect 403. With no login, navigate to
http://localhost:5173/api/routing/vehicles: expect 401 (navigation does not attach
the application's bearer header). Never export/share HAR files containing tokens.

An account is a login identity and role. DriverVehicle is its vehicle access
relationship; there is no separate persisted driver-profile model in this auth
implementation. A browser driver/demo profile alone grants no permissions.
Tracking authorization is a separate expiring, revocable credential bound to a
login, vehicle and active trip. An assigned driver is not automatically an
authorized phone/device upload session. Synthetic test vehicles use simulation
tracking, not actual-device provenance.

Focused rollback-only authorization checks:

```powershell
$env:SAFERIDE_RUN_AUTH_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_access_control.py -v
Remove-Item Env:SAFERIDE_RUN_AUTH_TESTS
```

The tests do not start application workers or call paid providers. Their temporary
fixtures are rolled back. They verify permission rules independently of the
manual activation and browser checks above.
