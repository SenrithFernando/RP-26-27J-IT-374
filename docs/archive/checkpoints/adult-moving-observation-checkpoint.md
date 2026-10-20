# Adult moving research observation checkpoint

Read-only database and code audit on 2026-10-19 (Asia/Colombo), after the saved 23:17 review. This document contains no coordinates or credentials. Only this documentation file was created by this checkpoint; no database records, model artifacts or datasets were changed.

## Physical evidence and provenance

The operator reports physically following A → B → C → A on an Android phone. Persisted evidence supports the following, without independently verifying the physical journey or device-reported accuracy:

- Trip `TRIP_06d72b08f1f6403aa792ba5e774350b1` is COMPLETED, fixed to research route `RROUTE_08deff8968d946599fbfe958d20b528c`, version 32, service date 2026-10-19, travel mode driving.
- Collection `moving_adult_landmark` was registered at 20:09:52 Colombo, before trip start at 20:12:00. Consent and the reviewed-adjacent-segment/v1 protocol were recorded. This is adult research, not student transport or a registered synthetic fixture.
- Phone session `DEVICE_bdaf9b9808264521b225c83668b2d634` is bound to this vehicle/trip and revoked. Trip ended at 20:27:18; session revoked at 20:27:24.
- 90 actual-device samples, 90 unique sample IDs; recorded period 20:19:02–20:26:56. Capture does not cover the first approximately seven minutes after trip start.
- 89 samples have acceptable reported accuracy, one poor (100 m, first sample). Maximum recorded sampling gap 6.101 s; none exceed the trip's 10 s gap limit. One sample has unknown speed, not zero speed.
- Separate arrival events exist for occurrences 1 A, 2 B, 3 C and 4 A. Initial and final A share a location but have distinct stop occurrences, events and confirming samples. Arrival confirmations: 20:19:43.747, 20:21:38.747, 20:23:58.747 and 20:25:47.748 respectively.
- Existing measured student-trip export exclusions remain. The earlier stationary test still has 225 samples and is not included in this moving collection.

## Saved decisions and immutable revision history

| Pair | Revision | Decision | Saved time, Colombo | Observation ID |
|---|---:|---|---|---|
| 1→2 | 1 | pending | 21:05:18.780 | OBS_97453450f4a63c34a86b5d8104bf9ec4e9e2a146 |
| 1→2 | 2 (latest) | accepted | 23:17:03.073 | OBS_6e4ac126f6e142ffb6fbbe5a2057cd8d |
| 2→3 | — | Not saved | — | — |
| 3→4 | — | Not saved | — | — |

Latest counts: one candidate family, one accepted, zero pending and zero rejected. There are two stored revisions; the earlier pending revision remains preserved. Both revisions have no stored quality flags and no flags on current read-only extraction. Revision 2 references revision 1. No duplicates were created by this audit.

The accepted 1→2 observation records explicit dwell review with no known service/dwell/interruption intervals. Elapsed and adjusted duration are both 21.897 s; reviewed service and deliberate dwell are both zero. Boundary IDs: departure `POS_35886f51bc3a470c828ca1d731c46d13`, arrival `POS_01b5850bcf084ee7aed65a5c23412b41`. Core coverage is five samples; ten context samples are all acceptable; maximum core gap 5.999 s. Sampled departure/arrival uncertainty is 5.101/5.999 s. Its separate saved provider-estimate record exists but estimate duration is unavailable, not a measured value or a prediction accuracy result.

Read-only extraction of the latest accepted revision passes the same lineage/quality revalidation used by export. Therefore the separate adult research export is currently eligible to contain exactly one outcome and its separate unavailable-estimate record. Unsaved 2→3 and 3→4 evidence is not exported. No HTTP export/download or browser walkthrough was executed during this audit.

## Boundary and model limitations

Target schema is `gps-geofence-travel/v1`: sampled origin geofence exit to destination entry, supported by repeated observations and destination dwell. Arrival confirmation is later than entry and is not the endpoint timestamp. Origin service before exit and destination service after entry are outside the duration. Approximately 5–6 s boundary uncertainty is material for a 21.897 s interval. Device-reported accuracy is not independently measured ground truth.

The existing model uses `travel-segment-v1` features and synthetic stopping-point/centroid-pair duration targets. `backend/ml/train_model.py` accepts explicitly synthetic input rows only and defaults to `data/travel_times_synthetic.csv`; it does not consume the research export. The accepted research target is not compatible merely because both use seconds or similar feature names. No targets were merged, no training ran, and no model was replaced. Weather remains unknown. No paired provider estimate exists here for an accuracy comparison.

Remaining work: manually review and save 2→3 and 3→4 if appropriate; deliberately decide their status; independently assess boundary/accuracy limitations, repeated journey coverage, background/foreground capture reliability and target compatibility before any future measured-data training. This checkpoint does not establish field precision/recall, representative travel-time accuracy or production readiness. Route geometry/provider estimates remain unavailable; the map is a stop sequence.

## Exact export verification

1. Log in as an administrator in Authenticated operations. Open **Adult research**, then **Evaluation — reviewed travel-time collection** (also available in Daily Plan).
2. Enter the trip ID above in **Research trip ID** and click **Refresh evaluation**. Expect candidate segments 1, accepted 1, pending 0, rejected 0, source moving_adult_landmark. Inspect the listed accepted revision 2 and its **Evidence diagnostics**. Do not click save/review actions for an export-only check.
3. Expand **Prepare collection and review boundaries** and select **Collection dataset → Moving adult landmark research**. Do not click **Prepare collection for planned trip**; this completed trip already has an immutable collection.
4. Click **Download reviewed research export**. It performs an authenticated GET, revalidates accepted latest revisions and downloads `private-reviewed-moving_adult_landmark.json` locally. Keep the download private and outside Git.
5. Verify top-level `dataset` is moving_adult_landmark, `measured_outcomes` contains exactly one item (sequences 1/2, revision 2, observation ID above), data_source reviewed_adult_landmark_measurement, target_schema gps-geofence-travel/v1, empty flags and duration_s 21.897. Verify provider_estimates is separate and its duration_s is null. No outcomes for 2/3 or 3/4 should appear until separately saved and accepted.

Existing same-origin authenticated read-only requests (the browser supplies its existing session; never copy credentials into commands):

```text
GET /api/research/evaluation?trip_id=TRIP_06d72b08f1f6403aa792ba5e774350b1
GET /api/research/observations?trip_id=TRIP_06d72b08f1f6403aa792ba5e774350b1
GET /api/research/observations?trip_id=TRIP_06d72b08f1f6403aa792ba5e774350b1&history=true
GET /api/research/export?trip_id=TRIP_06d72b08f1f6403aa792ba5e774350b1&dataset=moving_adult_landmark
```

Use the existing HTTPS frontend origin and /api proxy. These endpoints are administrator-only; anonymous/driver access is not a workaround. A future flag on export must be reviewed, not bypassed. No backend restart, migration or retraining is required for this documentation checkpoint.
