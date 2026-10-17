"""Generate reproducible SYNTHETIC targets from a snapshot of current DB locations."""
import argparse
import csv
from datetime import datetime, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import sys
from zoneinfo import ZoneInfo

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from database import get_engine
from models import School, Student, Vehicle
from sqlalchemy import select
from sqlalchemy.orm import Session
from travel_time import Coordinate, DeterministicSimulationProvider
from ml.features import DISCLAIMER, feature_record, segment_id

DEFAULT_OUTPUT = BACKEND.parent / 'data' / 'travel_times_synthetic.csv'


def current_locations():
    with Session(get_engine()) as session:
        students = session.scalars(select(Student).where(Student.active.is_(True)).order_by(Student.id)).all()
        schools = {s.id: s for s in session.scalars(select(School)).all()}
        vehicles = {v.id: v for v in session.scalars(select(Vehicle)).all()}
        locations = {}
        def add(id, lat, lon, confirmed, source):
            if confirmed and lat is not None and lon is not None:
                locations[id] = {'id': id, 'latitude': lat, 'longitude': lon, 'location_input_source': source}
        for student in students:
            add(student.home_id, student.home_latitude, student.home_longitude, student.location_confirmed, student.input_source)
            school = schools[student.school_id]
            add(school.id, school.latitude, school.longitude, school.location_confirmed, school.input_source)
            vehicle = vehicles[student.vehicle_id]
            for position in ('start', 'end'):
                add(f'{vehicle.id}:{position}', getattr(vehicle, f'{position}_latitude'), getattr(vehicle, f'{position}_longitude'), getattr(vehicle, f'{position}_confirmed'), vehicle.input_source)
        return sorted(locations.values(), key=lambda item: item['id'])


def generate(locations, seed=20261015):
    if len(locations) < 2: raise ValueError('At least two confirmed current routing locations are required; no coordinates will be invented.')
    rng = random.Random(seed)
    coordinates = [Coordinate(item['latitude'], item['longitude']) for item in locations]
    distances = DeterministicSimulationProvider().precompute(coordinates, 'morning', 21600).distance_metres
    # Exclude colocated/very distant arcs from this local development target population.
    destinations = {i: [j for j in range(len(locations)) if 25 <= distances[i][j] <= 30_000] for i in range(len(locations))}
    origins = [i for i, values in destinations.items() if values]
    if not origins: raise ValueError('No local non-colocated segments between 25 and 30000 metres in current locations.')
    start = datetime(2026, 7, 6, tzinfo=ZoneInfo('Asia/Colombo'))
    rows = []
    for week in range(8):
        for day in range(5):
            for trip in range(10):
                stamp = start + timedelta(weeks=week, days=day, hours=5.5 + 1.2 * trip, minutes=rng.uniform(0, 15))
                origin = rng.choice(origins)
                trip_weather = int(rng.random() < .28)
                trip_id = f'SYN_W{week:02}_D{day}_T{trip:02}'
                for _ in range(5):
                    stamp = stamp.replace(microsecond=0)
                    destination = rng.choice(destinations[origin])
                    oid, did = locations[origin]['id'], locations[destination]['id']
                    distance = distances[origin][destination]
                    record = feature_record(oid, did, stamp, distance, trip_weather)
                    hour = record['hour']
                    rush = 0.9 * math.exp(-((hour - 7.6) / .9) ** 2) + .6 * math.exp(-((hour - 14.2) / 1.3) ** 2)
                    segment_effect = .8 + int(sha256(segment_id(oid, did).encode()).hexdigest()[:8], 16) / 0xffffffff * .45
                    weekday_effect = 1 + .035 * math.sin(day * 1.4)
                    duration = (18 + distance / 7.5 * segment_effect * (1 + rush) * weekday_effect * (1 + .22 * trip_weather + .13 * trip_weather * rush))
                    duration *= math.exp(rng.gauss(0, .10))
                    duration = round(max(1., duration), 3)
                    # Some synthetic weather inputs are unobserved; targets still reflect latent weather.
                    weather = '' if rng.random() < .12 else trip_weather
                    rows.append(dict(trip_id=trip_id, origin_id=oid, destination_id=did, departure_timestamp=stamp.isoformat(timespec='seconds'),
                        distance_m=distance, hour=round(record['hour'], 8), day_of_week=record['day_of_week'], weather_flag=weather,
                        duration_s=duration, data_source='synthetic'))
                    stamp += timedelta(seconds=duration + 30)
                    origin = destination
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--locations', type=Path, help='Reuse saved location JSON instead of reading PostgreSQL.')
    parser.add_argument('--seed', type=int, default=20261015)
    args = parser.parse_args()
    locations = json.loads(args.locations.read_text(encoding='utf-8')) if args.locations else current_locations()
    rows = generate(locations, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    args.output.with_suffix('.locations.json').write_text(json.dumps(locations, indent=2), encoding='utf-8')
    manifest = {'seed': args.seed, 'rows': len(rows), 'trips': len({r['trip_id'] for r in rows}), 'weeks': 8,
        'data_source': 'synthetic', 'disclaimer': DISCLAIMER, 'location_count': len(locations),
        'csv_sha256': sha256(args.output.read_bytes()).hexdigest(), 'distance_source': 'haversine_straight_line',
        'target_recipe': 'Nonlinear morning/afternoon peaks, stable directed-segment effect, weekday and weather interactions, lognormal noise; synthetic targets, never measured times.'}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__': main()
