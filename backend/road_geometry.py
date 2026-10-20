"""Optional server-side Google Static Maps display; keys never enter the browser."""
from urllib.request import urlopen
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from models import RouteVersion
from persistence import session_dependency
from traffic_google import BoundedCache, config

router = APIRouter(tags=['Road geometry'])
images = BoundedCache(maximum=8, ttl=60)


def fetch_static_image(geometry, settings):
    """One bounded backend-only image request; never expose its signed/key URL."""
    params = {'size': '640x480', 'scale': '2', 'format': 'png', 'maptype': 'roadmap', 'path': 'weight:4|color:0x176b87ff|enc:' + geometry['encoded_polyline'], 'key': settings['map_key']}
    url = 'https://maps.googleapis.com/maps/api/staticmap?' + urlencode(params)
    if len(url) > 16_000: raise HTTPException(422, 'Geometry exceeds the bounded static-map request length.')
    try:
        with urlopen(url, timeout=settings['timeout']) as response:
            image = response.read(2_000_001)
            if not response.headers.get('Content-Type', '').startswith('image/') or len(image) > 2_000_000:
                raise ValueError()
    except Exception: raise HTTPException(502, 'Google road map image is unavailable. The stop-sequence map remains available.') from None
    return image


@router.get('/routes/{route_id}/map-image')
def map_image(route_id: str, session: Session = Depends(session_dependency)):
    route = session.get(RouteVersion, route_id)
    if route is None: raise HTTPException(404, 'Route not found.')
    geometry = route.result.get('road_geometry') or {}
    if geometry.get('status') != 'available': raise HTTPException(404, 'No road geometry is available for this route.')
    settings = config()
    if not settings['map_key']: raise HTTPException(503, 'Google Static Maps display is not configured; keep the stop-sequence map.')
    image = images.get(route_id)
    if image is None:
        image = fetch_static_image(geometry, settings)
        images.put(route_id, image)
    return Response(image, media_type='image/png', headers={'Cache-Control': 'no-store'})
