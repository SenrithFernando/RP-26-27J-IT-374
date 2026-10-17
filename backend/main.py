from contextlib import asynccontextmanager
from threading import Event, Thread

from typing import Literal

from fastapi import FastAPI, HTTPException

from optimizer import generate_route
from sample_data import STUDENTS, VEHICLE
from persistence import router as persistence_router
from geocoding import router as geocoding_router
from locations import router as locations_router
from route_api import router as database_routes_router
from planning_api import router as planning_router
from planning_worker import recovery_loop
from ml.api import router as ml_router
from ml.predictor import predictor
from traffic_provider import baseline_repository
from road_geometry import router as road_geometry_router
from trips import router as trips_router
from positions import router as positions_router
from arrivals import router as arrivals_router, configured_settings
from pickup_windows import router as pickup_router, policy as pickup_policy
from pickup_worker import pickup_loop, worker_status
from notifications import router as notification_router
from operational_monitor import router as operational_router, configured_operational_settings

@asynccontextmanager
async def lifespan(app):
    configured_settings()  # Fail early on invalid arrival thresholds; do not log credentials.
    pickup_policy()
    configured_operational_settings()
    predictor.load()
    baseline_repository.load()
    stop = Event()
    worker = Thread(target=recovery_loop, args=(stop,), daemon=True, name="pre-trip-recovery")
    expiry_worker = Thread(target=pickup_loop, args=(stop,), daemon=True, name="pickup-expiry")
    worker.start(); expiry_worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=5); expiry_worker.join(timeout=5)


app = FastAPI(title="SafeRide-LK Routing API", lifespan=lifespan)
app.include_router(persistence_router)
app.include_router(geocoding_router)
app.include_router(locations_router)
# Specific /routes/latest must precede the legacy /routes/{direction} route.
app.include_router(database_routes_router)
app.include_router(planning_router)
app.include_router(ml_router)
app.include_router(road_geometry_router)
app.include_router(trips_router)
app.include_router(positions_router)
app.include_router(arrivals_router)
app.include_router(pickup_router)
app.include_router(notification_router)
app.include_router(operational_router)

@app.get("/pickup-worker/status")
def pickup_worker_status():
    return worker_status()


@app.get("/")
def home():
    return {"message": "SafeRide-LK backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/students")
def get_students():
    return STUDENTS


@app.get("/vehicle")
def get_vehicle():
    return VEHICLE


@app.get("/routes/{direction}")
def get_route(direction: Literal["morning", "afternoon"]):
    try:
        return generate_route(direction)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

