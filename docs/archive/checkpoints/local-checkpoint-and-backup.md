# Local routing checkpoint and separate database preservation

> Latest backup update: see the verified private backup section at the end. Earlier
> inspection notes below are historical; PostgreSQL tools have now been located.

Checkpoint date: 2026-10-20. Branch: `feature/routing-pp1-clean`.

This checkpoint preserves the accumulated routing, dated attendance, departure
recommendation, provider/fallback, reviewed research collection, phone capture,
boarding/window and Administrator?Driver boundary implementation. It includes
source migrations; no migration, reseed, reset, training or paid API call was run
for this Git checkpoint. Existing account passwords and assignments are unchanged.
Earlier generated authentication reports are deliberately left unstaged.

Latest parity verification: 27 backend tests passed; three intercepted browser
suites, TypeScript and frontend build passed. Mobile layout was checked at 320px
and 390px. These are not physical navigation or Hasara mobile integration evidence.
Hasara's boundary remains API-ready, not connected. See
`hasara-driver-plan-contract-v1.md` for exact comparison steps.

The prior read-only preservation check found 225 stationary samples and 90 moving
samples, each trip COMPLETED. Raw GPS, observations and revisions are PostgreSQL
records, not Git objects. The synthetic-trained model was not retrained or changed.
A Git commit does **not** preserve database records or private credentials.

## Existing backup support and gap

Repository inspection found ignore rules for private dumps/backups, but no
project backup script or verified backup/restore runbook. No existing backup was
verified by this checkpoint. pg_dump was not found on PATH or in the usual
`C:\Program Files\PostgreSQL` location during inspection; this does not establish
that PostgreSQL tooling is absent elsewhere. pgAdmin's existing Backup/Restore
interface can invoke the installed PostgreSQL utilities after configuring its
binary path. Do not claim evidence is backed up until a backup has succeeded.

## Separate pgAdmin backup procedure (manual, no database reset)

1. Open pgAdmin and select the existing `saferide_routing` database.
2. Right-click the database ? **Backup...**. Choose **Custom** format and a
   timestamped filename in a private directory outside the repository, for
   example `C:\Users\MSI\SafeRide-private-backups\saferide_routing-YYYYMMDD-HHMM.backup`.
   Create that private folder locally if needed. Never upload the archive to Git.
3. Include the complete database schema and data, including GPS, research
   collections, observation revisions, route snapshots, trips and audit events.
   Do not select schema-only or data-only. Enter connection secrets only through
   pgAdmin's private credential prompt. The dump contains sensitive records.
4. Run **Backup** and inspect its completion/process log privately. Record its
   timestamp, file size and SHA-256 in the private backup folder. Retain a protected
   copy on another device/storage location. Do not paste database contents here.
5. A database dump does not contain PostgreSQL login passwords or the private
   `.env`, TLS keys or Android CA private key. Preserve required configuration
   separately in protected storage; do not commit credentials.
6. Verify restoration into a **new, isolated database**, with no application or
   scheduler pointed at it. Do not restore over `saferide_routing`. Confirm row
   counts, the two preserved phone-trip counts and observation revision history
   there before calling recovery verified. Roles/extensions may require local
   administrator preparation. No restore was performed by this checkpoint.

The root ignore rules exclude `.env`, private keys/certificates, virtualenvs,
node_modules, build output, private export folders and database dumps. Safe
`.env.example`, source migrations and explicitly allowed synthetic fixtures remain
eligible. New private JSON should go under an ignored private/export directory;
ignore rules cannot identify sensitive content placed at arbitrary filenames.


## Verified private checkpoint backup ? 20 October 2026, 16:48 Asia/Colombo

PostgreSQL 17.11 tools were located through the running Windows service at
`D:\programme\PostgreSQL\17\bin`. The custom-format backup procedure above was
executed using pgAdmin's underlying `pg_dump` utility rather than its UI.
A read-only repeatable-read transaction exported a snapshot; `pg_dump --snapshot`
used that same snapshot as the private table counts. No application records changed.

Local private archive:
`C:\Users\MSI\SafeRide-private-backups\checkpoint-20261020-164853\saferide_routing.backup`

- Size: 766,259 bytes.
- SHA-256: `5a5eb29764af1f379ffa7da35b63c88450ffe9d8eb52f62ab878b666730c3ec5`.
- Complete schema/data for all 32 public tables; required TABLE DATA entries for
  accounts, trips, GPS, route snapshots, research collections and observation
  revisions were checked. Snapshot counts retain 225 stationary and 90 moving
  adult-phone samples. Full table counts stay in the private backup manifest.
- `pg_restore --list` passed. `pg_restore --file=NUL --no-owner --no-privileges`
  read/decompressed the complete archive without connecting to or changing a DB.
- A restore into a separate database was **not performed**; full recovery remains
  unverified. Do not restore this archive over the evidence database for testing.
- Directory inheritance was removed; only the current user, SYSTEM and local
  Administrators have full access. The dump and private manifest/logs are outside
  the repository. No passwords, hashes, sessions or GPS records are copied into Git.
- Application account rows, including existing password hashes, are in the private
  dump. Cluster-level PostgreSQL login passwords, `.env`, TLS keys and model files
  are separate from this database backup; preserve their private originals.

For another manual backup, use pgAdmin as above or the located binary with its
interactive hidden password prompt (enter no password in command arguments):

```powershell
$privateDirectory = Join-Path $env:USERPROFILE 'SafeRide-private-backups'
$backupFile = Join-Path $privateDirectory ('saferide_routing-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.backup')
& 'D:\programme\PostgreSQL\17\bin\pg_dump.exe' --host=localhost --port=5432 --username=saferide_app --dbname=saferide_routing --format=custom --password --file=$backupFile
# Only after pg_dump exits successfully:
& 'D:\programme\PostgreSQL\17\bin\pg_restore.exe' --file=NUL --no-owner --no-privileges $backupFile
Get-FileHash -Algorithm SHA256 -LiteralPath $backupFile
```

Keep dumps and all contents listings private. Copy this private archive to another
protected storage location before relying on it against laptop/disk loss. A local
source commit and a same-disk backup alone do not cover hardware failure.
