"""Shared training/inference feature definitions; JSON-only preprocessing."""
from datetime import datetime
from math import isfinite
from zoneinfo import ZoneInfo
import numpy as np

DISCLAIMER = 'This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.'
SCHEMA_VERSION = 'travel-segment-v1'
NUMERIC = ['distance_m', 'hour', 'day_of_week', 'weather_flag', 'weather_missing']
CATEGORICAL = ['origin_id', 'destination_id', 'segment_id']
FEATURE_SCHEMA = {
    'version': SCHEMA_VERSION, 'timezone': 'Asia/Colombo',
    'numeric': NUMERIC, 'categorical': CATEGORICAL,
    'distance_m': 'Nonnegative approximate haversine straight-line metres, not road distance.',
    'hour': 'Local fractional hour: hour + minute/60 + second/3600.',
    'day_of_week': 'Local Monday=0 through Sunday=6.',
    'weather_flag': '0=dry, 1=adverse; missing encoded -1 plus weather_missing=1. Input, not weather forecast.',
    'segment_id': 'JSON ordered pair [origin_id,destination_id]; direction matters.',
    'unknown_categories': 'All-zero one-hot columns for each unknown categorical field; numeric features still apply.',
    'target': 'Synthetic segment duration_s; trained on log(duration_s), inverse exp at inference.',
    'excluded': ['duration_s', 'trip_id', 'data_source', 'future stops', 'observed arrival', 'target-derived features'],
}


def segment_id(origin, destination):
    import json
    return json.dumps([origin, destination], separators=(',', ':'), ensure_ascii=False)


def feature_record(origin_id, destination_id, departure_timestamp, distance_m, weather_flag=None):
    stamp = datetime.fromisoformat(departure_timestamp) if isinstance(departure_timestamp, str) else departure_timestamp
    if stamp.tzinfo is None or stamp.utcoffset() is None: raise ValueError('Departure timestamp must include a UTC offset.')
    local = stamp.astimezone(ZoneInfo('Asia/Colombo'))
    if not origin_id or not destination_id: raise ValueError('Origin/destination IDs are required.')
    if not isfinite(distance_m) or not 0 <= distance_m <= 40_100_000: raise ValueError('Invalid distance_m.')
    if weather_flag not in (None, 0, 1): raise ValueError('Weather must be 0, 1, or missing.')
    return dict(origin_id=origin_id, destination_id=destination_id, segment_id=segment_id(origin_id, destination_id),
        distance_m=float(distance_m), hour=local.hour + local.minute / 60 + local.second / 3600,
        day_of_week=local.weekday(), weather_flag=-1 if weather_flag is None else int(weather_flag),
        weather_missing=int(weather_flag is None))


def fit_preprocessing(records):
    return {'schema_version': SCHEMA_VERSION, 'categories': {
        field: sorted({record[field] for record in records}) for field in CATEGORICAL}}


def transform(records, preprocessing):
    if preprocessing['schema_version'] != SCHEMA_VERSION: raise ValueError('Feature schema mismatch.')
    result = np.zeros((len(records), len(NUMERIC) + sum(len(v) for v in preprocessing['categories'].values())), dtype=np.float32)
    result[:, :len(NUMERIC)] = [[r[field] for field in NUMERIC] for r in records]
    offset = len(NUMERIC)
    for field in CATEGORICAL:
        categories = preprocessing['categories'][field]
        lookup = {value: i for i, value in enumerate(categories)}
        for row, record in enumerate(records):
            if record[field] in lookup: result[row, offset + lookup[record[field]]] = 1
        offset += len(categories)
    if not np.isfinite(result).all(): raise ValueError('Nonfinite features.')
    return result


def fit_baseline(records, targets):
    groups = {}
    for record, target in zip(records, targets): groups.setdefault(record['segment_id'], []).append(float(target))
    return {'segment_means': {key: float(np.mean(values)) for key, values in groups.items()},
            'unseen_segment_fallback': float(np.mean(targets)), 'fallback_policy': 'Training-only global mean duration_s'}


def baseline_predict(records, baseline):
    return np.array([baseline['segment_means'].get(r['segment_id'], baseline['unseen_segment_fallback']) for r in records])
