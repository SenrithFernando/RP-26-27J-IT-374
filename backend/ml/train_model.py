"""Train fixed-parameter XGBoost with trip-grouped chronological evaluation."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from zoneinfo import ZoneInfo
import numpy as np
import sklearn
import xgboost
from xgboost import XGBRegressor

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from ml.features import (DISCLAIMER, FEATURE_SCHEMA, feature_record, fit_preprocessing, transform,
                         fit_baseline, baseline_predict)

PARAMETERS = dict(n_estimators=240, max_depth=4, learning_rate=.045, subsample=1., colsample_bytree=1.,
                  objective='reg:squarederror', tree_method='hist', random_state=20261015, n_jobs=1)


def load_data(path):
    with path.open(encoding='utf-8', newline='') as file: rows = list(csv.DictReader(file))
    if len(rows) < 100: raise ValueError('At least 100 observations required.')
    for row in rows:
        if row['data_source'] != 'synthetic': raise ValueError('This development trainer accepts explicitly synthetic rows only.')
        if not row['trip_id']: raise ValueError('Missing trip ID.')
        row['_timestamp'] = datetime.fromisoformat(row['departure_timestamp'])
        row['_record'] = feature_record(row['origin_id'], row['destination_id'], row['_timestamp'],
            float(row['distance_m']), None if row['weather_flag'] == '' else int(row['weather_flag']))
        if abs(float(row['hour']) - row['_record']['hour']) > 1e-7 or int(row['day_of_week']) != row['_record']['day_of_week']:
            raise ValueError('CSV clock features disagree with the timestamp schema.')
        row['_target'] = float(row['duration_s'])
        if not np.isfinite(row['_target']) or row['_target'] <= 0: raise ValueError('Targets must be finite and positive.')
    return sorted(rows, key=lambda row: (row['_timestamp'], row['trip_id']))


def chronological_blocks(rows):
    trips = {}
    for row in rows: trips.setdefault(row['trip_id'], []).append(row)
    blocks = {}
    for trip in trips.values():
        stamp = min(r['_timestamp'] for r in trip).astimezone(ZoneInfo('Asia/Colombo'))
        monday = stamp.date() - timedelta(days=stamp.weekday())
        blocks.setdefault(monday, []).extend(trip)
    blocks = [sorted(blocks[week], key=lambda r: r['_timestamp']) for week in sorted(blocks)]
    if len(blocks) < 6: raise ValueError('At least six chronological weekly trip blocks required.')
    for left, right in zip(blocks, blocks[1:]):
        if max(r['_timestamp'] for r in left) >= min(r['_timestamp'] for r in right):
            raise ValueError('Trip time ranges overlap a chronological block boundary; cannot split safely.')
    return blocks


def describe(rows):
    return {'samples': len(rows), 'trips': len({r['trip_id'] for r in rows}),
            'start': min(r['_timestamp'] for r in rows).isoformat(), 'end': max(r['_timestamp'] for r in rows).isoformat()}


def metrics(target, prediction):
    if not np.isfinite(prediction).all() or np.any(prediction <= 0): raise ValueError('Invalid model output; no artifact published.')
    residual = np.asarray(target) - prediction
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return {'mae_seconds': mae, 'mae_minutes': mae / 60, 'rmse_seconds': rmse, 'rmse_minutes': rmse / 60}


def fit_and_evaluate(train, evaluation):
    assert not {r['trip_id'] for r in train} & {r['trip_id'] for r in evaluation}
    assert max(r['_timestamp'] for r in train) < min(r['_timestamp'] for r in evaluation)
    records, targets = [r['_record'] for r in train], np.array([r['_target'] for r in train])
    eval_records, actual = [r['_record'] for r in evaluation], np.array([r['_target'] for r in evaluation])
    prep = fit_preprocessing(records)
    baseline = fit_baseline(records, targets)
    model = XGBRegressor(**PARAMETERS)
    model.fit(transform(records, prep), np.log(targets))
    predicted = np.exp(model.predict(transform(eval_records, prep)).astype(np.float64))
    baseline_predicted = baseline_predict(eval_records, baseline)
    unseen = [r['segment_id'] not in baseline['segment_means'] for r in eval_records]
    results = {'train': describe(train), 'evaluation': describe(evaluation),
               'xgboost': metrics(actual, predicted), 'baseline': metrics(actual, baseline_predicted),
               'unseen_segment_samples': sum(unseen), 'missing_weather_samples': sum(r['weather_missing'] for r in eval_records)}
    for label, mask in [('unseen_segments', np.array(unseen)), ('missing_weather', np.array([r['weather_missing'] == 1 for r in eval_records]))]:
        results[label] = {'samples': int(mask.sum()), 'xgboost': metrics(actual[mask], predicted[mask]) if mask.any() else None,
                          'baseline': metrics(actual[mask], baseline_predicted[mask]) if mask.any() else None}
    return model, prep, baseline, results, actual, predicted, baseline_predicted


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=BACKEND.parent / 'data' / 'travel_times_synthetic.csv')
    parser.add_argument('--artifacts', type=Path, default=BACKEND / 'ml' / 'artifacts')
    parser.add_argument('--metrics', type=Path, default=BACKEND.parent / 'docs' / 'ml_metrics.json')
    args = parser.parse_args()
    rows = load_data(args.data); blocks = chronological_blocks(rows)
    development, final_test = sum(blocks[:-2], []), sum(blocks[-2:], [])
    folds, actuals, predictions, baselines = [], [], [], []
    # Fixed parameters chosen in source before any final-test evaluation. No search,
    # early stopping, feature fitting or baseline averaging on validation/test data.
    for index in range(2, len(blocks) - 2):
        _, _, _, result, actual, predicted, baseline = fit_and_evaluate(sum(blocks[:index], []), blocks[index])
        result['fold'] = len(folds) + 1; folds.append(result)
        actuals.extend(actual); predictions.extend(predicted); baselines.extend(baseline)
    model, preprocessing, baseline, test_result, _, _, _ = fit_and_evaluate(development, final_test)
    dataset_hash = sha256(args.data.read_bytes()).hexdigest()
    libraries = {'xgboost': xgboost.__version__, 'numpy': np.__version__, 'scikit_learn': sklearn.__version__, 'python': platform.python_version()}
    version = 'synthetic-xgb-v1-' + sha256(json.dumps([dataset_hash, PARAMETERS, FEATURE_SCHEMA, libraries], sort_keys=True).encode()).hexdigest()[:16]
    report = {'model_version': version, 'trained_at': datetime.now(timezone.utc).isoformat(),
        'data_source': 'synthetic', 'disclaimer': DISCLAIMER, 'csv_sha256': dataset_hash,
        'sample_counts': {'all': len(rows), 'development': len(development), 'final_test': len(final_test), 'all_trips': len({r['trip_id'] for r in rows})},
        'validation_method': 'Expanding-window weekly walk-forward, whole trips; latest two weekly blocks held out. Training-only vocabularies and historical averages in each fold.',
        'parameter_selection': 'Fixed parameters; no tuning or early stopping on final test. Published model trained on development only.',
        'parameters': PARAMETERS, 'libraries': libraries, 'feature_schema': FEATURE_SCHEMA,
        'walk_forward': folds, 'walk_forward_aggregate': {'samples': len(actuals), 'xgboost': metrics(actuals, np.array(predictions)), 'baseline': metrics(actuals, np.array(baselines))},
        'final_test': test_result}
    directory = args.artifacts / version
    directory.mkdir(parents=True, exist_ok=True)
    model.save_model(directory / 'model.json')
    write_json(directory / 'preprocessing.json', preprocessing)
    write_json(directory / 'baseline.json', baseline)
    write_json(directory / 'metrics.json', report)
    metadata = {'model_version': version, 'data_source': 'synthetic', 'disclaimer': DISCLAIMER,
        'feature_schema': FEATURE_SCHEMA, 'trained_at': report['trained_at'], 'libraries': libraries,
        'training_range': describe(development), 'test_range': describe(final_test),
        'training_distance_range_m': [min(r['_record']['distance_m'] for r in development), max(r['_record']['distance_m'] for r in development)],
        'files_sha256': {name: sha256((directory / name).read_bytes()).hexdigest() for name in ('model.json', 'preprocessing.json', 'baseline.json', 'metrics.json')}}
    write_json(directory / 'metadata.json', metadata)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    temp_metrics = args.metrics.with_suffix('.tmp'); write_json(temp_metrics, report); temp_metrics.replace(args.metrics)
    pointer = args.artifacts / 'current.tmp'; write_json(pointer, {'model_version': version}); pointer.replace(args.artifacts / 'current.json')
    print(json.dumps({'model_version': version, 'sample_counts': report['sample_counts'],
        'walk_forward_aggregate': report['walk_forward_aggregate'], 'final_test': test_result, 'artifacts': str(directory), 'disclaimer': DISCLAIMER}, indent=2))


if __name__ == '__main__': main()
