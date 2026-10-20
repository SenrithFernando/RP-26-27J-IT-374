import { useEffect,useState } from 'react';
import { authHeaders } from '../services/session';
import { StoredRoute } from '../services/api';
import { MapLoader } from './MapLoader';
import type { RouteMapProps } from './RouteMap';
import { WorkspaceDialog } from './WorkspaceDialog';

export const sourceName = (source?: string) => ({ simulation: 'Simulation', ml_prediction: 'Experimental ML · synthetic training',
  google_live: 'Google traffic', historical_baseline: 'Historical baseline · synthetic training', mixed: 'Mixed sources',
  unavailable: 'Unavailable', geographic_zero: 'Colocated · zero travel', start: 'Vehicle start' }[source ?? ''] ?? source ?? 'Source unavailable');

export function SourceBadge({ source }: { source?: string }) {
  return <span className="inline-block rounded-full bg-slate-100 border border-slate-200 px-2 py-1 text-[11px] text-slate-700">{sourceName(source)}</span>;
}

export function AlternativeComparison({ route }: { route: StoredRoute }) {
  const value = route.alternative_comparison;
  if (!value) return null;
  return <section className="text-xs border-t border-slate-200 pt-3">
    <h3 className="font-semibold">Route comparison</h3>
    <p className="mt-2 break-all">Matrix {value.matrix_snapshot_id} · {route.provider_source?.traffic_scenario ?? 'normal'}</p>
    <p className="mt-1">{value.reference_label}. Reference: {value.reference_feasibility_status}.</p>
    {value.reference_errors.map((error) => <p key={error} className="text-amber-800 mt-1">{error}</p>)}
    <table className="w-full text-left mt-2"><thead><tr><th>Estimate</th><th>Reference</th><th>Selected</th><th>Ref − selected</th></tr></thead><tbody>
      {([['driving_seconds','Driving (s)'],['waiting_seconds','Waiting (s)'],['total_duration_seconds','Total (s)'],['distance_metres','Distance (m)']] as const).map(([field,label]) => <tr key={field} className="border-t border-slate-200"><td className="py-1">{label}</td><td>{value.reference?.[field] ?? 'Unavailable'}</td><td>{value.selected[field] ?? 'Unavailable'}</td><td>{value.reference_minus_selected[field] ?? 'Unavailable'}</td></tr>)}
    </tbody></table>
    <p className="mt-2">{value.sequence_changed ? 'Stop order differs.' : 'Stop order unchanged.'} Zero and negative differences are retained.</p>
    <p className="mt-1 text-slate-500">{value.note}</p>
  </section>;
}

export function TrafficRouteMap({ route, ...props }: RouteMapProps & { route?: StoredRoute | null }) {
  const [locationsOpen,setLocationsOpen]=useState(false);
  const landmarkTest=props.landmarkTest||route?.daily?.scenario_id==='MALABE_PP1'||!!route?.research_journey;
  const [failedImage, setFailedImage] = useState('');
  const [image,setImage]=useState<{key:string;url:string}|null>(null);
  const [requestedImage,setRequestedImage]=useState('');
  const geometry = route?.road_geometry;
  const imageId=geometry?.status==='available' && geometry.map_available?route?.route_id:'';
  useEffect(()=>{
    const controller=new AbortController();let alive=true,url='';setImage(null);
    if(imageId&&requestedImage===imageId)void fetch(`/api/routes/${encodeURIComponent(imageId)}/map-image`,{headers:authHeaders(),credentials:'omit',signal:controller.signal})
      .then(response=>{if(!response.ok)throw new Error('Map unavailable');return response.blob();})
      .then(blob=>{if(alive){url=URL.createObjectURL(blob);setImage({key:imageId,url});}})
      .catch(()=>{if(alive)setFailedImage(imageId);});
    return()=>{alive=false;controller.abort();if(url)URL.revokeObjectURL(url);};
  },[imageId,requestedImage]);
  if (route && geometry?.status === 'available' && geometry.map_available && failedImage !== route.route_id) {
    return <div className="space-y-2">{requestedImage!==route.route_id?<><button className="underline text-[#176B87]" onClick={()=>setRequestedImage(route.route_id)}>Load Google road map (up to 1 image request)</button><p className="text-xs">Explicit display request; may incur charges. Page loads and polling do not request this image.</p></>:image?.key===route.route_id?<img src={image.url} alt="Ordered road geometry on a Google Map" className="w-full rounded-xl" onError={() => setFailedImage(route.route_id)} />:<p>Loading authorized map…</p>}
      <p className="text-xs text-slate-600">Road geometry · Google Maps. {geometry.description} Saved road display, not embedded navigation. Live position and stop popups remain in the separate confirmed-locations panel below.</p>
      <button className="text-xs text-[#176B87] underline" onClick={()=>setLocationsOpen(true)}>View confirmed locations</button><WorkspaceDialog title="Confirmed locations" open={locationsOpen} onClose={()=>setLocationsOpen(false)}><MapLoader {...props} landmarkTest={landmarkTest} orderedStops={[]} /></WorkspaceDialog>
    </div>;
  }
  return <div className="space-y-2">{geometry && <p className="text-xs text-amber-800 px-3">{failedImage === route?.route_id ? 'Road map image unavailable; showing stop sequence.' : geometry.reason ?? geometry.map_reason}</p>}<MapLoader {...props} landmarkTest={landmarkTest} /></div>;
}
