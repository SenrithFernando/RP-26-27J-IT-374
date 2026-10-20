import { DriverOperationalEvents } from './DriverOperationalEvents';
import { PlannedRouteDurations } from './PlannedRouteDurations';
import { DriverNavigation } from './DriverNavigation';
import { DriverPickupWindows } from './DriverPickupWindows';
import { useEffect, useRef, useState } from 'react';
import { OperationalEvents, fetchPickupPolicy, PickupPolicy, PickupWindows, advanceTripStop, TripArrival, changeTripState, createPlannedTrip, StoredRoute, TripRecord, VehiclePosition } from '../services/api';
import { routePoints } from '../services/routePresentation';
import { SourceBadge, TrafficRouteMap } from './TrafficDetails';

const time = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) + ' (Sri Lanka)' : 'Not recorded';

export function DriverTrip({ trip, error, route, canCreate, refresh, DriverAction, trackingPanel, mapPanel, vehiclePosition, arrival, arrivalError, pickups, pickupError, simulationVehicle, operational, operationalError }: {
  trackingPanel?: React.ReactNode; mapPanel?: React.ReactNode;
  operational: OperationalEvents | null; operationalError: string;
  simulationVehicle: boolean;
  pickups: PickupWindows | null; pickupError: string;
  arrival: TripArrival | null; arrivalError: string;
  vehiclePosition?: VehiclePosition | null;
  trip: TripRecord | null; error: string | null; route: StoredRoute | null; canCreate: boolean;
  refresh: () => void; DriverAction: React.ComponentType<{ stop: StoredRoute['stops'][number] }>;
}) {
  const submitting=useRef(false);
  const [success,setSuccess]=useState('');
  const [saving, setSaving] = useState(false), [failure, setFailure] = useState('');
  const [confirmEnd, setConfirmEnd] = useState(false), [cancelling, setCancelling] = useState(false), [reason, setReason] = useState('');
  const [policy,setPolicy]=useState<PickupPolicy|null>(null), [policyError,setPolicyError]=useState('');
  const [pickupMode,setPickupMode]=useState<'production'|'simulation_demo'>('production');
  const [pickupScope,setPickupScope]=useState<'per_stop'|'per_school'>('per_stop');
  useEffect(()=>{const controller=new AbortController();fetchPickupPolicy(controller.signal).then(setPolicy).catch(e=>{if(!controller.signal.aborted)setPolicyError(String(e));});return()=>controller.abort();},[]);
  useEffect(()=>{if(policy)setPickupScope(route?.direction==='afternoon'?policy.afternoon_scope:policy.morning_scope);},[policy,route?.direction]);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setConfirmEnd(false); setCancelling(false); setReason(''); }, [trip?.trip_id, trip?.state]);
  async function save(action: 'create' | 'start' | 'complete' | 'cancel' | 'advance') {
    if (submitting.current) return;
    submitting.current=true; setSuccess('');
    setSaving(true); setFailure('');
    try {
      if (action === 'advance' && trip && arrival?.current_stop) await advanceTripStop(trip.trip_id, arrival.current_stop.sequence);
      else if (action === 'create' && route) await createPlannedTrip(route.route_id,pickupMode,route.research_journey?'per_stop':pickupScope);
      else if (trip && action !== 'create' && action !== 'advance') await changeTripState(trip.trip_id, action, reason.trim());
      if (alive.current) { setConfirmEnd(false); setCancelling(false); setSuccess(`Trip ${action} saved. Refreshing the persisted state.`); refresh(); }
    } catch (e) { if (alive.current) setFailure(e instanceof Error ? e.message : 'Trip save failed.'); }
    finally { submitting.current=false; if (alive.current) setSaving(false); }
  }
  const open = trip?.state === 'ACTIVE' || trip?.state === 'PLANNED';
  const research=!!route?.research_journey;
  const finalReached=trip?.state==='ACTIVE'&&arrival?.trip_id===trip.trip_id&&arrival.route_id===trip.route_id&&!!arrival.arrival_event&&arrival.current_stop?.sequence===trip.route.stops.at(-1)?.sequence;
  const button = 'px-3 py-2 rounded-lg bg-[#176B87] text-white text-xs font-semibold disabled:opacity-50';
  return <section aria-label="Persistent trip lifecycle" className="bg-white border border-slate-200 rounded-xl p-3 space-y-3 text-xs text-slate-600">
    <h3 className="font-bold text-sm text-slate-800">Persistent trip lifecycle</h3>
    <p>Manual prototype controls. These actions are not GPS, RFID verification or evidence of student delivery.</p>
    {error && <p role="alert" className="text-red-700">{error} Refresh before taking a trip action.</p>}
    {!error && !trip && <p>No persisted trip for this vehicle.</p>}
    <details><summary className="cursor-pointer">Trip preparation guidance</summary><p>Create planned trip saves a PLANNED record only. Start trip is a separate action; the backend rechecks publication, date, departure allowance and assignment.</p></details>
    {!canCreate&&!open&&<p>Missing prerequisite for a new trip: select a feasible, current published route for the service date; resolve the planning message above and refresh.</p>}
    {trip?.state==='ACTIVE'&&<p>A trip is already active. Its fixed itinerary remains authoritative; another trip cannot be started for this vehicle.</p>}
    {success&&<p role="status">{success}</p>}
    {failure && <p role="alert" className="text-red-700">Trip save failed: {failure}</p>}
    {!error && canCreate && route && !research && !open && <details><summary className="cursor-pointer">Pickup window settings</summary><div className="space-y-2">
      <p>Provisional pickup policy. Production: 15 minutes. Demo is simulation-only.</p>
      {!policy&&!policyError&&<p role="status">Create planned trip unavailable while pickup policy is loading.</p>}
      {policyError && <p role="alert">Pickup configuration unavailable: {policyError}</p>}
      <label className="block">Pickup window mode<select aria-label="Pickup window mode" value={pickupMode} onChange={e=>setPickupMode(e.target.value as typeof pickupMode)} className="w-full border rounded p-2"><option value="production">Production - 15 minutes</option><option value="simulation_demo" disabled={!simulationVehicle}>Simulation-only demo - {policy?.demo_duration_seconds ?? 'Unavailable'} seconds</option></select></label>
      <label className="block">Pickup window scope<select aria-label="Pickup window scope" value={pickupScope} onChange={e=>setPickupScope(e.target.value as typeof pickupScope)} className="w-full border rounded p-2"><option value="per_stop">Individual stop</option>{route.direction==='afternoon' && <option value="per_school">Shared contiguous school visit</option>}</select></label>
    </div></details>}
    {!error && canCreate && route && !open && <button className={button} disabled={saving || (!research&&(!policy || !!policyError)) || trip?.state === 'ACTIVE'} onClick={() => save('create')}>Create planned trip (manual prototype)</button>}
    {!trip&&mapPanel}
    {!trip&&trackingPanel}
    {!error && trip && <>
      {trip.state === 'PLANNED' && <button className={button} disabled={saving} onClick={() => save('start')}>Start trip (manual prototype)</button>}
      <details><summary className="cursor-pointer">Trip identity and history</summary><p data-testid="driver-trip-id" className="break-all">Trip ID: {trip.trip_id}</p>
      <p data-testid="driver-trip-state" className="font-semibold text-slate-800">State: {trip.state}</p>
      <p>Service date: {trip.route.service_date} (Asia/Colombo)<br/>Vehicle: {trip.vehicle_id} / {trip.route.research_journey?'Adult research — fixed order':trip.direction}</p>
      <p data-testid="driver-trip-route" className="break-all">Fixed trip route: {trip.route_id} / version {trip.route_version}</p>
      <p>The trip uses this saved snapshot, independently of the latest planning selection above. Regeneration never replaces its itinerary.</p>
      <p>Created: {time(trip.created_at)}<br />Started: {time(trip.started_at)}<br />Ended: {time(trip.completed_at)}<br />Cancelled: {time(trip.cancelled_at)}</p>
      </details>
      {trip.cancellation_reason && <p>Cancellation reason: {trip.cancellation_reason}</p>}
      <p className="font-semibold text-sm text-[#176B87]">{trip.state} / {trip.direction} / fixed version {trip.route_version}</p>
      {mapPanel}
      {trip.state==='ACTIVE'&&<DriverNavigation trip={trip} arrival={arrival} error={error||arrivalError||null} position={vehiclePosition} saving={saving} onAdvance={()=>void save('advance')} />}
      {trackingPanel}
      {trip.state === 'ACTIVE' && <details><summary className="cursor-pointer">Arrival diagnostics</summary><section aria-label="Current stop arrival" className="p-3 rounded-lg bg-blue-50 space-y-2">
        <h4 className="font-semibold">Current saved-route stop proximity</h4>
        <p data-testid="arrival-state" className="font-bold">{arrivalError || !arrival ? 'GPS unknown' : ({ approaching: 'Approaching', arrival_candidate: 'Arrival candidate', arrived: 'Arrived', gps_unknown: 'GPS unknown' })[arrival.state]}</p>
        {arrivalError && <p role="alert">Arrival status unavailable: {arrivalError}</p>}
        {arrival && <>
          <p>Stop {arrival.current_stop?.sequence ?? 'Unknown'}: {arrival.current_stop?.name ?? 'Unavailable'} / {arrival.current_stop?.action}</p>
          <p>{arrival.reason}</p>
          <p>Distance: {arrival.distance_metres == null ? 'Unknown' : `${arrival.distance_metres.toFixed(1)} m`} / Observations: {arrival.observation_count}</p>
          <p>Enter {arrival.settings.radius_metres} m / exit {arrival.settings.exit_radius_metres} m; dwell {arrival.settings.dwell_seconds} s with at least {arrival.settings.min_observations} observations; max gap {arrival.settings.max_gap_seconds} s; fresh for {arrival.settings.freshness_seconds} s.</p>
          {arrival.candidate_started_at && <p>Candidate began (GPS): {time(arrival.candidate_started_at)}</p>}
          {arrival.arrival_event && <><p>Arrival recorded (GPS): {time(arrival.arrival_event.arrived_at)}</p><p className="break-all">Event: {arrival.arrival_event.event_id} / {arrival.arrival_event.source === 'simulation' ? 'Simulation proximity' : 'Reported device proximity'}</p></>}
        </>}
        <p>Proximity only: no boarding or delivery is confirmed. Only this selected stop is monitored; arrival never advances automatically.</p>
      </section></details>}
      <details><summary className="cursor-pointer">Operational events</summary><DriverOperationalEvents data={operational} error={operationalError} /></details>
      {!trip.route.research_journey&&<details><summary className="cursor-pointer">Pickup outcomes and windows</summary><DriverPickupWindows key={trip.trip_id} data={pickups} error={pickupError} refresh={refresh} /></details>}

      {trip.state === 'ACTIVE' && !confirmEnd && <button className={finalReached?button:"px-3 py-2 rounded-lg border border-[#176B87] text-[#176B87] font-semibold"} disabled={saving} onClick={() => setConfirmEnd(true)}>End trip (manual prototype)</button>}
      {confirmEnd && <div className="p-3 bg-amber-50 rounded-lg space-y-2"><p>Close this trip lifecycle? {trip.unfinished_action_count} pickup/delivery actions remain unrecorded. Ending does not mark students delivered.</p><button className={button} disabled={saving} onClick={() => save('complete')}>Confirm end trip</button> <button disabled={saving} onClick={() => setConfirmEnd(false)}>Keep active</button></div>}
      {open && !cancelling && <button className="block text-red-700 underline" disabled={saving} onClick={() => setCancelling(true)}>Cancel trip deliberately</button>}
      {cancelling && <div className="p-3 bg-amber-50 rounded-lg space-y-2"><label className="block">Cancellation reason<textarea aria-label="Trip cancellation reason" maxLength={500} value={reason} onChange={e => setReason(e.target.value)} className="w-full p-2 border rounded-lg" /></label><button className={button} disabled={saving || !reason.trim()} onClick={() => save('cancel')}>Confirm cancellation</button> <button disabled={saving} onClick={() => setCancelling(false)}>Keep trip</button></div>}
      {saving && <p role="status">Saving trip state...</p>}
      <section aria-label="Trip route" className="space-y-3"><h4 className="font-semibold">Trip route</h4>
        <PlannedRouteDurations route={trip.route} context="Fixed trip plan" />
        <SourceBadge source={trip.route.provider_source?.duration_source} />
        <TrafficRouteMap vehiclePosition={vehiclePosition} key={trip.route_id} route={trip.route} points={routePoints(trip.route)} orderedStops={trip.route.stops.map(stop => ({ id: stop.event_id, order: stop.sequence, name: stop.name }))} height={260} />
        <ol aria-label="Fixed trip actions">{trip.route.stops.map(stop => <DriverAction key={stop.event_id} stop={stop} />)}</ol>
      </section>
      <section aria-label="Unconfirmed passenger actions" className="space-y-2"><h4 data-testid="unfinished-count" className="font-semibold">{trip.unfinished_action_count} passenger actions unconfirmed</h4>
        <p>Pickup outcomes are recorded separately by labelled manual actions. PENDING delivery means no delivery confirmation exists; pickup never confirms delivery.</p>
        <ol aria-label="Unfinished trip actions" className="space-y-1 mt-2">{trip.unfinished_actions.map(action => <li key={action.event_id}>{action.sequence}. {action.action} / {action.student_name ?? action.student_id} / {action.school_name ?? action.name} / {action.status}</li>)}</ol>
      </section>
    </>}
  </section>;
}
