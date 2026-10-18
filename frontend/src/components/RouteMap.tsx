import { useEffect, useMemo, useState } from 'react';
import { divIcon, latLngBounds, LatLngTuple, Marker as LeafletMarker } from 'leaflet';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPoint, VehiclePosition } from '../services/api';

type OrderedStop = { id: string; order: number; name: string };
export interface RouteMapProps {
  landmarkTest?: boolean;
  points: MapPoint[];
  vehiclePosition?: VehiclePosition | null;
  orderedStops?: OrderedStop[];
  missingLocations?: string[];
  loading?: boolean;
  error?: string | null;
  height?: number;
  editable?: boolean;
  onPositionChange?: (latitude: number, longitude: number) => void;
}
const colors = { home: '#176B87', school: '#7c3aed', vehicle_start: '#15803d', vehicle_end: '#c2410c' };
const names = { home: 'Student home', school: 'School', vehicle_start: 'Vehicle start', vehicle_end: 'Vehicle end' };
const methods = { manual: 'Manually entered / pinned', google: 'Google geocoding result', manual_correction: 'Manually corrected after geocoding' };

function MapBehavior({ positions, onPositionChange }: { positions: LatLngTuple[]; onPositionChange?: RouteMapProps['onPositionChange'] }) {
  const map = useMap();
  useMapEvents({ click(event) { onPositionChange?.(event.latlng.lat, event.latlng.lng); } });
  const coordinateKey = JSON.stringify(positions);
  useEffect(() => {
    const fixed: LatLngTuple[] = JSON.parse(coordinateKey);
    let needsInitialBounds = true;
    const resize = () => {
      const container = map.getContainer();
      if (!container.clientWidth || !container.clientHeight) return;
      map.invalidateSize();
      if (needsInitialBounds && fixed.length) {
        map.fitBounds(latLngBounds(fixed), { padding: [35, 35], maxZoom: 15, animate: false });
        needsInitialBounds = false;
      }
    };
    const observer = new ResizeObserver(resize);
    observer.observe(map.getContainer()); resize();
    return () => observer.disconnect();
  }, [map, coordinateKey]);
  return null;
}

export function RouteMap({ points, orderedStops = [], missingLocations = [], loading = false, error,
  vehiclePosition, height = 460, editable = false, onPositionChange, landmarkTest = false }: RouteMapProps) {
  const pointLabel=(kind:MapPoint['kind'])=>landmarkTest&&kind==='home'?'Participant landmark — not a student home':names[kind];
  const [tilesLoading, setTilesLoading] = useState(true);
  const [tileError, setTileError] = useState(false);
  const [tileAttempt, setTileAttempt] = useState(0);
  const validPoints = useMemo(() => points.filter((point) => Number.isFinite(point.latitude) && Number.isFinite(point.longitude) && Math.abs(point.latitude) <= 90 && Math.abs(point.longitude) <= 180), [points]);
  const positions = useMemo<LatLngTuple[]>(() => validPoints.map((point) => [point.latitude, point.longitude]), [validPoints]);
  const groups = useMemo(() => {
    const grouped = new Map<string, MapPoint[]>();
    for (const point of validPoints) {
      const key = `${point.latitude}:${point.longitude}`;
      grouped.set(key, [...(grouped.get(key) ?? []), point]);
    }
    return [...grouped.values()];
  }, [validPoints]);
  const ordered = orderedStops.map((stop) => ({ stop, point: validPoints.find((point) => point.location_id === stop.id) }));
  const missingStops = ordered.filter(({ point }) => !point).map(({ stop }) => stop.name);
  const line: LatLngTuple[] = !missingStops.length ? ordered.flatMap(({ point }) => point ? [[point.latitude, point.longitude] as LatLngTuple] : []) : [];

  return <div className="space-y-2">
    {loading && <p role="status" className="text-sm text-slate-500 px-3">Loading confirmed locations...</p>}
    {error && <p role="alert" className="p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</p>}
    {missingLocations.length > 0 && <p className="px-3 text-xs text-amber-800">Unconfirmed or missing locations: {missingLocations.join(', ')}. These are not plotted.</p>}
    {missingStops.length > 0 && <p className="px-3 text-xs text-amber-800">Sequence line unavailable until every ordered stop has a confirmed location: {missingStops.join(', ')}.</p>}
    {!loading && !error && validPoints.length === 0 && <p className="px-3 text-sm text-slate-500">{editable ? 'No selected location. Click the map or enter coordinates, then confirm.' : 'No confirmed locations to display.'}</p>}
    <div className="relative isolate z-0 rounded-xl overflow-hidden border border-slate-200" style={{ height }}>
      <MapContainer center={[7.8731, 80.7718]} zoom={7} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }} aria-label={editable ? 'Location preview map' : 'Confirmed routing locations map'}>
        <TileLayer key={tileAttempt}
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution={'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}
          eventHandlers={{ loading: () => setTilesLoading(true), load: () => setTilesLoading(false), tileerror: () => { setTileError(true); setTilesLoading(false); } }} />
        <MapBehavior positions={positions} onPositionChange={editable ? onPositionChange : undefined} />
        {vehiclePosition && <Marker position={[vehiclePosition.latitude, vehiclePosition.longitude]}
          title={`Vehicle position: ${vehiclePosition.vehicle_id}`}
          icon={divIcon({ className: 'saferide-position-marker', html: '<span style="display:block;width:24px;height:24px;border:3px solid white;border-radius:50%;background:#dc2626;box-shadow:0 0 0 2px #dc2626"></span>', iconSize: [24,24], iconAnchor: [12,12] })}>
          <Popup><strong>{vehiclePosition.vehicle_id}</strong><br />{vehiclePosition.source === 'simulation' ? 'Simulation: synthetic movement, not a driven road trace' : 'Actual device input (reported, not independently verified)'}<br />
            {vehiclePosition.latitude}, {vehiclePosition.longitude}<br />Recorded: {new Date(vehiclePosition.recorded_at).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' })}<br />
            Speed: {vehiclePosition.speed_mps == null ? 'Unknown' : `${vehiclePosition.speed_mps} m/s`}<br />Trip: {vehiclePosition.trip_id ?? 'Not associated'}</Popup>
        </Marker>}
        {groups.map((group) => {
          const point = group[0];
          const order = orderedStops.find((stop) => stop.id === point.location_id)?.order;
          const firstBadge = order ?? (point.kind === 'home' ? 'H' : point.kind === 'school' ? 'S' : point.kind === 'vehicle_start' ? 'A' : 'B');
          const badge = group.length > 1 ? `${firstBadge}+${group.length - 1}` : firstBadge;
          const icon = divIcon({ className: 'saferide-map-marker', html: `<span style="display:flex;align-items:center;justify-content:center;width:32px;height:32px;border:2px solid white;border-radius:50%;background:${colors[point.kind]};color:white;font-size:11px;font-weight:700;box-shadow:0 1px 5px #0005">${badge}</span>`, iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -16] });
          return <Marker key={point.id} position={[point.latitude, point.longitude]} icon={icon}
            title={`${pointLabel(point.kind)}: ${point.name}${group.length > 1 ? ` (${group.length} colocated actions)` : ''}`} draggable={editable}
            eventHandlers={editable ? { dragend(event) { const position = (event.target as LeafletMarker).getLatLng(); onPositionChange?.(position.lat, position.lng); } } : undefined}>
            <Popup maxHeight={300}>{group.map((entry) => {
              const number = orderedStops.find((stop) => stop.id === entry.location_id)?.order;
              return <div key={entry.id} className="py-1">
                <strong>{entry.name}</strong><br />{pointLabel(entry.kind)}{number ? ` | Stop ${number}` : ''}<br />{entry.address}<br />
                {entry.latitude.toFixed(6)}, {entry.longitude.toFixed(6)}<br />
                {entry.action && <>{entry.action} | Student: {entry.student_id ?? 'None'}<br /></>}
                {entry.eta && <>ETA: {new Date(entry.eta).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' })} | Onboard after: {entry.load_after}<br /></>}
                {methods[entry.location_method]}<br />Record input: {entry.input_source.replace('_', ' ')}<br />
                Location input: {(entry.location_input_source ?? (entry.location_method === 'google' ? 'live_provider' : entry.input_source)).replace('_', ' ')}
                {!editable && !number && entry.kind === 'home' && <><br />Not part of the current optimized sequence.</>}
              </div>;
            })}</Popup>
          </Marker>;
        })}
        {line.length > 1 && <Polyline positions={line} pathOptions={{ color: '#176B87', weight: 4, dashArray: '8 8' }}><Popup>Stop sequence — not a road route</Popup></Polyline>}
      </MapContainer>
      {tilesLoading && !tileError && <span role="status" className="absolute top-2 right-2 z-[1000] bg-white/95 rounded px-2 py-1 text-xs text-slate-600">Loading map tiles...</span>}
    </div>
    {tileError && <div role="alert" className="text-xs text-amber-800 px-3">Some map tiles could not load. Coordinates and markers remain available. <button type="button" className="underline" onClick={() => { setTileError(false); setTilesLoading(true); setTileAttempt((value) => value + 1); }}>Retry tiles</button></div>}
    {!editable && <p className="text-xs font-medium text-slate-600 px-3">Stop sequence — not a road route</p>}
    <p className="text-[11px] text-slate-500 px-3">OpenStreetMap supplies the basemap tiles, not routing or traffic data.{editable ? ' Drag the pin to correct the position.' : ' Marker numbers follow the backend stop order; other markers are locations only.'}</p>
  </div>;
}
