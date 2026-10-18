"""Current-stop proximity only. No boarding, delivery or automatic stop advancement."""
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Trip, TripStopArrival, RouteStop, VehiclePosition
from persistence import session_dependency
from planning_state import planning_lock

router=APIRouter(tags=["Current stop arrival"])


class ArrivalSettings(BaseModel):
    radius_metres: float = Field(default=50,gt=0,le=1000,allow_inf_nan=False)
    exit_radius_metres: float = Field(default=75,gt=0,le=2000,allow_inf_nan=False)
    dwell_seconds: float = Field(default=15,gt=0,le=600,allow_inf_nan=False)
    min_observations: int = Field(default=3,ge=2,le=100)
    max_gap_seconds: float = Field(default=10,gt=0,le=120,allow_inf_nan=False)
    freshness_seconds: float = Field(default=20,gt=0,le=120,allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_thresholds(self):
        if self.exit_radius_metres<=self.radius_metres: raise ValueError("Exit radius must exceed arrival radius.")
        if self.max_gap_seconds>self.freshness_seconds: raise ValueError("Maximum gap must not exceed freshness.")
        return self


def configured_settings():
    load_dotenv(Path(__file__).with_name(".env"),interpolate=False)
    return ArrivalSettings(**{key:os.environ['ARRIVAL_'+key.upper()] for key in ArrivalSettings.model_fields if 'ARRIVAL_'+key.upper() in os.environ}).model_dump()


def settings_for(trip):
    return ArrivalSettings(**(trip.arrival_settings or configured_settings()))


def distance_m(lat1,lon1,lat2,lon2):
    a=math.sin(math.radians(lat2-lat1)/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,max(0,a))))


def initialize_stop(session,trip,now):
    stop=session.scalar(select(RouteStop).where(RouteStop.route_id==trip.route_id,RouteStop.action!='start').order_by(RouteStop.sequence).limit(1))
    trip.current_stop_sequence=stop.sequence if stop else None
    trip.current_stop_selected_at=now
    trip.arrival_settings=configured_settings()


def process_position(session,position,now):
    if not position.trip_id: return "no_explicit_trip"
    trip=session.scalar(select(Trip).where(Trip.id==position.trip_id).with_for_update())
    if trip.state!='ACTIVE' or trip.current_stop_sequence is None: return "trip_not_active"
    cfg=settings_for(trip)
    age=(now-position.recorded_at).total_seconds()
    if age<0 or age>cfg.freshness_seconds: return "gps_not_fresh"
    if trip.arrival_settings is None: trip.arrival_settings=cfg.model_dump()
    if position.recorded_at < trip.started_at or position.recorded_at <= trip.current_stop_selected_at: return "before_current_stop"
    stop=session.get(RouteStop,(trip.route_id,trip.current_stop_sequence))
    if stop is None: return "stop_unavailable"
    row=session.get(TripStopArrival,(trip.id,stop.sequence))
    if row and position.recorded_at<=row.last_recorded_at: return "out_of_order"
    if row and row.arrived_at: return "already_arrived"
    distance=distance_m(position.latitude,position.longitude,stop.latitude,stop.longitude)
    if row is None:
        row=TripStopArrival(trip_id=trip.id,stop_sequence=stop.sequence,route_id=trip.route_id,
            last_recorded_at=position.recorded_at,observation_count=0,distance_metres=distance,source=position.source)
        session.add(row)
    else:
        gap=(position.recorded_at-row.last_recorded_at).total_seconds()
        if gap>cfg.max_gap_seconds or row.source!=position.source:
            row.candidate_started_at=None;row.observation_count=0
    row.last_recorded_at=position.recorded_at;row.distance_metres=distance;row.source=position.source
    if distance>cfg.exit_radius_metres:
        row.candidate_started_at=None;row.observation_count=0
    elif row.candidate_started_at is not None or distance<=cfg.radius_metres:
        if row.candidate_started_at is None: row.candidate_started_at=position.recorded_at
        row.observation_count+=1
        elapsed=(position.recorded_at-row.candidate_started_at).total_seconds()
        if elapsed>=cfg.dwell_seconds and row.observation_count>=cfg.min_observations:
            row.arrived_at=position.recorded_at;row.event_id='ARRIVAL_'+uuid4().hex;row.confirming_position_id=position.id
            if getattr(trip,"pickup_settings",None):
                session.flush()
                from pickup_windows import start_from_arrival
                start_from_arrival(session,trip,stop,row,now)
            return "arrived"
    return "arrival_candidate" if row.candidate_started_at else "approaching"


def arrival_view(session,trip,now=None):
    now=now or datetime.now(timezone.utc)
    cfg=settings_for(trip)
    stop=session.get(RouteStop,(trip.route_id,trip.current_stop_sequence)) if trip.current_stop_sequence is not None else None
    row=session.get(TripStopArrival,(trip.id,trip.current_stop_sequence)) if stop else None
    position=session.scalar(select(VehiclePosition).where(VehiclePosition.vehicle_id==trip.vehicle_id,VehiclePosition.trip_id==trip.id)
        .order_by(VehiclePosition.recorded_at.desc(),VehiclePosition.id).limit(1))
    age=(now-position.recorded_at).total_seconds() if position else None
    usable=position is not None and 0<=age<=cfg.freshness_seconds and trip.current_stop_selected_at is not None and position.recorded_at>trip.current_stop_selected_at
    from positions import accuracy_quality
    usable=usable and accuracy_quality(position)!='poor'
    usable=usable and row is not None and (row.arrived_at is not None or row.last_recorded_at==position.recorded_at)
    reason=None
    if trip.state!='ACTIVE': reason="Trip is not active. Historical arrival evidence is retained."
    elif not stop: reason="No current saved-route stop selected."
    elif not usable: reason="No fresh, eligible GPS for this trip/current stop; this does not mean outside the geofence."
    elif row and not row.arrived_at and row.candidate_started_at and (now-row.last_recorded_at).total_seconds()>cfg.max_gap_seconds:
        reason="Observation gap breaks continuous dwell; fresh repeated observations are required."
    status="gps_unknown" if reason else "arrived" if row and row.arrived_at else "arrival_candidate" if row and row.candidate_started_at else "approaching"
    event={"event_id":row.event_id,"arrived_at":row.arrived_at,"candidate_started_at":row.candidate_started_at,
        "confirming_position_id":row.confirming_position_id,"source":row.source,"route_id":row.route_id,"stop_sequence":row.stop_sequence} if row and row.arrived_at else None
    next_stop=session.scalar(select(RouteStop.sequence).where(RouteStop.route_id==trip.route_id,RouteStop.sequence>trip.current_stop_sequence).order_by(RouteStop.sequence).limit(1)) if stop else None
    return {"trip_id":trip.id,"route_id":trip.route_id,"state":status,"reason":reason,"settings":cfg.model_dump(),
        "current_stop":{**stop.details,"sequence":stop.sequence} if stop else None,
        "position_age_seconds":max(0,age) if age is not None else None,"gps_status":"fresh" if usable else "unknown" if position is None else "stale_or_ineligible",
        "distance_metres":distance_m(position.latitude,position.longitude,stop.latitude,stop.longitude) if usable else None,"observation_count":row.observation_count if row else 0,
        "candidate_started_at":row.candidate_started_at if row else None,"arrival_event":event,
        "can_advance":trip.state=='ACTIVE' and event is not None and next_stop is not None,
        "note":"GPS proximity only. No student boarding/delivery confirmation; no automatic stop advancement."}


@router.get('/trips/{trip_id}/arrival')
def read_arrival(trip_id:str,session:Session=Depends(session_dependency)):
    trip=session.get(Trip,trip_id)
    if trip is None: raise HTTPException(404,'Trip not found.')
    return arrival_view(session,trip)


@router.post('/trips/{trip_id}/advance-stop')
def advance_stop(trip_id:str,expected_stop_sequence:int=Query(...,ge=1),session:Session=Depends(session_dependency)):
    planning_lock(session)
    trip=session.scalar(select(Trip).where(Trip.id==trip_id).with_for_update())
    if trip is None: raise HTTPException(404,'Trip not found.')
    if trip.state!='ACTIVE' or trip.current_stop_sequence!=expected_stop_sequence:
        raise HTTPException(409,'Current active trip stop changed; refresh before advancing.')
    view=arrival_view(session,trip)
    if not view['can_advance']: raise HTTPException(409,'An arrival event and a following saved stop are required.')
    trip.current_stop_sequence=session.scalar(select(RouteStop.sequence).where(RouteStop.route_id==trip.route_id,RouteStop.sequence>trip.current_stop_sequence).order_by(RouteStop.sequence).limit(1))
    trip.current_stop_selected_at=datetime.now(timezone.utc)
    session.commit()
    return arrival_view(session,trip)
