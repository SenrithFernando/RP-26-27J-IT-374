"""Administrator account helpers for SafeRide-LK."""

import base64
import hashlib
import hmac
import os

import psycopg

from backend.database import database_url


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def _hash_password(password: str, salt: bytes | None = None) -> str:
    """Create a salted password hash using Python's standard-library scrypt."""
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return "$".join(
        (
            "scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def _password_matches(password: str, encoded_hash: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = encoded_hash.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def create_administrator(full_name: str, email: str, password: str) -> dict:
    """Create or update an administrator account in Neon."""
    normalized_email = email.strip().lower()
    if not full_name.strip():
        raise ValueError("Full name is required.")
    if "@" not in normalized_email:
        raise ValueError("Enter a valid email address.")
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")

    with psycopg.connect(url, autocommit=True, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO app_users (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, 'ADMINISTRATOR')
                ON CONFLICT (email) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    password_hash = EXCLUDED.password_hash,
                    role = 'ADMINISTRATOR',
                    is_active = TRUE,
                    updated_at = NOW()
                RETURNING id, full_name, email, role, is_active
                """,
                (full_name.strip(), normalized_email, _hash_password(password)),
            )
            row = cursor.fetchone()
    return _user_record(row)


def authenticate_administrator(email: str, password: str) -> dict | None:
    """Return the public account record only when credentials are correct."""
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, full_name, email, role, is_active, password_hash
                FROM app_users
                WHERE email = %s AND role = 'ADMINISTRATOR'
                """,
                (email.strip().lower(),),
            )
            row = cursor.fetchone()
    if not row or not row[4] or not _password_matches(password, row[5]):
        return None
    return _user_record(row[:5])


def _user_record(row: tuple) -> dict:
    return {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "role": row[3],
        "is_active": row[4],
    }
