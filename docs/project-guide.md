# Project guide

Authenticated operations uses the proposal's teal/white sidebar, spacing, cards and map layout with authorized API responses. The original synthetic proposal dashboards remain in the separate authenticated demo workspace; their context values are not operational inputs.

Administrator navigation: Overview, Daily Plan, Live Fleet, Notifications, Settings. Teammate controls are disabled and labelled Not connected. Settings contains Access, Students and collapsed Administrator tools: Adult research, School test tools, Evaluation and Routes. Normal school planning does not need these tools.

## Windows startup

From the project root, use separate PowerShell terminals:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

Do not start duplicate servers. Vite uses port 5173 strictly and proxies /api to private 127.0.0.1:8000. Existing [account management](archive/checkpoints/authentication-and-device-access.md) and [phone HTTPS setup](archive/checkpoints/phone-https-setup-current.md) remain applicable; never expose PostgreSQL or FastAPI to the phone.

Git does not preserve database records. Follow the existing [private backup procedure](archive/checkpoints/local-checkpoint-and-backup.md). This UI checkpoint does not create or alter records, credentials, model artifacts or backups.
