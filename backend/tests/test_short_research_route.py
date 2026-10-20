"""Rollback-only synthetic short-route checks; no real route/capture is created."""
import os,unittest
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch
from sqlalchemy import select,func
import test_landmark_daily as fixtures
from models import (LoginSession,DriverVehicle,Trip,RouteVersion,RoutePlanState,RouteStop,PickupWindow,PickupOutcome,MissedPickupNotification,TripStopArrival)
from auth import token_hash
from research_routes import VEHICLE
from positions import PositionInput,store_position

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_SHORT_RESEARCH_TESTS')=='1','Opt in to rollback-only synthetic research tests.')
class ShortResearchTests(unittest.TestCase):
 def setUp(self):
  fixtures.LandmarkTests.setUp(self)
  # Freeze only research planning's clock; a +5-minute fixture otherwise crosses
  # midnight and fails the deliberately strict same-day authorization rule.
  self.research_now=datetime.now(ZoneInfo('Asia/Colombo')).replace(hour=12,minute=0,second=0,microsecond=0)
  frozen=self.research_now
  class PlanningClock(datetime):
   @classmethod
   def now(cls,tz=None):return frozen.astimezone(tz) if tz else frozen.replace(tzinfo=None)
  clock=patch('research_routes.datetime',PlanningClock);clock.start();self.addCleanup(clock.stop)
  day=patch('trips.today',return_value=frozen.date());day.start();self.addCleanup(day.stop)
 tearDown=fixtures.LandmarkTests.tearDown
 def actor(self,role):
  with self.factory() as s:return s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(self.headers[role]['Authorization'].split()[1]))).account_id
 def body(self):
  with self.factory() as s:
   if not s.get(DriverVehicle,(self.actor('driver'),VEHICLE)):s.add(DriverVehicle(account_id=self.actor('driver'),vehicle_id=VEHICLE));s.commit()
  stamp=self.research_now+timedelta(minutes=5)
  return dict(service_date=str(stamp.date()),departure_seconds=stamp.hour*3600+stamp.minute*60+stamp.second,
   travel_mode='driving',driver_id=self.actor('driver'),operator_id=self.actor('administrator'),
   separate_people_confirmed=True,adults_only_confirmed=True,reason='Synthetic rollback separate-adult research preparation',
   pins={k:dict(latitude=lat,longitude=lon,manually_confirmed=True,permitted_public_stop=True,stopping_note='Synthetic reviewed public stopping point, rollback only') for k,lat,lon in [('A',6.9,79.9),('B',6.91,79.91),('C',6.92,79.9)]})
 def prepare(self):
  body=self.body();r=self.client.post('/research-routes',headers=self.headers['administrator'],json=body)
  self.assertEqual(r.status_code,200,r.text);return r.json(),body
 def trip(self,route):
  r=self.client.post('/trips',headers=self.headers['driver'],json={'route_id':route['route_id']})
  self.assertEqual(r.status_code,200,r.text);return r.json()
 def approve(self,trip):
  r=self.client.post('/tracking/adult-field-test',headers=self.headers['administrator'],json=dict(trip_id=trip['trip_id'],reason='Synthetic rollback consenting adult approval only',adults_only_confirmed=True))
  self.assertEqual(r.status_code,200,r.text)
 def test_unused_research_replacement_preserves_review_and_requires_new_grant(self):
  route,body=self.prepare();old=self.trip(route);self.approve(old)
  cancelled=self.client.post('/trips/'+old['trip_id']+'/cancel',headers=self.headers['administrator'],json={'reason':'Superseded unused research departure; preparing a later reviewed version.'})
  self.assertEqual(cancelled.status_code,200,cancelled.text)
  self.assertEqual(cancelled.json()['state'],'CANCELLED')
  self.assertIsNone(cancelled.json()['started_at'])
  body['departure_seconds']+=60
  replacement=self.client.post('/research-routes',headers=self.headers['administrator'],json=body)
  self.assertEqual(replacement.status_code,200,replacement.text)
  new_route=replacement.json();self.assertNotEqual(new_route['route_id'],route['route_id'])
  for key in ('pins','driver_id','operator_id','travel_mode','reason','ordered_keys'):
   self.assertEqual(new_route['research_journey'][key],route['research_journey'][key])
  new=self.trip(new_route);self.assertEqual(new['state'],'PLANNED')
  self.assertNotEqual(new['trip_id'],old['trip_id']);self.assertFalse(new['adult_phone_field_test_authorized'])
  self.assertEqual(self.trip(new_route)['trip_id'],new['trip_id'])
  self.assertEqual(self.client.post('/trips/'+old['trip_id']+'/start',headers=self.headers['driver']).status_code,409)
  self.assertEqual(self.client.get('/trips/'+old['trip_id'],headers=self.headers['administrator']).json()['route_id'],route['route_id'])
 def test_validation_idempotence_and_school_isolation(self):
  body=self.body()
  for role in [None,'driver','parent']:
   r=self.client.post('/research-routes',headers=self.headers.get(role,{}) if role else {},json=body)
   self.assertIn(r.status_code,(401,403))
  for change in ['mode','pin','public','separation','people','past','range']:
   from copy import deepcopy
   b=deepcopy(body)
   if change=='mode':b.pop('travel_mode')
   elif change=='pin':b['pins']['A']['manually_confirmed']=False
   elif change=='public':b['pins']['B']['permitted_public_stop']=False
   elif change=='separation':b['pins']['B']=dict(b['pins']['A'])
   elif change=='people':b['operator_id']=b['driver_id']
   elif change=='past':b['service_date']='2020-01-01'
   else:b['pins']['A']['latitude']=100
   self.assertEqual(self.client.post('/research-routes',headers=self.headers['administrator'],json=b).status_code,422,change)
  with self.factory() as s:
   # Explicit school baseline in the isolated database, rather than relying on
   # a historical user's plan already being present.
   fixtures.generate_daily(fixtures.Generation(direction='afternoon'),s)
   state=s.get(RoutePlanState,(VEHICLE,'afternoon'));before={c.name:getattr(state,c.name) for c in state.__table__.columns}
  prepared=self.client.post('/research-routes',headers=self.headers['administrator'],json=body);self.assertEqual(prepared.status_code,200,prepared.text)
  route=prepared.json();self.assertEqual([s['occurrence'] for s in route['stops']],[1,2,3,4])
  self.assertEqual(route['stops'][0]['location_id'],route['stops'][3]['location_id']);self.assertNotEqual(route['stops'][0]['event_id'],route['stops'][3]['event_id'])
  again=self.client.post('/research-routes',headers=self.headers['administrator'],json=body).json();self.assertEqual(again['route_id'],route['route_id'])
  self.assertIsNone(route['total_duration_seconds']);self.assertEqual(route['student_count'],0)
  self.assertEqual(route['research_journey']['landmarks']['A']['stopping_address'],'25 Wewa Rd, Sri Jayawardenepura Kotte 10115')
  with self.factory() as s:
   state=s.get(RoutePlanState,(VEHICLE,'afternoon'));self.assertEqual(before,{c.name:getattr(state,c.name) for c in state.__table__.columns})
   from route_service import latest_route
   self.assertNotEqual(latest_route(s,VEHICLE,'afternoon')['route_id'],route['route_id'])
 def test_operator_binding_collection_no_windows_and_initial_final_arrival(self):
  route,_=self.prepare();trip=self.trip(route);tid=trip['trip_id'];self.assertEqual(self.trip(route)['trip_id'],tid);self.approve(trip)
  r=self.client.post('/research/collections',headers=self.headers['administrator'],json=dict(trip_id=tid,dataset='moving_adult_landmark',reason='Synthetic rollback collection prepared before capture',consent_confirmed=True));self.assertEqual(r.status_code,200,r.text)
  start=self.client.post('/trips/'+tid+'/start',headers=self.headers['driver']);self.assertEqual(start.status_code,200,start.text)
  self.assertEqual(start.json()['unfinished_action_count'],0)
  self.assertEqual(self.client.post('/tracking/enroll',headers=self.headers['administrator'],json=dict(vehicle_id=VEHICLE,trip_id=tid,kind='simulation',label='Must reject research replay')).status_code,422)
  self.assertEqual(self.client.get(f'/research-routes/current?vehicle_id={VEHICLE}&service_date={route["service_date"]}',headers=self.headers['parent']).status_code,403)
  self.assertEqual(self.client.post('/tracking/enroll',headers=self.headers['driver'],json=dict(vehicle_id=VEHICLE,trip_id=tid,kind='phone',label='Synthetic rollback')).status_code,403)
  grant=self.client.post('/tracking/enroll',headers=self.headers['administrator'],json=dict(vehicle_id=VEHICLE,trip_id=tid,kind='phone',label='Synthetic rollback operator, not physical evidence'))
  self.assertEqual(grant.status_code,201,grant.text)
  with self.factory() as s:
   t=s.get(Trip,tid);self.assertEqual(t.current_stop_sequence,1)
   for model in (PickupWindow,PickupOutcome,MissedPickupNotification):self.assertEqual(s.scalar(select(func.count()).select_from(model).where(model.trip_id==tid)),0)
   base=datetime.now(timezone.utc)+timedelta(seconds=1)
   for offset in [0,5,10,15]:
    recorded=base+timedelta(seconds=offset)
    with patch('positions.datetime') as clock:
     clock.now.return_value=recorded+timedelta(milliseconds=100)
     store_position(VEHICLE,PositionInput(sample_id='research-rollback-'+str(offset),trip_id=tid,source='simulation',latitude=6.9,longitude=79.9,accuracy_m=5,speed_mps=None,recorded_at=recorded),s)
   self.assertIsNotNone(s.get(TripStopArrival,(tid,1)).arrived_at)
   self.assertIsNone(s.get(TripStopArrival,(tid,4)))
  advance=self.client.post('/trips/'+tid+'/advance-stop?expected_stop_sequence=1',headers=self.headers['driver']);self.assertEqual(advance.status_code,200,advance.text);self.assertEqual(advance.json()['current_stop']['sequence'],2)
  # Visit B/C with fresh synthetic observations and explicitly select final A.
  for sequence,point,offset in [(2,(6.91,79.91),20),(3,(6.92,79.9),40)]:
   with self.factory() as s:
    for delta in [0,5,10,15]:
     recorded=base+timedelta(seconds=offset+delta)
     with patch('positions.datetime') as clock:
      clock.now.return_value=recorded+timedelta(milliseconds=100)
      store_position(VEHICLE,PositionInput(sample_id=f'research-rollback-{sequence}-{delta}',trip_id=tid,source='simulation',latitude=point[0],longitude=point[1],accuracy_m=5,speed_mps=None,recorded_at=recorded),s)
   with patch('trips.datetime',wraps=datetime) as clock:
    clock.now.return_value=base+timedelta(seconds=offset+16)
    response=self.client.post(f'/trips/{tid}/advance-stop?expected_stop_sequence={sequence}',headers=self.headers['driver'])
   self.assertEqual(response.status_code,200,response.text)
  with self.factory() as s:
   self.assertEqual(s.get(Trip,tid).current_stop_sequence,4)
   self.assertIsNone(s.get(TripStopArrival,(tid,4)),'Initial A must not satisfy return A when selected.')
   for delta in [0,5,10,15]:
    recorded=base+timedelta(seconds=60+delta)
    with patch('positions.datetime') as clock:
     clock.now.return_value=recorded+timedelta(milliseconds=100)
     store_position(VEHICLE,PositionInput(sample_id=f'research-rollback-return-{delta}',trip_id=tid,source='simulation',latitude=6.9,longitude=79.9,accuracy_m=5,speed_mps=None,recorded_at=recorded),s)
   self.assertIsNotNone(s.get(TripStopArrival,(tid,4)).arrived_at)
   self.assertNotEqual(s.get(TripStopArrival,(tid,1)).event_id,s.get(TripStopArrival,(tid,4)).event_id)
  complete=self.client.post('/trips/'+tid+'/complete',headers=self.headers['driver']);self.assertEqual(complete.status_code,200,complete.text)
  self.assertEqual(complete.json()['unfinished_action_count'],0)
  self.assertEqual(self.client.post('/trips/'+tid+'/start',headers=self.headers['driver']).status_code,409)
