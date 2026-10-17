# Audited fixture provenance correction — 17 October 2026

Five controlled-clock Stage 9B GPS samples were incorrectly stored as `actual_device`. They have been preserved and corrected to `simulation`. No unrelated actual-device records were selected or changed. No model was retrained, no journey history deleted and no event processing replayed.

## Exact reviewed records and evidence

| Position ID | Vehicle | Trip |
|---|---|---|
| POS_0598d0d48fa549a987bbb000c5057d2a | S9B_2f7c7c9e_V | TRIP_6bb8dfb3a4f74959968488eff644c42a |
| POS_15af973a191c491bac63480317b0d870 | S9B_f3e4eeb3_V | TRIP_f6efc341bace4b51a2dacf2be7d0fe4d |
| POS_7ec5c3c5c5e34de7ae1a4c955107904a | S9B_6e6d0daf_V | TRIP_c6610cb20bba448688c7a191d86fa7ab |
| POS_8a56cdcdd4b847e28b37e24515559d64 | S9B_1a9c1ecc_V | TRIP_1bb65e3dec2742a1aef3f92b61992ca0 |
| POS_d0bb16045b2a4e369de95ae207e80303 | S9B_d81201ac_V | TRIP_eefe77aa7cf04f9aae6a7d0bfd90c21c |

All five have sample_id `28`. Generator: `backend/tests/test_arrivals.py:ArrivalIntegrationTests.test_boundaries_gaps_ordering_single_event_and_current_stop`. The old test intentionally submitted `feed(28,49,source='actual_device')` to exercise source-change candidate resets, despite its module stating all observations are synthetic. It created simulated school/vehicle/student records, a simulated route, generated coordinates relative to a synthetic stop and patched GPS processing time. This was not a device reading.

Correction validation additionally checked the exact vehicle/trip pair, all recorded location input sources in the saved route snapshot equal `simulated`, and adjacent samples 27/29 are simulation with identical generated coordinates and recorded times exactly one second either side. A name prefix alone is not accepted as rewrite evidence. Coordinates, addresses, names and credentials are omitted from these reports.

[Before-correction evidence](provenance-fixture-evidence.json) lists safe IDs and derived references. [Preview](provenance-correction-preview.json), [applied result](provenance-correction-result.json), [preservation/idempotency verification](provenance-correction-verification.json).

## Actual correction and derived record counts

- **5 position source fields corrected**, `actual_device` → `simulation`.
- **5 append-only provenance audit entries**, with entity/field, previous source, corrected source, reason, correction code and timezone-aware database correction time. Corrections occurred 2026-10-17 21:44:56.472288 through 21:44:56.529552 +05:30; exact per-record times are in the verification JSON.
- **5 existing trips registered synthetic**, covering all their derived events for measured-data exclusion. Registration does not modify the Trip row, its state, route version or settings.
- **0 derived source fields needed correction**: inspected seven arrival rows, two pickup windows, two individual outcomes, 16 pickup transitions, two operational monitors and two missed-pickup notifications. Their GPS provenance was already simulation; operational action sources such as expiry_worker remain truthful action sources, not relabelled GPS sources.
- **0 deviation episodes** associated with these trips. No measured segment-observation table/dataset existed to rewrite. Existing training CSV is explicitly synthetic and unchanged.
- **0 records deleted, 0 events replayed, 0 duplicate audit entries on rerun.** Second application reported zero changes.

Before/after full-content comparisons across positions, trips, arrivals, windows, outcomes, transitions, episodes, monitors and notifications verified exactly the five source substitutions and no other changes. All 664 pre-existing positions and 74 trips remained. Existing event counts and contents matched. Historical candidate-reset behaviour was not replayed/recomputed: the audit preserves why the prior input label existed.

The updated isolated fixture integration check subsequently added a new synthetic trip with **17 simulation positions and zero actual-device positions**. Current position totals at this check: **681 simulation, zero actual_device**. Those additional fixture records are separate from the five corrections. [New fixture evidence](provenance-new-fixture-check.json).

## Implementation and safeguards

- `migrations/versions/0013_fixture_provenance.py` adds `synthetic_trip_provenance` and `provenance_corrections`. Triggers reject UPDATE/DELETE of these history tables; database uniqueness prevents duplicate correction entries. Migration itself changes schema only; it does not relabel data.
- `correct_fixture_provenance.py` defaults to dry-run. Exact five-ID allowlist and independent evidence checks; all-or-nothing transaction; vehicle→trip locks serialize with ingestion/expiry. Only source-like fields on confirmed fixture records may change, with an audit for each. Already-corrected rows require their expected audit; conflicting evidence aborts. No broad source/prefix rewrite or event recreation.
- `tests/test_arrivals.py` registers new fixture trips explicitly. All persisted GPS remains simulation. Source-change handling now has an in-memory unit test; a negative actual-device request is rejected, not stored.
- `positions.py` rejects actual-device ingestion on explicitly registered synthetic trips. This is a fixture guard, not general device authentication. Physical devices are not rejected merely for having an unfamiliar ID.
- `data_provenance.py` supplies one fail-closed lineage gate for measured export and metrics. It requires explicit measured label, finite positive target, at least two distinct referenced positions, matching trip/vehicle, actual-device sources, no synthetic correction, no fixture registry entry, no known fixture/simulated vehicle, non-synthetic saved input provenance and no accelerated demo trip. Old unregistered simulated vehicles are also excluded. Relabelling JSON alone cannot promote fixture evidence.
- `export_measured_observations.py` validates the entire supplied observation JSON before writing anything; invalid input fails instead of silently dropping it. It writes atomically and preserves an existing export on validation failure. `measured_observation_metrics` uses the same gate. These are lineage consumers, **not a trace-to-target extractor, a measured-data database or a new trainer**.

The current synthetic trainer still rejects non-synthetic rows. No measured targets were generated and no measured performance metrics are claimed here. The existing model bundle checksums validate and training CSV checksum is unchanged.

## Tests and exact Windows commands

Already run: migration upgrade, correction preview, application, second application, database append-only trigger rejection, full pre-existing-row preservation checks, real-database export/metric rejection of corrected fixture evidence, and the updated isolated arrival integration test (**4/4 passed**).

Network-blocked non-mutating discovery: **40 passed, eight database tests skipped, zero failures/errors** (48 discovered). This includes four new lineage/correction regression tests and an additional in-memory source-change test. [Summary](provenance-regression-checks.json), [log](provenance-regression-checks.txt).

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
# Already applied locally; repeat upgrade is safe.
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
# Dry-run: after this correction it reports zero changes.
.\.venv\Scripts\python.exe correct_fixture_provenance.py
# Explicit application: repeat reports zero changes, preserves original audit times.
.\.venv\Scripts\python.exe correct_fixture_provenance.py --apply
$env:SAFERIDE_RUN_DB_TESTS = '0'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_data_provenance.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_arrivals.py -v
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
```

Optional isolated integration check (creates a new synthetic fixture, not a real student/trip):

```powershell
$env:SAFERIDE_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_arrivals.py -v
Remove-Item Env:\SAFERIDE_RUN_DB_TESTS
```

Future independently prepared measured-observation JSON can use the guarded export command below. It was not used to invent a measured dataset; fixture input is rejected. Records require `data_source: measured`, `duration_s` and `position_ids` with at least two actual evidence references. Do not reinterpret synthetic targets as measured:

```powershell
.\.venv\Scripts\python.exe export_measured_observations.py --input ..\data\measured_observations_input.json --output ..\data\measured_observations_validated.json
```

## Remaining provenance limitations

- Source tags remain caller claims on unrelated unregistered trips; authentication, physical device identity, accuracy and clock-quality validation remain absent. The new lineage gate is not proof of real measurement or target correctness.
- Only the five reviewed old trips and the new S9B generator are explicitly registered here. Other legacy fixtures remain; simulated vehicle/snapshot provenance conservatively excludes them from measured use. Do not blanket-relabel unrelated records based on a prefix.
- A real device can be tested against a simulated planning roster; its readings may be genuine, but the conservative measured-dataset gate excludes that ambiguous context pending review. It does not relabel or delete the readings.
- Future measured exporters and metric consumers must use the shared gate. Ad-hoc SQL or bypassing it is not a validated measured dataset. No genuine segment extraction/store or measured-training path has been implemented.
- Main dashboard/Parent/Live Fleet demo constants and synthetic-only ML remain as documented in the readiness audit. No live-provider success, measured accuracy or completion percentage is claimed.
