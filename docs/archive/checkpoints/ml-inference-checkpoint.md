# Synthetic-trained ML inference and fallback checkpoint — 2026-10-20

Reused the existing XGBoost JSON bundle, feature definitions, Python inference/matrix provider, Google fallback policy, startup lifecycle and authenticated endpoints. No model/data generation, training, model replacement, paid API call or operational mutation occurred. Full sanitized read-only results: `docs/ml-inference-verification.json`.

## Audit and changes

`main.lifespan` calls the singleton predictor's load method. Its lock and attempted-load flag allow one disk model load per process; status/predict requests do not reload. A focused test executes the actual lifespan with recovery/expiry threads mocked, calls status repeatedly and predicts, and observes exactly one XGBRegressor.load_model invocation. Startup config/model reads occur, but no test worker runs.

Existing artifact SHA-256 validation was extended to check the complete saved feature schema, preprocessing categories/order, XGBoost input width, baseline validity and matching evaluation metadata. Corrupt/mismatched bundles now fail closed. Tests modify copies under TemporaryDirectory only; working artifacts are untouched. Unavailable messages advise restoring the verified bundle/restarting, not automatically retraining.

The ML matrix adapter now rejects incomplete prediction batches and nonfinite/nonpositive values instead of leaving unfilled off-diagonal entries as zero. True colocated/diagonal geographic arcs remain zero with separate service accounting; those are not claimed as predictions. Costs are prepared before OR-Tools callbacks.

Added a collapsed **Synthetic-trained ML evaluation** panel to administrator **Daily Plan**, backed by the existing GET `/ml/status`. It displays training source, sample/trip counts, final-test XGBoost/baseline MAE/RMSE in seconds/minutes, chronological ranges, folds, unseen/missing-weather counts and saved feature schema. Missing status/evaluation stays unavailable, with no fabricated metrics. Existing requested/actual source, model version and fallback reasons remain on each route.

## Verified artifacts and evaluation

Model: `synthetic-xgb-v1-26c03624ed36a729`; schema `travel-segment-v1`; training source **synthetic**. Existing `docs/ml_metrics.json` equals the bundle metrics exactly. CSV SHA-256 matches the report. Training-only preprocessing vocabulary and historical-average baseline reproduce from the development block. Saved artifacts' hashes remained unchanged.

2000 synthetic observations / 400 synthetic trips; development 1500 / 300 trips; untouched final test 500 / 100 trips. Development runs **2026-07-06 05:43:42 to 2026-08-14 16:40:39**; final test **2026-08-17 05:42:52 to 2026-08-28 16:36:09**, all Asia/Colombo.

Four expanding weekly walk-forward folds, with whole trips kept together:

| Fold | Training samples | Evaluation samples | Evaluation dates |
|---|---:|---:|---|
| 1 | 500 | 250 | July 20–24 |
| 2 | 750 | 250 | July 27–31 |
| 3 | 1000 | 250 | August 3–7 |
| 4 | 1250 | 250 | August 10–14 |

Training-only preprocessing and means are fitted per fold. Fixed parameters; no final-test tuning or early stopping is implemented. Latest two weekly blocks are held out. Split/trip chronology is validated in tests. The published model was fitted to development only.

| Evaluation | Model | MAE seconds | MAE minutes | RMSE seconds | RMSE minutes |
|---|---|---:|---:|---:|---:|
| Final 500 | XGBoost | 28.012511859487336 | 0.4668751976581223 | 49.89851705630116 | 0.8316419509383527 |
| Final 500 | Historical average | 57.08666959838096 | 0.9514444933063493 | 111.90390381547041 | 1.8650650635911736 |
| Walk-forward aggregate 1000 | XGBoost | 29.857325989406917 | 0.4976220998234486 | 57.84007223986494 | 0.9640012039977489 |
| Walk-forward aggregate 1000 | Historical average | 75.66774007569524 | 1.2611290012615872 | 134.67356416304156 | 2.244559402717359 |

Final metrics were recomputed from inference over the 500 held-out synthetic rows and match stored values to nine decimal places, without fitting. Walk-forward aggregate statistics were checked against the saved fold metrics. Fold models/predictions are not archived, so individual fold predictions were not independently rerun without retraining. Final test includes 14 unseen-segment samples and 57 missing-weather samples. These results describe this synthetic dataset only; they are not measured-road accuracy or a promise of beating baseline on actual data.

## Features and isolated inference

Inputs are only stable origin/destination/segment IDs, approximate straight-line distance, departure local hour/day, supplied weather or explicit unknown. The API forbids extra target/outcome fields and requires offset-aware timestamps and finite valid distance/weather. No arrival, observed duration, future-stop outcome or GPS-derived target is an inference feature.

Unknown IDs use all-zero unknown categorical columns plus available numeric/known features. Historical fallback is a training-only global mean. Missing weather is weather_flag=-1 and weather_missing=1; no weather provider is fetched. Example at an explicitly supplied 1500 m, 2026-10-21 06:30 Colombo with unseen IDs/missing weather: actual model prediction **294.38736528891116 s**, baseline **214.20827133333333 s**, both unknown_segment and weather_missing true. This is a model-output check, not a measured journey. Training distance range is 43–4052 m; extrapolation/weekend warnings remain explicit.

Missing/corrupt bundles report unavailable and prediction API returns 503 rather than a substitute. Temporary copies test checksum failure, reordered schema and changed feature width. Synthetic injected NaN/infinite/underflow predictions and incomplete batches fail closed. The working model remains loaded and its files unchanged.

## Actual read-only routing checks

Using existing confirmed **2026-10-21** attendance/locations, pure Python solves generated no saved versions:

- AM: seven participants, feasible ML plan; 90 directed model predictions; all nine driven route legs equal the corresponding ceil(predicted seconds).
- PM: six participants, feasible ML plan; 72 directed predictions; all eight driven legs match; final depot return retained.
- Google forced failure + no fallback: unavailable; no model prediction fabricated.
- Google forced failure + ML: feasible AM, requested Google but actual ml_prediction, actual model version and forced failure reason.
- Google forced failure + isolated missing model + ML-only: unavailable, no predictions.
- Google forced failure + isolated missing model + explicit ML-then-baseline: feasible historical_baseline plan; no XGBoost inference. The displayed version identifies its shared synthetic artifact bundle, not evidence that XGBoost ran.

All cases use a transport that raises if a paid request is attempted; actual HTTP count zero. No automatic retries or configuration/model changes were needed. UI tests separately verify ML fallback labels, model version/reason, synthetic metrics and unavailable-model rendering with intercepted data.

These are departure-time matrix snapshots for every arc, not fully time-dependent predictions. Unknown segment IDs, synthetic domain and approximate distances limit interpretation. No route improvement or savings is forced or inferred.

## Exact UI verification

1. Stop/restart the existing backend terminal to load the stricter loader and expanded status response:

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Do not start a second backend/frontend on occupied ports. Keep the existing HTTPS frontend and /api proxy. No migrations, model training or account changes.

2. Administrator in **Authenticated operations → Daily Plan**. Expand **Synthetic-trained ML evaluation** near the bottom. Check model version, synthetic source, 2000/1500/500 counts, baseline table and **Chronological folds and prediction-time feature schema**. If the old backend response lacks evaluation, the panel explicitly asks for restart rather than substituting values.
3. For a deliberate saved-plan demonstration, select an unexecuted date with explicit confirmed attendance and stopping pins. Choose **Estimate provider → ML prediction — synthetic training**, then **Validate AM override** or **Generate PM plan**. Inspect actual ml_prediction source, model version and source-labelled warnings; these clicks save new drafts, not trips/publications.
4. To demonstrate Google fallback without paid calls: choose Google, **Declared fallback → Loaded ML only**, enable **Controlled adapter failure TEST**, set **HTTP budget per selected plan** to zero and leave road geometry off. Generate one selected draft. Expect requested Google, actual ML, synthetic model version, forced-failure reason and zero HTTP calls. Do not call this live traffic.
5. With failure TEST still enabled, choose **None** and generate one selected draft: it must be unavailable. Turn TEST off and switch back to ML afterwards if continuing a no-paid-call demo. Do not remove or corrupt working artifacts to demonstrate a missing model; use isolated automated tests.
6. Existing **Routes** also displays **ML available/unavailable**, provider selection, saved model version and fallback reasons. Evaluation details live in Daily Plan. Drivers receive reviewed/published saved plans; active manifests remain fixed. Neither GET `/ml/status` nor GET routes solves/retrains anything.

## Safe checks and evidence preservation

```powershell
Set-Location C:\Users\MSI\Desktop\Safe_Ride_LK\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ml_pipeline.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_traffic_provider.py -v
$env:SAFERIDE_RUN_RESEARCH_TESTS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_research_observations.py -v
Remove-Item Env:SAFERIDE_RUN_RESEARCH_TESTS
Set-Location ..\frontend
# Existing frontend origin; intercepted tests do not call Google or mutate records.
$env:SAFERIDE_UI_TEST_URL='https://YOUR_CURRENT_WIFI_IP:5173'
node scripts/verify-ml-evaluation.cjs
node scripts/verify-daily-plan.cjs
Remove-Item Env:SAFERIDE_UI_TEST_URL
npx tsc --noEmit
npm run build
```

Passed 31 backend tests: 11 ML, 12 traffic/fallback and eight research-observation regressions. Intercepted ML evaluation and Daily Plan UI checks pass at mobile width without page errors. TypeScript/build pass, retaining the existing nonfatal bundle-size warning. No retraining, artifact/CSV/doc-metric modification, paid request, student mutation, trip or observation save occurred.

Read-only evidence remains **225 stationary samples**, **90 moving adult samples**, both trips COMPLETED, **two moving-observation revisions**. They are not training rows. Reviewed adult observations retain target `gps-geofence-travel/v1` (sampled exit-to-entry, with boundary uncertainty), separate from the synthetic stopping-point/centroid duration target. The existing trainer accepts synthetic rows only and defaults to the synthetic CSV. No incompatible target merge, measured-label fabrication or real-world accuracy claim is made.
