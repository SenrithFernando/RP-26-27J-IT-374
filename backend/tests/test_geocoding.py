"""Adapter tests use synthetic responses; no Google calls or real credentials."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
from fastapi import HTTPException
from pydantic import ValidationError
from geocoding import GeocodeRequest, geocode, google_geocode
from persistence import StudentWrite


class GeocodingTests(unittest.TestCase):
    def response(self, body):
        return patch("geocoding.urlopen", return_value=io.BytesIO(json.dumps(body).encode()))

    def test_manual_configuration_returns_no_coordinates(self):
        with patch("geocoding.load_dotenv"), patch.dict("os.environ", {"GEOCODING_PROVIDER": "auto", "GOOGLE_GEOCODING_API_KEY": ""}):
            with self.assertRaises(HTTPException) as error:
                geocode(GeocodeRequest(address="Synthetic test address"))
        self.assertEqual(error.exception.status_code, 503)

    def test_google_adapter_returns_unconfirmed_provider_result(self):
        body = {"status": "OK", "results": [{"formatted_address": "Synthetic test address", "geometry": {"location": {"lat": 6.9271, "lng": 79.8612}}}]}
        with self.response(body):
            result = google_geocode("Synthetic test address", "synthetic-key")
        self.assertEqual(result["latitude"], 6.9271)
        self.assertEqual(result["provider"], "google")
        self.assertFalse(result["location_confirmed"])
        self.assertNotIn("key", result)

    def test_failed_or_malformed_responses_never_produce_coordinates(self):
        for body in ({"status": "ZERO_RESULTS"}, {"status": "REQUEST_DENIED", "error_message": "synthetic-key"},
                     {"status": "OK", "results": [{}]}, {"status": "OK", "results": [{"geometry": {"location": {"lat": 999, "lng": 80}}}]}, []):
            with self.subTest(body=body), self.response(body), self.assertRaises(HTTPException) as error:
                google_geocode("Synthetic test address", "synthetic-key")
            self.assertNotIn("synthetic-key", error.exception.detail)
        with patch("geocoding.urlopen", side_effect=URLError("synthetic-key")), self.assertRaises(HTTPException) as error:
            google_geocode("Synthetic test address", "synthetic-key")
        self.assertNotIn("synthetic-key", error.exception.detail)

    def test_student_requires_explicit_confirmation_and_address(self):
        payload = dict(name="Synthetic student", school_id="SCHOOL_01", vehicle_id="VAN_01",
                       home_latitude=6.9, home_longitude=79.8, input_source="simulated",
                       home_address="Synthetic test address", location_confirmed=True)
        self.assertTrue(StudentWrite(**payload).location_confirmed)
        for invalid in ({"location_confirmed": False}, {"home_address": " "}, {"home_latitude": 91}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                StudentWrite(**{**payload, **invalid})


if __name__ == "__main__":
    unittest.main()
