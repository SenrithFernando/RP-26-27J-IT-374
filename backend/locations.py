from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import School, Student, Vehicle
from persistence import SchoolRecord, VehicleRecord, SchoolMutationRecord, VehicleMutationRecord, session_dependency
from planning_orchestration import columns, mutate_and_plan

router = APIRouter(prefix="/routing", tags=["Locations"])


class ConfirmedLocation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    address: str = Field(min_length=1, max_length=500)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    location_confirmed: Literal[True]
    location_method: Literal["manual", "google", "manual_correction"] = "manual"


@router.put("/schools/{school_id}/location", response_model=SchoolMutationRecord)
def school_location(school_id: str, payload: ConfirmedLocation, session: Session = Depends(session_dependency),
                    request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        school = session.get(School, school_id)
        if school is None: raise HTTPException(404, "School not found.")
        before = columns(school)
        for key, value in payload.model_dump().items(): setattr(school, key, value)
        affected = session.scalars(select(Student.vehicle_id).where(Student.school_id == school_id, Student.active.is_(True)).distinct()).all()
        return school, affected, before
    return mutate_and_plan(session, event_type="school_location_edited", entity_id=school_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=SchoolRecord, mutation=change)


@router.put("/vehicles/{vehicle_id}/locations/{position}", response_model=VehicleMutationRecord)
def vehicle_location(vehicle_id: str, position: Literal["start", "end"], payload: ConfirmedLocation,
                     session: Session = Depends(session_dependency),
                     request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None: raise HTTPException(404, "Vehicle not found.")
        before = columns(vehicle)
        values = {"address": payload.address, "latitude": payload.latitude, "longitude": payload.longitude,
                  "confirmed": payload.location_confirmed, "method": payload.location_method}
        for key, value in values.items(): setattr(vehicle, f"{position}_{key}", value)
        return vehicle, [vehicle_id], before
    return mutate_and_plan(session, event_type=f"vehicle_{position}_edited", entity_id=vehicle_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=VehicleRecord, mutation=change)


@router.get("/map-locations/{vehicle_id}")
def map_locations(vehicle_id: str, direction: Literal["morning", "afternoon"] = "morning",
                  session: Session = Depends(session_dependency)):
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(404, "Vehicle not found.")
    points = []
    missing = []

    def add(key, location_id, name, kind, latitude, longitude, confirmed, address, source, method):
        if not confirmed or latitude is None or longitude is None:
            missing.append(name)
            return
        points.append({"id": key, "location_id": location_id, "name": name, "kind": kind,
                       "latitude": latitude, "longitude": longitude, "address": address,
                       "input_source": source, "location_method": method,
                       "location_input_source": "live_provider" if method == "google" else source})

    for position in ("start", "end"):
        is_depot = (direction == "morning" and position == "start") or (direction == "afternoon" and position == "end")
        add(f"{vehicle.id}:{position}", "DEPOT" if is_depot else f"{vehicle.id}:{position}",
            f"{vehicle.id} {position}", f"vehicle_{position}",
            getattr(vehicle, f"{position}_latitude"), getattr(vehicle, f"{position}_longitude"),
            getattr(vehicle, f"{position}_confirmed"), getattr(vehicle, f"{position}_address"),
            vehicle.input_source, getattr(vehicle, f"{position}_method"))
    students = session.scalars(select(Student).where(Student.vehicle_id == vehicle_id, Student.active.is_(True)).order_by(Student.id)).all()
    for student in students:
        add(student.id, student.home_id, student.name, "home", student.home_latitude, student.home_longitude,
            student.location_confirmed, student.home_address, student.input_source, student.location_method)
    school_ids = {student.school_id for student in students}
    if school_ids:
        for school in session.scalars(select(School).where(School.id.in_(school_ids)).order_by(School.id)):
            add(school.id, school.id, school.name, "school", school.latitude, school.longitude,
                school.location_confirmed, school.address, school.input_source, school.location_method)
    return {"vehicle_id": vehicle_id, "direction": direction, "points": points, "missing_locations": missing}
