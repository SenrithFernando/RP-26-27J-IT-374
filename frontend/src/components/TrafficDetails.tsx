import { useState } from 'react';
import { StoredRoute } from '../services/api';
import { MapLoader } from './MapLoader';
import type { RouteMapProps } from './RouteMap';

export const sourceName = (source?: string) => ({ simulation: 'Simulated traffic', ml_prediction: 'ML prediction · synthetic training',
  google_live: 'Google traffic-aware input', historical_baseline: 'Historical baseline · synthetic training', mixed: 'Mixed sources',
  unavailable: 'Unavailable', geographic_zero: 'Colocated · zero travel', start: 'Vehicle start' }[source ?? ''] ?? source ?? 'Source unavailable');

export function SourceBadge({ source }: { source?: string }) {
  return <span className="inline-block rounded-full bg-slate-100 border border-slate-200 px-2 py-1 text-[11px] text-slate-700">{sourceName(source)}</span>;
}

export function AlternativeComparison({ route }: { route: StoredRoute }) {
  const value = route.alternative_comparison;
  if (!value) return null;
  return <details className="text-xs border-t border-slate-200 pt-3" open>
    <summary className="font-semibold cursor-pointer">Alternatives under the same snapshot</summary>
    <p className="mt-2 break-all">Matrix {value.matrix_snapshot_id} · {route.provider_source?.traffic_scenario ?? 'normal'}</p>
    <p className="mt-1">{value.reference_label}. Reference: {value.reference_feasibility_status}.</p>
    {value.reference_errors.map((error) => <p key={error} className="text-amber-800 mt-1">{error}</p>)}
    <table className="w-full text-left mt-2"><thead><tr><th>Estimate</th><th>Reference</th><th>Selected</th><th>Ref − selected</th></tr></thead><tbody>
      {([['driving_seconds','Driving (s)'],['waiting_seconds','Waiting (s)'],['total_duration_seconds','Total (s)'],['distance_metres','Distance (m)']] as const).map(([field,label]) => <tr key={field} className="border-t border-slate-200"><td className="py-1">{label}</td><td>{value.reference?.[field] ?? 'Unavailable'}</td><td>{value.selected[field] ?? 'Unavailable'}</td><td>{value.reference_minus_selected[field] ?? 'Unavailable'}</td></tr>)}
    </tbody></table>
    <p className="mt-2">{value.sequence_changed ? 'Stop order differs.' : 'Stop order unchanged.'} Zero and negative differences are retained.</p>
    <p className="mt-1 text-slate-500">{value.note}</p>
  </details>;
}

export function TrafficRouteMap({ route, ...props }: RouteMapProps & { route?: StoredRoute | null }) {
  const [failedImage, setFailedImage] = useState('');
  const geometry = route?.road_geometry;
  if (!props.vehiclePosition && route && geometry?.status === 'available' && geometry.map_available && failedImage !== route.route_id) {
    return <div className="space-y-2"><img src={`/api/routes/${encodeURIComponent(route.route_id)}/map-image`} alt="Ordered road geometry on a Google Map" className="w-full rounded-xl" onError={() => setFailedImage(route.route_id)} />
      <p className="text-xs text-slate-600">Road geometry · Google Maps. {geometry.description}</p>
      <details className="text-xs text-slate-500"><summary className="cursor-pointer">Confirmed locations and stop popups</summary><MapLoader {...props} orderedStops={[]} /></details>
    </div>;
  }
  return <div className="space-y-2">{geometry && <p className="text-xs text-amber-800 px-3">{failedImage === route?.route_id ? 'Road map image unavailable; showing stop sequence.' : geometry.reason ?? geometry.map_reason}</p>}<MapLoader {...props} /></div>;
}
