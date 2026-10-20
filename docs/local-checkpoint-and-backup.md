# Local routing checkpoint and separate database preservation

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
