from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import School, Student
from persistence import SchoolRecord, SchoolMutationRecord, session_dependency
from planning_orchestration import columns, mutate_and_plan
from route_schemas import Direction, GenerateRouteRequest, GeneratedRouteResponse, SchoolSchedule
from route_service import generate_and_store, latest_route
from traffic_provider import provider_status
from datetime import date

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


@router.get('/routes/published')
def published(request:Request,vehicle_id:str,direction:Direction,service_date:date,session:Session=Depends(session_dependency)):
    """Provisional driver contract: read saved publication and pinned trip, never solve."""
    from landmark import scenario_for_vehicle
    from models import LandmarkDailyPlan,RouteVersion,Trip
    from route_service import serialize_version
    from trips import serialize_trip
    from sqlalchemy import case,or_
    scenario=scenario_for_vehicle(session,vehicle_id)
    state=session.get(LandmarkDailyPlan,(scenario.id,service_date,direction)) if scenario else None
    row=session.get(RouteVersion,state.route_id) if state and state.route_id else None
    if row and (row.vehicle_id!=vehicle_id or row.direction!=direction or row.service_date!=service_date):
        raise HTTPException(409,'Publication snapshot does not match selected vehicle/date/direction.')
    from auth import scope_route,scope_trip
    if row:scope_route(session,request.state.principal,row.id)
    status=state.publication if state else 'not_published'
    route=serialize_version(session,row) if row and status=='published' else None
    if route and (route['planning_status']=='stale' or route['feasibility_status']!='feasible'):
        status='stale';route=None
    trip=session.scalar(select(Trip).join(RouteVersion,RouteVersion.id==Trip.route_id).where(Trip.vehicle_id==vehicle_id,
        # An active vehicle trip stays visible, but closed/planned research journeys
        # belong to the separate research workspace, not school instructions.
        or_(Trip.state=='ACTIVE',(RouteVersion.service_date==service_date)&(Trip.direction==direction)&
            RouteVersion.input_snapshot['research_journey'].astext.is_(None)))
        .order_by(case((Trip.state=='ACTIVE',0),else_=1),Trip.created_at.desc(),Trip.id).limit(1))
    if trip:scope_trip(session,request.state.principal,trip.id)
    return {'contract_version':'saferide-driver-plan-provisional/v1','vehicle_id':vehicle_id,'service_date':str(service_date),
        'direction':direction,'timezone':'Asia/Colombo','publication_status':status,'published_route':route,
        'trip':serialize_trip(session,trip) if trip else None,'integration_status':'API-ready; Hasara app not connected',
        'note':'Published planning route and active trip route are separate saved snapshots. GET does not optimize.'}


@router.put("/routing/schools/{school_id}/schedule", response_model=SchoolMutationRecord)
def school_schedule(school_id: str, payload: SchoolSchedule, session: Session = Depends(session_dependency),
                    request_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=128)):
    def change():
        school = session.get(School, school_id)
        if school is None: raise HTTPException(404, "School not found.")
        from landmark import PREFIX,SCHOOLS
        if school_id in [PREFIX+k for k in SCHOOLS] and (payload.morning_deadline_seconds!=26100 or payload.afternoon_finish_seconds!=48600):
            raise HTTPException(422,'Malabe test policy fixes hard arrival at 07:15 and release at 13:30; it cannot be silently relaxed here.')
        before = columns(school)
        school.morning_deadline_seconds = payload.morning_deadline_seconds
        school.afternoon_finish_seconds = payload.afternoon_finish_seconds
        affected = session.scalars(select(Student.vehicle_id).where(Student.school_id == school_id, Student.active.is_(True)).distinct()).all()
        return school, affected, before
    return mutate_and_plan(session, event_type="school_schedule_edited", entity_id=school_id, payload=payload.model_dump(),
                           request_key=request_key, record_schema=SchoolRecord, mutation=change)
