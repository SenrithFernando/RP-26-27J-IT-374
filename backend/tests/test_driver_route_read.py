from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from route_service import serialize_version


class DriverRouteReadTests(TestCase):
    def test_names_are_read_from_generation_snapshot_without_mutation_or_solving(self):
        details = {'event_id': 'S:pickup', 'name': 'Pickup snapshot student', 'school_id': 'SCHOOL'}
        stop = SimpleNamespace(student_id='S', details=details)
        session = Mock(); session.scalars.return_value.all.return_value = [stop]
        version = SimpleNamespace(id='ROUTE_TEST', vehicle_id='VEHICLE', direction='morning', version=1,
            result={}, service_date=date(2026,10,16), departure_seconds=21600,
            created_at=datetime(2026,10,16,tzinfo=timezone.utc), request_settings={},
            input_snapshot={'students':[{'id':'S','name':'Snapshot student'}],
                            'schools':{'SCHOOL':{'name':'Snapshot school'}}})
        with patch('route_service.freshness',return_value={}), patch('route_service.solve_registered_route',side_effect=AssertionError('GET must not optimize')):
            result = serialize_version(session, version)
        self.assertEqual(result['stops'][0]['student_name'],'Snapshot student')
        self.assertEqual(result['stops'][0]['school_name'],'Snapshot school')
        self.assertNotIn('student_name',details)
        session.commit.assert_not_called(); session.add.assert_not_called()

    def test_past_service_date_is_stale_but_future_plan_remains_current(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        from planning_state import freshness
        today = datetime.now(ZoneInfo("Asia/Colombo")).date()
        session = Mock()
        session.get.side_effect = lambda model, key: SimpleNamespace(roster_version=1) if model.__name__ == "Vehicle" else None
        route = SimpleNamespace(vehicle_id="isolated", direction="morning", roster_version=1,
            service_date=today-timedelta(days=1), feasibility_status="feasible", execution_status="pre_trip",
            trigger_event_id=None, trigger_event_type="test")
        self.assertFalse(freshness(session, route)["is_current"])
        self.assertEqual(freshness(session, route)["planning_status"], "stale")
        for service_date in (today, today+timedelta(days=1)):
            route.service_date=service_date
            self.assertTrue(freshness(session, route)["is_current"])
