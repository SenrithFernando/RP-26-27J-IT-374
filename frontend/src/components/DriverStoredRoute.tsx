import { useEffect, useState } from 'react';
import { PositionStatus } from './PositionStatus';
import { PlannedRouteDurations } from './PlannedRouteDurations';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { DriverTrip } from './DriverTrip';
import { TrackingAuthorization } from './TrackingAuthorization';
import { ArrowLeft, Loader2, RefreshCw } from 'lucide-react';
import { fetchVehicles, InputSource, RouteDirection, StoredRouteStop, VehicleRecord } from '../services/api';
import { localPlanningDate, routePoints } from '../services/routePresentation';
import { useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { SourceBadge, TrafficRouteMap } from './TrafficDetails';

const time = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) : 'Unknown';
const inputs: Record<InputSource, string> = { simulated: 'Simulated input', live_provider: 'Live provider input', measured: 'Measured observation' };

export function DriverStoredRoute({ vehicleId, direction, onVehicleChange, onDirectionChange, onBack,initialPurpose='school',initialServiceDate }: {
  initialPurpose?:'school'|'research';initialServiceDate?:string;
  vehicleId: string; direction: RouteDirection; onVehicleChange: (id: string) => void;
  onDirectionChange: (direction: RouteDirection) => void; onBack: () => void;
}) {
  const [purpose,setPurpose]=useState<'school'|'research'>(initialPurpose);
  const [serviceDate,setServiceDate]=useState(initialServiceDate??localPlanningDate());
  const [vehicles, setVehicles] = useState<VehicleRecord[]>([]);
  const [directoryError, setDirectoryError] = useState('');
  const [directoryLoading, setDirectoryLoading] = useState(true);
  const [directoryRevision, setDirectoryRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setDirectoryLoading(true); setDirectoryError('');
    fetchVehicles(controller.signal).then((rows) => { if (active) setVehicles(rows); })
      .catch((error) => { if (active) { setVehicles([]); setDirectoryError(error instanceof Error ? error.message : 'Vehicles unavailable.'); } })
      .finally(() => { if (active) setDirectoryLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [directoryRevision]);
  const selected = vehicles.some((vehicle) => vehicle.id === vehicleId);
  const { view, visible, refresh } = useStoredDriverRoute(selected && !directoryError ? vehicleId : '', direction, serviceDate, purpose);
  const { route, plan } = view;
  const gps = useVehiclePosition(selected && !directoryError ? vehicleId : '', view.trip?.trip_id ?? '');
  const livePosition = !gps.error && !view.tripError && view.trip?.state==='ACTIVE' && gps.data?.position?.trip_id===view.trip.trip_id && gps.data.position.vehicle_id===vehicleId ? gps.data.position : null;
  const liveGps = gps.data ? {...gps.data,position:livePosition,status:livePosition?gps.data.status:'unknown' as const,age_seconds:livePosition?gps.data.age_seconds:null} : null;
  const pastDate = !!route && route.service_date < localPlanningDate();
  const current = !view.error && route?.feasibility_status === 'feasible' && route.is_current && plan?.is_current &&
    plan.route_id === route.route_id && plan.roster_version === route.roster_version && !pastDate && route.execution_status === 'pre_trip';
  const pending = selected && !view.checkedAt && !view.error;
  const issues = [...new Set([...(route?.errors ?? []), ...(route?.planning_errors ?? []), ...(plan?.errors ?? [])])];
  const matchingTrip = !view.tripError && view.trip?.route.direction === direction && view.trip.route.service_date === serviceDate ? view.trip : null;
  const durationRoute = !view.error ? (matchingTrip?.state === 'ACTIVE' ? matchingTrip.route : route ?? matchingTrip?.route ?? null) : null;
  const durationContext = durationRoute && matchingTrip && durationRoute.route_id === matchingTrip.route_id ? `Fixed ${matchingTrip.state.toLowerCase()} trip plan` : current ? 'Published pre-trip plan' : 'Saved historical / non-current plan';

  return <section aria-label="Database driver route" className="absolute inset-0 min-h-0 z-[80] bg-slate-50 flex flex-col animate-in slide-in-from-right duration-200">
    <header className="shrink-0 bg-[#176B87] text-white px-4 py-3 rounded-b-2xl shadow-md">
      <div className="flex items-center gap-3 mb-3">
        <button onClick={onBack} aria-label="Back to driver dashboard" className="p-2 -ml-2 rounded-full hover:bg-white/15"><ArrowLeft size={21} /></button>
        <div className="flex-1 min-w-0"><h2 className="text-lg font-bold">Stored route plan</h2><p className="text-xs text-blue-100 break-all">{vehicleId || 'Select a database vehicle'} · {purpose==='research'?'Adult research ? A ? B ? C ? A':direction === 'morning' ? 'Morning pickup' : 'Afternoon drop-off'}</p></div>
        <span className="shrink-0 px-2 py-1 bg-white/15 rounded-full text-xs">Authenticated access</span>
      </div>
      <p className="text-xs text-blue-100">Saved instructions / authorized vehicle access</p>
    </header>
    <main className="flex-1 min-h-0 overflow-y-auto p-4 md:p-5 space-y-4">
      <details open={!vehicleId} className="bg-white border rounded-xl p-3 space-y-3"><summary className="cursor-pointer font-semibold text-sm text-[#176B87]">Change vehicle, date or direction</summary><label className="block text-sm font-medium text-slate-700">Authorized vehicle<select aria-label="Driver test vehicle" value={vehicleId} disabled={directoryLoading || !!directoryError} onChange={(event) => onVehicleChange(event.target.value)} className="w-full mt-1 p-2 border border-slate-200 rounded-lg bg-white">
        <option value="">Select a database vehicle</option>
        {vehicleId && !selected && <option value={vehicleId}>{vehicleId} — unavailable in directory</option>}
        {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.id} · capacity {vehicle.capacity}</option>)}
      </select></label>
      <details className="text-xs"><summary className="cursor-pointer">Change route workspace</summary><label className="block text-sm">Route workspace<select aria-label="Route workspace" className="block border rounded p-2 w-full" value={purpose} onChange={e=>{setPurpose(e.target.value as 'school'|'research');if(e.target.value==='research')onDirectionChange('afternoon');}}><option value="school">Published school plans</option><option value="research">Isolated adult research route</option></select></label></details>
      <label className="block text-sm">Service date (Asia/Colombo)<input aria-label="Driver service date" type="date" value={serviceDate} onChange={e=>setServiceDate(e.target.value)} className="block border rounded-lg p-2 w-full"/></label>

      <div style={purpose==='research'?{display:'none'}:undefined} role="group" aria-label="Driver route direction" className="flex bg-white p-1 border border-slate-200 rounded-lg">
        {(['morning','afternoon'] as const).map((value) => <button key={value} aria-pressed={direction === value} onClick={() => onDirectionChange(value)} className={`flex-1 py-2 rounded-md text-sm font-medium ${direction === value ? 'bg-[#176B87] text-white' : 'text-slate-600 hover:bg-slate-50'}`}>{value === 'morning' ? 'Morning Pickup' : 'Afternoon Drop-off'}</button>)}
      </div>
      </details>
      <div className="flex gap-3 items-center text-xs"><button onClick={refresh} disabled={!selected || !visible} className="text-[#176B87] font-semibold flex gap-1 items-center disabled:opacity-50"><RefreshCw size={14} />Refresh route</button>
        <button onClick={() => setDirectoryRevision((value) => value+1)} className="text-[#176B87] underline">Reload vehicles</button>
        {view.refreshing && <Loader2 aria-label="Refreshing route" size={15} className="animate-spin" />}
      </div>

      {directoryLoading && <p role="status" className="text-sm text-slate-500">Loading database vehicles...</p>}
      {directoryError && <p role="alert" className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">Vehicles unavailable: {directoryError}</p>}
      {!directoryLoading && !directoryError && !vehicles.length && <p className="text-sm text-slate-500">No registered database vehicles.</p>}
      {!vehicleId && <p className="text-sm text-slate-500">Select a test vehicle to load its stored route. No mock route is substituted.</p>}
      {pending && <p role="status" className="text-sm text-slate-500">Loading stored {direction} plan...</p>}
      {view.error && <p role="alert" className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{view.error} No cached itinerary is treated as current.</p>}
      {!pending && !view.error && view.noRoute && <p role="status" className="p-3 bg-blue-50 text-slate-700 rounded-lg text-sm">{purpose==='research'?`No reviewed adult research route for ${vehicleId} on ${serviceDate}. Confirm pins/mode/people in Admin ? Adult research first.`:`No current published ${direction} route for ${vehicleId} on ${serviceDate}. Publication: ${view.publicationStatus??'Unavailable'}. Review and publish in Admin; this view never generates routes.`}</p>}
      <div className="bg-white border rounded-2xl p-4 text-sm shadow-sm" role="region" aria-label="Selected route summary"><p className="font-bold text-[#176B87]">{vehicleId||'Select a vehicle'} / {serviceDate} / {purpose==='research'?'Adult research':direction}</p><div className="flex flex-wrap gap-2 mt-2"><span className="rounded-full bg-blue-50 px-3 py-1">{route?`Plan v${route.version}`:'No saved plan'} / {view.publicationStatus??'Unknown'}</span><span className="rounded-full bg-slate-100 px-3 py-1">{view.trip?`${view.trip.state} / fixed v${view.trip.route_version}`:'No trip'}</span></div><div className="mt-2"><SourceBadge source={(view.trip?.state==='ACTIVE'?view.trip.route:route)?.provider_source?.duration_source}/></div>{view.trip?.state==='ACTIVE'&&<p className="font-semibold mt-2">Next stop: {gps.arrival?.trip_id===view.trip.trip_id&&gps.arrival.route_id===view.trip.route_id?gps.arrival.current_stop?.name??'Unknown - refresh arrival status':'Unknown - waiting for current-trip arrival status'}</p>}<p className="text-xs mt-2 text-slate-500">Planned ETAs are estimates. Live GPS is shown only for this vehicle's active trip.</p></div>


      {selected && <DriverTrip operational={gps.operational} operationalError={gps.operationalError} simulationVehicle={vehicles.find(vehicle=>vehicle.id===vehicleId)?.input_source==='simulated'} pickups={gps.pickups} pickupError={gps.pickupError} arrival={gps.arrival} arrivalError={gps.arrivalError} vehiclePosition={livePosition} key={`${vehicleId}:${direction}`} trip={view.trip} error={view.tripError} route={route} mapPanel={(view.trip?.state==='ACTIVE'||current)&&<TrafficRouteMap vehiclePosition={livePosition} route={view.trip?.state==='ACTIVE'?view.trip.route:route!} points={routePoints(view.trip?.state==='ACTIVE'?view.trip.route:route!)} orderedStops={(view.trip?.state==='ACTIVE'?view.trip.route:route!).stops.map(stop=>({id:stop.event_id,order:stop.sequence,name:stop.name}))} height={220}/>} trackingPanel={selected?<><PositionStatus data={liveGps} error={gps.error}/><TrackingAuthorization key={vehicleId} vehicleId={vehicleId} trip={view.trip} synthetic={vehicles.find(v=>v.id===vehicleId)?.input_source==='simulated'}/></>:null} canCreate={!!current && !view.refreshing} refresh={refresh} DriverAction={DriverAction} />}
      <PlannedRouteDurations route={durationRoute} context={durationContext} />
      {!pending && !view.error && route && !current && <div role="alert" className="p-3 bg-amber-50 text-amber-900 rounded-lg text-sm">
        <p>No current feasible pre-trip itinerary to display.</p>
        {pastDate && <p>The stored service date is in the past, even if the backend roster flag remains current.</p>}
        {plan && plan.route_id !== route.route_id && <p>Stored route and planning state do not match; refresh to obtain a consistent version.</p>}
        {issues.map((issue) => <p key={issue} className="mt-1">{issue}</p>)}
      </div>}
      {current && route && <>
        <div><p className="text-xs uppercase tracking-wide font-semibold text-slate-400">{route.research_journey?'Ordered adult research stop occurrences':'Ordered pickup / delivery actions'}</p><h3 className="font-bold text-slate-800">{route.stops.length} stored actions</h3><p className="text-xs text-slate-500">Planned ETA, Asia/Colombo; no live GPS or completion progress implied.</p></div>
        <ol aria-label="Driver stored actions">{route.stops.map((stop) => <DriverAction key={stop.event_id} stop={stop} />)}</ol>
      </>}
    </main>
    <footer className="shrink-0 p-3 bg-white border-t border-slate-200 text-xs text-slate-500"><details><summary className="cursor-pointer">Prototype and tracking limitations</summary>Persistent manual pickup lifecycle; delivery confirmation is unavailable. External next-stop navigation is available on active trips; embedded turn-by-turn is not implemented. GPS samples are source-labelled. Cabin, RFID, camera and emergency features: Not connected in Authenticated operations.</details></footer>
  </section>;
}

function DriverAction({ stop }: { stop: StoredRouteStop }) {
  return <li data-event-id={stop.event_id} className="flex gap-3 min-h-[88px]">
    <div className="flex flex-col items-center"><span className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 border-2 border-slate-200 text-slate-600 text-xs font-bold">{stop.sequence}</span><span className="w-0.5 flex-1 bg-slate-200" /></div>
    <div className="flex-1 min-w-0 rounded-xl border bg-white border-slate-200 p-3 mb-3 space-y-1 text-xs text-slate-500">
      <p className="font-semibold text-sm text-slate-800">{stop.name}</p><p className="font-semibold uppercase text-[#176B87]">{stop.research_visit?'Adult research visit — no passengers':stop.action}</p>
      {stop.student_id && <p>Student: {stop.student_name ?? 'Name unavailable'} · {stop.student_id}</p>}
      {stop.grouped&&<p>Grouped school visit: {stop.student_ids?.map(id=>stop.student_names?.[id]??id).join(', ')}</p>}
      {stop.school_id && <p>School: {stop.school_name ?? 'Name unavailable'} · {stop.school_id}</p>}
      <details><summary>Location details</summary><p className="break-all">{stop.latitude}, {stop.longitude} / {stop.location_id}</p></details>
      <p>Planned ETA: {time(stop.eta)}</p><p>Arrival: {time(stop.arrival)}</p>
      <p>Driving {stop.driving_seconds_from_previous ?? 'Unknown'} s · service {stop.service_seconds} s · waiting {stop.waiting_seconds} s</p>
      <p>Planned onboard: {stop.load_before} → {stop.load_after}</p><SourceBadge source={stop.travel_source?.source} />
      {stop.travel_source?.fallback_reason && <p className="text-amber-800">Fallback: {stop.travel_source.fallback_reason}</p>}
      <p>Location input: {stop.location_method === 'google' ? 'Live provider input (Google geocoding)' : inputs[stop.input_source]} · {stop.location_method}</p>
    </div>
  </li>;
}
