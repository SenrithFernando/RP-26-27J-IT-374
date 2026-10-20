# Evaluation and provenance

Settings → Administrator tools → Evaluation retains model disclosure and observation collection/review. Adult research preparation remains under Adult research, separate from school operations.

The model is synthetic-trained. [Saved metrics](ml_metrics.json), [pipeline](archive/checkpoints/stage6-ml-pipeline.md) and [inference checks](archive/checkpoints/ml-inference-checkpoint.md) do not establish real-world accuracy. No training or artifact replacement occurs here.

Preserved historical physical evidence: 225 stationary Android samples demonstrate ingestion, not moving travel-time labels. The separate completed moving adult journey has 90 samples. These are prior checkpoint counts, not new physical verification. Raw samples and revisions are unchanged. Geofence-exit-to-entry targets remain separate from stopping-point/centroid training targets.

Follow [collection/review instructions](archive/checkpoints/measured-observation-collection.md) and [moving checkpoint](archive/checkpoints/adult-moving-observation-checkpoint.md): explicitly create candidates, inspect quality/boundaries, record decisions, then export eligible reviewed records. Never auto-accept, turn provider estimates into measured labels or manufacture passenger events.

UI checks use intercepted synthetic responses. They verify presentation/action wiring, not physical handoff, background reliability, road-path equality or field precision/recall.
