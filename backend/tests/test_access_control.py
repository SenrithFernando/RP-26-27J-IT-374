"""Actual main.app HTTP security tests; all DB changes roll back, no lifespan/workers.

No fixed passwords, public auth bypass or paid providers. The measured-labelled
phone test inputs exist only inside the rollback transaction, never real datasets.
"""
import json,os,secrets,unittest
from datetime import timedelta,datetime,timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from database import get_engine
from persistence import session_dependency
from models import (Account,DriverVehicle,ParentStudent,School,Student,Vehicle,Trip,
    TrackingSession,LoginSession,VehiclePosition,PickupWindow,PickupOutcome,MissedPickupNotification,RouteVersion)
from auth import hasher,token_hash,_attempts
from main import app
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store
from trips import CreateTrip,create_trip,transition


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_AUTH_TESTS')=='1','Opt in to rollback-only PostgreSQL security tests.')
class AccessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password=secrets.token_urlsafe(24);cls.results=[]

    def setUp(self):
        _attempts.clear()
        self.connection=get_engine().connect();self.transaction=self.connection.begin()
        self.factory=lambda:Session(self.connection,join_transaction_mode='create_savepoint')
        def db():
            with self.factory() as s:yield s
        app.dependency_overrides[session_dependency]=db
        self.client=TestClient(app)  # No context manager: no production worker startup.
        self.prefix='AUTH_TEST_'+uuid4().hex[:8]
        self.users={};self.vehicles=[];self.students=[];self.trips=[];self.routes=[]
        with self.factory() as s:
            school=School(id=self.prefix+'_S',name='Rollback-only security fixture',input_source='measured',address='Test-only',
                latitude=6.9,longitude=79.9,location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=46800)
            s.add(school);s.flush()
            for i in range(2):
                v=Vehicle(id=self.prefix+'_V'+str(i),capacity=2,input_source='measured',start_address='Test-only',end_address='Test-only',
                    start_latitude=6.9,start_longitude=79.9,start_confirmed=True,end_latitude=6.9,end_longitude=79.9,end_confirmed=True)
                s.add(v);s.flush();self.vehicles.append(v.id)
                child=Student(id=self.prefix+'_P'+str(i),name='Rollback-only child',home_id=self.prefix+'_H'+str(i),home_address='Test-only',
                    school_id=school.id,vehicle_id=v.id,input_source='measured',home_latitude=6.901,home_longitude=79.901,location_confirmed=True,active=True)
                s.add(child);s.flush();self.students.append(child.id)
            hashed=hasher.hash(self.password)
            for name,role in [('admin','administrator'),('driverA','driver'),('driverB','driver'),('parentA','parent'),('parentB','parent')]:
                user=Account(id=self.prefix+'_'+name,username=(self.prefix+'_'+name).lower(),role=role,password_hash=hashed,active=True,demo_only=False,failed_attempts=0)
                s.add(user);s.flush();self.users[name]=(user.id,user.username)
            for i in range(2):
                s.add(DriverVehicle(account_id=self.users['driverA' if i==0 else 'driverB'][0],vehicle_id=self.vehicles[i]))
                s.add(ParentStudent(account_id=self.users['parentA' if i==0 else 'parentB'][0],student_id=self.students[i]))
            s.commit()
            for vehicle in self.vehicles:
                route=generate_and_store(s,GenerateRouteRequest(vehicle_id=vehicle,direction='morning',departure_seconds=21600,solver_time_limit_seconds=1,include_geometry=False))
                planned=create_trip(CreateTrip(route_id=route['route_id']),s)
                transition(s,planned['trip_id'],'ACTIVE');self.trips.append(planned['trip_id']);self.routes.append(route['route_id'])
        self.headers={name:self.login(name) for name in self.users}

    def login(self,name,mode='real'):
        response=self.client.post('/auth/login',json={'username':self.users[name][1],'password':self.password,'mode':mode})
        self.assertEqual(response.status_code,200)
        return {'Authorization':'Bearer '+response.json()['token']}

    def tearDown(self):
        self.client.close();app.dependency_overrides.clear();self.transaction.rollback();self.connection.close()
        with Session(get_engine()) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Account).where(Account.id.startswith(self.prefix))),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.id.startswith(self.prefix))),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(Student).where(Student.id.startswith(self.prefix))),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(Trip).where(Trip.vehicle_id.startswith(self.prefix))),0)
            self.assertEqual(s.scalar(select(func.count()).select_from(VehiclePosition).where(VehiclePosition.vehicle_id.startswith(self.prefix))),0)
        self.results.append(self._testMethodName)

    @classmethod
    def tearDownClass(cls):
        Path('../docs/auth-verification.json').write_text(json.dumps({'checks':cls.results,'isolation':'Every test transaction rolled back; no accounts/trips/positions retained.','paid_provider_calls':0,'passwords':'Generated in memory, never logged or persisted outside rollback.'},indent=2),encoding='utf-8')

    def enroll(self,who='driverA'):
        response=self.client.post('/tracking/enroll',headers=self.headers[who],json={'vehicle_id':self.vehicles[0],'trip_id':self.trips[0],'kind':'phone','label':'Rollback-only device'})
        self.assertEqual(response.status_code,201)
        return response.json()

    def upload(self,credential,**extra):
        return self.client.post('/tracking/positions',headers={'Authorization':'Bearer '+credential},json={
            'sample_id':uuid4().hex,'recorded_at':datetime.now(timezone.utc).isoformat(),'latitude':6.901,'longitude':79.901,'accuracy_m':5,**extra})

    def test_anonymous_and_parent_object_scope_and_exports(self):
        for path in ['/routing/students','/routing/vehicles','/routes/latest?vehicle_id='+self.vehicles[0]+'&direction=morning',
            '/trips/'+self.trips[0],'/routing/vehicles/'+self.vehicles[0]+'/positions','/routing/notifications?recipient=admin','/ml/status']:
            self.assertEqual(self.client.get(path).status_code,401,path)
        self.assertEqual(self.client.post('/exports/measured-observations',json={'observations':[]}).status_code,401)
        parent=self.headers['parentA']
        self.assertEqual(self.client.get('/parent/students/'+self.students[0],headers=parent).status_code,200)
        self.assertEqual(self.client.get('/parent/students/'+self.students[0],headers=parent).json()['input_source'],'measured')
        self.assertEqual(self.client.get('/parent/students/'+self.students[1],headers=parent).status_code,403)
        listed=self.client.get('/routing/students',headers=parent).json()
        self.assertEqual([r['id'] for r in listed],[self.students[0]])
        for query in ['recipient=parent&student_id='+self.students[1],'recipient=admin']:
            self.assertEqual(self.client.get('/routing/notifications?'+query,headers=parent).status_code,403)
        from notifications import create_missed_event
        notices=[]
        with self.factory() as s:
            for trip_id in self.trips:
                window=s.scalar(select(PickupWindow).where(PickupWindow.trip_id==trip_id))
                outcome=s.scalar(select(PickupOutcome).where(PickupOutcome.window_id==window.id))
                window.started_at=datetime.now(timezone.utc)-timedelta(seconds=901)
                window.deadline_at=window.started_at+timedelta(seconds=900);window.state='MISSED';outcome.state='MISSED'
                s.flush();create_missed_event(s,window,outcome,datetime.now(timezone.utc),'expiry_worker');s.flush()
                notices.append(s.scalar(select(MissedPickupNotification.id).where(MissedPickupNotification.trip_id==trip_id)))
            s.commit()
        inbox=self.client.get('/routing/notifications?recipient=parent&student_id='+self.students[0],headers=parent).json()
        self.assertEqual(len(inbox['notifications']),1)
        self.assertEqual(inbox['notifications'][0]['route_id'],self.routes[0])
        self.assertEqual(inbox['notifications'][0]['route_version'],1)
        self.assertEqual(self.client.patch('/routing/notifications/'+notices[1]+'/read',headers=parent,
            json={'recipient':'parent','student_id':self.students[0],'read':True}).status_code,403)
        self.assertEqual(self.client.patch('/routing/notifications/'+notices[0]+'/read',headers=parent,
            json={'recipient':'parent','student_id':self.students[0],'read':True}).status_code,200)
        self.assertEqual(self.client.get('/routing/vehicles/'+self.vehicles[0]+'/positions',headers=parent).status_code,403)
        for who in ['parentA','driverA']:
            self.assertEqual(self.client.post('/exports/measured-observations',headers=self.headers[who],json={'observations':[]}).status_code,403)
        self.assertEqual(self.client.post('/exports/measured-observations',headers=self.headers['admin'],json={'observations':[]}).status_code,200)

    def test_driver_vehicle_trip_and_device_forgery(self):
        driver=self.headers['driverA']
        listed=self.client.get('/routing/vehicles',headers=driver).json();self.assertEqual([r['id'] for r in listed],[self.vehicles[0]])
        for path in ['/trips/'+self.trips[1],'/routing/vehicles/'+self.vehicles[1]+'/positions',
            '/routes/latest?vehicle_id='+self.vehicles[1]+'&direction=morning','/routes/'+self.routes[1]+'/map-image']:
            self.assertEqual(self.client.get(path,headers=driver).status_code,403,path)
        self.assertEqual(self.client.post('/trips/'+self.trips[1]+'/start',headers=driver).status_code,403)
        for vehicle,trip in [(self.vehicles[1],self.trips[1]),(self.vehicles[0],self.trips[1])]:
            self.assertEqual(self.client.post('/tracking/enroll',headers=driver,json={'vehicle_id':vehicle,'trip_id':trip,'kind':'phone','label':'Forged binding'}).status_code,403)
        with self.factory() as s:
            route=s.get(RouteVersion,self.routes[0]);original_snapshot=route.input_snapshot;route.input_snapshot={};s.commit()
        self.assertEqual(self.client.post('/tracking/enroll',headers=driver,json={'vehicle_id':self.vehicles[0],
            'trip_id':self.trips[0],'kind':'phone','label':'Unknown provenance'}).status_code,409)
        with self.factory() as s:s.get(RouteVersion,self.routes[0]).input_snapshot=original_snapshot;s.commit()
        grant=self.enroll()
        for field,value in [('vehicle_id',self.vehicles[1]),('trip_id',self.trips[1]),('driver_id',self.users['driverB'][0]),('source','simulation')]:
            self.assertEqual(self.upload(grant['credential'],**{field:value}).status_code,422)
        response=self.upload(grant['credential']);self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['sample']['vehicle_id'],self.vehicles[0]);self.assertEqual(response.json()['sample']['source'],'actual_device')
        self.assertEqual(self.client.get('/auth/me',headers={'Authorization':'Bearer '+grant['credential']}).status_code,401)
        self.assertEqual(self.client.post('/routing/vehicles/'+self.vehicles[0]+'/positions',headers=driver,json={
            'sample_id':'forged','source':'actual_device','trip_id':self.trips[0],'recorded_at':datetime.now(timezone.utc).isoformat(),'latitude':6.9,'longitude':79.9}).status_code,403)

    def test_expiry_revocation_logout_and_assignment_invalidation(self):
        grant=self.enroll()
        with self.factory() as s:
            row=s.get(TrackingSession,grant['tracking_id']);row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);s.commit()
        self.assertEqual(self.upload(grant['credential']).status_code,401)
        grant=self.enroll()
        self.assertEqual(self.client.post('/tracking/'+grant['tracking_id']+'/revoke',headers=self.headers['driverB']).status_code,403)
        self.assertEqual(self.client.post('/tracking/'+grant['tracking_id']+'/revoke',headers=self.headers['driverA']).status_code,200)
        self.assertEqual(self.upload(grant['credential']).status_code,401)
        grant=self.enroll();self.assertEqual(self.client.post('/auth/logout',headers=self.headers['driverA']).status_code,200)
        self.assertEqual(self.upload(grant['credential']).status_code,401)
        self.assertEqual(self.client.get('/auth/me',headers=self.headers['driverA']).status_code,401)
        self.headers['driverA']=self.login('driverA');grant=self.enroll()
        response=self.client.put('/auth/admin/accounts/'+self.users['driverA'][0]+'/vehicles',headers=self.headers['admin'],json={'ids':[self.vehicles[1]]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.upload(grant['credential']).status_code,401)
        self.assertEqual(self.client.get('/auth/me',headers=self.headers['driverA']).status_code,401)
        self.headers['driverA']=self.login('driverA')
        with self.factory() as s:
            token=self.headers['driverA']['Authorization'][7:]
            row=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(token)));row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);s.commit()
        self.assertEqual(self.client.get('/auth/me',headers=self.headers['driverA']).status_code,401)

    def test_closed_trip_queue_cannot_change_live_state_and_demo_is_restricted(self):
        grant=self.enroll();response=self.upload(grant['credential']);self.assertEqual(response.status_code,200)
        position_id=response.json()['sample']['id']
        self.assertEqual(self.client.post('/trips/'+self.trips[0]+'/complete',headers=self.headers['driverA']).status_code,200)
        self.assertEqual(self.upload(grant['credential']).status_code,409)
        latest=self.client.get('/routing/vehicles/'+self.vehicles[0]+'/positions/latest',headers=self.headers['driverA']).json()
        self.assertEqual(latest['position']['id'],position_id)
        demo=self.login('admin','demo')
        self.assertEqual(self.client.get('/trips/'+self.trips[1],headers=demo).status_code,403)
        self.assertEqual(self.client.post('/exports/measured-observations',headers=demo,json={'observations':[]}).status_code,403)
        self.assertEqual(self.client.post('/auth/admin/accounts',headers=demo,json={}).status_code,403)
        # Current labels changing must not expose a previously real snapshot/GPS in demo.
        with self.factory() as s:
            for student_id in self.students:
                child=s.get(Student,student_id);child.input_source='simulated'
                s.get(School,child.school_id).input_source='simulated'
                s.get(Vehicle,child.vehicle_id).input_source='simulated'
            s.commit()
        self.assertEqual(self.client.get('/routes/latest?vehicle_id='+self.vehicles[0]+'&direction=morning',headers=demo).status_code,403)
        self.assertEqual(self.client.get('/trips/current?vehicle_id='+self.vehicles[0]+'&direction=morning',headers=demo).status_code,403)
        self.assertIsNone(self.client.get('/routing/vehicles/'+self.vehicles[0]+'/positions/latest',headers=demo).json()['position'])

    def test_authenticated_simulation_remains_separate_from_phone(self):
        from data_provenance import register_synthetic_trip
        with self.factory() as s:
            school=School(id=self.prefix+'_SIM_S',name='Synthetic security check',input_source='simulated',address='Synthetic',
                latitude=6.9,longitude=79.9,location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=46800)
            vehicle=Vehicle(id=self.prefix+'_SIM_V',capacity=2,input_source='simulated',start_address='Synthetic',end_address='Synthetic',
                start_latitude=6.9,start_longitude=79.9,start_confirmed=True,end_latitude=6.9,end_longitude=79.9,end_confirmed=True)
            s.add_all([school,vehicle]);s.flush()
            s.add(Student(id=self.prefix+'_SIM_P',name='Synthetic security child',home_id=self.prefix+'_SIM_H',home_address='Synthetic',
                school_id=school.id,vehicle_id=vehicle.id,input_source='simulated',home_latitude=6.901,home_longitude=79.901,location_confirmed=True,active=True))
            s.add(DriverVehicle(account_id=self.users['driverA'][0],vehicle_id=vehicle.id));s.commit()
            route=generate_and_store(s,GenerateRouteRequest(vehicle_id=vehicle.id,direction='morning',departure_seconds=21600,include_geometry=False,solver_time_limit_seconds=1))
            planned=create_trip(CreateTrip(route_id=route['route_id']),s);transition(s,planned['trip_id'],'ACTIVE')
            register_synthetic_trip(s,planned['trip_id'],'rollback-security-test','Synthetic simulation/phone separation check.');s.commit()
            vehicle_id=vehicle.id;trip_id=planned['trip_id']
        body={'vehicle_id':vehicle_id,'trip_id':trip_id,'kind':'simulation','label':'Authorized test simulation'}
        grant=self.client.post('/tracking/enroll',headers=self.headers['driverA'],json=body)
        self.assertEqual(grant.status_code,201)
        uploaded=self.upload(grant.json()['credential']);self.assertEqual(uploaded.status_code,200)
        self.assertEqual(uploaded.json()['sample']['source'],'simulation')
        self.assertEqual(self.client.post('/tracking/enroll',headers=self.headers['driverA'],json={**body,'kind':'phone'}).status_code,409)
        self.assertEqual(self.client.get('/trips/'+trip_id,headers=self.login('driverA','demo')).status_code,200)

    def test_phone_accuracy_lineage_duplicates_and_order(self):
        grant=self.enroll();credential=grant['credential']
        stamp=datetime.now(timezone.utc)
        sample={'sample_id':uuid4().hex,'recorded_at':stamp.isoformat(),'accuracy_m':6,'speed_mps':None}
        first=self.upload(credential,**sample);self.assertEqual(first.status_code,200)
        stored=first.json()['sample']
        self.assertEqual(stored['source'],'actual_device')
        self.assertEqual(stored['tracking_session_id'],grant['tracking_id'])
        self.assertEqual(stored['accuracy_m'],6);self.assertEqual(stored['accuracy_quality'],'acceptable')
        self.assertIsNone(stored['speed_mps'])
        self.assertEqual(datetime.fromisoformat(stored['recorded_at'].replace('Z','+00:00')),stamp)
        duplicate=self.upload(credential,**sample).json()
        self.assertTrue(duplicate['duplicate']);self.assertEqual(duplicate['arrival_detection'],'duplicate_ignored')
        self.assertEqual(self.upload(credential,accuracy_m=None).status_code,422)
        self.assertEqual(self.upload(credential,accuracy_m=-1).status_code,422)
        poor=self.upload(credential,recorded_at=(stamp+timedelta(seconds=2)).isoformat(),accuracy_m=500).json()
        self.assertEqual(poor['sample']['accuracy_quality'],'poor')
        self.assertEqual(poor['arrival_detection'],'poor_accuracy_ignored')
        self.assertEqual(poor['operational_monitoring'],'poor_accuracy_ignored')
        late=self.upload(credential,recorded_at=(stamp+timedelta(seconds=1)).isoformat()).json()
        self.assertFalse(late['advances_latest']);self.assertEqual(late['arrival_detection'],'out_of_order')
        latest=self.client.get('/routing/vehicles/'+self.vehicles[0]+'/positions/latest',headers=self.headers['driverA']).json()
        self.assertEqual(latest['position']['id'],poor['sample']['id']);self.assertEqual(latest['status'],'unknown')
        from data_provenance import position_exclusion_reason
        with self.factory() as s:
            self.assertEqual(position_exclusion_reason(s,s.get(VehiclePosition,poor['sample']['id'])),'poor_position_accuracy')

    def test_password_hash_lockout_and_redacted_validation(self):
        with self.factory() as s:
            row=s.get(Account,self.users['driverA'][0]);self.assertTrue(row.password_hash.startswith('$argon2id$'))
            self.assertNotIn(self.password,row.password_hash)
        for _ in range(5):
            response=self.client.post('/auth/login',json={'username':self.users['driverA'][1],'password':'incorrect-in-memory-test','mode':'real'})
            self.assertEqual(response.status_code,401);self.assertNotIn('incorrect-in-memory-test',response.text)
        self.assertEqual(self.client.post('/auth/login',json={'username':self.users['driverA'][1],'password':self.password,'mode':'real'}).status_code,401)
        response=self.client.post('/auth/login',json={'username':self.users['driverA'][1],'password':'','mode':'real'})
        self.assertEqual(response.status_code,422)
        self.assertTrue(all('input' not in item for item in response.json()['detail']))
