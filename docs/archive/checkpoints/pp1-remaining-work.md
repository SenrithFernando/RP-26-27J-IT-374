# PP1 remaining work before 22 October 2026

No official completion percentage is assigned. Stages 1?9 have implementation and synthetic verification evidence; they are not a production deployment certification.

## Priorities

| Target | Work | Acceptance evidence |
|---|---|---|
| 17 October | Supervisor confirms school-visit versus per-student pickup policy, exact deadline boundary rule, and meaning of delivery confirmation | Written approved policy; provisional configuration documented until approved |
| 17?18 October | Authentication/authorization plan for Admin, Driver vehicle assignment and Parent student ownership | Server rejects unrelated recipients/vehicles without trusting query selectors. Current prototype filtering is not sufficient |
| 18?19 October | Approved live-provider test, only when budget and credentials are explicitly authorized; validate road geometry/display and failure paths | Actual timestamped traffic matrix and geometry evidence, source attribution and paid-call accounting. Not performed in this audit |
| 18?20 October | Collect consented real segment observations and actual GPS-device trials; keep measured data separate from simulation | Device clock/order/gap quality evidence; actual observations labelled correctly; no synthetic-target accuracy claim |
| 19?20 October | Explicit delivery confirmation design and trip progress acceptance; finish operational workflow review | Pickup cannot mark delivery, terminal trip retains unfinished history, role actions audited. RFID integration remains outside this routing task |
| 20?21 October | Repeat isolated regression suite and manual Students/Driver/Parent walkthrough; stronger migration/backup and deployment checks | Fresh test logs, UI error/reconnect evidence, clean database setup/upgrade and restore validation |
| 21 October | Freeze demonstration fixtures, screenshots, commands and research claims | Five-minute offline-capable simulated demo, source labels consistent, no invented savings/percentages |
| 22 October | Present verified prototype and limitations | Synthetic-vs-live-vs-predicted-vs-measured distinction maintained |

Dates are proposed work targets, not completion promises. Real-world accuracy validation may require more data/time than this deadline permits.

## Implemented but not operationally verified

- Google traffic-aware matrix, geocoding and road-image adapters have mocked contract/failure tests; live Google calls and road rendering remain unverified. Missing credentials and explicit unavailable states are supported.
- Actual-device position source exists but physical GPS-device ingestion, network outages and field arrival accuracy are unverified.
- Worker startup/restart is tested locally. Multi-process/multi-host production lifecycle, deployment supervision, scale/load and backup recovery need separate validation. Local scheduler assumptions are explicit.
- Fresh Students browser CRUD was not repeated in this audit; backend persistence/regeneration was exercised and earlier stage browser evidence is retained.

## Simulation and research limitations

- All 2,000 training rows are synthetic. Real-world XGBoost accuracy, generalization, proposal MAE targets and deviation precision/recall have not been established. No retraining occurred in this audit.
- The solver uses one departure-time cost snapshot for all arcs, not fully time-dependent traffic optimization. OR-Tools has a bounded heuristic search, not a proven global optimum.
- Haversine distance and fallback stop-sequence geometry are approximate. OSM tiles are display tiles, not traffic/routing input. Provider-road geometry is not independently surveyed proof.
- Sustained deviation and low movement are preliminary operational episodes, not crash/safety diagnoses. Expected-stop exclusion is conservative around planned locations and may suppress a real anomaly there; thresholds need field calibration.
- GPS age uses backend time; device clock synchronization requires field verification. Missing GPS does not imply a stopped vehicle.
- Pickup windows are exception workflow separate from planned solver service/waiting. Morning per-stop / afternoon shared contiguous school visit is provisional, not a recorded supervisor-approved policy. Demo timing is not production timing.
- Delivery confirmation is incomplete. End-trip closes lifecycle and retains unresolved outcomes; it does not certify delivery. No automatic active-trip rerouting exists.
- No SMS/push transport delivery is implemented for missed pickup: only persistent in-app events.
- Unrelated driver cabin, camera, RFID, emergency, dashboard summary and safety panels remain demonstrations. They must not be presented as verified routing features.
- No real authentication: a caller can spoof prototype roles/student IDs. Parent filtering prevents accidental cross-selection in normal UI use but is not access control.

## Audit blockers

No blocker prevented local backend checks, PostgreSQL checks, TypeScript, build or isolated two-tab verification. Paid live-provider calls were deliberately excluded. Missing configured live-provider credentials and absent real measured/device evidence block live-provider/field claims; no substitute values were fabricated. Current database migration head is 0012_operational_episodes; this audit requires no new migration.
