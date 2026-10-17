"""Focused mathematical and opt-in controlled-clock PostgreSQL operational checks."""
import json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest import TestCase,skipUnless
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import School,Student,Vehicle,Trip,OperationalEpisode,TripOperationalMonitor
from database import get_engine
from trips import CreateTrip,create_trip,transition
from positions import PositionInput,ingest
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store
from operational_geometry import point_polyline_metres,decode_polyline,select_geometry
from operational_monitor import operational_view,OperationalSettings
from generate_operational_replays import generate


def encode(points):
    result='';last=[0,0]
    for point in points:
        for index,value in enumerate(point):
            current=round(value*1e5);delta=current-last[index];last[index]=current
            number=~(delta<<1) if delta<0 else delta<<1
            while number>=32:result+=chr((32|(number&31))+63);number>>=5
            result+=chr(number+63)
    return result


class OperationalMathTests(TestCase):
    def test_metric_segments_endpoints_and_degenerate(self):
        self.assertAlmostEqual(point_polyline_metres(.001,0,[[0,-.01],[0,.01]]),111.1949,places=3)
        self.assertAlmostEqual(point_polyline_metres(0,.02,[[0,0],[0,.01]]),1111.9493,places=3)
        self.assertAlmostEqual(point_polyline_metres(.001,0,[[0,0],[0,0]]),111.1949,places=3)
        self.assertEqual(point_polyline_metres(0,0,[[0,-.01],[0,.01]]),0)
        self.assertIsNone(point_polyline_metres(0,0,[]))
    def test_geometry_provenance_validation_and_fallback(self):
        points=[[6.9,79.9],[6.92,79.92],[6.94,79.94]];encoded=encode(points)
        self.assertEqual(decode_polyline(encoded),points)
        stops=[{'latitude':p[0],'longitude':p[1]} for p in points]
        valid={'road_geometry':{'status':'available','provider':'google_routes','encoded_polyline':encoded}}
        self.assertEqual(select_geometry(valid,stops)['quality'],'provider_road_geometry')
        for geometry in ({'status':'available','provider':'unknown','encoded_polyline':encoded},
                         {'status':'available','provider':'google_routes','encoded_polyline':'broken'},
                         {'status':'available','provider':'google_routes','encoded_polyline':encode([[0,0],[1,1]])}):
            self.assertEqual(select_geometry({'road_geometry':geometry},stops)['quality'],'approximate_stop_sequence')
        for text in ('','?', '!!!!!!!!', '_'*40):
            with self.assertRaises(ValueError):decode_polyline(text)
        with self.assertRaises(ValueError):OperationalSettings(max_gap_seconds=30,freshness_seconds=20)


@skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS')=='1','Opt in to isolated synthetic operational fixtures.')
class OperationalIntegrationTests(TestCase):
    def test_ordered_episodes_recovery_expected_waiting_and_loss(self):
        prefix='S9E_'+uuid4().hex[:8]
        with Session(get_engine()) as s:
            s.add(School(id=prefix+'_S',name='Synthetic operational school',input_source='simulated',address='Synthetic school',latitude=6.9,longitude=79.9,
                location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=46800))
            s.add(Vehicle(id=prefix+'_V',capacity=1,input_source='simulated',start_address='Synthetic depot',end_address='Synthetic depot',
                start_latitude=6.9,start_longitude=79.9,start_confirmed=True,end_latitude=6.9,end_longitude=79.9,end_confirmed=True));s.commit()
            s.add(Student(id=prefix+'_P',name='Synthetic operational student',home_id=prefix+'_H',school_id=prefix+'_S',vehicle_id=prefix+'_V',
                input_source='simulated',home_address='Synthetic home',home_latitude=6.94,home_longitude=79.94,location_confirmed=True,active=True));s.commit()
            route=generate_and_store(s,GenerateRouteRequest(vehicle_id=prefix+'_V',direction='morning',departure_seconds=21600,solver_time_limit_seconds=1,include_geometry=False))
            planned=create_trip(CreateTrip(route_id=route['route_id']),s);transition(s,planned['trip_id'],'ACTIVE')
            trip=s.get(Trip,planned['trip_id']);base=datetime.now(timezone.utc)-timedelta(seconds=500)
            trip.started_at=base-timedelta(seconds=1);trip.current_stop_selected_at=trip.started_at;s.commit()
            def feed(second,point,id=None,speed=0):
                payload=PositionInput(sample_id=id or str(second),trip_id=trip.id,source='simulation',latitude=point[0],longitude=point[1],speed_mps=speed,recorded_at=base+timedelta(seconds=second))
                with patch('positions.datetime') as clock:
                    clock.now.return_value=payload.recorded_at+timedelta(seconds=.1)
                    return ingest(trip.vehicle_id,payload,s)
            def view(second):return operational_view(s,trip,now=base+timedelta(seconds=second))
            def events(kind=None):
                query=select(OperationalEpisode).where(OperationalEpisode.trip_id==trip.id)
                if kind:query=query.where(OperationalEpisode.kind==kind)
                return s.scalars(query.order_by(OperationalEpisode.episode)).all()
            # Normal travel ignores a reported speed=0 because actual coordinates move.
            for t in range(0,20,5):feed(t,[6.91+t*.0001,79.91+t*.0001])
            self.assertEqual(events(),[])
            # Sustained approximate deviation opens exactly one episode.
            for t in range(20,50,5):feed(t,[6.95,79.91])
            deviation=events('route_deviation')[0];deviation_id=deviation.id
            self.assertEqual(deviation.geometry_quality,'approximate_stop_sequence')
            self.assertEqual(deviation.status,'ACTIVE')
            self.assertTrue(feed(45,[6.95,79.91])['duplicate'])
            self.assertFalse(feed(44,[6.95,79.91])['advances_latest'])
            self.assertEqual(len(events('route_deviation')),1)
            # Sustained return, not a single inside sample, records recovery.
            feed(50,[6.92,79.92]);self.assertEqual(s.get(OperationalEpisode,deviation_id).status,'ACTIVE')
            for t in (55,60,65):feed(t,[6.92+(t-50)*.00002,79.92+(t-50)*.00002])
            self.assertEqual(s.get(OperationalEpisode,deviation_id).status,'RECOVERED')
            # Unexpected stationary cluster far from every pickup/school/depot.
            for t in range(70,140,5):feed(t,[6.92,79.92])
            stopped=events('unexpected_stop');self.assertEqual(len(stopped),1);stop_id=stopped[0].id
            self.assertEqual(stopped[0].status,'ACTIVE')
            self.assertEqual(view(165)['gps_state'],'unknown')
            self.assertEqual(s.get(OperationalEpisode,stop_id).status,'ACTIVE','GPS loss is not recovery.')
            # The first sample after a gap cannot clear an existing stop episode.
            feed(170,[6.925,79.925]);self.assertEqual(s.get(OperationalEpisode,stop_id).status,'ACTIVE')
            for t in (175,180,185):feed(t,[6.925+(t-170)*.0001,79.925+(t-170)*.0001])
            self.assertEqual(s.get(OperationalEpisode,stop_id).status,'RECOVERED')
            # Current pickup waiting is excluded even longer than the stop threshold.
            for t in range(190,265,5):feed(t,[6.94,79.94])
            self.assertEqual(len(events('unexpected_stop')),1)
            self.assertEqual(view(260.2)['expected_waiting'],'known_pickup_window_waiting')
            self.assertEqual(view(300)['gps_state'],'unknown')
            before=len(events())
            # A lone off-route observation followed by a gap does not create another episode.
            feed(300,[6.95,79.91]);feed(320,[6.95,79.91])
            self.assertEqual(len(events()),before)
            for t in (325,330,335,340):feed(t,[6.95,79.91])
            self.assertEqual(len(events('route_deviation')),2)
            self.assertNotEqual(events('route_deviation')[1].id,deviation_id)
            # PostgreSQL enforces one ACTIVE episode per kind/trip.
            active=events('route_deviation')[1]
            with self.assertRaises(IntegrityError) as duplicate:
                with s.begin_nested():
                    data={column.name:getattr(active,column.name) for column in OperationalEpisode.__table__.columns if column.name not in ('id','episode')}
                    s.add(OperationalEpisode(id='OPS_'+uuid4().hex,episode=99,**data));s.flush()
            self.assertEqual(duplicate.exception.orig.diag.constraint_name,'operational_one_active_kind')
            with Session(get_engine()) as reader:
                self.assertEqual(reader.get(OperationalEpisode,stop_id).status,'RECOVERED')
                self.assertEqual(reader.get(TripOperationalMonitor,trip.id).last_recorded_at,base+timedelta(seconds=340))
            cfg=s.get(TripOperationalMonitor,trip.id).settings
            # Explicit lifecycle closure is not reported as GPS recovery.
            transition(s,trip.id,'CANCELLED','Synthetic operational checks complete.')
            self.assertEqual(s.get(OperationalEpisode,active.id).status,'CLOSED')
            self.assertIsNone(s.get(OperationalEpisode,active.id).recovered_at)
            # Leave a NEW isolated active trip ready for the six real-time replay scenarios.
            demo_route=generate_and_store(s,GenerateRouteRequest(vehicle_id=trip.vehicle_id,direction='morning',departure_seconds=21600,solver_time_limit_seconds=1,include_geometry=False))
            demo=create_trip(CreateTrip(route_id=demo_route['route_id']),s);demo=transition(s,demo['trip_id'],'ACTIVE')
            cfg=s.get(TripOperationalMonitor,demo['trip_id']).settings
            manifest=generate(demo,cfg,Path('../data/operational_replays'))
            self.assertEqual(set(manifest['scenarios']),{'normal_travel','sustained_deviation','recovery','expected_waiting','unexpected_stop','gps_loss'})
            report={'replay_trip_id':demo['trip_id'],'replay_route_id':demo_route['route_id'],'vehicle_id':trip.vehicle_id,'trip_id':trip.id,'route_id':trip.route_id,'geometry_quality':'approximate_stop_sequence',
                'deviation_episodes':2,'unexpected_stop_episodes':1,'replay_scenarios':manifest['scenarios'],
                'checks':['point-to-polyline metres','provider geometry validation/fallback','normal travel despite reported zero speed',
                    'sustained deviation and recovery','duplicate/late samples ignored','one alert per active episode',
                    'unexpected stop from ordered low-movement history','expected pickup/known waiting excluded',
                    'GPS loss neither stop nor recovery','gap interrupts candidates','PostgreSQL active episode uniqueness',
                    'new DB session persistence','trip closure distinct from GPS recovery'],
                'data_source':'synthetic controlled-clock observations; no live Google calls or accuracy/precision/recall validation'}
            Path('../docs/stage9e_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
