"""Read-only freshness metadata, shared transaction lock, and actual comparisons."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import and_, or_, select, text
from models import RoutePlanState, RouteStop, RouteVersion, Vehicle


def planning_lock(session):
    # A single research-prototype planning lock gives mutation/solver transactions
    # a consistent lock order, including school edits affecting multiple vehicles.
    session.execute(text("SELECT pg_advisory_xact_lock(73521, 5)"))


def newest(session, vehicle_id, direction):
    return session.scalar(select(RouteVersion).where(RouteVersion.vehicle_id == vehicle_id, RouteVersion.direction == direction)
                          .order_by(RouteVersion.version.desc()).limit(1))


def execution_guard(session, vehicle_id, direction, service_date):
    return session.scalar(select(RouteVersion).where(RouteVersion.vehicle_id == vehicle_id, RouteVersion.direction == direction,
        or_(RouteVersion.execution_status == "active", and_(RouteVersion.execution_status == "completed", RouteVersion.service_date >= service_date)))
        .order_by(RouteVersion.version.desc()).limit(1))


def summary(session, route):
    if route is None: return None
    stops = session.scalars(select(RouteStop).where(RouteStop.route_id == route.id).order_by(RouteStop.sequence)).all()
    return {"route_id": route.id, "version": route.version, "roster_version": route.roster_version,
            "feasibility_status": route.feasibility_status, "generated_at": route.created_at.isoformat(),
            "solver_runtime_seconds": route.result.get("solver_runtime_seconds"),
            "provider_source": route.result.get("provider_source"),
            **{field: route.result.get(field) for field in ("distance_metres", "driving_seconds", "service_seconds", "waiting_seconds", "total_duration_seconds")},
            "_signature": [[stop.details.get(field) for field in ("action", "student_id", "location_id", "latitude", "longitude", "eta_seconds", "service_seconds", "waiting_seconds", "load_after")] for stop in stops]}


def comparison(before, after):
    fields = ("distance_metres", "driving_seconds", "service_seconds", "waiting_seconds", "total_duration_seconds")
    return {"before": {k:v for k,v in before.items() if k != "_signature"} if before else None,
            "after": {k:v for k,v in after.items() if k != "_signature"} if after else None,
            "delta_after_minus_before": {field: after[field] - before[field] if before and after and before.get(field) is not None and after.get(field) is not None else None for field in fields},
            "itinerary_changed": before["_signature"] != after["_signature"] if before and after and before["feasibility_status"] == after["feasibility_status"] == "feasible" else None}


def freshness(session, route):
    vehicle = session.get(Vehicle, route.vehicle_id)
    state = session.get(RoutePlanState, (route.vehicle_id, route.direction))
    revision = vehicle.roster_version
    matches = route.roster_version == revision and (state is None or (state.route_id == route.id and state.generation_status in ("feasible", "empty")))
    expired = route.service_date < datetime.now(ZoneInfo("Asia/Colombo")).date()
    current = matches and not expired and route.feasibility_status == "feasible" and route.execution_status == "pre_trip"
    status = state.generation_status if state else route.feasibility_status
    if route.roster_version != revision and status in ("feasible", "empty"): status = "stale"
    if expired and status in ("feasible", "empty"): status = "stale"
    if route.execution_status != "pre_trip" and status in ("feasible", "empty"): status = "locked_" + route.execution_status
    return {"roster_version": route.roster_version, "current_roster_version": revision,
            "is_current": current, "planning_status": status, "planning_errors": state.errors if state else [],
            "trigger_event_id": route.trigger_event_id, "trigger_event": route.trigger_event_type,
            "execution_status": route.execution_status, "comparison": state.comparison if state else {}}


def set_generated_state(session, route, previous):
    state = session.get(RoutePlanState, (route.vehicle_id, route.direction))
    if state is None:
        state = RoutePlanState(vehicle_id=route.vehicle_id, direction=route.direction, comparison={})
        session.add(state)
    state.roster_version = route.roster_version
    state.route_id = route.id
    state.generation_status = route.feasibility_status
    state.trigger_event_id = route.trigger_event_id
    state.settings = route.request_settings
    state.errors = route.result.get("errors", [])
    state.generated_at = route.created_at
    state.solver_runtime_seconds = route.result.get("solver_runtime_seconds")
    state.comparison = comparison(previous, summary(session, route))
    session.flush()
    return state


def set_execution_status(session, route, status):
    """Shared execution protection, inside the caller's planning transaction."""
    route.execution_status = status
    state = session.get(RoutePlanState, (route.vehicle_id, route.direction))
    if state is None: state = set_generated_state(session, route, None)
    state.generation_status = "locked_" + status
    state.errors = [f"{status.title()} execution snapshot is protected from pre-trip regeneration."]
