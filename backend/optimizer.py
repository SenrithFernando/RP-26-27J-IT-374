from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2

from sample_data import (
    LOCATIONS,
    STUDENTS,
    VEHICLE,
    MORNING_MATRIX,
    AFTERNOON_MATRIX,
)


def generate_route(direction: str):
    # This first example has one vehicle and one school.
    # All students are onboard together during part of the trip.
    if len(STUDENTS) > VEHICLE["capacity"]:
        raise ValueError("Student count exceeds vehicle capacity")

    if direction == "morning":
        matrix = MORNING_MATRIX
        start_node = 0
        end_node = 4
    elif direction == "afternoon":
        matrix = AFTERNOON_MATRIX
        start_node = 4
        end_node = 0
    else:
        raise ValueError("Direction must be morning or afternoon")

    manager = pywrapcp.RoutingIndexManager(
        len(LOCATIONS),
        1,
        [start_node],
        [end_node],
    )

    routing = pywrapcp.RoutingModel(manager)

    def travel_time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return matrix[from_node][to_node]

    callback_index = routing.RegisterTransitCallback(
        travel_time_callback
    )

    routing.SetArcCostEvaluatorOfAllVehicles(callback_index)

    parameters = pywrapcp.DefaultRoutingSearchParameters()

    parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    parameters.time_limit.seconds = 1

    solution = routing.SolveWithParameters(parameters)

    if solution is None:
        raise ValueError("No feasible route was found")

    stops = []
    total_seconds = 0
    index = routing.Start(0)

    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)

        stops.append({
            "sequence": len(stops) + 1,
            "location_id": LOCATIONS[node]["id"],
            "name": LOCATIONS[node]["name"],
        })

        next_index = solution.Value(routing.NextVar(index))
        next_node = manager.IndexToNode(next_index)

        total_seconds += matrix[node][next_node]
        index = next_index

    final_node = manager.IndexToNode(index)

    stops.append({
        "sequence": len(stops) + 1,
        "location_id": LOCATIONS[final_node]["id"],
        "name": LOCATIONS[final_node]["name"],
    })

    return {
        "vehicle_id": VEHICLE["id"],
        "direction": direction,
        "student_count": len(STUDENTS),
        "capacity": VEHICLE["capacity"],
        "travel_time_source": "simulation",
        "estimated_driving_time_seconds": total_seconds,
        "estimated_driving_time_minutes": round(
            total_seconds / 60, 2
        ),
        "stops": stops,
    }