"""Mocked geocoding with session-private rollback tables; no live requests."""
import os,unittest
from copy import deepcopy
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select
import test_landmark_daily as fixtures
from models import Student,RouteVersion,LandmarkInputEvent,Trip
from landmark import PREFIX,DEFAULT_DATE,VEHICLE

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_REGISTRATION_TESTS')=='1','Opt in to isolated registration tests.')
class RegistrationGeocodingTests(unittest.TestCase):
 setUp=fixtures.LandmarkTests.setUp
 tearDown=fixtures.LandmarkTests.tearDown
 event=fixtures.LandmarkTests.event
 day=fixtures.LandmarkTests.day
 generate=fixtures.LandmarkTests.generate
 publish=fixtures.LandmarkTests.publish
 def body(self,records=None,budget=1):
  body=self.event('assignment',records or [{'student_external_id':'TEST_01','school_external_id':'SCH_A','address':'  Synthetic incoming address, unchanged spelling  '}])
  body['producer']='hasara_adapter_provisional';body['geocoding_http_budget']=budget;return body
 def send(self,body):return self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=body)
 def result(self,ambiguous=False):return dict(latitude=6.9002,longitude=79.9002,formatted_address='Synthetic building address',provider='google',partial_match=ambiguous,ambiguous=ambiguous,candidate_count=2 if ambiguous else 1,location_confirmed=False)
 def test_success_duplicates_review_invalidation_and_snapshot(self):
  route=self.generate();body=self.body()
  with self.factory() as s:original=deepcopy(s.get(RouteVersion,route['route_id']).input_snapshot)
  with patch('registration_geocoding.geocode',return_value=self.result()) as lookup:
   response=self.send(body);self.assertEqual(response.status_code,200,response.text)
   self.assertEqual(response.json()['geocoding_counts']['attempted'],1);self.assertEqual(response.json()['geocoding_counts']['successful'],1)
   duplicate=self.send(body);self.assertTrue(duplicate.json()['duplicate']);self.assertEqual(duplicate.json()['geocoding_counts']['attempted'],0);self.assertEqual(lookup.call_count,1)
  with self.factory() as s:
   p=s.get(Student,PREFIX+'TEST_01');self.assertEqual(p.home_address,body['records'][0]['address']);self.assertFalse(p.location_confirmed);self.assertEqual(p.location_method,'google')
   self.assertEqual(s.get(RouteVersion,route['route_id']).input_snapshot,original)
   event=s.get(LandmarkInputEvent,body['event_id']);self.assertEqual(event.payload['records'],body['records']);self.assertFalse(event.payload['geocoding_results'][0]['provider_result']['location_confirmed'])
  self.assertTrue(self.day()['plans']['morning']['publication_blockers'])
  self.assertFalse(self.day()['location_imports'][0]['current_location_confirmed'])
 def test_ambiguous_failure_zero_budget_and_supplied_stopping_pin(self):
  bodies=[self.body([{'student_external_id':'TEST_01','school_external_id':'SCH_A','address':'Synthetic ambiguous address'}]),self.body([{'student_external_id':'TEST_02','school_external_id':'SCH_A','address':'Synthetic failed address'}]),self.body([{'student_external_id':'TEST_03','school_external_id':'SCH_A','address':'Synthetic no-budget address'}],0)]
  with patch('registration_geocoding.geocode',return_value=self.result(True)):
   self.assertEqual(self.send(bodies[0]).json()['geocoding_counts']['ambiguous'],1)
  with patch('registration_geocoding.geocode',side_effect=HTTPException(404,'Synthetic no match')):
   self.assertEqual(self.send(bodies[1]).json()['geocoding_counts']['failed'],1)
  with patch('registration_geocoding.geocode',side_effect=AssertionError('No budget')) as lookup:
   self.assertEqual(self.send(bodies[2]).json()['geocoding_counts']['attempted'],0);lookup.assert_not_called()
  with self.factory() as s:
   for key in ('TEST_02','TEST_03'):
    p=s.get(Student,PREFIX+key);self.assertIsNone(p.home_latitude);self.assertIsNone(p.home_longitude);self.assertFalse(p.location_confirmed)
  pin=self.body([{'student_external_id':'TEST_04','school_external_id':'SCH_A','address':'Synthetic building and separate supplied stopping pin','latitude':6.91,'longitude':79.91}])
  with patch('registration_geocoding.geocode',return_value=self.result()):self.assertEqual(self.send(pin).status_code,200)
  with self.factory() as s:
   p=s.get(Student,PREFIX+'TEST_04');self.assertEqual(p.home_latitude,6.91);self.assertFalse(p.location_confirmed)
   self.assertEqual(s.get(LandmarkInputEvent,pin['event_id']).payload['geocoding_results'][0]['provider_result']['latitude'],6.9002)
 def test_auth_validation_budget_and_noop_prevent_requests(self):
  body=self.body()
  with patch('registration_geocoding.geocode',return_value=self.result()) as lookup:
   self.assertEqual(self.client.post('/daily-plan/import',json=body).status_code,401)
   for role in ('driver','parent'):self.assertEqual(self.client.post('/daily-plan/import',headers=self.headers[role],json=body).status_code,403)
   invalid=deepcopy(body);invalid['records'].append({'student_external_id':'UNKNOWN','school_external_id':'SCH_A','address':'Unknown fixture'})
   self.assertEqual(self.send(invalid).status_code,422);lookup.assert_not_called()
   invalid=deepcopy(body);invalid['records'][0]['address']='   ';self.assertEqual(self.send(invalid).status_code,422)
   records=[{'student_external_id':key,'school_external_id':'SCH_A','address':'Synthetic changed address '+key} for key in ('TEST_01','TEST_02')]
   response=self.send(self.body(records,budget=1)).json();self.assertEqual(response['geocoding_counts']['attempted'],1);self.assertEqual(response['geocoding_counts']['pending_budget'],1);self.assertEqual(lookup.call_count,1)
   # A distinct, explicitly budgeted event may resolve the second pending pin.
   self.assertEqual(self.send(self.body(records,budget=1)).json()['geocoding_counts']['attempted'],1);self.assertEqual(lookup.call_count,2)
   self.assertEqual(self.send(self.body(records,budget=1)).json()['geocoding_counts']['attempted'],0);self.assertEqual(lookup.call_count,2)
 def test_active_trip_coordinates_remain_fixed(self):
  route=self.generate('afternoon');self.assertEqual(self.publish(route,True).status_code,200)
  from trips import create_trip,CreateTrip,transition
  with self.factory() as s:
   trip=create_trip(CreateTrip(route_id=route['route_id']),s);transition(s,trip['trip_id'],'ACTIVE');snapshot=deepcopy(s.get(RouteVersion,route['route_id']).input_snapshot)
  with patch('registration_geocoding.geocode',return_value=self.result()):self.assertEqual(self.send(self.body()).status_code,200)
  with self.factory() as s:
   self.assertEqual(s.get(Trip,trip['trip_id']).route_id,route['route_id']);self.assertEqual(s.get(RouteVersion,route['route_id']).input_snapshot,snapshot)
 def test_initial_registration_address_with_missing_pin_triggers_lookup(self):
  with self.factory() as s:
   p=s.get(Student,PREFIX+'TEST_01');address=p.home_address;p.home_latitude=None;p.home_longitude=None;p.location_confirmed=False;s.commit()
  body=self.body([{'student_external_id':'TEST_01','school_external_id':'SCH_A','address':address}])
  with patch('registration_geocoding.geocode',return_value=self.result()) as lookup:
   response=self.send(body);self.assertEqual(response.status_code,200,response.text)
   self.assertEqual(response.json()['geocoding_counts']['successful'],1);self.assertEqual(lookup.call_count,1)
  with self.factory() as s:
   p=s.get(Student,PREFIX+'TEST_01');self.assertEqual(p.home_address,address);self.assertIsNotNone(p.home_latitude);self.assertFalse(p.location_confirmed)

if __name__=='__main__':unittest.main()
