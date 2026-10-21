"""Neon PostgreSQL storage for SafeRide-LK telemetry."""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def database_configured() -> bool:
    return bool(database_url())


def initialize_database() -> None:
    """Create the telemetry table if it has not been created already."""
    url = database_url()
    if not url:
        return

    with psycopg.connect(url, autocommit=True, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vehicle_telemetry (
                    id BIGSERIAL PRIMARY KEY,
                    captured_at TIMESTAMPTZ NOT NULL,
                    vehicle_id TEXT NOT NULL,
                    camera_source TEXT,
                    total_passengers INTEGER NOT NULL,
                    sitting_count INTEGER NOT NULL,
                    standing_count INTEGER NOT NULL,
                    walking_count INTEGER NOT NULL,
                    pose_unclear_count INTEGER NOT NULL,
                    rfid_count INTEGER NOT NULL,
                    ir_count INTEGER NOT NULL,
                    speed_kmh DOUBLE PRECISION NOT NULL DEFAULT 0,
                    speed_source TEXT NOT NULL DEFAULT 'NOT_CONNECTED',
                    risk_score INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    payload JSONB NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS vehicle_telemetry_vehicle_time_idx
                ON vehicle_telemetry (vehicle_id, captured_at DESC)
                """
            )
            # Supports databases created before speed telemetry was added.
            cursor.execute(
                "ALTER TABLE vehicle_telemetry ADD COLUMN IF NOT EXISTS speed_kmh DOUBLE PRECISION NOT NULL DEFAULT 0"
            )
            cursor.execute(
                "ALTER TABLE vehicle_telemetry ADD COLUMN IF NOT EXISTS speed_source TEXT NOT NULL DEFAULT 'NOT_CONNECTED'"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    id BIGSERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('ADMINISTRATOR')),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS app_users_role_idx
                ON app_users (role, is_active)
                """
            )


def save_telemetry(vehicle_id: str, metrics: dict) -> None:
    """Persist one camera-derived telemetry snapshot to Neon."""
    url = database_url()
    if not url:
        return

    risk = metrics["risk"]
    values = (
        float(metrics["updated_at"]),
        vehicle_id,
        str(metrics.get("source", "")),
        int(metrics.get("total_passengers", 0)),
        int(metrics.get("sitting", 0)),
        int(metrics.get("standing", 0)),
        int(metrics.get("walking", 0)),
        int(metrics.get("pose_unclear", 0)),
        int(metrics.get("rfid_count", 0)),
        int(metrics.get("ir_count", 0)),
        float(metrics.get("speed_kmh", 0)),
        str(metrics.get("speed_source", "NOT_CONNECTED")),
        int(risk["score"]),
        str(risk["level"]),
        json.dumps(metrics),
    )

    with psycopg.connect(url, autocommit=True, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vehicle_telemetry (
                    captured_at, vehicle_id, camera_source, total_passengers,
                    sitting_count, standing_count, walking_count, pose_unclear_count,
                    rfid_count, ir_count, speed_kmh, speed_source, risk_score, risk_level, payload
                ) VALUES (
                    to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                """,
                values,
            )
