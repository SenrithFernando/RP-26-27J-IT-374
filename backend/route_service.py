"""Capture a registered roster, solve it, and persist an immutable version."""
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from models import RouteStop, RouteVersion, School, Student, Vehicle
from route_schemas import GenerateRouteRequest
from routing_domain import GenerationSettings, Location, RegisteredSchool, RegisteredStudent, RegisteredVehicle
from route_solver import solve_registered_route, failure
from planning_state import execution_guard, freshness, newest, planning_lock, set_generated_state, summary
from traffic_provider import TrafficSnapshotProvider


def location(latitude, longitude, confirmed, address, source, method):
    return Location(latitude, longitude, confirmed, address, source, method)


def local_timestamp(service_date, seconds):
    midnight = datetime.combine(service_date, time(), tzinfo=ZoneInfo("Asia/Colombo"))
    return (midnight + timedelta(seconds=seconds)).isoformat()


def serialize_version(session: Session, version: RouteVersion):
    # Stored JSON and ordered stop rows only. No provider or solver call here.
    stops = session.scalars(select(RouteStop).where(RouteStop.route_id == version.id).order_by(RouteStop.sequence)).all()
    student_names = {student['id']: student.get('name') for student in version.input_snapshot.get('students', [])}
    school_names = {key: school.get('name') for key, school in version.input_snapshot.get('schools', {}).items()}
    return {**version.result, **freshness(session, version), "route_id": version.id, "version": version.version,
            "vehicle_id": version.vehicle_id, "direction": version.direction,
            "service_date": version.service_date.isoformat(), "departure_seconds": version.departure_seconds,
            "departure": local_timestamp(version.service_date, version.departure_seconds),
            "generated_at": version.created_at.isoformat(), "timezone": "Asia/Colombo",
            "request_settings": version.request_settings, "stops": [
                {**stop.details, 'student_name': student_names.get(stop.student_id),
                 'school_name': school_names.get(stop.details.get('school_id'))} for stop in stops]}


def latest_route(session: Session, vehicle_id: str, direction: str):
    version = session.scalar(select(RouteVersion).where(RouteVersion.vehicle_id == vehicle_id, RouteVersion.direction == direction)
                             .order_by(RouteVersion.version.desc()).limit(1))
    if version is None:
        raise HTTPException(404, f"No stored {direction} route for {vehicle_id}. Generate it first.")
    return serialize_version(session, version)


def generate_and_store(session: Session, request: GenerateRouteRequest, *, commit=True, trigger_event_id=None, trigger_event_type="manual_generation", previous_summary=None):
    planning_lock(session)
    if execution_guard(session, request.vehicle_id, request.direction, request.service_date):
        raise HTTPException(409, "This direction has an active/completed execution snapshot. Pre-trip generation cannot reorder or reset it.")
    if trigger_event_id:
        existing = session.scalar(select(RouteVersion).where(RouteVersion.trigger_event_id == trigger_event_id, RouteVersion.vehicle_id == request.vehicle_id, RouteVersion.direction == request.direction))
        if existing: return serialize_version(session, existing)
    prior = previous_summary if previous_summary is not None else summary(session, newest(session, request.vehicle_id, request.direction))
    # Serialize version allocation and hold the input rows stable during the bounded solve.
    vehicle_row = session.scalar(select(Vehicle).where(Vehicle.id == request.vehicle_id).with_for_update())
    if vehicle_row is None:
        raise HTTPException(404, "Registered vehicle not found.")
    # Lock inactive registrations too: reactivation cannot change the roster mid-solve.
    registered_rows = session.scalars(select(Student).where(Student.vehicle_id == vehicle_row.id)
                                      .order_by(Student.id).with_for_update()).all()
    student_rows = [student for student in registered_rows if student.active]
    school_ids = {student.school_id for student in student_rows}
    school_rows = session.scalars(select(School).where(School.id.in_(school_ids)).order_by(School.id).with_for_update()).all() if school_ids else []
    vehicle = RegisteredVehicle(vehicle_row.id, vehicle_row.capacity,
        location(vehicle_row.start_latitude, vehicle_row.start_longitude, vehicle_row.start_confirmed, vehicle_row.start_address, vehicle_row.input_source, vehicle_row.start_method),
        location(vehicle_row.end_latitude, vehicle_row.end_longitude, vehicle_row.end_confirmed, vehicle_row.end_address, vehicle_row.input_source, vehicle_row.end_method))
    students = [RegisteredStudent(row.id, row.name, row.home_id,
                location(row.home_latitude, row.home_longitude, row.location_confirmed, row.home_address, row.input_source, row.location_method),
                row.school_id, row.vehicle_id) for row in student_rows]
    schools = {row.id: RegisteredSchool(row.id, row.name,
                location(row.latitude, row.longitude, row.location_confirmed, row.address, row.input_source, row.location_method),
                row.morning_deadline_seconds, row.afternoon_finish_seconds) for row in school_rows}
    settings = GenerationSettings(request.direction, request.departure_seconds, request.pickup_service_seconds,
                                  request.delivery_service_seconds, request.max_route_seconds, request.solver_time_limit_seconds)
    provider = TrafficSnapshotProvider(request)
    prior_version = newest(session, request.vehicle_id, request.direction)
    provider.reference_stops = [s.details for s in session.scalars(select(RouteStop).where(RouteStop.route_id == prior_version.id).order_by(RouteStop.sequence))] if prior_version else None
    result = solve_registered_route(vehicle, students, schools, settings, provider) if students else failure("empty", ["No active students assigned; no pre-trip route is required."])
    result['road_geometry'] = {'status': 'unavailable', 'reason': 'This estimate has no configured road geometry; display stop sequence only.'}
    if request.provider == 'google' and request.include_geometry and result['feasibility_status'] == 'feasible':
        stamp = datetime.fromisoformat(result['provider_source']['departure_timestamp'])
        if request.force_live_failure or 'google_live' in result['provider_source'].get('route_source_counts', {}):
            result['road_geometry'] = provider.live.geometry(result['stops'], stamp, request.force_live_failure)
        else:
            result['road_geometry'] = {'status': 'unavailable', 'reason': 'Live matrix was unavailable; no additional road-geometry request was made. Showing stop sequence.'}
    if result["provider_source"] is None:
        result["provider_source"] = {"provider": "unavailable", "duration_source": "unavailable", "requested_provider": request.provider,
                                     "distance_source": "haversine_straight_line", "distance_is_approximate": True,
                                     "costs_computed": False}
    result["student_count"] = len(students)
    result["capacity"] = vehicle.capacity
    result["assignment_policy"] = "PP1 fixed registered vehicle assignments; no reassignment or dropped active students."
    stops = result.pop("stops")
    for stop in stops:
        stop["arrival"] = local_timestamp(request.service_date, stop["arrival_seconds"])
        stop["eta"] = local_timestamp(request.service_date, stop["eta_seconds"])
        stop["departure"] = local_timestamp(request.service_date, stop["departure_seconds"])
    previous = session.scalar(select(func.max(RouteVersion.version)).where(RouteVersion.vehicle_id == vehicle.id, RouteVersion.direction == request.direction)) or 0
    version = RouteVersion(created_at=datetime.now(timezone.utc), id=f"ROUTE_{uuid4().hex}", vehicle_id=vehicle.id, direction=request.direction,
        version=previous + 1, roster_version=vehicle_row.roster_version, trigger_event_id=trigger_event_id, trigger_event_type=trigger_event_type, execution_status="pre_trip", service_date=request.service_date, departure_seconds=request.departure_seconds,
        feasibility_status=result["feasibility_status"], request_settings=request.model_dump(mode="json"),
        input_snapshot={"vehicle": asdict(vehicle), "students": [asdict(student) for student in students],
                        "schools": {key: asdict(school) for key, school in schools.items()}}, result=result)
    session.add(version)
    session.flush()
    for stop in stops:
        session.add(RouteStop(route_id=version.id, sequence=stop["sequence"], action=stop["action"], student_id=stop["student_id"],
                              location_id=stop["location_id"], latitude=stop["latitude"], longitude=stop["longitude"],
                              eta_seconds=stop["eta_seconds"], details=stop))
    session.flush()
    set_generated_state(session, version, prior)
    if commit: session.commit()
    return serialize_version(session, version)
