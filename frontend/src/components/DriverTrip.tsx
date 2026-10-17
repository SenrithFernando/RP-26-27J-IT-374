import { DriverOperationalEvents } from './DriverOperationalEvents';
import { DriverPickupWindows } from './DriverPickupWindows';
import { useEffect, useRef, useState } from 'react';
import { OperationalEvents, fetchPickupPolicy, PickupPolicy, PickupWindows, advanceTripStop, TripArrival, changeTripState, createPlannedTrip, StoredRoute, TripRecord, VehiclePosition } from '../services/api';
import { routePoints } from '../services/routePresentation';
import { SourceBadge, TrafficRouteMap } from './TrafficDetails';

const time = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) + ' (Sri Lanka)' : 'Not recorded';

export function DriverTrip({ trip, error, route, canCreate, refresh, DriverAction, vehiclePosition, arrival, arrivalError, pickups, pickupError, simulationVehicle, operational, operationalError }: {
  operational: OperationalEvents | null; operationalError: string;
  simulationVehicle: boolean;
  pickups: PickupWindows | null; pickupError: string;
  arrival: TripArrival | null; arrivalError: string;
  vehiclePosition?: VehiclePosition | null;
  trip: TripRecord | null; error: string | null; route: StoredRoute | null; canCreate: boolean;
  refresh: () => void; DriverAction: React.ComponentType<{ stop: StoredRoute['stops'][number] }>;
}) {
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
    if (saving) return;
    setSaving(true); setFailure('');
    try {
      if (action === 'advance' && trip && arrival?.current_stop) await advanceTripStop(trip.trip_id, arrival.current_stop.sequence);
      else if (action === 'create' && route) await createPlannedTrip(route.route_id,pickupMode,pickupScope);
      else if (trip && action !== 'create' && action !== 'advance') await changeTripState(trip.trip_id, action, reason.trim());
      if (alive.current) { setConfirmEnd(false); setCancelling(false); refresh(); }
    } catch (e) { if (alive.current) setFailure(e instanceof Error ? e.message : 'Trip save failed.'); }
    finally { if (alive.current) setSaving(false); }
  }
  const open = trip?.state === 'ACTIVE' || trip?.state === 'PLANNED';
  const button = 'px-3 py-2 rounded-lg bg-[#176B87] text-white text-xs font-semibold disabled:opacity-50';
  return <section aria-label="Persistent trip lifecycle" className="bg-white border border-slate-200 rounded-xl p-3 space-y-3 text-xs text-slate-600">
    <h3 className="font-bold text-sm text-slate-800">Persistent trip lifecycle</h3>
    <p>Manual prototype controls. These actions are not GPS, RFID verification or evidence of student delivery.</p>
    {error && <p role="alert" className="text-red-700">{error} Refresh before taking a trip action.</p>}
    {!error && !trip && <p>No persisted trip for this vehicle.</p>}
    {failure && <p role="alert" className="text-red-700">Trip save failed: {failure}</p>}
    {!error && canCreate && route && !(open && trip?.route_id === route.route_id) && <div className="space-y-2">
      <p>Provisional pickup policy. Production: 15 minutes. Demo is simulation-only.</p>
      {policyError && <p role="alert">Pickup configuration unavailable: {policyError}</p>}
      <label className="block">Pickup window mode<select aria-label="Pickup window mode" value={pickupMode} onChange={e=>setPickupMode(e.target.value as typeof pickupMode)} className="w-full border rounded p-2"><option value="production">Production - 15 minutes</option><option value="simulation_demo" disabled={!simulationVehicle}>Simulation-only demo - {policy?.demo_duration_seconds ?? 'Unavailable'} seconds</option></select></label>
      <label className="block">Pickup window scope<select aria-label="Pickup window scope" value={pickupScope} onChange={e=>setPickupScope(e.target.value as typeof pickupScope)} className="w-full border rounded p-2"><option value="per_stop">Individual stop</option>{route.direction==='afternoon' && <option value="per_school">Shared contiguous school visit</option>}</select></label>
    </div>}
    {!error && canCreate && route && !(open && trip?.route_id === route.route_id) && <button className={button} disabled={saving || !policy || !!policyError || trip?.state === 'ACTIVE'} onClick={() => save('create')}>Create planned trip (manual prototype)</button>}
    {!error && trip && <>
      <p data-testid="driver-trip-id" className="break-all">Trip ID: {trip.trip_id}</p>
      <p data-testid="driver-trip-state" className="font-semibold text-slate-800">State: {trip.state}</p>
      <p>Vehicle: {trip.vehicle_id} / {trip.direction}</p>
      <p data-testid="driver-trip-route" className="break-all">Fixed trip route: {trip.route_id} / version {trip.route_version}</p>
      <p>The trip uses this saved snapshot, independently of the latest planning selection above. Regeneration never replaces its itinerary.</p>
      <p>Created: {time(trip.created_at)}<br />Started: {time(trip.started_at)}<br />Ended: {time(trip.completed_at)}<br />Cancelled: {time(trip.cancelled_at)}</p>
      {trip.cancellation_reason && <p>Cancellation reason: {trip.cancellation_reason}</p>}
      {trip.state === 'ACTIVE' && <section aria-label="Current stop arrival" className="p-3 rounded-lg bg-blue-50 space-y-2">
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
          {arrival.can_advance && <button className={button} disabled={saving} onClick={() => save('advance')}>Next stop (manual; no passenger confirmation)</button>}
        </>}
        <p>Proximity only: no boarding or delivery is confirmed. Only this selected stop is monitored; arrival never advances automatically.</p>
      </section>}
      <DriverOperationalEvents data={operational} error={operationalError} />
      <DriverPickupWindows key={trip.trip_id} data={pickups} error={pickupError} refresh={refresh} />
      {trip.state === 'PLANNED' && <button className={button} disabled={saving} onClick={() => save('start')}>Start trip (manual prototype)</button>}
      {trip.state === 'ACTIVE' && !confirmEnd && <button className={button} disabled={saving} onClick={() => setConfirmEnd(true)}>End trip (manual prototype)</button>}
      {confirmEnd && <div className="p-3 bg-amber-50 rounded-lg space-y-2"><p>Close this trip lifecycle? {trip.unfinished_action_count} pickup/delivery actions remain unrecorded. Ending does not mark students delivered.</p><button className={button} disabled={saving} onClick={() => save('complete')}>Confirm end trip</button> <button disabled={saving} onClick={() => setConfirmEnd(false)}>Keep active</button></div>}
      {open && !cancelling && <button className="block text-red-700 underline" disabled={saving} onClick={() => setCancelling(true)}>Cancel trip deliberately</button>}
      {cancelling && <div className="p-3 bg-amber-50 rounded-lg space-y-2"><label className="block">Cancellation reason<textarea aria-label="Trip cancellation reason" maxLength={500} value={reason} onChange={e => setReason(e.target.value)} className="w-full p-2 border rounded-lg" /></label><button className={button} disabled={saving || !reason.trim()} onClick={() => save('cancel')}>Confirm cancellation</button> <button disabled={saving} onClick={() => setCancelling(false)}>Keep trip</button></div>}
      {saving && <p role="status">Saving trip state...</p>}
      <details open={trip.state === 'ACTIVE'}><summary className="font-semibold cursor-pointer">Fixed trip itinerary and estimates</summary>
        <p>Driving: {trip.route.driving_seconds ?? 'Unavailable'} s / Service: {trip.route.service_seconds ?? 'Unavailable'} s / Waiting: {trip.route.waiting_seconds ?? 'Unavailable'} s / Total: {trip.route.total_duration_seconds ?? 'Unavailable'} s</p>
        <SourceBadge source={trip.route.provider_source?.duration_source} />
        <TrafficRouteMap vehiclePosition={vehiclePosition} key={trip.route_id} route={trip.route} points={routePoints(trip.route)} orderedStops={trip.route.stops.map(stop => ({ id: stop.event_id, order: stop.sequence, name: stop.name }))} height={260} />
        <ol aria-label="Fixed trip actions">{trip.route.stops.map(stop => <DriverAction key={stop.event_id} stop={stop} />)}</ol>
      </details>
      <details open><summary data-testid="unfinished-count" className="font-semibold cursor-pointer">{trip.unfinished_action_count} unresolved / unverified pickup/delivery actions</summary>
        <p>Pickup outcomes are recorded separately by labelled manual actions. PENDING delivery means no delivery confirmation exists; pickup never confirms delivery.</p>
        <ol aria-label="Unfinished trip actions" className="space-y-1 mt-2">{trip.unfinished_actions.map(action => <li key={action.event_id}>{action.sequence}. {action.action} / {action.student_name ?? action.student_id} / {action.school_name ?? action.name} / {action.status}</li>)}</ol>
      </details>
    </>}
  </section>;
}
