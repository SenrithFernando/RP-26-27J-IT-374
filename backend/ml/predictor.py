"""Load one verified JSON model bundle per backend process; never fake predictions."""
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from threading import Lock
import numpy as np
from ml.features import (DISCLAIMER, SCHEMA_VERSION, FEATURE_SCHEMA, NUMERIC, CATEGORICAL, baseline_predict, feature_record, transform)

ARTIFACTS = Path(__file__).resolve().parent / 'artifacts'


class ModelUnavailable(RuntimeError): pass


class TravelTimePredictor:
    def __init__(self, artifacts=ARTIFACTS):
        self.artifacts = Path(artifacts)
        self.model = None
        self.metadata = None
        self.preprocessing = None
        self.baseline = None
        self.metrics = None
        self.error = 'Model not loaded. Backend startup loads artifacts once.'
        self._attempted = False
        self._lock = Lock()

    def load(self):
        with self._lock:
            if self._attempted: return self.status()
            self._attempted = True
            try:
                from xgboost import XGBRegressor
                pointer = json.loads((self.artifacts / 'current.json').read_text(encoding='utf-8'))
                version = pointer['model_version']
                if not isinstance(version, str) or not version.startswith('synthetic-xgb-v1-') or Path(version).name != version:
                    raise ValueError('Invalid artifact version.')
                directory = self.artifacts / version
                metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
                if metadata['model_version'] != version or metadata['feature_schema'] != FEATURE_SCHEMA or metadata['data_source'] != 'synthetic':
                    raise ValueError('Metadata/schema mismatch.')
                for name in ('model.json', 'preprocessing.json', 'baseline.json', 'metrics.json'):
                    if sha256((directory / name).read_bytes()).hexdigest() != metadata['files_sha256'][name]:
                        raise ValueError('Artifact checksum mismatch.')
                preprocessing = json.loads((directory / 'preprocessing.json').read_text(encoding='utf-8'))
                baseline = json.loads((directory / 'baseline.json').read_text(encoding='utf-8'))
                metrics = json.loads((directory / 'metrics.json').read_text(encoding='utf-8'))
                if metrics['model_version'] != version or preprocessing['schema_version'] != SCHEMA_VERSION:
                    raise ValueError('Artifact versions differ.')
                categories=preprocessing['categories']
                if set(categories)!=set(CATEGORICAL) or any(not isinstance(categories[k],list) or any(not isinstance(x,str) for x in categories[k]) or categories[k]!=sorted(set(categories[k])) for k in CATEGORICAL):
                    raise ValueError('Preprocessing layout mismatch.')
                if metrics['feature_schema']!=FEATURE_SCHEMA or metrics['data_source']!='synthetic' or metrics['final_test']['train']!=metadata['training_range'] or metrics['final_test']['evaluation']!=metadata['test_range']:
                    raise ValueError('Evaluation metadata mismatch.')
                if any(not isfinite(v) or v<=0 for v in [baseline['unseen_segment_fallback'],*baseline['segment_means'].values()]):
                    raise ValueError('Invalid baseline.')
                model = XGBRegressor(); model.load_model(directory / 'model.json')
                if model.get_booster().num_features()!=len(NUMERIC)+sum(len(categories[k]) for k in CATEGORICAL):
                    raise ValueError('Model/preprocessing feature count mismatch.')
                self.model, self.metadata, self.preprocessing, self.baseline, self.metrics = model, metadata, preprocessing, baseline, metrics
                self.error = None
            except FileNotFoundError:
                self.error = 'Model artifacts missing. Restore the verified model bundle and restart FastAPI.'
            except ImportError:
                self.error = 'XGBoost dependency unavailable in this Python environment.'
            except Exception:
                self.model = None
                self.error = 'Model artifacts invalid or incompatible. Restore the verified model bundle and restart FastAPI.'
            return self.status()

    def status(self):
        return {'available': self.model is not None, 'status': 'available' if self.model is not None else 'unavailable',
                'reason': self.error, 'model_version': self.metadata['model_version'] if self.model is not None else None,
                'training_data_source': 'synthetic' if self.model is not None else None,
                'disclaimer': DISCLAIMER, 'feature_schema': self.metadata['feature_schema'] if self.model is not None else None,
                'final_test': self.metrics['final_test'] if self.model is not None else None,
                'evaluation': {key:self.metrics[key] for key in ('sample_counts','validation_method','parameter_selection','walk_forward','walk_forward_aggregate','final_test')} if self.model is not None else None}

    def predict_many(self, requests):
        if self.model is None: raise ModelUnavailable(self.error)
        if not requests: return []
        records = [feature_record(**request) for request in requests]
        with np.errstate(over='ignore', invalid='ignore'):
            durations = np.exp(self.model.predict(transform(records, self.preprocessing)).astype(np.float64))
        baseline = baseline_predict(records, self.baseline)
        if not np.isfinite(durations).all() or np.any(durations <= 0) or not np.isfinite(baseline).all() or np.any(baseline <= 0):
            raise ModelUnavailable('Model returned invalid durations. No prediction is available.')
        results = []
        low, high = self.metadata['training_distance_range_m']
        for request, record, duration, average in zip(requests, records, durations, baseline):
            unknown = record['segment_id'] not in self.baseline['segment_means']
            warnings = []
            if unknown: warnings.append('Unknown segment: model uses available numeric/known ID features; baseline uses training-only global mean.')
            if record['weather_missing']: warnings.append('Weather input missing: explicit unknown encoding used; no weather forecast was fetched.')
            if not low <= record['distance_m'] <= high: warnings.append('Distance is outside the development training range; extrapolation is unvalidated.')
            if record['day_of_week'] >= 5: warnings.append('Weekend is outside the synthetic weekday training population.')
            results.append({'origin_id': request['origin_id'], 'destination_id': request['destination_id'],
                'duration_s': float(duration), 'baseline_duration_s': float(average),
                'model_version': self.metadata['model_version'], 'prediction_source': 'ml_prediction',
                'training_data_source': 'synthetic', 'unknown_segment': unknown,
                'weather_missing': bool(record['weather_missing']), 'feature_values': record,
                'warnings': warnings, 'disclaimer': DISCLAIMER})
        return results


predictor = TravelTimePredictor()
