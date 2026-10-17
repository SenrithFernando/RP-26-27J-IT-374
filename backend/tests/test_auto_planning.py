"""Pre-trip mutation invariants; DB checks create isolated synthetic fixtures."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from database import get_engine
from models import School, Student, Vehicle, RouteVersion, RouteStop
from persistence import (StudentWrite, StudentTransfer, StudentStatus, create_student,
                         update_student, transfer_student, change_student_status, remove_student)
from planning_api import ExecutionLock, lock_execution, plan_status, retry_event
from planning_state import comparison
from planning_orchestration import process_event_safe
from route_api import school_schedule
from route_schemas import GenerateRouteRequest, SchoolSchedule
from route_service import generate_and_store, latest_route
from route_solver import solve_registered_route


class ComparisonTests(unittest.TestCase):
    def test_actual_signed_deltas_and_unavailable_values(self):
        before = dict(feasibility_status='feasible', _signature=['same'], distance_metres=10,
                      driving_seconds=2, service_seconds=3, waiting_seconds=0, total_duration_seconds=5)
        same = comparison(before, before)
        self.assertFalse(same['itinerary_changed'])
        self.assertEqual(set(same['delta_after_minus_before'].values()), {0})
        after = {**before, 'distance_metres': 15}
        self.assertEqual(comparison(before, after)['delta_after_minus_before']['distance_metres'], 5)
        self.assertTrue(all(v is None for v in comparison(before, None)['delta_after_minus_before'].values()))


@unittest.skipUnless(os.getenv('SAFERIDE_RUN_DB_TESTS') == '1', 'Opt in to synthetic PostgreSQL fixtures.')
class AutomaticPlanningTests(unittest.TestCase):
    def test_mutations_failures_idempotency_and_execution_protection(self):
        prefix = 'S5_' + uuid4().hex[:10]
        with get_engine().connect() as connection, Session(connection) as s:
            schools = [prefix + '_S' + str(i) for i in range(2)]
            vehicles = [prefix + '_V' + str(i) for i in range(2)]
            for id in schools:
                s.add(School(id=id, name='Synthetic Stage 5 school', input_source='simulated',
                    address='Synthetic colocated test location', latitude=6.9, longitude=79.9,
                    location_confirmed=True, morning_deadline_seconds=28800, afternoon_finish_seconds=46800))
            for id in vehicles:
                s.add(Vehicle(id=id, capacity=2, input_source='simulated',
                    start_address='Synthetic depot', start_latitude=6.9, start_longitude=79.9, start_confirmed=True,
                    end_address='Synthetic depot', end_latitude=6.9, end_longitude=79.9, end_confirmed=True))
            s.commit()
            def payload(school=0, vehicle=0, name='Synthetic Stage 5 student'):
                return StudentWrite(name=name, school_id=schools[school], vehicle_id=vehicles[vehicle],
                    home_address='Synthetic colocated home', home_latitude=6.9, home_longitude=79.9,
                    input_source='simulated', location_confirmed=True, location_method='manual')
            for vehicle in vehicles:
                for direction in ('morning', 'afternoon'):
                    generate_and_store(s, GenerateRouteRequest(vehicle_id=vehicle, direction=direction,
                        departure_seconds=21600 if direction == 'morning' else 46800,
                        pickup_service_seconds=0, delivery_service_seconds=0, solver_time_limit_seconds=1))
            def count():
                return s.scalar(select(func.count()).select_from(RouteVersion).where(RouteVersion.vehicle_id.in_(vehicles)))
            key = uuid4().hex
            added = create_student(payload(), s, key)
            student_id = added['id']
            self.assertEqual(added['routing']['outcome'], 'success', added['routing'])
            n = count()
            self.assertEqual(create_student(payload(), s, key)['routing']['event_id'], added['routing']['event_id'])
            for _ in range(2):
                latest_route(s, vehicles[0], 'morning'); plan_status(vehicles[0], 'morning', s)
            self.assertEqual(count(), n, 'Read/replay must never generate another route')
            unchanged = update_student(student_id, payload(), s, uuid4().hex)
            self.assertEqual(unchanged['routing']['outcome'], 'unchanged')
            self.assertEqual(count(), n)
            edited = update_student(student_id, payload(school=1), s, uuid4().hex)
            self.assertEqual(edited['routing']['outcome'], 'success')
            morning = latest_route(s, vehicles[0], 'morning')
            self.assertEqual([x['school_id'] for x in morning['stops'] if x['action'] == 'delivery'], [schools[1]])
            moved = transfer_student(student_id, StudentTransfer(vehicle_id=vehicles[1]), s, uuid4().hex)
            self.assertEqual(len(moved['routing']['plans']), 4)
            self.assertEqual(s.get(Student, student_id).vehicle_id, vehicles[1])
            self.assertEqual(latest_route(s, vehicles[0], 'morning')['feasibility_status'], 'empty')
            failed = school_schedule(schools[1], SchoolSchedule(morning_deadline_seconds=21000, afternoon_finish_seconds=46800), s, uuid4().hex)
            self.assertEqual(failed['save_status'], 'saved')
            self.assertEqual(failed['routing']['outcome'], 'failed')
            with Session(get_engine()) as reader:
                self.assertEqual(reader.get(School, schools[1]).morning_deadline_seconds, 21000)
                invalid = latest_route(reader, vehicles[1], 'morning')
                self.assertFalse(invalid['is_current'])
                self.assertIsNone(invalid['distance_metres'])
                self.assertTrue(invalid['errors'])
            school_schedule(schools[1], SchoolSchedule(morning_deadline_seconds=28800, afternoon_finish_seconds=46800), s, uuid4().hex)
            # A solver exception must not undo the student's successful edit.
            def fail_morning(vehicle, students, schools, settings, provider):
                if settings.direction == 'morning': raise RuntimeError('synthetic failure')
                return solve_registered_route(vehicle, students, schools, settings, provider)
            with patch('route_service.solve_registered_route', side_effect=fail_morning):
                broken = update_student(student_id, payload(school=1, vehicle=1, name='Synthetic saved despite failure'), s, uuid4().hex)
            self.assertEqual(broken['save_status'], 'saved')
            self.assertEqual(broken['routing']['outcome'], 'failed')
            self.assertFalse(latest_route(s, vehicles[1], 'morning')['is_current'])
            afternoon_version = latest_route(s, vehicles[1], 'afternoon')['version']
            recovered = retry_event(broken['routing']['event_id'], s)
            self.assertEqual(recovered['outcome'], 'success', recovered)
            self.assertEqual(latest_route(s, vehicles[1], 'afternoon')['version'], afternoon_version)
            self.assertFalse(next(p for p in recovered['plans'] if p['direction'] == 'afternoon')['generated'])
            n = count()
            retry_event(broken['routing']['event_id'], s)
            self.assertEqual(count(), n)
            deactivated = change_student_status(student_id, StudentStatus(active=False), s, uuid4().hex)
            self.assertEqual(deactivated['routing']['outcome'], 'success')
            self.assertEqual(latest_route(s, vehicles[1], 'morning')['stops'], [])
            change_student_status(student_id, StudentStatus(active=True), s, uuid4().hex)
            # Simulate process interruption after input/pending-state commit. The
            # session lock keeps the live recovery worker from winning this assertion.
            s.execute(text('SELECT pg_advisory_lock(73521, 5)'))
            try:
                with patch('planning_orchestration.process_event_safe', return_value={'outcome': 'failed'}):
                    pending = update_student(student_id, payload(school=1, vehicle=1, name='Synthetic durable recovery'), s, uuid4().hex)
                with Session(get_engine()) as reader:
                    state = plan_status(vehicles[1], 'morning', reader)
                    self.assertEqual(state['generation_status'], 'pending')
                    self.assertFalse(latest_route(reader, vehicles[1], 'morning')['is_current'])
                    self.assertEqual(reader.get(Student, student_id).name, 'Synthetic durable recovery')
                    event_id = state['trigger_event_id']
                self.assertEqual(process_event_safe(s, event_id)['outcome'], 'success')
                n = count()
                process_event_safe(s, event_id)
                self.assertEqual(count(), n)
            finally:
                s.execute(text('SELECT pg_advisory_unlock(73521, 5)'))
                s.commit()
            current = latest_route(s, vehicles[1], 'morning')
            stops_before = [x.details for x in s.scalars(select(RouteStop).where(RouteStop.route_id == current['route_id']).order_by(RouteStop.sequence))]
            lock_execution(current['route_id'], ExecutionLock(execution_status='active'), s)
            protected = update_student(student_id, payload(school=1, vehicle=1, name='Synthetic active trip edit'), s, uuid4().hex)
            self.assertIn('deferred_active', [p['generation_status'] for p in protected['routing']['plans']])
            with self.assertRaises(HTTPException) as raised:
                generate_and_store(s, GenerateRouteRequest(vehicle_id=vehicles[1], direction='morning', departure_seconds=21600))
            self.assertEqual(raised.exception.status_code, 409)
            s.rollback()
            lock_execution(current['route_id'], ExecutionLock(execution_status='completed'), s)
            removed = remove_student(student_id, s, uuid4().hex)
            self.assertIn('deferred_completed', [p['generation_status'] for p in removed['routing']['plans']])
            self.assertFalse(s.get(Student, student_id).active)
            self.assertEqual(stops_before, [x.details for x in s.scalars(select(RouteStop).where(RouteStop.route_id == current['route_id']).order_by(RouteStop.sequence))])
            print('Stage 5 verified synthetic fixtures:', ', '.join(vehicles), 'student', student_id)


if __name__ == '__main__': unittest.main()
