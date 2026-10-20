import { WorkspaceDialog } from './WorkspaceDialog';
import { useEffect,useRef,useState } from 'react';
import { apiFetch,TripRecord } from '../services/api';
import { PhoneGpsCapture } from './PhoneGpsCapture';
import { useAuth } from '../contexts/AuthContext';
type Grant={id:string;vehicle_id:string;trip_id:string;kind:string;expires_at:string;revoked_at:string|null;label:string};
export function TrackingAuthorization({vehicleId,trip,synthetic,onStatusChange}:{vehicleId:string;trip:TripRecord|null;synthetic:boolean;onStatusChange?:(state:string)=>void}){
  const {user}=useAuth();
  const operatorMismatch=!!trip?.route.research_journey&&trip.route.research_journey.operator_id!==user?.id;
  const simulationSender=synthetic&&!trip?.adult_phone_field_test_authorized&&!trip?.route.research_journey;
  const [rows,setRows]=useState<Grant[]>([]),[credential,setCredential]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false),[revision,setRevision]=useState(0);
  const [expiresAt,setExpiresAt]=useState(''),[sessionsOpen,setSessionsOpen]=useState(false);
  const contextKey=`${vehicleId}:${trip?.trip_id??''}:${trip?.state??''}:${simulationSender}`;
  const currentContext=useRef(contextKey);currentContext.current=contextKey;
  useEffect(()=>{const controller=new AbortController();setCredential('');setRows([]);setError('');
    apiFetch<Grant[]>('/auth/tracking',controller.signal).then(values=>setRows(values.filter(v=>v.vehicle_id===vehicleId)))
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();
  },[vehicleId,trip?.trip_id,trip?.state,simulationSender,revision]);
  useEffect(()=>{onStatusChange?.('Not sharing in this tab');},[vehicleId,trip?.trip_id,trip?.state,onStatusChange]);
  async function enroll(){
    if(!trip)return;const requestedContext=contextKey;setSaving(true);setError('');
    try{const result=await apiFetch<{credential:string;expires_at:string}>('/tracking/enroll',undefined,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vehicle_id:vehicleId,trip_id:trip.trip_id,kind:simulationSender?'simulation':'phone',label:simulationSender?'Authorized simulation sender':'Driver tracking device'})});
      if(currentContext.current!==requestedContext)return;
      setExpiresAt(result.expires_at);setCredential(result.credential);
      const grants=await apiFetch<Grant[]>('/auth/tracking');if(currentContext.current===requestedContext)setRows(grants.filter(r=>r.vehicle_id===vehicleId));
    }catch(e){setError(e instanceof Error?e.message:'Enrollment failed.');}finally{setSaving(false);}
  }
  async function revoke(id:string){setSaving(true);setError('');try{await apiFetch(`/tracking/${encodeURIComponent(id)}/revoke`,undefined,{method:'POST'});setCredential('');onStatusChange?.('Authorization revoked');setRevision(n=>n+1);}catch(e){setError(e instanceof Error?e.message:'Revocation failed.');}finally{setSaving(false);}}
  const blocked=operatorMismatch?'Sign in as the selected research operator to share GPS.':trip?.state!=='ACTIVE'?'Start the authorized trip before enrolling GPS.':trip?.route.research_journey&&!trip.adult_phone_field_test_authorized?'Administrator adult-test approval is required.':null;
  return <section aria-label="Tracking authorization" className="space-y-4 text-sm">
    {trip?.adult_phone_field_test_authorized&&<p className="rounded-lg bg-amber-50 p-3 text-amber-900 text-xs">Adult landmark test GPS; excluded from student-trip exports.</p>}
    {blocked&&<p className="rounded-lg bg-amber-50 p-3 text-amber-900">{blocked}</p>}
    {!blocked&&!credential&&<button disabled={saving} onClick={()=>void enroll()} className="rounded-lg bg-[#176B87] text-white px-4 py-3 disabled:opacity-40">Enroll {simulationSender?'simulation':'phone'} sender for active trip</button>}
    {simulationSender&&<p className="text-xs text-amber-900">Simulation sender only. Actual phone capture requires administrator approval for this adult test.</p>}
    {credential&&!simulationSender&&trip?.state==='ACTIVE'&&<PhoneGpsCapture key={`${vehicleId}:${trip.trip_id}:${credential}`} credential={credential} expiresAt={expiresAt} onStatusChange={onStatusChange}/>}
    {credential&&simulationSender&&<div className="rounded-lg bg-amber-50 p-3 space-y-2"><p>Private simulation credential. Never share in screenshots or logs.</p><input aria-label="Private tracking credential" type="password" readOnly value={credential} className="border rounded-lg p-2 w-full"/><button onClick={()=>void navigator.clipboard.writeText(credential).catch(()=>setError('Clipboard unavailable.'))} className="text-[#176B87] underline">Copy privately to authorized sender</button></div>}
    {error&&<p role="alert" className="text-red-800">{error}</p>}
    <button onClick={()=>setSessionsOpen(true)} className="text-[#176B87] font-medium underline">Manage GPS sessions</button>
    <p className="text-xs text-slate-500">GPS is bound to this trip and vehicle. Logout, expiry or revocation invalidates uploads.</p>
    <WorkspaceDialog title="GPS sessions" open={sessionsOpen} onClose={()=>setSessionsOpen(false)}>
      {!rows.length&&<p className="text-sm text-slate-500">No authorized sessions for this vehicle.</p>}
      {rows.slice(-10).map(row=><div key={row.id} className="rounded-lg border p-3 text-sm space-y-2"><p className="font-semibold">{row.label} / {row.kind}</p><p className="text-slate-500">{row.revoked_at?'Revoked':Date.parse(row.expires_at)<=Date.now()?'Expired':'Issued'} / expires {new Date(row.expires_at).toLocaleString('en-GB',{timeZone:'Asia/Colombo'})}</p><p className="text-xs break-all text-slate-500">Session reference: {row.id}</p>{!row.revoked_at&&<button disabled={saving} onClick={()=>void revoke(row.id)} className="text-red-700 font-medium">Revoke</button>}</div>)}
      {error&&<p role="alert" className="text-red-800">{error}</p>}
    </WorkspaceDialog>
  </section>;
}
