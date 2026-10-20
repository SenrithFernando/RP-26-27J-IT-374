"""Persistent in-app events. Recipient parameters are prototype filters, not authorization."""
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from models import MissedPickupNotification,Trip,TripStopArrival,RouteVersion
from persistence import session_dependency

router=APIRouter(prefix="/routing/notifications",tags=["Prototype notification recipients"])


def create_missed_event(session,window,outcome,now,source):
    # Called only inside the locked MISSED transition transaction. Defensive unique upsert
    # also makes duplicate processing safe at database level.
    if outcome.state!='MISSED': return
    trip=session.get(Trip,window.trip_id)
    route=session.get(RouteVersion,trip.route_id)
    daily=route.input_snapshot.get('daily') if route else None
    if daily and trip.direction=='afternoon':
        # One existing alert decision path. Preserve the active manifest/history,
        # but never alert a participant explicitly excluded from PM transport.
        from models import LandmarkAttendance,LandmarkBoarding
        snapshot=next((r for r in daily['attendance']['rows'] if r['student_id']==outcome.student_id),None)
        attendance=session.get(LandmarkAttendance,(daily['scenario_id'],route.service_date,outcome.student_id))
        boarding=session.get(LandmarkBoarding,(daily['scenario_id'],route.service_date,outcome.student_id))
        if not snapshot or not snapshot['eligible'] or (attendance and attendance.pm=='no') or (boarding and boarding.outcome=='no_show'):return
    position_source=session.scalar(select(TripStopArrival.source).where(TripStopArrival.event_id==window.arrival_event_id)) if window.arrival_event_id else None
    statement=insert(MissedPickupNotification).values(id='NOTICE_'+uuid4().hex,kind='missed_pickup',trip_id=trip.id,
        window_id=window.id,student_id=outcome.student_id,student_name=outcome.student_name,vehicle_id=trip.vehicle_id,
        route_id=window.route_id,stop_sequence=outcome.stop_sequence,occurred_at=window.deadline_at,created_at=now,
        action_source=source,position_source=position_source,mode=window.mode,delivery_status='in_app_event_created',
        message=f"Boarding unconfirmed at pickup-window deadline for {outcome.student_name}; no delivery or actual no-show is established.")
    session.execute(statement.on_conflict_do_nothing(constraint='one_missed_notification_per_pickup'))


def scoped_query(recipient,student_id):
    if recipient=='parent' and not student_id: raise HTTPException(422,'Parent recipient requires an explicit prototype student_id; no broadcast inbox exists.')
    if recipient=='admin' and student_id is not None: raise HTTPException(422,'Admin inbox does not accept a parent student_id filter.')
    query=select(MissedPickupNotification)
    if recipient=='parent': query=query.where(MissedPickupNotification.student_id==student_id)
    return query


def serialize(row,recipient,session=None):
    read_at=row.admin_read_at if recipient=='admin' else row.parent_read_at
    route=session.get(RouteVersion,row.route_id) if session is not None else None
    resolution=None
    if session is not None:
        from models import PickupTransition
        resolution=session.scalar(select(PickupTransition).where(PickupTransition.window_id==row.window_id,
            PickupTransition.student_id==row.student_id,PickupTransition.from_state=='MISSED',
            PickupTransition.to_state=='PICKED_UP',PickupTransition.action_source=='manual_test_delayed_review')
            .order_by(PickupTransition.order_id.desc()).limit(1))
    return {**{key:getattr(row,key) for key in ('id','order_id','kind','trip_id','window_id','student_id','student_name','vehicle_id',
        'route_id','stop_sequence','occurred_at','created_at','action_source','position_source','mode','delivery_status','message')},
        'read':read_at is not None,'read_at':read_at,'route_version':route.version if route else None,
        'alert_type':'boarding_unconfirmed','generation_status':'in_app_event_created',
        'parent_channel_status':'unavailable_hasara_not_connected',
        'resolution_status':'resolved_delayed_manual_test_evidence' if resolution else 'unresolved',
        'resolved_at':resolution.recorded_at if resolution else None}


@router.get('')
def inbox(recipient:Literal['admin','parent'],student_id:str|None=Query(None,min_length=1,max_length=64),
          limit:int=Query(50,ge=1,le=200),before_order_id:int|None=Query(None,ge=1),session:Session=Depends(session_dependency),request:Request=None):
    query=scoped_query(recipient,student_id)
    if request and request.state.principal.login.mode=='demo':
        from models import Student,Vehicle,RouteVersion
        from data_provenance import snapshot_sources
        allowed_routes=[r.id for r in session.scalars(select(RouteVersion).where(RouteVersion.vehicle_id.in_(select(Vehicle.id).where(Vehicle.input_source=='simulated'))))
            if list(snapshot_sources(r.input_snapshot)) and all(source=='simulated' for source in snapshot_sources(r.input_snapshot))]
        query=query.where(MissedPickupNotification.student_id.in_(select(Student.id).where(Student.input_source=='simulated')),
            MissedPickupNotification.vehicle_id.in_(select(Vehicle.id).where(Vehicle.input_source=='simulated')),
            MissedPickupNotification.route_id.in_(allowed_routes))
    read_column=MissedPickupNotification.admin_read_at if recipient=='admin' else MissedPickupNotification.parent_read_at
    unread=session.scalar(select(func.count()).select_from(query.where(read_column.is_(None)).subquery()))
    if before_order_id is not None: query=query.where(MissedPickupNotification.order_id<before_order_id)
    rows=session.scalars(query.order_by(MissedPickupNotification.order_id.desc()).limit(limit+1)).all()
    page=rows[:limit]
    return {'recipient':recipient,'student_id':student_id,'notifications':[serialize(row,recipient,session) for row in page],
        'unread_count':unread,'truncated':len(rows)>limit,'next_before_order_id':page[-1].order_id if page else None,
        'access':'authenticated_object_scoped' if request else 'internal_call','delivery_status':'in_app_event_created'}


class ReadState(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    recipient:Literal['admin','parent']
    student_id:str|None=Field(default=None,min_length=1,max_length=64)
    read:bool=True


@router.patch('/{notification_id}/read')
def mark_read(notification_id:str,payload:ReadState,session:Session=Depends(session_dependency)):
    query=scoped_query(payload.recipient,payload.student_id).where(MissedPickupNotification.id==notification_id).with_for_update()
    row=session.scalar(query)
    if row is None: raise HTTPException(404,'Notification not found for this selected recipient.')
    field='admin_read_at' if payload.recipient=='admin' else 'parent_read_at'
    if payload.read and getattr(row,field) is None: setattr(row,field,session.scalar(select(func.clock_timestamp())))
    elif not payload.read: setattr(row,field,None)
    session.commit()
    return serialize(row,payload.recipient,session)
