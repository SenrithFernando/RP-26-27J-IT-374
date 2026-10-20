"""Rollback-only scenario checks; all confirmed coordinates below are synthetic.
No workers, live geocoding, traffic calls or historical fixture edits persist.
"""
import os,secrets,unittest
from datetime import datetime,timedelta,timezone,date
from unittest.mock import patch
from uuid import uuid4
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session
from database import get_engine,Base
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
  self.assertEqual(r['service_seconds'],len(people)*120+2*600)
  self.assertEqual(r['waiting_seconds'],0)
  self.assertEqual(r['total_duration_seconds'],r['driving_seconds']+r['service_seconds'])
  self.assertEqual(r['stops'][-1]['departure_seconds']-21600,r['total_duration_seconds'])
 def test_pm_return_and_single_group_boarding_service(self):
  from dataclasses import replace
  from test_dual_route_solver import fixture
  from travel_time import TravelCosts
  vehicle,people,schools=fixture();vehicle=replace(vehicle,capacity=20)
  class Matrix:
   def precompute(self,points,*args):
    n=len(points)
    return TravelCosts([[0 if i==j else 60 for j in range(n)] for i in range(n)],
      [[0 if i==j else 100 for j in range(n)] for i in range(n)],
      {'provider':'synthetic_matrix_test','duration_source':'simulation','distance_source':'synthetic_test','distance_is_approximate':True})
  r=solve_landmark(vehicle,people,schools,GenerationSettings('afternoon',48600,solver_time_limit_seconds=1),Matrix())
  self.assertEqual(r['feasibility_status'],'feasible')
  self.assertEqual(r['stops'][-1]['action'],'end')
  self.assertEqual(r['stops'][-1]['driving_seconds_from_previous'],60)
  self.assertEqual(r['stops'][-1]['service_seconds'],0)
  self.assertEqual(r['driving_seconds'],(len(r['stops'])-1)*60)
  self.assertEqual([s['service_seconds'] for s in r['stops'] if s['grouped']],[900,900])
  self.assertEqual(r['service_seconds'],len(people)*120+1800)
  self.assertEqual(r['waiting_seconds'],0)
  self.assertEqual(r['total_duration_seconds'],r['driving_seconds']+r['service_seconds'])

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_LANDMARK_TESTS')=='1','Opt in to rollback-only PostgreSQL landmark tests.')
class LandmarkTests(unittest.TestCase):
 def setUp(self):
  # The dated scenario is intentionally fixed; freeze only its local planning
  # date so publication checks stay deterministic after the real date advances.
  class PlanningDate(datetime):
   @classmethod
   def now(cls,tz=None):
    value=datetime.now(tz)
    return value.replace(year=DEFAULT_DATE.year,month=DEFAULT_DATE.month,day=DEFAULT_DATE.day) if getattr(tz,'key',None)=='Asia/Colombo' else value
  clock=patch('landmark.datetime',PlanningDate);clock.start();self.addCleanup(clock.stop)
  day=patch('trips.today',return_value=DEFAULT_DATE);day.start();self.addCleanup(day.stop)
  _attempts.clear();self.c=get_engine().connect();self.tx=self.c.begin()
  # Session-private temporary tables require no database CREATE privilege.
  # Rollback removes every scratch table/row; public historical data is untouched.
  self.c=self.c.execution_options(schema_translate_map={None:'pg_temp'})
  self.c.execute(text('SET LOCAL search_path TO pg_temp'))
  Base.metadata.create_all(self.c,checkfirst=False)
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
 def test_departure_recommendation_saved_recomputed_and_override_validated(self):
  with self.factory() as s:
   original=generate_daily(Generation(direction='morning',departure_mode='recommend'),s)
  self.assertEqual(original['departure_seconds'],23940)
  self.assertEqual(original['departure_recommendation']['status'],'preferred_feasible')
  self.assertEqual(original['request_settings']['departure_mode'],'recommend')
  original_snapshot=original['departure_recommendation']['input_fingerprint']
  self.post_event('attendance',[{'student_external_id':'TEST_01','service_date':str(DEFAULT_DATE),'am':'no','pm':'yes'}])
  current=self.day()['plans']['morning']['route']
  self.assertGreater(current['version'],original['version']);self.assertEqual(current['departure_seconds'],24060)
  self.assertNotEqual(current['departure_recommendation']['input_fingerprint'],original_snapshot)
  with self.factory() as s:
   saved=s.get(RouteVersion,original['route_id']);self.assertEqual(saved.result['departure_recommendation']['input_fingerprint'],original_snapshot)
   bad=generate_daily(Generation(direction='morning',departure_mode='override',departure_seconds=26000),s)
  self.assertNotEqual(bad['feasibility_status'],'feasible')
  self.assertFalse(bad['departure_recommendation']['hard_feasible'])
  self.assertIn('override',bad['departure_recommendation']['status'])
  with self.factory() as s:valid=generate_daily(Generation(direction='morning',departure_mode='recommend'),s)
  self.assertEqual(self.publish(valid).status_code,200)
  from trips import create_trip,CreateTrip,transition
  from fastapi import HTTPException
  with self.factory() as s:
   trip=create_trip(CreateTrip(route_id=valid['route_id']),s)
   with patch('trips.today',return_value=DEFAULT_DATE):transition(s,trip['trip_id'],'ACTIVE')
   with self.assertRaises(HTTPException) as blocked:generate_daily(Generation(direction='morning',departure_mode='recommend'),s)
   self.assertEqual(blocked.exception.status_code,409)
   self.assertEqual(s.get(Trip,trip['trip_id']).route_id,valid['route_id'])
 def test_driver_published_boundary_date_scope_grouping_and_active_pin(self):
  from models import DriverVehicle
  from trips import create_trip,CreateTrip,transition
  with self.factory() as s:
   token=self.headers['driver']['Authorization'].split()[1]
   login=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(token)))
   s.add(DriverVehicle(account_id=login.account_id,vehicle_id=VEHICLE))
   other='OTHER_DRIVER_'+uuid4().hex;secret='sr_user_'+secrets.token_urlsafe(32)
   s.add(Account(id=other,username=other.lower(),role='driver',password_hash='!',active=True,demo_only=False,failed_attempts=0));s.flush()
   s.add(LoginSession(id='LOGIN_'+uuid4().hex,account_id=other,token_hash=token_hash(secret),mode='real',created_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1)));s.commit()
  url=f'/routes/published?vehicle_id={VEHICLE}&service_date={DEFAULT_DATE}&direction='
  self.assertEqual(self.client.get(url+'morning').status_code,401)
  self.assertEqual(self.client.get(url+'morning',headers={'Authorization':'Bearer '+secret}).status_code,403)
  self.assertEqual(self.client.get(url+'morning',headers=self.headers['parent']).status_code,403)
  with self.factory() as s:am=generate_daily(Generation(direction='morning',departure_mode='recommend'),s)
  pm=self.generate('afternoon')
  draft=self.client.get(url+'morning',headers=self.headers['driver']).json()
  self.assertIsNone(draft['published_route']);self.assertEqual(draft['publication_status'],'draft')
  self.assertEqual(self.publish(am).status_code,200);self.assertEqual(self.publish(pm,True).status_code,200)
  before=self.day()
  with patch('route_service.generate_and_store',side_effect=AssertionError('GET must never optimize')), patch('traffic_google.urlopen',side_effect=AssertionError('GET must never call Google')):
   for direction,expected in [('morning',am),('afternoon',pm)]:
    response=self.client.get(url+direction,headers=self.headers['driver']);self.assertEqual(response.status_code,200,response.text)
    route=response.json()['published_route'];admin=before['plans'][direction]['route']
    self.assertEqual(route['route_id'],admin['route_id']);self.assertEqual(route['version'],admin['version'])
    self.assertEqual(route['stops'],admin['stops']);self.assertEqual(route['departure'],admin['departure'])
    self.assertEqual(route['provider_source'],admin['provider_source'])
    for field in ['driving_seconds','service_seconds','waiting_seconds','total_duration_seconds']:
     self.assertEqual(route[field],admin[field])
    self.assertEqual(len([x for x in route['stops'] if x.get('grouped')]),2)
    self.assertEqual(route['total_duration_seconds'],sum(route[k] for k in ['driving_seconds','service_seconds','waiting_seconds']))
  # A closed research journey is not a school trip, even on the same date/direction.
  with self.factory() as s:
   research=RouteVersion(id='ISOLATED_RESEARCH_ROUTE',vehicle_id=VEHICLE,direction='afternoon',version=999,
    roster_version=0,service_date=DEFAULT_DATE,departure_seconds=64800,feasibility_status='feasible',
    execution_status='cancelled',request_settings={},input_snapshot={'research_journey':{'schema':'adult-ordered-route/v1'}},result={})
   s.add(research);s.flush()
   s.add(Trip(id='ISOLATED_CANCELLED_RESEARCH',vehicle_id=VEHICLE,route_id=research.id,direction='afternoon',
    state='CANCELLED',created_at=datetime.now(timezone.utc),cancelled_at=datetime.now(timezone.utc),
    cancellation_reason='Synthetic isolated fixture only',unfinished_actions=[],pickup_settings={}))
   s.commit()
  school=self.client.get(url+'afternoon',headers=self.headers['driver'])
  self.assertEqual(school.status_code,200,school.text)
  self.assertIsNone(school.json()['trip'])
  other_date=self.client.get(url.replace(str(DEFAULT_DATE),'2026-10-20')+'morning',headers=self.headers['driver']).json()
  self.assertIsNone(other_date['published_route']);self.assertEqual(other_date['publication_status'],'not_published')
  with self.factory() as s:
   a=s.get(LandmarkAttendance,(SCENARIO,DEFAULT_DATE,PREFIX+'TEST_01'));a.am='no';s.commit()
  stale=self.client.get(url+'morning',headers=self.headers['driver']).json()
  self.assertEqual(stale['publication_status'],'stale');self.assertIsNone(stale['published_route'])
  with self.factory() as s:
   a=s.get(LandmarkAttendance,(SCENARIO,DEFAULT_DATE,PREFIX+'TEST_01'));a.am='yes';s.commit()
   trip=create_trip(CreateTrip(route_id=am['route_id']),s)
   with patch('trips.today',return_value=DEFAULT_DATE):transition(s,trip['trip_id'],'ACTIVE')
  changed_pm=self.generate('afternoon');self.assertEqual(self.publish(changed_pm,True).status_code,200)
  selected=self.client.get(url+'afternoon',headers=self.headers['driver']).json()
  self.assertEqual(selected['published_route']['route_id'],changed_pm['route_id'])
  self.assertEqual(selected['trip']['state'],'ACTIVE');self.assertEqual(selected['trip']['route_id'],am['route_id'])
  self.assertEqual(selected['trip']['route']['stops'],am['stops'])
 def test_explicit_adult_phone_test_audit_binding_and_measured_export_exclusion(self):
  from models import DriverVehicle,LandmarkInputEvent
  from trips import create_trip,CreateTrip,transition
  from data_provenance import position_exclusion_reason
  am=self.generate();self.assertEqual(self.publish(am).status_code,200)
  with self.factory() as s:
   token=self.headers['driver']['Authorization'].split()[1]
   login=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(token)))
   s.add(DriverVehicle(account_id=login.account_id,vehicle_id=VEHICLE));s.commit()
   trip=create_trip(CreateTrip(route_id=am['route_id']),s)
   with patch('trips.today',return_value=DEFAULT_DATE):transition(s,trip['trip_id'],'ACTIVE')
  payload={'vehicle_id':VEHICLE,'trip_id':trip['trip_id'],'kind':'phone','label':'Synthetic rollback test only; NOT physical-phone evidence'}
  self.assertEqual(self.client.post('/tracking/enroll',headers=self.headers['driver'],json=payload).status_code,409)
  approval={'trip_id':trip['trip_id'],'reason':'Consenting adult landmark test synthetic rollback validation only','adults_only_confirmed':True}
  self.assertEqual(self.client.post('/tracking/adult-field-test',headers=self.headers['driver'],json=approval).status_code,403)
  with patch('trips.today',return_value=DEFAULT_DATE):
   response=self.client.post('/tracking/adult-field-test',headers=self.headers['administrator'],json=approval)
   self.assertEqual(response.status_code,200,response.text)
   duplicate=self.client.post('/tracking/adult-field-test',headers=self.headers['administrator'],json=approval)
   self.assertEqual(response.json()['authorization']['event_id'],duplicate.json()['authorization']['event_id'])
  grant=self.client.post('/tracking/enroll',headers=self.headers['driver'],json=payload)
  self.assertEqual(grant.status_code,201,grant.text);grant=grant.json()
  headers={'Authorization':'Bearer '+grant['credential']}
  stamp=datetime.now(timezone.utc)+timedelta(seconds=4)
  sample={'sample_id':str(uuid4()),'recorded_at':stamp.isoformat(),'latitude':6.9,'longitude':79.9,'accuracy_m':8,'speed_mps':None}
  accepted=self.client.post('/tracking/positions',headers=headers,json=sample)
  self.assertEqual(accepted.status_code,200,accepted.text)
  self.assertEqual(accepted.json()['sample']['source'],'actual_device');self.assertIsNone(accepted.json()['sample']['speed_mps'])
  self.assertEqual(accepted.json()['observation_context'],'adult_landmark_field_test')
  self.assertTrue(self.client.post('/tracking/positions',headers=headers,json=sample).json()['duplicate'])
  old={**sample,'sample_id':str(uuid4()),'recorded_at':(stamp-timedelta(seconds=1)).isoformat()}
  self.assertFalse(self.client.post('/tracking/positions',headers=headers,json=old).json()['advances_latest'])
  forged={**sample,'vehicle_id':'OTHER_VEHICLE'}
  self.assertEqual(self.client.post('/tracking/positions',headers=headers,json=forged).status_code,422)
  with self.factory() as s:
   row=s.get(VehiclePosition,accepted.json()['sample']['id'])
   self.assertEqual(row.tracking_session_id,grant['tracking_id'])
   self.assertEqual(position_exclusion_reason(s,row),'adult_landmark_field_test_not_measured_student_trip')
   self.assertEqual(s.get(Vehicle,VEHICLE).input_source,'simulated')
   self.assertIsNotNone(s.get(LandmarkInputEvent,response.json()['authorization']['event_id']))
  self.assertEqual(self.client.post('/tracking/'+grant['tracking_id']+'/revoke',headers=self.headers['driver']).status_code,200)
  self.assertEqual(self.client.post('/tracking/positions',headers=headers,json=sample).status_code,401)
 def test_start_button_empty_json_body_not_reported_as_database_outage(self):
  from models import DriverVehicle
  from trips import create_trip,CreateTrip
  am=self.generate();self.assertEqual(self.publish(am).status_code,200)
  with self.factory() as s:
   token=self.headers['driver']['Authorization'].split()[1]
   login=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(token)))
   s.add(DriverVehicle(account_id=login.account_id,vehicle_id=VEHICLE));s.commit()
   trip=create_trip(CreateTrip(route_id=am['route_id']),s)
  url='/trips/'+trip['trip_id']+'/start'
  headers={**self.headers['driver'],'Content-Type':'application/json'}
  bad=self.client.post(url,headers=headers,content='not-json-private-sentinel')
  self.assertEqual(bad.status_code,422);self.assertNotIn('private-sentinel',bad.text)
  self.assertEqual(self.client.post(url,headers={'Content-Type':'application/json'}).status_code,401)
  with patch('trips.today',return_value=DEFAULT_DATE):
   response=self.client.post(url,headers=headers) # Exactly the frontend's bodyless request.
  self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['state'],'ACTIVE')
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
