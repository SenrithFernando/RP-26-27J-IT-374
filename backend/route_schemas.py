from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Direction = Literal["morning", "afternoon"]


class GenerateRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    vehicle_id: str = Field(min_length=1, max_length=64)
    direction: Direction
    service_date: date = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Colombo")).date())
    departure_seconds: int = Field(ge=0, lt=86400, strict=True)
    pickup_service_seconds: int = Field(default=30, ge=0, le=3600, strict=True)
    delivery_service_seconds: int = Field(default=30, ge=0, le=3600, strict=True)
    max_route_seconds: int = Field(default=21600, ge=1, le=86400, strict=True)
    solver_time_limit_seconds: int = Field(default=2, ge=1, le=10, strict=True)
    provider: Literal["simulation", "ml", "google", "baseline", "unavailable"] = "simulation"
    traffic_scenario: Literal['normal', 'northbound_delay', 'directed_incident'] = 'normal'
    fallback_policy: Literal['none', 'ml', 'ml_then_baseline'] = 'ml'
    force_live_failure: bool = Field(default=False, strict=True)
    include_geometry: bool = Field(default=True, strict=True)
    weather_flag: Literal[0, 1] | None = None
    simulation_speed_mps: float | None = Field(default=None, ge=0.01, le=50, allow_inf_nan=False)

    @field_validator('weather_flag', mode='before')
    @classmethod
    def weather_values(cls, value):
        if value is not None and (type(value) is not int or value not in (0, 1)):
            raise ValueError('Weather must be integer 0, integer 1 or null.')
        return value

    @model_validator(mode='after')
    def distinct_provider_settings(self):
        if self.provider != 'simulation' and self.simulation_speed_mps is not None:
            raise ValueError('simulation_speed_mps must be null except for simulation.')
        if self.provider != 'simulation' and self.traffic_scenario != 'normal':
            raise ValueError('Synthetic traffic scenarios apply only to the simulation provider; they are not ML features or Google traffic.')
        if self.provider != 'google' and self.force_live_failure:
            raise ValueError('Forced live failure applies only to Google.')
        return self


class SchoolSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    morning_deadline_seconds: int = Field(ge=0, lt=86400, strict=True)
    afternoon_finish_seconds: int = Field(ge=0, lt=86400, strict=True)


class GeneratedRouteResponse(BaseModel):
    daily: dict | None = None
    warnings: list[str] = []
    preferred_buffer_met: bool | None = None
    end_policy: str | None = None
    alternative_comparison: dict | None = None
    road_geometry: dict | None = None
    route_id: str
    version: int
    vehicle_id: str
    direction: Direction
    service_date: date
    departure: str
    departure_seconds: int
    timezone: str
    generated_at: datetime
    student_count: int
    capacity: int
    feasibility_status: str
    errors: list[str]
    stops: list[dict]
    distance_metres: int | None
    driving_seconds: int | None
    service_seconds: int | None
    waiting_seconds: int | None
    total_duration_seconds: int | None
    solver_runtime_seconds: float | None
    solver_status: str
    provider_source: dict | None
    optimality: str
    request_settings: dict
    assignment_policy: str

    roster_version: int
    current_roster_version: int
    is_current: bool
    planning_status: str
    planning_errors: list[str]
    trigger_event_id: str | None
    trigger_event: str
    execution_status: str
    comparison: dict
