"""Rollback-only scenario checks; all confirmed coordinates below are synthetic.
No workers, live geocoding, traffic calls or historical fixture edits persist.
"""
import os,secrets,unittest
from datetime import datetime,timedelta,timezone,date
from unittest.mock import patch
from uuid import uuid4
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from database import get_engine
from persistence import session_dependency
from main import app
from auth import token_hash,_attempts
from models import (Account,LoginSession,Vehicle,School,Student,RouteVersion,RouteStop,Trip,PickupWindow,PickupOutcome,TripStopArrival,VehiclePosition,MissedPickupNotification,LandmarkAttendance,LandmarkDailyPlan)
from landmark import (setup,SCENARIO,VEHICLE,PREFIX,DEFAULT_DATE,PARTICIPANTS,SCHOOLS,VERSION,Generation,generate_daily,read_daily)
from route_service import serialize_version
from route_schemas import GenerateRouteRequest
from routing_domain import GenerationSettings
from landmark_solver import solve_landmark

class OpenEndCostTests(unittest.TestCase):
 def test_nonzero_costs_do_not_charge_a_hidden_depot_return(self):
  from dataclasses import replace
  from test_dual_route_solver import fixture
  from travel_time import TravelCosts
  vehicle,people,schools=fixture();vehicle=replace(vehicle,capacity=20)
  class Matrix:
   calls=0
   def precompute(self,points,*args):
    self.calls+=1;n=len(points)
    durations=[[0 if i==j else 99999 if j==0 else 60 for j in range(n)] for i in range(n)]
    return TravelCosts(durations,[[0 if i==j else 100 for j in range(n)] for i in range(n)],{'provider':'synthetic_matrix_test','duration_source':'simulation','distance_source':'synthetic_test','distance_is_approximate':True})
  matrix=Matrix();r=solve_landmark(vehicle,people,schools,GenerationSettings('morning',21600),matrix)
  self.assertEqual(r['feasibility_status'],'feasible');self.assertEqual(matrix.calls,1)
  self.assertEqual(r['driving_seconds'],(len(r['stops'])-1)*60)
  self.assertEqual(r['distance_metres'],(len(r['stops'])-1)*100)
  self.assertEqual(r['stops'][-1]['action'],'delivery')

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_LANDMARK_TESTS')=='1','Opt in to rollback-only PostgreSQL landmark tests.')
class LandmarkTests(unittest.TestCase):
 def setUp(self):
  _attempts.clear();self.c=get_engine().connect();self.tx=self.c.begin()
  self.factory=lambda:Session(self.c,join_transaction_mode='create_savepoint')
  def db():
   with self.factory() as s:yield s
  app.dependency_overrides[session_dependency]=db;self.client=TestClient(app)
  self.headers={}
  with self.factory() as s:
   setup(s)
   for role in ['administrator','driver','parent']:
    uid='LANDMARK_TEST_'+uuid4().hex;token='sr_user_'+secrets.token_urlsafe(32)
    s.add(Account(id=uid,username=uid.lower(),role=role,password_hash='!',active=True,demo_only=False,failed_attempts=0));s.flush()
    s.add(LoginSession(id='LOGIN_'+uuid4().hex,account_id=uid,token_hash=token_hash(token),mode='real',created_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
    self.headers[role]={'Authorization':'Bearer '+token}
   v=s.get(Vehicle,VEHICLE)
   for position in ['start','end']:
    setattr(v,position+'_latitude',6.9);setattr(v,position+'_longitude',79.9);setattr(v,position+'_confirmed',True)
   for key in SCHOOLS:
    sc=s.get(School,PREFIX+key);sc.latitude=6.9;sc.longitude=79.9;sc.location_confirmed=True
   for key,_,_,pm in PARTICIPANTS:
    p=s.get(Student,PREFIX+key);p.home_latitude=6.9;p.home_longitude=79.9;p.location_confirmed=True
    a=s.get(LandmarkAttendance,(SCENARIO,DEFAULT_DATE,p.id));a.am='yes';a.pm='yes' if pm else 'no'
   s.commit()
 def tearDown(self):
  self.client.close();app.dependency_overrides.clear();self.tx.rollback();self.c.close()
 def generate(self,direction='morning',departure=None):
  with self.factory() as s:return generate_daily(Generation(direction=direction,departure_seconds=departure),s)
 def day(self,day=DEFAULT_DATE):
  with self.factory() as s:return read_daily(day,s)
 def event(self,kind,records,event_id=None):
  return {'schema_version':VERSION,'event_id':event_id or str(uuid4()),'occurred_at':datetime.now(timezone.utc).isoformat(),'producer':'manual_test','provenance':'landmark_test','kind':kind,'reason':'Explicit synthetic rollback test decision','records':records}
 def post_event(self,kind,records):
  r=self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=self.event(kind,records));self.assertEqual(r.status_code,200,r.text);return r.json()
 def publish(self,route,review=False):
  return self.client.post('/daily-plan/publish',headers=self.headers['administrator'],json={'service_date':str(DEFAULT_DATE),'direction':route['direction'],'route_id':route['route_id'],'review_unresolved_boarding':review,'reason':'Explicit review of synthetic test outcomes'})
 def test_initial_mapping_idempotence_and_isolation(self):
  d=self.day();self.assertEqual(d['counts'],{'morning':8,'afternoon':7})
  self.assertEqual([s['name'] for s in d['schools']],['Horizon College International',"Boys' Model College"])
  self.assertEqual(len(d['students']),8);self.assertTrue(all(p['id'].startswith(PREFIX) for p in d['students']))
  with self.factory() as s:
   before=s.scalar(select(func.count()).select_from(Student));self.assertFalse(setup(s)['created']);self.assertEqual(s.scalar(select(func.count()).select_from(Student)),before)
 def test_grouped_am_no_return_and_pm_independent_roster(self):
  am=self.generate();pm=self.generate('afternoon')
  self.assertEqual(am['feasibility_status'],'feasible');self.assertEqual(pm['feasibility_status'],'feasible')
  self.assertEqual(am['student_count'],8);self.assertEqual(pm['student_count'],7)
  self.assertEqual([s['action'] for s in am['stops']],['start']+['pickup']*8+['delivery']*2)
  self.assertTrue(am['stops'][-1]['grouped']);self.assertEqual(am['stops'][-1]['service_seconds'],600)
  self.assertEqual(len(am['stops']),11);self.assertEqual(am['end_policy'],'last_school_no_depot_return')
  self.assertEqual(am['total_duration_seconds'],8*120+2*600)  # colocated synthetic edges: absolutely no depot leg
  self.assertEqual([s['action'] for s in pm['stops']],['pickup']*2+['delivery']*7+['end'])
  self.assertEqual(pm['stops'][0]['school_id'],PREFIX+'SCH_B');self.assertEqual(pm['stops'][1]['school_id'],PREFIX+'SCH_A')
  self.assertEqual(pm['total_duration_seconds'],2*900+7*120)
  self.assertNotIn(PREFIX+'TEST_03',[sid for stop in pm['stops'] for sid in stop['student_ids']])
  self.assertEqual(pm['stops'][-1]['location_id'],VEHICLE+':end')
  self.assertEqual(sum(s['service_seconds'] for s in pm['stops'][:2]),1800)
 def test_hard_deadline_preferred_buffer_departure_and_capacity(self):
  soft=self.generate(departure=24000);self.assertEqual(soft['feasibility_status'],'feasible');self.assertFalse(soft['preferred_buffer_met']);self.assertTrue(soft['warnings'])
  impossible=self.generate(departure=25200);self.assertNotEqual(impossible['feasibility_status'],'feasible')
  self.assertEqual(self.generate(departure=21599)['feasibility_status'],'invalid_input')
  with self.factory() as s:s.get(Vehicle,VEHICLE).capacity=7;s.commit()
  self.assertEqual(self.generate()['feasibility_status'],'infeasible')
 def test_unknown_locations_attendance_and_date_immutability(self):
  original=self.generate();day2=date(2026,10,20)
  with self.factory() as s:
   old=s.get(RouteVersion,original['route_id']);snapshot=old.input_snapshot.copy()
   blocked=generate_daily(Generation(direction='morning',service_date=day2),s)
   self.assertEqual(blocked['feasibility_status'],'attendance_unresolved');self.assertEqual(s.get(RouteVersion,original['route_id']).input_snapshot,snapshot)
  self.post_event('attendance',[{'student_external_id':'TEST_03','service_date':str(DEFAULT_DATE),'am':'no','pm':'no'}])
  self.assertEqual(self.day()['counts']['morning'],7);self.assertEqual(self.day(day2)['counts']['morning'],0)
  with self.factory() as s:
   self.assertEqual(len(s.get(RouteVersion,original['route_id']).input_snapshot['students']),8)
   s.get(Student,PREFIX+'TEST_01').location_confirmed=False;s.commit()
  self.assertEqual(self.generate()['feasibility_status'],'invalid_input')
 def test_missing_boarding_vs_no_show_and_event_idempotence(self):
  before=self.generate('afternoon');self.assertEqual(len(before['daily']['attendance']['unresolved_boarding']),7)
  self.assertEqual(self.publish(before).status_code,409);self.assertEqual(self.publish(before,True).status_code,200)
  record={'student_external_id':'TEST_01','service_date':str(DEFAULT_DATE),'direction':'morning','outcome':'no_show'}
  envelope=self.event('boarding',[record]);r=self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=envelope);self.assertEqual(r.status_code,200)
  d=self.day();self.assertEqual(d['counts']['afternoon'],6);after=d['plans']['afternoon']['route']['route_id']
  duplicate=self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=envelope);self.assertTrue(duplicate.json()['duplicate']);self.assertEqual(self.day()['plans']['afternoon']['route']['route_id'],after)
  self.assertEqual(self.publish(before,True).status_code,409)
  self.assertEqual(self.day()['plans']['afternoon']['publication'],'draft')
  self.post_event('boarding',[{**record,'outcome':'unknown'}]);self.assertEqual(self.day()['counts']['afternoon'],7)
 def test_import_auth_unknown_external_and_policy(self):
  body=self.event('attendance',[{'student_external_id':'HISTORICAL_FIXTURE','service_date':str(DEFAULT_DATE),'am':'yes','pm':'yes'}])
  self.assertEqual(self.client.post('/daily-plan/import',json=body).status_code,401)
  for role in ['driver','parent']:self.assertEqual(self.client.get('/daily-plan',headers=self.headers[role]).status_code,403)
  self.assertEqual(self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=body).status_code,422)
  self.assertEqual(self.client.put('/routing/schools/'+PREFIX+'SCH_A/schedule',headers=self.headers['administrator'],json={'morning_deadline_seconds':28800,'afternoon_finish_seconds':48600}).status_code,422)
  self.post_event('attendance',[{'student_external_id':'TEST_01','service_date':str(DEFAULT_DATE),'am':'no','pm':'yes'}])
  self.assertTrue(self.day()['plans']['afternoon']['attendance']['unresolved_afternoon_only'])
 def test_existing_pin_review_orchestration_updates_dated_plans(self):
  am=self.generate();pm=self.generate('afternoon')
  response=self.client.put('/routing/schools/'+PREFIX+'SCH_A/location',headers=self.headers['administrator'],json={'address':'Synthetic rollback pin review only','latitude':6.9001,'longitude':79.9,'location_confirmed':True,'location_method':'manual'})
  self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['save_status'],'saved')
  d=self.day();self.assertNotEqual(d['plans']['morning']['route']['route_id'],am['route_id']);self.assertNotEqual(d['plans']['afternoon']['route']['route_id'],pm['route_id'])
 def test_trip_publication_active_manifest_windows_and_no_pm_alert_for_test03(self):
  pm=self.generate('afternoon');self.assertEqual(self.publish(pm,True).status_code,200)
  from trips import create_trip,CreateTrip,transition
  with self.factory() as s:
   trip=create_trip(CreateTrip(route_id=pm['route_id'],pickup_scope='per_school'),s)
   with patch('trips.today',return_value=DEFAULT_DATE):trip=transition(s,trip['trip_id'],'ACTIVE')
   trip_id=trip['trip_id'];manifest=s.get(RouteVersion,pm['route_id']).input_snapshot.copy()
   windows=s.scalars(select(PickupWindow).where(PickupWindow.trip_id==trip_id)).all();self.assertEqual(len(windows),2)
   outcomes=s.scalars(select(PickupOutcome).where(PickupOutcome.trip_id==trip_id)).all();self.assertEqual(len(outcomes),7);self.assertNotIn(PREFIX+'TEST_03',[o.student_id for o in outcomes])
   t=s.get(Trip,trip_id);stop=s.get(RouteStop,(pm['route_id'],1))
   early=datetime.fromisoformat('2026-10-19T13:20:00+05:30');release=early+timedelta(minutes=10)
   pos=VehiclePosition(id='POS_'+uuid4().hex,sample_id=str(uuid4()),vehicle_id=VEHICLE,trip_id=trip_id,source='simulation',latitude=6.9,longitude=79.9,speed_mps=None,recorded_at=early,received_at=early);s.add(pos);s.flush()
   arrival=TripStopArrival(trip_id=trip_id,stop_sequence=1,route_id=pm['route_id'],last_recorded_at=early,observation_count=3,distance_metres=0,source='simulation',event_id='ARRIVAL_'+uuid4().hex,arrived_at=early,confirming_position_id=pos.id);s.add(arrival);s.flush()
   from pickup_windows import start_from_arrival,expire_window,outcomes as rows
   start_from_arrival(s,t,stop,arrival,early);s.flush()
   w=s.scalar(select(PickupWindow).where(PickupWindow.trip_id==trip_id,PickupWindow.school_id==PREFIX+'SCH_B'))
   self.assertIsNone(w.started_at);self.assertIsNotNone(w.arrival_event_id)
   s.commit()
   from pickup_worker import expire_due
   with patch('pickup_worker.Session',side_effect=lambda *a,**kw:self.factory()),patch('pickup_worker.clock',return_value=release):
    expire_due(trip_id=trip_id);expire_due(trip_id=trip_id)  # Repeated worker processing, no browser or unrelated trips.
   s.expire_all();self.assertEqual(w.started_at,release);self.assertEqual(w.deadline_at,release+timedelta(seconds=900))
   start_from_arrival(s,t,stop,arrival,release+timedelta(seconds=30));self.assertEqual(w.deadline_at,release+timedelta(seconds=900))
   s.commit()
   self.post_event('attendance',[{'student_external_id':'TEST_05','service_date':str(DEFAULT_DATE),'am':'yes','pm':'no'}])
   expire_window(s,w,rows(s,w),release+timedelta(seconds=901),'test_expiry');s.commit()
   self.assertFalse(expire_window(s,w,rows(s,w),release+timedelta(seconds=1000),'repeated_test_expiry'))
   alerts=s.scalars(select(MissedPickupNotification).where(MissedPickupNotification.trip_id==trip_id)).all();self.assertEqual(len(alerts),3);self.assertNotIn(PREFIX+'TEST_03',[a.student_id for a in alerts]);self.assertNotIn(PREFIX+'TEST_05',[a.student_id for a in alerts])
  self.post_event('boarding',[{'student_external_id':'TEST_01','service_date':str(DEFAULT_DATE),'outcome':'no_show'}])
  with self.factory() as s:
   self.assertEqual(s.get(RouteVersion,pm['route_id']).input_snapshot,manifest)
   self.assertEqual(s.get(Trip,trip_id).route_id,pm['route_id'])
