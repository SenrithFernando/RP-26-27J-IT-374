import { useEffect, useState } from 'react';
import type { TripArrival, TripRecord,VehiclePosition } from '../services/api';

export function DriverNavigation({ trip, arrival, error, onAdvance, saving }: { trip: TripRecord; arrival: TripArrival | null; error: string | null;position?:VehiclePosition|null;onAdvance:()=>void;saving:boolean }) {

  const [opened,setOpened]=useState(false),[returned,setReturned]=useState(false),[copyMessage,setCopyMessage]=useState('');
  const selected=arrival?.current_stop;
  const stop=trip.route.stops.find(s=>s.sequence===selected?.sequence && s.event_id===selected?.event_id);
  const consistent=arrival?.trip_id===trip.trip_id && arrival.route_id===trip.route_id && stop && selected &&
    stop.latitude===selected.latitude && stop.longitude===selected.longitude;
  const valid=consistent && stop.location_confirmed===true && selected.location_confirmed===true &&
    Number.isFinite(stop.latitude) && Number.isFinite(stop.longitude) && Math.abs(stop.latitude)<=90 && Math.abs(stop.longitude)<=180;
  const arrived=!!consistent && arrival?.arrival_event?.route_id===trip.route_id && arrival.arrival_event.stop_sequence===stop?.sequence;
  const final=!!stop && stop.sequence===trip.route.stops[trip.route.stops.length-1]?.sequence;
  const ready=trip.state==='ACTIVE' && !error && valid && !arrived;
  const url=ready?`https://www.google.com/maps/dir/?${new URLSearchParams({api:'1',destination:`${stop.latitude},${stop.longitude}`,travelmode:trip.route.research_journey?.travel_mode??'driving',dir_action:'navigate'})}`:null;
  useEffect(()=>{setOpened(false);setReturned(false);setCopyMessage('');},[trip.trip_id,selected?.sequence]);
  useEffect(()=>{
    const back=()=>{if(opened && document.visibilityState==='visible')setReturned(true);};
    window.addEventListener('focus',back);document.addEventListener('visibilitychange',back);
    return()=>{window.removeEventListener('focus',back);document.removeEventListener('visibilitychange',back);};
  },[opened]);
  async function copy(){
    if(!url)return;
    try{await navigator.clipboard.writeText(url);setCopyMessage('Navigation link copied. Open it on the second navigation device; keep the tracking phone in Chrome.');}
    catch{setCopyMessage('Copy unavailable. Use the browser link menu to copy the navigation link to your navigation device.');}
  }
  return <section aria-label="Next stop navigation" className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
    <div className="flex justify-between gap-3 items-center"><h3 className="text-xs uppercase tracking-wide font-semibold text-slate-500">{arrived?'Current stop reached':'Next stop'}</h3><span className="text-xs text-[#176B87]">{consistent?`Stop ${stop?.sequence} of ${trip.route.stops.length}`:'Unavailable'}</span></div>
    {consistent&&stop?<p data-testid="navigation-stop" className="font-bold text-lg text-slate-900">{stop.name}{final?' / final stop':''}</p>:<p className="text-sm text-amber-900">Current authorized stop unavailable. Refresh before navigating.</p>}
    {trip.route.research_journey&&<p className="text-xs text-amber-900">Adult research / occurrence {stop?.occurrence??stop?.sequence??'Unknown'}. No passenger actions.</p>}
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500"><span>{consistent&&arrival?.distance_metres!=null?`${Math.round(arrival.distance_metres)} m away`:'Distance unknown'}</span><span>{error?'GPS unavailable':arrived?'GPS arrival confirmed':arrival?.state==='arrival_candidate'?'Confirming arrival':arrival?.state==='approaching'?'Approaching':'GPS unknown'}</span></div>
    {error&&<p role="alert" className="text-sm text-red-800">{error}</p>}
    {consistent&&!valid&&<p className="text-sm text-amber-900">Saved pin confirmation or valid coordinates required. Navigation is disabled.</p>}
    {!arrived&&arrival?.state==='gps_unknown'&&<p className="text-xs text-amber-900">{arrival.reason??'Fresh eligible GPS required to confirm arrival.'}</p>}
    {url&&<div className="flex flex-wrap gap-3 items-center"><a href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" onClick={()=>{setOpened(true);setReturned(false);}} className="inline-flex min-h-11 items-center rounded-lg bg-[#176B87] px-4 py-2.5 text-white text-sm font-semibold">Navigate to next stop</a><button onClick={()=>void copy()} className="min-h-11 text-sm text-[#176B87] underline">Copy link for navigation device</button></div>}
    {copyMessage&&<p role="status" className="text-xs text-[#176B87]">{copyMessage}</p>}
    {trip.state==='ACTIVE'&&valid&&arrived&&!final&&arrival?.can_advance&&!error&&<button disabled={saving} onClick={onAdvance} className="min-h-11 rounded-lg bg-[#176B87] text-white px-4 py-2.5 text-sm font-semibold disabled:opacity-40">Next stop (manual; no passenger confirmation)</button>}
    {arrived&&<p className="text-xs text-slate-500">{final?'Final saved stop reached. End the trip deliberately; delivery is not implied.':'Arrival recorded. Use Next stop to select the next saved destination; passenger actions are separate.'}</p>}
    {opened&&<p role="status" className="text-xs text-[#176B87]">{returned?'Back in SafeRide. ':''}Opening Maps did not advance this trip. Wait for arrival, then select Next stop.</p>}
    <p className="text-xs text-amber-900">Google Maps can interrupt foreground GPS. Use a second navigation device and keep Chrome visible.</p>
    <p className="text-[11px] text-slate-500">External navigation, not embedded turn-by-turn. Saved stop order stays fixed; Google may choose a different road path.</p>
  </section>;
}
