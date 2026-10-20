"""Backend-only geocoding adapters. No fallback coordinates and no key logging."""
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/routing", tags=["Locations"])


class GeocodeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    address: str = Field(min_length=3, max_length=500)


def google_geocode(address: str, key: str):
    query = urlencode({"address": address, "key": key, "region": "lk"})
    request = Request("https://maps.googleapis.com/maps/api/geocode/json?" + query,
                      headers={"User-Agent": "SafeRide-LK-research/1.0"})
    try:
        with urlopen(request, timeout=8) as response:
            body = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(502, "Geocoding provider unavailable. Enter coordinates or place the pin manually.") from None
    if not isinstance(body, dict):
        raise HTTPException(502, "Geocoding provider returned an invalid response. Place the pin manually.")
    status = body.get("status")
    if status == "ZERO_RESULTS":
        raise HTTPException(404, "No address match found. Place the pin manually.")
    if status != "OK" or not body.get("results"):
        # Provider error_message may contain configuration details; never forward it.
        raise HTTPException(502, "Geocoding provider rejected the request. Check backend configuration or place the pin manually.")
    try:
        match = body["results"][0]
        latitude = float(match["geometry"]["location"]["lat"])
        longitude = float(match["geometry"]["location"]["lng"])
        if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Invalid coordinate")
        return {"latitude": latitude, "longitude": longitude,
                "formatted_address": match["formatted_address"], "provider": "google",
                "partial_match": bool(match.get("partial_match", False)),
                "candidate_count": len(body['results']),
                "ambiguous": bool(match.get('partial_match')) or len(body['results']) > 1,
                "location_type": match.get('geometry',{}).get('location_type','unknown'),
                "location_confirmed": False}
    except (KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(502, "Geocoding provider returned an invalid location. Place the pin manually.") from None


@router.post("/geocode")
def geocode(payload: GeocodeRequest):
    load_dotenv(Path(__file__).with_name(".env"), interpolate=False)
    key = os.getenv("GOOGLE_GEOCODING_API_KEY", "")
    provider = os.getenv("GEOCODING_PROVIDER", "auto").strip().lower()
    if provider == "auto":
        provider = "google" if key else "manual"
    if provider == "manual":
        raise HTTPException(503, "Automatic geocoding is not configured. Enter coordinates or click the map, then confirm the pin.")
    if provider != "google":
        raise HTTPException(503, "Configured geocoding provider is unsupported. Place the pin manually.")
    if not key:
        raise HTTPException(503, "Google geocoding key is missing on the backend. Place the pin manually.")
    return google_geocode(payload.address, key)
