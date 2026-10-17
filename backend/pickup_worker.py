"""Local single-process expiry scheduler. Database locks make repeats idempotent."""
from datetime import datetime, timezone
from threading import Event, Lock
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_engine
from models import Trip, PickupWindow
from pickup_windows import clock, policy, outcomes, expire_window

_status_lock=Lock()
_status={'running':False,'last_tick_at':None,'last_error':None,'expired_windows':0}


def worker_status():
    with _status_lock: return dict(_status)


def expire_due(limit=100):
    with Session(get_engine()) as session:
        ids=session.execute(select(PickupWindow.id,PickupWindow.trip_id).where(PickupWindow.state=='WAITING',PickupWindow.deadline_at<=clock(session))
            .order_by(PickupWindow.deadline_at,PickupWindow.id).limit(limit)).all()
    changed=0
    for id,trip_id in ids:
        with Session(get_engine()) as session:
            session.scalar(select(Trip).where(Trip.id==trip_id).with_for_update())
            window=session.scalar(select(PickupWindow).where(PickupWindow.id==id).with_for_update())
            if expire_window(session,window,outcomes(session,window),clock(session),'expiry_worker'): changed+=1
            session.commit()
    return changed


def pickup_loop(stop:Event):
    interval=policy()['worker_interval_seconds']
    with _status_lock: _status['running']=True
    try:
        while not stop.is_set():
            try:
                changed=expire_due()
                with _status_lock:
                    _status.update(last_tick_at=datetime.now(timezone.utc).isoformat(),last_error=None,expired_windows=_status['expired_windows']+changed)
            except Exception as error:
                # No SQL strings, parameters, connection URLs or credentials are logged.
                with _status_lock: _status.update(last_tick_at=datetime.now(timezone.utc).isoformat(),last_error=type(error).__name__)
            stop.wait(interval)
    finally:
        with _status_lock: _status['running']=False
