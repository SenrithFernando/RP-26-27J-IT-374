"""Explicit opt-in integration checks against the configured PostgreSQL database."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database import get_engine
from models import RouteStop, Student
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store, latest_route
from seed_routing_demo import seed_demo


@unittest.skipUnless(os.getenv("SAFERIDE_RUN_DB_TESTS") == "1", "Set SAFERIDE_RUN_DB_TESTS=1 to exercise PostgreSQL with isolated synthetic fixtures.")
class RouteStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefix = "PP1_" + uuid4().hex[:10]
        seed_demo(cls.prefix)

    def test_persistent_versions_both_vehicles_both_directions_and_read_only_latest(self):
        with Session(get_engine()) as session:
            before = dict(session.execute(select(Student.id, Student.vehicle_id).where(Student.id.startswith(self.prefix + "_STUDENT_"))).all())
            for vehicle in (self.prefix + "_VAN_A", self.prefix + "_VAN_B"):
                for direction, departure in (("morning", 21600), ("afternoon", 45000)):
                    result = generate_and_store(session, GenerateRouteRequest(vehicle_id=vehicle, direction=direction, departure_seconds=departure, solver_time_limit_seconds=1))
                    self.assertEqual(result["feasibility_status"], "feasible", result["errors"])
                    roster = {student_id for student_id, assigned in before.items() if assigned == vehicle}
                    self.assertEqual(len(roster), result["student_count"])
                    self.assertGreater(len(roster), result["capacity"])
                    self.assertEqual({stop["student_id"] for stop in result["stops"] if stop["action"] == "pickup"}, roster)
                    self.assertEqual({stop["student_id"] for stop in result["stops"] if stop["action"] == "delivery"}, roster)
                    self.assertEqual(session.scalar(select(func.count()).select_from(RouteStop).where(RouteStop.route_id == result["route_id"])), 2 * len(roster) + 2)
                    # New DB session plus disabled solver/provider proves latest is retrieval only.
                    with Session(get_engine()) as reader, patch("route_service.solve_registered_route", side_effect=AssertionError("Latest cannot solve")), patch("travel_time.DeterministicSimulationProvider.precompute", side_effect=AssertionError("Latest cannot fetch costs")):
                        self.assertEqual(latest_route(reader, vehicle, direction), result)
                    print(f"Verified {vehicle} {direction} version {result['version']}: {result['route_id']}")
            failed = generate_and_store(session, GenerateRouteRequest(vehicle_id=self.prefix + "_VAN_A", direction="morning", departure_seconds=82800, solver_time_limit_seconds=1))
            self.assertEqual(failed["feasibility_status"], "infeasible")
            self.assertEqual(failed["stops"], [])
            self.assertIsNone(failed["distance_metres"])
            self.assertEqual(latest_route(session, self.prefix + "_VAN_A", "morning")["route_id"], failed["route_id"])
            restored = generate_and_store(session, GenerateRouteRequest(vehicle_id=self.prefix + "_VAN_A", direction="morning", departure_seconds=21600, solver_time_limit_seconds=1))
            self.assertEqual(restored["version"], failed["version"] + 1)
            self.assertEqual(restored["feasibility_status"], "feasible")
            after = dict(session.execute(select(Student.id, Student.vehicle_id).where(Student.id.startswith(self.prefix + "_STUDENT_"))).all())
            self.assertEqual(before, after)


if __name__ == "__main__": unittest.main()
