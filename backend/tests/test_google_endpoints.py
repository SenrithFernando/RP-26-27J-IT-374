"""No live calls: guard distinct Google Routes REST method endpoints."""
import io
import unittest
from unittest.mock import patch
from traffic_google import post_google,ProviderFailure


class GoogleEndpointTests(unittest.TestCase):
    def test_daily_geometry_is_optin_and_recommendation_never_adds_it(self):
        from types import SimpleNamespace
        from landmark import Generation,generate_daily
        with patch('landmark.scenario',return_value=SimpleNamespace(vehicle_id='TEST')),patch('route_service.generate_and_store',return_value={}) as generate:
            for direction in ('morning','afternoon'):
                generate_daily(Generation(direction=direction,provider='google',live_http_budget=5),object())
                self.assertFalse(generate.call_args.args[1].include_geometry)
                generate_daily(Generation(direction=direction,provider='google',live_http_budget=5,include_geometry=True),object())
                self.assertTrue(generate.call_args.args[1].include_geometry)
                self.assertEqual(generate.call_args.args[1].live_http_budget,5)
            generate_daily(Generation(direction='morning',provider='google',departure_mode='recommend',recommendation_live_budget=1,include_geometry=True),object())
            self.assertFalse(generate.call_args.args[1].include_geometry)

    def test_matrix_endpoint(self):
        with patch('traffic_google.urlopen',return_value=io.BytesIO(b'[]')) as call:
            self.assertEqual(post_google('computeRouteMatrix',{},'status','test-only',1),[])
            self.assertEqual(call.call_args.args[0].full_url,'https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix')

    def test_geometry_endpoint(self):
        with patch('traffic_google.urlopen',return_value=io.BytesIO(b'{}')) as call:
            self.assertEqual(post_google('computeRoutes',{},'routes','test-only',1),{})
            self.assertEqual(call.call_args.args[0].full_url,'https://routes.googleapis.com/directions/v2:computeRoutes')

    def test_unsupported_method_makes_no_request(self):
        with patch('traffic_google.urlopen') as call:
            with self.assertRaises(ProviderFailure):post_google('unknown',{},'','test-only',1)
            call.assert_not_called()
