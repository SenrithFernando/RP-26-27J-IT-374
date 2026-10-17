"""Opt-in PostgreSQL integration checks; only new S8B synthetic fixtures are written."""
import json
import os
from pathlib import Path
import unittest
from uuid import uuid4
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI
import subprocess
import sys
import socket
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from trips import router as trip_router
from route_api import router as route_router
from planning_api import router as planning_router
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import get_engine
from models import School, Student, Vehicle, Trip, RouteVersion
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store
from trips import today

test_app = FastAPI()  # Focused test server: no recovery worker or provider startup.
test_app.include_router(trip_router)
test_app.include_router(route_router)
test_app.include_router(planning_router)

class Response:
    def __init__(self, response):
        self.status_code = response.status
        self.body = json.loads(response.read())
    def json(self): return self.body

class Client:
    def __init__(self, url): self.url = url
    def call(self, method, path, json=None, params=None):
        if params: path += '?' + urlencode(params)
        request = Request(self.url+path, data=__import__('json').dumps(json).encode() if json is not None else (b'' if method == 'POST' else None), method=method, headers={'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=20) as response: return Response(response)
        except HTTPError as response:
            with response: return Response(response)
    def post(self,path,**kw): return self.call('POST',path,**kw)
    def patch(self,path,**kw): return self.call('PATCH',path,**kw)
    def get(self,path,**kw): return self.call('GET',path,**kw)


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS') == '1', 'Opt in to synthetic PostgreSQL fixtures.')
class TripLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); cls.port=sock.getsockname()[1]
        cls.start_server()

    @classmethod
    def start_server(cls):
        env={**os.environ, 'PYTHONPATH': str(Path('tests').resolve())}
        cls.server=subprocess.Popen([sys.executable,'-m','uvicorn','test_trip_lifecycle:test_app','--host','127.0.0.1','--port',str(cls.port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.client=Client(f'http://127.0.0.1:{cls.port}')
        for _ in range(100):
            try:
                cls.client.get('/openapi.json'); return
            except OSError: time.sleep(.1)
        raise RuntimeError('Focused test server failed to start.')

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate(); cls.server.wait(timeout=10)

    def test_persistence_transitions_duplicates_and_pinned_route(self):
        prefix = 'S8B_' + uuid4().hex[:8]
        vehicle = prefix + '_V'
        client = self.client
        with Session(get_engine()) as s:
            s.add(School(id=prefix+'_S', name='Synthetic Stage 8B school', input_source='simulated', address='Synthetic test school',
                latitude=6.9, longitude=79.9, location_confirmed=True, morning_deadline_seconds=28800, afternoon_finish_seconds=46800))
            s.add(Vehicle(id=vehicle, capacity=2, input_source='simulated', start_address='Synthetic depot', end_address='Synthetic depot',
                start_latitude=6.9, start_longitude=79.9, start_confirmed=True, end_latitude=6.9, end_longitude=79.9, end_confirmed=True))
            s.commit()
            s.add(Student(id=prefix+'_P', name='Synthetic Stage 8B student', school_id=prefix+'_S', vehicle_id=vehicle,
                home_id=prefix+'_HOME', home_address='Synthetic test home', home_latitude=6.901, home_longitude=79.901,
                input_source='simulated', location_confirmed=True, active=True))
            s.commit()
            def generate(direction='morning', **kw):
                return generate_and_store(s, GenerateRouteRequest(vehicle_id=vehicle, direction=direction,
                    departure_seconds=21600 if direction == 'morning' else 46800, solver_time_limit_seconds=1,
                    include_geometry=False, **kw))
            old = generate()
            current = generate()
            afternoon = generate('afternoon')
            self.assertEqual(client.post('/trips', json={'route_id':'missing'}).status_code,404)
            # Older version with same roster must not be accepted.
            self.assertEqual(client.post('/trips', json={'route_id':old['route_id']}).status_code,409)
            planned = client.post('/trips',json={'route_id':current['route_id']}).json()
            tid = planned['trip_id']
            self.assertEqual(planned['state'],'PLANNED')
            self.assertEqual(planned['unfinished_action_count'],2)
            self.assertEqual(client.post('/trips',json={'route_id':current['route_id']}).json()['trip_id'],tid)
            self.assertEqual(client.post(f'/trips/{tid}/complete').status_code,409)
            other = client.post('/trips',json={'route_id':afternoon['route_id']}).json()
            # Race morning and afternoon: exactly one active vehicle trip is accepted.
            with ThreadPoolExecutor(max_workers=2) as pool:
                starts = list(pool.map(lambda id: client.post(f'/trips/{id}/start'),[tid,other['trip_id']]))
            self.assertEqual(sorted(r.status_code for r in starts),[200,409])
            active = next(r.json() for r in starts if r.status_code == 200)
            active_id = active['trip_id']
            self.assertEqual(client.post(f'/trips/{active_id}/start').json()['started_at'],active['started_at'])
            other_id = other['trip_id'] if active_id == tid else tid
            with self.assertRaises(IntegrityError) as duplicate:
                with s.begin_nested():
                    started_at = s.get(Trip, active_id).started_at
                    row = s.get(Trip, other_id)
                    row.state = 'ACTIVE'; row.started_at = started_at
                    s.flush()
            self.assertEqual(duplicate.exception.orig.diag.constraint_name,'one_active_trip_per_vehicle')

            self.assertEqual(client.get('/trips/current',params={'vehicle_id':vehicle}).json()['trip']['trip_id'],active_id)
            self.assertIsNotNone(s.get(Trip, active_id).started_at.tzinfo)
            with Session(get_engine()) as independent:
                self.assertEqual(independent.get(Trip,active_id).state,'ACTIVE')
            self.server.terminate(); self.server.wait(timeout=10)
            self.start_server()
            self.assertEqual(client.get(f'/trips/{active_id}').json()['state'],'ACTIVE')
            self.assertEqual(client.patch(f"/routes/{active['route_id']}/planning-lock",json={'execution_status':'completed'}).status_code,409)
            blocked = client.post('/routes/generate',json={**active['route']['request_settings'],'include_geometry':False})
            self.assertEqual(blocked.status_code,409)
            # A roster change makes planning stale but cannot alter the active snapshot.
            s.get(Vehicle,vehicle).roster_version += 1; s.commit()
            after = client.get(f'/trips/{active_id}').json()
            self.assertEqual(after['route_id'],active['route_id'])
            self.assertEqual(after['route']['stops'],active['route']['stops'])
            ended = client.post(f'/trips/{active_id}/complete').json()
            self.assertEqual(ended['state'],'COMPLETED')
            original_actions=planned['unfinished_actions'] if active_id==tid else other['unfinished_actions']
            # Stage 9C explicitly cancels unresolved pickups on lifecycle close; delivery stays unverified.
            self.assertEqual(ended['unfinished_actions'],[{**a,'status':'CANCELLED' if a['action']=='pickup' else a['status']} for a in original_actions])
            self.assertEqual(ended['unfinished_action_count'],2)
            self.assertEqual(client.post(f'/trips/{active_id}/complete').json()['completed_at'],ended['completed_at'])
            self.assertEqual(client.post(f'/trips/{active_id}/start').status_code,409)
            self.assertEqual(client.post(f'/trips/{active_id}/cancel',json={'reason':'test'}).status_code,409)
            waiting = other if active_id==tid else planned
            self.assertEqual(client.post(f"/trips/{waiting['trip_id']}/start").status_code,409)  # stale
            self.assertEqual(client.post(f"/trips/{waiting['trip_id']}/cancel",json={'reason':'   '}).status_code,422)
            cancelled = client.post(f"/trips/{waiting['trip_id']}/cancel",json={'reason':'Synthetic test cancellation'}).json()
            self.assertEqual(cancelled['state'],'CANCELLED')
            self.assertIsNone(cancelled['started_at'])
            self.assertEqual(client.post(f"/trips/{waiting['trip_id']}/start").status_code,409)
            # Active cancellation has an aware timestamp and keeps unfinished actions.
            direction = waiting['direction']
            fresh = generate(direction)
            cancel_active = client.post('/trips',json={'route_id':fresh['route_id']}).json()
            self.assertEqual(client.post(f"/trips/{cancel_active['trip_id']}/start").status_code,200)
            cancelled_active = client.post(f"/trips/{cancel_active['trip_id']}/cancel",json={'reason':'Deliberate active cancellation'}).json()
            self.assertEqual(cancelled_active['unfinished_action_count'],2)
            self.assertIsNotNone(cancelled_active['started_at'])
            self.assertEqual(cancelled_active['route']['execution_status'],'cancelled')
            # A cancelled active snapshot can be followed by a new pre-trip plan, never overwritten.
            fresh = generate(direction)
            # Test infeasible and old-date plan rejection on isolated rows.
            bad = generate(direction, service_date=today()-timedelta(days=1))
            self.assertEqual(client.post('/trips',json={'route_id':bad['route_id']}).status_code,409)
            badrow=s.get(RouteVersion,bad['route_id']); badrow.service_date=today(); badrow.feasibility_status='infeasible';s.commit()
            self.assertEqual(client.post('/trips',json={'route_id':bad['route_id']}).status_code,409)
            demo = generate(direction)
            # Leave a feasible current route without an open trip for browser verification.
            report={'vehicle_id':vehicle,'route_id':demo['route_id'],'direction':direction,
                'completed_trip_id':active_id,'cancelled_trip_id':cancelled_active['trip_id'],
                'checks':['planned-active-completed','planned-cancelled','active-cancelled','concurrent cross-direction duplicate start rejected','PostgreSQL active-vehicle unique index enforced',
                    'idempotent create/start/end','separate DB session and backend process restart persistence','active route regeneration blocked',
                    'roster edit does not replace trip snapshot','unfinished actions retained after end',
                    'stale/infeasible/past-date plans rejected','terminal trips cannot reopen','legacy lock bypass rejected'],
                'data_source':'isolated synthetic Stage 8B fixtures; deterministic simulation routing; no external provider calls'}
            Path('../docs/stage8b_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,indent=2))
