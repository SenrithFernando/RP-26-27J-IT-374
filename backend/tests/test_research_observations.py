"""Synthetic rollback-only phone-source fixtures; NOT physical-phone evidence."""
import os
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.testclient import TestClient
from database import get_engine
from models import (School,Vehicle,Student,Trip,Account,LoginSession,TrackingSession,VehiclePosition,
    ResearchCollection,TravelObservation,SegmentEstimate)
from route_service import generate_and_store
from route_schemas import GenerateRouteRequest
from trips import create_trip,CreateTrip,transition
from research_observations import Prepare,Candidate,Review,prepare_collection,extract,save_observation
from data_provenance import validate_measured_observations

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_RESEARCH_TESTS')=='1','Opt in to synthetic rollback research tests.')
class ResearchObservationTests(unittest.TestCase):
 def setUp(self):
  self.c=get_engine().connect();self.tx=self.c.begin();self.s=Session(self.c,join_transaction_mode='create_savepoint')
  self.addCleanup(self.c.close);self.addCleanup(self.tx.rollback);self.addCleanup(self.s.close)
  self.key='RESEARCH_TEST_'+uuid4().hex[:8];k=self.key;self.base=datetime.now(timezone.utc)-timedelta(minutes=10)
  s=self.s
  s.add(School(id=k+'S',name='Rollback school',input_source='simulated',address='Synthetic',latitude=6.9,longitude=79.9,location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=48600))
  s.add(Vehicle(id=k+'V',capacity=1,input_source='simulated',start_address='Synthetic',end_address='Synthetic',start_latitude=6.9,start_longitude=79.9,end_latitude=6.9,end_longitude=79.9,start_confirmed=True,end_confirmed=True));s.flush()
  s.add(Student(id=k+'P',name='Rollback adult landmark identity',home_id=k+'H',school_id=k+'S',vehicle_id=k+'V',input_source='simulated',home_address='Synthetic',home_latitude=6.94,home_longitude=79.94,location_confirmed=True,active=True));s.commit()
  route=generate_and_store(s,GenerateRouteRequest(vehicle_id=k+'V',direction='morning',departure_seconds=21600,include_geometry=False,solver_time_limit_seconds=1))
  planned=create_trip(CreateTrip(route_id=route['route_id']),s);transition(s,planned['trip_id'],'ACTIVE');self.trip=s.get(Trip,planned['trip_id'])
  self.trip.started_at=self.base-timedelta(seconds=30);self.trip.state='COMPLETED';self.trip.completed_at=self.base+timedelta(seconds=100)
  self.trip.pickup_settings={**self.trip.pickup_settings,'adult_phone_field_test':{'event_id':'ROLLBACK_TEST_ONLY'}}
  uid=k+'ADMIN';s.add(Account(id=uid,username=uid.lower(),password_hash='!',role='administrator',active=True,demo_only=False,failed_attempts=0));s.flush();self.actor=uid
  login=k+'LOGIN';s.add(LoginSession(id=login,account_id=uid,token_hash=k+'HASH',mode='real',created_at=self.base-timedelta(hours=1),expires_at=self.base+timedelta(hours=1)));s.flush()
  self.grant=k+'DEVICE';s.add(TrackingSession(id=self.grant,vehicle_id=self.trip.vehicle_id,trip_id=self.trip.id,login_session_id=login,
   token_hash=k+'DEVICE_HASH',kind='phone',label='Synthetic rollback-only phone-source test',created_at=self.base-timedelta(minutes=1),expires_at=self.base+timedelta(hours=1)));s.flush()
  s.add(ResearchCollection(trip_id=self.trip.id,dataset='moving_adult_landmark',protocol={'synthetic_rollback_test':True},actor_id=uid,created_at=self.base-timedelta(minutes=1)))
  for t in range(0,82,2):
   if t==0:lat=lon=0
   elif t<60:lat=lon=.001+(t-2)*(.039/58)
   else:lat=lon=.04
   s.add(VehiclePosition(id=k+'POS'+str(t),sample_id=k+'sample'+str(t),vehicle_id=self.trip.vehicle_id,trip_id=self.trip.id,
    source='actual_device',tracking_session_id=self.grant,latitude=6.9+lat,longitude=79.9+lon,accuracy_m=5,speed_mps=None,
    recorded_at=self.base+timedelta(seconds=t),received_at=self.base+timedelta(seconds=t,milliseconds=100)))
  s.commit()
  self.body=Candidate(trip_id=self.trip.id,origin_sequence=1,destination_sequence=2,departure_position_id=k+'POS2',arrival_position_id=k+'POS60',dwell_reviewed=True,reason='Synthetic rollback boundary review; not actual phone evidence')
 def test_supported_boundaries_features_and_separate_predictions(self):
  r=extract(self.s,self.body);self.assertEqual(r['flags'],[]);self.assertEqual(r['elapsed_duration_s'],58)
  self.assertEqual(r['duration_s'],58);self.assertEqual(r['known_service_s'],0);self.assertEqual(r['known_dwell_s'],0)
  self.assertEqual(r['prediction_time_features']['weather_flag'],-1);self.assertEqual(r['prediction_time_features']['weather_missing'],1)
  self.assertEqual(r['departure_boundary_uncertainty_s'],2)
  old=save_observation(self.s,self.body,self.actor);self.s.commit()
  accepted=save_observation(self.s,Review(**{**self.body.model_dump(),'status':'accepted','reason':'Explicit synthetic rollback acceptance review'}),self.actor,old);self.s.commit()
  self.assertEqual(old.status,'pending');self.assertEqual(accepted.revision,2);self.assertEqual(accepted.previous_id,old.id)
  estimate=self.s.get(SegmentEstimate,accepted.id)
  self.assertEqual(estimate.snapshot['kind'],'saved_planned_leg_estimate_not_measurement')
  self.assertNotEqual(estimate.snapshot['duration_s'],accepted.analysis['duration_s'])
  with self.assertRaises(ValueError):validate_measured_observations(self.s,[{**r,'data_source':'measured'}])
 def test_arbitrary_pairs_missing_boundaries_and_unknown_dwell(self):
  self.assertIn('departure_exit_not_established',extract(self.s,self.body.model_copy(update={'departure_position_id':self.key+'POS20'}))['flags'])
  self.assertIn('arrival_entry_dwell_not_established',extract(self.s,self.body.model_copy(update={'arrival_position_id':self.key+'POS70'}))['flags'])
  self.assertIn('missing_boundary',extract(self.s,self.body.model_copy(update={'arrival_position_id':None}))['flags'])
  self.assertIn('dwell_not_reviewed',extract(self.s,self.body.model_copy(update={'dwell_reviewed':False}))['flags'])
  with self.assertRaises(HTTPException):save_observation(self.s,Review(**{**self.body.model_dump(),'departure_position_id':None,'status':'accepted'}),self.actor)
 def test_gap_poor_unknown_accuracy_and_untrusted_binding(self):
  p=self.s.get(VehiclePosition,self.key+'POS20');p.recorded_at+=timedelta(seconds=1) # receipt ordering is not a travel boundary
  self.s.delete(self.s.get(VehiclePosition,self.key+'POS22'))
  for t in range(24,40,2):self.s.delete(self.s.get(VehiclePosition,self.key+'POS'+str(t)))
  self.s.get(VehiclePosition,self.key+'POS42').accuracy_m=10000
  self.s.get(VehiclePosition,self.key+'POS44').accuracy_m=None
  self.s.get(VehiclePosition,self.key+'POS46').tracking_session_id=None;self.s.flush()
  flags=extract(self.s,self.body)['flags']
  for f in ('long_gps_gap','poor_accuracy','unknown_accuracy','untrusted_device_binding'):self.assertIn(f,flags)
 def test_dwell_intervals_and_interruptions_not_planned_service(self):
  interval={'start':self.base+timedelta(seconds=20),'end':self.base+timedelta(seconds=24),'kind':'service','reason':'Observed manual test service'}
  body=Candidate(**{**self.body.model_dump(),'intervals':[interval]})
  r=extract(self.s,body);self.assertEqual(r['known_service_s'],4);self.assertEqual(r['duration_s'],54)
  overlapping=Candidate(**{**self.body.model_dump(),'intervals':[interval,interval]})
  self.assertIn('invalid_or_overlapping_dwell_intervals',extract(self.s,overlapping)['flags'])
  interrupt=Candidate(**{**self.body.model_dump(),'intervals':[{**interval,'kind':'interruption'}]})
  self.assertIn('declared_interruption',extract(self.s,interrupt)['flags'])
 def test_stationary_synthetic_datasets_and_no_reclassification(self):
  collection=self.s.get(ResearchCollection,self.trip.id)
  for dataset in ('stationary_adult_phone','synthetic'):
   collection.dataset=dataset;self.s.flush()
   self.assertIn('not_moving_measured_dataset',extract(self.s,self.body)['flags'])
  # No protocol can be registered retrospectively to turn a completed capture into moving research.
  self.s.delete(collection);self.s.flush()
  with self.assertRaises(HTTPException) as error:
   prepare_collection(self.s,Prepare(trip_id=self.trip.id,dataset='moving_adult_landmark',consent_confirmed=True,reason='Synthetic rollback retrospective protocol attempt'),self.actor)
  self.assertEqual(error.exception.status_code,409)
 def test_preparation_authorization_idempotence_and_fixture_exclusion(self):
  old=self.s.get(ResearchCollection,self.trip.id);self.s.delete(old);self.trip.state='PLANNED'
  self.trip.started_at=None;self.trip.completed_at=None;self.s.flush()
  body=Prepare(trip_id=self.trip.id,dataset='moving_adult_landmark',consent_confirmed=True,reason='Explicit synthetic rollback consent and collection protocol')
  with patch('tracking.adult_field_test_allowed',return_value=False):
   with self.assertRaises(HTTPException):prepare_collection(self.s,body,self.actor)
  with patch('tracking.adult_field_test_allowed',return_value=True):
   first=prepare_collection(self.s,body,self.actor);second=prepare_collection(self.s,body,self.actor)
   self.assertEqual(first.trip_id,second.trip_id)
   with self.assertRaises(HTTPException):prepare_collection(self.s,body.model_copy(update={'dataset':'stationary_adult_phone'}),self.actor)
  self.trip.state='COMPLETED';self.trip.started_at=self.base-timedelta(seconds=30);self.trip.completed_at=self.base+timedelta(seconds=100);self.s.flush()
  from data_provenance import register_synthetic_trip
  register_synthetic_trip(self.s,self.trip.id,'test_research_observations.py','Rollback-only synthetic fixture')
  self.assertIn('registered_synthetic_trip',extract(self.s,self.body)['flags'])
 def test_rejected_then_corrected_revision_keeps_raw_evidence(self):
  pending=save_observation(self.s,self.body.model_copy(update={'arrival_position_id':None}),self.actor)
  rejected=save_observation(self.s,Review(**{**pending.raw,'status':'rejected','reason':'Missing boundary; retain this rejected synthetic audit revision'}),self.actor,pending)
  accepted=save_observation(self.s,Review(**{**self.body.model_dump(),'status':'accepted','reason':'Corrected boundary from unchanged rollback raw GPS evidence'}),self.actor,rejected)
  self.assertEqual((pending.status,rejected.status,accepted.status),('pending','rejected','accepted'))
  self.assertIsNone(pending.raw['arrival_position_id']);self.assertEqual(accepted.revision,3)
  with self.assertRaises(HTTPException):save_observation(self.s,Review(**{**self.body.model_dump(),'status':'accepted'}),self.actor,rejected)
 def test_http_authorization_and_export_revalidation(self):
  import secrets
  from main import app
  from persistence import session_dependency
  from auth import token_hash
  token='sr_user_'+secrets.token_urlsafe(32)
  login=self.s.get(LoginSession,self.key+'LOGIN');login.token_hash=token_hash(token);self.s.commit()
  def db():yield self.s
  app.dependency_overrides[session_dependency]=db
  try:
   client=TestClient(app);self.addCleanup(client.close)
   headers={'Authorization':'Bearer '+token}
   self.assertEqual(client.get('/research/evaluation').status_code,401)
   evidence=client.get(f'/research/evidence?trip_id={self.trip.id}&origin_sequence=1&destination_sequence=2&limit=10',headers=headers)
   self.assertEqual(evidence.status_code,200,evidence.text)
   self.assertEqual(len(evidence.json()['positions']),10);self.assertIsNotNone(evidence.json()['next_before'])
   self.assertNotIn('latitude',evidence.json()['positions'][0]);self.assertIsNone(evidence.json()['positions'][0]['speed_mps'])
   created=client.post('/research/observations',headers=headers,json=self.body.model_dump(mode='json'))
   self.assertEqual(created.status_code,200,created.text);oid=created.json()['id']
   accepted=client.post('/research/observations/'+oid+'/review',headers=headers,json={**self.body.model_dump(mode='json'),'status':'accepted'})
   self.assertEqual(accepted.status_code,200,accepted.text)
   url=f'/research/export?trip_id={self.trip.id}&dataset=moving_adult_landmark'
   exported=client.get(url,headers=headers)
   self.assertEqual(exported.status_code,200,exported.text);self.assertEqual(len(exported.json()['measured_outcomes']),1)
   self.assertEqual(len(exported.json()['provider_estimates']),1)
   self.assertEqual(client.get('/research/evaluation?trip_id='+self.trip.id,headers=headers).json()['accepted'],1)
   self.s.get(VehiclePosition,self.key+'POS20').source='simulation';self.s.commit()
   self.assertEqual(client.get(url,headers=headers).status_code,409)
   self.s.get(Account,self.actor).role='driver';self.s.commit()
   self.assertEqual(client.get('/research/evaluation',headers=headers).status_code,403)
   self.assertEqual(client.get(url,headers=headers).status_code,403)
   self.s.get(Account,self.actor).role='parent';self.s.commit()
   self.assertEqual(client.get(url,headers=headers).status_code,403)
  finally:app.dependency_overrides.pop(session_dependency,None)
