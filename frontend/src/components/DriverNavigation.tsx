import { useEffect, useState } from 'react';
import type { TripArrival, TripRecord,VehiclePosition } from '../services/api';

export function DriverNavigation({ trip, arrival, error, position, onAdvance, saving }: { trip: TripRecord; arrival: TripArrival | null; error: string | null;position?:VehiclePosition|null;onAdvance:()=>void;saving:boolean }) {
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const [opened,setOpened]=useState(false),[returned,setReturned]=useState(false),[copyMessage,setCopyMessage]=useState('');
  const selected=arrival?.current_stop;
  const stop=trip.route.stops.find(s=>s.sequence===selected?.sequence && s.event_id===selected?.event_id);
  const consistent=arrival?.trip_id===trip.trip_id && arrival.route_id===trip.route_id && stop && selected &&
    stop.latitude===selected.latitude && stop.longitude===selected.longitude;
  const valid=consistent && stop.location_confirmed===true && selected.location_confirmed===true &&
    Number.isFinite(stop.latitude) && Number.isFinite(stop.longitude) && Math.abs(stop.latitude)<=90 && Math.abs(stop.longitude)<=180;
  const arrived=!!arrival?.arrival_event;
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
  return <section aria-label="Next stop navigation" className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
    <h4 className="font-semibold text-slate-800">{arrived?'Current stop reached':'Next stop'}</h4>
    {consistent&&stop?<><p data-testid="navigation-stop" className="font-semibold break-words">Stop {stop.sequence}: {stop.name}{final?' — final saved stop':''}</p><details><summary className="cursor-pointer text-xs">Saved destination reference</summary><p className="text-xs break-all">Fixed route version {trip.route_version} · {trip.route_id}</p></details></>:<p>Current authorized stop unavailable. Refresh; no destination is guessed.</p>}
    {trip.route.research_journey&&<p>Adult research occurrence {stop?.occurrence??'Unknown'} of 4. No student boarding or school windows. Initial A and final A are different occurrences.</p>}
    <p>Last successful backend upload: {position?.received_at?new Date(position.received_at).toLocaleString('en-GB',{timeZone:'Asia/Colombo'}):'Unavailable'} (Sri Lanka) · upload age {position?`${Math.max(0,Math.floor((now-Date.parse(position.received_at))/1000))} s`:'Unknown'}</p>
    <p>GPS recorded age: {position?`${Math.max(0,Math.floor((now-Date.parse(position.recorded_at))/1000))} s`:'Unknown'} · accuracy: {position?.accuracy_m==null?'Unknown':`${position.accuracy_m} m`} / {position?.accuracy_quality??'unknown'}</p>
    <p>Distance: {arrival?.distance_metres==null?'Unknown':`${arrival.distance_metres.toFixed(1)} m`} · Arrival/dwell: {arrival?.state??'GPS unknown'} · observations {arrival?.observation_count??0}</p>
    <p>Prerequisite/status: {error??arrival?.reason??(arrived?'Arrival recorded; explicit advancement required.':arrival?.state==='arrival_candidate'?'Remain for sustained fresh observations.':'Fresh GPS must enter the configured arrival radius; the exit radius alone does not start dwell.')}</p>
    {error&&<p role="alert">Navigation unavailable: {error}</p>}
    {consistent&&!valid&&<p>Saved location confirmation or valid coordinates unavailable. Navigation is disabled.</p>}
    {url&&<div className="flex flex-wrap gap-3 items-center"><a href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" onClick={()=>{setOpened(true);setReturned(false);}} className="inline-flex min-h-11 items-center rounded-lg bg-[#176B87] px-3 py-2 text-white font-semibold">Navigate to next stop</a><button onClick={()=>void copy()} className="min-h-11 text-[#176B87] underline">Copy link for navigation device</button></div>}
    {copyMessage&&<p role="status">{copyMessage}</p>}
    <p className="text-amber-900">Foreground GPS limitation: opening Google Maps can background Chrome and interrupt GPS capture. For today’s research, use a second navigation device and keep Chrome visible and the screen awake on the tracking phone.</p>
    <p>External Google Maps directions/navigation, not embedded turn-by-turn. Only this destination is sent; SafeRide’s saved stop order is unchanged. Maps may show a route preview depending on device/location availability.</p>
    {opened&&<p role="status">{returned?'Back in SafeRide. ':''}Opening Maps did not advance this trip. Keep/resume foreground capture, wait for confirmed arrival, then use “Next stop (manual; no passenger confirmation)”.</p>}
    {arrived&&<p>{final?'Final saved stop reached. No further navigation target. Close the trip deliberately using End trip; no passenger delivery is implied.':'Arrival recorded. Use “Next stop (manual; no passenger confirmation)” below to select the next saved destination.'}</p>}
    {arrival?.can_advance&&!error&&<button disabled={saving} onClick={onAdvance} className="min-h-11 rounded bg-[#176B87] text-white px-3 py-2">Next stop (manual; no passenger confirmation)</button>}
    {!arrived&&<p>On returning to SafeRide, inspect GPS freshness and wait for confirmed arrival. Our trip advances only through the authorized Next stop action; opening or copying a link never advances it.</p>}
  </section>;
}
