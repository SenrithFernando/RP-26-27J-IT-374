import { useEffect,useRef,useState } from 'react';
import { apiFetch,TripRecord } from '../services/api';
import { PhoneGpsCapture } from './PhoneGpsCapture';
type Grant={id:string;vehicle_id:string;trip_id:string;kind:string;expires_at:string;revoked_at:string|null;label:string};
export function TrackingAuthorization({vehicleId,trip,synthetic}:{vehicleId:string;trip:TripRecord|null;synthetic:boolean}){
  const [rows,setRows]=useState<Grant[]>([]),[credential,setCredential]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false),[revision,setRevision]=useState(0);
  const [expiresAt,setExpiresAt]=useState('');
  const contextKey=`${vehicleId}:${trip?.trip_id??''}:${trip?.state??''}`;
  const currentContext=useRef(contextKey);currentContext.current=contextKey;
  useEffect(()=>{const controller=new AbortController();setCredential('');setRows([]);setError('');
    apiFetch<Grant[]>('/auth/tracking',controller.signal).then(values=>setRows(values.filter(v=>v.vehicle_id===vehicleId)))
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();
  },[vehicleId,trip?.trip_id,revision]);
  async function enroll(){
    if(!trip)return;const requestedContext=contextKey;setSaving(true);setError('');
    try{const result=await apiFetch<{credential:string;expires_at:string}>('/tracking/enroll',undefined,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vehicle_id:vehicleId,trip_id:trip.trip_id,kind:synthetic?'simulation':'phone',label:synthetic?'Authorized simulation sender':'Driver tracking device'})});
      if(currentContext.current!==requestedContext)return;
      setExpiresAt(result.expires_at);setCredential(result.credential);
      const grants=await apiFetch<Grant[]>('/auth/tracking');if(currentContext.current===requestedContext)setRows(grants.filter(r=>r.vehicle_id===vehicleId));
    }catch(e){setError(e instanceof Error?e.message:'Enrollment failed.');}finally{setSaving(false);}
  }
  async function revoke(id:string){setSaving(true);setError('');try{await apiFetch(`/tracking/${encodeURIComponent(id)}/revoke`,undefined,{method:'POST'});setCredential('');setRevision(n=>n+1);}catch(e){setError(e instanceof Error?e.message:'Revocation failed.');}finally{setSaving(false);}}
  return <section aria-label="Tracking authorization" className="bg-white border rounded-xl p-4 space-y-3 text-xs">
    <h3 className="font-bold text-sm">Vehicle-bound tracking authorization</h3>
    <p>{synthetic?'Simulation sender only; samples are never labelled actual device.':'Phone credential only; backend derives vehicle, trip and source.'} Logout, expiry, reassignment or revocation removes authorization. Closed-trip queued samples are rejected.</p>
    {synthetic&&<p className="text-amber-800">Actual phone Start sharing is unavailable for this synthetic vehicle. Select an assigned non-synthetic vehicle with an eligible active trip; simulation enrollment does not collect phone GPS.</p>}
    {trip?.state!=='ACTIVE'&&<p>Start sharing requires an ACTIVE trip. Create and start a current feasible saved plan in Persistent trip lifecycle below, then enroll the phone sender.</p>}
    <button disabled={saving||trip?.state!=='ACTIVE'} onClick={()=>void enroll()} className="rounded bg-[#176B87] text-white px-3 py-2 disabled:opacity-40">Enroll {synthetic?'simulation':'phone'} sender for active trip</button>
    {credential&&!synthetic&&trip?.state==='ACTIVE'&&<PhoneGpsCapture key={`${vehicleId}:${trip.trip_id}:${credential}`} credential={credential} expiresAt={expiresAt}/>}
    {credential&&synthetic&&<div className="bg-amber-50 p-3 rounded space-y-2"><p>Private simulation credential shown once in this tab. Treat it like a password; do not put it in URLs, screenshots or logs. Enrollment does not itself collect GPS.</p>
      <input aria-label="Private tracking credential" type="password" readOnly value={credential} className="border rounded p-2 w-full"/>
      <button onClick={()=>{void navigator.clipboard.writeText(credential).catch(()=>setError('Clipboard unavailable; use the private credential field.'));}} className="underline">Copy privately to your authorized sender</button></div>}
    {error&&<p role="alert" className="text-red-700">{error}</p>}
    <ul>{rows.slice(-10).map(row=><li key={row.id} className="border-t py-2 break-all">{row.label} / {row.id} / {row.kind} / trip {row.trip_id}<br/>
      Expires {new Date(row.expires_at).toLocaleString('en-GB',{timeZone:'Asia/Colombo'})} (Sri Lanka) / {row.revoked_at?'Revoked':'Issued'}
      {!row.revoked_at&&<button disabled={saving} onClick={()=>void revoke(row.id)} className="ml-2 text-red-700 underline">Revoke</button>}</li>)}</ul>
  </section>;
}
