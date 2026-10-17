"""Exercise the running API and store actual ML inference/routing responses."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from ml.features import DISCLAIMER
from travel_time import Coordinate, DeterministicSimulationProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--vehicle-id', required=True, help='Existing pre-trip vehicle; this command intentionally generates and stores both routes.')
    parser.add_argument('--output', type=Path, default=BACKEND.parent / 'docs' / 'ml_routing_demo.json')
    args = parser.parse_args()
    def request(path, body=None):
        req = Request(args.base_url + path, data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=90) as response: return json.load(response)
    status = request('/ml/status')
    if not status['available']: raise RuntimeError(status['reason'])
    roster = [student for student in request('/routing/students') if student['active'] and student['vehicle_id'] == args.vehicle_id and student['location_confirmed']]
    if not roster: raise RuntimeError('Select a vehicle with an active confirmed student roster for this routing demonstration.')
    student = roster[0]
    school = next(s for s in request('/routing/schools') if s['id'] == student['school_id'])
    if not school['location_confirmed']: raise RuntimeError('Assigned school location must be confirmed.')
    points = [Coordinate(student['home_latitude'], student['home_longitude']), Coordinate(school['latitude'], school['longitude'])]
    example_distance = DeterministicSimulationProvider().precompute(points, 'morning', 21600).distance_metres[0][1]
    predictions = []
    for weather in (None, 0, 1):
        body = dict(origin_id=student['home_id'], destination_id=school['id'],
            departure_timestamp='2026-10-15T07:30:00+05:30', distance_m=example_distance, weather_flag=weather)
        predictions.append({'input': body, 'output': request('/ml/predict', body)})
    unknown_body = {**predictions[0]['input'], 'origin_id': 'UNSEEN_ORIGIN', 'destination_id': 'UNSEEN_DESTINATION'}
    unknown = request('/ml/predict', unknown_body)
    invalid = {**unknown_body, 'distance_m': -1}
    try: request('/ml/predict', invalid)
    except HTTPError as error:
        if error.code != 422: raise
        validation_status = error.code
    else: raise AssertionError('Negative distance must be rejected.')
    routes = []
    for direction, departure in (('morning', 21600), ('afternoon', 45000)):
        route = request('/routes/generate', dict(vehicle_id=args.vehicle_id, direction=direction,
            departure_seconds=departure, pickup_service_seconds=30, delivery_service_seconds=30,
            solver_time_limit_seconds=2, provider='ml', weather_flag=None))
        # Retrieval must return the stored version, not create a new result.
        latest = request(f'/routes/latest?vehicle_id={args.vehicle_id}&direction={direction}')
        assert route['route_id'] == latest['route_id'] and route['version'] == latest['version']
        assert route['provider_source']['provider'] == 'xgboost_synthetic_v1'
        if route['feasibility_status'] == 'feasible':
            for action in ('pickup', 'delivery'):
                served = [s['student_id'] for s in route['stops'] if s['action'] == action]
                assert len(served) == len(set(served)) == route['student_count']
            assert all(0 <= s['load_after'] <= route['capacity'] for s in route['stops'])
        routes.append(route)
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'disclaimer': DISCLAIMER,
        'model_version': status['model_version'], 'predictions': predictions,
        'unknown_segment': {'input': unknown_body, 'output': unknown}, 'invalid_input_http_status': validation_status, 'routes': routes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'model_version': status['model_version'],
        'predictions_seconds': [{'weather_flag': p['input']['weather_flag'], 'xgboost': p['output']['duration_s'], 'baseline': p['output']['baseline_duration_s']} for p in predictions],
        'unknown_segment_seconds': unknown['duration_s'], 'invalid_input_http_status': validation_status,
        'routes': [{k: r[k] for k in ('direction', 'route_id', 'version', 'student_count', 'feasibility_status', 'distance_metres', 'driving_seconds', 'service_seconds', 'waiting_seconds', 'total_duration_seconds', 'solver_runtime_seconds', 'errors')} for r in routes],
        'output': str(args.output), 'disclaimer': DISCLAIMER}, indent=2))


if __name__ == '__main__': main()
