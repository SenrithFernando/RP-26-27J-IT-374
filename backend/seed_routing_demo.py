"""Insert-only, explicitly simulated multi-school fixtures for Stage 4 verification."""
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from database import get_engine
from models import School, Student, Vehicle


def seed_demo(prefix="S4"):
    """Default repeatable demo IDs; callers may choose a unique isolated prefix."""
    schools = [
        dict(id="S4_SCHOOL_A", name="Stage 4 synthetic school A", latitude=6.9300, longitude=79.8600,
             morning_deadline_seconds=28800, afternoon_finish_seconds=46800),
        dict(id="S4_SCHOOL_B", name="Stage 4 synthetic school B", latitude=6.9400, longitude=79.8700,
             morning_deadline_seconds=30600, afternoon_finish_seconds=48600),
    ]
    schools = [{**row, "address": row["name"] + ", synthetic test location", "input_source": "simulated", "location_confirmed": True, "location_method": "manual"} for row in schools]
    vehicles = [dict(id=f"S4_VAN_{suffix}", capacity=2, input_source="simulated",
                     start_address="Synthetic vehicle start", start_latitude=6.919 + offset, start_longitude=79.850,
                     start_confirmed=True, start_method="manual", end_address="Synthetic vehicle end",
                     end_latitude=6.920 + offset, end_longitude=79.851, end_confirmed=True, end_method="manual")
                for suffix, offset in (("A", 0), ("B", .002))]
    students = [dict(id=f"S4_STUDENT_{number:02}", name=f"Stage 4 synthetic student {number:02}",
                     home_id=f"S4_HOME_{number:02}", school_id="S4_SCHOOL_A" if number % 2 else "S4_SCHOOL_B",
                     vehicle_id="S4_VAN_A" if number <= 6 else "S4_VAN_B",
                     home_latitude=6.921 + number * .00025, home_longitude=79.851 + number * .0003,
                     home_address=f"Synthetic home {number}", input_source="simulated", location_confirmed=True,
                     location_method="manual", active=True) for number in range(1, 13)]
    if prefix != "S4":
        for rows in (schools, vehicles, students):
            for row in rows:
                for key in ("id", "home_id", "school_id", "vehicle_id"):
                    if key in row:
                        row[key] = row[key].replace("S4_", prefix + "_", 1)
    reports = []
    with Session(get_engine()) as session, session.begin():
        for model, rows in ((School, schools), (Vehicle, vehicles), (Student, students)):
            result = session.execute(insert(model).values(rows).on_conflict_do_nothing(index_elements=["id"]).returning(model.id))
            inserted = result.scalars().all()
            reports.append((model.__tablename__, inserted))
    for table, inserted in reports:
        print(f"{table}: inserted {len(inserted)}; IDs: {', '.join(inserted) or '(none; existing IDs preserved)'}")
    print("Synthetic Stage 4 fixture committed. No existing records were overwritten or deleted.")


if __name__ == "__main__":
    try: seed_demo()
    except (SQLAlchemyError, RuntimeError, ValueError):
        raise SystemExit("Demo seed failed. Check local database configuration and migrations; credentials are not printed.") from None
