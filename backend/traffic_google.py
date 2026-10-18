"""Google Routes transport. Bounded requests/cache; no credentials in responses."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv


class ProviderFailure(Exception):
    def __init__(self, code, message): self.code, self.message = code, message; super().__init__(message)
    def as_dict(self): return {'code': self.code, 'message': self.message}


class BoundedCache:
    def __init__(self, maximum=32, ttl=60):
        self.maximum, self.ttl, self.items, self.lock = maximum, ttl, OrderedDict(), Lock()
    def get(self, key):
        with self.lock:
            now = monotonic()
            for old in list(self.items):
                if self.items[old][0] <= now: del self.items[old]
            if key not in self.items: return None
            self.items.move_to_end(key)
            return deepcopy(self.items[key][1])
    def put(self, key, value):
        if self.ttl <= 0: return
        with self.lock:
            self.items[key] = (monotonic() + self.ttl, deepcopy(value)); self.items.move_to_end(key)
            while len(self.items) > self.maximum: self.items.popitem(last=False)


def config():
    load_dotenv(Path(__file__).with_name('.env'), interpolate=False)
    return {'key': os.getenv('GOOGLE_ROUTES_API_KEY', '').strip(),
            'map_key': os.getenv('GOOGLE_STATIC_MAPS_API_KEY', '').strip(),
            'timeout': max(.1, min(10., float(os.getenv('TRAFFIC_HTTP_TIMEOUT_SECONDS', '4')))),
            'budget': max(.1, min(30., float(os.getenv('TRAFFIC_MATRIX_BUDGET_SECONDS', '12'))))}


cache = BoundedCache(maximum=32, ttl=60)


def post_google(method, body, fields, key, timeout):
    endpoints = {'computeRouteMatrix': 'distanceMatrix/v2:computeRouteMatrix',
                 'computeRoutes': 'directions/v2:computeRoutes'}
    if method not in endpoints:
        raise ProviderFailure('unsupported_method', 'Unsupported Google Routes method.')
    req = Request('https://routes.googleapis.com/' + endpoints[method], data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key, 'X-Goog-FieldMask': fields})
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000: raise ProviderFailure('oversize_response', 'Google response exceeded the bounded response size.')
            return json.loads(raw)
    except HTTPError as error:
        code = 'quota_exceeded' if error.code == 429 else 'credentials_rejected' if error.code in (401, 403) else 'http_error'
        error.close()
        raise ProviderFailure(code, f'Google Routes request failed (HTTP {error.code}).') from None
    except (TimeoutError, URLError, OSError): raise ProviderFailure('timeout_or_network', 'Google Routes timed out or the network was unavailable.') from None
    except (ValueError, TypeError): raise ProviderFailure('malformed_response', 'Google Routes returned invalid JSON.') from None


def waypoint(coordinate):
    return {'location': {'latLng': {'latitude': coordinate.latitude, 'longitude': coordinate.longitude}}}


def duration_seconds(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+)?s', value): raise ValueError('Invalid duration')
    number = float(value[:-1])
    if not math.isfinite(number) or number > 1_000_000_000: raise ValueError('Invalid duration')
    result = math.ceil(number)
    if not 0 <= result <= 1_000_000_000: raise ValueError('Invalid duration')
    return result


class GoogleRoutesAdapter:
    def __init__(self, configuration=None, transport=post_google, store=cache):
        self.configuration = config() if configuration is None else configuration
        self.transport, self.cache = transport, store

    def matrix(self, coordinates, departure_timestamp, force_failure=False):
        n = len(coordinates)
        values, failures = {}, {}
        def fail_all(failure):
            return {}, {(i, j): failure.as_dict() for i in range(n) for j in range(n) if i != j}
        if force_failure: return fail_all(ProviderFailure('forced_live_failure', 'Local demonstration forced the live adapter to fail; no external request was made.'))
        if not self.configuration['key']: return fail_all(ProviderFailure('missing_credentials', 'Google Routes API is not configured: GOOGLE_ROUTES_API_KEY is missing on the backend.'))
        if departure_timestamp <= datetime.now(timezone.utc):
            return fail_all(ProviderFailure('past_departure', 'Google driving matrices require a future departure time; the requested time was not silently changed.'))
        # Deduplicate physical locations, including repeated school actions.
        unique, indices, lookup = [], [], {}
        for c in coordinates:
            key = (c.latitude, c.longitude)
            if key not in lookup: lookup[key] = len(unique); unique.append(c)
            indices.append(lookup[key])
        if len(unique) > 40: return fail_all(ProviderFailure('matrix_limit', 'Live snapshot exceeds this prototype\'s bounded 40-unique-location limit.'))
        deadline = monotonic() + self.configuration['budget']
        found, issues = {}, {}
        for oi in range(0, len(unique), 10):
            for di in range(0, len(unique), 10):
                origins, destinations = unique[oi:oi+10], unique[di:di+10]
                body = {'origins': [{'waypoint': waypoint(c)} for c in origins],
                    'destinations': [{'waypoint': waypoint(c)} for c in destinations],
                    'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE',
                    'departureTime': departure_timestamp.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')}
                cache_key = sha256(json.dumps([sha256(self.configuration['key'].encode()).hexdigest(), body], sort_keys=True).encode()).hexdigest()
                try:
                    elements = self.cache.get(cache_key)
                    cache_miss = elements is None
                    if elements is None:
                        remaining = deadline - monotonic()
                        if remaining <= 0: raise ProviderFailure('matrix_timeout', 'Live matrix exhausted its total request budget.')
                        elements = self.transport('computeRouteMatrix', body, 'originIndex,destinationIndex,status,condition,distanceMeters,duration', self.configuration['key'], min(self.configuration['timeout'], remaining))
                        if not isinstance(elements, list): raise ProviderFailure('malformed_matrix', 'Google matrix response was not an element list.')
                        # Only cache complete successful chunks; no transient failures.
                        # Cache publication happens only after full element validation below.
                    seen = set()
                    for element in elements:
                        if not isinstance(element, dict): continue
                        a, b = element.get('originIndex', 0), element.get('destinationIndex', 0)
                        if type(a) is not int or type(b) is not int or not 0 <= a < len(origins) or not 0 <= b < len(destinations): continue
                        pair = (oi+a, di+b)
                        if pair in seen:
                            found.pop(pair, None); issues[pair] = {'code': 'duplicate_element', 'message': 'Google returned duplicate matrix indices.'}; continue
                        seen.add(pair)
                        status = element.get('status', {})
                        code = status.get('code', 0) if isinstance(status, dict) else -1
                        if element.get('condition') == 'ROUTE_NOT_FOUND':
                            issues[pair] = {'code': 'unreachable', 'message': 'Google reports no reachable road route for this directed pair; estimates cannot establish reachability.'}
                        elif code:
                            issues[pair] = {'code': 'quota_exceeded' if code == 8 else 'element_error', 'message': 'Google matrix element failed (quota).' if code == 8 else 'Google matrix element failed.'}
                        elif element.get('condition') != 'ROUTE_EXISTS':
                            issues[pair] = {'code': 'unknown_condition', 'message': 'Google matrix element has no confirmed route condition.'}
                        else:
                            try:
                                duration = duration_seconds(element['duration'])
                                distance = element['distanceMeters']
                                if type(distance) is not int or not 0 <= distance <= 1_000_000_000: raise ValueError()
                                if pair[0] != pair[1] and duration <= 0: raise ValueError()
                                found[pair] = (duration, distance)
                            except (KeyError, TypeError, ValueError): issues[pair] = {'code': 'invalid_element', 'message': 'Google matrix element has invalid duration or distance.'}
                    for a in range(len(origins)):
                        for b in range(len(destinations)):
                            pair = (oi+a, di+b)
                            if pair not in found and pair not in issues: issues[pair] = {'code': 'partial_matrix', 'message': 'Google matrix omitted a requested directed pair.'}
                    if cache_miss and all((oi+a,di+b) in found and (oi+a,di+b) not in issues for a in range(len(origins)) for b in range(len(destinations))):
                        self.cache.put(cache_key, elements)
                except ProviderFailure as failure:
                    for a in range(len(origins)):
                        for b in range(len(destinations)): issues[oi+a, di+b] = failure.as_dict()
        for i in range(n):
            for j in range(n):
                pair = (indices[i], indices[j])
                if pair in found and pair not in issues: values[i,j] = found[pair]
                elif i != j: failures[i,j] = issues.get(pair, {'code': 'partial_matrix', 'message': 'Live matrix pair unavailable.'})
        return values, failures

    def geometry(self, stops, departure_timestamp, force_failure=False):
        if force_failure: return {'status': 'unavailable', 'reason': 'Forced live failure also disables live road geometry.'}
        if not self.configuration['key']: return {'status': 'unavailable', 'reason': 'Google Routes API is not configured.'}
        if len(stops) > 27: return {'status': 'unavailable', 'reason': 'Ordered route exceeds the 25-intermediate-waypoint geometry limit.'}
        if departure_timestamp <= datetime.now(timezone.utc): return {'status': 'unavailable', 'reason': 'Requested departure is in the past.'}
        def point(s): return {'location': {'latLng': {'latitude': s['latitude'], 'longitude': s['longitude']}}}
        body = {'origin': point(stops[0]), 'destination': point(stops[-1]),
            'intermediates': [point(s) for s in stops[1:-1]], 'travelMode': 'DRIVE',
            'routingPreference': 'TRAFFIC_AWARE', 'departureTime': departure_timestamp.astimezone(timezone.utc).isoformat(),
            'polylineEncoding': 'ENCODED_POLYLINE', 'optimizeWaypointOrder': False}
        try:
            result = self.transport('computeRoutes', body, 'routes.polyline.encodedPolyline', self.configuration['key'], self.configuration['timeout'])
            encoded = result['routes'][0]['polyline']['encodedPolyline']
            if not isinstance(encoded, str) or not 1 <= len(encoded) <= 12_000: raise ValueError()
            return {'status': 'available', 'provider': 'google_routes', 'encoded_polyline': encoded,
                'map_available': bool(self.configuration.get('map_key')),
                'map_reason': None if self.configuration.get('map_key') else 'Backend GOOGLE_STATIC_MAPS_API_KEY is not configured; Google road geometry cannot be displayed on the existing OpenStreetMap basemap.',
                'description': 'Ordered road geometry requested separately; it does not replace snapshot duration estimates.'}
        except ProviderFailure as failure: return {'status': 'unavailable', 'reason': failure.message, 'failure_code': failure.code}
        except (KeyError, IndexError, TypeError, ValueError): return {'status': 'unavailable', 'reason': 'Google returned no usable ordered road geometry.'}
