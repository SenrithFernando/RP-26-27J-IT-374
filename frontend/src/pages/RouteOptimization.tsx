import { FormEvent, useEffect, useRef, useState } from 'react';
import { Bus, Loader2, MapPin, Route, Zap } from 'lucide-react';
import { useAppContext } from '../contexts/AppContext';
import { AlternativeComparison, SourceBadge, sourceName, TrafficRouteMap } from '../components/TrafficDetails';
import { RouteComparisonView, RoutingOutcomeNotice } from '../components/RoutingOutcomeNotice';
import { LocationSetup } from '../components/RouteLocations';
import { routePoints } from '../services/routePresentation';
import {
  ApiError, fetchLatestRoute, fetchPlanStatus, PlanStatus, fetchMapLocations, fetchSchools, fetchVehicles, generateStoredRoute,
  GenerateRouteRequest, MapLocations, RouteDirection, saveSchoolSchedule, SchoolRecord,
  StoredRoute, StoredRouteStop, VehicleRecord, fetchMLStatus, MLStatus, fetchTrafficStatus, TrafficStatus,
} from '../services/api';

const control = 'w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white';
const errorText = (failure: unknown) => failure instanceof Error ? failure.message : 'Unable to complete the request.';
const clock = (iso: string | null) => iso ? new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Colombo', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(iso)) : 'Unknown';
const timeInput = (seconds: number | null) => seconds === null ? '' : `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
const secondsInput = (value: string) => { const [hours, minutes, seconds = 0] = value.split(':').map(Number); return hours * 3600 + minutes * 60 + seconds; };
const duration = (seconds: number | null | undefined) => seconds == null ? 'Unavailable' : `${seconds} s`;

type Draft = { date: string; departure: string; pickup: string; delivery: string; horizon: string; limit: string; speed: string; provider: GenerateRouteRequest['provider']; weather: string; scenario: NonNullable<GenerateRouteRequest['traffic_scenario']>; fallback: NonNullable<GenerateRouteRequest['fallback_policy']>; forceFailure: boolean };
function defaults(direction: RouteDirection): Draft {
  return { date: new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()),
    departure: direction === 'morning' ? '06:00:00' : '12:30:00', pickup: '30', delivery: '30', horizon: '21600', limit: '2', speed: direction === 'morning' ? '6' : '5', provider: 'simulation', weather: '', scenario: 'normal', fallback: 'ml', forceFailure: false };
}
function storedDraft(route: StoredRoute): Draft {
  const request = route.request_settings;
  return { date: request.service_date, departure: timeInput(request.departure_seconds), pickup: String(request.pickup_service_seconds), delivery: String(request.delivery_service_seconds), horizon: String(request.max_route_seconds), limit: String(request.solver_time_limit_seconds), speed: String(request.simulation_speed_mps ?? (route.direction === 'morning' ? 6 : 5)), provider: request.provider, weather: request.weather_flag == null ? '' : String(request.weather_flag), scenario: request.traffic_scenario ?? 'normal', fallback: request.fallback_policy ?? 'ml', forceFailure: request.force_live_failure ?? false };
}
export function RouteOptimization() {
  const { routeState: { routeTab }, setRouteState, routingRevision, lastRoutingOutcome } = useAppContext();
  const direction: RouteDirection = routeTab === 'MORNING' ? 'morning' : 'afternoon';
  const [vehicles, setVehicles] = useState<VehicleRecord[]>([]);
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState('');
  const [directoryLoading, setDirectoryLoading] = useState(true);
  const [directoryError, setDirectoryError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [setup, setSetup] = useState(false);
  const [notice, setNotice] = useState('');
  const [mlStatus, setMLStatus] = useState<MLStatus | null>(null);
  const [mlError, setMLError] = useState('');
  const [trafficStatus, setTrafficStatus] = useState<TrafficStatus | null>(null);
  const [trafficError, setTrafficError] = useState('');
  const [draft, setDraft] = useState<Draft>(() => defaults(direction));
  const [view, setView] = useState<{ key: string; loading: boolean; generating: boolean; route: StoredRoute | null;
    error: string | null; empty: boolean; plan: PlanStatus | null; planError: string | null; locations: MapLocations | null; mapError: string | null } | null>(null);
  const requestId = useRef(0);
  const vehicleId = selectedVehicle || vehicles[0]?.id || '';
  const key = `${vehicleId}:${direction}`;
  const currentKey = useRef(key); currentKey.current = key;
  const current = view?.key === key ? view : null;
  const route = current?.route;
  const feasible = route?.feasibility_status === 'feasible' && route.is_current && !current?.planError && (!current?.plan || (current.plan.is_current && current.plan.route_id === route.route_id));
  const loading = !!vehicleId && (!current || current.loading);
  const generating = current?.generating ?? false;

  useEffect(() => {
    const controller = new AbortController(); let active = true;
    fetchMLStatus(controller.signal).then((status) => { if (active) { setMLStatus(status); setMLError(''); } })
      .catch((failure) => { if (active) { setMLStatus(null); setMLError(errorText(failure)); } });
    fetchTrafficStatus(controller.signal).then((status) => { if (active) { setTrafficStatus(status); setTrafficError(''); } })
      .catch((failure) => { if (active) { setTrafficStatus(null); setTrafficError(errorText(failure)); } });
    return () => { active = false; controller.abort(); };
  }, [revision]);

  useEffect(() => {
    let active = true; const controller = new AbortController();
    setDirectoryLoading(true); setDirectoryError(null);
    Promise.all([fetchVehicles(controller.signal), fetchSchools(controller.signal)])
      .then(([newVehicles, newSchools]) => { if (active) { setVehicles(newVehicles); setSchools(newSchools); } })
      .catch((failure) => { if (active) { setVehicles([]); setSchools([]); setDirectoryError(errorText(failure)); } })
      .finally(() => { if (active) setDirectoryLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [revision, routingRevision]);

  useEffect(() => {
    if (!vehicleId) return;
    const id = ++requestId.current;
    let active = true; const controller = new AbortController();
    setDraft(defaults(direction)); setNotice('');
    setView({ key, loading: true, generating: false, route: null, error: null, empty: false, plan: null, planError: null, locations: null, mapError: null });
    Promise.allSettled([fetchLatestRoute(vehicleId, direction, controller.signal), fetchMapLocations(vehicleId, direction, controller.signal), fetchPlanStatus(vehicleId, direction, controller.signal)])
      .then(([latest, locations, plan]) => {
        if (!active || id !== requestId.current || currentKey.current !== key) return;
        const result = latest.status === 'fulfilled' ? latest.value : null;
        const empty = latest.status === 'rejected' && latest.reason instanceof ApiError && latest.reason.status === 404;
        if (result) setDraft(storedDraft(result));
        setView({ key, loading: false, generating: false, route: result, empty,
          error: latest.status === 'rejected' && !empty ? errorText(latest.reason) : null,
          plan: plan.status === 'fulfilled' ? plan.value : null, planError: plan.status === 'rejected' ? errorText(plan.reason) : null,
          locations: locations.status === 'fulfilled' ? locations.value : null,
          mapError: locations.status === 'rejected' ? errorText(locations.reason) : null });
      });
    return () => { active = false; controller.abort(); requestId.current += 1; };
  }, [vehicleId, direction, key, revision, routingRevision]);

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    if (!vehicleId || loading || generating) return;
    const payload: GenerateRouteRequest = { vehicle_id: vehicleId, direction, service_date: draft.date,
      departure_seconds: secondsInput(draft.departure), pickup_service_seconds: Number(draft.pickup),
      delivery_service_seconds: Number(draft.delivery), max_route_seconds: Number(draft.horizon),
      solver_time_limit_seconds: Number(draft.limit), simulation_speed_mps: draft.provider !== 'simulation' ? null : Number(draft.speed), provider: draft.provider,
      weather_flag: draft.weather !== '' ? Number(draft.weather) as 0 | 1 : null,
      traffic_scenario: draft.provider === 'simulation' ? draft.scenario : 'normal', fallback_policy: draft.fallback,
      force_live_failure: draft.provider === 'google' && draft.forceFailure, include_geometry: true };
    const id = ++requestId.current;
    setNotice('');
    setView({ key, loading: false, generating: true, route: null, error: null, empty: false, plan: current?.plan ?? null, planError: current?.planError ?? null, locations: current?.locations ?? null, mapError: current?.mapError ?? null });
    try {
      const result = await generateStoredRoute(payload);
      if (id !== requestId.current || currentKey.current !== key) return;
      setView((prev) => prev && ({ ...prev, generating: false, route: result, empty: false, planError: null,
        plan: { vehicle_id: result.vehicle_id, direction: result.direction, roster_version: result.current_roster_version,
          generation_status: result.planning_status, errors: result.planning_errors, is_current: result.is_current,
          student_count: result.student_count, capacity: result.capacity, route_id: result.route_id,
          trigger_event_id: result.trigger_event_id, generation_timestamp: result.generated_at,
          solver_runtime_seconds: result.solver_runtime_seconds, comparison: result.comparison } }));
      setNotice(`Stored ${direction} version ${result.version}. ${result.feasibility_status === 'feasible' ? 'All assigned active students were served.' : 'No feasible itinerary was stored; inspect the reported status.'}`);
    } catch (failure) {
      if (id === requestId.current && currentKey.current === key) setView((prev) => prev && ({ ...prev, generating: false, error: errorText(failure) }));
    }
  };
  const points = feasible && route ? routePoints(route) : current?.locations?.points ?? [];
  const orderedStops = feasible && route ? route.stops.map((stop) => ({ id: stop.event_id, name: stop.name, order: stop.sequence })) : [];

  return <div className="space-y-6 max-w-6xl mx-auto">
    <div className="flex flex-wrap justify-between items-center gap-4">
      <div><h2 className="text-2xl font-bold text-[#17212B]">Traffic-Aware ML Route Optimization</h2><p className="text-slate-500">Database-backed dual routes · fixed registered assignments · Python optimization</p></div>
      <div className="bg-white p-1 rounded-lg border border-slate-200 shadow-sm flex">
        {(['morning', 'afternoon'] as const).map((value) => <button key={value} onClick={() => setRouteState((prev) => ({ ...prev, routeTab: value === 'morning' ? 'MORNING' : 'AFTERNOON' }))}
          className={`px-4 py-1.5 rounded-md text-sm font-medium ${direction === value ? 'bg-[#176B87] text-white shadow' : 'text-slate-600 hover:bg-slate-50'}`}>{value === 'morning' ? 'Morning Pickup' : 'Afternoon Drop-off'}</button>)}
      </div>
    </div>
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-wrap gap-4 items-end">
      <label className="flex-1 min-w-[180px] text-sm font-medium text-slate-600">Vehicle<select aria-label="Route vehicle" className={control} value={vehicleId} disabled={directoryLoading || !!directoryError} onChange={(event) => setSelectedVehicle(event.target.value)}>
        {!vehicles.length && <option value="">No database vehicles</option>}{vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.id} · capacity {vehicle.capacity}</option>)}
      </select></label>
      <button disabled={!vehicleId || directoryLoading || generating} onClick={() => setSetup(true)} className="text-[#176B87] text-sm font-medium disabled:opacity-50">Configure map locations</button>
      <button disabled={generating} onClick={() => setRevision((value) => value + 1)} className="text-[#176B87] text-sm font-medium disabled:opacity-50">Reload stored route</button>
    </div>
    {directoryLoading && <p role="status" className="text-sm text-slate-500">Loading database vehicles and schools...</p>}
    {directoryError && <p role="alert" className="p-3 rounded-lg bg-red-50 text-red-700">{directoryError}</p>}
    {lastRoutingOutcome?.plans.some((plan) => plan.vehicle_id === vehicleId) && <RoutingOutcomeNotice outcome={lastRoutingOutcome} />}
    {notice && <p role="status" className="p-3 rounded-lg bg-blue-50 text-[#176B87] text-sm">{notice}</p>}
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="space-y-6">
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <h3 className="font-semibold text-[#17212B] flex gap-2 items-center"><Bus size={18} /> Route Summary</h3>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Assigned students" value={current?.plan ? String(current.plan.student_count) : feasible && route ? String(route.student_count) : 'Unavailable'} />
            <Metric label="Capacity" value={current?.plan ? String(current.plan.capacity) : feasible && route ? String(route.capacity) : 'Unavailable'} />
            <Metric label={route?.provider_source?.distance_source === 'google_road_network' ? 'Road distance' : route?.provider_source?.distance_source === 'mixed' ? 'Mixed road / approximate distance' : 'Approx. straight-line distance'} value={!feasible || route?.distance_metres == null ? 'Unavailable' : `${route.distance_metres} m`} />
            <Metric label="Feasibility" value={current?.plan ? current.plan.generation_status.replace(/_/g, ' ') : route ? route.planning_status.replace(/_/g, ' ') : current?.error || directoryError ? 'Unavailable' : generating ? 'Generating' : loading ? 'Loading' : 'Not generated'} />
          </div>
          <div className="space-y-2 border-t border-slate-100 pt-4 text-sm">
            <Metric label={route?.provider_source?.duration_source === 'ml_prediction' ? 'ML-predicted driving (synthetic training)' : `Selected driving estimate · ${sourceName(route?.provider_source?.duration_source)}`} value={duration(feasible ? route?.driving_seconds : null)} />
            <Metric label="Service" value={duration(feasible ? route?.service_seconds : null)} />
            <Metric label="Waiting" value={duration(feasible ? route?.waiting_seconds : null)} />
            <Metric label="Total duration" value={duration(feasible ? route?.total_duration_seconds : null)} />
          </div>
          {route && <div className="space-y-1 text-xs text-slate-500 break-all">
            <p>{feasible ? 'Current route' : 'Historical snapshot (not current)'} {route.route_id} · version {route.version}</p><p>Departure: {route.service_date} {clock(route.departure)} ({route.timezone})</p>
            <p>Solver: {route.solver_status}; runtime {route.solver_runtime_seconds == null ? 'not run' : `${route.solver_runtime_seconds} s`}</p>
            <p>Roster snapshot: {route.roster_version}; current roster: {current?.plan?.roster_version ?? route.current_roster_version}. Trigger: {route.trigger_event}. Execution: {route.execution_status}.</p>
            <p>Provider: {route.provider_source?.provider ?? 'Unavailable'}</p><p>{route.optimality}</p>
            <p>Requested: {route.provider_source?.requested_provider ?? route.request_settings.provider} · Selected: {sourceName(route.provider_source?.duration_source)}</p>
            <SourceBadge source={route.provider_source?.duration_source} />
            {Object.entries(route.provider_source?.route_source_counts ?? {}).map(([source,count]) => <p key={source}>{sourceName(source)}: {count} legs</p>)}
            {route.provider_source?.live_configured === false && <p className="text-amber-800">Google Routes API is not configured on the backend.</p>}
            {(route.provider_source?.route_fallback_reasons ?? route.provider_source?.fallback_reasons ?? []).map((reason) => <p key={reason} className="text-amber-800">Fallback reason: {reason}</p>)}
            <p>Scenario: {route.provider_source?.traffic_scenario ?? 'normal'} · Modified directed matrix arcs: {route.provider_source?.scenario_modified_directed_arcs ?? 'Unavailable'}</p>
            {route.provider_source?.model_version && <p>Model: {route.provider_source.model_version} · training data: synthetic</p>}
            {route.provider_source?.time_assumption && <p>{route.provider_source.time_assumption}</p>}
            {route.provider_source?.warnings?.map((warning) => <p key={warning} className="text-amber-800">{warning}</p>)}
          </div>}
          {route && <AlternativeComparison route={route} />}
          <details className="text-xs"><summary className="cursor-pointer text-slate-500">Historical before/after (different snapshots; not traffic savings)</summary><RouteComparisonView value={current?.plan?.comparison ?? route?.comparison ?? {}} /></details>
          <p className="text-xs text-slate-500">Distances and durations use the labelled sources. Service is configured; waiting is calculated. Provider estimates and ML predictions are not measured journey times.</p>
          <p className="text-xs text-slate-500">This demonstrates a synthetic-data ML pipeline. Real-world accuracy has not yet been established.</p>
        </div>
        <form onSubmit={generate} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <h3 className="font-semibold text-[#17212B]">Generate {direction} route</h3>
          <p className="text-xs text-slate-500">Each direction is solved independently. No students are moved between vehicles or dropped.</p>
          <fieldset disabled={loading || generating || !vehicleId || directoryLoading || !!directoryError} className="space-y-3">
            <label className="block text-sm text-slate-600">Duration provider<select aria-label="Duration provider" value={draft.provider} onChange={(event) => setDraft({ ...draft, provider: event.target.value as Draft['provider'], scenario: 'normal', forceFailure: false })} className={control}>
              <option value="simulation">Deterministic simulated traffic</option><option value="google">Google traffic-aware (with explicit fallback)</option><option value="ml" disabled={!mlStatus?.available}>XGBoost — synthetic training</option><option value="baseline">Historical average baseline</option><option value="unavailable">Unavailable (no estimate)</option>
            </select></label>
            <p className="text-xs text-slate-500">{mlError ? `ML status unavailable: ${mlError}` : mlStatus?.available ? `ML available: ${mlStatus.model_version}` : mlStatus ? `ML unavailable: ${mlStatus.reason}` : 'Loading ML availability...'}</p>
            <p className="text-xs text-slate-500">{trafficError ? `Traffic status unavailable: ${trafficError}` : trafficStatus ? trafficStatus.google.configured ? 'Google Routes credentials configured; live access is verified only by a successful request.' : `Google Routes API not configured: ${trafficStatus.google.reason}` : 'Loading traffic provider status...'}</p>
            {draft.provider === 'simulation' && <label className="block text-sm text-slate-600">Traffic scenario<select aria-label="Traffic scenario" value={draft.scenario} onChange={(event) => setDraft({ ...draft, scenario: event.target.value as Draft['scenario'] })} className={control}><option value="normal">Normal simulation</option><option value="northbound_delay">Northbound corridor delay</option><option value="directed_incident">Selected directed-edge incidents</option></select></label>}
            {(draft.provider === 'google' || draft.provider === 'ml') && <label className="block text-sm text-slate-600">Fallback policy<select aria-label="Fallback policy" value={draft.fallback} onChange={(event) => setDraft({ ...draft, fallback: event.target.value as Draft['fallback'] })} className={control}><option value="none">No fallback; show unavailable</option><option value="ml">ML only; otherwise unavailable</option><option value="ml_then_baseline">ML, then explicit historical baseline</option></select></label>}
            {draft.provider === 'google' && <label className="flex gap-2 text-xs text-amber-800"><input type="checkbox" checked={draft.forceFailure} onChange={(event) => setDraft({ ...draft, forceFailure: event.target.checked })} />Force live adapter failure (local demonstration; makes no external call)</label>}
            {(draft.provider === 'ml' || draft.provider === 'google') && <label className="block text-sm text-slate-600">Weather planning input<select aria-label="Weather planning input" value={draft.weather} onChange={(event) => setDraft({ ...draft, weather: event.target.value })} className={control}><option value="">Unknown / missing</option><option value="0">Dry (user supplied)</option><option value="1">Adverse (user supplied)</option></select></label>}
            <label className="block text-sm text-slate-600">Service date<input required type="date" value={draft.date} onChange={(event) => setDraft({ ...draft, date: event.target.value })} className={control} /></label>
            <label className="block text-sm text-slate-600">Departure (Asia/Colombo)<input required type="time" step="1" value={draft.departure} onChange={(event) => setDraft({ ...draft, departure: event.target.value })} className={control} /></label>
            {([
              ['pickup', 'Pickup service seconds', 0, 3600, 1], ['delivery', 'Delivery service seconds', 0, 3600, 1],
              ['horizon', 'Maximum route seconds', 1, 86400, 1], ['limit', 'Solver limit seconds', 1, 10, 1],
            ] as const).map(([field, label, min, max, step]) => <label key={field} className="block text-sm text-slate-600">{label}<input required type="number" min={min} max={max} step={step} value={draft[field]} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })} className={control} /></label>)}
            {draft.provider === 'simulation' && <label className="block text-sm text-slate-600">Simulation speed (m/s)<input required type="number" min={.01} max={50} step="any" value={draft.speed} onChange={(event) => setDraft({ ...draft, speed: event.target.value })} className={control} /></label>}
            <button type="submit" className="w-full py-3 bg-slate-800 text-white rounded-xl font-semibold shadow-md hover:bg-slate-700 flex items-center justify-center gap-2 disabled:opacity-50">
              {generating ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}{generating ? 'Generating on backend...' : 'Generate route'}
            </button>
          </fieldset>
          {loading && <p role="status" className="text-sm text-slate-500">Loading stored route...</p>}
          {generating && <p role="status" className="text-sm text-slate-500">Solving the registered roster. Switching selection will not cancel backend generation.</p>}
          {current?.empty && !generating && <p className="text-sm text-slate-500">No stored route for this vehicle and direction. Generate it first.</p>}
          {current?.error && <p role="alert" className="text-sm p-3 bg-red-50 text-red-700 rounded-lg">{current.error}</p>}
          {!loading && !generating && current?.plan && !current.plan.is_current && current.plan.generation_status !== 'unconfigured' && <div role="alert" className="text-sm p-3 bg-amber-50 text-amber-900 rounded-lg"><strong>Pre-trip plan: {current.plan.generation_status.replace(/_/g, ' ')}</strong><p>No older itinerary is displayed as current.</p><ul className="list-disc pl-4 mt-2">{current.plan.errors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
          {current?.planError && <p role="alert" className="text-sm text-red-700">Plan freshness could not be verified: {current.planError}</p>}
        </form>
      </div>
      <div className="bg-white rounded-2xl p-2 border border-slate-200 shadow-sm">
        <div className="px-3 py-3 border-b border-slate-100 mb-3"><h3 className="font-semibold text-[#17212B] flex gap-2 items-center"><MapPin size={18} className="text-blue-500" /> {feasible ? 'Stored Route Locations' : 'Current Confirmed Locations'}</h3>
          <p className="text-xs text-slate-500 mt-1">{feasible ? `Version ${route?.version} snapshot. The backend refreshes pre-trip plans after saved input changes.` : 'No feasible current itinerary. These markers are current saved locations only.'}</p></div>
        <TrafficRouteMap route={feasible ? route : null} points={points} orderedStops={orderedStops} missingLocations={feasible ? [] : current?.locations?.missing_locations} loading={loading} error={feasible ? null : current?.mapError} height={540} />
      </div>
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100"><h3 className="font-semibold text-[#17212B] flex gap-2 items-center"><Route size={18} className="text-blue-500" /> Stops & Actions</h3><p className="text-xs text-slate-500 mt-1">ETA is service start; early physical arrival may include waiting. Times: Asia/Colombo.</p></div>
        <ol className="p-2 space-y-2 max-h-[1050px] overflow-y-auto">
          {feasible && route?.stops.map((stop) => <StopRow key={stop.sequence} stop={stop} />)}
        </ol>
        {!feasible && <p className="text-sm text-slate-500 p-5">{loading ? 'Loading stored stops...' : generating ? 'Waiting for the backend solver...' : 'No feasible itinerary to display.'}</p>}
      </div>
    </div>
    <details className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
      <summary className="font-semibold text-[#17212B] cursor-pointer">School schedules (Asia/Colombo)</summary>
      <p className="text-xs text-slate-500 mt-3">Set morning arrival deadlines and afternoon finish times. Blank values are unknown and block generation for the affected school. Saving schedules automatically refreshes affected pre-trip routes using saved generation settings.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">{schools.map((school) => <SchoolScheduleEditor key={`${school.id}:${school.morning_deadline_seconds}:${school.afternoon_finish_seconds}`} school={school} onSaved={(saved) => { setSchools((prev) => prev.map((entry) => entry.id === saved.id ? saved : entry)); setNotice('School schedule saved. See the backend planning outcome above.'); }} />)}</div>
    </details>
    {setup && vehicleId && <LocationSetup schools={schools} vehicles={vehicles} defaultVehicle={vehicleId} onClose={() => setSetup(false)} onSaved={() => { setSetup(false); setRevision((value) => value + 1); }} />}
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="bg-slate-50 rounded-lg border border-slate-100 p-3"><p className="text-xs text-slate-500 mb-1">{label}</p><p className="font-semibold text-[#17212B] break-words">{value}</p></div>;
}
function StopRow({ stop }: { stop: StoredRouteStop }) {
  return <li className="flex gap-3 p-3 rounded-xl hover:bg-slate-50">
    <span className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-bold border-2 border-slate-200 text-slate-600">{stop.sequence}</span>
    <div className="min-w-0 text-xs text-slate-500 space-y-1"><p className="font-semibold text-sm text-slate-800">{stop.name}</p>
      <p className="uppercase font-medium text-[#176B87]">{stop.action}</p><p className="break-all">Student: {stop.student_id ?? '—'} · School: {stop.school_id ?? '—'}</p>
      <p className="break-all">Location: {stop.location_id}</p><p>{stop.latitude}, {stop.longitude}</p>
      <p>{stop.eta ? new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Colombo' }).format(new Date(stop.eta)) : 'Unknown'} | Arrival {clock(stop.arrival)} · ETA {clock(stop.eta)} · Leave {clock(stop.departure)}</p>
      <p>Driving {stop.driving_seconds_from_previous} s · Service {stop.service_seconds} s · Waiting {stop.waiting_seconds} s</p>
      <SourceBadge source={stop.travel_source?.source} />
      {stop.travel_source?.fallback_reason && <p className="text-amber-800">Fallback: {stop.travel_source.fallback_reason}</p>}
      {stop.travel_source?.scenario_modified && <p>Directed scenario delay applied to this leg.</p>}
      <p>Onboard {stop.load_before} → {stop.load_after}</p>
    </div>
  </li>;
}
function SchoolScheduleEditor({ school, onSaved }: { school: SchoolRecord; onSaved: (school: SchoolRecord) => void }) {
  const [morning, setMorning] = useState(timeInput(school.morning_deadline_seconds));
  const [afternoon, setAfternoon] = useState(timeInput(school.afternoon_finish_seconds));
  const [saving, setSaving] = useState(false); const [error, setError] = useState<string | null>(null);
  const save = async (event: FormEvent) => {
    event.preventDefault(); if (saving) return;
    setSaving(true); setError(null);
    try { onSaved(await saveSchoolSchedule(school.id, secondsInput(morning), secondsInput(afternoon))); }
    catch (failure) { setError(errorText(failure)); }
    finally { setSaving(false); }
  };
  return <form onSubmit={save} className="border border-slate-100 rounded-xl bg-slate-50 p-4">
    <fieldset disabled={saving} className="space-y-3"><legend className="text-sm font-semibold text-slate-700">{school.name} ({school.id})</legend>
      <label className="block text-sm text-slate-600">Morning arrival deadline<input required aria-label={`Morning deadline ${school.id}`} type="time" step="1" value={morning} onChange={(event) => setMorning(event.target.value)} className={control} /></label>
      <label className="block text-sm text-slate-600">Afternoon finish time<input required aria-label={`Afternoon finish ${school.id}`} type="time" step="1" value={afternoon} onChange={(event) => setAfternoon(event.target.value)} className={control} /></label>
      <button type="submit" className="text-sm font-medium text-[#176B87] disabled:opacity-50">{saving ? 'Saving schedule...' : 'Save school schedule'}</button>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    </fieldset>
  </form>;
}
