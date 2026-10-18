"""Opaque bearer login sessions and fail-closed object-level API authorization.

No authentication cookies, URL tokens, public signup, or demo bypass. Raw tokens
are returned once; only SHA-256 digests of random 256-bit tokens are persisted.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import secrets
from uuid import uuid4
from collections import OrderedDict
from threading import Lock
from time import monotonic
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,update,case,or_
from sqlalchemy.orm import Session
from persistence import session_dependency
from models import (Account,LoginSession,TrackingSession,DriverVehicle,ParentStudent,
    Vehicle,Student,School,Trip,RouteVersion,RoutingEvent,MissedPickupNotification)
from data_provenance import snapshot_sources

router=APIRouter(tags=['Authentication and access'])
bearer=HTTPBearer(auto_error=False)
hasher=PasswordHasher()
_dummy=hasher.hash(secrets.token_urlsafe(32))
SESSION_HOURS=8
_attempts=OrderedDict()
_rate_lock=Lock()


def login_rate(request):
    key=request.client.host if request.client else 'unknown'
    stamp=monotonic()
    with _rate_lock:
        entries=[t for t in _attempts.pop(key,[]) if stamp-t<60]
        _attempts[key]=entries+[stamp]
        while len(_attempts)>1024:_attempts.popitem(last=False)
        if len(entries)>=20:raise HTTPException(429,'Too many login attempts; retry later.')


def now():return datetime.now(timezone.utc)
def token_hash(token):return sha256(token.encode()).hexdigest()
def deny():raise HTTPException(403,'Not authorized for this resource.')


@dataclass
class Principal:
    user: Account
    login: LoginSession


def authenticate(session,token):
    if not token or not token.startswith('sr_user_'):raise HTTPException(401,'Login required.')
    login=session.scalar(select(LoginSession).where(LoginSession.token_hash==token_hash(token)))
    user=session.scalar(select(Account).where(Account.id==login.account_id).with_for_update()) if login else None
    if login:
        session.scalar(select(LoginSession).where(LoginSession.id==login.id).with_for_update())
        session.refresh(login)
    if not login or login.revoked_at or login.expires_at<=now() or not user or not user.active:
        raise HTTPException(401,'Session expired or revoked; log in again.')
    return Principal(user,login)


def scope_vehicle(session,p,vehicle_id):
    vehicle=session.get(Vehicle,vehicle_id)
    if not vehicle:raise HTTPException(404,'Resource not found.')
    if p.user.role!='administrator' and (p.user.role!='driver' or not session.get(DriverVehicle,(p.user.id,vehicle_id))):deny()
    if p.login.mode=='demo':
        if vehicle.input_source!='simulated':deny()
        students=session.scalars(select(Student).where(Student.vehicle_id==vehicle_id)).all()
        if any(s.input_source!='simulated' or session.get(School,s.school_id).input_source!='simulated' for s in students):deny()
    return vehicle


def scope_student(session,p,student_id):
    student=session.get(Student,student_id)
    if not student:raise HTTPException(404,'Resource not found.')
    if p.user.role=='parent':
        if not session.get(ParentStudent,(p.user.id,student_id)):deny()
    else:scope_vehicle(session,p,student.vehicle_id)
    if p.login.mode=='demo' and (student.input_source!='simulated' or session.get(Vehicle,student.vehicle_id).input_source!='simulated' or session.get(School,student.school_id).input_source!='simulated'):deny()
    return student


def scope_route(session,p,route_id):
    route=session.get(RouteVersion,route_id)
    if not route:raise HTTPException(404,'Resource not found.')
    scope_vehicle(session,p,route.vehicle_id)
    sources=list(snapshot_sources(route.input_snapshot))
    if p.login.mode=='demo' and (not sources or set(sources)!={'simulated'}):deny()
    return route


def scope_trip(session,p,trip_id):
    trip=session.get(Trip,trip_id)
    if not trip:raise HTTPException(404,'Resource not found.')
    scope_route(session,p,trip.route_id)
    return trip


async def authorize(request:Request,credential:HTTPAuthorizationCredentials|None=Depends(bearer),session:Session=Depends(session_dependency)):
    body=await request.json() if request.method in ('POST','PUT','PATCH') and request.headers.get('content-type','').startswith('application/json') else {}
    # Row-lock waits must never block the event loop: an earlier request may
    # need that loop to finish and release the very same transaction lock.
    return await run_in_threadpool(authorize_sync,request,credential,session,body)


def authorize_sync(request,credential,session,body):
    path=request.url.path
    if path in ('/','/health','/auth/login'):return
    # Upload credential is intentionally not a login credential. Bound checks are
    # performed inside tracking.py under vehicle/login/trip locks.
    if path=='/tracking/positions':return
    p=authenticate(session,credential.credentials if credential else None)
    request.state.principal=p
    if path.startswith('/daily-plan'):
        if p.user.role!='administrator' or p.login.mode!='real':deny()
        return
    method=request.method
    if path=='/auth/tracking' and p.user.role not in ('administrator','driver'):deny()
    if method=='GET' and path in ('/auth/me','/auth/tracking','/pickup-policy','/ml/status','/traffic/status'):return
    if path=='/auth/logout':return
    if not isinstance(body,dict):raise HTTPException(422,'Expected an object.')
    parts=path.strip('/').split('/')
    if path.startswith('/parent/students/'):
        scope_student(session,p,parts[2]);return
    if path=='/tracking/enroll':
        scope_vehicle(session,p,body.get('vehicle_id'));scope_trip(session,p,body.get('trip_id'));return
    if path.startswith('/tracking/') and path.endswith('/revoke'):
        tracking=session.get(TrackingSession,parts[1])
        if not tracking:raise HTTPException(404,'Tracking session not found.')
        scope_vehicle(session,p,tracking.vehicle_id)
        if p.user.role!='administrator' and session.get(LoginSession,tracking.login_session_id).account_id!=p.user.id:deny()
        return
    if path=='/routing/students' and method=='GET':return
    if path=='/routing/schools' and method=='GET':return
    if path=='/routing/vehicles' and method=='GET':
        if p.user.role not in ('administrator','driver'):deny()
        return
    if path.startswith('/routing/notifications'):
        recipient=request.query_params.get('recipient') if method=='GET' else body.get('recipient')
        student_id=request.query_params.get('student_id') if method=='GET' else body.get('student_id')
        if p.user.role=='parent':
            if recipient!='parent' or not student_id:deny()
            scope_student(session,p,student_id)
        elif p.user.role!='administrator':deny()
        if len(parts)>=3:
            notice=session.get(MissedPickupNotification,parts[2])
            if not notice:raise HTTPException(404,'Notification not found.')
            scope_student(session,p,notice.student_id)
            if p.user.role=='parent' and notice.student_id!=student_id:deny()
            if p.login.mode=='demo':
                route=session.get(RouteVersion,notice.route_id)
                sources=list(snapshot_sources(route.input_snapshot)) if route else []
                if not sources or set(sources)!={'simulated'}:deny()
        elif student_id:scope_student(session,p,student_id)
        return
    if path in ('/routes/latest','/trips/current'):
        vehicle_id=request.query_params.get('vehicle_id');scope_vehicle(session,p,vehicle_id)
        direction=request.query_params.get('direction')
        if path=='/routes/latest':
            route=session.scalar(select(RouteVersion).where(RouteVersion.vehicle_id==vehicle_id,RouteVersion.direction==direction).order_by(RouteVersion.version.desc()).limit(1))
            if route:scope_route(session,p,route.id)
        else:
            query=select(Trip).where(Trip.vehicle_id==vehicle_id)
            if direction:query=query.where(or_(Trip.state=='ACTIVE',Trip.direction==direction))
            trip=session.scalar(query.order_by(case((Trip.state=='ACTIVE',0),else_=1),Trip.created_at.desc(),Trip.id).limit(1))
            if trip:scope_trip(session,p,trip.id)
        return
    if parts[0]=='trips':
        if len(parts)==1 and method=='POST':scope_route(session,p,body.get('route_id'));return
        if len(parts)>1:scope_trip(session,p,parts[1]);return
    if parts[0]=='routes' and len(parts)==3 and parts[2] in ('map-image','planning-lock'):
        scope_route(session,p,parts[1])
        if p.login.mode=='demo' and parts[2]=='map-image':deny()
        if method!='GET' and p.user.role!='administrator':deny()
        return
    if path.startswith('/routing/map-locations/'):
        scope_vehicle(session,p,parts[-1]);return
    if path.startswith('/routing/plans/'):
        scope_vehicle(session,p,parts[2]);return
    if path.startswith('/routing/vehicles/') and 'positions' in parts:
        scope_vehicle(session,p,parts[2])
        if request.query_params.get('trip_id'):scope_trip(session,p,request.query_params['trip_id'])
        if method=='POST':
            # Legacy path is AUTHENTICATED SIMULATION ONLY; phone uses scoped credential.
            if body.get('source')!='simulation':deny()
            vehicle=session.get(Vehicle,parts[2])
            if vehicle.input_source!='simulated':deny()
            if body.get('trip_id'):
                trip=scope_trip(session,p,body['trip_id'])
                if trip.vehicle_id!=vehicle.id:deny()
                if trip.state!='ACTIVE':raise HTTPException(409,'Simulation trip is not active; queued samples rejected.')
        return
    # Everything else is administrator-only, including transport mutations,
    # generation, ML prediction, exports, assignments and legacy demo endpoints.
    if p.user.role!='administrator':deny()
    if path=='/routes/generate':scope_vehicle(session,p,body.get('vehicle_id'))
    if path.startswith('/routing/students/') or path=='/routing/students':
        if len(parts)>2:scope_student(session,p,parts[2])
        if body.get('vehicle_id'):scope_vehicle(session,p,body['vehicle_id'])
        if p.login.mode=='demo' and (body.get('input_source','simulated')!='simulated' or body.get('location_method')=='google'):deny()
        if p.login.mode=='demo' and body.get('school_id'):
            school=session.get(School,body['school_id'])
            if not school or school.input_source!='simulated':deny()
    if path.startswith('/routing/events/'):
        event=session.get(RoutingEvent,parts[2])
        if not event:raise HTTPException(404,'Event not found.')
        for vehicle_id in event.affected_vehicles:scope_vehicle(session,p,vehicle_id)
    if path.startswith('/routing/schools/'):
        school=session.get(School,parts[2])
        if not school:raise HTTPException(404,'School not found.')
        if p.login.mode=='demo' and school.input_source!='simulated':deny()
    if path.startswith('/routing/vehicles/') and len(parts)>2:scope_vehicle(session,p,parts[2])
    if p.login.mode=='demo':
        if path.startswith('/exports') or path.startswith('/auth/admin') or path=='/routing/geocode':deny()
        if path=='/routes/generate' and body.get('provider')=='google' and not body.get('force_live_failure'):deny()
        if path.startswith('/routes/') and path.endswith('/map-image'):deny()
    if path in ('/students','/vehicle','/routes/morning','/routes/afternoon') and p.login.mode!='demo':deny()


class LoginInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username:str=Field(min_length=1,max_length=100)
    password:str=Field(min_length=1,max_length=1024)
    mode:str=Field(pattern='^(real|demo)$')


def identity(session,p):
    return {'id':p.user.id,'username':p.user.username,'role':p.user.role,'mode':p.login.mode,
        'expires_at':p.login.expires_at.isoformat(),
        'vehicle_ids':session.scalars(select(DriverVehicle.vehicle_id).where(DriverVehicle.account_id==p.user.id)).all(),
        'student_ids':session.scalars(select(ParentStudent.student_id).where(ParentStudent.account_id==p.user.id)).all()}


@router.post('/auth/login')
def login(body:LoginInput,response:Response,request:Request,session:Session=Depends(session_dependency)):
    login_rate(request)
    user=session.scalar(select(Account).where(Account.username==body.username.strip().lower()).with_for_update())
    valid=False
    try:valid=hasher.verify(user.password_hash if user and user.password_hash.startswith('$argon2') else _dummy,body.password)
    except (VerificationError,InvalidHashError):pass
    if not user or not valid or not user.active or (user.locked_until and user.locked_until>now()):
        if user:
            user.failed_attempts+=1
            if user.failed_attempts>=5:user.locked_until=now()+timedelta(minutes=15)
            session.commit()
        raise HTTPException(401,'Invalid credentials or temporarily locked account.')
    if user.demo_only and body.mode!='demo':deny()
    user.failed_attempts=0;user.locked_until=None
    if hasher.check_needs_rehash(user.password_hash):user.password_hash=hasher.hash(body.password)
    token='sr_user_'+secrets.token_urlsafe(32)
    row=LoginSession(id='LOGIN_'+uuid4().hex,token_hash=token_hash(token),account_id=user.id,mode=body.mode,
        created_at=now(),expires_at=now()+timedelta(hours=SESSION_HOURS))
    session.add(row);session.flush();result=identity(session,Principal(user,row));session.commit()
    response.headers['Cache-Control']='no-store'
    return {'token':token,'user':result}


@router.get('/auth/me')
def me(request:Request,session:Session=Depends(session_dependency)):
    return identity(session,request.state.principal)


@router.post('/auth/logout')
def logout(request:Request,session:Session=Depends(session_dependency)):
    p=request.state.principal;p.login.revoked_at=now()
    session.execute(update(TrackingSession).where(TrackingSession.login_session_id==p.login.id,TrackingSession.revoked_at.is_(None)).values(revoked_at=now()))
    session.commit();return {'logged_out':True}


@router.get('/parent/students/{student_id}')
def parent_student(student_id:str,request:Request,session:Session=Depends(session_dependency)):
    student=scope_student(session,request.state.principal,student_id)
    return {'student_id':student.id,'name':student.name,'school_name':session.get(School,student.school_id).name,
        'vehicle_id':student.vehicle_id,'active':student.active,'input_source':student.input_source,
        'note':'Only your linked registration and in-app notifications are shown; no unverified boarding/delivery claim.'}
