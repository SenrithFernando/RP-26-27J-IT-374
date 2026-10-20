"""Manual prototype trip lifecycle; no GPS, RFID or passenger completion claims."""
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, select, or_
from sqlalchemy.orm import Session
from models import RouteVersion, Trip, Vehicle
from persistence import session_dependency
from planning_state import freshness, newest, planning_lock, set_execution_status
from route_service import serialize_version

router = APIRouter(tags=["Prototype trips"])


class CreateTrip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_id: str = Field(min_length=1, max_length=64)
    pickup_mode: Literal["production", "simulation_demo"] = "production"
    pickup_scope: Literal["per_stop", "per_school"] | None = None


class CancelTrip(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=500)


def today():
    return datetime.now(ZoneInfo("Asia/Colombo")).date()


def require_plan(session, route, *, starting=False):
    from research_routes import is_research,require_research_plan
    if is_research(route):
        require_research_plan(session,route,starting=starting);return
    if not route or route.feasibility_status != "feasible" or not freshness(session, route)["is_current"]:
        raise HTTPException(409, "A feasible, current saved pre-trip route is required. Refresh or generate a new plan in Admin.")
    from landmark import scenario_for_vehicle,publication_blockers
    from models import LandmarkDailyPlan
    sc=scenario_for_vehicle(session,route.vehicle_id)
    if sc:
        state=session.get(LandmarkDailyPlan,(sc.id,route.service_date,route.direction))
        blockers,snapshot=publication_blockers(session,sc,route.service_date,route.direction,route)
        if not state or state.route_id!=route.id or state.publication!='published' or blockers or (snapshot['unresolved_boarding'] and not state.review.get('review_unresolved_boarding')):
            raise HTTPException(409,'Publish the current dated Daily Plan after attendance/location/evidence review before creating or starting a trip.')
    elif newest(session, route.vehicle_id, route.direction).id != route.id:
        raise HTTPException(409, "Only the latest current saved route can create or start a trip.")
    if route.service_date < today() or (starting and route.service_date != today()):
        raise HTTPException(409, "Trip start requires today's Sri Lankan service date; past plans cannot create trips.")


def serialize_trip(session, trip):
    route = session.get(RouteVersion, trip.route_id)
    from pickup_windows import pending_actions
    unfinished = pending_actions(session, trip)
    from tracking import adult_field_test_allowed
    return {"trip_id": trip.id, "route_id": trip.route_id, "route_version": route.version,
        "vehicle_id": trip.vehicle_id, "direction": trip.direction, "state": trip.state,
        "adult_phone_field_test_authorized":adult_field_test_allowed(session,trip),
        "gps_observation_context":"adult_landmark_field_test" if (trip.pickup_settings or {}).get('adult_phone_field_test') else None,
        **{key: getattr(trip, key).isoformat() if getattr(trip, key) else None for key in
           ("created_at", "started_at", "completed_at", "cancelled_at")},
        "cancellation_reason": trip.cancellation_reason, "action_source": "manual_prototype",
        "unfinished_actions": unfinished, "unfinished_action_count": len(unfinished),
        "passenger_event_recording": "not_applicable_adult_research" if route.input_snapshot.get('research_journey') else "manual_pickup_only_delivery_unavailable",
        "route": serialize_version(session, route)}


@router.get("/trips/current")
def current_trip(vehicle_id: str, direction: Literal["morning", "afternoon"] | None = None, session: Session = Depends(session_dependency)):
    if session.get(Vehicle, vehicle_id) is None: raise HTTPException(404, "Vehicle not found.")
    # Across both directions: an active morning trip must remain visible while viewing afternoon planning.
    query = select(Trip).where(Trip.vehicle_id == vehicle_id)
    if direction: query = query.where(or_(Trip.state == "ACTIVE", Trip.direction == direction))
    trip = session.scalar(query.order_by(
        case((Trip.state == "ACTIVE", 0), else_=1), Trip.created_at.desc(), Trip.id).limit(1))
    return {"trip": serialize_trip(session, trip) if trip else None}


@router.get("/trips/{trip_id}")
def read_trip(trip_id: str, session: Session = Depends(session_dependency)):
    trip = session.get(Trip, trip_id)
    if trip is None: raise HTTPException(404, "Trip not found.")
    return serialize_trip(session, trip)


@router.post("/trips")
def create_trip(payload: CreateTrip, session: Session = Depends(session_dependency)):
    planning_lock(session)
    route = session.get(RouteVersion, payload.route_id)
    if route is None: raise HTTPException(404, "Saved route not found.")
    from research_routes import is_research
    research=is_research(route)
    if research and (payload.pickup_mode!='production' or payload.pickup_scope not in (None,'per_stop')):
        raise HTTPException(422,'Research has no school pickup windows; use production/default scope, never accelerated or school-window settings.')
    existing = session.scalar(select(Trip).where(Trip.route_id == route.id, Trip.state.in_(("PLANNED", "ACTIVE"))))
    if existing:
        if existing.pickup_settings and (existing.pickup_settings["mode"]!=payload.pickup_mode or (payload.pickup_scope and existing.pickup_settings["scope"]!=payload.pickup_scope)):
            raise HTTPException(409,"An open trip already exists with different immutable pickup settings.")
        return serialize_trip(session, existing)  # Double-click/retry cannot create duplicates.
    require_plan(session, route)
    snapshot = serialize_version(session, route)
    actions = [{"event_id": stop["event_id"]+(':'+sid if stop.get('grouped') else ''), "sequence": stop["sequence"], "action": stop["action"],
                "student_id": sid, "student_name": stop.get('student_names',{}).get(sid,stop.get("student_name")),
                "school_name": stop.get("school_name"), "name": stop["name"], "status": "PENDING"}
               for stop in snapshot["stops"] if stop["action"] in ("pickup", "delivery") for sid in stop.get('student_ids',[stop.get('student_id')])]
    from pickup_windows import trip_settings, create_windows
    from research_routes import is_research
    research=is_research(route)
    if research and payload.pickup_mode!='production':raise HTTPException(422,'Adult research uses real-duration GPS, never accelerated simulation mode.')
    pickup_settings={'mode':'production','scope':'per_stop','research_only':True} if research else trip_settings(session,route,payload.pickup_mode,payload.pickup_scope)
    trip = Trip(pickup_settings=pickup_settings,id="TRIP_"+uuid4().hex, route_id=route.id, vehicle_id=route.vehicle_id,
        direction=route.direction, state="PLANNED", created_at=datetime.now(timezone.utc), unfinished_actions=actions)
    session.add(trip); session.flush()
    if not research:create_windows(session,trip,snapshot)
    session.commit()
    return serialize_trip(session, trip)


def transition(session, trip_id, target, reason=None):
    planning_lock(session)
    trip = session.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
    if trip is None: raise HTTPException(404, "Trip not found.")
    if trip.state == target: return serialize_trip(session, trip)  # Idempotent retries preserve timestamps.
    route = session.get(RouteVersion, trip.route_id)
    now = datetime.now(timezone.utc)
    if target == "ACTIVE":
        if trip.state != "PLANNED": raise HTTPException(409, "Only a planned trip can start; terminal trips cannot reopen.")
        require_plan(session, route, starting=True)
        # Also respect legacy execution snapshots created before persisted trips existed.
        active = session.scalar(select(RouteVersion.id).where(RouteVersion.vehicle_id == trip.vehicle_id,
            RouteVersion.execution_status == "active").limit(1))
        other = session.scalar(select(Trip.id).where(Trip.vehicle_id == trip.vehicle_id, Trip.state == "ACTIVE").limit(1))
        if active or other: raise HTTPException(409, "This vehicle already has an active trip/execution snapshot. End or cancel it first.")
        set_execution_status(session, route, "active")
        from arrivals import initialize_stop
        initialize_stop(session, trip, now)
        trip.started_at = now
    elif target == "COMPLETED":
        if trip.state != "ACTIVE": raise HTTPException(409, "Only an active trip can be ended.")
        set_execution_status(session, route, "completed")
        trip.completed_at = now
        # Deliberately do not mark any pickup/delivery event completed.
    elif target == "CANCELLED":
        if trip.state not in ("PLANNED", "ACTIVE"): raise HTTPException(409, "Only a planned or active trip can be cancelled.")
        if trip.state == "ACTIVE": set_execution_status(session, route, "cancelled")
        trip.cancelled_at = now; trip.cancellation_reason = reason
    trip.state = target
    if target=="ACTIVE":
        from operational_monitor import initialize_monitor
        initialize_monitor(session,trip)
    if target in ("COMPLETED","CANCELLED"):
        from pickup_windows import close_trip_windows, clock
        close_trip_windows(session,trip,clock(session))
        from operational_monitor import close_operational_episodes
        close_operational_episodes(session,trip,clock(session))
    session.commit()
    return serialize_trip(session, trip)


@router.post("/trips/{trip_id}/start")
def start_trip(trip_id: str, session: Session = Depends(session_dependency)):
    return transition(session, trip_id, "ACTIVE")


@router.post("/trips/{trip_id}/complete")
def complete_trip(trip_id: str, session: Session = Depends(session_dependency)):
    return transition(session, trip_id, "COMPLETED")


@router.post("/trips/{trip_id}/cancel")
def cancel_trip(trip_id: str, payload: CancelTrip, session: Session = Depends(session_dependency)):
    return transition(session, trip_id, "CANCELLED", payload.reason)
