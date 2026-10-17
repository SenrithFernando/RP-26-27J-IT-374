"""Recover durable pending events after a disconnect or backend restart."""
from threading import Event
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_engine
from models import RoutingEvent
from planning_orchestration import process_event_safe


def recover_pending():
    with Session(get_engine()) as session:
        ids = session.scalars(select(RoutingEvent.id).where(RoutingEvent.status == "pending").order_by(RoutingEvent.created_at).limit(10)).all()
    for event_id in ids:
        with Session(get_engine()) as session:
            process_event_safe(session, event_id)


def recovery_loop(stop: Event):
    while not stop.is_set():
        try: recover_pending()
        except Exception:
            # Missing DB/config/migrations never logs credentials; pending work is
            # retained in PostgreSQL. API health remains independent of storage.
            pass
        stop.wait(5)
