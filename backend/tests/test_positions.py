"""Opt-in isolated position ingestion checks; no arrival/passenger events are created."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from uuid import uuid4
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database import get_engine
from models import Vehicle, VehiclePosition, Trip
from positions import router
from test_trip_lifecycle import Client

app=FastAPI(); app.include_router(router)

@unittest.skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS')=='1','Opt in to isolated PostgreSQL fixtures.')
class PositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.start_server()
    @classmethod
    def start_server(cls):
        cls.server=subprocess.Popen([sys.executable,'-m','uvicorn','test_positions:app','--host','127.0.0.1','--port',str(cls.port)],
            env={**os.environ,'PYTHONPATH':str(Path('tests').resolve())},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.client=Client(f'http://127.0.0.1:{cls.port}')
        for _ in range(100):
            try: cls.client.get('/openapi.json');return
            except OSError: time.sleep(.1)
        raise RuntimeError('Position test server unavailable.')
    @classmethod
    def tearDownClass(cls):
        cls.server.terminate();cls.server.wait(timeout=10)
    def test_ingestion_ordering_validation_history_and_persistence(self):
        vehicle='S9A_'+uuid4().hex[:10]
        with Session(get_engine()) as session:
            session.add(Vehicle(id=vehicle,capacity=2,input_source='simulated'));session.commit()
        client=self.client;root=f'/routing/vehicles/{vehicle}/positions'
        unknown=client.get(root+'/latest').json()
        self.assertEqual(unknown['status'],'unknown');self.assertIsNone(unknown['position'])
        self.assertEqual(unknown['movement_state'],'unknown')
        now=datetime.now(timezone.utc)
        def post(id,at,**kw):
            return client.post(root,json=dict(sample_id=id,recorded_at=at.isoformat(),source='simulation',latitude=6.9,longitude=79.9,speed_mps=None,**kw))
        first=post('first',now-timedelta(seconds=120));self.assertEqual(first.status_code,200)
        self.assertEqual(client.get(root+'/latest').json()['status'],'stale')
        fresh=post('fresh',now);self.assertTrue(fresh.json()['advances_latest'])
        duplicate=post('fresh',now);self.assertTrue(duplicate.json()['duplicate']);self.assertFalse(duplicate.json()['advances_latest'])
        alias=post('another-id',now);self.assertTrue(alias.json()['duplicate'])
        late=post('late',now-timedelta(seconds=90));self.assertFalse(late.json()['advances_latest'])
        self.assertEqual(client.get(root+'/latest').json()['position']['sample_id'],'fresh')
        self.assertEqual(post('fresh',now-timedelta(seconds=1)).status_code,409)
        self.assertEqual(post('future',now+timedelta(minutes=5)).status_code,422)
        base=dict(sample_id='bad',recorded_at=now.isoformat(),source='simulation',latitude=6.9,longitude=79.9)
        for patch in ({'latitude':91},{'longitude':181},{'latitude':'NaN'},{'speed_mps':-1},{'speed_mps':'Infinity'},
                      {'recorded_at':now.replace(tzinfo=None).isoformat()},{'source':'unknown'},{'trip_id':'missing'}):
            self.assertIn(client.post(root,json={**base,**patch}).status_code,(422,404))
        with Session(get_engine()) as session:
            trip=session.scalar(select(Trip).order_by(Trip.created_at.desc()).limit(1))
            if trip: self.assertEqual(client.post(root,json={**base,'trip_id':trip.id}).status_code,422)
            self.assertEqual(session.scalar(select(func.count()).select_from(VehiclePosition).where(VehiclePosition.vehicle_id==vehicle)),3)
            stored=session.scalar(select(VehiclePosition).where(VehiclePosition.vehicle_id==vehicle).limit(1))
            self.assertIsNotNone(stored.recorded_at.tzinfo);self.assertIsNotNone(stored.received_at.tzinfo)
        limited=client.get(root,params={'limit':2}).json()
        self.assertEqual(len(limited['positions']),2);self.assertTrue(limited['truncated'])
        self.assertEqual(client.get(root,params={'limit':501}).status_code,422)
        self.assertEqual(client.get(root+'/latest',params={'trip_id':''}).status_code,422)
        self.assertEqual(client.get(root,params={'window_seconds':604801}).status_code,422)
        self.assertEqual(client.get('/routing/vehicles/missing/positions/latest').status_code,404)
        self.server.terminate();self.server.wait(timeout=10);self.start_server()
        self.assertEqual(client.get(root+'/latest').json()['position']['id'],fresh.json()['sample']['id'])
        report={'vehicle_id':vehicle,'stored_samples':3,'duplicate_samples_inserted':0,'latest_sample':'fresh',
            'checks':['unknown/stale/fresh status','duplicate identity and timestamp alias deduplicated','out-of-order retained without latest rollback',
                      'conflicting duplicate rejected','future and invalid inputs rejected','bounded history','aware timestamps','backend restart persistence'],
            'arrival_detection':'not exercised by this unassociated vehicle-only fixture; see test_arrivals.py','actual_device_verification':'not performed'}
        output=Path('../docs/stage9a_verification.json')
        if output.exists():
            previous=json.loads(output.read_text(encoding='utf-8'))
            if previous.get('browser'): report['browser']=previous['browser']
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
