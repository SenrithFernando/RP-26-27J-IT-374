from fastapi import APIRouter, Depends, Header, HTTPException, Request
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from database import get_session
from models import School, Student, Vehicle
from planning_orchestration import columns, mutate_and_plan

router = APIRouter(prefix="/routing", tags=["Persistent routing records"])


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    input_source: str


class SchoolRecord(Record):
    name: str
    morning_deadline_seconds: int | None
    afternoon_finish_seconds: int | None
    address: str
    latitude: float | None
    longitude: float | None
    location_confirmed: bool
    location_method: str


class VehicleRecord(Record):
    capacity: int
    start_address: str
    start_latitude: float | None
    start_longitude: float | None
    start_confirmed: bool
    start_method: str
    end_address: str
    end_latitude: float | None
    end_longitude: float | None
    end_confirmed: bool
    end_method: str


class StudentRecord(Record):
    name: str
    home_id: str
    school_id: str
    vehicle_id: str
    home_latitude: float | None
    home_longitude: float | None
    active: bool
    home_address: str
    location_confirmed: bool
    location_method: str


class StudentMutationRecord(StudentRecord):
    save_status: str
    routing: dict


class SchoolMutationRecord(SchoolRecord):
    save_status: str
    routing: dict


class VehicleMutationRecord(VehicleRecord):
    save_status: str
    routing: dict


def session_dependency():
    try:
        yield from get_session()
    except (SQLAlchemyError, RuntimeError, ValueError):
        # Never expose database URLs, parameters or driver exception details.
        raise HTTPException(503, "Routing database unavailable. Check local configuration and run migrations.") from None


@router.get("/health")
def database_health(session: Session = Depends(session_dependency)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "storage": "postgresql"}


@router.get("/schools", response_model=list[SchoolRecord])
def schools(session: Session = Depends(session_dependency),request:Request=None):
    query=select(School)
    if request:
        from models import DriverVehicle,ParentStudent
        p=request.state.principal
        if p.user.role=='parent':query=query.where(School.id.in_(select(Student.school_id).join(ParentStudent,ParentStudent.student_id==Student.id).where(ParentStudent.account_id==p.user.id)))
        if p.user.role=='driver':query=query.where(School.id.in_(select(Student.school_id).join(DriverVehicle,DriverVehicle.vehicle_id==Student.vehicle_id).where(DriverVehicle.account_id==p.user.id)))
        if p.login.mode=='demo':query=query.where(School.input_source=='simulated')
    return session.scalars(query.order_by(School.id)).all()


@router.get("/vehicles", response_model=list[VehicleRecord])
def vehicles(session: Session = Depends(session_dependency),request:Request=None):
    query=select(Vehicle)
    if request:
        from models import DriverVehicle
        p=request.state.principal
        if p.user.role=='driver':query=query.where(Vehicle.id.in_(select(DriverVehicle.vehicle_id).where(DriverVehicle.account_id==p.user.id)))
        if p.login.mode=='demo':query=query.where(Vehicle.input_source=='simulated')
    rows=session.scalars(query.order_by(Vehicle.id)).all()
    if request:
        from auth import scope_vehicle
        rows=[r for r in rows if scope_vehicle(session,request.state.principal,r.id)]
    return rows


@router.get("/students", response_model=list[StudentRecord])
def students(session: Session = Depends(session_dependency),request:Request=None):
    query=select(Student)
    if request:
        from models import DriverVehicle,ParentStudent
        p=request.state.principal
        if p.user.role=='parent':query=query.where(Student.id.in_(select(ParentStudent.student_id).where(ParentStudent.account_id==p.user.id)))
        if p.user.role=='driver':query=query.where(Student.vehicle_id.in_(select(DriverVehicle.vehicle_id).where(DriverVehicle.account_id==p.user.id)))
        if p.login.mode=='demo':query=query.where(Student.input_source=='simulated',
            Student.vehicle_id.in_(select(Vehicle.id).where(Vehicle.input_source=='simulated')),
            Student.school_id.in_(select(School.id).where(School.input_source=='simulated')))
    return session.scalars(query.order_by(Student.id)).all()


class StudentWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    school_id: str = Field(min_length=1, max_length=64)
    vehicle_id: str = Field(min_length=1, max_length=64)
    home_latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    home_longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    input_source: Literal["simulated", "live_provider", "measured"]
    home_address: str = Field(min_length=1, max_length=500)
    location_confirmed: Literal[True]
    location_method: Literal["manual", "google", "manual_correction"] = "manual"


class StudentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    active: bool


class StudentTransfer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    vehicle_id: str = Field(min_length=1, max_length=64)


def find_student(session: Session, student_id: str):
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Student not found.")
    return student


def validate_vehicle(session: Session, vehicle_id: str):
    if session.get(Vehicle, vehicle_id) is None:
        raise HTTPException(422, "Select an existing vehicle.")


def validate_assignment(session: Session, payload: StudentWrite):
    if session.get(School, payload.school_id) is None:
        raise HTTPException(422, "Select an existing school.")
    validate_vehicle(session, payload.vehicle_id)


@router.post("/students", response_model=StudentMutationRecord, status_code=201)
def create_student(payload: StudentWrite, session: Session = Depends(session_dependency),
                   request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        validate_assignment(session, payload)
        student = Student(id=f"STU_{uuid4().hex}", home_id=f"HOME_{uuid4().hex}", active=True, **payload.model_dump())
        session.add(student)
        return student, [student.vehicle_id], None
    return mutate_and_plan(session, event_type="student_added", entity_id="", payload=payload.model_dump(),
                           request_key=request_key, record_schema=StudentRecord, mutation=change)


@router.put("/students/{student_id}", response_model=StudentMutationRecord)
def update_student(student_id: str, payload: StudentWrite, session: Session = Depends(session_dependency),
                   request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        student = find_student(session, student_id); before = columns(student)
        validate_assignment(session, payload)
        old_vehicle = student.vehicle_id
        for key, value in payload.model_dump().items(): setattr(student, key, value)
        return student, [old_vehicle, student.vehicle_id], before
    return mutate_and_plan(session, event_type="student_edited", entity_id=student_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=StudentRecord, mutation=change)


@router.patch("/students/{student_id}/status", response_model=StudentMutationRecord)
def change_student_status(student_id: str, payload: StudentStatus, session: Session = Depends(session_dependency),
                          request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        student = find_student(session, student_id); before = columns(student)
        student.active = payload.active
        return student, [student.vehicle_id], before
    return mutate_and_plan(session, event_type="student_reactivated" if payload.active else "student_deactivated", entity_id=student_id,
                           payload=payload.model_dump(), request_key=request_key, record_schema=StudentRecord, mutation=change)


@router.patch("/students/{student_id}/vehicle", response_model=StudentMutationRecord)
def transfer_student(student_id: str, payload: StudentTransfer, session: Session = Depends(session_dependency),
                     request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        student = find_student(session, student_id); before = columns(student)
        validate_vehicle(session, payload.vehicle_id)
        old_vehicle = student.vehicle_id; student.vehicle_id = payload.vehicle_id
        return student, [old_vehicle, student.vehicle_id], before
    return mutate_and_plan(session, event_type="student_transferred", entity_id=student_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=StudentRecord, mutation=change)


@router.delete("/students/{student_id}", response_model=StudentMutationRecord)
def remove_student(student_id: str, session: Session = Depends(session_dependency),
                   request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        student = find_student(session, student_id); before = columns(student)
        student.active = False  # Soft removal preserves route/student references.
        return student, [student.vehicle_id], before
    return mutate_and_plan(session, event_type="student_removed", entity_id=student_id, payload={},
                           request_key=request_key, record_schema=StudentRecord, mutation=change)
