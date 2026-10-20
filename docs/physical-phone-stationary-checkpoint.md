# Physical Android stationary GPS checkpoint — 19 October 2026

**Verified scope: one stationary adult landmark phone-ingestion test.**
The operator explicitly confirmed personally operating the physical Android
phone. A read-only PostgreSQL inspection independently confirmed the stored
phone-session binding and sample evidence. This combines operator attestation
with server evidence; an `actual_device` label alone is not sensor attestation.

## Persisted evidence

| Item | Verified value |
|---|---|
| Tracking session | `DEVICE_acd0873144ca4681ace2d3a09fd82d33` |
| Vehicle | `MALABE_PP1_VAN_01` (external VAN_01) |
| Trip | `TRIP_f682a6851f3d41ca94dd4cf6e182fafc` |
| Pinned route | `ROUTE_14dd3b2c6fbc4ec5a2136f94115a0209`, version 39 |
| Observation context | `adult_landmark_field_test` |
| Session kind | `phone` |
| Samples / unique sample IDs | **225 / 225** |
| Duplicate persisted sample IDs | **0** |
| Source | All **225 actual_device**, backend-derived from scoped session |
| Vehicle/trip/session binding | Consistent across all 225 samples |
| Reported accuracy classification | **222 acceptable; 3 poor** |
| Null speed observations | **3**, preserved as null rather than zero |
| First recorded sample | 2026-10-19 00:53:45.424 +05:30 |
| Last recorded sample | 2026-10-19 01:13:41.749 +05:30 |
| Last received sample | 2026-10-19 01:13:41.911421 +05:30 |
| Latest state at inspection | **Stale**, using recorded timestamp and 60-second threshold |
| Session revoked | **2026-10-19 01:19:35.722291 +05:30** |
| Trip state | **COMPLETED**, at **2026-10-19 01:20:07.293656 +05:30** |

All times above are Sri Lankan local time. The machine-readable sanitized
[checkpoint](physical-phone-stationary-checkpoint.json) records exact inspection
time, age at inspection and a SHA-256 digest of non-coordinate sample metadata.
The digest does not export samples, coordinates or raw sensor values.

## Provenance and lifecycle boundaries

VAN_01's planning source remains **simulated**: demonstration assignments and
landmark plans were not relabelled as real student trips. Physical phone GPS is
preserved as actual-device adult-test observations under the explicit trip
approval. Every sample is excluded by the shared measured-student-observation
export/metric gate: 222 by adult-landmark-test context and 3 earlier by poor
accuracy. No observation was converted into a measured travel-time label.

The session is revoked and the trip is completed in PostgreSQL. All inspected
samples were recorded after enrollment and received before revocation. This
inspection made no upload using a revoked credential, so it verifies persisted
revocation/closure rather than claiming a new physical rejection test. Existing
backend authorization code rejects revoked credentials and closed-trip queues;
that behavior has separate synthetic rollback regression evidence.

Zero duplicate stored IDs confirms uniqueness of this accepted dataset. It does
not establish that the physical test exercised retry/duplicate delivery, offline
recovery, or every possible out-of-order case. Latest stale GPS is not a stopped
vehicle assertion. Stationarity is the operator's test description, not an
independent surveyed accuracy result. Completion does not confirm student pickup
or delivery; no student passengers were claimed.

**Not verified by this test:** moving-vehicle tracking, road-route coverage,
route-deviation detection accuracy, sustained background-browser reliability,
measured travel-time accuracy or real-world ML accuracy. No dataset regeneration,
model training, paid-provider call or extra artificial position was performed.

## Read-only reinspection command

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe verify_phone_capture.py --tracking-id DEVICE_acd0873144ca4681ace2d3a09fd82d33 --limit 10
```

The command omits coordinates and credentials. Its statement that physical origin
requires operator confirmation is satisfied for this run by the explicit user
statement recorded above, not by changing the verifier's generic wording.

## Preservation

Only these sanitized documentation artifacts and links to them were added for
this checkpoint. Existing samples, provenance, session, trip, accounts and
uncommitted implementation work were preserved. There was no commit, push,
database migration or additional trip/session creation.
