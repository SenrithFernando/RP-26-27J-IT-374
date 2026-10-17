"""Mandatory, per-student pickup/delivery on one fixed registered vehicle."""
from dataclasses import dataclass
from time import perf_counter
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from routing_domain import GenerationSettings, Location, RegisteredSchool, RegisteredStudent, RegisteredVehicle
from travel_time import Coordinate, InvalidTravelCosts, TravelCosts, TravelTimeProvider, validate_costs
from route_alternatives import compare_alternatives


@dataclass(frozen=True)
class Event:
    id: str
    location_id: str
    name: str
    action: str
    location: Location
    student_id: str | None = None
    school_id: str | None = None
    demand: int = 0
    service_seconds: int = 0
    earliest_seconds: int = 0
    latest_seconds: int = 172800


def failure(status, errors, metadata=None, runtime=None, solver_status="not_run"):
    return {"feasibility_status": status, "errors": errors, "stops": [],
            "distance_metres": None, "driving_seconds": None, "service_seconds": None,
            "waiting_seconds": None, "total_duration_seconds": None,
            "solver_runtime_seconds": runtime, "solver_status": solver_status,
            "provider_source": metadata, "optimality": "No global optimum is claimed."}


def solve_registered_route(vehicle: RegisteredVehicle, students: list[RegisteredStudent],
                           schools: dict[str, RegisteredSchool], settings: GenerationSettings,
                           provider: TravelTimeProvider):
    errors = []
    if settings.direction not in ("morning", "afternoon"):
        errors.append("Direction must be morning or afternoon.")
    if not 1 <= settings.solver_time_limit_seconds <= 10:
        errors.append("Solver time limit must be between 1 and 10 seconds.")
    if not 0 <= settings.departure_seconds < 86400 or not 1 <= settings.max_route_seconds <= 86400:
        errors.append("Invalid departure or route horizon in seconds.")
    if not 0 <= settings.pickup_service_seconds <= 3600 or not 0 <= settings.delivery_service_seconds <= 3600:
        errors.append("Service duration must be between 0 and 3600 seconds.")
    if vehicle.capacity <= 0:
        errors.append("Vehicle capacity must be positive.")
    if not vehicle.start.valid(): errors.append(f"Missing confirmed start coordinates for {vehicle.id}.")
    if not vehicle.end.valid(): errors.append(f"Missing confirmed end coordinates for {vehicle.id}.")
    if not students: errors.append("No active students assigned to this vehicle.")
    if len(students) > 200: errors.append("Roster exceeds this prototype's explicit 200-student generation limit; no students were dropped.")
    if len({student.id for student in students}) != len(students): errors.append("Duplicate student IDs in roster.")
    for student in students:
        if student.vehicle_id != vehicle.id: errors.append(f"Student {student.id} is not registered to vehicle {vehicle.id}.")
        if not student.home.valid(): errors.append(f"Missing confirmed home coordinates for {student.id}.")
        school = schools.get(student.school_id)
        if school is None:
            errors.append(f"School {student.school_id} is missing for {student.id}.")
        else:
            if not school.location.valid(): errors.append(f"Missing confirmed coordinates for school {school.id}.")
            bell = school.morning_deadline_seconds if settings.direction == "morning" else school.afternoon_finish_seconds
            if bell is None or not 0 <= bell < 86400:
                errors.append(f"Missing/invalid {settings.direction} schedule for school {school.id}.")
    if errors: return failure("invalid_input", sorted(set(errors)))

    horizon = settings.departure_seconds + settings.max_route_seconds
    events = [Event(f"{vehicle.id}:start", f"{vehicle.id}:start", f"{vehicle.id} start", "start", vehicle.start),
              Event(f"{vehicle.id}:end", f"{vehicle.id}:end", f"{vehicle.id} end", "end", vehicle.end)]
    pairs = []
    for student in sorted(students, key=lambda item: item.id):
        school = schools[student.school_id]
        if settings.direction == "morning":
            pickup_location, delivery_location = student.home, school.location
            pickup_id, delivery_id = student.home_id, school.id
            earliest, latest = settings.departure_seconds, school.morning_deadline_seconds
        else:
            pickup_location, delivery_location = school.location, student.home
            pickup_id, delivery_id = school.id, student.home_id
            earliest, latest = school.afternoon_finish_seconds, horizon
        pickup = len(events)
        events.append(Event(f"{student.id}:pickup", pickup_id, f"Pickup {student.name}", "pickup", pickup_location,
                            student.id, school.id, 1, settings.pickup_service_seconds, max(settings.departure_seconds, earliest), horizon))
        delivery = len(events)
        events.append(Event(f"{student.id}:delivery", delivery_id, f"Deliver {student.name}", "delivery", delivery_location,
                            student.id, school.id, -1, settings.delivery_service_seconds, settings.departure_seconds, min(horizon, latest)))
        pairs.append((pickup, delivery))
    for event in events[2:]:
        if event.earliest_seconds > event.latest_seconds:
            return failure("infeasible", [f"Time window for {event.id} at school {event.school_id} cannot be met: earliest allowed {event.earliest_seconds} s exceeds latest allowed {event.latest_seconds} s (departure {settings.departure_seconds} s, route horizon {horizon} s)."], solver_status="infeasible_time_window")
    costs = None
    try:
        # Every cost is fetched and validated BEFORE constructing OR-Tools callbacks.
        costs = provider.precompute([Coordinate(event.location.latitude, event.location.longitude, event.location_id) for event in events],
                                    settings.direction, settings.departure_seconds)
        if isinstance(costs, TravelCosts) and isinstance(costs.metadata, dict) and costs.metadata.get('has_unavailable_pairs'):
            raise InvalidTravelCosts('Some directed pairs have no permitted travel estimate; generation rejected.')
        validate_costs(costs, len(events))
    except InvalidTravelCosts as error:
        metadata = costs.metadata if isinstance(costs, TravelCosts) else None
        unavailable = metadata and metadata.get('has_unavailable_pairs')
        message = str(error) + (' ' + ' '.join(metadata.get('fallback_reasons', [])) if unavailable else '')
        return failure('unavailable' if unavailable else "invalid_provider_input", [message], metadata)

    manager = pywrapcp.RoutingIndexManager(len(events), 1, [0], [1])
    routing = pywrapcp.RoutingModel(manager)
    def transit(from_index, to_index):
        origin, destination = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return events[origin].service_seconds + costs.duration_seconds[origin][destination]
    transit_index = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)
    routing.AddDimension(transit_index, settings.max_route_seconds, horizon, False, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")
    time_dimension.CumulVar(routing.Start(0)).SetValue(settings.departure_seconds)
    time_dimension.CumulVar(routing.End(0)).SetRange(settings.departure_seconds, horizon)
    for node in range(2, len(events)):
        time_dimension.CumulVar(manager.NodeToIndex(node)).SetRange(events[node].earliest_seconds, events[node].latest_seconds)
    time_dimension.SetGlobalSpanCostCoefficient(1)

    demand_index = routing.RegisterUnaryTransitCallback(lambda index: events[manager.IndexToNode(index)].demand)
    routing.AddDimensionWithVehicleCapacity(demand_index, 0, [vehicle.capacity], True, "Load")
    load_dimension = routing.GetDimensionOrDie("Load")
    load_dimension.CumulVar(routing.End(0)).SetValue(0)
    # Rank uses a unit increment; time alone cannot order colocated zero-time actions.
    routing.AddConstantDimension(1, len(events) + 1, True, "Order")
    order_dimension = routing.GetDimensionOrDie("Order")
    solver = routing.solver()
    for pickup, delivery in pairs:
        pickup_index, delivery_index = manager.NodeToIndex(pickup), manager.NodeToIndex(delivery)
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        routing.VehicleVar(pickup_index).SetValue(0)
        routing.VehicleVar(delivery_index).SetValue(0)
        solver.Add(routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index))
        solver.Add(order_dimension.CumulVar(pickup_index) + 1 <= order_dimension.CumulVar(delivery_index))
        solver.Add(time_dimension.CumulVar(pickup_index) <= time_dimension.CumulVar(delivery_index))
    # Minimize schedule slack as well as driving; no global-optimality claim.
    for index in range(routing.Size()):
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(index))
    routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.End(0)))
    parameters = pywrapcp.DefaultRoutingSearchParameters()
    parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parameters.time_limit.seconds = settings.solver_time_limit_seconds
    started = perf_counter()
    solution = routing.SolveWithParameters(parameters)
    runtime = round(perf_counter() - started, 6)
    status = routing.status()
    status_names = {0: "not_solved", 1: "success", 2: "partial_success", 3: "no_solution_found", 4: "timeout", 5: "invalid_model", 6: "infeasible", 7: "optimal_solver_status"}
    status_name = status_names.get(status, f"status_{status}")
    if solution is None:
        feasibility = "infeasible" if status == 6 else "timeout" if status == 4 else "no_solution_found"
        return failure(feasibility, ["No feasible route returned within the configured constraints and search limit. Students were not reassigned or dropped.",
                       f"Required: {len(students)} active students on {vehicle.id}, capacity {vehicle.capacity}; departure {settings.departure_seconds} s, maximum duration {settings.max_route_seconds} s; per-action service {settings.pickup_service_seconds}/{settings.delivery_service_seconds} s.",
                       "School constraints: " + "; ".join(f"{school.id}: {'morning delivery by' if settings.direction == 'morning' else 'afternoon pickup from'} {school.morning_deadline_seconds if settings.direction == 'morning' else school.afternoon_finish_seconds} s" for school in schools.values())],
                       costs.metadata, runtime, status_name)
    stops = []
    index = routing.Start(0)
    load, driving, service, waiting, distance = 0, 0, 0, 0, 0
    previous_node, previous_departure = None, settings.departure_seconds
    while True:
        node = manager.IndexToNode(index)
        event = events[node]
        drive = 0 if previous_node is None else costs.duration_seconds[previous_node][node]
        leg_distance = 0 if previous_node is None else costs.distance_metres[previous_node][node]
        physical_arrival = previous_departure + drive
        service_start = solution.Value(time_dimension.CumulVar(index))
        wait = service_start - physical_arrival
        before = load
        load += event.demand
        stop = {"sequence": len(stops) + 1, "event_id": event.id, "location_id": event.location_id,
                "name": event.name, "action": event.action, "student_id": event.student_id, "school_id": event.school_id,
                "latitude": event.location.latitude, "longitude": event.location.longitude, "address": event.location.address,
                "input_source": event.location.input_source, "location_method": event.location.location_method,
                "arrival_seconds": physical_arrival, "eta_seconds": service_start, "departure_seconds": service_start + event.service_seconds,
                "driving_seconds_from_previous": drive, "distance_metres_from_previous": leg_distance,
                "service_seconds": event.service_seconds, "waiting_seconds": wait, "load_before": before, "load_after": load}
        stop['travel_source'] = ({'source': 'start', 'fallback_reason': None} if previous_node is None else
            costs.leg_sources[previous_node][node] if costs.leg_sources else
            {'source': costs.metadata['duration_source'], 'distance_source': costs.metadata['distance_source'], 'fallback_reason': None})
        stops.append(stop)
        driving += drive; distance += leg_distance; service += event.service_seconds; waiting += wait
        previous_node, previous_departure = node, stop["departure_seconds"]
        if routing.IsEnd(index): break
        index = solution.Value(routing.NextVar(index))
    result = {"feasibility_status": "feasible", "errors": [], "stops": stops,
              "distance_metres": distance, "driving_seconds": driving, "service_seconds": service,
              "waiting_seconds": waiting, "total_duration_seconds": previous_departure - settings.departure_seconds,
              "solver_runtime_seconds": runtime, "solver_status": status_name, "provider_source": costs.metadata,
              "optimality": "Feasible heuristic solution; no proven global optimum is claimed.",
              "objective": "Minimize driving-plus-service arc cost and elapsed route duration, in seconds."}
    validate_solution(result, vehicle, students, schools, settings)
    from collections import Counter
    counts = Counter(s['travel_source']['source'] for s in stops if s['travel_source']['source'] not in ('start','geographic_zero'))
    sources = list(counts)
    actual = sources[0] if len(sources) == 1 else 'mixed' if sources else 'geographic_zero'
    result['provider_source'] = {**costs.metadata, 'matrix_duration_source': costs.metadata['duration_source'],
        'duration_source': actual, 'route_source_counts': dict(counts),
        'route_is_mixed': len(sources) > 1,
        'route_fallback_reasons': sorted({s['travel_source']['fallback_reason'] for s in stops if s['travel_source'].get('fallback_reason')})}
    distance_sources = {s['travel_source'].get('distance_source', costs.metadata['distance_source']) for s in stops if s['travel_source']['source'] not in ('start','geographic_zero')}
    result['provider_source']['matrix_distance_source'] = costs.metadata['distance_source']
    if distance_sources:
        result['provider_source']['distance_source'] = next(iter(distance_sources)) if len(distance_sources) == 1 else 'mixed'
        result['provider_source']['distance_is_approximate'] = distance_sources != {'google_road_network'}
    if costs.leg_sources:
        result['provider_source']['provider'] = {'ml_prediction': 'xgboost_synthetic_v1', 'simulation': 'deterministic_simulation_v1', 'google_live': 'google_routes', 'historical_baseline': 'historical_baseline'}.get(actual, actual)
    result['alternative_comparison'] = compare_alternatives(result, events, costs, settings, vehicle, students, schools, getattr(provider, 'reference_stops', None), validate_solution)
    return result


def validate_solution(result, vehicle, students, schools, settings):
    """Independent audit before any route can be persisted as feasible."""
    roster = {student.id: student for student in students}
    pickups, deliveries, load = {}, {}, 0
    stops = result["stops"]
    if len(stops) != 2 * len(students) + 2 or stops[0]["action"] != "start" or stops[-1]["action"] != "end":
        raise RuntimeError("Route coverage/start/end validation failed.")
    for expected, stop in enumerate(stops, 1):
        if stop["sequence"] != expected or stop["load_before"] != load or stop["waiting_seconds"] < 0:
            raise RuntimeError("Route sequence/time/load validation failed.")
        sid, action = stop["student_id"], stop["action"]
        if action in ("pickup", "delivery"):
            if sid not in roster or roster[sid].vehicle_id != vehicle.id: raise RuntimeError("Unregistered student in route.")
            student = roster[sid]; school = schools[student.school_id]
            at_home = (settings.direction == "morning" and action == "pickup") or (settings.direction == "afternoon" and action == "delivery")
            expected_id, expected_location = (student.home_id, student.home) if at_home else (school.id, school.location)
            if stop["school_id"] != school.id or stop["location_id"] != expected_id or (stop["latitude"], stop["longitude"]) != (expected_location.latitude, expected_location.longitude):
                raise RuntimeError("Wrong pickup/delivery destination.")
            if action == "pickup":
                if sid in pickups: raise RuntimeError("Duplicate pickup.")
                pickups[sid] = expected; load += 1
                if settings.direction == "afternoon" and stop["eta_seconds"] < school.afternoon_finish_seconds: raise RuntimeError("Pickup before school finish.")
            else:
                if sid not in pickups or pickups[sid] >= expected or sid in deliveries: raise RuntimeError("Pickup precedence violated.")
                deliveries[sid] = expected; load -= 1
                if settings.direction == "morning" and stop["eta_seconds"] > school.morning_deadline_seconds: raise RuntimeError("Morning deadline violated.")
        elif action not in ("start", "end") or sid is not None or expected not in (1, len(stops)):
            raise RuntimeError("Invalid endpoint/action.")
        if not 0 <= load <= vehicle.capacity or stop["load_after"] != load: raise RuntimeError("Vehicle load outside capacity.")
        if stop["eta_seconds"] != stop["arrival_seconds"] + stop["waiting_seconds"] or stop["departure_seconds"] != stop["eta_seconds"] + stop["service_seconds"]:
            raise RuntimeError("Stop time accounting failed.")
        if expected > 1:
            previous = stops[expected - 2]
            if stop["arrival_seconds"] != previous["departure_seconds"] + stop["driving_seconds_from_previous"]:
                raise RuntimeError("Leg time accounting failed.")
    if set(pickups) != set(roster) or set(deliveries) != set(roster) or load != 0: raise RuntimeError("Student coverage failed.")
    if stops[0]["eta_seconds"] != settings.departure_seconds: raise RuntimeError("Incorrect departure.")
    for stop, endpoint in ((stops[0], vehicle.start), (stops[-1], vehicle.end)):
        if (stop["latitude"], stop["longitude"]) != (endpoint.latitude, endpoint.longitude): raise RuntimeError("Wrong vehicle endpoint.")
    totals = {"driving_seconds": "driving_seconds_from_previous", "service_seconds": "service_seconds", "waiting_seconds": "waiting_seconds", "distance_metres": "distance_metres_from_previous"}
    for total, field in totals.items():
        if result[total] != sum(stop[field] for stop in stops): raise RuntimeError("Route totals do not match stops.")
    if result["total_duration_seconds"] != result["driving_seconds"] + result["service_seconds"] + result["waiting_seconds"] or result["total_duration_seconds"] > settings.max_route_seconds:
        raise RuntimeError("Route duration accounting failed.")
