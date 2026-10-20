"""Opt-in real PostgreSQL/HTTP/worker checks; isolated synthetic Stage 9C fixtures."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from threading import Event,Thread
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase,skipUnless
from unittest.mock import patch,Mock
from uuid import uuid4
from types import SimpleNamespace
from fastapi import FastAPI,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from database import get_engine
from models import School,Vehicle,Student,Trip,PickupWindow,PickupOutcome,PickupTransition,RouteVersion
from pickup_windows import router,manual_action,clock,create_windows
from pickup_worker import pickup_loop,expire_due
from positions import router as positions_router
from trips import router as trips_router
from arrivals import router as arrivals_router
from notifications import router as notification_router
from route_service import generate_and_store
from route_schemas import GenerateRouteRequest
from test_trip_lifecycle import Client

@asynccontextmanager
async def lifespan(app):
    stop=Event();thread=Thread(target=pickup_loop,args=(stop,),daemon=True);thread.start()
    try: yield
    finally: stop.set();thread.join(timeout=5)
app=FastAPI(lifespan=lifespan)
from domain_http_context import install_domain_context
install_domain_context(app)  # Never imported by main.app; no authentication claims for this harness.
for api in (router,positions_router,trips_router,arrivals_router,notification_router): app.include_router(api)

class PickupGroupingTests(TestCase):
    def test_shared_revisit_and_per_stop_scope(self):
        snapshot={'stops':[
            dict(sequence=1,action='start'),
            dict(sequence=2,action='pickup',school_id='S',latitude=6.9,longitude=79.9,student_id='A',name='A'),
            dict(sequence=3,action='pickup',school_id='S',latitude=6.9,longitude=79.9,student_id='B',name='B'),
            dict(sequence=4,action='delivery'),
            dict(sequence=5,action='pickup',school_id='S',latitude=6.9,longitude=79.9,student_id='C',name='C')]}
        for scope,expected in [('per_school',2),('per_stop',3)]:
            session=Mock();session.scalar.return_value=datetime.now(timezone.utc);added=[];session.add.side_effect=added.append
            trip=SimpleNamespace(id='T',route_id='R',direction='afternoon',pickup_settings={'scope':scope,'mode':'production','duration_seconds':900})
            create_windows(session,trip,snapshot)
            windows=[row for row in added if isinstance(row,PickupWindow)]
            rows=[row for row in added if isinstance(row,PickupOutcome)]
            self.assertEqual(len(windows),expected);self.assertEqual(len(rows),3)
            if scope=='per_school':
                self.assertEqual(rows[0].window_id,rows[1].window_id)
                self.assertNotEqual(rows[1].window_id,rows[2].window_id)


@skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS')=='1','Opt in to isolated synthetic pickup fixtures.')
class PickupWindowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock: sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.start_server()
    @classmethod
    def start_server(cls):
        cls.server=subprocess.Popen([sys.executable,'-m','uvicorn','test_pickup_windows:app','--host','127.0.0.1','--port',str(cls.port)],
            env={**os.environ,'PYTHONPATH':str(Path('tests').resolve()),'PICKUP_DEMO_DURATION_SECONDS':'5','PICKUP_WORKER_INTERVAL_SECONDS':'.2'},
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.client=Client(f'http://127.0.0.1:{cls.port}')
        for _ in range(100):
            try: cls.client.get('/openapi.json');return
            except OSError:time.sleep(.1)
        raise RuntimeError('Pickup worker test server unavailable.')
    @classmethod
    def stop_server(cls): cls.server.terminate();cls.server.wait(timeout=10)
    @classmethod
    def tearDownClass(cls): cls.stop_server()
    def fixture(self,mode='simulation_demo',scope='per_school',prefix_label='S9C_'):
        prefix=prefix_label+uuid4().hex[:8]
        with Session(get_engine()) as s:
            s.add(School(id=prefix+'_S',name='Synthetic shared pickup school',input_source='simulated',address='Synthetic school',latitude=6.9,longitude=79.9,
                location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=46800))
            s.add(Vehicle(id=prefix+'_V',capacity=3,input_source='simulated',start_address='Synthetic depot',end_address='Synthetic depot',
                start_latitude=6.9,start_longitude=79.9,start_confirmed=True,end_latitude=6.9,end_longitude=79.9,end_confirmed=True));s.commit()
            for i in range(3):
                s.add(Student(id=prefix+'_P'+str(i),name='Synthetic pupil '+str(i),home_id=prefix+'_H'+str(i),vehicle_id=prefix+'_V',school_id=prefix+'_S',
                    input_source='simulated',home_address='Synthetic home',home_latitude=6.901+i*.001,home_longitude=79.901,location_confirmed=True,active=True))
            s.commit()
            route=generate_and_store(s,GenerateRouteRequest(vehicle_id=prefix+'_V',direction='afternoon',departure_seconds=46800,solver_time_limit_seconds=1,include_geometry=False))
        response=self.client.post('/trips',json={'route_id':route['route_id'],'pickup_mode':mode,'pickup_scope':scope})
        self.assertEqual(response.status_code,200,response.json())
        trip=response.json();self.assertEqual(self.client.post(f"/trips/{trip['trip_id']}/start").status_code,200)
        with Session(get_engine()) as s:
            row=s.get(Trip,trip['trip_id']);row.started_at=datetime.now(timezone.utc)-timedelta(seconds=25);row.current_stop_selected_at=row.started_at;s.commit()
        return trip,route
    def arrive(self,trip,route):
        now=datetime.now(timezone.utc);stop=route['stops'][1];last=None
        for index,seconds in enumerate((15,7,0)):
            last=dict(sample_id='pickup-test-'+uuid4().hex,trip_id=trip['trip_id'],source='simulation',latitude=stop['latitude'],longitude=stop['longitude'],recorded_at=(now-timedelta(seconds=seconds)).isoformat())
            response=self.client.post(f"/routing/vehicles/{trip['vehicle_id']}/positions",json=last)
            self.assertEqual(response.status_code,200,response.json())
        self.assertEqual(response.json()['arrival_detection'],'arrived')
        return last
    def windows(self,trip):return self.client.get(f"/trips/{trip['trip_id']}/pickup-windows").json()
    def test_persistence_expiry_restart_boundary_and_races(self):
        trip,route=self.fixture();before=self.windows(trip)
        self.assertEqual(len(before['windows']),1,'One shared school visit, not one window per student.')
        self.assertEqual(len(before['windows'][0]['outcomes']),3)
        self.assertEqual(before['windows'][0]['state'],'SCHEDULED')
        student=before['windows'][0]['outcomes'][0]['student_id']
        self.assertEqual(self.client.post(f"/trips/{trip['trip_id']}/pickups/{student}/confirm").status_code,409)
        last=self.arrive(trip,route);active=self.windows(trip);window=active['windows'][0]
        self.assertEqual(window['state'],'WAITING');self.assertEqual(window['duration_seconds'],5)
        for _ in range(2):
            self.assertEqual(self.windows(trip)['windows'][0]['deadline_at'],window['deadline_at'])
        self.assertTrue(self.client.post(f"/routing/vehicles/{trip['vehicle_id']}/positions",json=last).json()['duplicate'])
        self.assertEqual(self.windows(trip)['windows'][0]['deadline_at'],window['deadline_at'])
        people=window['outcomes']
        confirm=f"/trips/{trip['trip_id']}/pickups/{people[0]['student_id']}/confirm"
        self.assertEqual(self.client.post(confirm).status_code,200);self.assertEqual(self.client.post(confirm).status_code,200)
        self.assertEqual(self.client.post(f"/trips/{trip['trip_id']}/pickups/{people[1]['student_id']}/cancel",json={'reason':'Synthetic student absent'}).status_code,200)
        # No browser or API reads are used to cause expiry; inspect PostgreSQL directly.
        deadline=datetime.fromisoformat(window['deadline_at'])
        time.sleep(max(0,(deadline-datetime.now(timezone.utc)).total_seconds())+.8)
        with Session(get_engine()) as s:
            outcomes=s.scalars(select(PickupOutcome).where(PickupOutcome.trip_id==trip['trip_id']).order_by(PickupOutcome.stop_sequence)).all()
            self.assertEqual([row.state for row in outcomes],['PICKED_UP','CANCELLED','MISSED'])
            self.assertEqual(s.get(PickupWindow,window['window_id']).state,'MISSED')
            count=s.scalar(select(func.count()).select_from(PickupTransition).where(PickupTransition.window_id==window['window_id']))
            self.assertEqual(s.get(RouteVersion,route['route_id']).result['waiting_seconds'],route['waiting_seconds'])
        self.assertEqual(expire_due(),0)
        with Session(get_engine()) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(PickupTransition).where(PickupTransition.window_id==window['window_id'])),count)
        unfinished=self.client.get(f"/trips/{trip['trip_id']}").json()['unfinished_actions']
        self.assertEqual(len([a for a in unfinished if a['action']=='delivery']),3)
        self.assertFalse(any(a['action']=='pickup' and a['student_id']==people[0]['student_id'] for a in unfinished))
        # Production duration and shared student outcomes; deterministic exact deadline boundary.
        prod,prodroute=self.fixture('production');self.arrive(prod,prodroute);pw=self.windows(prod)['windows'][0]
        self.assertEqual(pw['duration_seconds'],900)
        self.assertEqual((datetime.fromisoformat(pw['deadline_at'])-datetime.fromisoformat(pw['started_at'])).total_seconds(),900)
        end=datetime.fromisoformat(pw['deadline_at']);pupils=pw['outcomes']
        with Session(get_engine()) as s,patch('pickup_windows.clock',return_value=end-timedelta(microseconds=1)):
            manual_action(s,prod['trip_id'],pupils[0]['student_id'],'confirm')
        with Session(get_engine()) as s,patch('pickup_windows.clock',return_value=end):
            with self.assertRaises(HTTPException) as rejected:manual_action(s,prod['trip_id'],pupils[1]['student_id'],'confirm')
            self.assertEqual(rejected.exception.status_code,409)
        self.assertEqual(self.windows(prod)['windows'][0]['outcomes'][0]['state'],'PICKED_UP')
        self.assertEqual(self.windows(prod)['windows'][0]['outcomes'][1]['state'],'MISSED')
        # Separate per-stop scope remains available.
        separate,_=self.fixture('production','per_stop');self.assertEqual(len(self.windows(separate)['windows']),3)
        # Closing a trip cancels scheduled pickups explicitly, without delivery confirmation.
        self.assertEqual(self.client.post(f"/trips/{separate['trip_id']}/complete").status_code,200)
        self.assertTrue(all(w['state']=='CANCELLED' for w in self.windows(separate)['windows']))
        # Recovery: stop the worker/backend before deadline, restart after deadline.
        recovery,rr=self.fixture();self.arrive(recovery,rr);rw=self.windows(recovery)['windows'][0]
        self.stop_server();time.sleep(max(0,(datetime.fromisoformat(rw['deadline_at'])-datetime.now(timezone.utc)).total_seconds())+.2)
        self.start_server()
        for _ in range(50):
            with Session(get_engine()) as s: recovered=s.get(PickupWindow,rw['window_id']).state
            if recovered=='MISSED':break
            time.sleep(.1)
        self.assertEqual(recovered,'MISSED')
        self.assertEqual(self.windows(recovery)['windows'][0]['deadline_at'],rw['deadline_at'])
        # Race at an already reached deadline. Both paths must converge on MISSED once.
        race,rroute=self.fixture('production');self.arrive(race,rroute);racew=self.windows(race)['windows'][0]
        with Session(get_engine()) as s:
            w=s.get(PickupWindow,racew['window_id']);w.started_at=datetime.now(timezone.utc)-timedelta(seconds=901);w.deadline_at=w.started_at+timedelta(seconds=900);s.commit()
        def confirm_race():
            with Session(get_engine()) as s:
                try:manual_action(s,race['trip_id'],racew['outcomes'][0]['student_id'],'confirm');return 200
                except HTTPException as e:return e.status_code
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(confirm_race);b=pool.submit(expire_due)
            self.assertEqual(a.result(),409);b.result()
        with Session(get_engine()) as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(PickupTransition).where(PickupTransition.window_id==racew['window_id'],PickupTransition.student_id==racew['outcomes'][0]['student_id'],PickupTransition.to_state=='MISSED')),1)
        # Demo never accepts device samples, even when a simulated vehicle was selected.
        self.assertEqual(self.client.post(f"/routing/vehicles/{trip['vehicle_id']}/positions",json={**last,'sample_id':'device-rejection','source':'actual_device'}).status_code,422)
        report={'trip_id':trip['trip_id'],'vehicle_id':trip['vehicle_id'],'shared_windows':1,'individual_students':3,
            'outcomes':['PICKED_UP','CANCELLED','MISSED'],'production_seconds':900,'test_demo_seconds':5,
            'checks':['arrival-only start','refresh and duplicate arrival preserve deadline','shared-school grouping','per-stop alternative',
                'manual confirmation idempotent','expiry without browser','restart overdue recovery','repeat worker processing idempotent',
                'strict before/exact deadline boundary','confirmation/expiry race','individual mixed outcomes/history retained',
                'deliveries remain unconfirmed','optimizer waiting unchanged','demo device samples rejected'],
            'data_source':'isolated synthetic fixtures; controlled deadline boundary tests; real background worker and process restart'}
        output=Path('../docs/stage9c_verification.json')
        if output.exists():
            previous=json.loads(output.read_text(encoding='utf-8'))
            if previous.get('browser'):report['browser']=previous['browser']
        output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
