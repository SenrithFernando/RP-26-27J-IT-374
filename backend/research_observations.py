"""Reviewed adjacent-stop GPS observations. Never automatic ML training labels."""
import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from persistence import session_dependency
from models import (ResearchCollection, TravelObservation, SegmentEstimate, Trip, RouteVersion, TripStopArrival,
    RouteStop, VehiclePosition, TrackingSession, SyntheticTripProvenance, OperationalEpisode)
from arrivals import distance_m, settings_for
from positions import accuracy_quality
from ml.features import feature_record, SCHEMA_VERSION
from auth import deny

router=APIRouter(prefix='/research',tags=['Reviewed travel-time research'])
Dataset=Literal['synthetic','stationary_adult_phone','moving_adult_landmark','authorized_operational']

class Prepare(BaseModel):
    model_config=ConfigDict(extra='forbid')
    trip_id:str=Field(min_length=1,max_length=64)
    dataset:Dataset
    reason:str=Field(min_length=10,max_length=1000)
    consent_confirmed:bool=Field(strict=True)

class Dwell(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start:AwareDatetime
    end:AwareDatetime
    kind:Literal['service','dwell','interruption']
    reason:str=Field(min_length=5,max_length=300)

class Candidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    trip_id:str=Field(min_length=1,max_length=64)
    origin_sequence:int=Field(ge=1)
    destination_sequence:int=Field(ge=2)
    departure_position_id:str|None=Field(default=None,max_length=64)
    arrival_position_id:str|None=Field(default=None,max_length=64)
    dwell_reviewed:bool=Field(default=False,strict=True)
    intervals:list[Dwell]=Field(default_factory=list,max_length=100)
    reason:str=Field(min_length=10,max_length=1000)

class Review(Candidate):
    status:Literal['pending','accepted','rejected']

def administrator(request):
    p=request.state.principal
    if p.user.role!='administrator' or p.login.mode!='real':deny()
    return p.user.id

def prepare_collection(session,body,actor):
    trip=session.scalar(select(Trip).where(Trip.id==body.trip_id).with_for_update())
    if not trip:raise HTTPException(404,'Trip not found.')
    existing=session.get(ResearchCollection,trip.id)
    protocol={'reason':body.reason,'consent_confirmed':body.consent_confirmed,'version':'reviewed-adjacent-segment/v1',
        'boundaries':'GPS-supported origin exit and sustained destination entry, administrator reviewed',
        'weather':'unknown until a separate timestamped weather observation exists'}
    if existing:
        if existing.dataset!=body.dataset or existing.protocol!=protocol:raise HTTPException(409,'Collection protocol is immutable; use a separate planned test trip.')
        return existing
    if trip.state!='PLANNED':raise HTTPException(409,'Prepare collection on a separate PLANNED trip before capture; completed/stationary evidence cannot be reclassified.')
    if not body.consent_confirmed:raise HTTPException(422,'Explicit authorization/consent required.')
    fixture=session.get(SyntheticTripProvenance,trip.id)
    adult=bool((trip.pickup_settings or {}).get('adult_phone_field_test'))
    if body.dataset in ('moving_adult_landmark','stationary_adult_phone'):
        from tracking import adult_field_test_allowed
        if fixture or not adult_field_test_allowed(session,trip):raise HTTPException(409,'Existing adult landmark phone-test authorization is required for this new trip.')
    if body.dataset=='authorized_operational':
        from data_provenance import snapshot_sources
        route=session.get(RouteVersion,trip.route_id)
        sources=list(snapshot_sources(route.input_snapshot))
        if fixture or adult or not sources or any(x not in ('measured','live_provider') for x in sources):
            raise HTTPException(409,'Operational collection requires authorized nonsynthetic assignments; adult landmark trips remain separate.')
    row=ResearchCollection(trip_id=trip.id,dataset=body.dataset,protocol=protocol,actor_id=actor,created_at=datetime.now(timezone.utc))
    session.add(row);session.flush();return row

def extract(session,body):
    """Sampled geofence boundaries, not arbitrary point-pair travel durations."""
    trip=session.get(Trip,body.trip_id)
    collection=session.get(ResearchCollection,body.trip_id)
    if not trip or not collection:raise HTTPException(422,'Prepare a separate collection trip first; unclassified GPS is not a segment dataset.')
    if body.destination_sequence!=body.origin_sequence+1:raise HTTPException(422,'Use adjacent saved stops, including grouped school visits.')
    origin=session.get(RouteStop,(trip.route_id,body.origin_sequence))
    destination=session.get(RouteStop,(trip.route_id,body.destination_sequence))
    if not origin or not destination:raise HTTPException(422,'Boundary stops must exist in the trip fixed route.')
    cfg=settings_for(trip)
    flags=[]
    result={'schema_version':'reviewed-adjacent-segment/v1','dataset':collection.dataset,'trip_id':trip.id,'vehicle_id':trip.vehicle_id,
        'route_id':trip.route_id,'route_version':session.get(RouteVersion,trip.route_id).version,
        'origin_id':origin.details['location_id'],'destination_id':destination.details['location_id'],
        'origin_sequence':origin.sequence,'destination_sequence':destination.sequence,'flags':flags,
        'departure_timestamp':None,'arrival_timestamp':None,'elapsed_duration_s':None,'known_service_s':None,'known_dwell_s':None,
        'duration_s':None,'position_ids':[],'gps':{},'prediction_time_features':None,'weather':'unknown',
        'boundary_method':'sampled geofence exit/entry + explicit administrator review',
        'target_schema':'gps-geofence-travel/v1; not centroid-to-centroid model training data',
        'boundary_settings':cfg.model_dump(),
        'planned_service_s':{'origin':origin.details.get('service_seconds'),'destination':destination.details.get('service_seconds')},
        'planned_service_is_not_measured':True}
    research=session.get(RouteVersion,trip.route_id).input_snapshot.get('research_journey')
    if research:
        result['travel_mode']=research['travel_mode']
        if research['travel_mode']!='driving':flags.append('non_driving_research_not_vehicle_label')
    if collection.dataset in ('synthetic','stationary_adult_phone'):flags.append('not_moving_measured_dataset')
    if trip.state!='COMPLETED':flags.append('trip_not_completed_or_interrupted')
    a=session.get(VehiclePosition,body.departure_position_id) if body.departure_position_id else None
    b=session.get(VehiclePosition,body.arrival_position_id) if body.arrival_position_id else None
    if not a or not b:
        flags.append('missing_boundary');return result
    if any(p.trip_id!=trip.id or p.vehicle_id!=trip.vehicle_id for p in (a,b)):
        raise HTTPException(422,'Boundary position belongs to another trip/vehicle.')
    elapsed=(b.recorded_at-a.recorded_at).total_seconds()
    if elapsed<=0:flags.append('invalid_boundary_order');return result
    result.update(departure_timestamp=a.recorded_at.isoformat(),arrival_timestamp=b.recorded_at.isoformat(),elapsed_duration_s=elapsed)
    # Bounded interval plus short context. The full list of evidence IDs is retained.
    rows=session.scalars(select(VehiclePosition).where(VehiclePosition.trip_id==trip.id,
        VehiclePosition.recorded_at>=a.recorded_at-timedelta(seconds=cfg.max_gap_seconds),
        VehiclePosition.recorded_at<=b.recorded_at+timedelta(seconds=cfg.dwell_seconds+cfg.max_gap_seconds))
        .order_by(VehiclePosition.recorded_at,VehiclePosition.id).limit(10001)).all()
    if len(rows)>10000:flags.append('coverage_query_limit');rows=rows[:10000]
    core=[p for p in rows if a.recorded_at<=p.recorded_at<=b.recorded_at]
    result['position_ids']=[p.id for p in core]
    gaps=[(q.recorded_at-p.recorded_at).total_seconds() for p,q in zip(core,core[1:])]
    maxgap=max(gaps,default=elapsed)
    quality=Counter(accuracy_quality(p) for p in rows)
    result['gps']={'core_sample_count':len(core),'context_sample_count':len(rows),'max_gap_s':maxgap,
        'max_allowed_gap_s':cfg.max_gap_seconds,'quality_counts':dict(quality),
        'evidence_position_ids':[p.id for p in rows],'coverage':'bounded interval; no interpolation over gaps'}
    if len(core)<3:flags.append('insufficient_coverage')
    if maxgap>cfg.max_gap_seconds:flags.append('long_gps_gap')
    if quality['poor']:flags.append('poor_accuracy')
    if quality['unknown']:flags.append('unknown_accuracy')
    for p in rows:
        if p.source!='actual_device':flags.append('non_device_evidence');continue
        grant=session.get(TrackingSession,p.tracking_session_id) if p.tracking_session_id else None
        if not grant or grant.kind!='phone' or grant.trip_id!=trip.id or grant.vehicle_id!=trip.vehicle_id:
            flags.append('untrusted_device_binding');continue
        if p.received_at<grant.created_at or p.received_at>grant.expires_at or (grant.revoked_at and p.received_at>grant.revoked_at):
            flags.append('outside_tracking_authorization')
        if p.recorded_at<grant.created_at or p.recorded_at>p.received_at:
            flags.append('recorded_timestamp_clock_skew')
    if not trip.started_at or a.recorded_at<trip.started_at or (trip.completed_at and b.recorded_at>trip.completed_at):flags.append('outside_trip_lifecycle')
    if session.get(SyntheticTripProvenance,trip.id):flags.append('registered_synthetic_trip')
    # Previous inside observation brackets the first outside exit sample.
    previous=[p for p in rows if p.recorded_at<a.recorded_at]
    after=[p for p in rows if p.recorded_at>a.recorded_at]
    dist=lambda p,s:distance_m(p.latitude,p.longitude,s.latitude,s.longitude)
    departure_ok=bool(previous and after and dist(previous[-1],origin)<=cfg.exit_radius_metres and
        dist(a,origin)>cfg.exit_radius_metres and dist(after[0],origin)>cfg.exit_radius_metres and
        (a.recorded_at-previous[-1].recorded_at).total_seconds()<=cfg.max_gap_seconds and
        (after[0].recorded_at-a.recorded_at).total_seconds()<=cfg.max_gap_seconds)
    if not departure_ok:flags.append('departure_exit_not_established')
    result['departure_boundary_uncertainty_s']=(a.recorded_at-previous[-1].recorded_at).total_seconds() if previous else None
    before=[p for p in rows if p.recorded_at<b.recorded_at]
    dwell=[p for p in rows if b.recorded_at<=p.recorded_at<=b.recorded_at+timedelta(seconds=cfg.dwell_seconds+cfg.max_gap_seconds)]
    arrival_ok=bool(before and dist(before[-1],destination)>cfg.radius_metres and dist(b,destination)<=cfg.radius_metres and
        len(dwell)>=cfg.min_observations and (dwell[-1].recorded_at-b.recorded_at).total_seconds()>=cfg.dwell_seconds and
        all(dist(p,destination)<=cfg.exit_radius_metres for p in dwell) and
        all((q.recorded_at-p.recorded_at).total_seconds()<=cfg.max_gap_seconds for p,q in zip(dwell,dwell[1:])))
    if not arrival_ok:flags.append('arrival_entry_dwell_not_established')
    result['arrival_boundary_uncertainty_s']=(b.recorded_at-before[-1].recorded_at).total_seconds() if before else None
    if distance_m(origin.latitude,origin.longitude,destination.latitude,destination.longitude)<=2*cfg.exit_radius_metres:
        flags.append('overlapping_stop_geofences')
    if session.scalar(select(OperationalEpisode.id).where(OperationalEpisode.trip_id==trip.id,
        OperationalEpisode.started_at<=b.recorded_at,
        (OperationalEpisode.recovered_at.is_(None))|(OperationalEpisode.recovered_at>=a.recorded_at)).limit(1)):
        flags.append('operational_interruption_requires_review')
    intervals=sorted(body.intervals,key=lambda x:x.start)
    valid=True
    for i,item in enumerate(intervals):
        if not a.recorded_at<=item.start<item.end<=b.recorded_at or (i and item.start<intervals[i-1].end):valid=False
    if not valid:flags.append('invalid_or_overlapping_dwell_intervals')
    if any(x.kind=='interruption' for x in intervals):flags.append('declared_interruption')
    if not body.dwell_reviewed:flags.append('dwell_not_reviewed')
    if body.dwell_reviewed and valid:
        service=sum((x.end-x.start).total_seconds() for x in intervals if x.kind=='service')
        dwell_s=sum((x.end-x.start).total_seconds() for x in intervals if x.kind=='dwell')
        result.update(known_service_s=service,known_dwell_s=dwell_s,duration_s=elapsed-service-dwell_s)
        if result['duration_s']<=0:flags.append('nonpositive_adjusted_duration')
    result['prediction_time_features']=feature_record(result['origin_id'],result['destination_id'],a.recorded_at,
        round(distance_m(origin.latitude,origin.longitude,destination.latitude,destination.longitude)),None)
    result['feature_schema_version']=SCHEMA_VERSION
    if collection.dataset=='authorized_operational':
        from data_provenance import position_exclusion_reason
        if any(position_exclusion_reason(session,p) for p in core):flags.append('student_export_lineage_exclusion')
    result['flags']=sorted(set(flags))
    return result

def save_observation(session,body,actor,previous=None):
    analysis=extract(session,body)
    status=body.status if isinstance(body,Review) else 'pending'
    raw=body.model_dump(mode='json');raw.pop('status',None)
    root='OBS_'+hashlib.sha256(f'{body.trip_id}:{body.origin_sequence}:{body.destination_sequence}'.encode()).hexdigest()[:40]
    # Trip lock serializes initial extraction/review and protects revision identity.
    session.scalar(select(Trip).where(Trip.id==body.trip_id).with_for_update())
    if previous:
        if (previous.trip_id,previous.raw['origin_sequence'],previous.raw['destination_sequence'])!=(body.trip_id,body.origin_sequence,body.destination_sequence):
            raise HTTPException(422,'A correction cannot change segment identity; create a separate candidate.')
        latest=session.scalar(select(func.max(TravelObservation.revision)).where(TravelObservation.family_id==previous.family_id))
        if latest!=previous.revision:raise HTTPException(409,'Review the latest revision; audit history is retained.')
    else:
        old=session.get(TravelObservation,root)
        if old:
            if old.raw!=raw:raise HTTPException(409,'Candidate exists. Use its review endpoint for an audited correction.')
            return old
    if status=='accepted' and analysis['flags']:raise HTTPException(422,{'message':'Cannot accept flagged observation. Preserve/reject or correct its evidence.','reasons':analysis['flags']})
    row=TravelObservation(id='OBS_'+uuid4().hex if previous else root,family_id=previous.family_id if previous else root,
        revision=previous.revision+1 if previous else 1,previous_id=previous.id if previous else None,
        trip_id=body.trip_id,route_id=analysis['route_id'],dataset=analysis['dataset'],status=status,raw=raw,analysis=analysis,
        actor_id=actor,reason=body.reason,created_at=datetime.now(timezone.utc))
    session.add(row);session.flush()
    route=session.get(RouteVersion,row.route_id)
    dest=session.get(RouteStop,(route.id,body.destination_sequence));origin=session.get(RouteStop,(route.id,body.origin_sequence))
    provider=route.result.get('provider_source') or {}
    estimate_features=None
    if provider.get('departure_timestamp'):
        try:
            estimate_features=feature_record(origin.details['location_id'],dest.details['location_id'],provider['departure_timestamp'],
                round(distance_m(origin.latitude,origin.longitude,dest.latitude,dest.longitude)),route.request_settings.get('weather_flag'))
        except (ValueError,TypeError):pass # Incomplete legacy prediction inputs remain unavailable.
    session.add(SegmentEstimate(observation_id=row.id,snapshot={'kind':'saved_planned_leg_estimate_not_measurement',
        'duration_s':dest.details.get('driving_seconds_from_previous'),'source':dest.details.get('travel_source'),
        'provider':route.result.get('provider_source'),'estimate_timestamp':route.created_at.isoformat(),
        'planned_departure':origin.details.get('departure'),'planned_departure_seconds':origin.details.get('departure_seconds'),
        'prediction_features':estimate_features,'feature_schema_version':SCHEMA_VERSION,
        'features_reconstructed_from_saved_inputs':True,
        'route_id':route.id,'route_version':route.version,'not_reestimated_at_observed_departure':True}))
    session.flush();return row

def view(row):
    return {'id':row.id,'family_id':row.family_id,'revision':row.revision,'previous_id':row.previous_id,'status':row.status,
        'dataset':row.dataset,'trip_id':row.trip_id,'route_id':row.route_id,'raw':row.raw,'analysis':row.analysis,
        'reviewer_id':row.actor_id,'reason':row.reason,'reviewed_at':row.created_at}

def latest_query():
    latest=select(TravelObservation.family_id,func.max(TravelObservation.revision).label('rev')).group_by(TravelObservation.family_id).subquery()
    return select(TravelObservation).join(latest,and_(TravelObservation.family_id==latest.c.family_id,TravelObservation.revision==latest.c.rev))

@router.get('/evidence')
def evidence(request:Request,trip_id:str,origin_sequence:int=Query(ge=1),destination_sequence:int=Query(ge=2),
             before:AwareDatetime|None=None,limit:int=Query(100,ge=1,le=500),session:Session=Depends(session_dependency)):
    administrator(request)
    trip=session.get(Trip,trip_id)
    if not trip:raise HTTPException(404,'Trip not found.')
    origin=session.get(RouteStop,(trip.route_id,origin_sequence));destination=session.get(RouteStop,(trip.route_id,destination_sequence))
    if not origin or not destination or destination_sequence!=origin_sequence+1:raise HTTPException(422,'Select adjacent stops on the fixed trip route.')
    from positions import query_positions
    q=query_positions(trip.vehicle_id,trip.id)
    if before:q=q.where(VehiclePosition.recorded_at<before)
    rows=session.scalars(q.limit(limit+1)).all();shown=rows[:limit]
    arrival=session.get(TripStopArrival,(trip.id,destination.sequence))
    return {'positions':[{'id':p.id,'recorded_at':p.recorded_at,'received_at':p.received_at,'source':p.source,
        'accuracy_m':p.accuracy_m,'accuracy_quality':accuracy_quality(p),'speed_mps':p.speed_mps,
        'origin_distance_m':round(distance_m(p.latitude,p.longitude,origin.latitude,origin.longitude),1),
        'destination_distance_m':round(distance_m(p.latitude,p.longitude,destination.latitude,destination.longitude),1)} for p in shown],
        'next_before':shown[-1].recorded_at if len(rows)>limit and shown else None,
        'boundary_settings':settings_for(trip).model_dump(),
        'destination_arrival':{'event_id':arrival.event_id,'candidate_started_at':arrival.candidate_started_at,
            'confirmed_at':arrival.arrived_at} if arrival and arrival.arrived_at else None,
        'note':'Read-only GPS history; distances support review, not automatic reliable segment labels.'}

@router.post('/collections')
def prepare(body:Prepare,request:Request,session:Session=Depends(session_dependency)):
    row=prepare_collection(session,body,administrator(request));session.commit()
    return {'trip_id':row.trip_id,'dataset':row.dataset,'protocol':row.protocol,'created_at':row.created_at}

@router.post('/observations')
def candidate(body:Candidate,request:Request,session:Session=Depends(session_dependency)):
    row=save_observation(session,body,administrator(request));session.commit();return view(row)

@router.post('/observations/{observation_id}/review')
def review(observation_id:str,body:Review,request:Request,session:Session=Depends(session_dependency)):
    actor=administrator(request);old=session.get(TravelObservation,observation_id)
    if not old:raise HTTPException(404,'Observation not found.')
    row=save_observation(session,body,actor,old);session.commit();return view(row)

@router.get('/observations')
def observations(request:Request,trip_id:str|None=None,limit:int=Query(100,ge=1,le=500),history:bool=False,session:Session=Depends(session_dependency)):
    administrator(request);q=select(TravelObservation) if history else latest_query()
    if trip_id:q=q.where(TravelObservation.trip_id==trip_id)
    rows=session.scalars(q.order_by(TravelObservation.created_at.desc(),TravelObservation.id).limit(limit+1)).all()
    return {'observations':[view(r) for r in rows[:limit]],'truncated':len(rows)>limit}

@router.get('/evaluation')
def evaluation(request:Request,trip_id:str|None=None,session:Session=Depends(session_dependency)):
    administrator(request)
    q=latest_query()
    if trip_id:q=q.where(TravelObservation.trip_id==trip_id)
    rows=session.scalars(q.limit(10001)).all();counts=Counter(r.status for r in rows[:10000]);sources=Counter(r.dataset for r in rows[:10000])
    return {'candidate_segments':len(rows[:10000]),'accepted':counts['accepted'],'rejected':counts['rejected'],'pending':counts['pending'],
        'sources':dict(sources),'flag_counts':dict(Counter(f for r in rows[:10000] for f in r.analysis.get('flags',[]))),
        'rejection_reasons':dict(Counter(f for r in rows[:10000] if r.status=='rejected' for f in (r.analysis.get('flags') or ['manual_review_rejection']))),
        'truncated':len(rows)>10000,'note':'Reviewed collection counts only. Stationary ingestion is not a moving segment label; no accuracy metrics or retraining.'}

@router.get('/export')
def export(request:Request,dataset:Literal['moving_adult_landmark','authorized_operational'],trip_id:str,session:Session=Depends(session_dependency)):
    administrator(request)
    rows=session.scalars(latest_query().where(TravelObservation.trip_id==trip_id,TravelObservation.dataset==dataset,
        TravelObservation.status=='accepted').order_by(TravelObservation.id).limit(1001)).all()
    if len(rows)>1000:raise HTTPException(422,'Export is bounded to 1000 reviewed segments per trip.')
    outcomes=[];estimates=[]
    for row in rows:
        # Revalidate raw evidence on every export. Later provenance corrections fail closed.
        current=extract(session,Candidate(**row.raw))
        if current['flags']:raise HTTPException(409,{'message':'Evidence changed; review again before export.','observation_id':row.id,'reasons':current['flags']})
        outcome={'observation_id':row.id,'review_revision':row.revision,**current,
            'data_source':'reviewed_adult_landmark_measurement' if dataset=='moving_adult_landmark' else 'measured'}
        if dataset=='authorized_operational':
            from data_provenance import validate_measured_observations
            validate_measured_observations(session,[outcome])
        outcomes.append(outcome)
        estimate=session.get(SegmentEstimate,row.id)
        estimates.append({'observation_id':row.id,**estimate.snapshot} if estimate else {'observation_id':row.id,'status':'unavailable'})
    return {'dataset':dataset,'measured_outcomes':outcomes,'provider_estimates':estimates,
        'note':'Separate reviewed research export; provider estimates are not measured targets. No real-world accuracy claim.'}
