from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Location:
    latitude: float | None
    longitude: float | None
    confirmed: bool
    address: str = ""
    input_source: str = "simulated"
    location_method: str = "manual"

    def valid(self):
        return (self.confirmed and self.latitude is not None and self.longitude is not None
                and isfinite(self.latitude) and isfinite(self.longitude)
                and -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180)


@dataclass(frozen=True)
class RegisteredVehicle:
    id: str
    capacity: int
    start: Location
    end: Location


@dataclass(frozen=True)
class RegisteredSchool:
    id: str
    name: str
    location: Location
    morning_deadline_seconds: int | None
    afternoon_finish_seconds: int | None


@dataclass(frozen=True)
class RegisteredStudent:
    id: str
    name: str
    home_id: str
    home: Location
    school_id: str
    vehicle_id: str


@dataclass(frozen=True)
class GenerationSettings:
    direction: str
    departure_seconds: int
    pickup_service_seconds: int = 30
    delivery_service_seconds: int = 30
    max_route_seconds: int = 21600
    solver_time_limit_seconds: int = 2
