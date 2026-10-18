import { FormEvent,useEffect,useState } from 'react';
import { apiFetch,fetchVehicles,fetchStudents,VehicleRecord,StudentRecord } from '../services/api';
interface Account{id:string;username:string;role:string;active:boolean;demo_only:boolean;vehicle_ids:string[];student_ids:string[]}
export function AccountAccess(){
  const [accounts,setAccounts]=useState<Account[]>([]),[vehicles,setVehicles]=useState<VehicleRecord[]>([]),[students,setStudents]=useState<StudentRecord[]>([]),[revision,setRevision]=useState(0);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[saving,setSaving]=useState(false),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('driver'),[demoOnly,setDemoOnly]=useState(false),[selected,setSelected]=useState(''),[ids,setIds]=useState<string[]>([]);
  const account=accounts.find(a=>a.id===selected);
  useEffect(()=>{const controller=new AbortController();setError('');Promise.all([apiFetch<Account[]>('/auth/admin/accounts',controller.signal),fetchVehicles(controller.signal),fetchStudents(controller.signal)])
    .then(([a,v,s])=>{setAccounts(a);setVehicles(v);setStudents(s);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();},[revision]);
  async function run(action:()=>Promise<unknown>,message:string){setSaving(true);setError('');setNotice('');try{await action();setNotice(message);setRevision(n=>n+1);}catch(e){setError(e instanceof Error?e.message:'Access change failed.');}finally{setSaving(false);}}
  function create(event:FormEvent){event.preventDefault();void run(async()=>{await apiFetch('/auth/admin/accounts',undefined,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,role,password,demo_only:demoOnly})});setPassword('');setUsername('');},'Account created. Password is not displayed or stored by the UI.');}
  return <section className="bg-white border rounded-xl p-5 space-y-5 max-w-4xl"><h1 className="font-bold text-xl">Accounts and access</h1>
    {error&&<p role="alert" className="text-red-700">{error}</p>}{notice&&<p role="status" className="text-[#176B87]">{notice}</p>}
    <form onSubmit={create} className="grid gap-3 sm:grid-cols-2"><label>New username<input required pattern="[a-z0-9_.@-]{3,100}" autoComplete="off" value={username} onChange={e=>setUsername(e.target.value)} className="border rounded p-2 w-full"/></label>
      <label>Initial password (private)<input type="password" required minLength={12} autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} className="border rounded p-2 w-full"/></label>
      <label>Account role<select value={role} onChange={e=>setRole(e.target.value)} className="border rounded p-2 w-full"><option value="administrator">Administrator</option><option value="driver">Driver</option><option value="parent">Parent</option></select></label>
      <label className="flex gap-2 items-center"><input type="checkbox" checked={demoOnly} onChange={e=>setDemoOnly(e.target.checked)}/>Restrict account to synthetic demo sessions</label>
      <button disabled={saving} className="bg-[#176B87] text-white rounded p-2">Create account</button></form>
    <h2 className="font-semibold">Assign vehicle or student access</h2>
    <select aria-label="Manage account" value={selected} onChange={e=>{const a=accounts.find(v=>v.id===e.target.value);setSelected(e.target.value);setIds(a?.role==='driver'?a.vehicle_ids:a?.student_ids??[]);}} className="border rounded p-2 w-full"><option value="">Select an account</option>{accounts.map(a=><option value={a.id} key={a.id}>{a.username} / {a.role} / {a.active?'Active':'Locked'}</option>)}</select>
    {account&&<div className="space-y-3">{account.role!=='administrator'&&<><select multiple aria-label="Authorized relationships" value={ids} onChange={e=>setIds(Array.from(e.target.selectedOptions,o=>o.value))} className="border rounded p-2 w-full min-h-32">
      {(account.role==='driver'?vehicles.map(v=>({id:v.id,name:v.id})):students.map(s=>({id:s.id,name:s.name}))).map(row=><option key={row.id} value={row.id}>{row.name} / {row.id}</option>)}
      </select><button disabled={saving} onClick={()=>void run(()=>apiFetch(`/auth/admin/accounts/${account.id}/${account.role==='driver'?'vehicles':'students'}`,undefined,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})}),'Relationships saved; account login and tracking sessions revoked.')} className="bg-[#176B87] text-white rounded p-2">Save assignments and revoke old sessions</button></>}
      <button disabled={saving} onClick={()=>void run(()=>apiFetch(`/auth/admin/accounts/${account.id}/revoke`,undefined,{method:'POST'}),'All account sessions revoked.')} className="block text-red-700 underline">Revoke all login/tracking sessions</button></div>}
    <p className="text-xs text-slate-500">Accounts do not inherit a role from the role selector. Password reset/disable is available through the private local administrator CLI. Reassigning requires a new login.</p>
  </section>;
}
