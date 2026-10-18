"""No live calls: guard distinct Google Routes REST method endpoints."""
import io
import unittest
from unittest.mock import patch
from traffic_google import post_google,ProviderFailure


class GoogleEndpointTests(unittest.TestCase):
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
