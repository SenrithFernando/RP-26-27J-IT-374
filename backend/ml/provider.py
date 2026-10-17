"""Static departure-time ML matrix; predictions are fetched before solver callbacks."""
from datetime import datetime, time, timedelta
from math import ceil
from zoneinfo import ZoneInfo
from travel_time import DeterministicSimulationProvider, InvalidTravelCosts, TravelCosts
from ml.features import DISCLAIMER
from ml.predictor import ModelUnavailable, predictor


class MLTravelTimeProvider:
    def __init__(self, service_date, weather_flag=None, model=predictor):
        self.service_date, self.weather_flag, self.model = service_date, weather_flag, model

    def precompute(self, coordinates, direction, departure_seconds):
        if direction not in ('morning', 'afternoon'): raise InvalidTravelCosts('Unknown direction.')
        if not self.model.status()['available']: raise InvalidTravelCosts(self.model.error)
        # Reuse the validated existing geometry calculation; distance is not predicted.
        distances = DeterministicSimulationProvider().precompute(coordinates, direction, departure_seconds).distance_metres
        durations = [[0 for _ in coordinates] for _ in coordinates]
        stamp = datetime.combine(self.service_date, time(), tzinfo=ZoneInfo('Asia/Colombo')) + timedelta(seconds=departure_seconds)
        requests, arcs = [], []
        for i, origin in enumerate(coordinates):
            if not origin.location_id: raise InvalidTravelCosts('ML provider requires stable routing location IDs.')
            for j, destination in enumerate(coordinates):
                if not destination.location_id: raise InvalidTravelCosts('ML provider requires stable routing location IDs.')
                if distances[i][j] == 0: continue  # Exact colocated/diagonal geographic arcs; not fabricated model predictions.
                requests.append(dict(origin_id=origin.location_id, destination_id=destination.location_id,
                    departure_timestamp=stamp, distance_m=distances[i][j], weather_flag=self.weather_flag))
                arcs.append((i, j))
        try: predictions = self.model.predict_many(requests)
        except (ModelUnavailable, ValueError) as error: raise InvalidTravelCosts(str(error)) from None
        for (i, j), result in zip(arcs, predictions): durations[i][j] = ceil(result['duration_s'])
        return TravelCosts(durations, distances, {
            'provider': 'xgboost_synthetic_v1', 'duration_source': 'ml_prediction',
            'training_data_source': 'synthetic', 'model_version': self.model.metadata['model_version'],
            'distance_source': 'haversine_straight_line', 'distance_is_approximate': True,
            'departure_timestamp': stamp.isoformat(), 'weather_flag': self.weather_flag,
            'weather_source': 'missing' if self.weather_flag is None else 'planning_input',
            'prediction_count': len(predictions), 'unknown_segment_predictions': sum(p['unknown_segment'] for p in predictions),
            'warnings': sorted({warning for p in predictions for warning in p['warnings']}),
            'time_assumption': 'Static matrix evaluated at vehicle departure for every arc, not a time-dependent traffic forecast.',
            'zero_arc_policy': 'Colocated/diagonal arcs have zero travel duration; service times remain separate.',
            'description': DISCLAIMER,
        })
