import { useEffect,useState } from 'react';
import { apiFetch,StoredRoute } from '../services/api';
import { LocationPicker,LocationDraft } from '../components/LocationPicker';
import { DriverStoredRoute } from '../components/DriverStoredRoute';
import { ResearchEvaluation } from '../components/ResearchEvaluation';
type Landmark={name:string;place_address:string;stopping_address:string;instruction:string};
type Account={id:string;username:string;role:string;active:boolean;demo_only:boolean;vehicle_ids:string[]};
type SavedReview=NonNullable<StoredRoute['research_journey']>&{reason:string;separate_people_confirmed:boolean;adults_only_confirmed:boolean;pins:Record<string,{latitude:number;longitude:number;manually_confirmed:boolean;permitted_public_stop:boolean;stopping_note:string;reviewed_address:string;location_method:LocationDraft['method']}>};
export function AdultResearch(){
 const [template,setTemplate]=useState<{vehicle_id:string;landmarks:Record<string,Landmark>}|null>(null),[accounts,setAccounts]=useState<Account[]>([]);
 const [pins,setPins]=useState<Record<string,LocationDraft>>({}),[allowed,setAllowed]=useState<Record<string,boolean>>({}),[notes,setNotes]=useState<Record<string,string>>({});
 const [date,setDate]=useState('2026-10-19'),[departure,setDeparture]=useState('18:00'),[mode,setMode]=useState(''),[driver,setDriver]=useState(''),[operator,setOperator]=useState('');
 const [separate,setSeparate]=useState(false),[adults,setAdults]=useState(false),[reason,setReason]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false),[saved,setSaved]=useState<StoredRoute|null>(null),[open,setOpen]=useState(false);
 const [reuseInfo,setReuseInfo]=useState('');
 async function reuseReview(){
  if(!template)return;
  setSaving(true);setError('');setReuseInfo('');
  try{
   const result=await apiFetch<{published_route:StoredRoute|null;trip:{trip_id:string;state:string}|null}>(`/research-routes/current?vehicle_id=${encodeURIComponent(template.vehicle_id)}&service_date=${encodeURIComponent(date)}`);
   const route=result.published_route;
   if(!route)throw new Error('No saved research review exists for this date.');
   if(route.execution_status!=='pre_trip')throw new Error('Only an unused pre-trip review may be reused here. Active/completed snapshots remain unchanged.');
   const review=route.research_journey as SavedReview|undefined;
   if(!review?.pins||!['A','B','C'].every(k=>review.pins[k]))throw new Error('This older snapshot lacks reusable pin review; inspect it before preparing a replacement.');
   setPins(Object.fromEntries(Object.entries(review.pins).map(([k,p])=>[k,{address:p.reviewed_address||p.stopping_note,latitude:String(p.latitude),longitude:String(p.longitude),confirmed:p.manually_confirmed,method:p.location_method}])));
   setAllowed(Object.fromEntries(Object.entries(review.pins).map(([k,p])=>[k,p.permitted_public_stop])));
   setNotes(Object.fromEntries(Object.entries(review.pins).map(([k,p])=>[k,p.stopping_note])));
   setMode(review.travel_mode);setDriver(review.driver_id);setOperator(review.operator_id);setSeparate(review.separate_people_confirmed);setAdults(review.adults_only_confirmed);setReason(review.reason);
   setDeparture(`${String(Math.floor(route.departure_seconds/3600)).padStart(2,'0')}:${String(Math.floor(route.departure_seconds%3600/60)).padStart(2,'0')}`);
   setReuseInfo(`Loaded version ${route.version}: confirmed pins, order, travel mode, people and review notes. ${result.trip?`Trip ${result.trip.trip_id}: ${result.trip.state}.`:''} Cancel the unused PLANNED trip deliberately in the research driver/operator view before saving a replacement. Choose a future departure below. Nothing has been changed on the server.`);
  }catch(e){setError(e instanceof Error?e.message:'Could not load saved review.');}finally{setSaving(false);}
 }
 useEffect(()=>{const c=new AbortController();Promise.all([apiFetch<{vehicle_id:string;landmarks:Record<string,Landmark>}>('/research-routes/template',c.signal),apiFetch<Account[]>('/auth/admin/accounts',c.signal)]).then(([t,a])=>{setTemplate(t);setAccounts(a);setPins(Object.fromEntries(Object.entries(t.landmarks).map(([key,l])=>[key,{address:l.stopping_address||l.place_address,latitude:'',longitude:'',confirmed:false,method:'manual'}])));}).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[]);
 async function save(){setSaving(true);setError('');try{const [h,m]=departure.split(':').map(Number);const r=await apiFetch<StoredRoute>('/research-routes',undefined,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service_date:date,departure_seconds:h*3600+m*60,travel_mode:mode,driver_id:driver,operator_id:operator,separate_people_confirmed:separate,adults_only_confirmed:adults,reason,
  pins:Object.fromEntries(Object.entries(pins).map(([key,p])=>[key,{latitude:Number(p.latitude),longitude:Number(p.longitude),manually_confirmed:p.confirmed,permitted_public_stop:!!allowed[key],stopping_note:notes[key]||'',reviewed_address:p.address,location_method:p.method}]))})});setSaved(r);}catch(e){setError(e instanceof Error?e.message:'Preparation failed.');}finally{setSaving(false);}}
 if(open&&template)return <div className="relative h-[calc(100dvh-10rem)] min-h-96"><DriverStoredRoute initialPurpose="research" initialServiceDate={date} vehicleId={template.vehicle_id} direction="afternoon" onVehicleChange={()=>{}} onDirectionChange={()=>{}} onBack={()=>setOpen(false)}/></div>;
 const ready=template&&mode&&driver&&operator&&driver!==operator&&adults&&separate&&reason.length>=10&&Object.keys(pins).length===3&&Object.entries(pins).every(([key,p])=>p.confirmed&&p.latitude.trim()&&p.longitude.trim()&&allowed[key]&&(notes[key]||'').length>=10);
 return <section aria-label="Isolated adult research preparation" className="max-w-4xl mx-auto space-y-4">
  <h1 className="text-2xl font-bold text-[#176B87]">Adult research — A → B → C → A</h1>
  <p className="bg-amber-50 border rounded p-3 text-sm">Adult-only research, no student roster, boarding or school windows. Fixed supplied order; no optimization claim. School routes remain separate. No automatic paid lookup, trip start or observation acceptance.</p>
  {error&&<p role="alert" className="text-red-700">{error}</p>}
  <p>Vehicle: {template?.vehicle_id??'Loading authorized vehicle...'}</p>
  <button disabled={!template||saving} onClick={()=>void reuseReview()} className="underline text-[#176B87] disabled:opacity-40">Reuse saved research review for selected date</button>
  {reuseInfo&&<p role="status" className="bg-blue-50 border rounded p-3 text-sm break-words">{reuseInfo}</p>}
  <div className="grid sm:grid-cols-2 gap-3"><label>Research service date<input className="border rounded p-2 w-full" type="date" value={date} onChange={e=>setDate(e.target.value)}/></label><label>Research departure (Asia/Colombo)<input className="border rounded p-2 w-full" type="time" value={departure} onChange={e=>setDeparture(e.target.value)}/></label></div>
  <p className="text-xs">Choose a future departure if preparation finishes later. Starts use actual server time; more than 10 minutes late requires a newly reviewed departure version before starting.</p>
  <label className="block">Research travel mode<select aria-label="Research travel mode" className="border rounded p-2 w-full" value={mode} onChange={e=>setMode(e.target.value)}><option value="">Select actual travel mode — required</option><option value="driving">Driving</option><option value="walking">Walking (not a vehicle travel-time label)</option><option value="bicycling">Bicycling (not a vehicle travel-time label)</option></select></label>
  <label className="block">Assigned research driver<select aria-label="Assigned research driver" className="border rounded p-2 w-full" value={driver} onChange={e=>setDriver(e.target.value)}><option value="">Select existing assigned driver</option>{accounts.filter(a=>a.active&&!a.demo_only&&a.role==='driver'&&a.vehicle_ids.includes(template?.vehicle_id??'')).map(a=><option key={a.id} value={a.id}>{a.username}</option>)}</select></label>
  <label className="block">Separate phone operator (existing administrator)<select aria-label="Separate phone operator (existing administrator)" className="border rounded p-2 w-full" value={operator} onChange={e=>setOperator(e.target.value)}><option value="">Select existing administrator/operator</option>{accounts.filter(a=>a.active&&!a.demo_only&&a.role==='administrator').map(a=><option key={a.id} value={a.id}>{a.username}</option>)}</select></label>
  <label className="block"><input type="checkbox" checked={separate} onChange={e=>setSeparate(e.target.checked)}/> I confirm the operator and driver are separate people while moving.</label>
  <label className="block"><input type="checkbox" checked={adults} onChange={e=>setAdults(e.target.checked)}/> Consenting adults only; no student transport.</label>
  {template&&Object.entries(template.landmarks).map(([key,l])=><section key={key} aria-label={`Research stopping point ${key}`} className="border bg-white rounded-xl p-4 space-y-3">
   <h2 className="font-bold">{key}: {l.name}{key==='A'?' — occurrences 1 and 4':''}</h2><p className="text-sm">Supplied place address: {l.place_address}</p>{l.stopping_address&&<p className="text-sm">Separately supplied stopping-point address: {l.stopping_address}</p>}
   <p className="font-semibold text-sm text-amber-900">{l.instruction}</p><p className="text-xs">Supplied addresses above are preserved. A lookup result is only a suggestion and never substitutes for manual stopping-pin review.</p>
   {pins[key]&&<LocationPicker home={false} landmarkTest value={pins[key]} onChange={p=>{setPins(prev=>({...prev,[key]:p}));setAllowed(prev=>({...prev,[key]:false}));}}/>}
   <label className="block text-sm"><input type="checkbox" checked={!!allowed[key]} onChange={e=>setAllowed(prev=>({...prev,[key]:e.target.checked}))}/> I manually reviewed this accessible, permitted public stopping point{key==='B'?', outside the electrical facility':''}.</label>
   <label className="block">Stopping-point review note<textarea className="border rounded p-2 w-full" value={notes[key]||''} onChange={e=>setNotes(prev=>({...prev,[key]:e.target.value}))}/></label>
  </section>)}
  <label className="block">Research route review reason<textarea className="border rounded p-2 w-full" value={reason} onChange={e=>setReason(e.target.value)}/></label>
  <button disabled={!ready||saving} onClick={()=>void save()} className="bg-[#176B87] text-white rounded px-4 py-3 disabled:opacity-40">{saving?'Saving reviewed route...':'Save reviewed research route'}</button>
  {saved&&<p className="text-sm break-all">Saved {saved.route_id} / version {saved.version}. No trip was started. Departure {new Date(saved.departure).toLocaleString('en-GB',{timeZone:'Asia/Colombo'})}. Travel durations/ETAs unavailable; no provider was called.</p>}
  <button disabled={!template} onClick={()=>setOpen(true)} className="block underline text-[#176B87]">Open research driver/operator view</button>
  <p className="text-sm">After creating a PLANNED research trip: Access → Authorize adult landmark phone test; Evaluation → Prepare collection for planned trip; then Start trip. Only the selected separate operator may enroll the phone. Keep Chrome foregrounded; use a second navigation device.</p>
  <ResearchEvaluation />
 </section>;
}
