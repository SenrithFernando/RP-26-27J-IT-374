"""Rollback-only GPS replay checks; no physical-phone or existing trip writes."""
import os
import csv
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_engine
from models import School, Vehicle, Student, Trip, OperationalEpisode, TripOperationalMonitor
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store
from trips import CreateTrip, create_trip, transition
from positions import PositionInput, ingest, latest_result
from operational_monitor import operational_view
from generate_operational_replays import generate
from trips import serialize_trip


class ReplayPayloadTests(unittest.TestCase):
    def test_terminal_replay_preserves_quality_null_speed_and_simulation_source(self):
        import replay_positions
        with tempfile.TemporaryDirectory() as directory:
            fixture=Path(directory)/'quality.csv'
            with fixture.open('w',newline='',encoding='utf-8') as handle:
                writer=csv.DictWriter(handle,fieldnames=['recorded_at','latitude','longitude','speed_mps','accuracy_m','source'])
                writer.writeheader()
                writer.writerow(dict(recorded_at=datetime.now(timezone.utc).isoformat(),latitude=6.9,longitude=79.9,
                    speed_mps='',accuracy_m='100000',source='simulation'))
            posted=[]
            def request(base,path,body=None):
                if body is None:return {'vehicle_id':'SYNTHETIC_V'}
                posted.append((path,body))
                return {'duplicate':False,'advances_latest':True}
            with patch('sys.argv',['replay_positions.py','--vehicle-id','SYNTHETIC_V','--trip-id','SYNTHETIC_TRIP',
                '--fixture',str(fixture),'--rebase-to-now']), patch('builtins.input',return_value=''), \
                patch('replay_positions.cli_auth.configure'),patch('replay_positions.request',side_effect=request),patch('builtins.print'):
                replay_positions.main()
            self.assertEqual(len(posted),1)
            path,body=posted[0]
            self.assertEqual(path,'/routing/vehicles/SYNTHETIC_V/positions')
            self.assertEqual(body['source'],'simulation')
            self.assertEqual(body['accuracy_m'],100000)
            self.assertIsNone(body['speed_mps'])


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_MONITORING_TESTS') == '1', 'Opt in to rollback-only replay tests.')
class MonitoringCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.connection = get_engine().connect()
        self.outer = self.connection.begin()
        self.s = Session(self.connection, join_transaction_mode='create_savepoint')
        self.addCleanup(self.connection.close)
        self.addCleanup(self.outer.rollback)
        self.addCleanup(self.s.close)
        self.base = datetime.now(timezone.utc) - timedelta(hours=2)
        self.prefix = 'REPLAY_CHECK_' + uuid4().hex[:10]
        self.trip = self.make_trip('A')

    def make_trip(self, suffix):
        key = self.prefix + suffix
        self.s.add(School(id=key+'S', name='Synthetic replay school', input_source='simulated',
            address='Synthetic', latitude=6.9, longitude=79.9, location_confirmed=True,
            morning_deadline_seconds=28800, afternoon_finish_seconds=46800))
        self.s.add(Vehicle(id=key+'V', capacity=1, input_source='simulated', start_address='Synthetic depot',
            end_address='Synthetic depot', start_latitude=6.9, start_longitude=79.9,
            end_latitude=6.9, end_longitude=79.9, start_confirmed=True, end_confirmed=True))
        self.s.flush()
        self.s.add(Student(id=key+'P', name='Synthetic replay participant', home_id=key+'H',
            school_id=key+'S', vehicle_id=key+'V', input_source='simulated', home_address='Synthetic',
            home_latitude=6.94, home_longitude=79.94, location_confirmed=True, active=True))
        self.s.commit()
        route = generate_and_store(self.s, GenerateRouteRequest(vehicle_id=key+'V', direction='morning',
            departure_seconds=21600, solver_time_limit_seconds=1, include_geometry=False))
        planned = create_trip(CreateTrip(route_id=route['route_id']), self.s)
        transition(self.s, planned['trip_id'], 'ACTIVE')
        trip = self.s.get(Trip, planned['trip_id'])
        trip.started_at = self.base - timedelta(seconds=1)
        trip.current_stop_selected_at = trip.started_at
        from data_provenance import register_synthetic_trip
        register_synthetic_trip(self.s,trip.id,'tests/test_monitoring_checkpoint.py','Rollback-only deterministic simulation replay')
        self.s.commit()
        return trip

    def feed(self, second, point=(6.92,79.92), *, trip=None, accuracy=5, speed=None, sample_id=None):
        trip = trip or self.trip
        payload = PositionInput(sample_id=sample_id or str(second), trip_id=trip.id, source='simulation',
            latitude=point[0], longitude=point[1], accuracy_m=accuracy, speed_mps=speed,
            recorded_at=self.base + timedelta(seconds=second))
        with patch('positions.datetime') as clock:
            clock.now.return_value = payload.recorded_at + timedelta(milliseconds=100)
            return ingest(trip.vehicle_id, payload, self.s)

    def events(self, kind=None, trip=None):
        query = select(OperationalEpisode).where(OperationalEpisode.trip_id==(trip or self.trip).id)
        if kind: query = query.where(OperationalEpisode.kind==kind)
        return self.s.scalars(query.order_by(OperationalEpisode.episode)).all()

    def view(self, second, trip=None):
        return operational_view(self.s, trip or self.trip, now=self.base+timedelta(seconds=second))

    def test_movement_noise_deviation_recovery_and_ordering(self):
        cfg = self.s.get(TripOperationalMonitor, self.trip.id).settings
        step = min(2, cfg['max_gap_seconds']/2)
        for i in range(5): self.feed(i*step, (6.91+i*.0001,79.91+i*.0001))
        self.assertEqual(self.events(), [])
        # One off-route noise sample cannot satisfy persistence.
        t = 5*step
        self.feed(t, (6.95,79.91)); self.feed(t+step)
        self.assertEqual(self.events(), [])
        t += 2*step
        end = t + cfg['deviation_seconds'] + 2*step
        while t <= end:
            self.feed(t, (6.95,79.91)); t += step
        events = self.events('route_deviation')
        self.assertEqual(len(events),1)
        event = events[0]
        self.assertEqual(event.source,'simulation')
        self.assertEqual(event.geometry_quality,'approximate_stop_sequence')
        self.assertGreaterEqual((event.confirmed_at-event.started_at).total_seconds(),cfg['deviation_seconds'])
        last=t-step
        self.assertTrue(self.feed(last,(6.95,79.91))['duplicate'])
        self.assertFalse(self.feed(last-0.5,(6.95,79.91))['advances_latest'])
        self.assertEqual(self.s.get(TripOperationalMonitor,self.trip.id).last_recorded_at,self.base+timedelta(seconds=last))
        self.feed(t); self.assertEqual(event.status,'ACTIVE')
        end=t+cfg['recovery_seconds']+step
        t+=step
        while t<=end: self.feed(t); t+=step
        self.assertEqual(event.status,'RECOVERED')
        self.assertEqual(len(self.events('route_deviation')),1)

    def test_expected_dwell_stop_missing_speed_and_gps_loss(self):
        cfg=self.s.get(TripOperationalMonitor,self.trip.id).settings
        step=min(2,cfg['max_gap_seconds']/2)
        t=0
        for expected_point in ((6.94,79.94),(6.9,79.9)):
            end=t+cfg['stop_seconds']+step*2
            while t<=end:
                self.feed(t,expected_point);t+=step
            self.assertEqual(self.events('unexpected_stop'),[])
            self.assertIsNotNone(self.view(t-step)['expected_waiting'])
        # Null reported speed stays null; coordinate history supplies movement evidence.
        end=t+cfg['stop_seconds']+step*2
        while t<=end:
            response=self.feed(t)
            self.assertIsNone(response['sample']['speed_mps'])
            t+=step
        self.assertEqual(len(self.events('unexpected_stop')),1)
        self.assertEqual(self.view(t+cfg['freshness_seconds']+1)['gps_state'],'unknown')
        self.assertEqual(len(self.events('unexpected_stop')),1)
        self.assertEqual(self.events('unexpected_stop')[0].status,'ACTIVE')

    def test_gap_and_poor_accuracy_break_candidate(self):
        cfg=self.s.get(TripOperationalMonitor,self.trip.id).settings
        outside=(6.95,79.91)
        self.feed(0,outside);self.feed(2,outside)
        bad=self.feed(4,outside,accuracy=100000)
        self.assertEqual(bad['operational_monitoring'],'poor_accuracy_ignored')
        self.assertEqual(self.view(4)['gps_state'],'unknown')
        self.feed(6,outside)
        self.assertEqual(self.events(),[])
        self.feed(6+cfg['max_gap_seconds']+1,outside)
        self.assertEqual(self.events(),[])
        with patch('positions.datetime') as clock:
            clock.now.return_value=self.base+timedelta(seconds=200)
            self.assertEqual(latest_result(self.s,self.trip.vehicle_id)['status'],'stale')

    def test_missing_speed_moving_and_separate_vehicle_state(self):
        other=self.make_trip('B')
        cfg=self.s.get(TripOperationalMonitor,self.trip.id).settings
        step=min(2,cfg['max_gap_seconds']/2)
        t=0
        while t<=cfg['deviation_seconds']+step*2:
            self.feed(t,(6.95,79.91))
            self.feed(t,(6.91+t*.00004,79.91+t*.00004),trip=other)
            t+=step
        self.assertEqual(len(self.events('route_deviation')),1)
        self.assertEqual(self.events(trip=other),[])
        self.assertIsNotNone(self.view(t-step,other)['derived_step_speed_mps'])
        self.assertGreater(self.view(t-step,other)['derived_step_speed_mps'],cfg['low_movement_mps'])

    def test_generated_csv_replay_scenarios(self):
        for name in ('normal_travel','sustained_deviation','recovery','expected_waiting','unexpected_stop','gps_loss'):
            with self.subTest(scenario=name), tempfile.TemporaryDirectory() as directory:
                trip=self.make_trip(name)
                monitor=self.s.get(TripOperationalMonitor,trip.id)
                manifest=generate(serialize_trip(self.s,trip),monitor.settings,Path(directory))
                self.assertEqual(manifest['geometry_quality'],'approximate_stop_sequence')
                with (Path(directory)/(name+'.csv')).open(newline='',encoding='utf-8') as handle:
                    rows=list(csv.DictReader(handle))
                start=datetime.fromisoformat(rows[0]['recorded_at'])
                previous=None
                for index,row in enumerate(rows):
                    self.assertEqual(row['source'],'simulation')
                    self.assertEqual(row['speed_mps'],'')
                    second=(datetime.fromisoformat(row['recorded_at'])-start).total_seconds()
                    if previous is not None and second-previous>monitor.settings['freshness_seconds']:
                        self.assertEqual(self.view(previous+monitor.settings['freshness_seconds']+1,trip)['gps_state'],'unknown')
                    self.feed(second,(float(row['latitude']),float(row['longitude'])),trip=trip,
                        accuracy=None,sample_id=f'{name}-{index}')
                    previous=second
                events=self.events(trip=trip)
                if name in ('normal_travel','expected_waiting','gps_loss'):
                    self.assertEqual(events,[])
                elif name=='unexpected_stop':
                    self.assertEqual([e.kind for e in events],['unexpected_stop'])
                else:
                    self.assertEqual([e.kind for e in events],['route_deviation'])
                    self.assertEqual(events[0].status,'RECOVERED' if name=='recovery' else 'ACTIVE')

    def test_authenticated_simulation_endpoint_not_phone_ingestion(self):
        import secrets
        from fastapi.testclient import TestClient
        from main import app
        from persistence import session_dependency
        from auth import token_hash
        from models import Account, LoginSession
        uid=self.prefix+'ADMIN'
        token='sr_user_'+secrets.token_urlsafe(32)
        self.s.add(Account(id=uid,username=uid.lower(),password_hash='!',role='administrator',
            active=True,demo_only=False,failed_attempts=0))
        self.s.flush()
        self.s.add(LoginSession(id='LOGIN_'+uuid4().hex,account_id=uid,token_hash=token_hash(token),mode='real',
            created_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.s.commit()
        def db():
            yield self.s
        app.dependency_overrides[session_dependency]=db
        try:
            with patch('positions.datetime') as clock:
                clock.now.return_value=self.base+timedelta(milliseconds=100)
                client=TestClient(app)
                self.addCleanup(client.close)
                path=f'/routing/vehicles/{self.trip.vehicle_id}/positions'
                body=dict(sample_id='http-simulation',trip_id=self.trip.id,source='simulation',
                    latitude=6.92,longitude=79.92,speed_mps=None,accuracy_m=5,recorded_at=self.base.isoformat())
                self.assertEqual(client.post(path,json=body).status_code,401)
                headers={'Authorization':'Bearer '+token}
                result=client.post(path,json=body,headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['sample']['source'],'simulation')
                self.assertIsNone(result.json()['sample']['tracking_session_id'])
                self.assertTrue(client.post(path,json=body,headers=headers).json()['duplicate'])
                body['source']='actual_device'
                self.assertEqual(client.post(path,json=body,headers=headers).status_code,403)
        finally:
            app.dependency_overrides.pop(session_dependency,None)
