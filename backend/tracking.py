"""Vehicle/trip/session-bound credentials. Closed-trip backlog is explicitly rejected."""
from datetime import timedelta
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
    if body.kind=='phone':
        route=session.get(RouteVersion,trip.route_id)
        sources=list(snapshot_sources(route.input_snapshot))
        if p.login.mode!='real' or vehicle.input_source=='simulated' or session.get(SyntheticTripProvenance,trip.id) or not sources or any(s not in ('measured','live_provider') for s in sources):
            raise HTTPException(409,'Phone tracking requires real mode and non-synthetic trip context.')
        if trip.pickup_settings and trip.pickup_settings.get('mode')=='simulation_demo':deny()
    elif vehicle.input_source!='simulated':deny()
    token='sr_track_'+secrets.token_urlsafe(32)
    row=TrackingSession(id='DEVICE_'+uuid4().hex,token_hash=token_hash(token),login_session_id=p.login.id,
        vehicle_id=vehicle.id,trip_id=trip.id,kind=body.kind,label=body.label,created_at=now(),
        expires_at=min(p.login.expires_at,now()+timedelta(hours=2)))
    session.add(row);session.commit()
    return {'tracking_id':row.id,'credential':token,'vehicle_id':vehicle.id,'trip_id':trip.id,
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
        sources=list(snapshot_sources(route.input_snapshot))
        if login.mode!='real' or vehicle.input_source=='simulated' or session.get(SyntheticTripProvenance,trip.id) or not sources or any(s not in ('measured','live_provider') for s in sources):deny()
    elif vehicle.input_source!='simulated':deny()
    # IDs/source are derived here; forged browser IDs/source are rejected as extra fields.
    return store_position(row.vehicle_id,PositionInput(**body.model_dump(),trip_id=row.trip_id,
        source='actual_device' if row.kind=='phone' else 'simulation'),session,tracking_session_id=row.id)


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
