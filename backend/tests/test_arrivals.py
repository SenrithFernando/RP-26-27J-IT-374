"""Controlled-clock PostgreSQL checks. All fixtures and observations are synthetic."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock
from uuid import uuid4
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from arrivals import ArrivalSettings, arrival_view, advance_stop, distance_m, process_position
from database import get_engine
from models import School, Student, Vehicle, Trip, TripStopArrival, RouteStop, VehiclePosition
from positions import PositionInput, ingest
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store
from trips import CreateTrip, create_trip, transition
from data_provenance import register_synthetic_trip, ARRIVAL_GENERATOR
import unittest


class ArrivalSettingsTests(TestCase):
    def test_source_change_resets_candidate_without_persisting_fake_device_samples(self):
        base=datetime.now(timezone.utc)
        trip=SimpleNamespace(id='T',state='ACTIVE',current_stop_sequence=2,route_id='R',
            arrival_settings=ArrivalSettings().model_dump(),started_at=base-timedelta(seconds=1),
            current_stop_selected_at=base-timedelta(seconds=1))
        stop=SimpleNamespace(sequence=2,latitude=0,longitude=0)
        row=SimpleNamespace(last_recorded_at=base,arrived_at=None,source='simulation',
            candidate_started_at=base,observation_count=2)
        session=Mock();session.scalar.return_value=trip
        session.get.side_effect=lambda model,key: stop if model is RouteStop else row
        position=SimpleNamespace(id='in-memory-only',trip_id='T',source='actual_device',
            latitude=0,longitude=0,recorded_at=base+timedelta(seconds=1))
        self.assertEqual(process_position(session,position,position.recorded_at),'arrival_candidate')
        self.assertEqual(row.observation_count,1)
        self.assertEqual(row.candidate_started_at,position.recorded_at)
        session.commit.assert_not_called()

    def test_thresholds_and_distance(self):
        self.assertAlmostEqual(distance_m(6.9,79.9,6.9,79.9),0)
        self.assertAlmostEqual(distance_m(0,0,0.001,0),111.195,places=2)
        for values in ({'exit_radius_metres':50},{'min_observations':1},{'dwell_seconds':0},{'max_gap_seconds':30,'freshness_seconds':20}):
            with self.assertRaises(ValueError): ArrivalSettings(**values)


    def test_minimum_count_is_required_even_after_dwell(self):
        base=datetime.now(timezone.utc)
        cfg=ArrivalSettings(dwell_seconds=5,min_observations=4).model_dump()
        trip=SimpleNamespace(id='T',state='ACTIVE',current_stop_sequence=2,route_id='R',
            arrival_settings=cfg,started_at=base-timedelta(seconds=1),current_stop_selected_at=base-timedelta(seconds=1))
        stop=SimpleNamespace(sequence=2,latitude=0,longitude=0)
        rows=[]
        session=Mock();session.scalar.return_value=trip
        session.get.side_effect=lambda model,key: stop if model is RouteStop else rows[0] if rows else None
        session.add.side_effect=rows.append
        for second in (0,3,6):
            position=SimpleNamespace(id=str(second),trip_id='T',source='simulation',latitude=0,longitude=0,recorded_at=base+timedelta(seconds=second))
            self.assertEqual(process_position(session,position,position.recorded_at),'arrival_candidate')
        self.assertIsNone(rows[0].arrived_at)  # 6 seconds, but only 3 of 4 observations.
        position=SimpleNamespace(id='9',trip_id='T',source='simulation',latitude=0,longitude=0,recorded_at=base+timedelta(seconds=9))
        self.assertEqual(process_position(session,position,position.recorded_at),'arrived')


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS')=='1','Opt in to synthetic PostgreSQL arrival fixtures.')
class ArrivalIntegrationTests(TestCase):
    def test_boundaries_gaps_ordering_single_event_and_current_stop(self):
        prefix='S9B_'+uuid4().hex[:8]
        with Session(get_engine()) as s:
            s.add(School(id=prefix+'_S',name='Synthetic arrival school',input_source='simulated',address='Synthetic test school',
                latitude=6.9,longitude=79.9,location_confirmed=True,morning_deadline_seconds=28800,afternoon_finish_seconds=46800))
            s.add(Vehicle(id=prefix+'_V',capacity=2,input_source='simulated',start_address='Synthetic depot',end_address='Synthetic depot',
                start_latitude=6.9,start_longitude=79.9,start_confirmed=True,end_latitude=6.9,end_longitude=79.9,end_confirmed=True));s.commit()
            s.add(Student(id=prefix+'_P',name='Synthetic arrival student',home_id=prefix+'_H',school_id=prefix+'_S',vehicle_id=prefix+'_V',
                input_source='simulated',home_address='Synthetic home',home_latitude=6.901,home_longitude=79.901,location_confirmed=True,active=True));s.commit()
            route=generate_and_store(s,GenerateRouteRequest(vehicle_id=prefix+'_V',direction='morning',departure_seconds=21600,include_geometry=False,solver_time_limit_seconds=1))
            planned=create_trip(CreateTrip(route_id=route['route_id']),s)
            register_synthetic_trip(s,planned['trip_id'],ARRIVAL_GENERATOR,'Controlled-clock arrival fixture; no physical device.')
            s.commit()
            started=transition(s,planned['trip_id'],'ACTIVE')
            trip=s.get(Trip,planned['trip_id'])
            self.assertEqual(trip.current_stop_sequence,2)
            self.assertEqual(trip.arrival_settings,ArrivalSettings().model_dump())
            # Controlled GPS clock only in this isolated fixture, no waiting or future GPS.
            base=datetime.now(timezone.utc)-timedelta(minutes=5)
            trip.started_at=base-timedelta(seconds=1);trip.current_stop_selected_at=trip.started_at;s.commit()
            target=route['stops'][1]
            def feed(second,metres=0,id=None,source='simulation',age=.1,latitude=None,longitude=None):
                recorded=base+timedelta(seconds=second)
                payload=PositionInput(sample_id=id or str(second),trip_id=trip.id,source=source,
                    latitude=latitude if latitude is not None else target['latitude']+metres/111194.9266,
                    longitude=longitude if longitude is not None else target['longitude'],recorded_at=recorded)
                with patch('positions.datetime') as clock:
                    clock.now.return_value=recorded+timedelta(seconds=age)
                    return ingest(trip.vehicle_id,payload,s)
            def view(second): return arrival_view(s,trip,now=base+timedelta(seconds=second))
            self.assertEqual(view(0)['state'],'gps_unknown')
            # A future delivery-school location cannot start arrival of current home pickup.
            feed(0,latitude=6.9,longitude=79.9)
            self.assertEqual(view(.2)['state'],'approaching')
            self.assertEqual(s.scalar(select(func.count()).select_from(TripStopArrival).where(TripStopArrival.trip_id==trip.id,TripStopArrival.stop_sequence==3)),0)
            feed(1,49);self.assertEqual(view(1.2)['state'],'arrival_candidate')
            candidate=view(1.2)['candidate_started_at']
            feed(5,51);self.assertEqual(view(5.2)['candidate_started_at'],candidate) # Hysteresis band.
            feed(9,74);self.assertEqual(view(9.2)['state'],'arrival_candidate')
            feed(10,76);self.assertEqual(view(10.2)['state'],'approaching')
            self.assertIsNone(view(10.2)['candidate_started_at'])
            feed(11,49);feed(15,49)
            # Duplicates and late samples never accumulate dwell/observations.
            count=view(15.2)['observation_count']
            self.assertTrue(feed(15,49)['duplicate'])
            self.assertFalse(feed(14,49)['advances_latest'])
            self.assertEqual(view(15.2)['observation_count'],count)
            self.assertEqual(view(26)['state'],'gps_unknown') # Gap exceeds maximum, not outside.
            feed(27,49);self.assertEqual(view(27.2)['observation_count'],1)
            self.assertEqual(view(27.2)['candidate_started_at'],base+timedelta(seconds=27))
            # Source-change logic has a pure in-memory test above; all persisted GPS is simulation.
            with self.assertRaises(HTTPException) as rejected:
                feed(28,49,source='actual_device')
            self.assertEqual(rejected.exception.status_code,422)
            s.rollback()
            feed(28,49);feed(29,49)
            self.assertEqual(s.scalar(select(func.count()).select_from(VehiclePosition).where(
                VehiclePosition.trip_id==trip.id,VehiclePosition.source=='actual_device')),0)
            feed(34,49,age=30) # stale batch cannot earn dwell.
            self.assertEqual(view(64)['state'],'gps_unknown')
            feed(40,49);self.assertEqual(view(40.2)['observation_count'],1)
            feed(47,60);self.assertIsNone(view(47.2)['arrival_event'])
            feed(55,49)
            arrived=view(55.2)
            self.assertEqual(arrived['state'],'arrived')
            self.assertEqual(arrived['arrival_event']['arrived_at'],base+timedelta(seconds=55))
            event=arrived['arrival_event']
            feed(56,0);feed(57,100)
            self.assertEqual(view(57.2)['arrival_event'],event)
            self.assertAlmostEqual(view(57.2)['distance_metres'],100,places=1)
            self.assertTrue(feed(56,0)['duplicate'])
            self.assertEqual(s.scalar(select(func.count()).select_from(TripStopArrival).where(TripStopArrival.trip_id==trip.id,TripStopArrival.arrived_at.is_not(None))),1)
            self.assertEqual(view(90)['state'],'gps_unknown')
            self.assertEqual(view(90)['arrival_event'],event)
            with Session(get_engine()) as fresh:
                persisted=arrival_view(fresh,fresh.get(Trip,trip.id),now=base+timedelta(seconds=57.2))
                self.assertEqual(persisted['arrival_event'],event)
            # Advancing is explicit and does not confirm any passenger action.
            pending=list(trip.unfinished_actions)
            next_view=advance_stop(trip.id,2,s)
            self.assertEqual(next_view['current_stop']['sequence'],3)
            self.assertEqual(next_view['state'],'gps_unknown')
            self.assertEqual(trip.unfinished_actions,pending)
            with self.assertRaises(HTTPException) as conflict: advance_stop(trip.id,2,s)
            self.assertEqual(conflict.exception.status_code,409);s.rollback()
            with self.assertRaises(HTTPException): advance_stop(trip.id,3,s)
            s.rollback()
            # Leave a clean active, unknown second stop for a real browser check.
            report={'vehicle_id':trip.vehicle_id,'trip_id':trip.id,'route_id':trip.route_id,'current_stop_sequence':3,
                'event_id':event['event_id'],'arrival_events':1,'unfinished_actions':len(pending),
                'checks':['radius boundary/hysteresis','future stops ignored','duplicate/out-of-order ignored','GPS gaps reset dwell',
                          'stale samples ignored','source changes reset dwell','dwell and minimum observations both required',
                          'one immutable arrival event','unknown GPS differs from outside','event survives new DB session',
                          'explicit next stop preserves passenger actions','duplicate advance rejected'],
                'data_source':'synthetic fixtures and controlled GPS timestamps; actual hardware not verified'}
            output=Path('../docs/stage9b_verification.json')
            if output.exists():
                previous=json.loads(output.read_text(encoding='utf-8'))
                if previous.get('browser'): report['browser']=previous['browser']
            output.write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,indent=2))
