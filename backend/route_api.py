from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import School, Student
from persistence import SchoolRecord, SchoolMutationRecord, session_dependency
from planning_orchestration import columns, mutate_and_plan
from route_schemas import Direction, GenerateRouteRequest, GeneratedRouteResponse, SchoolSchedule
from route_service import generate_and_store, latest_route
from traffic_provider import provider_status

router = APIRouter(tags=["Database route optimization"])


@router.get('/traffic/status')
def traffic_status(): return provider_status()


@router.post("/routes/generate", response_model=GeneratedRouteResponse, status_code=201)
def generate(request: GenerateRouteRequest, session: Session = Depends(session_dependency)):
    return generate_and_store(session, request)


@router.get("/routes/latest", response_model=GeneratedRouteResponse)
def latest(vehicle_id: str = Query(min_length=1, max_length=64), direction: Direction = Query(),
           session: Session = Depends(session_dependency)):
    return latest_route(session, vehicle_id, direction)


@router.put("/routing/schools/{school_id}/schedule", response_model=SchoolMutationRecord)
def school_schedule(school_id: str, payload: SchoolSchedule, session: Session = Depends(session_dependency),
                    request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        school = session.get(School, school_id)
        if school is None: raise HTTPException(404, "School not found.")
        before = columns(school)
        school.morning_deadline_seconds = payload.morning_deadline_seconds
        school.afternoon_finish_seconds = payload.afternoon_finish_seconds
        affected = session.scalars(select(Student.vehicle_id).where(Student.school_id == school_id, Student.active.is_(True)).distinct()).all()
        return school, affected, before
    return mutate_and_plan(session, event_type="school_schedule_edited", entity_id=school_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=SchoolRecord, mutation=change)
