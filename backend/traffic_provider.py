"""Observable departure-snapshot source selection and directed traffic scenarios."""
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import json
from math import ceil, isfinite
from zoneinfo import ZoneInfo
from ml.features import DISCLAIMER, feature_record, segment_id
from ml.predictor import ARTIFACTS, predictor
from ml.provider import MLTravelTimeProvider
from traffic_google import GoogleRoutesAdapter
from travel_time import DeterministicSimulationProvider, InvalidTravelCosts, TravelCosts

SNAPSHOT_LIMITATION = 'PP1 uses one departure-time matrix snapshot for every arc. This is not a fully time-dependent solver.'


class BaselineRepository:
    def __init__(self): self.baseline = None; self.version = None; self.error = 'Baseline not loaded.'
    def load(self):
        try:
            version = json.loads((ARTIFACTS / 'current.json').read_text(encoding='utf-8'))['model_version']
            if not isinstance(version, str) or '/' in version or '\\' in version or not version.startswith('synthetic-xgb-v1-'): raise ValueError()
            directory = ARTIFACTS / version
            metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
            raw = (directory / 'baseline.json').read_bytes()
            if sha256(raw).hexdigest() != metadata['files_sha256']['baseline.json']: raise ValueError()
            baseline = json.loads(raw)
            if not all(isfinite(v) and v > 0 for v in [baseline['unseen_segment_fallback'], *baseline['segment_means'].values()]): raise ValueError()
            self.baseline, self.version, self.error = baseline, version, None
        except Exception: self.baseline = None; self.error = 'Verified historical baseline artifact unavailable.'


baseline_repository = BaselineRepository()


class TrafficSnapshotProvider:
    def __init__(self, request, live=None, model=predictor, baseline=baseline_repository):
        self.request, self.live, self.model, self.baseline = request, live or GoogleRoutesAdapter(), model, baseline
        self.reference_stops = None
        self.live_http_requests=0
        if request.provider=='google':
            from traffic_google import ProviderFailure
            transport=self.live.transport
            def bounded_transport(*args):
                if request.live_http_budget is not None and self.live_http_requests>=request.live_http_budget:
                    raise ProviderFailure('explicit_request_budget','Administrator HTTP request budget exhausted; live pairs unavailable.')
                self.live_http_requests+=1
                return transport(*args)
            self.live.transport=bounded_transport

    def precompute(self, coordinates, direction, departure_seconds):
        request = self.request
        simulated = DeterministicSimulationProvider() if request.simulation_speed_mps is None else DeterministicSimulationProvider(request.simulation_speed_mps, request.simulation_speed_mps)
        base = simulated.precompute(coordinates, direction, departure_seconds)
        stamp = datetime.combine(request.service_date, time(), tzinfo=ZoneInfo('Asia/Colombo')) + timedelta(seconds=departure_seconds)
        n = len(coordinates)
        live_values, live_failures = ({}, {})
        if request.provider == 'google': live_values, live_failures = self.live.matrix(coordinates, stamp, request.force_live_failure)
        ml_costs, ml_error = None, None
        needs_ml = request.provider == 'ml' or request.provider == 'google' and request.fallback_policy != 'none' and bool(live_failures)
        if needs_ml:
            try: ml_costs = MLTravelTimeProvider(request.service_date, request.weather_flag, self.model).precompute(coordinates, direction, departure_seconds)
            except Exception: ml_error = self.model.status().get('reason') or 'Loaded model inference failed; no ML estimate is available.'
        durations, distances, sources = [], [], []
        median_lat = sorted(c.latitude for c in coordinates)[n // 2]
        affected = 0
        for i, origin in enumerate(coordinates):
            dr, mr, sr = [], [], []
            for j, destination in enumerate(coordinates):
                distance, duration = base.distance_metres[i][j], None
                source, reason, failure_code, distance_source = 'unavailable', None, None, 'haversine_straight_line'
                reason_chain = []
                if distance == 0 and request.provider != 'unavailable':
                    duration, source = 0, 'geographic_zero'
                elif request.provider == 'simulation':
                    duration, source = base.duration_seconds[i][j], 'simulation'
                    selected = (request.traffic_scenario == 'northbound_delay' and origin.latitude < median_lat <= destination.latitude)
                    selected |= (request.traffic_scenario == 'directed_incident' and int(sha256(segment_id(origin.location_id or f'{origin.latitude},{origin.longitude}', destination.location_id or f'{destination.latitude},{destination.longitude}').encode()).hexdigest()[:8], 16) % 5 == 0)
                    if selected:
                        duration = ceil(duration * (1.8 if request.traffic_scenario == 'northbound_delay' else 2.5)) + (120 if request.traffic_scenario == 'northbound_delay' else 180)
                        affected += 1
                elif request.provider == 'google' and (i,j) in live_values:
                    duration, distance = live_values[i,j]; source, distance_source = 'google_live', 'google_road_network'
                else:
                    if request.provider == 'google':
                        issue = live_failures.get((i,j), {'code': 'partial_matrix', 'message': 'Google pair unavailable.'})
                        reason_chain.append(issue['message']); failure_code = issue['code']
                    if request.provider == 'unavailable': reason_chain.append('Explicit unavailable estimate selected.')
                    unreachable = failure_code == 'unreachable'
                    allow_ml = request.provider == 'ml' or request.provider == 'google' and request.fallback_policy != 'none'
                    if allow_ml and not unreachable:
                        if ml_costs is not None:
                            duration, source = ml_costs.duration_seconds[i][j], 'ml_prediction'
                        else: reason_chain.append(ml_error or 'ML provider is unavailable.')
                    allow_baseline = request.provider == 'baseline' or (request.provider in ('ml','google') and request.fallback_policy == 'ml_then_baseline')
                    if duration is None and allow_baseline and not unreachable:
                        if self.baseline.baseline is not None:
                            means = self.baseline.baseline['segment_means']
                            duration = ceil(means.get(segment_id(origin.location_id, destination.location_id), self.baseline.baseline['unseen_segment_fallback']))
                            source = 'historical_baseline'
                            if segment_id(origin.location_id, destination.location_id) not in means: reason_chain.append('Unseen segment: training-only global historical mean used.')
                        else: reason_chain.append(self.baseline.error)
                reason = ' '.join(reason_chain) or None
                dr.append(duration); mr.append(distance if duration is not None else None)
                sr.append({'source': source, 'distance_source': distance_source,
                    'fallback_reason': reason if source != 'unavailable' else None,
                    'unavailable_reason': reason if source == 'unavailable' else None,
                    'failure_code': failure_code,
                    'scenario': request.traffic_scenario if request.provider == 'simulation' else 'normal',
                    'scenario_modified': request.provider == 'simulation' and duration != base.duration_seconds[i][j],
                    'model_version': self.model.metadata['model_version'] if source == 'ml_prediction' else self.baseline.version if source == 'historical_baseline' else None,
                    'training_data_source': 'synthetic' if source in ('ml_prediction','historical_baseline') else None})
            durations.append(dr); distances.append(mr); sources.append(sr)
        counts = Counter(item['source'] for row in sources for item in row if item['source'] != 'geographic_zero')
        actual = list(counts)
        aggregate = actual[0] if len(actual) == 1 else 'mixed' if actual else 'geographic_zero'
        metadata = dict(base.metadata)
        metadata.update(provider={'ml_prediction': 'xgboost_synthetic_v1', 'google_live': 'google_routes', 'historical_baseline': 'historical_baseline', 'simulation': 'deterministic_simulation_v1'}.get(aggregate, aggregate),
            duration_source=aggregate, requested_provider=request.provider, fallback_policy=request.fallback_policy,
            traffic_scenario=request.traffic_scenario, scenario_modified_directed_arcs=affected,
            distance_source='google_road_network' if actual == ['google_live'] else 'mixed' if 'google_live' in counts else 'haversine_straight_line',
            distance_is_approximate=actual != ['google_live'], live_configured=bool(self.live.configuration['key']),
            force_live_failure=request.force_live_failure, departure_timestamp=stamp.isoformat(),
            snapshot_generated_at=datetime.now(timezone.utc).isoformat(), time_assumption=SNAPSHOT_LIMITATION,
            matrix_source_counts=dict(counts), has_unavailable_pairs=any(v is None for row in durations for v in row),
            fallback_reasons=sorted({item['fallback_reason'] or item['unavailable_reason'] for row in sources for item in row if item['fallback_reason'] or item['unavailable_reason']}),
            model_version=self.model.metadata['model_version'] if ml_costs else self.baseline.version if 'historical_baseline' in counts else None,
            live_http_requests=self.live_http_requests,live_http_budget=request.live_http_budget,
            matrix_contains_mixed_sources=len(actual)>1,
            matrix_failure_counts=dict(Counter(item['failure_code'] for row in sources for item in row if item.get('failure_code'))),
            training_data_source='synthetic' if any(source in counts for source in ('ml_prediction','historical_baseline')) else None,
            warnings=ml_costs.metadata.get('warnings', []) if ml_costs else [], description=DISCLAIMER if ml_costs else 'Source-labelled traffic planning estimates; not measured journeys.')
        fingerprint = [durations, distances, sources, [(c.location_id,c.latitude,c.longitude) for c in coordinates], stamp.isoformat(), request.traffic_scenario]
        metadata['matrix_snapshot_id'] = sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()[:24]
        return TravelCosts(durations, distances, metadata, sources)


def provider_status():
    from traffic_google import config
    settings = config()
    return {'google': {'configured': bool(settings['key']), 'status': 'configured_not_verified' if settings['key'] else 'not_configured',
        'reason': None if settings['key'] else 'GOOGLE_ROUTES_API_KEY is missing on the backend.',
        'timeout_seconds': settings['timeout'], 'total_matrix_budget_seconds': settings['budget'],
        'cache_ttl_seconds': 60, 'cache_max_entries': 32, 'max_unique_locations': 40,
        'road_geometry_supported': True, 'google_map_display_configured': bool(settings['map_key'])},
        'ml': predictor.status(), 'baseline': {'available': baseline_repository.baseline is not None, 'reason': baseline_repository.error,
            'data_source': 'synthetic' if baseline_repository.baseline else None},
        'scenarios': ['normal', 'northbound_delay', 'directed_incident'], 'time_assumption': SNAPSHOT_LIMITATION}
