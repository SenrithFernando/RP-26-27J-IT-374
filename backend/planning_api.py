from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from models import RoutePlanState, RouteVersion, RoutingEvent, Student, Vehicle, Trip
from persistence import session_dependency
from planning_orchestration import get_event_response, process_event_safe
from planning_state import freshness, newest, planning_lock, set_execution_status

router = APIRouter(tags=["Pre-trip planning"])


@router.get("/routing/events/{event_id}")
def event_status(event_id: str, session: Session = Depends(session_dependency)):
    return get_event_response(session, event_id)


@router.post("/routing/events/{event_id}/retry")
def retry_event(event_id: str, session: Session = Depends(session_dependency)):
    planning_lock(session)
    event = session.get(RoutingEvent, event_id)
    if event is None: raise HTTPException(404, "Routing event not found.")
    # Constraint failures already have an immutable attempt; only exception/pending
    # recovery needs another execution. Successfully stored directions are reused.
    if any(plan.get("generation_status") == "error" for plan in event.outcome.get("plans", [])):
        event.status = "pending"
    session.commit()
    return process_event_safe(session, event_id)


@router.get("/routing/plans/{vehicle_id}/{direction}")
def plan_status(vehicle_id: str, direction: Literal["morning", "afternoon"], session: Session = Depends(session_dependency)):
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None: raise HTTPException(404, "Vehicle not found.")
    state = session.get(RoutePlanState, (vehicle_id, direction))
    route = newest(session, vehicle_id, direction)
    meta = freshness(session, route) if route else {}
    return {"vehicle_id": vehicle_id, "direction": direction, "roster_version": vehicle.roster_version,
            "student_count": session.scalar(select(func.count()).select_from(Student).where(Student.vehicle_id == vehicle_id, Student.active.is_(True))),
            "capacity": vehicle.capacity,
            "generation_status": state.generation_status if state else route.feasibility_status if route else "unconfigured",
            "errors": state.errors if state else [], "is_current": meta.get("is_current", False),
            "route_id": state.route_id if state else route.id if route else None,
            "trigger_event_id": state.trigger_event_id if state else None,
            "generation_timestamp": state.generated_at.isoformat() if state and state.generated_at else None,
            "solver_runtime_seconds": state.solver_runtime_seconds if state else None,
            "comparison": state.comparison if state else {}}


class ExecutionLock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_status: Literal["active", "completed"]


@router.patch("/routes/{route_id}/planning-lock")
def lock_execution(route_id: str, payload: ExecutionLock, session: Session = Depends(session_dependency)):
    """Minimal backend guard, not a trip simulation or stop-progress reset API."""
    planning_lock(session)
    route = session.get(RouteVersion, route_id)
    if route is None: raise HTTPException(404, "Stored route not found.")
    if session.scalar(select(Trip.id).where(Trip.route_id == route_id, Trip.state.in_(("PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"))).limit(1)):
        raise HTTPException(409, "This snapshot belongs to a persisted trip. Use the trip lifecycle endpoints.")
    if payload.execution_status == "active" and session.scalar(select(Trip.id).where(Trip.vehicle_id == route.vehicle_id, Trip.state == "ACTIVE").limit(1)):
        raise HTTPException(409, "This vehicle already has an active trip.")
    if route.execution_status == payload.execution_status:
        return {"route_id": route.id, "execution_status": route.execution_status}
    if payload.execution_status == "active":
        if route.execution_status != "pre_trip" or not freshness(session, route)["is_current"]:
            raise HTTPException(409, "Only a current feasible pre-trip plan can be locked active.")
    elif route.execution_status != "active":
        raise HTTPException(409, "Only an active execution snapshot can be marked completed; completed trips cannot be reopened here.")
    set_execution_status(session, route, payload.execution_status)
    session.commit()
    return {"route_id": route.id, "execution_status": route.execution_status}
