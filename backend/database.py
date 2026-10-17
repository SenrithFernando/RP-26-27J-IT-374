from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def database_url():
    load_dotenv(Path(__file__).with_name(".env"), interpolate=False)
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError("Set DB_PASSWORD locally in backend/.env before using persistence.")
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "saferide_app"),
        password=password,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "saferide_routing"),
    )


@lru_cache
def get_engine():
    return create_engine(database_url(), pool_pre_ping=True, hide_parameters=True,
                         connect_args={"connect_timeout": 5})


def get_session():
    with Session(get_engine()) as session:
        yield session
