import { useEffect, useState } from 'react';
import { Bell, Bus, Navigation, RefreshCw } from 'lucide-react';
import { fetchCurrentTrip, fetchPersistentInbox, fetchVehicles, PersistentInbox, TripRecord, VehicleRecord } from '../services/api';
import { useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { routePoints } from '../services/routePresentation';
import { vehicleLabel } from '../services/uiFormat';
import { SourceBadge, TrafficRouteMap } from '../components/TrafficDetails';

/** Dedicated read-only overview, backed exclusively by authorized GET responses. */
export function OperationsOverview({onPlan,onAlerts}:{onPlan:()=>void;onAlerts:()=>void}) {
  const [vehicles,setVehicles]=useState<VehicleRecord[]|null>(null),[trips,setTrips]=useState<TripRecord[]|null>(null),[inbox,setInbox]=useState<PersistentInbox|null>(null);
  const [vehicle,setVehicle]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
  useEffect(()=>{
    const c=new AbortController();setLoading(true);setError('');setTrips(null);setInbox(null);setVehicles(null);
    void fetchVehicles(c.signal).then(async rows=>{
      if(c.signal.aborted)return;if(!Array.isArray(rows))throw new Error('Vehicle directory unavailable. Refresh to try again.');setVehicles(rows);setVehicle(old=>rows.some(v=>v.id===old)?old:rows[0]?.id??'');
      const results=await Promise.all(rows.flatMap(v=>(['morning','afternoon'] as const).map(d=>fetchCurrentTrip(v.id,d,c.signal))));
      if(results.some(r=>!r||!('trip' in r)))throw new Error('Trip status unavailable. Refresh to try again.');
      if(!c.signal.aborted)setTrips([...new Map(results.flatMap(r=>r.trip?[r.trip]:[]).map(t=>[t.trip_id,t])).values()]);
    }).catch(e=>{if(!c.signal.aborted)setError(e.message);}).finally(()=>{if(!c.signal.aborted)setLoading(false);});
    void fetchPersistentInbox('admin','',c.signal).then(value=>{if(!value||!Array.isArray(value.notifications)||!Number.isFinite(value.unread_count))throw new Error('Alerts unavailable. Refresh to try again.');if(!c.signal.aborted)setInbox(value);}).catch(e=>{if(!c.signal.aborted)setError(e.message);});
    return()=>c.abort();
  },[revision]);
  const active=trips?.find(t=>t.vehicle_id===vehicle&&t.state==='ACTIVE');
  const {view}=useStoredDriverRoute(vehicle,'morning');
  const gps=useVehiclePosition(active?vehicle:'',active?.trip_id??'');
  const route=active?.route??(!view.error?view.route:null);
  const p=gps.data?.position;
  const age=p?(Date.now()-Date.parse(p.recorded_at))/1000:Infinity;
  const position=active&&!gps.error&&p?.trip_id===active.trip_id&&p.vehicle_id===vehicle&&gps.data?.status==='fresh'&&age>=0&&age<=gps.data.stale_after_seconds&&p.accuracy_quality!=='poor'?p:null;
  return <section aria-label="Routing overview" className="space-y-6">
    <div className="flex justify-between gap-3 items-center"><p className="text-sm text-slate-500">Today's transport planning and current journeys</p><button onClick={()=>setRevision(n=>n+1)} disabled={loading} aria-label="Refresh overview" className="p-2 text-[#176B87]"><RefreshCw size={18}/></button></div>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-6">{[{label:'Authorized vehicles',value:vehicles?.length,icon:Bus,tone:'bg-blue-50 text-blue-600'},{label:'Active trips',value:trips?.filter(t=>t.state==='ACTIVE').length,icon:Navigation,tone:'bg-teal-50 text-teal-600'},{label:'Unread routing alerts',value:inbox?.unread_count,icon:Bell,tone:'bg-amber-50 text-amber-600'}].map(({label,value,icon:Icon,tone})=><div key={label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex items-center justify-between"><div><p className="text-sm text-slate-500">{label}</p><p className="text-2xl font-bold mt-2 text-slate-900">{value??'Unavailable'}</p></div><span className={`p-3 rounded-xl ${tone}`}><Icon size={24}/></span></div>)}</div>
    {loading&&<p role="status" className="text-sm text-slate-500">Loading overview…</p>}{error&&<p role="alert" className="bg-amber-50 text-amber-900 p-3 rounded-lg text-sm">Overview incomplete: {error}</p>}
    <div className="grid lg:grid-cols-3 gap-6 items-start">
      <section aria-label="Overview fleet map" className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden"><div className="px-5 py-4 border-b flex flex-wrap justify-between items-center gap-3"><h2 className="font-semibold text-slate-900">Fleet map</h2><select aria-label="Overview vehicle" value={vehicle} onChange={e=>setVehicle(e.target.value)} className="border rounded-lg p-2 text-sm max-w-full">{!vehicles?.length&&<option value="">No vehicle available</option>}{vehicles?.map(v=><option key={v.id} value={v.id}>{vehicleLabel(v.id)}</option>)}</select></div>
        {route?<div className="p-3"><TrafficRouteMap route={route} points={routePoints(route)} orderedStops={route.stops.map(s=>({id:s.event_id,order:s.sequence,name:s.name}))} vehiclePosition={position} height={390}/><div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 mt-3"><SourceBadge source={route.provider_source?.duration_source}/><span>Version {route.version} / {route.service_date}</span></div></div>:<div className="h-[330px] flex items-center justify-center text-slate-500 text-sm p-6">{view.error??'No saved route available.'}</div>}
        <p className="border-t px-5 py-3 text-xs text-slate-500">{active?position?'Current active-trip position.':'Active trip: GPS unavailable or stale.':'Saved plan preview. No active-trip position available.'}</p>
      </section>
      <section className="bg-white rounded-xl shadow-sm border border-slate-200"><div className="px-5 py-4 border-b flex justify-between items-center"><h2 className="font-semibold">Recent routing alerts</h2><Bell size={18} className="text-slate-400"/></div><div className="p-5 space-y-4">{!inbox?<p className="text-sm text-slate-500">Alerts unavailable.</p>:!inbox.notifications.length?<p className="text-sm text-slate-500">No stored routing alerts.</p>:inbox.notifications.slice(0,4).map(n=><article key={n.id} className="border-l-2 border-amber-400 pl-3"><p className="text-sm font-medium text-slate-800">{n.message}</p><p className="text-xs text-slate-500 mt-1">{new Date(n.occurred_at).toLocaleString('en-GB',{timeZone:'Asia/Colombo'})}</p><p className="text-xs text-slate-500">In-app event created / external delivery {n.parent_channel_status??'unavailable'}</p></article>)}<button onClick={onAlerts} className="text-sm font-semibold text-[#176B87]">View notifications</button></div></section>
    </div>
    <button onClick={onPlan} className="rounded-lg bg-[#176B87] px-5 py-3 text-white font-semibold text-sm">Open Daily Plan</button>
  </section>;
}
