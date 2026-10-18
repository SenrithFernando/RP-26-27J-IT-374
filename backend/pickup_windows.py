"""Provisional pickup policy: durable exception windows, never optimizer wait constraints."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from models import Trip, Vehicle, PickupWindow, PickupOutcome, PickupTransition
from persistence import session_dependency

router=APIRouter(tags=["Persistent prototype pickups"])
TERMINAL={'PICKED_UP','MISSED','CANCELLED'}


def clock(session):
    # PostgreSQL clock after locks, not browser or transaction-start now().
    return session.scalar(select(func.clock_timestamp()))


def policy():
    load_dotenv(Path(__file__).with_name('.env'),interpolate=False)
    morning=os.getenv('PICKUP_MORNING_SCOPE','per_stop')
    afternoon=os.getenv('PICKUP_AFTERNOON_SCOPE','per_school')
    seconds=int(os.getenv('PICKUP_DEMO_DURATION_SECONDS','30'))
    interval=float(os.getenv('PICKUP_WORKER_INTERVAL_SECONDS','1'))
    if morning!='per_stop' or afternoon not in ('per_stop','per_school') or not 5<=seconds<=120 or not .2<=interval<=30:
        raise ValueError('Invalid pickup policy: morning per_stop, afternoon per_stop/per_school, demo 5..120 s, worker .2..30 s.')
    return {'supervisor_confirmed':False,'policy':'Provisional: morning individual home pickup; afternoon contiguous shared school visit unless per_stop selected.',
        'morning_scope':morning,'afternoon_scope':afternoon,'production_duration_seconds':900,'demo_duration_seconds':seconds,
        'worker_interval_seconds':interval,'deadline_rule':'Confirm only when backend lock-time is strictly before deadline; at/after deadline unresolved outcomes are MISSED.'}


def trip_settings(session,route,mode,scope):
    cfg=policy()
    scope=scope or cfg[route.direction+'_scope']
    if route.input_snapshot.get('daily'):
        if mode!='production':raise HTTPException(422,'Landmark checkpoint uses the explicit 900-second production-duration window, not accelerated mode.')
        if route.direction=='afternoon':
            if scope!='per_school':raise HTTPException(422,'Landmark PM boarding uses one shared window per grouped school visit.')
    if route.direction=='morning' and scope!='per_stop': raise HTTPException(422,'Home pickups require per_stop scope; shared school scope applies to afternoon school visits.')
    if mode=='simulation_demo' and session.get(Vehicle,route.vehicle_id).input_source!='simulated':
        raise HTTPException(422,'Accelerated mode requires a simulated vehicle and simulation-only GPS.')
    return {'mode':mode,'scope':scope,'duration_seconds':900 if mode=='production' else cfg['demo_duration_seconds'],
        'supervisor_confirmed':False,'policy':cfg['policy'],'deadline_rule':cfg['deadline_rule']}


def audit(session,window,student,old,new,effective,recorded,source,reason):
    session.add(PickupTransition(id='PICKUP_EVENT_'+uuid4().hex,window_id=window.id,student_id=student,
        from_state=old,to_state=new,effective_at=effective,recorded_at=recorded,action_source=source,reason=reason))


def change_window(session,window,state,effective,now,source,reason):
    if window.state==state: return
    old=window.state;window.state=state;window.changed_at=now
    audit(session,window,None,old,state,effective,now,source,reason)


def change_outcome(session,window,outcome,state,effective,now,source,reason):
    if outcome.state==state: return
    old=outcome.state;outcome.state=state;outcome.changed_at=now;outcome.action_source=source
    if state=='PICKED_UP': outcome.picked_up_at=now
    audit(session,window,outcome.student_id,old,state,effective,now,source,reason)


def outcomes(session,window):
    return session.scalars(select(PickupOutcome).where(PickupOutcome.window_id==window.id).order_by(PickupOutcome.student_id).with_for_update()).all()


def aggregate(session,window,rows,now,source,reason):
    states={row.state for row in rows}
    if states and states<=TERMINAL:
        target='PICKED_UP' if states=={'PICKED_UP'} else 'MISSED' if 'MISSED' in states else 'CANCELLED'
        change_window(session,window,target,now,now,source,reason)


def create_windows(session,trip,snapshot):
    cfg=trip.pickup_settings
    names={s['id']:s.get('name',s['id']) for s in snapshot['input_snapshot']['students']} if 'input_snapshot' in snapshot else {}
    now=clock(session);window=None;previous=None
    for stop in snapshot['stops']:
        if stop['action']!='pickup': previous=None;continue
        student_ids=stop.get('student_ids',[stop.get('student_id')])
        if not student_ids:continue
        shared=cfg['scope']=='per_school' and trip.direction=='afternoon'
        visit=(stop.get('school_id'),stop['latitude'],stop['longitude']) if shared else None
        if not shared or previous!=visit or window is None:
            key=f"school:{stop.get('school_id')}:visit:{stop['sequence']}" if shared else f"stop:{stop['sequence']}"
            window=PickupWindow(id='WINDOW_'+uuid4().hex,trip_id=trip.id,route_id=trip.route_id,scope_key=key,
                scope='per_school' if shared else 'per_stop',school_id=stop.get('school_id'),state='SCHEDULED',
                mode=cfg['mode'],duration_seconds=cfg['duration_seconds'],changed_at=now)
            session.add(window);session.flush()
            audit(session,window,None,None,'SCHEDULED',now,now,'backend_schedule','Saved route pickup visit scheduled.')
        for sid in student_ids:
            student=PickupOutcome(window_id=window.id,trip_id=trip.id,student_id=sid,stop_sequence=stop['sequence'],
                student_name=stop.get('student_names',{}).get(sid) or stop.get('student_name') or names.get(sid) or stop['name'],state='SCHEDULED',changed_at=now,action_source='backend_schedule')
            session.add(student)
            audit(session,window,student.student_id,None,'SCHEDULED',now,now,'backend_schedule','Individual pickup outcome scheduled; delivery is separate.')
        previous=visit


def start_from_arrival(session,trip,stop,arrival,now):
    if not getattr(trip,'pickup_settings',None) or trip.state!='ACTIVE' or stop.action!='pickup': return
    outcome=session.scalar(select(PickupOutcome).where(PickupOutcome.trip_id==trip.id,PickupOutcome.stop_sequence==stop.sequence))
    if outcome is None: return
    window=session.scalar(select(PickupWindow).where(PickupWindow.id==outcome.window_id).with_for_update())
    if window.started_at is not None or window.state!='SCHEDULED': return
    if window.mode=='simulation_demo' and arrival.source!='simulation': return
    started=arrival.arrived_at
    from models import RouteVersion
    route=session.get(RouteVersion,trip.route_id)
    if trip.direction=='afternoon' and route.input_snapshot.get('daily'):
        from zoneinfo import ZoneInfo
        from datetime import time
        release=datetime.combine(route.service_date,time(13,30),ZoneInfo('Asia/Colombo'))
        window.arrival_event_id=arrival.event_id
        if now<release:return  # Worker opens it at release, without another GPS transition.
        started=max(started,release)
    window.started_at=started;window.deadline_at=started+timedelta(seconds=window.duration_seconds)
    window.arrival_event_id=arrival.event_id
    rows=outcomes(session,window)
    source='arrival_simulation' if arrival.source=='simulation' else 'arrival_actual_device'
    change_window(session,window,'ARRIVED',started,now,source,'Confirmed arrival at applicable current pickup visit and release reached.')
    for row in rows:
        if row.state=='SCHEDULED': change_outcome(session,window,row,'ARRIVED',started,now,source,'Shared visit arrival applies to this student; not pickup confirmation.')
    change_window(session,window,'WAITING',started,now,'backend_window','Pickup window opened once from confirmed arrival and applicable release timestamp; overlaps planned boarding service.')
    for row in rows:
        if row.state=='ARRIVED': change_outcome(session,window,row,'WAITING',started,now,'backend_window','Awaiting explicit pickup confirmation.')
    expire_window(session,window,rows,now,'expiry_ingestion')


def expire_window(session,window,rows,now,source):
    if window.state!='WAITING' or window.deadline_at is None or now<window.deadline_at: return False
    for row in rows:
        if row.state not in TERMINAL:
            change_outcome(session,window,row,'MISSED',window.deadline_at,now,source,'Pickup deadline reached without confirmation.')
            from notifications import create_missed_event
            create_missed_event(session,window,row,now,source)
    aggregate(session,window,rows,now,source,'Window expired; individual outcomes retained.')
    return True


def close_trip_windows(session,trip,now):
    windows=session.scalars(select(PickupWindow).where(PickupWindow.trip_id==trip.id,PickupWindow.state.in_(('SCHEDULED','ARRIVED','WAITING'))).order_by(PickupWindow.id).with_for_update()).all()
    for window in windows:
        rows=outcomes(session,window)
        expire_window(session,window,rows,now,'expiry_lifecycle')
        for row in rows:
            if row.state not in TERMINAL: change_outcome(session,window,row,'CANCELLED',now,now,'manual_trip_lifecycle','Trip closed without pickup confirmation; no delivery implied.')
        aggregate(session,window,rows,now,'manual_trip_lifecycle','Trip lifecycle closed; existing terminal outcomes retained.')


def pending_actions(session,trip):
    rows=session.scalars(select(PickupOutcome).where(PickupOutcome.trip_id==trip.id)).all()
    states={row.student_id:row.state for row in rows}
    result=[]
    for original in trip.unfinished_actions:
        action=dict(original)
        if action['action']=='pickup':
            state=states.get(action['student_id'])
            if state=='PICKED_UP': continue
            if state in ('MISSED','CANCELLED'): action['status']=state
        result.append(action)
    return result


def serialize_windows(session,trip):
    now=clock(session)
    windows=session.scalars(select(PickupWindow).where(PickupWindow.trip_id==trip.id).order_by(PickupWindow.scope_key)).all()
    result=[]
    for window in windows:
        rows=session.scalars(select(PickupOutcome).where(PickupOutcome.window_id==window.id).order_by(PickupOutcome.stop_sequence)).all()
        active=trip.state=='ACTIVE' and window.state=='WAITING' and window.deadline_at is not None and now<window.deadline_at
        result.append({'window_id':window.id,'scope':window.scope,'scope_key':window.scope_key,'school_id':window.school_id,
            'state':window.state,'mode':window.mode,'duration_seconds':window.duration_seconds,'started_at':window.started_at,'deadline_at':window.deadline_at,
            'remaining_seconds':0 if window.state in TERMINAL else max(0,(window.deadline_at-now).total_seconds()) if window.deadline_at else None,
            'expiry_pending':window.state=='WAITING' and window.deadline_at is not None and now>=window.deadline_at,
            'outcomes':[{'student_id':row.student_id,'student_name':row.student_name,'stop_sequence':row.stop_sequence,'state':row.state,
                'changed_at':row.changed_at,'picked_up_at':row.picked_up_at,'action_source':row.action_source,
                'can_confirm':active and row.state=='WAITING','can_cancel':trip.state=='ACTIVE' and row.state not in TERMINAL and not (window.deadline_at and now>=window.deadline_at)} for row in rows]})
    return {'trip_id':trip.id,'server_now':now,'settings':trip.pickup_settings,'windows':result,
        'note':'Manual prototype pickup only; delivery/RFID are separate. Times are server-owned. Older trips without pickup_settings are not retrofitted.'}


class CancelPickup(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:str=Field(min_length=1,max_length=500)


@router.get('/pickup-policy')
def get_policy(): return policy()


@router.get('/trips/{trip_id}/pickup-windows')
def get_windows(trip_id:str,session:Session=Depends(session_dependency)):
    trip=session.get(Trip,trip_id)
    if trip is None: raise HTTPException(404,'Trip not found.')
    return serialize_windows(session,trip)


def manual_action(session,trip_id,student_id,action,reason='Manual driver prototype confirmation; not RFID verified.'):
    trip=session.scalar(select(Trip).where(Trip.id==trip_id).with_for_update())
    if trip is None: raise HTTPException(404,'Trip not found.')
    row=session.scalar(select(PickupOutcome).where(PickupOutcome.trip_id==trip_id,PickupOutcome.student_id==student_id))
    if row is None: raise HTTPException(404,'Student pickup not found in this trip.')
    window=session.scalar(select(PickupWindow).where(PickupWindow.id==row.window_id).with_for_update())
    rows=outcomes(session,window);now=clock(session)
    target='PICKED_UP' if action=='confirm' else 'CANCELLED'
    if row.state==target:
        session.commit();return serialize_windows(session,trip)
    expire_window(session,window,rows,now,'expiry_confirmation')
    if trip.state!='ACTIVE' or row.state in TERMINAL or (action=='confirm' and (row.state!='WAITING' or window.state!='WAITING')):
        session.commit()  # Persist expiry even when rejecting a late confirmation.
        raise HTTPException(409,'Pickup cannot be changed: trip inactive, window not waiting, deadline reached, or outcome already terminal. Refresh server state.')
    change_outcome(session,window,row,target,now,now,'manual_driver_prototype',reason)
    aggregate(session,window,rows,now,'manual_driver_prototype','All individual outcomes terminal; mixed outcomes remain individually visible.')
    session.commit();return serialize_windows(session,trip)


@router.post('/trips/{trip_id}/pickups/{student_id}/confirm')
def confirm_pickup(trip_id:str,student_id:str,session:Session=Depends(session_dependency)):
    return manual_action(session,trip_id,student_id,'confirm')


@router.post('/trips/{trip_id}/pickups/{student_id}/cancel')
def cancel_pickup(trip_id:str,student_id:str,payload:CancelPickup,session:Session=Depends(session_dependency)):
    return manual_action(session,trip_id,student_id,'cancel',payload.reason)


@router.get('/trips/{trip_id}/pickup-history')
def pickup_history(trip_id:str,limit:int=Query(100,ge=1,le=500),after_order_id:int=Query(0,ge=0),session:Session=Depends(session_dependency)):
    if session.get(Trip,trip_id) is None: raise HTTPException(404,'Trip not found.')
    rows=session.scalars(select(PickupTransition).join(PickupWindow).where(PickupWindow.trip_id==trip_id,PickupTransition.order_id>after_order_id)
        .order_by(PickupTransition.order_id).limit(limit+1)).all()
    return {'events':[{key:getattr(row,key) for key in ('id','order_id','window_id','student_id','from_state','to_state','effective_at','recorded_at','action_source','reason')} for row in rows[:limit]],'limit':limit,'truncated':len(rows)>limit,'next_after_order_id':rows[min(limit,len(rows))-1].order_id if rows else after_order_id}
