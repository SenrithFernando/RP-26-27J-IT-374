"""Pure solver checks; all input coordinates, schedules and provider costs are synthetic."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from route_schemas import GenerateRouteRequest
from routing_domain import GenerationSettings, Location, RegisteredSchool, RegisteredStudent, RegisteredVehicle
from route_solver import solve_registered_route, validate_solution
from travel_time import DeterministicSimulationProvider, InvalidTravelCosts, TravelCosts, validate_costs


def fixture(colocated=False):
    start = Location(6.90, 79.80, True, "Synthetic start")
    second = start if colocated else Location(6.905, 79.805, True, "Synthetic school B")
    schools = {
        "A": RegisteredSchool("A", "School A", start, 28800, 46800),
        "B": RegisteredSchool("B", "School B", second, 30600, 48600),
    }
    vehicle = RegisteredVehicle("FIXED", 1, start, start)
    students = [RegisteredStudent(f"S{i}", f"Student {i}", f"H{i}",
                 start if colocated else Location(6.901 + i * .0001, 79.801 + i * .0001, True, "Synthetic home"),
                 "A" if i % 2 == 0 else "B", vehicle.id) for i in range(4)]
    return vehicle, students, schools


class CountingProvider(DeterministicSimulationProvider):
    def __init__(self):
        super().__init__(); self.calls = []
    def precompute(self, coordinates, direction, departure_seconds):
        self.calls.append((len(coordinates), direction, departure_seconds))
        return super().precompute(coordinates, direction, departure_seconds)


class DualRouteTests(unittest.TestCase):
    def test_multi_school_roster_exceeds_capacity_and_both_directions_serve_every_student(self):
        vehicle, students, schools = fixture()
        provider = CountingProvider()
        for direction, departure in (("morning", 21600), ("afternoon", 45000)):
            settings = GenerationSettings(direction, departure, 20, 25, 21600, 1)
            result = solve_registered_route(vehicle, students, schools, settings, provider)
            self.assertEqual(result["feasibility_status"], "feasible")
            validate_solution(result, vehicle, students, schools, settings)
            self.assertGreater(len(students), vehicle.capacity)
            for student in students:
                events = [stop for stop in result["stops"] if stop["student_id"] == student.id]
                self.assertEqual([event["action"] for event in events], ["pickup", "delivery"])
                self.assertLess(events[0]["sequence"], events[1]["sequence"])
                self.assertEqual(events[0]["location_id"], student.home_id if direction == "morning" else student.school_id)
                self.assertEqual(events[1]["location_id"], student.school_id if direction == "morning" else student.home_id)
            self.assertTrue(all(0 <= stop["load_after"] <= vehicle.capacity for stop in result["stops"]))
            self.assertEqual(result["service_seconds"], len(students) * 45)
            self.assertEqual(result["total_duration_seconds"], result["driving_seconds"] + result["service_seconds"] + result["waiting_seconds"])
            if direction == "afternoon": self.assertGreater(result["waiting_seconds"], 0)
        # Independent dynamic matrices; no provider calls occur inside callbacks.
        self.assertEqual([call[1] for call in provider.calls], ["morning", "afternoon"])
        self.assertEqual([call[0] for call in provider.calls], [2 + 2 * len(students)] * 2)

    def test_strict_precedence_with_colocated_zero_time_actions(self):
        vehicle, students, schools = fixture(colocated=True)
        schools = {key: replace(value, afternoon_finish_seconds=0) for key, value in schools.items()}
        settings = GenerationSettings("morning", 21600, 0, 0, 21600, 1)
        result = solve_registered_route(vehicle, students, schools, settings, CountingProvider())
        self.assertEqual(result["feasibility_status"], "feasible")
        self.assertEqual(result["total_duration_seconds"], 0)
        for student in students:
            actions = [stop for stop in result["stops"] if stop["student_id"] == student.id]
            self.assertEqual(actions[0]["eta_seconds"], actions[1]["eta_seconds"])
            self.assertLess(actions[0]["sequence"], actions[1]["sequence"])
            self.assertEqual([stop["action"] for stop in actions], ["pickup", "delivery"])

    def test_impossible_deadline_cannot_drop_or_move_students(self):
        vehicle, students, schools = fixture()
        schools = {key: replace(value, morning_deadline_seconds=21000) for key, value in schools.items()}
        result = solve_registered_route(vehicle, students, schools, GenerationSettings("morning", 21600), CountingProvider())
        self.assertEqual(result["feasibility_status"], "infeasible")
        self.assertEqual(result["stops"], [])
        self.assertIsNone(result["total_duration_seconds"])
        self.assertTrue(all(student.vehicle_id == "FIXED" for student in students))

    def test_travel_time_can_make_a_nonempty_window_impossible(self):
        vehicle, students, schools = fixture()
        schools = {key: replace(value, morning_deadline_seconds=21601) for key, value in schools.items()}
        result = solve_registered_route(vehicle, students, schools, GenerationSettings("morning", 21600, 30, 30, 21600, 1), CountingProvider())
        self.assertNotEqual(result["feasibility_status"], "feasible")
        self.assertFalse(result["stops"])
        self.assertIsNone(result["distance_metres"])

    def test_missing_coordinates_schedules_and_wrong_assignments_rejected_before_costs(self):
        vehicle, students, schools = fixture()
        cases = [
            (replace(vehicle, start=replace(vehicle.start, confirmed=False)), students, schools),
            (vehicle, [replace(students[0], home=Location(None, None, False)), *students[1:]], schools),
            (vehicle, students, {**schools, "A": replace(schools["A"], location=Location(None, None, False))}),
            (vehicle, students, {**schools, "A": replace(schools["A"], morning_deadline_seconds=None)}),
            (vehicle, [replace(students[0], vehicle_id="OTHER"), *students[1:]], schools),
        ]
        for v, roster, school_map in cases:
            with self.subTest(roster=roster[0].id):
                provider = CountingProvider()
                result = solve_registered_route(v, roster, school_map, GenerationSettings("morning", 21600), provider)
                self.assertEqual(result["feasibility_status"], "invalid_input")
                self.assertIsNone(result["solver_runtime_seconds"])
                self.assertFalse(provider.calls)

    def test_unreachable_pair_rejected_before_model_construction(self):
        vehicle, students, schools = fixture()
        class Unreachable(CountingProvider):
            def precompute(self, *args):
                costs = super().precompute(*args)
                costs.duration_seconds[0][2] = None
                return costs
        with patch("route_solver.pywrapcp.RoutingModel", side_effect=AssertionError("Model must not be constructed")):
            result = solve_registered_route(vehicle, students, schools, GenerationSettings("morning", 21600), Unreachable())
        self.assertEqual(result["feasibility_status"], "invalid_provider_input")
        self.assertIn("Unreachable", result["errors"][0])

    def test_postsolve_audit_rejects_wrong_destination_and_load(self):
        vehicle, students, schools = fixture(colocated=True)
        settings = GenerationSettings("morning", 21600, 0, 0, 21600, 1)
        original = solve_registered_route(vehicle, students, schools, settings, CountingProvider())
        for change in ({"location_id": "WRONG_SCHOOL"}, {"load_after": 999}, {"student_id": "UNREGISTERED"}):
            result = deepcopy(original)
            result["stops"][1].update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                validate_solution(result, vehicle, students, schools, settings)

    def test_provider_shapes_numeric_costs_and_solver_bound(self):
        metadata = dict(provider="test", duration_source="simulation", distance_source="synthetic", distance_is_approximate=True)
        for matrix in (None, [None, None], [[0]], [[0, -1], [1, 0]], [[0, True], [1, 0]], [[0, None], [1, 0]]):
            with self.subTest(matrix=matrix), self.assertRaises(InvalidTravelCosts):
                validate_costs(TravelCosts(matrix, [[0, 1], [1, 0]], metadata), 2)
        with self.assertRaises(InvalidTravelCosts):
            validate_costs(TravelCosts([[0, 1], [1, 0]], [[0, 1], [1, 0]], {**metadata, "distance_is_approximate": "yes"}), 2)
        with self.assertRaises(ValidationError):
            GenerateRouteRequest(vehicle_id="FIXED", direction="morning", departure_seconds=21600, solver_time_limit_seconds=11)


if __name__ == "__main__": unittest.main()
