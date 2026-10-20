"""Future-dated, rollback-only synthetic PM trips. Never write to the physical trip."""
import os,secrets,unittest
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from database import get_engine
from persistence import session_dependency
from main import app
from auth import token_hash,_attempts
from models import (Account,LoginSession,Vehicle,Student,School,Trip,RouteVersion,RouteStop,VehiclePosition,
 LandmarkScenario,LandmarkAttendance,LandmarkBoarding,PickupOutcome,PickupWindow,PickupTransition,TripStopArrival,MissedPickupNotification,LandmarkInputEvent)
from landmark import SCENARIO,VEHICLE,PREFIX,PARTICIPANTS,VERSION,Generation,generate_daily,read_daily
from trips import create_trip,CreateTrip,transition

DAY=date(2099,10,19)
def moment(h,m=0,s=0):return datetime.fromisoformat(f'2099-10-19T{h:02}:{m:02}:{s:02}+05:30')

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_BOARDING_TESTS')=='1','Opt in to rollback-only synthetic boarding tests.')
class BoardingCheckpointTests(unittest.TestCase):
 def setUp(self):
  import boarding_evidence # Import clock aliases before patching controlled clocks.
  _attempts.clear();self.c=get_engine().connect();self.outer=self.c.begin();self.now=moment(13,20)
  self.factory=lambda:Session(self.c,join_transaction_mode='create_savepoint')
  def db():
   with self.factory() as s:yield s
  app.dependency_overrides[session_dependency]=db;self.client=TestClient(app);self.headers={}
  self.patches=[patch('pickup_windows.clock',side_effect=lambda s:self.now),patch('pickup_worker.clock',side_effect=lambda s:self.now),patch('boarding_evidence.clock',side_effect=lambda s:self.now),patch('landmark.event_clock',side_effect=lambda:self.now)]
  for p in self.patches:p.start()
  with self.factory() as s:
   sc=s.get(LandmarkScenario,SCENARIO)
   if not sc:self.skipTest('Initialize Malabe scenario first; tests do not provision operational records.')
   sc.policy={**sc.policy,'afternoon_only':'unresolved'}
   v=s.get(Vehicle,VEHICLE)
   for end in ['start','end']:
    setattr(v,end+'_latitude',6.9);setattr(v,end+'_longitude',79.9);setattr(v,end+'_confirmed',True)
   for key in sc.policy['school_ids']:
    school=s.get(School,key);school.latitude=6.9;school.longitude=79.9;school.location_confirmed=True
   for key,_,school,pm in PARTICIPANTS:
    p=s.get(Student,PREFIX+key);p.active=True;p.vehicle_id=VEHICLE;p.school_id=PREFIX+school
    p.home_latitude=6.9;p.home_longitude=79.9;p.location_confirmed=True
    s.add(LandmarkAttendance(scenario_id=SCENARIO,service_date=DAY,student_id=p.id,am='yes',pm='yes' if pm else 'no',occurred_at=moment(13),event_id='ROLLBACK_INITIAL'))
   for role in ['administrator','driver','parent']:
    uid='BOARDING_TEST_'+uuid4().hex;token='sr_user_'+secrets.token_urlsafe(32)
    s.add(Account(id=uid,username=uid.lower(),password_hash='!',role=role,active=True,demo_only=False,failed_attempts=0));s.flush()
    s.add(LoginSession(id='LOGIN_'+uuid4().hex,account_id=uid,token_hash=token_hash(token),mode='real',created_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
    self.headers[role]={'Authorization':'Bearer '+token}
   s.commit()
  self.trip_id=None
 def tearDown(self):
  self.client.close();app.dependency_overrides.clear()
  for p in reversed(self.patches):p.stop()
  self.outer.rollback();self.c.close()
 def envelope(self,records,kind='boarding',when=None,event_id=None):
  return dict(schema_version=VERSION,event_id=event_id or str(uuid4()),occurred_at=(when or self.now).isoformat(),producer='manual_test',provenance='landmark_test',kind=kind,reason='Isolated synthetic rollback manual boarding test',records=records)
 def event(self,student,when=None,resolve=None):
  return self.envelope([dict(student_external_id=student,service_date=str(DAY),direction='afternoon',trip_id=self.trip_id,outcome='boarded',resolves_event_id=resolve)],when=when)
 def post(self,body,role='administrator'):
  return self.client.post('/daily-plan/import',headers=self.headers[role],json=body)
 def start(self):
  with self.factory() as s:route=generate_daily(Generation(service_date=DAY,direction='afternoon'),s)
  self.assertEqual(route['student_count'],7);self.assertEqual(route['stops'][0]['school_id'],PREFIX+'SCH_B')
  pub=self.client.post('/daily-plan/publish',headers=self.headers['administrator'],json=dict(service_date=str(DAY),direction='afternoon',route_id=route['route_id'],review_unresolved_boarding=True,reason='Explicit isolated synthetic test review'))
  self.assertEqual(pub.status_code,200,pub.text)
  with self.factory() as s:
   trip=create_trip(CreateTrip(route_id=route['route_id'],pickup_scope='per_school'),s)
   with patch('trips.today',return_value=DAY):transition(s,trip['trip_id'],'ACTIVE')
   self.trip_id=trip['trip_id'];t=s.get(Trip,self.trip_id);stop=s.get(RouteStop,(t.route_id,1))
   pos=VehiclePosition(id='POS_'+uuid4().hex,sample_id=str(uuid4()),vehicle_id=VEHICLE,trip_id=t.id,source='simulation',latitude=6.9,longitude=79.9,speed_mps=None,recorded_at=self.now,received_at=self.now)
   s.add(pos);s.flush()
   arrival=TripStopArrival(trip_id=t.id,stop_sequence=1,route_id=t.route_id,last_recorded_at=self.now,observation_count=3,distance_metres=0,source='simulation',event_id='ARRIVAL_'+uuid4().hex,arrived_at=self.now,confirming_position_id=pos.id)
   s.add(arrival);s.flush()
   from pickup_windows import start_from_arrival
   start_from_arrival(s,t,stop,arrival,self.now);s.commit()
   windows=s.scalars(select(PickupWindow).where(PickupWindow.trip_id==t.id)).all()
   self.assertEqual(len(windows),2);self.assertTrue(all(w.duration_seconds==900 for w in windows))
   self.window_id=next(w.id for w in windows if w.school_id==PREFIX+'SCH_B')
  return route
 def worker(self):
  from pickup_worker import expire_due
  with patch('pickup_worker.Session',side_effect=lambda *a,**kw:self.factory()):return expire_due(trip_id=self.trip_id)
 def get_row(self,student):
  with self.factory() as s:
   r=s.scalar(select(PickupOutcome).where(PickupOutcome.trip_id==self.trip_id,PickupOutcome.student_id==PREFIX+student))
   return r.state,r.picked_up_at
 def alerts(self,student=None):
  with self.factory() as s:
   q=select(func.count()).select_from(MissedPickupNotification).where(MissedPickupNotification.trip_id==self.trip_id)
   if student:q=q.where(MissedPickupNotification.student_id==PREFIX+student)
   return s.scalar(q)
 def test_roster_mapping_unknown_no_show_and_am_false_policy(self):
  with self.factory() as s:initial_route=generate_daily(Generation(service_date=DAY,direction='afternoon'),s)
  with self.factory() as s:
   d=read_daily(DAY,s)
   self.assertEqual(d['counts']['afternoon'],7)
   self.assertEqual([x['name'] for x in d['schools']],['Horizon College International',"Boys' Model College"])
   self.assertTrue(all(x['morning_evidence']=='unknown' for x in d['plans']['afternoon']['attendance']['rows']))
  body=self.envelope([dict(student_external_id='TEST_01',service_date=str(DAY),am='no',pm='yes')],kind='attendance')
  self.assertEqual(self.post(body).status_code,200)
  with self.factory() as s:
   d=read_daily(DAY,s);row=next(r for r in d['plans']['afternoon']['attendance']['rows'] if r['external_id']=='TEST_01')
   self.assertEqual(row['pm'],'yes');self.assertTrue(row['eligible'])
   self.assertIn(PREFIX+'TEST_01',d['plans']['afternoon']['attendance']['unresolved_afternoon_only'])
  self.now+=timedelta(seconds=1)
  no_show=self.envelope([dict(student_external_id='TEST_05',service_date=str(DAY),direction='morning',outcome='no_show')])
  self.assertEqual(self.post(no_show).status_code,200)
  with self.factory() as s:
   d=read_daily(DAY,s);self.assertEqual(d['counts']['afternoon'],6)
   row=next(r for r in d['plans']['afternoon']['attendance']['rows'] if r['external_id']=='TEST_05');self.assertFalse(row['eligible'])
   latest=d['plans']['afternoon']['route'];self.assertGreater(latest['version'],initial_route['version'])
   self.assertEqual(latest['student_count'],6)
   self.assertNotIn(PREFIX+'TEST_05',[sid for stop in latest['stops'] for sid in stop.get('student_ids',[])])
 def test_release_overlap_confirmation_expiry_and_no_duplicate_alert(self):
  route=self.start()
  self.now=moment(13,29);self.worker()
  with self.factory() as s:
   w=s.get(PickupWindow,self.window_id);self.assertIsNone(w.started_at);self.assertIsNone(w.deadline_at)
  self.assertEqual(self.alerts(),0)
  self.now=moment(13,30);self.worker()
  with self.factory() as s:
   w=s.get(PickupWindow,self.window_id);self.assertEqual(w.started_at,moment(13,30));self.assertEqual(w.deadline_at,moment(13,45))
   self.assertEqual(datetime.fromisoformat(route['stops'][0]['departure']),w.deadline_at)
   t=s.get(Trip,self.trip_id);stop=s.get(RouteStop,(t.route_id,1));arrival=s.get(TripStopArrival,(t.id,1))
   from pickup_windows import start_from_arrival
   start_from_arrival(s,t,stop,arrival,self.now);s.commit();self.assertEqual(w.deadline_at,moment(13,45))
   self.assertEqual(s.scalar(select(func.count()).select_from(PickupOutcome).where(PickupOutcome.trip_id==t.id)),7)
  self.now=moment(13,35);event=self.event('TEST_05',moment(13,34))
  response=self.post(event);self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['boarding_result']['status'],'test_boarding_confirmed')
  self.assertTrue(self.post(event).json()['duplicate'])
  from pickup_windows import manual_action
  with self.factory() as s:manual_action(s,self.trip_id,PREFIX+'TEST_06','cancel','Isolated cancellation test')
  self.now=moment(13,45);self.assertEqual(self.worker(),1);self.assertEqual(self.worker(),0)
  self.assertEqual(self.alerts('TEST_03'),0);self.assertEqual(self.alerts('TEST_05'),0);self.assertEqual(self.alerts('TEST_06'),0)
  self.assertEqual(self.alerts('TEST_07'),1);self.assertEqual(self.alerts('TEST_08'),1);self.assertEqual(self.alerts(),2)
  with self.factory() as s:
   w=s.get(PickupWindow,self.window_id);self.assertEqual(w.started_at,moment(13,30));self.assertEqual(w.deadline_at,moment(13,45))
 def test_delayed_evidence_review_preserves_alert_and_history(self):
  self.start();self.now=moment(13,30);self.worker();self.now=moment(13,46);self.worker()
  original=self.event('TEST_05',moment(13,35));response=self.post(original)
  self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['boarding_result']['status'],'delayed_evidence_pending_admin_review')
  self.assertEqual(self.get_row('TEST_05')[0],'MISSED');self.assertEqual(self.alerts('TEST_05'),1)
  self.now=moment(13,47);review=self.event('TEST_05',resolve=original['event_id'])
  response=self.post(review);self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(self.get_row('TEST_05'),('PICKED_UP',moment(13,35)));self.assertEqual(self.alerts('TEST_05'),1)
  self.assertTrue(self.post(review).json()['duplicate']);self.worker();self.assertEqual(self.alerts('TEST_05'),1)
  with self.factory() as s:
   event=s.get(LandmarkInputEvent,original['event_id']);self.assertEqual(event.received_at,moment(13,46))
   alert=s.scalar(select(MissedPickupNotification).where(MissedPickupNotification.trip_id==self.trip_id,MissedPickupNotification.student_id==PREFIX+'TEST_05'))
   from notifications import serialize
   data=serialize(alert,'admin',s);self.assertEqual(data['resolution_status'],'resolved_delayed_manual_test_evidence')
   self.assertEqual(data['generation_status'],'in_app_event_created');self.assertEqual(data['parent_channel_status'],'unavailable_hasara_not_connected')
   self.assertGreater(s.scalar(select(func.count()).select_from(PickupTransition).where(PickupTransition.window_id==self.window_id,PickupTransition.student_id==PREFIX+'TEST_05',PickupTransition.to_state=='MISSED')),0)
 def test_at_deadline_evidence_does_not_become_on_time(self):
  self.start();self.now=moment(13,30);self.worker();self.now=moment(13,46)
  response=self.post(self.event('TEST_05',moment(13,45)))
  self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['boarding_result']['status'],'after_deadline_recorded_not_confirmed')
  self.assertEqual(self.get_row('TEST_05')[0],'MISSED');self.assertEqual(self.alerts('TEST_05'),1)
 def test_auth_pm_false_and_completed_physical_trip_are_rejected(self):
  self.start();self.now=moment(13,30);self.worker();body=self.event('TEST_05')
  self.assertEqual(self.client.post('/daily-plan/import',json=body).status_code,401)
  for role in ('driver','parent'):self.assertEqual(self.post(body,role).status_code,403)
  self.assertEqual(self.post(self.event('TEST_03')).status_code,422)
  forbidden=self.event('TEST_05');forbidden['records'][0]['trip_id']='TRIP_f682a6851f3d41ca94dd4cf6e182fafc'
  self.assertEqual(self.post(forbidden).status_code,409)
  with self.factory() as s:self.assertIsNone(s.get(LandmarkInputEvent,forbidden['event_id']))

if __name__=='__main__':unittest.main()
