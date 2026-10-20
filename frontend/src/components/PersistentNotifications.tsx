import { useEffect, useRef, useState } from 'react';
import { Bell, RefreshCw } from 'lucide-react';
import { fetchPersistentInbox, NotificationRecipient, PersistentInbox, setNoticeRead } from '../services/api';
const time=(value:string)=>new Date(value).toLocaleString('en-GB',{timeZone:'Asia/Colombo'});

/** Separate persisted inbox; never merges student-scoped details into ALL/demo notifications. */
export function PersistentNotifications({recipient,allowedStudentIds}:{recipient:NotificationRecipient;allowedStudentIds?:string[]}) {
  const [input,setInput]=useState(allowedStudentIds?.[0]??''),[studentId,setStudentId]=useState(allowedStudentIds?.[0]??'');
  const [revision,setRevision]=useState(0),[cursor,setCursor]=useState<number|undefined>();
  const key=`${recipient}:${studentId}:${cursor??''}`;
  const [view,setView]=useState<{key:string;data:PersistentInbox|null;error:string;loading:boolean}>({key:'',data:null,error:'',loading:false});
  const [saving,setSaving]=useState(''),[saveError,setSaveError]=useState('');
  const currentKey=useRef(key);currentKey.current=key;
  useEffect(()=>{
    let alive=true,sequence=0;
    let controller:AbortController|undefined,timer:ReturnType<typeof setTimeout>|undefined,deadline:ReturnType<typeof setTimeout>|undefined;
    const cancel=()=>{++sequence;controller?.abort();clearTimeout(timer);clearTimeout(deadline);};
    const load=async()=>{
      cancel();if(!alive||document.visibilityState!=='visible'||(recipient==='parent'&&!studentId))return;
      const id=sequence;controller=new AbortController();const request=controller;
      const timeout=setTimeout(()=>request.abort(),8000);deadline=timeout;
      setView(prev=>({...prev,key,loading:true}));
      try{const data=await fetchPersistentInbox(recipient,studentId,request.signal,cursor);if(alive&&id===sequence)setView({key,data,error:'',loading:false});}
      catch(e){if(alive&&id===sequence)setView({key,data:null,error:e instanceof Error?e.message:'Notifications unavailable.',loading:false});}
      finally{clearTimeout(timeout);if(alive&&id===sequence&&document.visibilityState==='visible')timer=setTimeout(load,5000);}
    };
    const visibility=()=>{if(document.visibilityState==='visible')void load();else cancel();};
    setView({key,data:null,error:'',loading:false});setSaveError('');setSaving('');
    document.addEventListener('visibilitychange',visibility);void load();
    return()=>{alive=false;cancel();document.removeEventListener('visibilitychange',visibility);};
  },[key,recipient,studentId,cursor,revision]);
  const shown=view.key===key?view:{key,data:null,error:'',loading:false};
  async function mark(id:string,read:boolean){
    if(saving)return;const requestKey=key;setSaving(id);setSaveError('');
    try{await setNoticeRead(id,recipient,studentId,read);if(currentKey.current===requestKey)setRevision(n=>n+1);}
    catch(e){if(currentKey.current===requestKey)setSaveError(e instanceof Error?e.message:'Read-state save failed.');}
    finally{if(currentKey.current===requestKey)setSaving('');}
  }
  return <section aria-label="Persistent missed-pickup notifications" className="bg-white rounded-xl border border-slate-200 p-4 mb-6 space-y-3">
    <h3 className="font-bold text-slate-800 flex items-center gap-2"><Bell size={18}/>Database missed-pickup events</h3>
    <p className="text-xs text-slate-600">Authenticated inbox. The backend enforces account role and student ownership on every request.</p>
    {recipient==='parent'&&allowedStudentIds&&<select aria-label="Notification linked student" value={studentId} onChange={e=>{setStudentId(e.target.value);setCursor(undefined);}} className="border rounded p-2">{allowedStudentIds.map(id=><option key={id}>{id}</option>)}</select>}
    {recipient==='parent'&&!allowedStudentIds&&<form onSubmit={e=>{e.preventDefault();setCursor(undefined);setStudentId(input.trim());}} className="space-y-2">
      <label className="block text-sm text-slate-700">Database student ID (prototype)<input aria-label="Notification student ID" maxLength={64} value={input} onChange={e=>{setInput(e.target.value);setStudentId('');setCursor(undefined);}} className="w-full mt-1 border rounded-lg p-2"/></label>
      <button disabled={!input.trim()} className="rounded-lg bg-[#176B87] text-white px-3 py-2 text-xs disabled:opacity-40">Load selected student notifications</button>
    </form>}
    {recipient==='parent'&&!studentId&&<p className="text-sm text-slate-500">Select an authorized linked student. No events are loaded without a permitted recipient.</p>}
    {(recipient==='admin'||studentId)&&<>
      <p className="text-xs text-slate-500">{recipient==='parent'?`Selected student: ${studentId}`:'Admin inbox'} / Unread: {shown.data?.unread_count??'Unavailable'}. In-app event created; no external delivery is claimed.</p>
      <button onClick={()=>setRevision(n=>n+1)} className="text-xs text-[#176B87] font-semibold flex items-center gap-1"><RefreshCw size={13}/>Refresh in-app events</button>
      {shown.loading&&<p role="status" className="text-xs text-slate-500">Checking stored events...</p>}
      {shown.error&&<p role="alert" className="text-sm text-red-700">{shown.error} No mock events are substituted.</p>}
      {saveError&&<p role="alert" className="text-sm text-red-700">Read state could not be saved: {saveError}</p>}
      {shown.data&&!shown.data.notifications.length&&<p className="text-sm text-slate-500">No stored missed-pickup events for this recipient.</p>}
      <ol aria-label="Stored missed-pickup events" className="space-y-3">{shown.data?.notifications.map(notice=><li key={notice.id} data-notice-id={notice.id} className={`rounded-xl border p-3 space-y-1 text-xs ${notice.read?'border-slate-200 bg-slate-50':'border-red-100 bg-red-50'}`}>
        <p className="font-semibold text-sm text-slate-800">{notice.message}</p>
        <p>{notice.student_name} / {notice.student_id} / vehicle {notice.vehicle_id}</p>
        <p className="break-all">Trip {notice.trip_id} / route {notice.route_id} / version {notice.route_version??'Unavailable'} / stop {notice.stop_sequence} / window {notice.window_id}</p>
        <p>Deadline event: {time(notice.occurred_at)} / Created: {time(notice.created_at)} (Sri Lanka)</p>
        <p>{notice.mode==='simulation_demo'?'Simulation demo window':'Production-duration window'} / Arrival source: {notice.position_source==='simulation'?'Simulation':notice.position_source==='actual_device'?'Actual device input (reported)':'Unavailable'} / {notice.action_source}</p>
        <p className="font-semibold">In-app event created / {notice.read?'Read':'Unread'}</p>
        <p>Alert generation: {notice.generation_status??'in_app_event_created'}. Hasara parent-channel delivery: {notice.parent_channel_status??'Unavailable — not connected'}.</p>
        {notice.resolution_status&&<p>Resolution: {notice.resolution_status}{notice.resolved_at?` / ${time(notice.resolved_at)} (Sri Lanka)`:''}. Original event/history retained.</p>}
        {notice.read_at&&<p>Read at: {time(notice.read_at)}</p>}
        <button disabled={!!saving} onClick={()=>void mark(notice.id,!notice.read)} className="text-[#176B87] underline disabled:opacity-40">{notice.read?'Mark unread':'Mark read'}</button>
      </li>)}</ol>
      <div className="flex gap-3 text-xs text-[#176B87]">{cursor&&<button onClick={()=>setCursor(undefined)}>Newest events</button>}{shown.data?.truncated&&shown.data.next_before_order_id&&<button onClick={()=>setCursor(shown.data?.next_before_order_id??undefined)}>Older events</button>}</div>
    </>}
  </section>;
}
