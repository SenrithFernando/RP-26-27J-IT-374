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


if __name__ == '__main__': unittest.main()
