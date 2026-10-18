from sqlalchemy import ForeignKeyConstraint, BigInteger, Identity, Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    input_source: Mapped[str] = mapped_column(String(32))
    address: Mapped[str] = mapped_column(String(500), server_default="")
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    location_confirmed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    location_method: Mapped[str] = mapped_column(String(32), server_default="manual")
    morning_deadline_seconds: Mapped[int | None]
    afternoon_finish_seconds: Mapped[int | None]
    __table_args__ = (CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="school_source"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="school_coordinate_range"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="school_coordinates_pair"),
        CheckConstraint("NOT location_confirmed OR (latitude IS NOT NULL AND longitude IS NOT NULL AND length(trim(address)) > 0)", name="school_confirmed_location"),
        CheckConstraint("morning_deadline_seconds BETWEEN 0 AND 86399", name="school_morning_deadline_range"),
        CheckConstraint("afternoon_finish_seconds BETWEEN 0 AND 86399", name="school_afternoon_finish_range"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    roster_version: Mapped[int] = mapped_column(server_default="0")
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    capacity: Mapped[int]
    input_source: Mapped[str] = mapped_column(String(32))
    start_address: Mapped[str] = mapped_column(String(500), server_default="")
    start_latitude: Mapped[float | None]
    start_longitude: Mapped[float | None]
    start_confirmed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    start_method: Mapped[str] = mapped_column(String(32), server_default="manual")
    end_address: Mapped[str] = mapped_column(String(500), server_default="")
    end_latitude: Mapped[float | None]
    end_longitude: Mapped[float | None]
    end_confirmed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    end_method: Mapped[str] = mapped_column(String(32), server_default="manual")
    __table_args__ = (
        *tuple(constraint for position in ("start", "end") for constraint in (
            CheckConstraint(f"{position}_latitude BETWEEN -90 AND 90 AND {position}_longitude BETWEEN -180 AND 180", name=f"vehicle_{position}_coordinate_range"),
            CheckConstraint(f"({position}_latitude IS NULL) = ({position}_longitude IS NULL)", name=f"vehicle_{position}_coordinates_pair"),
            CheckConstraint(f"NOT {position}_confirmed OR ({position}_latitude IS NOT NULL AND {position}_longitude IS NOT NULL AND length(trim({position}_address)) > 0)", name=f"vehicle_{position}_confirmed_location"),
        )),
        CheckConstraint("capacity > 0", name="vehicle_capacity_positive"),
        CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="vehicle_source"),
    )


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    home_id: Mapped[str] = mapped_column(String(64))
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True)
    input_source: Mapped[str] = mapped_column(String(32))
    home_latitude: Mapped[float | None]
    home_longitude: Mapped[float | None]
    home_address: Mapped[str] = mapped_column(String(500), server_default="")
    location_confirmed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    location_method: Mapped[str] = mapped_column(String(32), server_default="manual")
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    __table_args__ = (
        CheckConstraint("input_source IN ('simulated', 'live_provider', 'measured')", name="student_source"),
        CheckConstraint("home_latitude BETWEEN -90 AND 90", name="student_latitude_range"),
        CheckConstraint("home_longitude BETWEEN -180 AND 180", name="student_longitude_range"),
        CheckConstraint("(home_latitude IS NULL) = (home_longitude IS NULL)", name="student_coordinates_pair"),
        CheckConstraint("NOT location_confirmed OR (home_latitude IS NOT NULL AND home_longitude IS NOT NULL AND length(trim(home_address)) > 0)", name="student_confirmed_location"),
    )


from datetime import date, datetime
from sqlalchemy import Date, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB


class RouteVersion(Base):
    __tablename__ = "route_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    direction: Mapped[str] = mapped_column(String(16))
    version: Mapped[int]
    roster_version: Mapped[int] = mapped_column(server_default="0")
    trigger_event_id: Mapped[str | None] = mapped_column(ForeignKey("routing_events.id"))
    trigger_event_type: Mapped[str] = mapped_column(String(64), server_default="manual_generation")
    execution_status: Mapped[str] = mapped_column(String(16), server_default="pre_trip")
    service_date: Mapped[date] = mapped_column(Date)
    departure_seconds: Mapped[int]
    feasibility_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request_settings: Mapped[dict] = mapped_column(JSONB)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        UniqueConstraint("vehicle_id", "direction", "version", name="uq_route_vehicle_direction_version"),
        UniqueConstraint("trigger_event_id", "vehicle_id", "direction", name="uq_route_event_vehicle_direction"),
        CheckConstraint("execution_status IN ('pre_trip', 'active', 'completed', 'cancelled')", name="route_execution_status"),
        CheckConstraint("version > 0", name="route_version_positive"),
        CheckConstraint("direction IN ('morning', 'afternoon')", name="route_direction"),
    )


class RouteStop(Base):
    __tablename__ = "route_stops"
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id", ondelete="CASCADE"), primary_key=True)
    sequence: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(16))
    # IDs are immutable generation-time references, preserved if registrations change.
    student_id: Mapped[str | None] = mapped_column(String(64), index=True)
    location_id: Mapped[str] = mapped_column(String(128))
    latitude: Mapped[float]
    longitude: Mapped[float]
    eta_seconds: Mapped[int]
    details: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("sequence > 0", name="route_stop_sequence_positive"),
        CheckConstraint("action IN ('start', 'pickup', 'delivery', 'end')", name="route_stop_action"),
    )


class RoutingEvent(Base):
    __tablename__ = "routing_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    affected_vehicles: Mapped[dict] = mapped_column(JSONB)
    record_snapshot: Mapped[dict] = mapped_column(JSONB)
    before_routes: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoutePlanState(Base):
    __tablename__ = "route_plan_states"
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), primary_key=True)
    direction: Mapped[str] = mapped_column(String(16), primary_key=True)
    roster_version: Mapped[int]
    generation_status: Mapped[str] = mapped_column(String(32))
    trigger_event_id: Mapped[str | None] = mapped_column(ForeignKey("routing_events.id"))
    route_id: Mapped[str | None] = mapped_column(ForeignKey("route_versions.id"))
    settings: Mapped[dict] = mapped_column(JSONB)
    errors: Mapped[list] = mapped_column(JSONB)
    comparison: Mapped[dict] = mapped_column(JSONB)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solver_runtime_seconds: Mapped[float | None]
    __table_args__ = (CheckConstraint("direction IN ('morning', 'afternoon')", name="plan_direction"),)


class Trip(Base):
    """Lifecycle only. Route and unfinished action snapshot never follow the latest plan."""
    __tablename__ = "trips"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id", ondelete="RESTRICT"))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    direction: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    current_stop_sequence: Mapped[int | None]
    current_stop_selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_settings: Mapped[dict | None] = mapped_column(JSONB)
    pickup_settings: Mapped[dict | None] = mapped_column(JSONB)
    unfinished_actions: Mapped[list] = mapped_column(JSONB)
    __table_args__ = (
        CheckConstraint("state IN ('PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED')", name="trip_state"),
        CheckConstraint("direction IN ('morning', 'afternoon')", name="trip_direction"),
        CheckConstraint("(state = 'PLANNED' AND started_at IS NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (state = 'ACTIVE' AND started_at IS NOT NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (state = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND cancelled_at IS NULL) OR (state = 'CANCELLED' AND cancelled_at IS NOT NULL AND completed_at IS NULL AND cancellation_reason IS NOT NULL)", name="trip_timestamps"),
    )

from sqlalchemy import Index
Index("one_active_trip_per_vehicle", Trip.vehicle_id, unique=True, postgresql_where=text("state = 'ACTIVE'"))
Index("one_open_trip_per_route", Trip.route_id, unique=True, postgresql_where=text("state IN ('PLANNED', 'ACTIVE')"))


class VehiclePosition(Base):
    __tablename__ = "vehicle_positions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sample_id: Mapped[str] = mapped_column(String(128))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"))
    source: Mapped[str] = mapped_column(String(24))
    latitude: Mapped[float]
    longitude: Mapped[float]
    speed_mps: Mapped[float | None]
    accuracy_m: Mapped[float | None]
    tracking_session_id: Mapped[str | None] = mapped_column(ForeignKey('tracking_sessions.id',ondelete='RESTRICT'))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("vehicle_id", "source", "sample_id", name="position_sample_identity"),
        UniqueConstraint("vehicle_id", "recorded_at", name="position_vehicle_timestamp"),
        CheckConstraint("source IN ('simulation', 'actual_device')", name="position_source"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="position_coordinates"),
        CheckConstraint("speed_mps IS NULL OR (speed_mps >= 0 AND speed_mps < 'Infinity'::float8)", name="position_speed"),
        CheckConstraint("accuracy_m IS NULL OR (accuracy_m >= 0 AND accuracy_m < 'Infinity'::float8)", name="position_accuracy"),
    )
Index("positions_vehicle_recorded", VehiclePosition.vehicle_id, VehiclePosition.recorded_at.desc(), VehiclePosition.id)
Index("positions_trip_recorded", VehiclePosition.trip_id, VehiclePosition.recorded_at.desc(), VehiclePosition.id)


class TripStopArrival(Base):
    __tablename__ = "trip_stop_arrivals"
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), primary_key=True)
    stop_sequence: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id", ondelete="RESTRICT"))
    candidate_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_count: Mapped[int]
    distance_metres: Mapped[float]
    source: Mapped[str] = mapped_column(String(24))
    event_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirming_position_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_positions.id", ondelete="RESTRICT"))
    __table_args__ = (
        CheckConstraint("observation_count >= 0", name="arrival_observations"),
        CheckConstraint("(arrived_at IS NULL AND event_id IS NULL AND confirming_position_id IS NULL) OR (arrived_at IS NOT NULL AND event_id IS NOT NULL AND confirming_position_id IS NOT NULL)", name="arrival_event_complete"),
    )


class PickupWindow(Base):
    __tablename__ = "pickup_windows"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"))
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id", ondelete="RESTRICT"))
    scope_key: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(16))
    school_id: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(24))
    duration_seconds: Mapped[int]
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    arrival_event_id: Mapped[str | None] = mapped_column(ForeignKey("trip_stop_arrivals.event_id", ondelete="RESTRICT"))
    __table_args__ = (
        UniqueConstraint("trip_id","scope_key",name="pickup_visit_once"),
        CheckConstraint("state IN ('SCHEDULED','ARRIVED','WAITING','PICKED_UP','MISSED','CANCELLED')",name="pickup_window_state"),
        CheckConstraint("(mode='production' AND duration_seconds=900) OR (mode='simulation_demo' AND duration_seconds BETWEEN 5 AND 120)",name="pickup_duration_mode"),
        CheckConstraint("(started_at IS NULL AND deadline_at IS NULL) OR (started_at IS NOT NULL AND deadline_at > started_at)",name="pickup_deadline_pair"),
    )
Index("pickup_expiry_due",PickupWindow.deadline_at,PickupWindow.id,postgresql_where=text("state = 'WAITING'"))

class PickupOutcome(Base):
    __tablename__ = "pickup_outcomes"
    window_id: Mapped[str] = mapped_column(ForeignKey("pickup_windows.id",ondelete="RESTRICT"),primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64),primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id",ondelete="RESTRICT"))
    stop_sequence: Mapped[int]
    student_name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(16))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_source: Mapped[str] = mapped_column(String(48))
    __table_args__ = (UniqueConstraint("trip_id","student_id",name="pickup_student_once"),
        UniqueConstraint("trip_id","stop_sequence","student_id",name="pickup_stop_once"),
        CheckConstraint("state IN ('SCHEDULED','ARRIVED','WAITING','PICKED_UP','MISSED','CANCELLED')",name="pickup_outcome_state"))

class PickupTransition(Base):
    __tablename__ = "pickup_transitions"
    __table_args__ = (UniqueConstraint("order_id", name="pickup_transition_order_unique"),)
    order_id: Mapped[int] = mapped_column(BigInteger, Identity())
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    window_id: Mapped[str] = mapped_column(ForeignKey("pickup_windows.id",ondelete="RESTRICT"))
    student_id: Mapped[str | None] = mapped_column(String(64))
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action_source: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str] = mapped_column(String(500))
Index("pickup_transition_history",PickupTransition.window_id,PickupTransition.recorded_at,PickupTransition.id)

Index("pickup_history_order",PickupTransition.window_id,PickupTransition.order_id)


class MissedPickupNotification(Base):
    __tablename__ = "missed_pickup_notifications"
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger,Identity())
    kind: Mapped[str] = mapped_column(String(32))
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id",ondelete="RESTRICT"))
    window_id: Mapped[str] = mapped_column(String(64))
    student_id: Mapped[str] = mapped_column(String(64))
    student_name: Mapped[str] = mapped_column(String(200))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id",ondelete="RESTRICT"))
    route_id: Mapped[str] = mapped_column(String(64))
    stop_sequence: Mapped[int]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action_source: Mapped[str] = mapped_column(String(48))
    position_source: Mapped[str | None] = mapped_column(String(24))
    mode: Mapped[str] = mapped_column(String(24))
    delivery_status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(500))
    admin_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("order_id",name="missed_notification_order"),
        UniqueConstraint("trip_id","student_id","kind",name="one_missed_notification_per_pickup"),
        ForeignKeyConstraint(["window_id","student_id"],["pickup_outcomes.window_id","pickup_outcomes.student_id"],ondelete="RESTRICT"),
        ForeignKeyConstraint(["route_id","stop_sequence"],["route_stops.route_id","route_stops.sequence"],ondelete="RESTRICT"),
        CheckConstraint("kind='missed_pickup'",name="missed_notification_kind"),
        CheckConstraint("delivery_status='in_app_event_created'",name="missed_notification_delivery"),
    )
Index("missed_notification_student_order",MissedPickupNotification.student_id,MissedPickupNotification.order_id.desc())
Index("missed_notification_admin_unread",MissedPickupNotification.order_id,postgresql_where=text("admin_read_at IS NULL"))
Index("missed_notification_parent_unread",MissedPickupNotification.student_id,MissedPickupNotification.order_id,postgresql_where=text("parent_read_at IS NULL"))


class TripOperationalMonitor(Base):
    __tablename__ = "trip_operational_monitors"
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id",ondelete="RESTRICT"),primary_key=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id",ondelete="RESTRICT"))
    settings: Mapped[dict] = mapped_column(JSONB)
    geometry: Mapped[dict] = mapped_column(JSONB)
    progress: Mapped[dict] = mapped_column(JSONB)
    last_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_source: Mapped[str | None] = mapped_column(String(24))


class OperationalEpisode(Base):
    __tablename__ = "operational_episodes"
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id",ondelete="RESTRICT"))
    route_id: Mapped[str] = mapped_column(ForeignKey("route_versions.id",ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(32))
    episode: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_reason: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(24))
    recovery_source: Mapped[str | None] = mapped_column(String(24))
    geometry_quality: Mapped[str] = mapped_column(String(40))
    geometry_source: Mapped[str] = mapped_column(String(32))
    thresholds: Mapped[dict] = mapped_column(JSONB)
    evidence: Mapped[dict] = mapped_column(JSONB)
    confirming_position_id: Mapped[str] = mapped_column(ForeignKey("vehicle_positions.id",ondelete="RESTRICT"))
    recovery_position_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_positions.id",ondelete="RESTRICT"))
    __table_args__ = (
        UniqueConstraint("trip_id","kind","episode",name="operational_episode_identity"),
        CheckConstraint("kind IN ('route_deviation','unexpected_stop')",name="operational_episode_kind"),
        CheckConstraint("status IN ('ACTIVE','RECOVERED','CLOSED')",name="operational_episode_status"),
    )
Index("operational_one_active_kind",OperationalEpisode.trip_id,OperationalEpisode.kind,unique=True,postgresql_where=text("status='ACTIVE'"))
Index("operational_trip_history",OperationalEpisode.trip_id,OperationalEpisode.confirmed_at.desc(),OperationalEpisode.id)


class SyntheticTripProvenance(Base):
    __tablename__ = "synthetic_trip_provenance"
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), primary_key=True)
    generator: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(String(500))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProvenanceCorrection(Base):
    __tablename__ = "provenance_corrections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_table: Mapped[str] = mapped_column(String(64))
    entity_key: Mapped[str] = mapped_column(String(200))
    field_name: Mapped[str] = mapped_column(String(64))
    previous_source: Mapped[str] = mapped_column(String(48))
    corrected_source: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str] = mapped_column(String(500))
    correction_code: Mapped[str] = mapped_column(String(80))
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("entity_table", "entity_key", "field_name", "correction_code", name="provenance_correction_once"),)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(64),primary_key=True)
    username: Mapped[str] = mapped_column(String(100),unique=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean,default=False)
    demo_only: Mapped[bool] = mapped_column(Boolean,default=False)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__=(CheckConstraint("role IN ('administrator','driver','parent')",name="account_role"),)


class DriverVehicle(Base):
    __tablename__="driver_vehicles"
    account_id: Mapped[str]=mapped_column(ForeignKey("accounts.id",ondelete="RESTRICT"),primary_key=True)
    vehicle_id: Mapped[str]=mapped_column(ForeignKey("vehicles.id",ondelete="RESTRICT"),primary_key=True)


class ParentStudent(Base):
    __tablename__="parent_students"
    account_id: Mapped[str]=mapped_column(ForeignKey("accounts.id",ondelete="RESTRICT"),primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey("students.id",ondelete="RESTRICT"),primary_key=True)


class LoginSession(Base):
    __tablename__="login_sessions"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    token_hash: Mapped[str]=mapped_column(String(64),unique=True)
    account_id: Mapped[str]=mapped_column(ForeignKey("accounts.id",ondelete="RESTRICT"),index=True)
    mode: Mapped[str]=mapped_column(String(8))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    revoked_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    __table_args__=(CheckConstraint("mode IN ('demo','real')",name="login_mode"),)


class TrackingSession(Base):
    __tablename__="tracking_sessions"
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    token_hash: Mapped[str]=mapped_column(String(64),unique=True)
    login_session_id: Mapped[str]=mapped_column(ForeignKey("login_sessions.id",ondelete="RESTRICT"),index=True)
    vehicle_id: Mapped[str]=mapped_column(ForeignKey("vehicles.id",ondelete="RESTRICT"),index=True)
    trip_id: Mapped[str]=mapped_column(ForeignKey("trips.id",ondelete="RESTRICT"),index=True)
    kind: Mapped[str]=mapped_column(String(16))
    label: Mapped[str]=mapped_column(String(100))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    __table_args__=(CheckConstraint("kind IN ('phone','simulation')",name="tracking_kind"),)


class LandmarkScenario(Base):
    __tablename__='landmark_scenarios'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    vehicle_id: Mapped[str]=mapped_column(ForeignKey('vehicles.id'),unique=True)
    default_date: Mapped[date]=mapped_column(Date)
    policy: Mapped[dict]=mapped_column(JSONB)


class LandmarkAttendance(Base):
    __tablename__='landmark_attendance'
    scenario_id: Mapped[str]=mapped_column(ForeignKey('landmark_scenarios.id'),primary_key=True)
    service_date: Mapped[date]=mapped_column(Date,primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey('students.id'),primary_key=True)
    am: Mapped[str]=mapped_column(String(12))
    pm: Mapped[str]=mapped_column(String(12))
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    event_id: Mapped[str]=mapped_column(String(128))
    __table_args__=(CheckConstraint("am IN ('yes','no','unknown') AND pm IN ('yes','no','unknown')",name='landmark_attendance_values'),)


class LandmarkBoarding(Base):
    __tablename__='landmark_boarding'
    scenario_id: Mapped[str]=mapped_column(ForeignKey('landmark_scenarios.id'),primary_key=True)
    service_date: Mapped[date]=mapped_column(Date,primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey('students.id'),primary_key=True)
    outcome: Mapped[str]=mapped_column(String(12))
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    event_id: Mapped[str]=mapped_column(String(128))
    __table_args__=(CheckConstraint("outcome IN ('boarded','no_show','unknown')",name='landmark_boarding_values'),)


class LandmarkInputEvent(Base):
    __tablename__='landmark_input_events'
    event_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    scenario_id: Mapped[str]=mapped_column(ForeignKey('landmark_scenarios.id'))
    payload_hash: Mapped[str]=mapped_column(String(64))
    payload: Mapped[dict]=mapped_column(JSONB)
    actor_id: Mapped[str]=mapped_column(String(64))
    received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))


class LandmarkDailyPlan(Base):
    __tablename__='landmark_daily_plans'
    scenario_id: Mapped[str]=mapped_column(ForeignKey('landmark_scenarios.id'),primary_key=True)
    service_date: Mapped[date]=mapped_column(Date,primary_key=True)
    direction: Mapped[str]=mapped_column(String(16),primary_key=True)
    route_id: Mapped[str|None]=mapped_column(ForeignKey('route_versions.id'))
    publication: Mapped[str]=mapped_column(String(16),default='draft')
    review: Mapped[dict]=mapped_column(JSONB,default=dict)
