"""Preliminary source-labelled operational episodes. Never crash/safety diagnoses."""
import copy
import os
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from models import Trip,RouteVersion,RouteStop,PickupWindow,PickupOutcome,TripOperationalMonitor,OperationalEpisode
from persistence import session_dependency
from arrivals import distance_m
from operational_geometry import select_geometry,point_polyline_metres

router=APIRouter(tags=['Preliminary operational monitoring'])

class OperationalSettings(BaseModel):
    road_deviation_metres:float=Field(default=100,gt=0,le=5000,allow_inf_nan=False)
    sequence_deviation_metres:float=Field(default=300,gt=0,le=10000,allow_inf_nan=False)
    deviation_seconds:float=Field(default=20,ge=1,le=600,allow_inf_nan=False)
    recovery_seconds:float=Field(default=10,ge=1,le=300,allow_inf_nan=False)
    stop_seconds:float=Field(default=60,ge=1,le=1800,allow_inf_nan=False)
    low_movement_mps:float=Field(default=.5,ge=0,le=5,allow_inf_nan=False)
    stop_radius_metres:float=Field(default=15,gt=0,le=100,allow_inf_nan=False)
    stop_recovery_metres:float=Field(default=30,gt=0,le=500,allow_inf_nan=False)
    expected_dwell_radius_metres:float=Field(default=75,gt=0,le=500,allow_inf_nan=False)
    max_gap_seconds:float=Field(default=10,gt=0,le=60,allow_inf_nan=False)
    freshness_seconds:float=Field(default=20,gt=0,le=120,allow_inf_nan=False)
    min_observations:int=Field(default=3,ge=3,le=100)
    @model_validator(mode='after')
    def consistent(self):
        if self.max_gap_seconds>self.freshness_seconds or self.stop_recovery_metres<=self.stop_radius_metres:
            raise ValueError('Gap must not exceed freshness; stop recovery distance must exceed stationary radius.')
        return self


def configured_operational_settings():
    load_dotenv(Path(__file__).with_name('.env'),interpolate=False)
    return OperationalSettings(**{key:os.environ['OPS_'+key.upper()] for key in OperationalSettings.model_fields if 'OPS_'+key.upper() in os.environ}).model_dump()


def initialize_monitor(session,trip):
    existing=session.get(TripOperationalMonitor,trip.id)
    if existing:return existing
    route=session.get(RouteVersion,trip.route_id)
    stops=session.scalars(select(RouteStop).where(RouteStop.route_id==trip.route_id).order_by(RouteStop.sequence)).all()
    geometry=select_geometry(route.result,[{'latitude':s.latitude,'longitude':s.longitude} for s in stops])
    geometry['stops']=[dict(s.details) for s in stops]
    cfg=configured_operational_settings()
    cfg['selected_deviation_metres']=cfg['road_deviation_metres'] if geometry['quality']=='provider_road_geometry' else cfg['sequence_deviation_metres']
    cfg['deviation_recovery_metres']=cfg['selected_deviation_metres']*.6
    row=TripOperationalMonitor(trip_id=trip.id,route_id=trip.route_id,settings=cfg,geometry=geometry,progress={})
    session.add(row);session.flush();return row


def expected_dwell(session,trip,position,monitor):
    stops=monitor.geometry['stops'];radius=monitor.settings['expected_dwell_radius_metres']
    nearby={s['sequence']:s for s in stops if distance_m(position.latitude,position.longitude,s['latitude'],s['longitude'])<=radius}
    if not nearby:return None
    # Waiting only excuses movement at that visit, never a remote stop while a window is open.
    waiting=session.scalars(select(PickupOutcome.stop_sequence).join(PickupWindow).where(PickupWindow.trip_id==trip.id,PickupWindow.state=='WAITING',
        PickupWindow.started_at<=position.recorded_at,PickupWindow.deadline_at>position.recorded_at)).all()
    if any(sequence in nearby for sequence in waiting):return 'known_pickup_window_waiting'
    for stop in nearby.values():
        if stop.get('waiting_seconds',0)>0 and stop.get('arrival') and stop.get('eta') and datetime.fromisoformat(stop['arrival'])<=position.recorded_at<=datetime.fromisoformat(stop['eta']):
            return 'planned_waiting_at_saved_stop'
    return 'expected_pickup_school_or_depot_dwell'


def confirm_episode(session,trip,monitor,kind,position,candidate,now,evidence):
    number=(session.scalar(select(func.max(OperationalEpisode.episode)).where(OperationalEpisode.trip_id==trip.id,OperationalEpisode.kind==kind)) or 0)+1
    event=OperationalEpisode(id='OPS_'+uuid4().hex,trip_id=trip.id,route_id=trip.route_id,kind=kind,episode=number,status='ACTIVE',
        started_at=datetime.fromisoformat(candidate['since']),confirmed_at=position.recorded_at,created_at=now,source=position.source,
        geometry_quality=monitor.geometry['quality'],geometry_source=monitor.geometry['source'],thresholds=dict(monitor.settings),
        evidence=evidence,confirming_position_id=position.id)
    session.add(event);return event


def recovered(event,position,reason):
    event.status='RECOVERED';event.recovered_at=position.recorded_at;event.recovery_position_id=position.id
    event.recovery_reason=reason;event.recovery_source=position.source


def sustained(progress,key,condition,position,seconds,cfg,extra=None):
    if not condition:progress.pop(key,None);return False
    candidate=progress.get(key)
    if candidate is None:
        candidate={'since':position.recorded_at.isoformat(),'count':0,**(extra or {})};progress[key]=candidate
    candidate['count']+=1
    return candidate['count']>=cfg['min_observations'] and (position.recorded_at-datetime.fromisoformat(candidate['since'])).total_seconds()>=seconds


def process_operational_position(session,position,now):
    if not position.trip_id:return 'no_explicit_trip'
    trip=session.scalar(select(Trip).where(Trip.id==position.trip_id).with_for_update())
    if trip.state!='ACTIVE':return 'trip_not_active'
    monitor=session.get(TripOperationalMonitor,trip.id)
    cfg=monitor.settings if monitor else configured_operational_settings()
    age=(now-position.recorded_at).total_seconds()
    if age<0 or age>cfg['freshness_seconds'] or position.recorded_at<trip.started_at:return 'gps_ineligible'
    if monitor is None:monitor=initialize_monitor(session,trip);cfg=monitor.settings
    if monitor.last_recorded_at and position.recorded_at<=monitor.last_recorded_at:return 'out_of_order'
    gap=(position.recorded_at-monitor.last_recorded_at).total_seconds() if monitor.last_recorded_at else None
    progress=copy.deepcopy(monitor.progress)
    if gap is None or gap>cfg['max_gap_seconds'] or monitor.last_source!=position.source:progress={}
    last=progress.get('last')
    step_speed=distance_m(last['latitude'],last['longitude'],position.latitude,position.longitude)/gap if last and gap and gap>0 else None
    events={e.kind:e for e in session.scalars(select(OperationalEpisode).where(OperationalEpisode.trip_id==trip.id,OperationalEpisode.status=='ACTIVE')).all()}
    distance=point_polyline_metres(position.latitude,position.longitude,monitor.geometry['points']) if monitor.geometry['quality']!='unavailable' else None
    if distance is not None:
        if 'route_deviation' not in events:
            if sustained(progress,'deviation',distance>cfg['selected_deviation_metres'],position,cfg['deviation_seconds'],cfg):
                confirm_episode(session,trip,monitor,'route_deviation',position,progress['deviation'],now,{'distance_metres':distance,'observations':progress['deviation']['count']})
                progress.pop('deviation',None)
        elif sustained(progress,'deviation_recovery',distance<=cfg['deviation_recovery_metres'],position,cfg['recovery_seconds'],cfg):
            recovered(events['route_deviation'],position,'Sustained return within saved-route recovery corridor.');progress.pop('deviation_recovery',None)
    waiting=expected_dwell(session,trip,position,monitor)
    active_stop=events.get('unexpected_stop')
    if active_stop:
        anchor=active_stop.evidence['anchor']
        away=distance_m(position.latitude,position.longitude,anchor[0],anchor[1])>cfg['stop_recovery_metres']
        if sustained(progress,'stop_recovery',bool(waiting) or away,position,cfg['recovery_seconds'],cfg):
            recovered(active_stop,position,'Reclassified as expected dwell: '+waiting if waiting else 'Sustained displacement away from stopped-position cluster.')
            progress.pop('stop_recovery',None);progress.pop('stationary',None)
    elif waiting:progress.pop('stationary',None)
    else:
        candidate=progress.get('stationary')
        if candidate is None or step_speed is None or step_speed>cfg['low_movement_mps'] or distance_m(position.latitude,position.longitude,*candidate['anchor'])>cfg['stop_radius_metres']:
            progress['stationary']={'since':position.recorded_at.isoformat(),'count':1,'anchor':[position.latitude,position.longitude]}
        else:
            candidate['count']+=1
            if candidate['count']>=cfg['min_observations'] and (position.recorded_at-datetime.fromisoformat(candidate['since'])).total_seconds()>=cfg['stop_seconds']:
                confirm_episode(session,trip,monitor,'unexpected_stop',position,candidate,now,
                    {'anchor':candidate['anchor'],'derived_step_speed_mps':step_speed,'observations':candidate['count'],'qualification':'Operational low-movement anomaly, not a crash or safety diagnosis.'})
                progress.pop('stationary',None)
    progress['last']={'latitude':position.latitude,'longitude':position.longitude,'position_id':position.id,'recorded_at':position.recorded_at.isoformat()}
    progress['distance_metres']=distance;progress['derived_step_speed_mps']=step_speed;progress['expected_waiting']=waiting
    monitor.progress=progress;monitor.last_recorded_at=position.recorded_at;monitor.last_source=position.source
    return 'processed'


def close_operational_episodes(session,trip,now):
    for event in session.scalars(select(OperationalEpisode).where(OperationalEpisode.trip_id==trip.id,OperationalEpisode.status=='ACTIVE')).all():
        event.status='CLOSED';event.closed_at=now;event.recovery_reason='Trip lifecycle closed; no GPS recovery inferred.'


def operational_view(session,trip,now=None,limit=50):
    now=now or datetime.now(timezone.utc);monitor=session.get(TripOperationalMonitor,trip.id)
    episodes=session.scalars(select(OperationalEpisode).where(OperationalEpisode.trip_id==trip.id).order_by(OperationalEpisode.confirmed_at.desc(),OperationalEpisode.id).limit(limit+1)).all()
    age=(now-monitor.last_recorded_at).total_seconds() if monitor and monitor.last_recorded_at else None
    fresh=trip.state=='ACTIVE' and age is not None and 0<=age<=monitor.settings['freshness_seconds']
    progress=monitor.progress if monitor else {}
    # Gaps interrupt candidate evidence; they never resolve an active episode or infer a stop.
    interrupted=fresh and age>monitor.settings['max_gap_seconds']
    return {'trip_id':trip.id,'route_id':trip.route_id,'gps_state':'fresh' if fresh and not interrupted else 'unknown',
        'position_age_seconds':max(0,age) if age is not None else None,'source':monitor.last_source if monitor else None,
        'settings':monitor.settings if monitor else None,'geometry':{k:v for k,v in monitor.geometry.items() if k not in ('points','stops')} if monitor else None,
        'distance_metres':progress.get('distance_metres') if fresh else None,'derived_step_speed_mps':progress.get('derived_step_speed_mps') if fresh else None,
        'expected_waiting':progress.get('expected_waiting') if fresh else None,
        'deviation_candidate':bool(progress.get('deviation')) and fresh and not interrupted,
        'stop_candidate':progress.get('stationary',{}).get('count',0)>=2 and fresh and not interrupted,
        'episodes':[{key:getattr(event,key) for key in ('id','kind','episode','status','started_at','confirmed_at','created_at','recovered_at','closed_at','recovery_reason','source','recovery_source','geometry_quality','geometry_source','thresholds','evidence')} for event in episodes[:limit]],
        'truncated':len(episodes)>limit,'note':'Preliminary operational monitoring only. Stop-sequence deviation is approximate. No validated accuracy, precision/recall, crash or safety diagnosis is claimed.'}


@router.get('/trips/{trip_id}/operational-events')
def read_operational_events(trip_id:str,limit:int=Query(50,ge=1,le=200),session:Session=Depends(session_dependency)):
    trip=session.get(Trip,trip_id)
    if trip is None:raise HTTPException(404,'Trip not found.')
    return operational_view(session,trip,limit=limit)
