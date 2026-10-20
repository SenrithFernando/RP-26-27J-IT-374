import { useEffect, useState } from 'react';
import { PositionStatus } from './PositionStatus';
import { PlannedRouteDurations } from './PlannedRouteDurations';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { DriverTrip } from './DriverTrip';
import { TrackingAuthorization } from './TrackingAuthorization';
import { ArrowLeft, Loader2, RefreshCw } from 'lucide-react';
import { fetchVehicles, InputSource, RouteDirection, StoredRouteStop, VehicleRecord } from '../services/api';
import { localPlanningDate, routePoints } from '../services/routePresentation';
import { DRIVER_ROUTE_POLL_MS, useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { SourceBadge, sourceName, TrafficRouteMap } from './TrafficDetails';

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
  const pastDate = !!route && route.service_date < localPlanningDate();
  const current = !view.error && route?.feasibility_status === 'feasible' && route.is_current && plan?.is_current &&
    plan.route_id === route.route_id && plan.roster_version === route.roster_version && !pastDate && route.execution_status === 'pre_trip';
  const pending = selected && !view.checkedAt && !view.error;
  const issues = [...new Set([...(route?.errors ?? []), ...(route?.planning_errors ?? []), ...(plan?.errors ?? [])])];
  const points = current && route ? routePoints(route) : [];
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
      <p className="text-xs text-blue-100 mb-3">Only server-authorized vehicles are listed. Trip and GPS permissions are checked on every request.</p>
    </header>
    <main className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
      <PlannedRouteDurations route={durationRoute} context={durationContext} />
      {selected&&<TrackingAuthorization key={vehicleId} vehicleId={vehicleId} trip={view.trip} synthetic={vehicles.find(v=>v.id===vehicleId)?.input_source==='simulated'}/>}
      <label className="block text-sm font-medium text-slate-700">Authorized vehicle<select aria-label="Driver test vehicle" value={vehicleId} disabled={directoryLoading || !!directoryError} onChange={(event) => onVehicleChange(event.target.value)} className="w-full mt-1 p-2 border border-slate-200 rounded-lg bg-white">
        <option value="">Select a database vehicle</option>
        {vehicleId && !selected && <option value={vehicleId}>{vehicleId} — unavailable in directory</option>}
        {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.id} · capacity {vehicle.capacity}</option>)}
      </select></label>
      <label className="block text-sm">Route workspace<select aria-label="Route workspace" className="block border rounded p-2 w-full" value={purpose} onChange={e=>{setPurpose(e.target.value as 'school'|'research');if(e.target.value==='research')onDirectionChange('afternoon');}}><option value="school">Published school plans</option><option value="research">Isolated adult research route</option></select></label>
      <label className="block text-sm">Service date (Asia/Colombo)<input aria-label="Driver service date" type="date" value={serviceDate} onChange={e=>setServiceDate(e.target.value)} className="block border rounded-lg p-2 w-full"/></label>
      <p className="text-xs text-slate-500">API-ready provisional integration. Hasara app is not connected.</p>
      <div style={purpose==='research'?{display:'none'}:undefined} role="group" aria-label="Driver route direction" className="flex bg-white p-1 border border-slate-200 rounded-lg">
        {(['morning','afternoon'] as const).map((value) => <button key={value} aria-pressed={direction === value} onClick={() => onDirectionChange(value)} className={`flex-1 py-2 rounded-md text-sm font-medium ${direction === value ? 'bg-[#176B87] text-white' : 'text-slate-600 hover:bg-slate-50'}`}>{value === 'morning' ? 'Morning Pickup' : 'Afternoon Drop-off'}</button>)}
      </div>
      <div className="flex gap-3 items-center text-xs"><button onClick={refresh} disabled={!selected || !visible} className="text-[#176B87] font-semibold flex gap-1 items-center disabled:opacity-50"><RefreshCw size={14} />Refresh route</button>
        <button onClick={() => setDirectoryRevision((value) => value+1)} className="text-[#176B87] underline">Reload vehicles</button>
        {view.refreshing && <Loader2 aria-label="Refreshing route" size={15} className="animate-spin" />}
      </div>
      <details className="text-xs text-slate-500"><summary>Refresh diagnostics</summary>{visible ? `Checks every ${DRIVER_ROUTE_POLL_MS/1000} seconds while this view is visible.` : 'Polling paused while the page is hidden.'} GET reads only; no optimization.<br />Last checked: {view.checkedAt ? time(view.checkedAt) : 'Not checked'}</details>
      {directoryLoading && <p role="status" className="text-sm text-slate-500">Loading database vehicles...</p>}
      {directoryError && <p role="alert" className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">Vehicles unavailable: {directoryError}</p>}
      {!directoryLoading && !directoryError && !vehicles.length && <p className="text-sm text-slate-500">No registered database vehicles.</p>}
      {!vehicleId && <p className="text-sm text-slate-500">Select a test vehicle to load its stored route. No mock route is substituted.</p>}
      {pending && <p role="status" className="text-sm text-slate-500">Loading stored {direction} plan...</p>}
      {view.error && <p role="alert" className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{view.error} No cached itinerary is treated as current.</p>}
      {!pending && !view.error && view.noRoute && <p role="status" className="p-3 bg-blue-50 text-slate-700 rounded-lg text-sm">{purpose==='research'?`No reviewed adult research route for ${vehicleId} on ${serviceDate}. Confirm pins/mode/people in Admin ? Adult research first.`:`No current published ${direction} route for ${vehicleId} on ${serviceDate}. Publication: ${view.publicationStatus??'Unavailable'}. Review and publish in Admin; this view never generates routes.`}</p>}
      {selected && <PositionStatus data={gps.data} error={gps.error} />}
      {selected && <DriverTrip operational={gps.operational} operationalError={gps.operationalError} simulationVehicle={vehicles.find(vehicle=>vehicle.id===vehicleId)?.input_source==='simulated'} pickups={gps.pickups} pickupError={gps.pickupError} arrival={gps.arrival} arrivalError={gps.arrivalError} vehiclePosition={gps.error ? null : gps.data?.position} key={`${vehicleId}:${direction}`} trip={view.trip} error={view.tripError} route={route} canCreate={!!current && !view.refreshing} refresh={refresh} DriverAction={DriverAction} />}
      {route && <details className="bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-600 space-y-2"><summary className="cursor-pointer font-semibold">Published route details and diagnostics</summary>
        <p className="font-semibold text-slate-800">{current ? 'Current stored pre-trip plan' : 'Historical / non-current plan'}</p>
        <p data-testid="driver-route-id" className="break-all">Route ID: {route.route_id}</p>
        <p data-testid="driver-route-version">Version: {route.version} · roster {route.roster_version} / {plan?.roster_version ?? 'Unavailable'}</p>
        <p>Service date: {route.service_date} · Departure: {time(route.departure)}</p>
        <p>Recommended departure: {route.departure_recommendation?.recommended_departure_seconds!=null?`${String(Math.floor(route.departure_recommendation.recommended_departure_seconds/3600)).padStart(2,'0')}:${String(Math.floor(route.departure_recommendation.recommended_departure_seconds%3600/60)).padStart(2,'0')} Asia/Colombo`:'Unavailable ? selected departure shown above'}</p>
        <p>Departure validation: {route.departure_recommendation?.status??'Legacy fixed-departure plan'}</p>
        <p>Publication: {view.publicationStatus}</p>
        <p>Estimate timestamp: {route.provider_source?.snapshot_generated_at?time(route.provider_source.snapshot_generated_at):'Unavailable'}</p>
        <p>Generated: {time(route.generated_at)} · Execution: {route.execution_status}</p>
        <p data-testid="driver-freshness">Freshness: {pastDate ? 'Past service date — historical plan' : current ? 'Current for this roster' : plan?.generation_status ?? route.planning_status}</p>
        <p>Assigned students: {plan?.student_count ?? route.student_count} · capacity: {plan?.capacity ?? route.capacity}</p>
        <p>Distance: {current && route.distance_metres != null ? `${route.distance_metres} m (${route.provider_source?.distance_is_approximate ? 'approximate' : 'road network'})` : 'Unavailable'}</p>
        <p>Requested provider: {route.request_settings.provider}</p><SourceBadge source={route.provider_source?.duration_source} />
        <p>Selected estimate: {sourceName(route.provider_source?.duration_source)}</p>
        {route.provider_source?.model_version && <p className="break-all">Model: {route.provider_source.model_version} · synthetic training</p>}
        {route.provider_source?.live_configured === false && <p className="text-amber-800">Google Routes is not configured.</p>}
        {(route.provider_source?.route_fallback_reasons ?? route.provider_source?.fallback_reasons ?? []).map((reason) => <p key={reason} className="text-amber-800">Fallback: {reason}</p>)}
        {route.provider_source?.warnings?.map((warning) => <p key={warning} className="text-amber-800">{warning}</p>)}
        <p>{route.provider_source?.time_assumption}</p>
      </details>}
      {!pending && !view.error && route && !current && <div role="alert" className="p-3 bg-amber-50 text-amber-900 rounded-lg text-sm">
        <p>No current feasible pre-trip itinerary to display.</p>
        {pastDate && <p>The stored service date is in the past, even if the backend roster flag remains current.</p>}
        {plan && plan.route_id !== route.route_id && <p>Stored route and planning state do not match; refresh to obtain a consistent version.</p>}
        {issues.map((issue) => <p key={issue} className="mt-1">{issue}</p>)}
      </div>}
      {current && route && <>
        <TrafficRouteMap vehiclePosition={gps.error ? null : gps.data?.position} key={route.route_id} route={route} points={points} orderedStops={route.stops.map((stop) => ({ id: stop.event_id, order: stop.sequence, name: stop.name }))} height={300} />
        <div><p className="text-xs uppercase tracking-wide font-semibold text-slate-400">{route.research_journey?'Ordered adult research stop occurrences':'Ordered pickup / delivery actions'}</p><h3 className="font-bold text-slate-800">{route.stops.length} stored actions</h3><p className="text-xs text-slate-500">Planned ETA, Asia/Colombo; no live GPS or completion progress implied.</p></div>
        <ol aria-label="Driver stored actions">{route.stops.map((stop) => <DriverAction key={stop.event_id} stop={stop} />)}</ol>
      </>}
    </main>
    <footer className="shrink-0 p-3 bg-white border-t border-slate-200 text-xs text-slate-500">Persistent manual pickup lifecycle; delivery recording and navigation are not connected here. GPS samples are source-labelled. Cabin, RFID, camera and emergency features: Not connected in Authenticated operations.</footer>
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
      <p className="break-all">{stop.latitude}, {stop.longitude} · {stop.location_id}</p>
      <p>Planned ETA: {time(stop.eta)}</p><p>Arrival: {time(stop.arrival)}</p>
      <p>Driving {stop.driving_seconds_from_previous ?? 'Unknown'} s · service {stop.service_seconds} s · waiting {stop.waiting_seconds} s</p>
      <p>Planned onboard: {stop.load_before} → {stop.load_after}</p><SourceBadge source={stop.travel_source?.source} />
      {stop.travel_source?.fallback_reason && <p className="text-amber-800">Fallback: {stop.travel_source.fallback_reason}</p>}
      <p>Location input: {stop.location_method === 'google' ? 'Live provider input (Google geocoding)' : inputs[stop.input_source]} · {stop.location_method}</p>
    </div>
  </li>;
}
