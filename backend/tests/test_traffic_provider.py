"""Mocked Google contracts are test inputs, not live API observations."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest
from urllib.error import HTTPError
from traffic_google import BoundedCache, GoogleRoutesAdapter, ProviderFailure, post_google
from traffic_provider import TrafficSnapshotProvider, baseline_repository
from ml.predictor import predictor
from route_schemas import GenerateRouteRequest
from route_solver import solve_registered_route
from routing_domain import GenerationSettings
from travel_time import Coordinate, InvalidTravelCosts, validate_costs
from test_dual_route_solver import fixture

CONFIG = {'key': 'synthetic-test-credential', 'map_key': '', 'timeout': .2, 'budget': 1.}
FUTURE = datetime.now(timezone.utc) + timedelta(days=2)
POINTS = [Coordinate(6.90,79.80,'A'), Coordinate(6.91,79.81,'B'), Coordinate(6.92,79.82,'C')]


def response(method, body, fields, key, timeout):
    return [{'originIndex':i, 'destinationIndex':j, 'status': {}, 'condition':'ROUTE_EXISTS',
        'duration':'100.1s', 'distanceMeters':1000} for i in range(len(body['origins'])) for j in range(len(body['destinations']))]


class GoogleAdapterTests(unittest.TestCase):
    def test_unsupported_departure_error_is_sanitized(self):
        from io import BytesIO
        error=HTTPError('https://redacted.invalid',400,'Bad Request',{},BytesIO(b'{"error":{"message":"departure time unsupported for this date; PRIVATE_SENTINEL"}}'))
        with patch('traffic_google.urlopen',side_effect=error):
            with self.assertRaises(ProviderFailure) as raised:post_google('computeRouteMatrix',{},'duration','synthetic-test-key',1)
        self.assertEqual(raised.exception.code,'unsupported_departure')
        self.assertNotIn('PRIVATE_SENTINEL',str(raised.exception))
    def test_missing_credentials_forced_failure_and_past_departure_do_not_call_network(self):
        transport = Mock(side_effect=AssertionError('No network permitted'))
        for settings, force, stamp, expected in [({**CONFIG,'key':''},False,FUTURE,'missing_credentials'),
                (CONFIG,True,FUTURE,'forced_live_failure'), (CONFIG,False,datetime(2000,1,1,tzinfo=timezone.utc),'past_departure')]:
            values, failures = GoogleRoutesAdapter(settings,transport).matrix(POINTS,stamp,force)
            self.assertFalse(values); self.assertEqual(failures[0,1]['code'],expected)
        transport.assert_not_called()
        large = [Coordinate(6+i*.001,79.8,str(i)) for i in range(41)]
        _, failures = GoogleRoutesAdapter(CONFIG,transport).matrix(large,FUTURE)
        self.assertEqual(failures[0,1]['code'],'matrix_limit')
        _, failures = GoogleRoutesAdapter({**CONFIG,'budget':0},transport).matrix(POINTS,FUTURE)
        self.assertEqual(failures[0,1]['code'],'matrix_timeout')
        transport.assert_not_called()

    def test_success_cache_expiry_bounds_and_departure_cache_key(self):
        store = BoundedCache(maximum=2, ttl=60)
        transport = Mock(side_effect=response)
        adapter = GoogleRoutesAdapter(CONFIG,transport,store)
        values, failures = adapter.matrix(POINTS,FUTURE)
        self.assertFalse(failures); self.assertEqual(values[0,1],(101,1000))
        original_expiry = next(iter(store.items.values()))[0]
        adapter.matrix(POINTS,FUTURE); self.assertEqual(transport.call_count,1)
        self.assertEqual(next(iter(store.items.values()))[0],original_expiry)
        adapter.matrix(POINTS,FUTURE+timedelta(minutes=1)); self.assertEqual(transport.call_count,2)
        adapter.matrix(POINTS,FUTURE+timedelta(minutes=2)); self.assertLessEqual(len(store.items),2)
        with patch('traffic_google.monotonic', return_value=10**12): self.assertIsNone(store.get('any'))
        self.assertEqual(len(store.items),0)

    def test_timeouts_quota_malformed_and_partial_elements(self):
        for code in ('timeout_or_network','quota_exceeded','malformed_response'):
            adapter = GoogleRoutesAdapter(CONFIG,Mock(side_effect=ProviderFailure(code,'Synthetic transport failure')),BoundedCache())
            values, failures = adapter.matrix(POINTS,FUTURE)
            self.assertFalse(values); self.assertEqual(failures[0,1]['code'],code)
        def partial(*args):
            return [{'originIndex':0,'destinationIndex':1,'condition':'ROUTE_EXISTS','duration':'12s','distanceMeters':100},
                    {'originIndex':1,'destinationIndex':0,'condition':'ROUTE_NOT_FOUND','status':{'code':5}}]
        adapter = GoogleRoutesAdapter(CONFIG,partial,BoundedCache())
        values, failures = adapter.matrix(POINTS,FUTURE)
        self.assertEqual(values[0,1],(12,100)); self.assertEqual(failures[1,0]['code'],'unreachable')
        self.assertEqual(failures[2,0]['code'],'partial_matrix')
        self.assertFalse(adapter.cache.items)
        def invalid(*args):
            return [{'originIndex':0,'destinationIndex':1,'condition':'ROUTE_EXISTS','duration':'12s','distanceMeters':100},
                    {'originIndex':0,'destinationIndex':1,'condition':'ROUTE_EXISTS','duration':'12s','distanceMeters':100},
                    {'originIndex':1,'destinationIndex':0,'condition':'ROUTE_EXISTS','status':{'code':8}},
                    {'originIndex':2,'destinationIndex':0,'condition':'ROUTE_EXISTS','duration':'nans','distanceMeters':100}]
        values, failures = GoogleRoutesAdapter(CONFIG,invalid,BoundedCache()).matrix(POINTS,FUTURE)
        self.assertNotIn((0,1),values)
        self.assertEqual(failures[0,1]['code'],'duplicate_element')
        self.assertEqual(failures[1,0]['code'],'quota_exceeded')
        self.assertEqual(failures[2,0]['code'],'invalid_element')
        with patch('traffic_google.urlopen',side_effect=HTTPError('https://example.invalid',429,'quota',{},None)):
            with self.assertRaises(ProviderFailure) as caught: post_google('computeRouteMatrix',{},'',CONFIG['key'],1)
        self.assertEqual(caught.exception.code,'quota_exceeded')
        self.assertNotIn(CONFIG['key'],str(caught.exception))
        with patch('traffic_google.urlopen',side_effect=TimeoutError()):
            with self.assertRaises(ProviderFailure) as caught: post_google('computeRouteMatrix',{},'',CONFIG['key'],1)
        self.assertEqual(caught.exception.code,'timeout_or_network')

    def test_geometry_preserves_order_and_reports_missing_display_configuration(self):
        transport = Mock(return_value={'routes':[{'polyline':{'encodedPolyline':'synthetic-test-geometry'}}]})
        adapter = GoogleRoutesAdapter(CONFIG,transport)
        stops = [{'latitude':p.latitude,'longitude':p.longitude} for p in POINTS]
        result = adapter.geometry(stops,FUTURE)
        self.assertEqual(result['status'],'available'); self.assertFalse(result['map_available'])
        body = transport.call_args.args[1]
        self.assertFalse(body['optimizeWaypointOrder']); self.assertEqual(len(body['intermediates']),1)
        self.assertEqual(adapter.geometry(stops,FUTURE,True)['status'],'unavailable')
        self.assertEqual(transport.call_count,1)

    def test_geometry_shares_explicit_matrix_budget(self):
        transport=Mock(side_effect=response)
        request=GenerateRouteRequest(vehicle_id='FIXED',direction='morning',service_date=FUTURE.date(),departure_seconds=21600,provider='google',live_http_budget=1)
        provider=TrafficSnapshotProvider(request,live=GoogleRoutesAdapter(CONFIG,transport,BoundedCache(ttl=0)))
        provider.precompute(POINTS,'morning',21600)
        geometry=provider.live.geometry([{'latitude':p.latitude,'longitude':p.longitude} for p in POINTS],FUTURE)
        self.assertEqual(geometry['status'],'unavailable')
        self.assertEqual(geometry['failure_code'],'explicit_request_budget')
        self.assertEqual(provider.live_http_requests,1)
        self.assertEqual(transport.call_count,1)


class SnapshotTests(unittest.TestCase):
    def test_explicit_zero_budget_never_calls_google_and_preserves_failure_metadata(self):
        from landmark_solver import solve_landmark
        transport=Mock(side_effect=AssertionError('Zero HTTP budget'))
        live=GoogleRoutesAdapter(CONFIG,transport,BoundedCache(ttl=0))
        request=self.request(provider='google',live_http_budget=0,fallback_policy='none')
        vehicle,students,schools=fixture();vehicle=replace(vehicle,capacity=20)
        result=solve_landmark(vehicle,students,schools,GenerationSettings('morning',21600),TrafficSnapshotProvider(request,live))
        self.assertEqual(result['feasibility_status'],'unavailable')
        self.assertEqual(result['provider_source']['requested_provider'],'google')
        self.assertEqual(result['provider_source']['live_http_requests'],0)
        self.assertIn('explicit_request_budget',result['provider_source']['matrix_failure_counts'])
        transport.assert_not_called()
    @classmethod
    def setUpClass(cls): predictor.load(); baseline_repository.load()

    def request(self, **values):
        return GenerateRouteRequest(vehicle_id='FIXED',direction='morning',departure_seconds=21600,
            service_date=FUTURE.date(), solver_time_limit_seconds=1, **values)

    def test_directed_scenarios_are_selective_deterministic_and_not_global_scaling(self):
        normal = TrafficSnapshotProvider(self.request(provider='simulation')).precompute(POINTS,'morning',21600)
        heavy_provider = TrafficSnapshotProvider(self.request(provider='simulation',traffic_scenario='northbound_delay'))
        heavy = heavy_provider.precompute(POINTS,'morning',21600)
        self.assertGreater(heavy.duration_seconds[0][1], normal.duration_seconds[0][1])
        self.assertEqual(heavy.duration_seconds[1][0],normal.duration_seconds[1][0])
        self.assertEqual(heavy.duration_seconds, heavy_provider.precompute(POINTS,'morning',21600).duration_seconds)
        self.assertNotEqual(heavy.metadata['matrix_snapshot_id'],normal.metadata['matrix_snapshot_id'])

    def test_forced_live_failure_uses_loaded_real_xgboost_or_explicit_unavailable(self):
        transport = Mock(side_effect=AssertionError('Forced failure must not call live API'))
        live = GoogleRoutesAdapter(CONFIG,transport)
        costs = TrafficSnapshotProvider(self.request(provider='google',force_live_failure=True),live).precompute(POINTS,'morning',21600)
        validate_costs(costs,3)
        self.assertEqual(costs.metadata['duration_source'],'ml_prediction')
        self.assertEqual(costs.leg_sources[0][1]['failure_code'],'forced_live_failure')
        self.assertEqual(costs.leg_sources[0][1]['model_version'],predictor.metadata['model_version'])
        transport.assert_not_called()
        class MissingModel:
            metadata = None
            error = 'Synthetic missing model'
            def status(self): return {'available':False,'reason':self.error}
        unavailable = TrafficSnapshotProvider(self.request(provider='google',force_live_failure=True),live,MissingModel()).precompute(POINTS,'morning',21600)
        self.assertIsNone(unavailable.duration_seconds[0][1])
        fallback = TrafficSnapshotProvider(self.request(provider='google',force_live_failure=True,fallback_policy='ml_then_baseline'),live,MissingModel()).precompute(POINTS,'morning',21600)
        self.assertEqual(fallback.leg_sources[0][1]['source'],'historical_baseline')
        validate_costs(fallback,3)
        vehicle, students, schools = fixture()
        rejected = solve_registered_route(vehicle,students,schools,GenerationSettings('morning',21600,30,30,21600,1),TrafficSnapshotProvider(self.request(provider='unavailable')))
        self.assertEqual(rejected['feasibility_status'],'unavailable')
        self.assertEqual(rejected['stops'],[]); self.assertIsNone(rejected['driving_seconds'])

    def test_unreachable_never_becomes_ml_zero_cost(self):
        def unreachable(*args): return [{'originIndex':0,'destinationIndex':1,'condition':'ROUTE_NOT_FOUND','status':{'code':5}}]
        live = GoogleRoutesAdapter(CONFIG,unreachable,BoundedCache())
        costs = TrafficSnapshotProvider(self.request(provider='google'),live).precompute(POINTS,'morning',21600)
        self.assertIsNone(costs.duration_seconds[0][1]); self.assertEqual(costs.leg_sources[0][1]['failure_code'],'unreachable')
        with self.assertRaises(InvalidTravelCosts): validate_costs(costs,3)

    def test_partial_matrix_mixed_route_and_no_calls_during_ortools(self):
        vehicle, students, schools = fixture()
        students = students[:1]
        state = {'solver_constructed':False}
        def partial(method,body,*args):
            self.assertFalse(state['solver_constructed'])
            return [e for e in response(method,body,*args) if (e['originIndex'],e['destinationIndex']) != (1,0)]
        live = GoogleRoutesAdapter(CONFIG,partial,BoundedCache())
        provider = TrafficSnapshotProvider(self.request(provider='google'),live)
        import route_solver
        original = route_solver.pywrapcp.RoutingModel
        def construct(*args): state['solver_constructed'] = True; return original(*args)
        with patch('route_solver.pywrapcp.RoutingModel',side_effect=construct):
            result = solve_registered_route(vehicle,students,schools,GenerationSettings('morning',21600,30,30,21600,1),provider)
        self.assertEqual(result['feasibility_status'],'feasible',result['errors'])
        self.assertEqual(result['provider_source']['duration_source'],'mixed')
        self.assertTrue(result['provider_source']['matrix_contains_mixed_sources'])
        self.assertEqual(set(result['provider_source']['route_source_counts']),{'google_live','ml_prediction'})
        self.assertTrue(any(s['travel_source'].get('fallback_reason') for s in result['stops']))

    def test_alternative_repricing_ignores_old_normal_costs(self):
        vehicle, students, schools = fixture()
        settings = GenerationSettings('morning',21600,30,30,21600,1)
        normal = solve_registered_route(vehicle,students,schools,settings,TrafficSnapshotProvider(self.request(provider='simulation')))
        provider = TrafficSnapshotProvider(self.request(provider='simulation',traffic_scenario='northbound_delay'))
        provider.reference_stops = [{**s,'driving_seconds_from_previous':999999} for s in normal['stops']]
        heavy = solve_registered_route(vehicle,students,schools,settings,provider)
        comparison = heavy['alternative_comparison']
        self.assertTrue(comparison['same_matrix']); self.assertEqual(comparison['matrix_snapshot_id'],heavy['provider_source']['matrix_snapshot_id'])
        self.assertNotEqual(comparison['reference']['driving_seconds'],normal['driving_seconds'])
        self.assertLess(comparison['reference']['driving_seconds'],999999)
        self.assertEqual(comparison['reference_minus_selected']['driving_seconds'],comparison['reference']['driving_seconds']-heavy['driving_seconds'])


if __name__ == '__main__': unittest.main()
