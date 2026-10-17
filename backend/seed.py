"""Repeatable, insert-only simulated seed: python seed.py."""
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from database import get_engine
from models import School, Student, Vehicle
from sample_data import STUDENTS, VEHICLE


def seed():
    with Session(get_engine()) as session, session.begin():
        rows = [
            (School, [{"id": "SCHOOL_01", "name": "Test school", "input_source": "simulated"}]),
            (Vehicle, [{**VEHICLE, "input_source": "simulated"}]),
            (Student, [{**student, "input_source": "simulated"} for student in STUDENTS]),
        ]
        for model, records in rows:
            session.execute(insert(model).values(records).on_conflict_do_nothing(index_elements=["id"]))
    print("Simulated seed committed; existing records were preserved.")


if __name__ == "__main__":
    try:
        seed()
    except (SQLAlchemyError, RuntimeError, ValueError):
        raise SystemExit("Seed failed. Check backend/.env, database permissions and migrations; no credentials are printed.") from None
