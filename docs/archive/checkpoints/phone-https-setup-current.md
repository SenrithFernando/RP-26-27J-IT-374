# Current Windows/Android HTTPS setup

Inspected the existing Vite configuration, package scripts, API/login and phone
upload clients, device approval and live network interfaces. No authentication,
tracking or Vite redesign was needed. Existing uncommitted work was preserved.

Detected **physical Wi-Fi**, Up, Native 802.11, interface index **21**, IPv4
**10.123.106.157/24**, with a default gateway. VMware and disconnected adapters
were excluded. The intended phone URL is **https://10.123.106.157:5173**. The
address is DHCP-assigned: regenerate the certificate/revisit commands if changed.

`C:\Tools\mkcert.exe.exe` was corrected to `C:\Tools\mkcert.exe`, version 1.4.4.
No CA/private key contents were printed. `-CAROOT` returned
`C:\Users\MSI\AppData\Local\mkcert`; rootCA.pem exists. The expected server
certificate/key files do not yet exist. CA trust installation, certificate
generation and firewall/profile changes remain manual actions below.

PostgreSQL currently listens only on **127.0.0.1:5432 and ::1:5432**. FastAPI is
stopped. The existing frontend is HTTP on 127.0.0.1:5173; stop it before HTTPS.
Wi-Fi is **Public**. Do not change an untrusted/public network to Private simply
to run the test; use your own trusted Wi-Fi or private hotspot, then re-detect its
actual IP and issue the certificate for that new IP if needed.

## 1. Confirm the selected address (ordinary PowerShell)

```powershell
Get-NetAdapter -Physical | Select-Object Name,InterfaceIndex,Status,MediaType
Get-NetIPAddress -InterfaceIndex 21 -AddressFamily IPv4 | Select-Object IPAddress,AddressState,PrefixLength
Get-NetConnectionProfile -InterfaceIndex 21 | Select-Object InterfaceAlias,NetworkCategory
```

Use 10.123.106.157 only while it is still the assigned Wi-Fi address. Do not use a
VMware address or 127.0.0.1 on the phone.

## 2. Install local CA trust (Windows administrator action if prompted)

In a PowerShell opened **as Administrator**, run:

```powershell
& 'C:\Tools\mkcert.exe' -install
```

This installs development CA trust on this PC. Do not copy its private key to
Android. No need to reinstall mkcert or modify PATH.

## 3. Generate server certificate outside the repository (ordinary PowerShell)

```powershell
$phoneHost = '10.123.106.157'
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
New-Item -ItemType Directory -Path $tlsDirectory -Force | Out-Null
& 'C:\Tools\mkcert.exe' -cert-file (Join-Path $tlsDirectory 'phone-cert.pem') -key-file (Join-Path $tlsDirectory 'phone-key.pem') $phoneHost localhost 127.0.0.1 ::1
```

Expected files:
`C:\Users\MSI\AppData\Local\SafeRide-LK-TLS\phone-cert.pem` and
`C:\Users\MSI\AppData\Local\SafeRide-LK-TLS\phone-key.pem`. Never put either in
frontend/public or frontend/src. No TLS files were found there or tracked by Git.
Root `.gitignore` now excludes `.crt`, `.cer`, `.der` in addition to existing
`.pem`, `.key`, `.pfx`, `.p12` and private environment rules. Git ignore rules
alone do not prevent a file from being served if manually copied into public.

## 4. Locate and transfer only the public CA certificate

```powershell
$caDirectory = (& 'C:\Tools\mkcert.exe' -CAROOT).Trim()
Write-Output $caDirectory
Get-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') | Select-Object FullName
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
Copy-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') -Destination (Join-Path $tlsDirectory 'saferide-development-ca.crt')
explorer.exe $tlsDirectory
```

Via USB transfer **only saferide-development-ca.crt** to your own Android phone.
It is a renamed copy of public rootCA.pem. Never transfer **rootCA-key.pem** or
**phone-key.pem**; do not open/paste their contents.

Android: Settings → Security and privacy → More security settings / Encryption &
credentials → Install a certificate → **CA certificate** → select that .crt.
Exact menus vary. This is a CA installation, not a Wi-Fi client certificate or
native-app keystore import. Restart Chrome if necessary. The final URL must open
without a certificate warning; never disable secure-context checks. Remove the
development CA from Android after testing.

Reference: [official mkcert mobile-device guidance](https://github.com/FiloSottile/mkcert#mobile-devices).

## 5. Narrow firewall rule (Windows administrator actions)

Only on **your trusted private network**, elevated PowerShell:

```powershell
Set-NetConnectionProfile -InterfaceIndex 21 -NetworkCategory Private
$phoneAddress = Read-Host 'Enter Android Wi-Fi IPv4 from its connected network details'
New-NetFirewallRule -DisplayName 'SafeRide adult phone HTTPS only' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -LocalAddress 10.123.106.157 -RemoteAddress $phoneAddress -InterfaceAlias 'Wi-Fi' -Profile Private
```

The phone address is not the PC address: read it from Android's connected Wi-Fi
details. If this named rule already exists, inspect it first:

```powershell
Get-NetFirewallRule -DisplayName 'SafeRide adult phone HTTPS only' -ErrorAction SilentlyContinue | Get-NetFirewallAddressFilter
```

Do not accumulate duplicate broad rules. To replace this test rule, remove only
that exact display name and recreate it with current addresses. Existing broader
Node rules are separate; this narrow rule does not override them. Never allow
ports 5432/8000, disable the firewall or configure router port-forwarding.

## 6. Start FastAPI on loopback (ordinary terminal A)

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. No migrations, model training or database credentials
need changing for this HTTPS follow-up.

## 7. Start a single HTTPS Vite server (ordinary terminal B)

Ctrl+C in the existing Vite terminal first; never start a second port-5173 server.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
$tlsDirectory = Join-Path $env:LOCALAPPDATA 'SafeRide-LK-TLS'
$env:SAFERIDE_HTTPS_HOST = '10.123.106.157'
$env:SAFERIDE_HTTPS_CERT = Join-Path $tlsDirectory 'phone-cert.pem'
$env:SAFERIDE_HTTPS_KEY = Join-Path $tlsDirectory 'phone-key.pem'
npm run dev
```

Existing package script is `npx vite`; configuration reads these process
environment variables, serves HTTPS at the specified interface with strict port
5173, and proxies `/api` to **http://127.0.0.1:8000**, stripping `/api`.
Do not substitute `npm run preview` or set VITE_API_URL to localhost. The phone's
requests use relative `/api/...` on its HTTPS origin; only the PC proxy targets
loopback FastAPI. Binding only the Wi-Fi IP means use that same URL on PC too,
even though localhost is included in the certificate.

Confirm listeners in a third ordinary PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 5173,8000,5432 -State Listen | Select-Object LocalAddress,LocalPort
```

Expected: 10.123.106.157:5173, 127.0.0.1:8000, and PostgreSQL loopback addresses.
Do not proceed if backend/database have wildcard listeners.

## 8. Android Chrome and same-origin authentication

1. Connect to the same trusted Wi-Fi; open **https://10.123.106.157:5173**.
   It is not https://localhost:5173 on the phone. Client isolation on guest Wi-Fi
   can still prevent access; a successful PC page alone does not prove phone access.
2. Log in privately as `driver.local`, **Authenticated operations**. Desktop
   localhost sessions do not transfer to this origin or the phone.
3. Authentication uses an opaque bearer session in per-tab sessionStorage and
   Authorization headers; **no authentication cookies are used**. The API and
   GPS clients use relative `/api` URLs and `credentials:'omit'`. There is no
   SameSite/Secure-cookie setting to alter and no CORS/authentication bypass needed.
4. Select VAN_01, today's service date/direction and its published route. Confirm
   the correct active trip. In Admin Access the adult-only approval must first
   be recorded for that specific trip; default synthetic fixtures remain blocked.
5. Driver → **Refresh route** → **Enroll phone sender for active trip** →
   **Start sharing** → grant precise location. Approval is real-admin-only,
   scoped/audited, expires within two hours, and preserves landmark-test provenance.
6. Continue the physical checklist in [adult phone test](van01-adult-phone-test.md).
   Do not mark ingestion complete until real accepted samples and operator
   confirmation exist. This follow-up creates no sample or trip record.

After testing, elevated PowerShell can remove only the temporary frontend rule:

```powershell
Remove-NetFirewallRule -DisplayName 'SafeRide adult phone HTTPS only'
```

Leave PostgreSQL and FastAPI private. If Wi-Fi addresses change, update certificate,
frontend host and narrow firewall addresses before the next test.
