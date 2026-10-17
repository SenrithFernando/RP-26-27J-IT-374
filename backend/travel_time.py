from dataclasses import dataclass
from math import asin, ceil, cos, isfinite, radians, sin, sqrt
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float
    location_id: str | None = None


@dataclass(frozen=True)
class TravelCosts:
    duration_seconds: list[list[int | None]]
    distance_metres: list[list[int | None]]
    metadata: dict
    leg_sources: list[list[dict]] | None = None


class TravelTimeProvider(Protocol):
    def precompute(self, coordinates: Sequence[Coordinate], direction: str, departure_seconds: int) -> TravelCosts: ...


class InvalidTravelCosts(ValueError):
    pass


def validate_costs(costs: TravelCosts, count: int) -> None:
    """Reject missing/unreachable arcs, malformed shapes and invalid numeric costs."""
    if not isinstance(costs, TravelCosts):
        raise InvalidTravelCosts("Provider must return TravelCosts.")
    if costs.leg_sources is not None:
        if len(costs.leg_sources) != count or any(len(row) != count for row in costs.leg_sources):
            raise InvalidTravelCosts('Invalid per-leg source matrix shape.')
        if any(not isinstance(item, dict) or not item.get('source') for row in costs.leg_sources for item in row):
            raise InvalidTravelCosts('Incomplete per-leg source metadata.')
    for name, matrix in (("duration_seconds", costs.duration_seconds), ("distance_metres", costs.distance_metres)):
        if not isinstance(matrix, (list, tuple)) or len(matrix) != count or any(not isinstance(row, (list, tuple)) or len(row) != count for row in matrix):
            raise InvalidTravelCosts(f"Provider {name} matrix has the wrong shape.")
        for i, row in enumerate(matrix):
            for j, value in enumerate(row):
                if value is None:
                    raise InvalidTravelCosts(f"Unreachable pair {i} -> {j}; generation rejected.")
                if type(value) is not int or value < 0 or value > 1_000_000_000:
                    raise InvalidTravelCosts(f"Invalid {name} cost at {i} -> {j}.")
                if i == j and value != 0:
                    raise InvalidTravelCosts(f"Nonzero diagonal in {name}.")
    required = ("provider", "duration_source", "distance_source", "distance_is_approximate")
    if not isinstance(costs.metadata, dict) or any(key not in costs.metadata for key in required):
        raise InvalidTravelCosts("Provider provenance is incomplete.")
    if not all(isinstance(costs.metadata[key], str) and costs.metadata[key].strip() for key in required[:3]) or type(costs.metadata["distance_is_approximate"]) is not bool:
        raise InvalidTravelCosts("Provider provenance has invalid types.")


class DeterministicSimulationProvider:
    """Straight-line metres / configured speed; no road or live traffic claims."""
    def __init__(self, morning_speed_mps: float = 6.0, afternoon_speed_mps: float = 5.0):
        for speed in (morning_speed_mps, afternoon_speed_mps):
            if not isfinite(speed) or not 0.01 <= speed <= 50:
                raise ValueError("Simulation speeds must be finite and between 0.01 and 50 metres/second.")
        self.speeds = {"morning": morning_speed_mps, "afternoon": afternoon_speed_mps}

    def precompute(self, coordinates: Sequence[Coordinate], direction: str, departure_seconds: int) -> TravelCosts:
        if direction not in self.speeds:
            raise InvalidTravelCosts("Unknown direction.")
        for coordinate in coordinates:
            if not (isfinite(coordinate.latitude) and isfinite(coordinate.longitude)
                    and -90 <= coordinate.latitude <= 90 and -180 <= coordinate.longitude <= 180):
                raise InvalidTravelCosts("Provider received invalid coordinates.")
        distances = []
        durations = []
        speed = self.speeds[direction]
        for origin in coordinates:
            distance_row, duration_row = [], []
            for destination in coordinates:
                lat1, lat2 = radians(origin.latitude), radians(destination.latitude)
                dlat, dlon = lat2 - lat1, radians(destination.longitude - origin.longitude)
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                distance = round(6_371_000 * 2 * asin(sqrt(min(1.0, max(0.0, a)))))
                distance_row.append(distance)
                duration_row.append(ceil(distance / speed))
            distances.append(distance_row)
            durations.append(duration_row)
        return TravelCosts(durations, distances, {
            "provider": "deterministic_simulation_v1", "duration_source": "simulation",
            "distance_source": "haversine_straight_line", "distance_is_approximate": True,
            "speed_metres_per_second": speed, "direction": direction,
            "departure_seconds": departure_seconds,
            "description": "Approximate straight-line distances and simulated durations; no roads or live traffic.",
        })
