"""Session-private rollback fixtures; no paid providers or operational records."""
import os,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from sqlalchemy import select,func
import test_landmark_daily as fixtures
from models import Vehicle,Student,RouteVersion,LandmarkAttendance,Trip
from landmark import DEFAULT_DATE,PREFIX,VEHICLE,SCENARIO,Generation,generate_daily,regenerate,scenario
from persistence import transfer_student,StudentTransfer,create_student,StudentWrite,remove_student
from route_service import latest_route,serialize_version

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_PRETRIP_TESTS')=='1','Opt in to temporary-table pre-trip tests.')
class PretripCheckpoint(fixtures.LandmarkTests):
 # Reuse helpers without rerunning the inherited suite in this module.
 def setUp(self):
  super().setUp()
  class PlanningClock(datetime):
   @classmethod
   def now(cls,tz=None):
    now=datetime.now(tz)
    return now.replace(year=DEFAULT_DATE.year,month=DEFAULT_DATE.month,day=DEFAULT_DATE.day) if getattr(tz,'key',None)=='Asia/Colombo' else now
  clock=patch('landmark.datetime',PlanningClock);clock.start();self.addCleanup(clock.stop)
  day=patch('trips.today',return_value=DEFAULT_DATE);day.start();self.addCleanup(day.stop)
  # A test fails rather than issuing any external Google request.
  network=patch('traffic_google.GoogleRoutesAdapter.matrix',side_effect=AssertionError('No paid calls in fixture'))
  network.start();self.addCleanup(network.stop)

 def roster(self,route,action):return {sid for stop in route['stops'] if stop['action']==action for sid in stop.get('student_ids',[stop.get('student_id')]) if sid}

 def test_checkpoint_dated_independence_duplicate_and_draft(self):
  from datetime import timedelta
  with self.factory() as s:am=generate_daily(Generation(direction='morning',departure_mode='recommend'),s)
  pm=self.generate('afternoon');self.assertEqual(self.publish(am).status_code,200);self.assertEqual(self.publish(pm,True).status_code,200)
  day2=DEFAULT_DATE+timedelta(days=2)
  with self.factory() as s:
   for p in s.scalars(select(Student).where(Student.vehicle_id==VEHICLE)):
    s.add(LandmarkAttendance(scenario_id=SCENARIO,service_date=day2,student_id=p.id,am='yes',pm='no',occurred_at=datetime.now(timezone.utc),event_id='isolated-day-two'))
   s.commit();other=generate_daily(Generation(direction='morning',service_date=day2),s)
  body=self.event('attendance',[{'student_external_id':'TEST_03','service_date':str(DEFAULT_DATE),'am':'no','pm':'no'}])
  response=self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=body)
  self.assertEqual(response.status_code,200,response.text)
  d=self.day();new=d['plans']['morning']['route']
  self.assertNotEqual(new['route_id'],am['route_id']);self.assertTrue(new['is_current'])
  self.assertNotEqual(new['departure_recommendation']['input_fingerprint'],am['departure_recommendation']['input_fingerprint'])
  self.assertEqual(new['student_count'],7);self.assertNotIn(PREFIX+'TEST_03',self.roster(new,'pickup'))
  self.assertEqual(d['plans']['afternoon']['route']['route_id'],pm['route_id'])
  self.assertEqual(d['plans']['morning']['publication'],'draft')
  self.assertEqual(self.day(day2)['plans']['morning']['route']['route_id'],other['route_id'])
  with self.factory() as s:
   self.assertFalse(serialize_version(s,s.get(RouteVersion,am['route_id']))['is_current'])
   count=s.scalar(select(func.count()).select_from(RouteVersion))
  duplicate=self.client.post('/daily-plan/import',headers=self.headers['administrator'],json=body)
  self.assertTrue(duplicate.json()['duplicate'])
  with self.factory() as s:self.assertEqual(s.scalar(select(func.count()).select_from(RouteVersion)),count)
  self.post_event('attendance',[{'student_external_id':'TEST_01','service_date':str(DEFAULT_DATE),'am':'yes','pm':'no'}])
  self.assertEqual(self.day()['plans']['morning']['route']['route_id'],new['route_id'])
  self.assertEqual(self.day()['plans']['afternoon']['route']['student_count'],6)

 def test_checkpoint_assignment_reactivation_and_failed_plan_keeps_inputs(self):
  am=self.generate();pm=self.generate('afternoon')
  self.post_event('assignment',[{'student_external_id':'TEST_01','school_external_id':'SCH_A','active':False}])
  d=self.day();self.assertEqual(d['plans']['morning']['route']['student_count'],7);self.assertEqual(d['plans']['afternoon']['route']['student_count'],6)
  self.post_event('assignment',[{'student_external_id':'TEST_01','school_external_id':'SCH_A','active':True}])
  self.assertEqual(self.day()['plans']['morning']['route']['student_count'],8)
  response=self.post_event('vehicle',[{'vehicle_external_id':'VAN_01','capacity':7}])
  self.assertEqual(response['routing']['outcome'],'failed')
  with self.factory() as s:self.assertEqual(s.get(Vehicle,VEHICLE).capacity,7)
  failed=self.day()['plans']['morning'];self.assertEqual(failed['route']['feasibility_status'],'infeasible');self.assertFalse(failed['route']['is_current'])
  self.assertEqual(len(failed['route']['daily']['attendance']['rows']),8)
  self.assertTrue(failed['publication_blockers'])

 def test_checkpoint_transfer_updates_both_vehicles_and_rejects_hidden_addition(self):
  from fastapi import HTTPException
  self.generate();self.generate('afternoon')
  with self.factory() as s:
   v=Vehicle(id='ISOLATED_OTHER_VEHICLE',capacity=20,input_source='simulated',start_address='Synthetic depot',end_address='Synthetic depot',start_latitude=6.9,start_longitude=79.9,end_latitude=6.9,end_longitude=79.9,start_confirmed=True,end_confirmed=True)
   s.add(v);s.commit()
   result=transfer_student(PREFIX+'TEST_01',StudentTransfer(vehicle_id=v.id),s,'isolated-transfer-key')
   self.assertEqual({p['vehicle_id'] for p in result['routing']['plans']},{VEHICLE,v.id})
   for direction in ('morning','afternoon'):
    route=latest_route(s,v.id,direction);self.assertEqual(self.roster(route,'pickup'),{PREFIX+'TEST_01'});self.assertEqual(self.roster(route,'delivery'),{PREFIX+'TEST_01'})
   count=s.scalar(select(func.count()).select_from(RouteVersion))
   transfer_student(PREFIX+'TEST_01',StudentTransfer(vehicle_id=v.id),s,'isolated-transfer-key')
   self.assertEqual(s.scalar(select(func.count()).select_from(RouteVersion)),count)
   added=create_student(StudentWrite(name='Isolated new participant',school_id=PREFIX+'SCH_A',vehicle_id=v.id,home_address='Synthetic only',home_latitude=6.9,home_longitude=79.9,input_source='simulated',location_confirmed=True),s,'isolated-general-add')
   self.assertEqual(added['routing']['outcome'],'success')
   for direction in ('morning','afternoon'):
    route=latest_route(s,v.id,direction)
    self.assertEqual(self.roster(route,'pickup'),{PREFIX+'TEST_01',added['id']})
    self.assertEqual(self.roster(route,'delivery'),{PREFIX+'TEST_01',added['id']})
   self.assertEqual(remove_student(added['id'],s,'isolated-general-remove')['routing']['outcome'],'success')
   for direction in ('morning','afternoon'):self.assertEqual(self.roster(latest_route(s,v.id,direction),'pickup'),{PREFIX+'TEST_01'})
   payload=StudentWrite(name='Unregistered scenario addition',school_id=PREFIX+'SCH_A',vehicle_id=VEHICLE,home_address='Synthetic only',home_latitude=6.9,home_longitude=79.9,input_source='simulated',location_confirmed=True)
   with self.assertRaises(HTTPException) as caught:create_student(payload,s,'rejected-hidden-addition')
   self.assertEqual(caught.exception.status_code,422);s.rollback()
  self.assertEqual(self.day()['plans']['morning']['route']['student_count'],7)
  self.assertEqual(self.day()['plans']['afternoon']['route']['student_count'],6)

 def test_checkpoint_legacy_google_settings_defer_without_external_calls(self):
  route=self.generate()
  with self.factory() as s:
   saved=s.get(RouteVersion,route['route_id']);saved.request_settings={**saved.request_settings,'provider':'google','live_http_budget':None,'departure_mode':'fixed'}
   s.get(Student,PREFIX+'TEST_01').name='Synthetic changed assignment metadata';s.commit()
   result=regenerate(s,scenario(s),[DEFAULT_DATE],directions=('morning',))
   self.assertEqual(result[0]['status'],'explicit_live_verification_required')
   self.assertFalse(serialize_version(s,saved)['is_current'])
   self.assertEqual(self.day()['plans']['morning']['publication'],'stale')

# Only the four new tests run here. The inherited suite is run separately.
for _name in list(vars(fixtures.LandmarkTests)):
 if _name.startswith('test_'):
  setattr(PretripCheckpoint,_name,None)

if __name__=='__main__':unittest.main()
