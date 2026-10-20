"""Read-only local phone-ingestion evidence; never prints coordinates or credentials."""
import argparse
from datetime import datetime,timezone
from sqlalchemy import select,text,func
from sqlalchemy.orm import Session
from database import get_engine
from models import Vehicle,VehiclePosition,TrackingSession,Trip
from positions import accuracy_quality


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking-id',help='DEVICE_ ID shown in Driver; NOT its private credential')
    def bounded_limit(value):
        count=int(value)
        if not 1<=count<=50:raise argparse.ArgumentTypeError('Use --limit between 1 and 50.')
        return count
    parser.add_argument('--limit',type=bounded_limit,default=10,help='Recent accepted samples to list, 1..50; no coordinates')
    args=parser.parse_args()
    with Session(get_engine()) as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        print('Database:',session.scalar(text('SELECT current_database()')))
        print('Migration:',session.scalar(text('SELECT version_num FROM alembic_version')))
        print('Non-synthetic vehicles:',session.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.input_source!='simulated')))
        print('Phone sessions:',session.scalar(select(func.count()).select_from(TrackingSession).where(TrackingSession.kind=='phone')))
        print('Actual-device samples:',session.scalar(select(func.count()).select_from(VehiclePosition).where(VehiclePosition.source=='actual_device')))
        if not args.tracking_id:
            print('Pass --tracking-id DEVICE_... after your actual phone upload. No upload performed.');return
        grant=session.get(TrackingSession,args.tracking_id)
        if not grant:parser.error('Unknown tracking-session ID.')
        print('Session:',grant.id,'kind:',grant.kind,'vehicle:',grant.vehicle_id,'trip:',grant.trip_id,'revoked:',bool(grant.revoked_at))
        trip=session.get(Trip,grant.trip_id)
        print('Observation context:','adult_landmark_field_test (excluded from measured student-trip exports)' if trip and (trip.pickup_settings or {}).get('adult_phone_field_test') else 'registered transport / inspect provenance')
        count=session.scalar(select(func.count()).select_from(VehiclePosition).where(VehiclePosition.tracking_session_id==grant.id))
        print('Persisted samples:',count)
        unique=session.scalar(select(func.count(func.distinct(VehiclePosition.sample_id))).where(VehiclePosition.tracking_session_id==grant.id))
        print('Unique sample IDs:',unique,'duplicate persisted IDs:',count-unique)
        rows=session.scalars(select(VehiclePosition).where(VehiclePosition.tracking_session_id==grant.id).order_by(VehiclePosition.recorded_at.desc(),VehiclePosition.id).limit(args.limit)).all()
        if not rows:
            print('No position evidence. Actual phone ingestion NOT verified.');return
        row=rows[0]
        print('Latest position ID:',row.id,'source:',row.source)
        print('Recorded:',row.recorded_at.isoformat(),'received:',row.received_at.isoformat())
        print('Accuracy metres:',row.accuracy_m,'quality:',accuracy_quality(row),'speed available:',row.speed_mps is not None)
        age=max(0,(datetime.now(timezone.utc)-row.recorded_at).total_seconds())
        print('Age seconds:',round(age,1),'stale:',age>60)
        print('Recent accepted samples (newest recorded first; coordinates omitted):')
        for item in rows:
            print({'position_id':item.id,'sample_id':item.sample_id,'source':item.source,
                   'recorded_at':item.recorded_at.isoformat(),'received_at':item.received_at.isoformat(),
                   'accuracy_m':item.accuracy_m,'accuracy_quality':accuracy_quality(item),
                   'speed_available':item.speed_mps is not None})
        if grant.kind!='phone' or any(item.source!='actual_device' or item.vehicle_id!=grant.vehicle_id or item.trip_id!=grant.trip_id for item in rows):
            print('Not verified as actual-phone evidence: simulation session or inconsistent source/binding.');return
        print('Stored phone-session binding checked; physical Android origin still requires the phone test/operator confirmation.')


if __name__=='__main__':main()
