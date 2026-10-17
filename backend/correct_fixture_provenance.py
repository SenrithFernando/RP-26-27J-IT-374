"""Dry-run by default; exact reviewed allowlist, append-only audit, no event replay."""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database import get_engine
from models import (VehiclePosition, Vehicle, Trip, RouteVersion, TripStopArrival,
    PickupWindow, PickupOutcome, PickupTransition, OperationalEpisode,
    TripOperationalMonitor, MissedPickupNotification, ProvenanceCorrection)
from data_provenance import register_synthetic_trip, snapshot_sources, ARRIVAL_GENERATOR

CODE = "s9b-source-change-fixture-v1"
REASON = "Controlled-clock Stage 9B generated sample 28 tested source changes; no physical device observation."
# Exact reviewed identities. Prefix matching alone never authorizes a rewrite.
REVIEWED = {
 "POS_0598d0d48fa549a987bbb000c5057d2a": ("S9B_2f7c7c9e_V", "TRIP_6bb8dfb3a4f74959968488eff644c42a"),
 "POS_15af973a191c491bac63480317b0d870": ("S9B_f3e4eeb3_V", "TRIP_f6efc341bace4b51a2dacf2be7d0fe4d"),
 "POS_7ec5c3c5c5e34de7ae1a4c955107904a": ("S9B_6e6d0daf_V", "TRIP_c6610cb20bba448688c7a191d86fa7ab"),
 "POS_8a56cdcdd4b847e28b37e24515559d64": ("S9B_1a9c1ecc_V", "TRIP_1bb65e3dec2742a1aef3f92b61992ca0"),
 "POS_d0bb16045b2a4e369de95ae207e80303": ("S9B_d81201ac_V", "TRIP_eefe77aa7cf04f9aae6a7d0bfd90c21c"),
}


def verify_fixture(session, position_id, vehicle_id, trip_id):
    p=session.get(VehiclePosition,position_id)
    if p is None or (p.vehicle_id,p.trip_id,p.sample_id)!=(vehicle_id,trip_id,'28'):
        raise ValueError("Reviewed position identity differs or is missing; no correction applied.")
    vehicle=session.get(Vehicle,vehicle_id);trip=session.get(Trip,trip_id)
    route=session.get(RouteVersion,trip.route_id) if trip else None
    sources=list(snapshot_sources(route.input_snapshot)) if route else []
    if not vehicle or vehicle.input_source!='simulated' or not sources or set(sources)!={'simulated'}:
        raise ValueError("Reviewed synthetic context no longer matches; no correction applied.")
    for sample_id,offset in [('27',-1),('29',1)]:
        other=session.scalar(select(VehiclePosition).where(VehiclePosition.vehicle_id==vehicle_id,
            VehiclePosition.trip_id==trip_id,VehiclePosition.sample_id==sample_id))
        if not other or other.source!='simulation' or other.recorded_at!=p.recorded_at+timedelta(seconds=offset) or (other.latitude,other.longitude)!=(p.latitude,p.longitude):
            raise ValueError("Controlled-clock neighbouring fixture evidence differs.")
    if p.source=='simulation':
        audit=session.scalar(select(ProvenanceCorrection).where(ProvenanceCorrection.entity_table=='vehicle_positions',
            ProvenanceCorrection.entity_key==p.id,ProvenanceCorrection.field_name=='source',ProvenanceCorrection.correction_code==CODE))
        if not audit:raise ValueError("Source already changed without expected audit; manual review required.")
    elif p.source!='actual_device':raise ValueError("Unexpected original source.")
    return p


def correct_field(session, row, table, key, field, replacements, changes):
    previous=getattr(row,field)
    if previous not in replacements:return
    corrected=replacements[previous]
    session.add(ProvenanceCorrection(id='PROV_'+uuid4().hex,entity_table=table,entity_key=key,
        field_name=field,previous_source=previous,corrected_source=corrected,reason=REASON,
        correction_code=CODE,corrected_at=session.scalar(select(func.clock_timestamp()))))
    setattr(row,field,corrected)
    changes.append({'table':table,'key':key,'field':field,'previous_source':previous,'corrected_source':corrected})


def run(session, apply=False):
    # Same vehicle->trip ordering as ingest; serializes correction against GPS/expiry.
    if apply:
        session.scalars(select(Vehicle).where(Vehicle.id.in_([v for v,t in REVIEWED.values()])).order_by(Vehicle.id).with_for_update()).all()
        session.scalars(select(Trip).where(Trip.id.in_([t for v,t in REVIEWED.values()])).order_by(Trip.id).with_for_update()).all()
    positions=[verify_fixture(session,id,*pair) for id,pair in REVIEWED.items()]
    changes=[];checked=Counter()
    for p in positions:
        if apply:register_synthetic_trip(session,p.trip_id,ARRIVAL_GENERATOR,REASON)
        if apply:correct_field(session,p,'vehicle_positions',p.id,'source',{'actual_device':'simulation'},changes)
        elif p.source=='actual_device':changes.append({'table':'vehicle_positions','key':p.id,'field':'source','previous_source':p.source,'corrected_source':'simulation'})
        for model,fields in [
            (TripStopArrival,['source']), (PickupWindow,[]), (PickupOutcome,['action_source']),
            (PickupTransition,['action_source']), (OperationalEpisode,['source','recovery_source']),
            (TripOperationalMonitor,['last_source']), (MissedPickupNotification,['position_source'])]:
            query=select(model)
            if model is PickupTransition:
                query=query.where(model.window_id.in_(select(PickupWindow.id).where(PickupWindow.trip_id==p.trip_id)))
            else:query=query.where(model.trip_id==p.trip_id)
            rows=session.scalars(query).all();checked[model.__tablename__]+=len(rows)
            for row in rows:
                key=getattr(row,'id',None) or (p.trip_id+':'+str(row.stop_sequence) if hasattr(row,'stop_sequence') else p.trip_id)
                for field in fields:
                    if apply:correct_field(session,row,model.__tablename__,key,field,
                        {'actual_device':'simulation','arrival_actual_device':'arrival_simulation'},changes)
                    elif getattr(row,field) in ('actual_device','arrival_actual_device'):
                        changes.append({'table':model.__tablename__,'key':key,'field':field,'previous_source':getattr(row,field)})
    if apply:session.commit()
    else:session.rollback()
    return {'applied':apply,'reviewed_positions':len(positions),'changes':changes,
        'corrected_counts':dict(Counter(c['table'] for c in changes)),'derived_records_checked':dict(checked),
        'observation_store':'No measured segment-observation table/dataset exists; measured lineage gate added separately.',
        'events_replayed':0,'records_deleted':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path);args=parser.parse_args()
    with Session(get_engine()) as session:report=run(session,args.apply)
    rendered=json.dumps(report,indent=2)
    if args.report:args.report.write_text(rendered,encoding='utf-8')
    print(rendered)


if __name__=='__main__':main()
