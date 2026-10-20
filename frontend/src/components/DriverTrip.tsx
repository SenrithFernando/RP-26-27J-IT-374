import { WorkspaceDialog } from './WorkspaceDialog';
import { DriverOperationalEvents } from './DriverOperationalEvents';
import { PlannedRouteDurations } from './PlannedRouteDurations';
import { DriverNavigation } from './DriverNavigation';
import { DriverPickupWindows } from './DriverPickupWindows';
import { useEffect, useRef, useState } from 'react';
import { OperationalEvents, fetchPickupPolicy, PickupPolicy, PickupWindows, advanceTripStop, TripArrival, changeTripState, createPlannedTrip, StoredRoute, TripRecord, VehiclePosition } from '../services/api';


export function DriverTrip({ trip, error, route, canCreate, refresh, DriverAction, trackingPanel, sharingState, vehiclePosition, arrival, onArrivalUpdated, arrivalError, pickups, pickupError, simulationVehicle, operational, operationalError }: {
  sharingState?:string; trackingPanel?: React.ReactNode; mapPanel?: React.ReactNode;
  operational: OperationalEvents | null; operationalError: string;
  simulationVehicle: boolean;
  pickups: PickupWindows | null; pickupError: string;
  onArrivalUpdated?: (arrival:TripArrival)=>void;
  arrival: TripArrival | null; arrivalError: string;
  vehiclePosition?: VehiclePosition | null;
  trip: TripRecord | null; error: string | null; route: StoredRoute | null; canCreate: boolean;
  refresh: () => void; DriverAction: React.ComponentType<{ stop: StoredRoute['stops'][number] }>;
}) {
  const [gpsOpen,setGpsOpen]=useState(false),[prepareOpen,setPrepareOpen]=useState(false),[itineraryOpen,setItineraryOpen]=useState(false),[passengersOpen,setPassengersOpen]=useState(false),[eventsOpen,setEventsOpen]=useState(false);
  const submitting=useRef(false);
  const [success,setSuccess]=useState('');
  const [referenceNotice,setReferenceNotice]=useState('');
  const [saving, setSaving] = useState(false), [failure, setFailure] = useState('');
  const [confirmEnd, setConfirmEnd] = useState(false), [cancelling, setCancelling] = useState(false), [reason, setReason] = useState('');
  const [policy,setPolicy]=useState<PickupPolicy|null>(null), [policyError,setPolicyError]=useState('');
  const [pickupMode,setPickupMode]=useState<'production'|'simulation_demo'>('production');
  const [pickupScope,setPickupScope]=useState<'per_stop'|'per_school'>('per_stop');
  useEffect(()=>{const controller=new AbortController();fetchPickupPolicy(controller.signal).then(setPolicy).catch(e=>{if(!controller.signal.aborted)setPolicyError(String(e));});return()=>controller.abort();},[]);
  useEffect(()=>{if(policy)setPickupScope(route?.direction==='afternoon'?policy.afternoon_scope:policy.morning_scope);},[policy,route?.direction]);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { setConfirmEnd(false); setCancelling(false); setReason(''); setReferenceNotice(''); }, [trip?.trip_id, trip?.state]);
  async function save(action: 'create' | 'start' | 'complete' | 'cancel' | 'advance') {
    if (submitting.current) return;
    submitting.current=true; setSuccess('');
    setSaving(true); setFailure('');
    try {
      if (action === 'advance' && trip && arrival?.current_stop) { const next=await advanceTripStop(trip.trip_id, arrival.current_stop.sequence); if(next.trip_id!==trip.trip_id||next.route_id!==trip.route_id)throw new Error('Returned stop does not match this fixed trip. Refresh before continuing.'); onArrivalUpdated?.(next); }
      else if (action === 'create' && route) await createPlannedTrip(route.route_id,pickupMode,route.research_journey?'per_stop':pickupScope);
      else if (trip && action !== 'create' && action !== 'advance') await changeTripState(trip.trip_id, action, reason.trim());
      if (alive.current) { setPrepareOpen(false); setConfirmEnd(false); setCancelling(false); setSuccess(`Trip ${action} saved. Refreshing the persisted state.`); refresh(); }
    } catch (e) { if (alive.current) setFailure(e instanceof Error ? e.message : 'Trip save failed.'); }
    finally { submitting.current=false; if (alive.current) setSaving(false); }
  }
  const open = trip?.state === 'ACTIVE' || trip?.state === 'PLANNED';
  const research=!!route?.research_journey;
  const finalReached=trip?.state==='ACTIVE'&&arrival?.trip_id===trip.trip_id&&arrival.route_id===trip.route_id&&arrival.arrival_event?.route_id===trip.route_id&&arrival.arrival_event?.stop_sequence===arrival.current_stop?.sequence&&arrival.current_stop?.sequence===trip.route.stops.at(-1)?.sequence;
  const button = 'px-3 py-2 rounded-lg bg-[#176B87] text-white text-xs font-semibold disabled:opacity-50';
  async function copyReference(kind:'trip'|'route'){
    if(!trip)return;
    const value=kind==='trip'?trip.trip_id:trip.route_id;
    try{await navigator.clipboard.writeText(value);setReferenceNotice(`${kind==='trip'?'Trip':'Route'} reference copied for authorized administrator tools.`);}
    catch{setReferenceNotice(`Clipboard unavailable. ${kind==='trip'?'Trip':'Route'} reference: ${value}`);}
  }
  return <section aria-label="Persistent trip lifecycle" className="space-y-3">
    {!error&&trip?.state==='ACTIVE'&&<DriverNavigation trip={trip} arrival={arrival} error={arrivalError||null} position={vehiclePosition} saving={saving} onAdvance={()=>void save('advance')}/>}
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
      <div className="flex flex-wrap gap-2 items-center justify-between"><h2 className="font-semibold text-slate-900">Trip controls</h2><span className="text-xs font-medium text-slate-500">{trip?.state??'Not prepared'}</span></div>
      {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800 text-sm">{error} Refresh before continuing.</p>}
      {failure&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800 text-sm">Trip save failed: {failure}</p>}
      {success&&<p role="status" className="text-sm text-[#176B87]">{success}</p>}
      {!open&&!canCreate&&<p className="text-sm text-amber-900">{trip?.state==='COMPLETED'?'This trip is completed. Its fixed itinerary remains available.':'A current, feasible published plan is required to prepare a trip.'}</p>}
      {trip?.state==='PLANNED'&&<p className="text-xs text-slate-500">Prepared only. Start separately within the authorized departure window.</p>}
      {trip?.state==='COMPLETED'&&<p className="text-xs text-slate-500">Completed journey. Review its fixed itinerary below.</p>}
      <div className="flex flex-wrap gap-2">
        {!error&&!open&&canCreate&&route&&trip?.state!=='COMPLETED'&&<button className={button} disabled={saving} onClick={()=>setPrepareOpen(true)}>Prepare trip</button>}
        {!error&&trip?.state==='PLANNED'&&<button className={button} disabled={saving} onClick={()=>void save('start')}>Start trip</button>}
        {trip?.state==='COMPLETED'&&<button className={button} onClick={()=>setItineraryOpen(true)}>View itinerary</button>}
        {!error&&trip?.state==='ACTIVE'&&<button className={finalReached?button:'rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-[#176B87] font-medium'} disabled={saving} onClick={()=>setConfirmEnd(true)}>End trip</button>}
        <button disabled={saving} onClick={()=>setGpsOpen(true)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-[#176B87] font-medium">GPS controls</button>
        {trip&&trip.state!=='COMPLETED'&&<button onClick={()=>setItineraryOpen(true)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-[#176B87]">View itinerary</button>}
      </div>
      <p className="text-xs text-slate-500">Sharing: {sharingState??'Not sharing in this tab'}</p>
      {!error&&trip?.state==='COMPLETED'&&canCreate&&route&&<button disabled={saving} onClick={()=>setPrepareOpen(true)} className="text-xs text-[#176B87] underline">Prepare another trip</button>}
      {open&&<button onClick={()=>setCancelling(true)} className="text-xs text-slate-500 underline">Cancel trip</button>}
      {saving&&<p role="status" className="text-sm text-[#176B87]">Saving trip state?</p>}
    </div>
    {trip&&!trip.route.research_journey&&<button onClick={()=>setPassengersOpen(true)} className="w-full bg-white rounded-xl border border-slate-200 p-4 text-left flex justify-between items-center text-sm"><span className="font-medium text-slate-800">Passenger actions</span><span className="text-slate-500">{trip.unfinished_action_count} unconfirmed</span></button>}
    {!!operational?.episodes?.length&&<button onClick={()=>setEventsOpen(true)} className="rounded-xl bg-amber-50 border border-amber-200 text-amber-900 p-4 w-full text-left text-sm">{operational.episodes.length} stored movement alert{operational.episodes.length===1?'':'s'} / Review alert</button>}
    {operationalError&&<p className="text-xs text-amber-900">Movement monitoring unavailable: {operationalError}</p>}
    <WorkspaceDialog title="GPS controls" keepMounted open={gpsOpen} onClose={()=>setGpsOpen(false)}>{trackingPanel}</WorkspaceDialog>
    <WorkspaceDialog title="Prepare trip" open={prepareOpen} onClose={()=>{if(!saving)setPrepareOpen(false);}}>
      <p className="text-sm text-slate-600">Create a PLANNED trip from published version {route?.version??'Unavailable'}. Starting is a separate action.</p>
      {!research&&<p className="text-sm text-slate-500">Pickup windows: {pickupScope==='per_school'?'shared school visit':'per stop'} / production 15 minutes.</p>}
      {!research&&(!policy||policyError)&&<p role="alert" className="text-amber-900 text-sm">{policyError||'Loading pickup policy?'}</p>}
      {simulationVehicle&&!research&&<div className="space-y-3 border rounded-lg p-3"><p className="text-xs text-amber-900">Simulation trip options</p><label className="block text-sm">Window mode<select aria-label="Pickup window mode" value={pickupMode} onChange={e=>setPickupMode(e.target.value as typeof pickupMode)} className="border rounded-lg p-2 block w-full"><option value="production">Production duration</option><option value="simulation_demo">Simulation demo / {policy?.demo_duration_seconds??'Unavailable'} seconds</option></select></label><label className="block text-sm">Window scope<select aria-label="Pickup window scope" value={pickupScope} onChange={e=>setPickupScope(e.target.value as typeof pickupScope)} className="border rounded-lg p-2 block w-full"><option value="per_stop">Individual stop</option>{route?.direction==='afternoon'&&<option value="per_school">Shared school visit</option>}</select></label></div>}
      {failure&&<p role="alert" className="text-red-800">{failure}</p>}
      <button className={button} disabled={saving||!canCreate||(!research&&(!policy||!!policyError))} onClick={()=>void save('create')}>Create planned trip</button>
    </WorkspaceDialog>
    <WorkspaceDialog title="End trip" open={confirmEnd} onClose={()=>{if(!saving)setConfirmEnd(false);}}><p className="text-sm text-slate-700">{trip?.unfinished_action_count??'Unknown'} passenger actions remain unconfirmed. Ending closes the trip; it does not confirm delivery.</p>{failure&&<p role="alert" className="text-red-800">{failure}</p>}<button className={button} disabled={saving} onClick={()=>void save('complete')}>Confirm end trip</button><button className="ml-3 text-sm text-[#176B87]" onClick={()=>setConfirmEnd(false)}>Keep active</button></WorkspaceDialog>
    <WorkspaceDialog title="Cancel trip" open={cancelling} onClose={()=>{if(!saving)setCancelling(false);}}><label className="block text-sm">Cancellation reason<textarea aria-label="Trip cancellation reason" maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} className="w-full p-2 border rounded-lg mt-1"/></label>{failure&&<p role="alert" className="text-red-800">{failure}</p>}<button className={button} disabled={saving||!reason.trim()} onClick={()=>void save('cancel')}>Confirm cancellation</button></WorkspaceDialog>
    <WorkspaceDialog title="Fixed trip itinerary" open={itineraryOpen} onClose={()=>setItineraryOpen(false)}>{trip&&<><p className="text-sm text-slate-500">{trip.state} / {trip.route.service_date} / {trip.direction} / fixed version {trip.route_version}</p><PlannedRouteDurations route={trip.route} context="Fixed trip plan"/><ol aria-label="Fixed trip actions">{trip.route.stops.map(stop=><DriverAction key={stop.event_id} stop={stop}/>)}</ol><div className="flex flex-wrap gap-3 text-xs text-[#176B87]"><button onClick={()=>void copyReference('trip')}>Copy trip reference</button><button onClick={()=>void copyReference('route')}>Copy route reference</button></div>{referenceNotice&&<p role="status" className="text-xs text-slate-500 break-all">{referenceNotice}</p>}</>}</WorkspaceDialog>
    <WorkspaceDialog title="Passenger actions" open={passengersOpen} onClose={()=>setPassengersOpen(false)}>{trip&&!trip.route.research_journey&&<><p className="text-sm text-amber-900">Manual prototype actions, not RFID verification. Delivery remains separate.</p><DriverPickupWindows key={trip.trip_id} data={pickups} error={pickupError} refresh={refresh}/><h3 className="font-semibold text-sm">Unconfirmed passenger actions</h3><ol className="space-y-2 text-sm">{trip.unfinished_actions.map(a=><li key={a.event_id}>{a.sequence}. {a.student_name??'Name unavailable'} / {a.action} / {a.status}</li>)}</ol></>}</WorkspaceDialog>
    <WorkspaceDialog title="Movement alert" open={eventsOpen} onClose={()=>setEventsOpen(false)}><DriverOperationalEvents data={operational} error={operationalError}/></WorkspaceDialog>
  </section>;
}
