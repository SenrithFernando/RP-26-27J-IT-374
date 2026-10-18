"""Source-labelled positions and transactional current-stop proximity processing."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4
import os
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from models import Trip, Vehicle, VehiclePosition
from persistence import session_dependency

router = APIRouter(prefix="/routing/vehicles", tags=["Vehicle positions"])
STALE_SECONDS = 60
FUTURE_TOLERANCE_SECONDS = 30


class PositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sample_id: str = Field(min_length=1,max_length=128)
    trip_id: str | None = Field(default=None,min_length=1,max_length=64)
    source: Literal["simulation", "actual_device"]
    latitude: float = Field(ge=-90,le=90,allow_inf_nan=False)
    longitude: float = Field(ge=-180,le=180,allow_inf_nan=False)
    speed_mps: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    accuracy_m: float | None = Field(default=None,ge=0,le=100000,allow_inf_nan=False)
    recorded_at: AwareDatetime


def validate_ids(session, vehicle_id, trip_id, lock=False):
    query=select(Vehicle).where(Vehicle.id==vehicle_id)
    if lock: query=query.with_for_update()
    if session.scalar(query) is None: raise HTTPException(404,"Vehicle not found.")
    if trip_id:
        trip=session.get(Trip,trip_id)
        if trip is None: raise HTTPException(404,"Trip not found.")
        if trip.vehicle_id != vehicle_id: raise HTTPException(422,"Trip belongs to another vehicle.")


def query_positions(vehicle_id, trip_id=None):
    query=select(VehiclePosition).where(VehiclePosition.vehicle_id==vehicle_id)
    if trip_id: query=query.where(VehiclePosition.trip_id==trip_id)
    return query.order_by(VehiclePosition.recorded_at.desc(),VehiclePosition.id)


def sample(row):
    return {**{key:getattr(row,key) for key in ("id","sample_id","vehicle_id","trip_id","source","latitude","longitude","speed_mps","accuracy_m","tracking_session_id","recorded_at","received_at")},
        'accuracy_quality':accuracy_quality(row),'poor_accuracy_threshold_m':poor_accuracy_threshold()}


def poor_accuracy_threshold():
    value=float(os.getenv('GPS_POOR_ACCURACY_METRES','50'))
    if not 1<=value<=1000:raise ValueError('GPS_POOR_ACCURACY_METRES must be between 1 and 1000.')
    return value


def accuracy_quality(row):
    if getattr(row,'accuracy_m',None) is None:return 'unknown'
    return 'poor' if row.accuracy_m>poor_accuracy_threshold() else 'acceptable'


def latest_result(session,vehicle_id,trip_id=None,simulation_only=False):
    query=query_positions(vehicle_id,trip_id)
    if simulation_only:query=query.where(VehiclePosition.source=='simulation')
    row=session.scalar(query.limit(1))
    age=max(0,(datetime.now(timezone.utc)-row.recorded_at).total_seconds()) if row else None
    return {"position":sample(row) if row else None,"age_seconds":age,
        "status":"unknown" if row is None or accuracy_quality(row)=='poor' else "stale" if age>STALE_SECONDS else "fresh",
        "stale_after_seconds":STALE_SECONDS,"movement_state":"unknown",
        "note":"Missing/stale GPS does not mean stopped. Position alone does not verify arrival or passenger events."}


@router.post("/{vehicle_id}/positions")
def ingest(vehicle_id:str,payload:PositionInput,session:Session=Depends(session_dependency)):
    return store_position(vehicle_id,payload,session)


def store_position(vehicle_id,payload,session,tracking_session_id=None):
    now=datetime.now(timezone.utc)
    if payload.recorded_at > now+timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        raise HTTPException(422,"recorded_at is more than 30 seconds in the future.")
    validate_ids(session,vehicle_id,payload.trip_id,lock=True)
    if payload.trip_id:
        trip=session.get(Trip,payload.trip_id)
        from models import SyntheticTripProvenance
        if payload.source == "actual_device" and session.get(SyntheticTripProvenance, trip.id):
            raise HTTPException(422,"Registered synthetic fixture trips accept simulation positions only.")
        if trip.pickup_settings and trip.pickup_settings["mode"]=="simulation_demo" and payload.source!="simulation":
            raise HTTPException(422,"Accelerated pickup demo accepts only simulation positions, never actual-device samples.")
    matches=session.scalars(select(VehiclePosition).where(VehiclePosition.vehicle_id==vehicle_id,or_(
        (VehiclePosition.source==payload.source)&(VehiclePosition.sample_id==payload.sample_id),
        VehiclePosition.recorded_at==payload.recorded_at)).limit(2)).all()
    if matches:
        existing=matches[0]
        fields=("trip_id","source","latitude","longitude","speed_mps","accuracy_m","recorded_at")
        if any(getattr(row,k)!=getattr(payload,k) for row in matches for k in fields) or any(row.tracking_session_id!=tracking_session_id for row in matches):
            raise HTTPException(409,"Sample ID or recorded timestamp already exists with different content.")
        result={"operational_monitoring":"duplicate_ignored","sample":sample(existing),"duplicate":True,"advances_latest":False,"arrival_detection":"duplicate_ignored"}
        session.commit()
        return result
    latest=session.scalar(query_positions(vehicle_id).limit(1))
    advances=latest is None or payload.recorded_at>latest.recorded_at
    row=VehiclePosition(id="POS_"+uuid4().hex,vehicle_id=vehicle_id,received_at=now,tracking_session_id=tracking_session_id,**payload.model_dump())
    session.add(row); session.flush()
    from arrivals import process_position
    usable=accuracy_quality(row)!='poor'
    if advances and not usable and row.trip_id:
        # Unusable observations break sustained candidates, but never erase
        # confirmed arrival/pickup/episode history or manufacture recovery.
        from models import TripStopArrival,TripOperationalMonitor
        trip=session.get(Trip,row.trip_id)
        if trip.state=='ACTIVE':
            candidate=session.get(TripStopArrival,(trip.id,trip.current_stop_sequence)) if trip.current_stop_sequence is not None else None
            if candidate and candidate.arrived_at is None:
                candidate.candidate_started_at=None;candidate.observation_count=0
            monitor=session.get(TripOperationalMonitor,trip.id)
            if monitor:
                monitor.progress={};monitor.last_recorded_at=None
    arrival_result=process_position(session,row,datetime.now(timezone.utc)) if advances and usable else "poor_accuracy_ignored" if not usable else "out_of_order"
    from operational_monitor import process_operational_position
    operational_result=process_operational_position(session,row,datetime.now(timezone.utc)) if advances and usable else "poor_accuracy_ignored" if not usable else "out_of_order"
    session.commit()
    return {"operational_monitoring":operational_result,"sample":sample(row),"duplicate":False,"advances_latest":advances,"arrival_detection":arrival_result}


@router.get("/{vehicle_id}/positions/latest")
def latest(vehicle_id:str,trip_id:str|None=Query(None,min_length=1,max_length=64),session:Session=Depends(session_dependency),request:Request=None):
    validate_ids(session,vehicle_id,trip_id)
    return latest_result(session,vehicle_id,trip_id,simulation_only=bool(request and request.state.principal.login.mode=='demo'))


@router.get("/{vehicle_id}/positions")
def history(vehicle_id:str,trip_id:str|None=Query(None,min_length=1,max_length=64),limit:int=Query(100,ge=1,le=500),
            window_seconds:int=Query(3600,ge=1,le=604800),session:Session=Depends(session_dependency),request:Request=None):
    validate_ids(session,vehicle_id,trip_id)
    cutoff=datetime.now(timezone.utc)-timedelta(seconds=window_seconds)
    query=query_positions(vehicle_id,trip_id).where(VehiclePosition.recorded_at>=cutoff)
    if request and request.state.principal.login.mode=='demo':query=query.where(VehiclePosition.source=='simulation')
    rows=session.scalars(query.limit(limit+1)).all()
    return {"positions":[sample(row) for row in rows[:limit]],"limit":limit,"truncated":len(rows)>limit,
        "window_seconds":window_seconds,"order":"recorded_at_desc"}
