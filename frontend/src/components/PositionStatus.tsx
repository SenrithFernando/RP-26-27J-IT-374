import { useEffect, useState } from 'react';
import { LatestPosition } from '../services/api';

export const localTime = (value?: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) : 'Unavailable';
export function PositionStatus({ data, error }: { data: LatestPosition | null; error: string }) {
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const position=error?null:data?.position;
  const age=position?Math.max(0,(now-new Date(position.recorded_at).getTime())/1000):null;
  const status=!position?'unknown':data?.status==='unknown'?'unknown':data?.status==='stale'||age==null||age>data!.stale_after_seconds?'stale':'fresh';
  return <section aria-label="Vehicle GPS status" className="bg-white border border-slate-200 rounded-xl p-3 space-y-1 text-xs text-slate-600">
    <p className="font-semibold">Vehicle position: {status}</p>
    {error&&<p role="alert" className="text-red-700">Position unavailable: {error}</p>}
    {!position&&<p>Position, speed and live arrival estimate: Unavailable. No GPS observation is available.</p>}
    {position&&<>
      <p>Recorded: {localTime(position.recorded_at)} (Sri Lanka)</p><p>Received: {localTime(position.received_at)}</p>
      <p>Source: {position.source==='simulation'?'Simulation — synthetic movement, not a driven road trace':'Actual device input (reported; not independently verified)'}</p>
      {position.source==='simulation'&&<p>Actual-device position: Unavailable. The displayed sample is synthetic.</p>}
      <p>Position ID: {position.id} / Sample: {position.sample_id} / Trip: {position.trip_id??'Not linked to a trip'}</p>
      <p>Accuracy: {position.accuracy_m==null?'Unavailable':`${position.accuracy_m} m`} / {position.accuracy_quality??'unknown'}{position.accuracy_quality==='poor'?' — excluded from arrival/anomaly transitions':''}</p>
      <p>Age: {age==null||!Number.isFinite(age)?'Unavailable':`${Math.floor(age)} s`} / stale after {data?.stale_after_seconds??'Unavailable'} s</p>
      <p>{position.latitude}, {position.longitude} / Recorded speed: {position.speed_mps==null?'Unavailable':`${position.speed_mps} m/s`}{status!=='fresh'?' (historical sample; current speed unavailable)':''}</p>
      <p>Live arrival estimate: Unavailable. Saved route ETAs are planning estimates.</p>
    </>}
    <p>Missing or stale GPS is not evidence of a stopped vehicle. GPS proximity does not verify passengers.</p>
  </section>;
}
