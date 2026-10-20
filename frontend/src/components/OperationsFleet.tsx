import { useEffect, useState, ReactNode } from 'react';
import { Bus, Clock3, MapPin, RefreshCw } from 'lucide-react';
import { fetchVehicles, VehicleRecord, RouteDirection } from '../services/api';
import { useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { localPlanningDate, routePoints } from '../services/routePresentation';
import { durationLabel, serviceDateLabel, vehicleLabel } from '../services/uiFormat';
import { SourceBadge, TrafficRouteMap } from './TrafficDetails';
import { PositionStatus } from './PositionStatus';

/** Read-only fleet view. Active-trip GPS is always scoped to that trip. */
export function OperationsFleet() {
  const [vehicles, setVehicles] = useState<VehicleRecord[]>([]);
  const [vehicle, setVehicle] = useState('');
  const [direction, setDirection] = useState<RouteDirection>('morning');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    fetchVehicles(controller.signal).then(rows => {
      if (!controller.signal.aborted) {
        setVehicles(rows); setVehicle(old => rows.some(row => row.id === old) ? old : rows[0]?.id ?? '');
      }
    }).catch(cause => {
      if (!controller.signal.aborted) { setVehicles([]); setError(cause instanceof Error ? cause.message : 'Please try again.'); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  const selected = !loading && !error && vehicles.some(row => row.id === vehicle) ? vehicle : '';
  const { view, refresh } = useStoredDriverRoute(selected, direction);
  const trip = !view.tripError ? view.trip : null;
  const active = trip?.state === 'ACTIVE' ? trip : null;
  const gps = useVehiclePosition(active ? selected : '', active?.trip_id ?? '');
  const route = active?.route ?? (!view.error ? view.route : null);
  const position = !gps.error && active && gps.data?.position?.trip_id === active.trip_id && gps.data.position.vehicle_id === selected ? gps.data.position : null;
  const tripGps = gps.data ? {...gps.data,position,status:position?gps.data.status:'unknown' as const,age_seconds:position?gps.data.age_seconds:null} : null;
  const age = position ? (now - new Date(position.recorded_at).getTime()) / 1000 : Infinity;
  const mapPosition = active && position?.trip_id === active.trip_id && gps.data?.status === 'fresh' &&
    Number.isFinite(age) && age >= 0 && age <= gps.data.stale_after_seconds && position.accuracy_quality !== 'poor' ? position : null;
  const arrival = !gps.arrivalError && gps.arrival?.trip_id === active?.trip_id ? gps.arrival : null;
  const historical = !!route && route.service_date < localPlanningDate();
  const current = !!route && route.is_current && (active || (view.plan?.is_current && view.plan.route_id === route.route_id));
  const routeState = active ? 'Trip in progress' : !route ? 'No route available' : historical ? 'Past plan' : current ? 'Saved plan' : 'Needs review';
  const directionName = (active?.route.direction ?? direction) === 'morning' ? 'Morning pickup' : 'Afternoon drop-off';
  const field = 'mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#176B87]';
  return <section aria-label="Authorized fleet operations" className="mx-auto max-w-7xl space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h1 className="text-2xl font-bold tracking-tight text-slate-900">Live Tracking</h1><p className="mt-1 text-sm text-slate-500">Track active trips and view saved routes.</p></div>
      <button type="button" disabled={loading || view.refreshing} onClick={() => { refresh(); setRevision(value => value + 1); }} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={16} className={loading || view.refreshing ? 'animate-spin' : ''} />Refresh</button>
    </div>
    <div className="flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-4">
      <label className="w-full min-w-0 text-sm font-medium text-slate-600 sm:w-auto sm:flex-1">Vehicle<select aria-label="Fleet vehicle" disabled={loading || !vehicles.length} value={vehicle} onChange={event => setVehicle(event.target.value)} className={field}>
        {!vehicles.length && <option value="">{loading ? 'Loading vehicles…' : 'No vehicles available'}</option>}
        {vehicles.map(row => <option key={row.id} value={row.id}>{vehicleLabel(row.id)}</option>)}
      </select></label>
      <label className="w-full min-w-0 text-sm font-medium text-slate-600 sm:w-auto sm:flex-1">Route<select aria-label="Fleet direction" disabled={!!active} value={active?.route.direction ?? direction} onChange={event => setDirection(event.target.value as RouteDirection)} className={field}><option value="morning">Morning pickup</option><option value="afternoon">Afternoon drop-off</option></select></label>
      {selected && <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600">{vehicles.find(row => row.id === selected)?.input_source === 'simulated' ? 'Test vehicle' : 'Registered vehicle'}</span>}
    </div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">Vehicles could not be loaded. {error}</p>}
    {view.error && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Route information is unavailable. {view.error}</p>}
    {view.tripError && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Trip status could not be checked. {view.tripError}</p>}
    {selected && !view.checkedAt && <p role="status" className="text-sm text-slate-500">Loading fleet information…</p>}
    {selected && view.checkedAt && <>
      <div className="grid gap-3 sm:grid-cols-3">
        <FleetStat icon={<Bus size={19} />} label="Trip status" value={active ? 'In progress' : trip?.state === 'PLANNED' ? 'Not started' : trip?.state === 'COMPLETED' ? 'Completed' : trip?.state === 'CANCELLED' ? 'Cancelled' : view.tripError ? 'Unavailable' : 'No active trip'} />
        <FleetStat icon={<MapPin size={19} />} label="Route" value={directionName} />
        <FleetStat icon={<Clock3 size={19} />} label="Estimated route duration" value={durationLabel(route?.total_duration_seconds)} />
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_290px]">
        <section aria-label="Fleet route map" className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
            <div><h2 className="font-semibold text-slate-900">{vehicleLabel(selected)} route</h2>{route && <p className="mt-1 text-xs text-slate-500">{serviceDateLabel(route.service_date)} · Version {route.version}</p>}</div>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${active ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>{routeState}</span>
          </div>
          {route ? <div className="p-3"><TrafficRouteMap route={route} points={routePoints(route)} orderedStops={route.stops.map(stop => ({ id: stop.event_id, order: stop.sequence, name: stop.name }))} vehiclePosition={mapPosition} height={420} /></div> : <div className="flex min-h-[300px] flex-col items-center justify-center gap-3 px-6 text-center text-slate-500"><MapPin size={30} /><p>No saved route to display.</p><p className="text-sm">Prepare a route in Daily Plan, then return here.</p></div>}
          <p className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500">{active ? 'Following the active trip’s fixed route.' : 'Saved route preview. No live vehicle position is shown until a trip starts.'}</p>
        </section>
        <aside className="space-y-4">
          {active ? <PositionStatus data={tripGps} error={gps.error} /> : <div className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-900">Live location</h2><p className="mt-2 text-sm text-slate-500">{view.tripError ? 'Trip status is unavailable.' : 'No trip is currently active.'}</p><p className="mt-2 text-xs text-slate-500">Previous journeys are not shown as live tracking.</p></div>}
          {active && <div className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-900">Current stop</h2><p className="mt-2 text-sm text-slate-700">{arrival?.current_stop?.name ?? 'Waiting for stop information'}</p><p className="mt-2 text-xs text-slate-500">{gps.arrivalError ? 'Arrival status unavailable.' : arrival?.state === 'arrived' ? 'GPS arrival confirmed. Boarding is recorded separately.' : arrival?.state === 'arrival_candidate' ? 'Checking arrival…' : arrival?.state === 'approaching' ? 'Approaching this stop.' : 'Waiting for fresh GPS.'}</p></div>}
          {route && <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-900">Plan summary</h2><dl className="space-y-2 text-sm"><div className="flex justify-between gap-2"><dt className="text-slate-500">Stops</dt><dd className="font-medium">{route.stops.filter(stop => stop.action !== 'start' && stop.action !== 'end').length}</dd></div><div className="flex justify-between gap-2"><dt className="text-slate-500">Driving</dt><dd>{durationLabel(route.driving_seconds)}</dd></div><div className="flex justify-between gap-2"><dt className="text-slate-500">At stops</dt><dd>{durationLabel(route.service_seconds)}</dd></div></dl><SourceBadge source={route.provider_source?.duration_source} />{route.provider_source?.force_live_failure && <p className="text-xs text-amber-800">Failure test enabled. This estimate is not live Google traffic.</p>}{!!route.provider_source?.route_fallback_reasons?.length && <p className="text-xs text-amber-800">A fallback estimate was used.</p>}</div>}
        </aside>
      </div>
    </>}
  </section>;
}
function FleetStat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4"><span className="rounded-lg bg-slate-50 p-2.5 text-[#176B87]">{icon}</span><div className="min-w-0"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-sm font-semibold text-slate-900">{value}</p></div></div>;
}
