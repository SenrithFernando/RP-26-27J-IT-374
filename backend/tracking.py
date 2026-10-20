"""Vehicle/trip/session-bound credentials. Closed-trip backlog is explicitly rejected."""
from datetime import timedelta,datetime
import secrets
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field,AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from persistence import session_dependency
from models import (TrackingSession,LoginSession,Account,Vehicle,Trip,SyntheticTripProvenance,RouteVersion,DriverVehicle)
from auth import now,token_hash,Principal,scope_vehicle,scope_trip,deny
from positions import PositionInput,store_position
from data_provenance import snapshot_sources

router=APIRouter(tags=['Authorized tracking'])


def adult_field_test_allowed(session,trip):
    """Explicit audited exception for physical adult GPS, never synthetic replay."""
    from models import LandmarkInputEvent
    grant=(trip.pickup_settings or {}).get('adult_phone_field_test',{})
    route=session.get(RouteVersion,trip.route_id)
    event=session.get(LandmarkInputEvent,grant.get('event_id',''))
    from research_routes import is_research,participants_valid
    eligible=bool(route and (route.input_snapshot.get('daily',{}).get('scenario_id')=='MALABE_PP1' or
        (is_research(route) and participants_valid(session,route.input_snapshot['research_journey']))))
    return bool(trip.vehicle_id=='MALABE_PP1_VAN_01' and route and
        eligible and
        not session.get(SyntheticTripProvenance,trip.id) and event and
        event.payload.get('kind')=='adult_phone_field_test_authorized' and event.payload.get('trip_id')==trip.id and
        event.payload.get('route_id')==trip.route_id and not grant.get('revoked_at') and
        grant.get('expires_at') and datetime.fromisoformat(grant['expires_at'])>now() and
        (trip.pickup_settings or {}).get('mode')!='simulation_demo')


class AdultFieldTest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    trip_id:str=Field(min_length=1,max_length=64)
    reason:str=Field(min_length=10,max_length=500)
    adults_only_confirmed:bool=Field(strict=True)


@router.post('/tracking/adult-field-test')
def authorize_adult_field_test(body:AdultFieldTest,request:Request,session:Session=Depends(session_dependency)):
    from models import LandmarkInputEvent
    from landmark import digest
    from trips import today
    p=request.state.principal
    if p.user.role!='administrator' or p.login.mode!='real':deny()
    if not body.adults_only_confirmed:raise HTTPException(422,'Confirm consenting adults only, no student passengers and no measured student-trip labels.')
    trip=session.scalar(select(Trip).where(Trip.id==body.trip_id).with_for_update())
    if not trip:raise HTTPException(404,'Trip not found.')
    scope_trip(session,p,trip.id);route=session.get(RouteVersion,trip.route_id)
    from research_routes import is_research,participants_valid
    research=is_research(route)
    if trip.state not in ('PLANNED','ACTIVE') or route.service_date!=today():raise HTTPException(409,'Use an open trip for today in Asia/Colombo; no clock/date bypass.')
    if trip.vehicle_id!='MALABE_PP1_VAN_01' or (route.input_snapshot.get('daily',{}).get('scenario_id')!='MALABE_PP1' and not (research and participants_valid(session,route.input_snapshot['research_journey']))) or session.get(SyntheticTripProvenance,trip.id) or (trip.pickup_settings or {}).get('mode')=='simulation_demo':
        raise HTTPException(409,'Only the isolated Malabe landmark scenario in production-duration mode is eligible; replay fixtures remain blocked.')
    if adult_field_test_allowed(session,trip):return {'authorized':True,'trip_id':trip.id,'authorization':trip.pickup_settings['adult_phone_field_test']}
    stamp=now();event_id='ADULT_PHONE_'+uuid4().hex
    payload={'kind':'adult_phone_field_test_authorized','trip_id':trip.id,'route_id':trip.route_id,'reason':body.reason,
        'adults_only_confirmed':True,'recorded_at':stamp.isoformat(),'expires_at':(stamp+timedelta(hours=2)).isoformat(),
        'gps_context':'adult_landmark_field_test','planning_context':'landmark_test','exclude_measured_student_exports':True}
    session.add(LandmarkInputEvent(event_id=event_id,scenario_id='MALABE_PP1',payload=payload,payload_hash=digest(payload),actor_id=p.user.id,received_at=stamp))
    trip.pickup_settings={**(trip.pickup_settings or {}),'adult_phone_field_test':{**payload,'event_id':event_id}}
    session.commit();return {'authorized':True,'trip_id':trip.id,'authorization':trip.pickup_settings['adult_phone_field_test']}


class Enrollment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    vehicle_id:str=Field(min_length=1,max_length=64)
    trip_id:str=Field(min_length=1,max_length=64)
    kind:str=Field(pattern='^(phone|simulation)$')
    label:str=Field(min_length=1,max_length=100)


@router.post('/tracking/enroll',status_code=201)
def enroll(body:Enrollment,request:Request,session:Session=Depends(session_dependency)):
    p=request.state.principal
    vehicle=session.scalar(select(Vehicle).where(Vehicle.id==body.vehicle_id).with_for_update())
    if not vehicle:raise HTTPException(404,'Vehicle not found.')
    scope_vehicle(session,p,vehicle.id)
    trip=session.scalar(select(Trip).where(Trip.id==body.trip_id).with_for_update())
    if not trip or trip.vehicle_id!=vehicle.id:deny()
    scope_trip(session,p,trip.id)
    if trip.state!='ACTIVE':raise HTTPException(409,'Tracking enrollment requires an active trip.')
    from research_routes import is_research
    if is_research(session.get(RouteVersion,trip.route_id)) and body.kind!='phone':raise HTTPException(422,'Adult research trips accept the authorized operator phone only; use a separate simulation trip for replay.')
    if body.kind=='phone':
        route=session.get(RouteVersion,trip.route_id)
        from research_routes import is_research
        if is_research(route) and p.user.id!=route.input_snapshot['research_journey']['operator_id']:
            raise HTTPException(403,'Only the separately selected research operator may enroll/capture phone GPS. Driver controls remain assigned to the driver.')
        sources=list(snapshot_sources(route.input_snapshot))
        field_test=adult_field_test_allowed(session,trip)
        if p.login.mode!='real' or (not field_test and (vehicle.input_source=='simulated' or session.get(SyntheticTripProvenance,trip.id) or not sources or any(s not in ('measured','live_provider') for s in sources))):
            raise HTTPException(409,'Phone tracking requires real mode and an eligible non-synthetic trip, or explicit administrator approval for this adult Malabe landmark trip. Simulation fixtures remain blocked.')
        if trip.pickup_settings and trip.pickup_settings.get('mode')=='simulation_demo':deny()
    elif vehicle.input_source!='simulated':deny()
    token='sr_track_'+secrets.token_urlsafe(32)
    row=TrackingSession(id='DEVICE_'+uuid4().hex,token_hash=token_hash(token),login_session_id=p.login.id,
        vehicle_id=vehicle.id,trip_id=trip.id,kind=body.kind,label=body.label,created_at=now(),
        expires_at=min(p.login.expires_at,now()+timedelta(hours=2),datetime.fromisoformat(trip.pickup_settings['adult_phone_field_test']['expires_at']) if body.kind=='phone' and adult_field_test_allowed(session,trip) else p.login.expires_at))
    session.add(row);session.commit()
    return {'tracking_id':row.id,'credential':token,'vehicle_id':vehicle.id,'trip_id':trip.id,
        'observation_context':'simulation' if row.kind=='simulation' else 'adult_landmark_field_test' if adult_field_test_allowed(session,trip) else 'registered_transport',
        'source':'actual_device' if row.kind=='phone' else 'simulation','expires_at':row.expires_at,
        'queue_policy':'Closed trip uploads rejected with 409; never change current live state.'}


class TrackingPosition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sample_id:str=Field(min_length=1,max_length=128)
    recorded_at:AwareDatetime
    latitude:float=Field(ge=-90,le=90,allow_inf_nan=False)
    longitude:float=Field(ge=-180,le=180,allow_inf_nan=False)
    speed_mps:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    accuracy_m:float|None=Field(default=None,ge=0,le=100000,allow_inf_nan=False)


@router.post('/tracking/positions')
def upload(body:TrackingPosition,request:Request,session:Session=Depends(session_dependency)):
    header=request.headers.get('authorization','')
    token=header[7:] if header.startswith('Bearer sr_track_') else ''
    row=session.scalar(select(TrackingSession).where(TrackingSession.token_hash==token_hash(token))) if token else None
    if not row:raise HTTPException(401,'Scoped tracking credential required.')
    # Account -> login -> vehicle -> trip; assignment/password changes share order.
    login=session.get(LoginSession,row.login_session_id)
    user=session.scalar(select(Account).where(Account.id==login.account_id).with_for_update()) if login else None
    if login:
        session.scalar(select(LoginSession).where(LoginSession.id==login.id).with_for_update())
        session.refresh(login)
    session.refresh(row)  # Revocation may have completed while waiting for login lock.
    if not login or not user or not user.active or login.revoked_at or login.expires_at<=now() or row.revoked_at or row.expires_at<=now():
        raise HTTPException(401,'Tracking authorization expired or revoked.')
    vehicle=session.scalar(select(Vehicle).where(Vehicle.id==row.vehicle_id).with_for_update())
    p=Principal(user,login);scope_vehicle(session,p,row.vehicle_id)
    trip=session.scalar(select(Trip).where(Trip.id==row.trip_id).with_for_update())
    scope_trip(session,p,row.trip_id)
    if trip.vehicle_id!=row.vehicle_id:deny()
    if trip.state!='ACTIVE':raise HTTPException(409,'Trip closed or inactive: queued sample rejected; no live state changed.')
    if body.recorded_at<trip.started_at or body.recorded_at<row.created_at:
        raise HTTPException(422,'Sample predates the active trip or tracking enrollment.')
    if row.kind=='phone':
        if body.accuracy_m is None:raise HTTPException(422,'Phone position requires accuracy_m.')
        route=session.get(RouteVersion,trip.route_id)
        from research_routes import is_research
        if is_research(route) and user.id!=route.input_snapshot['research_journey']['operator_id']:deny()
        sources=list(snapshot_sources(route.input_snapshot))
        if login.mode!='real' or (not adult_field_test_allowed(session,trip) and (vehicle.input_source=='simulated' or session.get(SyntheticTripProvenance,trip.id) or not sources or any(s not in ('measured','live_provider') for s in sources))):deny()
    elif vehicle.input_source!='simulated':deny()
    # IDs/source are derived here; forged browser IDs/source are rejected as extra fields.
    result=store_position(row.vehicle_id,PositionInput(**body.model_dump(),trip_id=row.trip_id,
        source='actual_device' if row.kind=='phone' else 'simulation'),session,tracking_session_id=row.id)
    result['observation_context']='simulation' if row.kind=='simulation' else 'adult_landmark_field_test' if (trip.pickup_settings or {}).get('adult_phone_field_test') else 'registered_transport'
    return result


@router.get('/auth/tracking')
def sessions(request:Request,session:Session=Depends(session_dependency)):
    p=request.state.principal
    query=select(TrackingSession).join(LoginSession).where(LoginSession.account_id==p.user.id)
    if p.user.role=='driver':query=query.where(TrackingSession.vehicle_id.in_(select(DriverVehicle.vehicle_id).where(DriverVehicle.account_id==p.user.id)))
    if p.login.mode=='demo':query=query.where(TrackingSession.vehicle_id.in_(select(Vehicle.id).where(Vehicle.input_source=='simulated')))
    return [{'id':r.id,'vehicle_id':r.vehicle_id,'trip_id':r.trip_id,'kind':r.kind,'expires_at':r.expires_at,
        'revoked_at':r.revoked_at,'label':r.label} for r in session.scalars(query).all()]


@router.post('/tracking/{tracking_id}/revoke')
def revoke(tracking_id:str,request:Request,session:Session=Depends(session_dependency)):
    row=session.get(TrackingSession,tracking_id)
    if not row:raise HTTPException(404,'Tracking session not found.')
    owner=session.get(LoginSession,row.login_session_id)
    session.scalar(select(Account).where(Account.id==owner.account_id).with_for_update())
    session.scalar(select(LoginSession).where(LoginSession.id==row.login_session_id).with_for_update())
    scope_vehicle(session,request.state.principal,row.vehicle_id)
    row.revoked_at=row.revoked_at or now();session.commit();return {'revoked':True}
