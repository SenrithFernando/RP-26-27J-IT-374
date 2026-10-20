import { WorkspaceHeader } from './WorkspaceHeader';
import { WorkspaceDialog } from './WorkspaceDialog';
import { vehicleLabel, durationLabel, serviceDateLabel } from '../services/uiFormat';
import { useEffect, useState } from 'react';
import { PositionStatus } from './PositionStatus';
import { PlannedRouteDurations } from './PlannedRouteDurations';
import { useVehiclePosition } from '../hooks/useVehiclePosition';
import { DriverTrip } from './DriverTrip';
import { TrackingAuthorization } from './TrackingAuthorization';
import { fetchVehicles, RouteDirection, StoredRouteStop, VehicleRecord } from '../services/api';
import { localPlanningDate, routePoints } from '../services/routePresentation';
import { useStoredDriverRoute } from '../hooks/useStoredDriverRoute';
import { SourceBadge, TrafficRouteMap } from './TrafficDetails';

const time = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) : 'Unknown';

export function DriverStoredRoute({ vehicleId, direction, onVehicleChange, onDirectionChange, onBack,accountName,initialPurpose='school',initialServiceDate }: {
  accountName?:string; initialPurpose?:'school'|'research';initialServiceDate?:string;
  vehicleId: string; direction: RouteDirection; onVehicleChange: (id: string) => void;
  onDirectionChange: (direction: RouteDirection) => void; onBack: () => void;
}) {
  const [optionsOpen,setOptionsOpen]=useState(false),[routeOpen,setRouteOpen]=useState(false),[sharingState,setSharingState]=useState('Not sharing in this tab');
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

  const trip=!view.tripError?view.trip:null;
  const published=view.publicationStatus===(purpose==='research'?'reviewed_research':'published');
  const displayRoute=trip?.route??(!view.error&&published?route:null);
  const mapAge=livePosition?(Date.now()-Date.parse(livePosition.recorded_at))/1000:Infinity;
  const mapPosition=livePosition&&gps.data?.status==='fresh'&&mapAge>=0&&mapAge<=gps.data.stale_after_seconds&&livePosition.accuracy_quality!=='poor'?livePosition:null;
  const gpsState=gps.error?'Unavailable':!livePosition?'No GPS':livePosition.accuracy_quality==='poor'?'Poor accuracy':gps.data?.status==='stale'||mapAge>(gps.data?.stale_after_seconds??0)?'Stale GPS':mapPosition?'Fresh GPS':'GPS unknown';
  return <section aria-label="Database driver route" className="absolute inset-0 min-h-0 bg-[#F7F9FC] flex flex-col">
    <WorkspaceHeader driver title={`${vehicleId?vehicleLabel(vehicleId):'Select vehicle'} / ${(trip?.direction??direction)==='morning'?'Morning':'Afternoon'}`} subtitle={`${serviceDateLabel(trip?.route.service_date??serviceDate)}${purpose==='research'?' / Adult research':''}`} username={accountName} onLogout={accountName?onBack:undefined} actions={<><button onClick={()=>setOptionsOpen(true)} className="rounded-lg bg-white/15 px-3 py-2 text-xs font-semibold">Choose route</button>{!accountName&&<button onClick={onBack} className="p-2 text-xs">Back</button>}</>}/>
    <main className="flex-1 min-h-0 overflow-y-auto p-3 md:p-6 space-y-4">
      {directoryLoading&&<p role="status" className="text-sm text-slate-500">Loading assigned vehicles?</p>}
      {directoryError&&<p role="alert" className="bg-red-50 p-3 rounded-lg text-sm text-red-800">{directoryError}<button onClick={()=>setDirectoryRevision(n=>n+1)} className="ml-2 underline">Retry vehicles</button></p>}
      {!directoryLoading&&!vehicles.length&&!directoryError&&<p className="bg-amber-50 p-3 rounded-lg text-sm text-amber-900">No assigned vehicle available. Contact an administrator.</p>}
      {pending&&<p role="status" className="text-sm text-slate-500">Loading published plan?</p>}
      {view.error&&<p role="alert" className="bg-red-50 p-3 rounded-lg text-sm text-red-800">{view.error}<button onClick={refresh} className="ml-2 underline">Retry route</button></p>}
      {!pending&&!view.error&&!displayRoute&&<p role="status" className="bg-amber-50 p-3 rounded-lg text-sm text-amber-900">{purpose==='research'?'No reviewed research route. Review it in administrator tools.':`No current published ${direction} route for this date. ${view.publicationStatus==='draft'?'The draft needs administrator publication.':'Ask the administrator to review and publish.'}`}</p>}
      <section aria-label="Selected route summary" className="rounded-xl bg-white border border-slate-200 shadow-sm p-4">
        <div className="grid grid-cols-3 gap-3"><div><p className="text-xs text-slate-500">Departure</p><p className="font-bold text-lg text-slate-900 mt-1">{displayRoute?new Date(displayRoute.departure).toLocaleTimeString('en-GB',{timeZone:'Asia/Colombo',hour:'2-digit',minute:'2-digit'}):'Unavailable'}</p></div><div><p className="text-xs text-slate-500">Trip</p><p className="font-bold text-sm text-slate-900 mt-2">{trip?.state??'Not prepared'}</p></div><div><p className="text-xs text-slate-500">Planned duration</p><p className="font-bold text-sm text-slate-900 mt-2">{durationLabel(displayRoute?.total_duration_seconds)}</p></div></div>
        <div className="flex flex-wrap justify-between gap-2 items-center mt-3 pt-3 border-t text-xs text-slate-500"><span>{trip?`Fixed v${trip.route_version}`:displayRoute?`Published v${displayRoute.version}`:'No published plan'}</span>{displayRoute&&<SourceBadge source={displayRoute.provider_source?.duration_source}/>}<button disabled={!selected||!visible||view.refreshing} onClick={refresh} className="text-[#176B87] font-semibold">{view.refreshing?'Refreshing?':'Refresh route'}</button></div>
        {trip&&purpose==='school'&&view.publicationStatus!=='published'&&<p className="mt-2 text-xs text-amber-900">Planning: {view.publicationStatus??'unavailable'}. Follow this trip's fixed itinerary; drafts are not instructions.</p>}
        {trip&&route&&trip.route_id!==route.route_id&&<p className="mt-2 text-xs text-amber-900">The published planning version is separate. This trip follows fixed version {trip.route_version}.</p>}
      </section>
      <div className="grid lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)] gap-4 items-start">
        <div className="space-y-3 min-w-0">
          <section aria-label="Driver route map" className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            {displayRoute?<TrafficRouteMap route={displayRoute} vehiclePosition={mapPosition} points={routePoints(displayRoute)} orderedStops={displayRoute.stops.map(s=>({id:s.event_id,order:s.sequence,name:s.name}))} height={220}/>:<div className="h-[220px] flex items-center justify-center p-5 text-sm text-slate-500">No authorized itinerary to map.</div>}
          </section>
          <div role="region" aria-label="Vehicle GPS status" className="bg-white rounded-xl border border-slate-200 p-3 flex flex-wrap justify-between items-start gap-2 text-xs"><div><p className="font-semibold text-slate-800">{gpsState}</p><p className="mt-1 text-slate-500">Last upload: {livePosition?new Date(livePosition.received_at).toLocaleTimeString('en-GB',{timeZone:'Asia/Colombo'}):'Unavailable'} / accuracy {livePosition?.accuracy_m==null?'Unavailable':`${Math.round(livePosition.accuracy_m)} m`}</p></div>{livePosition?.source==='simulation'&&<span className="text-amber-900">Simulated GPS</span>}</div>
          {!trip&&displayRoute&&<button onClick={()=>setRouteOpen(true)} className="text-sm text-[#176B87] font-semibold">View published itinerary</button>}
        </div>
        {selected&&<DriverTrip sharingState={sharingState} onArrivalUpdated={gps.acceptArrival} operational={gps.operational} operationalError={gps.operationalError} simulationVehicle={vehicles.find(v=>v.id===vehicleId)?.input_source==='simulated'} pickups={gps.pickups} pickupError={gps.pickupError} arrival={gps.arrival} arrivalError={gps.arrivalError} vehiclePosition={livePosition} key={`${vehicleId}:${direction}`} trip={trip} error={view.tripError} route={!view.error&&published?route:null} trackingPanel={<><PositionStatus data={liveGps} error={gps.error}/><TrackingAuthorization onStatusChange={setSharingState} key={`${vehicleId}:${trip?.trip_id??''}`} vehicleId={vehicleId} trip={trip} synthetic={vehicles.find(v=>v.id===vehicleId)?.input_source==='simulated'}/></>} canCreate={!!current&&published&&!view.refreshing} refresh={refresh} DriverAction={DriverAction}/>}
      </div>
      {!trip&&route&&!current&&!view.error&&published&&<p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Saved plan is stale or outside its service date. Review in Daily Plan before preparing a trip. {issues.join(' ')}</p>}
    </main>
    <WorkspaceDialog title="Choose route" open={optionsOpen||!vehicleId} onClose={()=>setOptionsOpen(false)}>
      <label className="block text-sm">Assigned vehicle<select aria-label="Driver test vehicle" className="border rounded-lg p-2 block w-full mt-1" value={vehicleId} disabled={directoryLoading||!!directoryError} onChange={e=>onVehicleChange(e.target.value)}><option value="">Select vehicle</option>{vehicles.map(v=><option key={v.id} value={v.id}>{vehicleLabel(v.id)} / {v.capacity} seats</option>)}</select></label>
      <label className="block text-sm">Service date<input type="date" aria-label="Driver service date" value={serviceDate} onChange={e=>setServiceDate(e.target.value)} className="border rounded-lg p-2 block w-full mt-1"/></label>
      <div role="group" aria-label="Driver route direction" className="flex gap-2">{(['morning','afternoon'] as const).map(d=><button key={d} disabled={purpose==='research'} aria-pressed={direction===d} onClick={()=>onDirectionChange(d)} className={`flex-1 rounded-lg p-3 text-sm ${direction===d?'bg-[#176B87] text-white':'border text-slate-600'}`}>{d==='morning'?'Morning Pickup':'Afternoon Drop-off'}</button>)}</div>
      <label className="block text-sm">Journey type<select aria-label="Route workspace" className="border rounded-lg p-2 block w-full mt-1" value={purpose} onChange={e=>{setPurpose(e.target.value as 'school'|'research');if(e.target.value==='research')onDirectionChange('afternoon');}}><option value="school">Published school plan</option><option value="research">Adult research</option></select></label>
      <button onClick={()=>setOptionsOpen(false)} disabled={!selected} className="rounded-lg px-4 py-2.5 text-white bg-[#176B87] disabled:opacity-40">Use selected route</button><button onClick={()=>setDirectoryRevision(n=>n+1)} className="ml-3 text-sm text-[#176B87]">Reload vehicles</button>
    </WorkspaceDialog>
    <WorkspaceDialog title="Published itinerary" open={routeOpen} onClose={()=>setRouteOpen(false)}>{displayRoute&&<><PlannedRouteDurations route={displayRoute} context="Published pre-trip plan"/><ol aria-label="Driver stored actions">{displayRoute.stops.map(s=><DriverAction key={s.event_id} stop={s}/>)}</ol></>}</WorkspaceDialog>
  </section>;
}
function DriverAction({stop}:{stop:StoredRouteStop}){
 return <li data-event-id={stop.event_id} className="flex gap-3 py-3 border-t"><span className="w-8 h-8 rounded-full bg-blue-50 text-[#176B87] font-bold flex items-center justify-center shrink-0 text-sm">{stop.sequence}</span><div><p className="font-semibold text-sm text-slate-900">{stop.name}</p><p className="text-xs text-slate-500 mt-1">{stop.research_visit?'Research visit':stop.action} / planned arrival {time(stop.arrival)} / service {durationLabel(stop.service_seconds)}</p>{stop.grouped&&<p className="text-xs text-slate-500 mt-1">Grouped school visit / {stop.student_ids?.length??'Unknown'} participants</p>}</div></li>;
}
