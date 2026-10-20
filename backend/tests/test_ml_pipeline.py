"""Leakage boundaries, reproducibility, real JSON inference and provider checks."""
import csv
import json
from math import ceil, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from datetime import date
from fastapi import HTTPException
from pydantic import ValidationError
import numpy as np
from ml.api import PredictionRequest, predict
from ml.features import baseline_predict, feature_record, fit_baseline, fit_preprocessing, transform
from ml.generate_synthetic_data import DEFAULT_OUTPUT, generate
from ml.predictor import ARTIFACTS, ModelUnavailable, TravelTimePredictor
from ml.provider import MLTravelTimeProvider
from ml.train_model import chronological_blocks, load_data
from travel_time import Coordinate, InvalidTravelCosts, validate_costs


class FeatureTests(unittest.TestCase):
    def test_startup_loads_once_and_status_predict_do_not_reload(self):
        import asyncio,xgboost
        from main import lifespan,app
        from ml.api import status
        model=TravelTimePredictor()
        original=xgboost.XGBRegressor.load_model
        async def check():
            async with lifespan(app):
                for _ in range(3):self.assertTrue(status()['available'])
                predict(PredictionRequest(origin_id='A',destination_id='B',distance_m=100,departure_timestamp='2026-10-21T06:00:00+05:30'))
        # No real recovery/expiry worker runs and no records are touched.
        with patch('main.Thread'),patch('main.predictor',model),patch('ml.api.predictor',model),patch.object(xgboost.XGBRegressor,'load_model',autospec=True,side_effect=original) as load:
            asyncio.run(check());self.assertEqual(load.call_count,1)

    def test_unknown_segment_missing_weather_and_training_only_averages(self):
        known = feature_record('A', 'B', '2026-07-06T06:30:00+05:30', 100, 0)
        unknown = feature_record('NEW', 'B', '2026-07-07T13:00:00+05:30', 200, None)
        prep = fit_preprocessing([known])
        values = transform([unknown], prep)
        self.assertEqual(values[0, 3], -1)
        self.assertEqual(values[0, 4], 1)
        self.assertEqual(prep['categories']['origin_id'], ['A'])
        baseline = fit_baseline([known, known], [10, 30])
        np.testing.assert_equal(baseline_predict([unknown], baseline), [20])
        self.assertEqual(known['hour'], 6.5)
        self.assertEqual(unknown['day_of_week'], 1)

    def test_prediction_input_validation(self):
        good = dict(origin_id='A', destination_id='B', departure_timestamp='2026-07-06T06:00:00+05:30', distance_m=100)
        for update in ({'distance_m': float('nan')}, {'distance_m': -1}, {'weather_flag': 2},
                       {'weather_flag': True}, {'departure_timestamp': '2026-07-06T06:00:00'}, {'origin_id': ''}, {'duration_s': 5}):
            with self.assertRaises(ValidationError): PredictionRequest(**{**good, **update})

    def test_missing_model_reports_unavailable_not_a_prediction(self):
        with TemporaryDirectory() as directory:
            empty = TravelTimePredictor(directory)
            self.assertFalse(empty.load()['available'])
            with self.assertRaises(ModelUnavailable): empty.predict_many([{}])
            with patch('ml.api.predictor', empty), self.assertRaises(HTTPException) as error:
                predict(PredictionRequest(origin_id='A', destination_id='B', distance_m=10, departure_timestamp='2026-07-06T06:00:00+05:30'))
            self.assertEqual(error.exception.status_code, 503)


@unittest.skipUnless(DEFAULT_OUTPUT.exists() and (ARTIFACTS / 'current.json').exists(), 'Run generation and training first.')
class GeneratedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = TravelTimePredictor()
        if not cls.model.load()['available']: raise AssertionError(cls.model.error)

    def test_reproducible_dataset_and_whole_trip_chronology(self):
        locations = json.loads(DEFAULT_OUTPUT.with_suffix('.locations.json').read_text(encoding='utf-8'))
        manifest = json.loads(DEFAULT_OUTPUT.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        regenerated = generate(locations, manifest['seed'])
        with DEFAULT_OUTPUT.open(encoding='utf-8', newline='') as file: saved = list(csv.DictReader(file))
        self.assertEqual([{key: str(value) for key, value in row.items()} for row in regenerated], saved)
        self.assertEqual(len(saved), 2000)
        self.assertEqual({row['data_source'] for row in saved}, {'synthetic'})
        blocks = chronological_blocks(load_data(DEFAULT_OUTPUT))
        seen = set()
        for block in blocks:
            trips = {r['trip_id'] for r in block}
            self.assertFalse(seen & trips); seen |= trips
        development = sum(blocks[:-2], [])
        final = sum(blocks[-2:], [])
        self.assertLess(max(r['_timestamp'] for r in development), min(r['_timestamp'] for r in final))
        expected = fit_preprocessing([r['_record'] for r in development])
        self.assertEqual(expected, self.model.preprocessing)
        for fold in self.model.metrics['walk_forward']:
            self.assertLess(fold['train']['end'], fold['evaluation']['start'])

    def test_real_json_model_unknown_ids_and_load_once(self):
        request = dict(origin_id='UNSEEN_A', destination_id='UNSEEN_B', departure_timestamp='2026-10-15T06:30:00+05:30', distance_m=1500, weather_flag=None)
        result = self.model.predict_many([request])[0]
        self.assertTrue(isfinite(result['duration_s']) and result['duration_s'] > 0)
        self.assertTrue(result['unknown_segment']); self.assertTrue(result['weather_missing'])
        self.assertEqual(result['training_data_source'], 'synthetic')
        self.assertEqual(result['baseline_duration_s'], self.model.baseline['unseen_segment_fallback'])
        loaded = self.model.model
        self.model.load(); self.assertIs(self.model.model, loaded)
        second = TravelTimePredictor(); second.load()
        self.assertEqual(result['duration_s'], second.predict_many([request])[0]['duration_s'])

    def test_provider_costs_are_actual_model_predictions(self):
        points = [Coordinate(6.93, 79.86, 'A'), Coordinate(6.94, 79.87, 'B'), Coordinate(6.93, 79.86, 'C')]
        costs = MLTravelTimeProvider(date(2026, 10, 15), None, self.model).precompute(points, 'morning', 21600)
        validate_costs(costs, 3)
        request = dict(origin_id='A', destination_id='B', departure_timestamp='2026-10-15T06:00:00+05:30', distance_m=costs.distance_metres[0][1], weather_flag=None)
        self.assertEqual(costs.duration_seconds[0][1], ceil(self.model.predict_many([request])[0]['duration_s']))
        self.assertEqual(costs.duration_seconds[0][0], 0)
        self.assertEqual(costs.duration_seconds[0][2], 0)
        self.assertEqual(costs.metadata['duration_source'], 'ml_prediction')
        with self.assertRaises(InvalidTravelCosts):
            MLTravelTimeProvider(date(2026, 10, 15), None, self.model).precompute([Coordinate(6.93, 79.86)], 'morning', 21600)

    def test_corrupt_or_mismatched_copies_fail_closed_and_load_once(self):
        import shutil
        from hashlib import sha256
        version=self.model.metadata['model_version']
        for kind in ('checksum','schema','width'):
            with self.subTest(kind=kind),TemporaryDirectory() as root:
                target=Path(root);shutil.copytree(ARTIFACTS/version,target/version);shutil.copy2(ARTIFACTS/'current.json',target/'current.json')
                directory=target/version;meta=json.loads((directory/'metadata.json').read_text())
                if kind=='checksum':(directory/'model.json').write_text('{}')
                elif kind=='schema':
                    meta['feature_schema']['numeric']=list(reversed(meta['feature_schema']['numeric']))
                    (directory/'metadata.json').write_text(json.dumps(meta))
                else:
                    prep=json.loads((directory/'preprocessing.json').read_text());prep['categories']['origin_id'].append('ZZZZ_UNEXPECTED_FEATURE')
                    prep['categories']['origin_id'].sort()  # Valid ordering; rejection must be the model-width mismatch.
                    (directory/'preprocessing.json').write_text(json.dumps(prep))
                    meta['files_sha256']['preprocessing.json']=sha256((directory/'preprocessing.json').read_bytes()).hexdigest()
                    (directory/'metadata.json').write_text(json.dumps(meta))
                broken=TravelTimePredictor(target);self.assertFalse(broken.load()['available'])
                with self.assertRaises(ModelUnavailable):broken.predict_many([{}])
        import xgboost
        original=xgboost.XGBRegressor.load_model
        with patch.object(xgboost.XGBRegressor,'load_model',autospec=True,side_effect=original) as read:
            model=TravelTimePredictor();model.load();model.load();model.status()
            self.assertTrue(model.status()['available']);self.assertEqual(read.call_count,1)

    def test_saved_final_metrics_reproduce_without_training(self):
        from hashlib import sha256
        from ml.train_model import metrics
        report=self.model.metrics
        self.assertEqual(json.loads((ARTIFACTS.parent.parent.parent/'docs/ml_metrics.json').read_text()),report)
        self.assertEqual(sha256(DEFAULT_OUTPUT.read_bytes()).hexdigest(),report['csv_sha256'])
        blocks=chronological_blocks(load_data(DEFAULT_OUTPUT));development=sum(blocks[:-2],[]);test=sum(blocks[-2:],[])
        expected_baseline=fit_baseline([r['_record'] for r in development],[r['_target'] for r in development])
        self.assertEqual(expected_baseline,self.model.baseline)
        predicted=self.model.predict_many([dict(origin_id=r['origin_id'],destination_id=r['destination_id'],departure_timestamp=r['_timestamp'],distance_m=float(r['distance_m']),weather_flag=None if r['weather_flag']=='' else int(r['weather_flag'])) for r in test])
        actual=np.array([r['_target'] for r in test])
        for key,values in [('xgboost',[p['duration_s'] for p in predicted]),('baseline',[p['baseline_duration_s'] for p in predicted])]:
            computed=metrics(actual,np.array(values))
            for field,value in computed.items():self.assertAlmostEqual(value,report['final_test'][key][field],places=9)
        folds=report['walk_forward'];total=sum(f['evaluation']['samples'] for f in folds)
        for key in ('xgboost','baseline'):
            mae=sum(f[key]['mae_seconds']*f['evaluation']['samples'] for f in folds)/total
            rmse=(sum(f[key]['rmse_seconds']**2*f['evaluation']['samples'] for f in folds)/total)**.5
            self.assertAlmostEqual(mae,report['walk_forward_aggregate'][key]['mae_seconds'],places=9)
            self.assertAlmostEqual(rmse,report['walk_forward_aggregate'][key]['rmse_seconds'],places=9)

    def test_incomplete_and_nonpositive_prediction_batches_are_not_zero_matrix_arcs(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        points=[Coordinate(6.9,79.9,'A'),Coordinate(6.91,79.91,'B')]
        for values in ([],[{'duration_s':1}],[{'duration_s':0}]*2,[{'duration_s':float('nan')}]*2):
            broken=SimpleNamespace(status=lambda:{'available':True},predict_many=Mock(return_value=values))
            with self.assertRaises(InvalidTravelCosts):MLTravelTimeProvider(date(2026,10,15),None,broken).precompute(points,'morning',21600)

    def test_nonfinite_or_underflow_model_output_is_unavailable(self):
        request=dict(origin_id='UNKNOWN',destination_id='ALSO_UNKNOWN',departure_timestamp='2026-10-21T06:00:00+05:30',distance_m=100)
        for value in (float('nan'),float('inf'),-1000.):
            with patch.object(self.model.model,'predict',return_value=np.array([value])):
                with self.assertRaises(ModelUnavailable):self.model.predict_many([request])


if __name__ == '__main__': unittest.main()
