"""Backend-owned, durable pre-trip mutation -> regeneration orchestration."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from models import RoutePlanState, RouteVersion, RoutingEvent, Vehicle
from planning_state import comparison, execution_guard, newest, planning_lock, summary
from route_schemas import GenerateRouteRequest
from route_service import generate_and_store

DIRECTIONS = ("morning", "afternoon")
SUCCESS = {"feasible", "empty", "unchanged"}


def columns(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def default_request(session, vehicle_id, direction):
    state = session.get(RoutePlanState, (vehicle_id, direction))
    last = newest(session, vehicle_id, direction)
    settings = dict(state.settings if state and state.settings else last.request_settings if last else {})
    today = datetime.now(ZoneInfo("Asia/Colombo")).date().isoformat()
    if not settings:
        settings = {"vehicle_id": vehicle_id, "direction": direction,
                    "departure_seconds": int(os.getenv("PLANNING_MORNING_DEPARTURE_SECONDS", "21600") if direction == "morning" else os.getenv("PLANNING_AFTERNOON_DEPARTURE_SECONDS", "45000")),
                    "pickup_service_seconds": int(os.getenv("PLANNING_PICKUP_SERVICE_SECONDS", "30")),
                    "delivery_service_seconds": int(os.getenv("PLANNING_DELIVERY_SERVICE_SECONDS", "30")),
                    "solver_time_limit_seconds": int(os.getenv("PLANNING_SOLVER_LIMIT_SECONDS", "2"))}
    if settings.get("service_date", "") < today: settings["service_date"] = today
    return GenerateRouteRequest(**settings)


def get_event_response(session, event_id):
    event = session.get(RoutingEvent, event_id)
    if event is None: raise HTTPException(404, "Routing event not found.")
    return {"event_id": event.id, "trigger_event": event.event_type, "generation_status": event.status,
            "generation_timestamp": event.finished_at.isoformat() if event.finished_at else None,
            **event.outcome}


def mutate_and_plan(session, *, event_type, entity_id, payload, request_key, record_schema, mutation):
    """Only phase 1 saves input. Routing failures cannot roll back that commit."""
    planning_lock(session)
    fingerprint = sha256(json.dumps({"type": event_type, "id": entity_id, "body": payload}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if request_key:
        old = session.scalar(select(RoutingEvent).where(RoutingEvent.request_key == request_key))
        if old:
            if old.payload_hash != fingerprint: raise HTTPException(409, "Idempotency key was already used for a different change.")
            saved = dict(old.record_snapshot); event_id = old.id
            session.commit()
            return {**saved, "save_status": "saved", "routing": process_event_safe(session, event_id)}
    row, affected_ids, before = mutation()
    session.flush()
    changed = before is None or before != columns(row)
    record = record_schema.model_validate(row).model_dump(mode="json")
    affected_ids = sorted(set(affected_ids))
    revisions, before_routes = {}, {}
    event_id = f"EVENT_{uuid4().hex}"
    for vehicle_id in affected_ids:
        vehicle = session.get(Vehicle, vehicle_id)
        if changed: vehicle.roster_version += 1
        revisions[vehicle_id] = vehicle.roster_version
        for direction in DIRECTIONS:
            before_routes[f"{vehicle_id}:{direction}"] = summary(session, newest(session, vehicle_id, direction))
    event = RoutingEvent(id=event_id, event_type=event_type, entity_id=row.id, request_key=request_key,
        payload_hash=fingerprint, affected_vehicles=revisions, record_snapshot=record, before_routes=before_routes,
        status="pending" if changed else "unchanged", outcome={})
    session.add(event); session.flush()
    if changed:
        for vehicle_id, revision in revisions.items():
            for direction in DIRECTIONS:
                state = session.get(RoutePlanState, (vehicle_id, direction))
                if state is None:
                    state = RoutePlanState(vehicle_id=vehicle_id, direction=direction, settings={}, comparison={})
                    session.add(state)
                state.roster_version = revision
                state.generation_status = "pending"
                state.trigger_event_id = event_id
                state.errors = ["Inputs saved; backend pre-trip regeneration is pending. Older routes are not current."]
                state.generated_at = None; state.solver_runtime_seconds = None
                state.route_id = None
                state.comparison = comparison(before_routes[f"{vehicle_id}:{direction}"], None)
    else:
        event.outcome = {"outcome": "unchanged", "errors": [], "plans": [
            {"vehicle_id": vehicle_id, "direction": direction, "roster_version": revisions[vehicle_id],
             "generation_status": "unchanged", "generated": False, "comparison": comparison(before_routes[f"{vehicle_id}:{direction}"], before_routes[f"{vehicle_id}:{direction}"])}
            for vehicle_id in affected_ids for direction in DIRECTIONS]}
        event.finished_at = datetime.now(timezone.utc)
    session.commit()  # Registration + revision + durable pending markers become visible together.
    return {**record, "save_status": "saved", "routing": process_event_safe(session, event_id)}


def process_event(session, event_id):
    planning_lock(session)
    event = session.get(RoutingEvent, event_id)
    if event is None: raise HTTPException(404, "Routing event not found.")
    # All workers/retries serialize here; completed events never generate another version.
    if event.status != "pending":
        response = get_event_response(session, event_id); session.commit(); return response
    plans, errors = [], []
    for vehicle_id, target_revision in sorted(event.affected_vehicles.items()):
        for direction in DIRECTIONS:
            state = session.get(RoutePlanState, (vehicle_id, direction))
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle.roster_version != target_revision or state.trigger_event_id != event.id:
                plans.append({"vehicle_id": vehicle_id, "direction": direction, "roster_version": target_revision,
                              "generation_status": "superseded", "generated": False, "comparison": {}})
                continue
            item = {"vehicle_id": vehicle_id, "direction": direction, "roster_version": target_revision, "generated": False}
            try:
                request = default_request(session, vehicle_id, direction)
                protected = execution_guard(session, vehicle_id, direction, request.service_date)
                if protected:
                    status = "deferred_" + protected.execution_status
                    state.generation_status = status
                    state.errors = [f"{protected.execution_status.title()} trip {protected.id} is unchanged. The next pre-trip plan is stale; no stops were reordered or reset."]
                    item.update(generation_status=status, errors=state.errors, route_id=protected.id, comparison={})
                else:
                    existing = session.scalar(select(RouteVersion.id).where(
                        RouteVersion.trigger_event_id == event.id, RouteVersion.vehicle_id == vehicle_id,
                        RouteVersion.direction == direction))
                    with session.begin_nested():
                        route = generate_and_store(session, request, commit=False, trigger_event_id=event.id,
                            trigger_event_type=event.event_type, previous_summary=event.before_routes.get(f"{vehicle_id}:{direction}"))
                    state = session.get(RoutePlanState, (vehicle_id, direction))
                    item.update(generation_status=route["feasibility_status"], generated=existing is None,
                                route_id=route["route_id"], route_version=route["version"],
                                generation_timestamp=route["generated_at"], solver_runtime_seconds=route["solver_runtime_seconds"],
                                errors=route["errors"], comparison=state.comparison)
            except Exception:
                # The save is already committed. A failed solve/DB savepoint must not turn it into a save failure.
                state = session.get(RoutePlanState, (vehicle_id, direction))
                state.generation_status = "error"
                state.errors = ["Routing generation failed unexpectedly. The input change is saved; the previous plan is stale. Retry this routing event."]
                item.update(generation_status="error", errors=state.errors, comparison={})
            plans.append(item)
            if item["generation_status"] not in SUCCESS and not item["generation_status"].startswith("deferred_"):
                errors.extend(item.get("errors", []))
    statuses = {plan["generation_status"] for plan in plans}
    outcome = "failed" if errors else "deferred" if any(status.startswith("deferred_") for status in statuses) else "superseded" if "superseded" in statuses else "success"
    event.status = "routing_failed" if errors else "completed"
    event.outcome = {"outcome": outcome, "errors": list(dict.fromkeys(errors)), "plans": plans}
    event.finished_at = datetime.now(timezone.utc)
    session.commit()
    return get_event_response(session, event_id)


def process_event_safe(session, event_id):
    try:
        return process_event(session, event_id)
    except Exception:
        session.rollback()
        # Pending state from phase 1 remains durable even when PostgreSQL is temporarily unavailable.
        return {"event_id": event_id, "outcome": "failed", "generation_status": "pending",
                "errors": ["Input saved; routing failed or is unavailable. Plans remain pending/stale. Backend recovery will retry the durable event."], "plans": []}
