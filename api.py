"""Local API bridge between the computer-vision process and SafeRide-LK React UI."""

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.database import database_configured, initialize_database, save_telemetry
from backend.users import authenticate_administrator


PROJECT_ROOT = Path(__file__).resolve().parent
METRICS_FILE = PROJECT_ROOT / "data" / "live_metrics.json"
FRAME_FILE = PROJECT_ROOT / "data" / "live_frame.jpg"
SPEED_FILE = PROJECT_ROOT / "data" / "vehicle_speed.json"
BUS_CAPACITY = 29

app = FastAPI(title="SafeRide-LK Local Camera API")
logger = logging.getLogger(__name__)
last_persisted_capture = 0.0
last_persist_attempt = 0.0
last_persist_failure = 0.0
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # Development access from a phone using the laptop's LAN address.
    allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?::\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AdministratorLogin(BaseModel):
    email: str
    password: str


class VehicleSpeedUpdate(BaseModel):
    speed_kmh: float
    source: str = "SIMULATED_DASHBOARD"


def read_vehicle_speed(vehicle_id: str) -> dict:
    """Load the latest speed sent by the dashboard, GPS, or OBD device."""
    default_state = {
        "vehicle_id": vehicle_id,
        "speed_kmh": 0.0,
        "source": "NOT_CONNECTED",
        "updated_at": 0.0,
    }
    if not SPEED_FILE.exists():
        return default_state
    try:
        state = json.loads(SPEED_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_state
    return state if state.get("vehicle_id") == vehicle_id else default_state


def save_vehicle_speed(vehicle_id: str, speed_kmh: float, source: str) -> dict:
    """Save a local speed state; live telemetry will carry it into Neon."""
    SPEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "vehicle_id": vehicle_id,
        "speed_kmh": round(speed_kmh, 1),
        "source": source[:60],
        "updated_at": time.time(),
    }
    temporary_file = SPEED_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state), encoding="utf-8")
    temporary_file.replace(SPEED_FILE)
    return state


def calculate_camera_risk(metrics: dict) -> dict[str, int | str]:
    """Prototype risk score derived only from currently available camera data."""
    total = int(metrics.get("total_passengers", 0))
    standing = int(metrics.get("standing", 0))
    walking = int(metrics.get("walking", 0))

    # Occupancy starts at 0 and rises proportionally toward the 29-seat bus limit.
    occupancy_risk = min(20, int((total / BUS_CAPACITY) * 20))
    if total > BUS_CAPACITY:
        occupancy_risk = min(40, 20 + (total - BUS_CAPACITY) * 2)

    # Sitting passengers add no behaviour risk. Standing/walking is capped at 30.
    behaviour_risk = min(30, standing * 5 + walking * 3)
    door_risk = 0       # Door ROI is not implemented yet.
    speed_kmh = float(metrics.get("speed_kmh", 0))
    # Prototype school-transport thresholds. Validate and tune these against
    # the applicable route and legal speed policy before real deployment.
    if speed_kmh <= 40:
        speed_risk = 0
    elif speed_kmh <= 50:
        speed_risk = 4
    elif speed_kmh <= 60:
        speed_risk = 8
    elif speed_kmh <= 70:
        speed_risk = 14
    else:
        speed_risk = 20
    sensor_risk = 0     # No RFID/IR/pressure/ultrasonic sensors connected yet.
    score = min(100, occupancy_risk + behaviour_risk + door_risk + speed_risk + sensor_risk)
    level = "LOW" if score < 20 else "MODERATE" if score < 40 else "HIGH" if score < 70 else "CRITICAL"

    return {
        "capacity": BUS_CAPACITY,
        "occupancy_risk": occupancy_risk,
        "behaviour_risk": behaviour_risk,
        "door_risk": door_risk,
        "speed_risk": speed_risk,
        "sensor_risk": sensor_risk,
        "speed_kmh": speed_kmh,
        "score": score,
        "level": level,
    }


@app.on_event("startup")
def start_database() -> None:
    if not database_configured():
        logger.warning("DATABASE_URL is not configured; telemetry will stay local.")
        return
    try:
        initialize_database()
        logger.info("Neon telemetry storage is ready.")
    except Exception:
        # The dashboard should remain usable if the network or database is down.
        logger.exception("Neon is unavailable; telemetry will remain local until it reconnects.")


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/auth/administrator/login")
def administrator_login(credentials: AdministratorLogin) -> dict:
    """Validate an administrator account stored in Neon.

    This validates credentials for the prototype. Add signed sessions before
    exposing the application beyond local development.
    """
    try:
        user = authenticate_administrator(credentials.email, credentials.password)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"authenticated": True, "user": user}


@app.get("/api/vehicles/{vehicle_id}/speed")
def get_vehicle_speed(vehicle_id: str) -> dict:
    """Read the newest speed state for one vehicle."""
    return read_vehicle_speed(vehicle_id)


@app.post("/api/vehicles/{vehicle_id}/speed")
def update_vehicle_speed(vehicle_id: str, update: VehicleSpeedUpdate) -> dict:
    """Accept a Stage-1 dashboard value or a future GPS/OBD device update."""
    if not 0 <= update.speed_kmh <= 160:
        raise HTTPException(status_code=422, detail="Speed must be between 0 and 160 km/h")
    return save_vehicle_speed(vehicle_id, update.speed_kmh, update.source)


@app.get("/api/live")
def live_metrics() -> dict:
    global last_persisted_capture, last_persist_attempt, last_persist_failure
    if not METRICS_FILE.exists():
        raise HTTPException(status_code=503, detail="Camera analyzer has not produced metrics yet")
    try:
        metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=503, detail="Camera metrics are being updated") from error

    metrics["is_live"] = time.time() - float(metrics.get("updated_at", 0)) <= 5
    # Stage 1 has no physical door/RFID hardware. Mirror the vision count as
    # explicitly simulated sensor readings until hardware events are connected.
    metrics["sensor_mode"] = "SIMULATED_FROM_VISION"
    metrics["rfid_count"] = int(metrics.get("total_passengers", 0))
    metrics["ir_count"] = int(metrics.get("total_passengers", 0))
    speed_state = read_vehicle_speed("BUS-01")
    metrics["speed_kmh"] = speed_state["speed_kmh"]
    metrics["speed_source"] = speed_state["source"]
    metrics["risk"] = calculate_camera_risk(metrics)

    # Browser polling may happen several times a second. Persist each new camera
    # snapshot at most once per second instead of creating duplicate database rows.
    captured_at = float(metrics.get("updated_at", 0))
    # If Neon is unavailable, wait five seconds before retrying so a database
    # outage cannot make the live camera UI feel stuck.
    retry_interval = 5 if last_persist_failure else 1
    can_attempt_save = time.time() - last_persist_attempt >= retry_interval
    if database_configured() and captured_at - last_persisted_capture >= 1 and can_attempt_save:
        last_persist_attempt = time.time()
        try:
            save_telemetry("BUS-01", metrics)
            last_persisted_capture = captured_at
            last_persist_failure = 0.0
        except Exception:
            last_persist_failure = time.time()
            logger.exception("Could not save telemetry to Neon; live viewing continues locally.")

    return metrics


@app.get("/api/live/frame")
def live_frame() -> Response:
    """Return a stable in-memory JPEG even while the analyzer writes the next frame."""
    try:
        frame_bytes = FRAME_FILE.read_bytes()
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail="Camera analyzer has not produced a frame yet") from error

    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
