import { useEffect, useRef, useState } from 'react';
import { cancelPickup, confirmPickup, PickupWindows } from '../services/api';
const time = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) : 'Not started';

export function DriverPickupWindows({ data, error, refresh }: { data: PickupWindows | null; error: string; refresh: () => void }) {
  const [saving, setSaving] = useState(false), [failure, setFailure] = useState('');
  const [cancelId, setCancelId] = useState(''), [reason, setReason] = useState('');
  const alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  async function save(studentId: string, action: 'confirm' | 'cancel') {
    if (!data || saving) return;
    setSaving(true);setFailure('');
    try {
      if (action==='confirm') await confirmPickup(data.trip_id,studentId);
      else await cancelPickup(data.trip_id,studentId,reason.trim());
      if(alive.current){setCancelId('');setReason('');refresh();}
    } catch(e){if(alive.current)setFailure(e instanceof Error?e.message:'Pickup action failed.');}
    finally{if(alive.current)setSaving(false);}
  }
  return <section aria-label="Persistent pickup windows" className="rounded-lg border border-slate-200 p-3 space-y-2">
    <h4 className="font-semibold">Pickup exception windows</h4>
    <p>Provisional policy; supervisor confirmation is not recorded. Manual prototype actions are not RFID verification. Student delivery is separate.</p>
    {error && <p role="alert" className="text-red-700">Pickup windows unavailable: {error}</p>}
    {failure && <p role="alert" className="text-red-700">Pickup action failed: {failure}</p>}
    {!error && !data && <p>Loading server pickup windows...</p>}
    {!error && data && <>
      <p>Server time (Sri Lanka): {time(data.server_now)}. Remaining time is sampled from the server; no browser-owned deadline.</p>
      {!data.settings && <p>This trip predates persistent pickup windows. Existing history is preserved; create a new trip for this workflow.</p>}
      {data.windows.map(window=><div key={window.window_id} data-window-id={window.window_id} className="border-t border-slate-200 pt-2 space-y-2">
        <p className="font-semibold">{window.mode==='production'?'PRODUCTION - 15 minutes':`SIMULATION DEMO - ${window.duration_seconds} seconds`} / {window.scope==='per_school'?'Shared school visit':'Individual stop'} / {window.state}</p>
        <p className="break-all">{window.scope_key}</p>
        <p>Started: {time(window.started_at)} / Deadline: {time(window.deadline_at)}</p>
        <p>Remaining (server): {window.remaining_seconds==null?'Awaiting confirmed pickup arrival':`${Math.ceil(window.remaining_seconds)} seconds`}{window.expiry_pending?' / Expiry pending worker; confirmation disabled':''}</p>
        {window.outcomes.map(outcome=><div key={outcome.student_id} data-student-id={outcome.student_id} className="bg-slate-50 rounded-lg p-2 space-y-1">
          <p className="font-semibold">{outcome.student_name} / stop {outcome.stop_sequence}: <span data-testid="pickup-outcome">{outcome.state}</span></p>
          <p>{outcome.action_source} / Changed: {time(outcome.changed_at)}</p>
          {outcome.picked_up_at && <p>Manual pickup recorded: {time(outcome.picked_up_at)}; delivery remains unconfirmed.</p>}
          <button disabled={saving || !outcome.can_confirm} onClick={()=>save(outcome.student_id,'confirm')} className="px-2 py-1 rounded bg-[#176B87] text-white disabled:opacity-40">Confirm pickup (manual prototype)</button>
          <button disabled={saving || !outcome.can_cancel} onClick={()=>{setCancelId(outcome.student_id);setReason('');}} className="ml-2 text-red-700 underline disabled:opacity-40">Cancel pickup</button>
          {cancelId===outcome.student_id && <div><label>Cancellation reason<input aria-label="Pickup cancellation reason" maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} className="w-full border rounded p-1" /></label><button disabled={saving || !reason.trim() || !outcome.can_cancel} onClick={()=>save(outcome.student_id,'cancel')} className="underline">Confirm pickup cancellation</button></div>}
        </div>)}
      </div>)}
    </>}
  </section>;
}
