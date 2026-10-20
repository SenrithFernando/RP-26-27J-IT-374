"""PM manual test evidence through the existing import log and pickup state machine."""
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select
from models import Trip,RouteVersion,PickupOutcome,PickupWindow,LandmarkInputEvent
from pickup_windows import clock,outcomes,expire_window,change_outcome,aggregate,audit


def apply_pm_test_evidence(session,scenario,envelope,record):
    trip=session.scalar(select(Trip).where(Trip.id==record.trip_id).with_for_update())
    if not trip or trip.vehicle_id!=scenario.vehicle_id or trip.direction!='afternoon' or trip.state!='ACTIVE':
        raise HTTPException(409,'Select an isolated ACTIVE afternoon trip; closed/physical morning trips cannot receive PM test events.')
    route=session.get(RouteVersion,trip.route_id)
    if route.service_date!=record.service_date or route.input_snapshot.get('daily',{}).get('scenario_id')!=scenario.id:
        raise HTTPException(422,'Trip, service date and scenario do not match.')
    sid='MALABE_PP1_'+record.student_external_id
    row=session.scalar(select(PickupOutcome).where(PickupOutcome.trip_id==trip.id,PickupOutcome.student_id==sid))
    if not row:raise HTTPException(422,'Participant is not an eligible pickup in this saved trip manifest.')
    window=session.scalar(select(PickupWindow).where(PickupWindow.id==row.window_id).with_for_update())
    rows=outcomes(session,window);now=clock(session)
    if window.started_at is None or window.deadline_at is None:raise HTTPException(409,'Confirmed school arrival and release must open the window first.')
    effective=envelope.occurred_at;resolution=record.resolves_event_id is not None
    if resolution:
        original=session.get(LandmarkInputEvent,record.resolves_event_id)
        data=original.payload if original else {};items=data.get('records',[])
        if data.get('kind')!='boarding' or data.get('producer')!='manual_test' or len(items)!=1 or items[0].get('direction')!='afternoon' or items[0].get('trip_id')!=trip.id or items[0].get('student_external_id')!=record.student_external_id or items[0].get('resolves_event_id'):
            raise HTTPException(422,'Resolution must reference matching original manual PM test evidence.')
        effective=datetime.fromisoformat(data['occurred_at'])
        if original.received_at<window.deadline_at:raise HTTPException(422,'Referenced evidence was not a delayed receipt.')
    if effective<window.started_at:raise HTTPException(422,'Boarding evidence predates the confirmed/released school window.')
    expire_window(session,window,rows,now,'expiry_test_evidence')
    changed=False
    reason=(f'event_id={envelope.event_id}; resolves={record.resolves_event_id}; '+envelope.reason)[:500]
    if row.state=='CANCELLED':raise HTTPException(409,'Cancelled pickup cannot be confirmed by test evidence.')
    if effective>=window.deadline_at:
        status='after_deadline_recorded_not_confirmed'
        audit(session,window,sid,row.state,row.state,effective,now,'manual_test_after_deadline',reason)
    elif row.state=='PICKED_UP':
        status='already_confirmed_history_retained'
        audit(session,window,sid,row.state,row.state,effective,now,'manual_test_evidence',reason)
    elif now>=window.deadline_at and not resolution:
        status='delayed_evidence_pending_admin_review'
        audit(session,window,sid,row.state,row.state,effective,now,'manual_test_delayed_evidence',reason)
    else:
        if row.state not in ('WAITING','MISSED') or (row.state=='MISSED' and not resolution):raise HTTPException(409,'Pickup is not eligible for this confirmation.')
        source='manual_test_delayed_review' if resolution else 'manual_test_adapter'
        change_outcome(session,window,row,'PICKED_UP',effective,now,source,reason)
        aggregate(session,window,rows,now,source,'Manual test boarding evidence; earlier history and alerts retained.')
        status='delayed_evidence_resolved' if resolution else 'test_boarding_confirmed'
        changed=True
    return {'status':status,'trip_id':trip.id,'student_id':sid,'window_id':window.id,'outcome_state':row.state,
        'outcome_changed':changed,'effective_at':effective.isoformat(),'received_at':now.isoformat(),
        'provenance':'manual_test / landmark_test; no card scan','delivery_status':'not_applicable_to_boarding_evidence',
        '_received_at':now}
