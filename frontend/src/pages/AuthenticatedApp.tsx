import { CalendarDays, MapPin, Bell, Settings, FlaskConical } from 'lucide-react';
import { ResearchEvaluation } from '../components/ResearchEvaluation';
import { ModelEvaluation } from '../components/ModelEvaluation';
import { FormEvent,useEffect,useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useAppContext } from '../contexts/AppContext';
import { BrandLogo } from '../components/BrandLogo';
import { DriverStoredRoute } from '../components/DriverStoredRoute';
import { PersistentNotifications } from '../components/PersistentNotifications';
import { OperationsFleet } from '../components/OperationsFleet';
import { AccountAccess } from '../components/AccountAccess';
import { RouteOptimization } from './RouteOptimization';
import { StudentsPage } from './StudentsPage';
import { DailyPlan } from './DailyPlan';
import { AdultResearch } from './AdultResearch';
import { apiFetch,RouteDirection } from '../services/api';

function Login(){
  const auth=useAuth();const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[mode,setMode]=useState('real'),[error,setError]=useState(''),[saving,setSaving]=useState(false);
  async function submit(event:FormEvent){event.preventDefault();setSaving(true);setError('');try{await auth.login(username,password,mode);setPassword('');}catch(e){setError(e instanceof Error?e.message:'Login failed.');}finally{setSaving(false);}}
  return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-6"><form onSubmit={submit} className="bg-white border rounded-2xl p-8 w-full max-w-md space-y-5 shadow-sm">
    <BrandLogo className="w-20 h-20 mx-auto"/><h1 className="text-2xl font-bold text-[#176B87]">SafeRide-LK login</h1>
    <label className="block">Username<input autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)} className="border rounded p-2 w-full"/></label>
    <label className="block">Password<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} className="border rounded p-2 w-full"/></label>
    <label className="block">Workspace<select value={mode} onChange={e=>setMode(e.target.value)} className="border rounded p-2 w-full"><option value="real">Authenticated operations</option><option value="demo">Authenticated synthetic demo</option></select></label>
    {(error||auth.error)&&<p role="alert" className="text-red-700">{error||auth.error}</p>}
    <button disabled={saving} className="bg-[#176B87] text-white rounded p-3 w-full disabled:opacity-50">{saving?'Signing in…':'Sign in'}</button>
    <p className="text-xs text-slate-500">Accounts and access are assigned by an administrator. No role-selector or anonymous demo bypass.</p>
  </form></main>;
}

function ParentView(){
  const {user}=useAuth();const [student,setStudent]=useState(user?.student_ids[0]??''),[data,setData]=useState<{name:string;school_name:string;vehicle_id:string;note:string;input_source:string;active:boolean}|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  useEffect(()=>{const controller=new AbortController();setData(null);setError('');setLoading(!!student);if(student)apiFetch<typeof data>(`/parent/students/${encodeURIComponent(student)}`,controller.signal).then(value=>{if(!controller.signal.aborted)setData(value);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[student]);
  return <main className="max-w-3xl mx-auto p-6 space-y-4"><h1 className="text-2xl font-bold">Your linked students</h1>
    <select aria-label="Linked student" value={student} onChange={e=>setStudent(e.target.value)} className="border rounded p-2">{user?.student_ids.map(id=><option key={id}>{id}</option>)}</select>
    {!student&&<p>No student is linked to this account. Contact the administrator.</p>}{error&&<p role="alert" className="text-red-700">{error}</p>}
    {loading&&<p role="status">Loading linked registration...</p>}
    {data&&<section className="bg-white border rounded-xl p-4"><h2 className="font-bold">{data.name}</h2><p>{data.school_name} · {data.vehicle_id}</p><p>Registration input: {data.input_source??'Unavailable'} / {data.active?'Active':'Inactive'}</p><p className="text-sm text-slate-500">{data.note}</p></section>}
    <p className="text-sm text-slate-500">Live position, speed, route/trip IDs, ETA and pickup countdown: Unavailable in this permitted parent summary. No demonstration values are substituted.</p>
    <PersistentNotifications recipient="parent" allowedStudentIds={user?.student_ids??[]}/>
  </main>;
}

export function AuthenticatedApp({demo}:{demo:React.ReactNode}){
  const auth=useAuth();const {setRole}=useAppContext();const [tab,setTab]=useState('Daily Plan'),[vehicle,setVehicle]=useState(''),[direction,setDirection]=useState<RouteDirection>('morning'),[error,setError]=useState('');
  useEffect(()=>{setRole(null);setVehicle(auth.user?.vehicle_ids[0]??'');},[auth.user?.id,auth.user?.mode,setRole]);
  if(auth.loading)return <p className="p-8">Checking authenticated session…</p>;
  if(!auth.user)return <Login/>;
  const user=auth.user;
  const navigation=[{label:'Daily Plan',icon:CalendarDays},{label:'Live Tracking',icon:MapPin},{label:'Alerts',icon:Bell},{label:'Setup',icon:Settings},{label:'Research & Testing',icon:FlaskConical}];
  return <div className={user.mode==='real'&&user.role==='driver'?'h-dvh min-h-0 flex flex-col overflow-hidden bg-slate-50':'min-h-screen bg-slate-50'}><header className="shrink-0 bg-[#176B87] text-white px-5 py-3 flex flex-wrap gap-3 items-center relative z-[100]">
    <span className="flex-1">{user.username} · {user.role} · {user.mode==='demo'?'SYNTHETIC DEMO':'Authenticated operations'}</span>
    <button className="border rounded px-3 py-1" onClick={()=>{setError('');void auth.logout().catch(e=>setError(e.message));}}>Log out</button>
  </header>{user.mode==='real'&&<p className="shrink-0 px-5 py-2 text-xs text-slate-500 border-b bg-white">{user.role==='driver'?'Authenticated routing / unrelated teammate features: Not connected.':'Cabin safety, camera, RFID and emergency teammate features: Not connected. Synthetic component demonstrations are available only in the separate authenticated simulation workspace.'}</p>}{error&&<p role="alert" className="p-3 text-red-700">Logout failed: {error}. Server authorization has not been confirmed revoked; retry.</p>}
    {user.mode==='demo'?demo:user.role==='administrator'?<>
      <div className="md:flex min-h-[calc(100vh-5rem)]">
        <aside className="md:w-60 shrink-0 bg-white border-b md:border-r border-slate-200"><div className="hidden md:flex items-center gap-3 p-6"><BrandLogo className="w-12 h-12 rounded-xl"/><div><p className="font-bold text-[#176B87]">SafeRide-LK</p><p className="text-xs text-slate-500">Routing workspace</p></div></div>
        <nav aria-label="Administrator workspace" className="grid grid-cols-2 md:flex md:flex-col gap-1 p-3">{navigation.map(({label,icon:Icon})=><button key={label} aria-current={tab===label?'page':undefined} onClick={()=>setTab(label)} className={`flex min-w-0 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-left ${label==='Research & Testing'?'col-span-2 border-t md:mt-3':''} ${tab===label?'bg-[#176B87] text-white shadow-sm':'text-slate-600 hover:bg-slate-50'}`}><Icon size={18}/>{label}</button>)}</nav></aside>
        <main className="flex-1 min-w-0 p-4 md:p-7 bg-[#F7F9FC]">{tab==='Daily Plan'?<DailyPlan/>:tab==='Live Tracking'?<OperationsFleet/>:tab==='Alerts'?<><h1 className="text-2xl font-bold text-[#176B87] mb-4">Alerts</h1><PersistentNotifications recipient="admin"/></>:tab==='Setup'?<SetupWorkspace/>:<ResearchWorkspace/>}</main>
      </div>
    </>:user.role==='driver'?<div className="relative flex-1 min-h-0"><DriverStoredRoute vehicleId={vehicle} direction={direction} onVehicleChange={setVehicle} onDirectionChange={setDirection} onBack={()=>{void auth.logout().catch(e=>setError(e.message));}}/></div>:<ParentView/>}
  </div>;
}

function SetupWorkspace(){
 const [section,setSection]=useState('Access');
 return <section className="space-y-5"><div><h1 className="text-2xl font-bold text-[#176B87]">Setup</h1><p className="text-sm text-slate-500">Authorized assignments and transport records. Hasara integration remains provisional.</p></div><nav aria-label="Setup sections" className="flex gap-2">{['Access','Students'].map(label=><button key={label} aria-pressed={section===label} onClick={()=>setSection(label)} className={`px-4 py-2 rounded-lg ${section===label?'bg-[#176B87] text-white':'bg-white border'}`}>{label}</button>)}</nav>{section==='Access'?<AccountAccess/>:<StudentsPage/>}</section>;
}
function ResearchWorkspace(){
 const [section,setSection]=useState('Adult research');
 return <section className="space-y-5"><div><h1 className="text-2xl font-bold text-[#176B87]">Research & Testing</h1><p className="text-sm text-amber-800">Separate adult research, synthetic testing and provisional integration tools. Not student-trip evidence.</p></div><nav aria-label="Research sections" className="flex flex-wrap gap-2">{['Adult research','School test tools','Evaluation','Routes'].map(label=><button key={label} aria-pressed={section===label} onClick={()=>setSection(label)} className={`px-4 py-2 rounded-lg ${section===label?'bg-[#176B87] text-white':'bg-white border'}`}>{label}</button>)}</nav>{section==='Adult research'?<AdultResearch/>:section==='School test tools'?<DailyPlan researchTools/>:section==='Evaluation'?<><ModelEvaluation/><ResearchEvaluation/></>:<RouteOptimization/>}</section>;
}
