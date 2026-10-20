"""Future-dated rollback API duration checks; never reopen the phone trip."""
import os
import unittest
from datetime import date
from unittest.mock import patch
from sqlalchemy import select
import test_landmark_daily as fixtures
from models import LandmarkAttendance, DriverVehicle, LoginSession
from auth import token_hash
from landmark import SCENARIO, VEHICLE, PREFIX, PARTICIPANTS, Generation, generate_daily, read_daily
from trips import create_trip, CreateTrip, transition


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_LANDMARK_TESTS')=='1','Opt in to rollback-only duration checks.')
class DriverDurationSnapshotTests(unittest.TestCase):
    setUp=fixtures.LandmarkTests.setUp
    tearDown=fixtures.LandmarkTests.tearDown

    def test_admin_driver_totals_and_pinned_trip_match_saved_snapshots(self):
        day=date(2099,10,21)
        with self.factory() as s:
            login=s.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(self.headers['driver']['Authorization'].split()[1])))
            s.add(DriverVehicle(account_id=login.account_id,vehicle_id=VEHICLE))
            for key,_,_,pm in PARTICIPANTS:
                s.add(LandmarkAttendance(scenario_id=SCENARIO,service_date=day,student_id=PREFIX+key,
                    am='yes',pm='yes' if pm else 'no',occurred_at=fixtures.datetime.now(fixtures.timezone.utc),event_id='DURATION_ROLLBACK'))
            s.commit()
            routes={d:generate_daily(Generation(service_date=day,direction=d),s) for d in ('morning','afternoon')}
        for direction,route in routes.items():
            result=self.client.post('/daily-plan/publish',headers=self.headers['administrator'],json={
                'service_date':str(day),'direction':direction,'route_id':route['route_id'],
                'review_unresolved_boarding':True,'reason':'Isolated synthetic duration accounting check'})
            self.assertEqual(result.status_code,200,result.text)
        with self.factory() as s:
            admin=read_daily(day,s)
        for direction in routes:
            url=f'/routes/published?vehicle_id={VEHICLE}&service_date={day}&direction={direction}'
            response=self.client.get(url,headers=self.headers['driver'])
            self.assertEqual(response.status_code,200,response.text)
            driver=response.json()['published_route'];saved=admin['plans'][direction]['route']
            self.assertEqual(driver['route_id'],saved['route_id']);self.assertEqual(driver['version'],saved['version'])
            for field in ('driving_seconds','service_seconds','waiting_seconds','total_duration_seconds'):
                self.assertEqual(driver[field],saved[field])
            self.assertEqual(driver['total_duration_seconds'],sum(driver[k] for k in ('driving_seconds','service_seconds','waiting_seconds')))
            self.assertEqual(driver['waiting_seconds'],0)
            self.assertEqual(driver['service_seconds'],2160 if direction=='morning' else 2640)
            self.assertEqual(driver['stops'][-1]['service_seconds'],600 if direction=='morning' else 0)
        with self.factory() as s:
            trip=create_trip(CreateTrip(route_id=routes['morning']['route_id']),s)
            with patch('trips.today',return_value=day):transition(s,trip['trip_id'],'ACTIVE')
        response=self.client.get(f'/routes/published?vehicle_id={VEHICLE}&service_date={day}&direction=afternoon',headers=self.headers['driver']).json()
        self.assertEqual(response['published_route']['route_id'],routes['afternoon']['route_id'])
        self.assertEqual(response['trip']['route_id'],routes['morning']['route_id'])
        self.assertEqual(response['trip']['route']['total_duration_seconds'],routes['morning']['total_duration_seconds'])
