# Reviewed travel-time observation preparation — 2026-10-19

## What changed and what did not

Existing authenticated trip/device ingestion, raw GPS history, saved route/stop versions, arrival settings/geofences, provenance exclusions, ML feature definitions and planned provider metadata are reused. New tables store collection intent, append-only observation/review revisions and separate saved estimates. A compact administrator **Evaluation — reviewed travel-time collection** section is in **Daily Plan**. Nothing automatically trains a model or turns GPS pairs into labels.

Migration `0018_research_observations` was applied locally. It only adds `research_collections`, `travel_observations` and `segment_estimates`; it does not update historical trip/position records. Read-only evidence after checks: **zero persistent research collections, zero observation revisions, zero segment estimates**. The completed stationary phone trip still has **225 samples**, its session is revoked and no collection protocol was retrospectively registered. No new physical moving-trip evidence exists from this checkpoint.

The current synthetic-trained XGBoost model, artifacts, dataset and metrics were not retrained, regenerated or replaced. Google predictions are never measured labels. No external provider request was made.

## Four separate contexts

| Dataset | Purpose / label eligibility |
| --- | --- |
| `synthetic` | Simulation fixtures; never accepted as measured moving observations |
| `stationary_adult_phone` | Stationary ingestion tests; never accepted as moving observations |
| `moving_adult_landmark` | Separate consenting-adult moving test, prepared before capture; reviewed adult research export only |
| `authorized_operational` | Future authorized nonsynthetic transport assignments; existing student export lineage exclusions additionally apply |

Old unregistered adult captures stay unclassified ingestion evidence. The existing 225 stationary samples remain documented stationary evidence; source tags are unchanged. A completed/ACTIVE trip cannot be newly declared a moving collection. Dataset/protocol are immutable and cannot be switched on an existing collection. Retrying the identical preparation is idempotent.

For moving-adult preparation, the existing administrator adult-phone authorization must already be valid for the new PLANNED trip. Preparation is research intent, not tracking authorization: the assigned driver's scoped session is still required for every actual phone upload. Existing synthetic-fixture registrations remain disqualifying even if a position says `actual_device`.

## Segment identity and boundaries

A candidate is exactly one adjacent pair of **saved ordered stops on the trip's fixed route version**, identified by trip ID, route ID/version, stop sequences and stable location IDs. Grouped school visits stay single stops. A plan published later cannot change this identity.

Departure is the **first observed point outside the origin exit radius**, bracketed by an inside point and followed by another outside observation. Both gaps must be within the trip's existing arrival max-gap setting. Arrival is the **first observed entry into the destination entry radius**, preceded by an outside point and followed by the configured sustained dwell/minimum observations within the exit radius, without excessive gaps. Existing arrival event candidate/confirmation times are shown as review evidence; confirmation occurs after dwell and must not be substituted for entry. No arrival/trip/passenger event is created by extraction.

The administrator explicitly selects and reviews both boundary position IDs. Arbitrary pairs, points midway along a road, repeated stationary destination samples, nonadjacent stops and overlapping stop geofences cannot become accepted segments. Boundaries are sampled geofence crossings, not precise driveway/centroid arrival times. The stored uncertainty is the time bracket between adjacent boundary observations. This may be several seconds even with good accuracy. GPS accuracy is a device-reported estimate, not independent ground truth.

Target schema: **`gps-geofence-travel/v1`**. It is not automatically interchangeable with the current synthetic centroid-to-centroid target. Separate schema/domain review is required before any future measured-data training.

## Stored data and time accounting

Each observation revision stores:

- trip/vehicle, fixed route ID/version, adjacent origin/destination IDs and sequences;
- departure and arrival recorded timestamps with timezone offsets, elapsed seconds, boundary uncertainty and settings;
- raw candidate request, boundary IDs, bounded evidence position IDs, coverage sample counts/max gap, accuracy-quality counts and flags;
- known observed service/dwell intervals and explicit administrator review, with reasons;
- feature schema version and prediction-time features: ordered IDs, approximate straight-line distance from saved locations, departure local hour/day, **unknown weather** (`weather_flag=-1`, `weather_missing=1`);
- immutable collection provenance, review status, reviewer, reason, revision, previous revision and backend review time.

`elapsed_duration_s = arrival_timestamp - departure_timestamp`. Origin service before exit and destination service after entry are outside this boundary interval. Within it, `duration_s = elapsed - documented service - documented deliberate nontraffic dwell`. Traffic/congestion waiting remains part of travel time. Planned optimizer service/wait times are shown separately and are **never** substituted for measured dwell. PM boarding-window duration is not added or subtracted again.

Until dwell has been explicitly reviewed, known service/dwell and adjusted duration remain unknown. Empty intervals plus the review checkbox explicitly records that no such nontraffic dwell was observed in the interval. Do not check it without reviewing. Interruption intervals invalidate acceptance rather than manufacturing an uninterrupted target. Interval evidence must be within the boundaries and nonoverlapping. Elapsed duration and raw intervals are retained even when a candidate is rejected or corrected.

Provider predictions are stored in **`segment_estimates`**, not measured outcome fields: the saved leg's planned driving estimate, source/fallback metadata, model version where present, route version, estimate timestamp and planned departure. They are explicitly labelled **saved planned leg estimate, not measurement**, and were not re-estimated at actual departure. These are not an accuracy evaluation against the captured departure. No live request or retrospective forecast is triggered.

Where saved matrix departure metadata exists, prediction features are reconstructed from saved inputs using the existing ML schema and rounded haversine distance; they are labelled reconstructed, not a newly executed prediction or an archived model tensor. The matrix departure snapshot is used, not a guessed per-leg traffic forecast. Missing legacy inputs remain unavailable. Observation features use the observed departure and keep weather unknown, separately from the earlier planned prediction inputs.

## Quality gates and audit

Acceptance requires a completed trip, supported boundaries, positive duration, at least three core samples, bounded gaps, known acceptable accuracy, phone-session vehicle/trip binding, capture within authorization/lifecycle timestamps, no simulation/fixture evidence, no overlapping geofences and completed dwell review. Existing operational episodes overlapping the interval or declared interruptions block acceptance. Timestamp clock skew is flagged. Missing speed remains null and is never used as zero.

The bounded extraction reads at most 10,000 observations including short boundary context; exceeding that limit is a blocking flag. Historical processing uses recorded GPS time, not current wall-clock freshness; a long gap is not interpolated or called stopped. Arrival settings are taken from the trip. Operational stop/deviation episodes remain preliminary; conservative exclusion can reject legitimate travel, particularly with stop-sequence geometry. There is no override button that silently clears quality flags: retain pending, reject with a reason, or correct the actual supported evidence. Broader interruption adjudication is future work.

Candidate submission starts **pending**. Reviewing/correcting appends a new revision; earlier raw requests, decisions and reasons remain. Only the latest revision counts in Evaluation and export. Stale concurrent reviews return 409. Duplicate identical initial candidates return the existing record; changed boundaries require the review endpoint. Raw GPS rows and original arrivals/trip events are not edited. Export re-extracts and revalidates source/quality, so later provenance corrections can invalidate an earlier accepted review.

The existing `/exports/measured-observations` and CLI remain lineage-only interfaces, not reviewed segment extraction or proof of measurement accuracy. Their student-trip exclusions are unchanged. Use the new reviewed research export for these candidates. Adult exports use `reviewed_adult_landmark_measurement`, never student `measured` provenance. Synthetic/stationary export through the research endpoint is disallowed.

## Exact Windows startup, migration and checks

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Restart an already-running backend so it loads the new router/models. Keep FastAPI and PostgreSQL private. In another terminal, use the existing configured Vite HTTPS/proxy setup from `docs/phone-https-setup-current.md` / `docs/van01-adult-phone-test.md`; do not change keys, phone origin or network settings for extraction.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\frontend
npm run dev
```

Only start Vite if the existing port 5173 server is not already running.

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
$env:SAFERIDE_RUN_RESEARCH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_research_observations.py -v
Remove-Item Env:SAFERIDE_RUN_RESEARCH_TESTS
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_data_provenance.py -v
Set-Location ..\frontend
npx tsc --noEmit
npm run build
```

Research tests use synthetic phone-source fixtures inside outer rollback transactions. They do not represent physical phone captures, retain synthetic `actual_device` rows or create real measured observations. Existing accounts/records are not changed.

Actual checks: eight research extraction/validation/audit/API tests passed, plus four existing provenance regression tests. TypeScript and frontend production build passed (Vite 5.4.21, 1740 modules). Tests cover missing/arbitrary boundaries, gaps/quality, nullable speed, clock skew flags, trusted binding, dwell accounting, separate predictions, immutable/idempotent preparation, synthetic/stationary exclusions, append-only corrections, stale review rejection, bounded GPS evidence and export revalidation. Anonymous, driver and parent access were denied. The existing TestClient/httpx and SWIG deprecation warnings did not fail tests. This is automated extraction/API evidence; the new manual UI walkthrough and a physical moving test have not been executed against real collected segments.

## Exact moving-adult preparation and review walkthrough

1. Choose a **new service date/trip**, not the completed phone AM trip. AM generation for 2026-10-19 is protected because that trip completed; do not bypass it. On the actual test date, Admin **Daily Plan**: confirm locations, dated roster, appropriate departure/provider and explicit evidence review; generate/publish the desired AM/PM plan through existing controls. No student/card event should be manufactured to run an adult test. Actual trip start/adult authorization require today's Asia/Colombo date.
2. Assigned Driver: **Authorized vehicle** → VAN_01 → **Service date (Asia/Colombo)** → **Morning Pickup** or **Afternoon Drop-off** → **Refresh route**. Locate an existing matching PLANNED trip or use **Create planned trip (manual prototype)** once. Record its Trip ID and fixed route version. Do **not** start yet.
3. Administrator **Access → Adult landmark phone test authorization**: enter this new Trip ID, reason, confirm adults-only consent, then **Authorize adult landmark phone test**. Do not reauthorize or reuse the completed stationary test.
4. Administrator **Daily Plan → Evaluation — reviewed travel-time collection**: enter **Research trip ID**; expand **Prepare collection and review boundaries**. Choose **Collection dataset → Moving adult landmark research**. Confirm collection authorization/consent, enter **Research review reason**, click **Prepare collection for planned trip**. Do this before capture, while PLANNED. This does not create GPS or start a trip.
5. Driver: **Start trip (manual prototype)** → **Enroll phone sender for active trip** → **Start sharing** through existing HTTPS phone capture. Keep capture running during actual travel. No replay/simulation upload is acceptable for this collection. Follow existing foreground-browser limitations. At each real saved stop, use the existing current-stop proximity/next-stop controls deliberately; proximity never verifies passenger delivery. Record a short field note of any service, deliberate stop, interruption or permission/network loss with timestamps.
6. Finish the actual adult test and stop sharing; close the trip through **End trip (manual prototype) → Confirm end trip** and revoke the tracking session using existing controls. Completion does not claim student deliveries. Review can occur later; accepted segments require COMPLETED state.
7. Administrator return to Evaluation and enter the trip ID, then **Refresh evaluation**. Expand review controls. Set adjacent **Origin stop sequence** and **Destination stop sequence** from the fixed trip itinerary. Expand **Review GPS boundary evidence**, click **Load GPS evidence**. Use **Older GPS evidence** as necessary; rows are newest first, so review timestamps in travel order. Each row shows position ID, Sri Lankan time, source/accuracy, nullable speed and distances to the two stops, without printing coordinates.
8. Locate first exit with prior inside/repeated outside samples and first destination entry supported by sustained dwell. Click **Use as departure boundary** and **Use as arrival boundary** on the correct rows. Inspect the existing destination arrival entry/confirmation hints, if present. Do not choose merely two convenient timestamps. Missing suitable evidence should produce a rejected/pending candidate.
9. Enter observed interval evidence under **Known interval evidence**, if applicable; review all known dwell/interruptions and check the explicit review checkbox only when justified. Enter a reason and **Save candidate segment**. Inspect flags and elapsed versus adjusted candidate seconds. For unresolved boundaries, blank IDs may be saved pending, never accepted.
10. Click **Review / correct segment**. Inspect **Evidence diagnostics**, select **Review decision → Accepted** only if all validation flags are clear, or **Rejected/Pending** with a reason. Click **Save review revision**. Corrections require a new reason and preserve the old revision. Accepted means passed this research protocol, not independently validated road-travel accuracy.
11. With dataset **Moving adult landmark research** selected, click **Download reviewed research export**. It includes only latest accepted segments of that trip/dataset, with **measured_outcomes** and **provider_estimates** separate. Store it in ignored `private_data/` or outside the repository. `private-reviewed-*.json` is ignored as well. Empty accepted results produce an empty dataset, never invented labels.

Example observed-interval JSON (replace timestamps with actual field-note evidence; do not copy these as measurements):

```json
[{"start":"2026-10-20T06:40:00+05:30","end":"2026-10-20T06:41:00+05:30","kind":"dwell","reason":"Documented deliberate adult test pause, not traffic congestion"}]
```

Use `[]` only when the explicit review established no such within-segment dwell. Do not insert planned 120/600/900-second service constants as observations.

## Endpoints (existing authentication, real administrator only)

| Method/path | Purpose |
| --- | --- |
| POST `/research/collections` | Immutable pre-capture intent: trip_id, dataset, reason, consent_confirmed |
| GET `/research/evidence?trip_id=...&origin_sequence=1&destination_sequence=2&limit=100` | Bounded read-only GPS review; `before` aware timestamp paginates older samples |
| POST `/research/observations` | Candidate: trip_id, adjacent sequences, boundary position IDs, dwell_reviewed, intervals, reason |
| POST `/research/observations/{id}/review` | Same identity/evidence fields plus pending/accepted/rejected status; append revision |
| GET `/research/observations?trip_id=...&history=true` | Bounded audit revisions; omit history for latest only |
| GET `/research/evaluation?trip_id=...` | Latest candidate/accepted/rejected/pending counts by dataset, flag and rejection reasons |
| GET `/research/export?trip_id=...&dataset=moving_adult_landmark` | Separate revalidated adult export; authorized_operational is separate and additionally student-lineage gated |

Anonymous requests are 401; driver/parent and demo-workspace research requests are denied. The UI uses the existing authenticated `/api` proxy; no new accounts, tokens, public ingestion or login bypass were added.

## Limits and remaining verification

The collector is prepared, not validated real-world accuracy. No moving adult segment has yet been collected/reviewed/exported from a physical run. Manual boundary/dwell review remains necessary. Conservative geofences, inaccurate GPS, nearby stops, interruptions and missing coverage can prevent acceptance. Unknown weather remains unknown. Planned provider snapshots may differ from actual departure conditions. There is no new trainer or model evaluation score; comparing future measured labels to estimates requires a separately agreed matched-departure evaluation protocol.
