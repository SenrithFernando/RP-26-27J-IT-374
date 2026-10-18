import { useEffect,useState } from 'react';
import { fetchVehicles,VehicleRecord,RouteDirection } from '../services/api';
import { useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { localPlanningDate,routePoints } from '../services/routePresentation';
import { SourceBadge,TrafficRouteMap } from './TrafficDetails';
import { localTime,PositionStatus } from './PositionStatus';

/** Authorized read-only operations; never generates plans or supplies demo values. */
export function OperationsFleet(){
  const [vehicles,setVehicles]=useState<VehicleRecord[]>([]),[vehicle,setVehicle]=useState(''),[direction,setDirection]=useState<RouteDirection>('morning');
  const [loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{const c=new AbortController();setLoading(true);setError('');setVehicles([]);
    fetchVehicles(c.signal).then(rows=>{if(!c.signal.aborted){setVehicles(rows);setVehicle(old=>rows.some(v=>v.id===old)?old:rows[0]?.id??'');}})
      .catch(e=>{if(!c.signal.aborted){setError(e.message);setVehicle('');}}).finally(()=>{if(!c.signal.aborted)setLoading(false);});return()=>c.abort();
  },[revision]);
  const selected=!loading&&!error&&vehicles.some(v=>v.id===vehicle)?vehicle:'';
  const {view,refresh}=useStoredDriverRoute(selected,direction);
  const trip=view.trip;
  const gps=useVehiclePosition(selected,trip?.state==='ACTIVE'?trip.trip_id:'');
  const shown=trip?.state==='ACTIVE'?trip.route:view.error?null:view.route;
  return <section aria-label="Authorized fleet operations" className="space-y-4">
    <h1 className="text-2xl font-bold text-[#176B87]">Live Fleet — backend observations</h1>
    <p className="text-sm text-slate-600">Authorized database records only. Planning estimates are separate from GPS observations; no automatic navigation ETA is connected.</p>
    <button onClick={()=>setRevision(n=>n+1)} className="text-[#176B87] underline">Reload authorized vehicles</button>
    {loading&&<p role="status">Loading authorized vehicles…</p>}{error&&<p role="alert">Fleet unavailable: {error}. No demo data substituted.</p>}
    {!loading&&!error&&!vehicles.length&&<p>No authorized vehicles.</p>}
    {!!vehicles.length&&<>
      <label>Vehicle<select aria-label="Fleet vehicle" value={vehicle} onChange={e=>setVehicle(e.target.value)} className="border rounded p-2 m-2">{vehicles.map(v=><option key={v.id}>{v.id}</option>)}</select></label>
      <label>Direction<select aria-label="Fleet direction" value={direction} onChange={e=>setDirection(e.target.value as RouteDirection)} className="border rounded p-2 m-2"><option value="morning">Morning</option><option value="afternoon">Afternoon</option></select></label>
      <p>Vehicle input: {vehicles.find(v=>v.id===selected)?.input_source??'Unavailable'}</p>
      <button onClick={refresh} className="text-[#176B87] underline">Refresh stored route / trip</button>
      {view.refreshing&&<p role="status">Checking server plans…</p>}{view.error&&<p role="alert">Planning unavailable: {view.error}</p>}
      {view.noRoute&&!view.error&&<p>No saved {direction} route.</p>}
      {view.route&&<div className="bg-white rounded-xl border p-3"><p>Latest planning route: {view.route.route_id} / version {view.route.version} / roster {view.route.roster_version}</p><p>Freshness: {view.error?'Unavailable':view.route.service_date<localPlanningDate()?'Historical service date':view.plan?.is_current&&view.route.is_current&&view.plan.route_id===view.route.route_id?'Current roster':'Not current'} / Service date: {view.route.service_date}</p><p>Generated: {localTime(view.route.generated_at)} (Sri Lanka)</p><SourceBadge source={view.route.provider_source?.duration_source}/></div>}
      {view.tripError?<p role="alert">Trip unavailable: {view.tripError}</p>:trip?<div className="bg-white rounded-xl border p-3"><p>Saved trip: {trip.trip_id} / {trip.state} / {trip.direction}</p><p>Pinned route: {trip.route_id} / version {trip.route_version}</p>{trip.state!=='ACTIVE'&&<p>No active trip. This is a saved {trip.state.toLowerCase()} trip.</p>}</div>:<p>{view.checkedAt?'No active trip or saved trip returned.':'Trip status: Unavailable while loading.'}</p>}
      <PositionStatus data={gps.data} error={gps.error}/>
      {shown&&<><p>{trip?.state==='ACTIVE'?'Active trip’s pinned route':'Saved planning route — not live vehicle movement'}</p><SourceBadge source={shown.provider_source?.duration_source}/><p>Planned driving {shown.driving_seconds??'Unavailable'} s / service {shown.service_seconds??'Unavailable'} s / waiting {shown.waiting_seconds??'Unavailable'} s / total {shown.total_duration_seconds??'Unavailable'} s</p>
      {(shown.provider_source?.route_fallback_reasons??shown.provider_source?.fallback_reasons??[]).map(reason=><p key={reason}>Fallback: {reason}</p>)}
      <TrafficRouteMap route={shown} points={routePoints(shown)} orderedStops={shown.stops.map(s=>({id:s.event_id,order:s.sequence,name:s.name}))} vehiclePosition={gps.error?null:gps.data?.position} height={380}/></>}
    </>}
  </section>;
}
