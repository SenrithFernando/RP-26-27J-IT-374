import { WorkspaceHeader } from '../components/WorkspaceHeader';
import { OperationsOverview } from './OperationsOverview';
import { CalendarDays, MapPin, Bell, Settings, LayoutDashboard, Shield, Camera, CreditCard, AlertTriangle } from 'lucide-react';
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
  const auth=useAuth();const {setRole}=useAppContext();
  const [tab,setTab]=useState('Overview'),[vehicle,setVehicle]=useState(''),[direction,setDirection]=useState<RouteDirection>('morning'),[error,setError]=useState(''),[menu,setMenu]=useState(false);
  useEffect(()=>{setRole(null);setVehicle(auth.user?.vehicle_ids[0]??'');},[auth.user?.id,auth.user?.mode,setRole]);
  if(auth.loading)return <p role="status" className="p-8">Checking session...</p>;
  if(!auth.user)return <Login/>;
  const user=auth.user;
  const logout=()=>{setError('');void auth.logout().catch(e=>setError(e.message));};
  const failure=error&&<p role="alert" className="bg-red-50 p-3 text-sm text-red-700">Logout failed: {error}. Retry logout.</p>;
  if(user.mode==='demo')return <>{failure}<div className="bg-amber-50 p-2 text-xs flex justify-between">Synthetic demo workspace<button onClick={logout}>Log out</button></div>{demo}</>;
  if(user.role==='driver')return <div className="h-dvh flex flex-col bg-[#F7F9FC]">{failure}<div className="relative flex-1 min-h-0"><DriverStoredRoute accountName={user.username} vehicleId={vehicle} direction={direction} onVehicleChange={setVehicle} onDirectionChange={setDirection} onBack={logout}/></div></div>;
  if(user.role!=='administrator')return <><WorkspaceHeader title="SafeRide-LK" username={user.username} onLogout={logout}/>{failure}<ParentView/></>;
  const navigation=[{label:'Overview',icon:LayoutDashboard},{label:'Daily Plan',icon:CalendarDays},{label:'Live Fleet',icon:MapPin},{label:'Notifications',icon:Bell},{label:'Settings',icon:Settings}];
  const date=new Date().toLocaleDateString('en-GB',{timeZone:'Asia/Colombo',weekday:'long',day:'numeric',month:'long',year:'numeric'});
  return <div className="flex min-h-screen bg-[#F7F9FC]">
    {menu&&<button aria-label="Close navigation backdrop" className="fixed inset-0 z-[1900] bg-slate-900/40 md:hidden" onClick={()=>setMenu(false)}/>}
    <aside className={`${menu?'flex':'hidden'} md:flex fixed md:sticky top-0 left-0 z-[2000] md:z-30 w-64 h-dvh shrink-0 flex-col bg-white border-r border-slate-200`}>
      <div className="p-6 border-b border-slate-100 flex items-center gap-3"><BrandLogo className="h-12 w-12 rounded-xl shadow-sm"/><div><p className="text-xl font-bold text-[#176B87] leading-tight">SafeRide-LK</p><p className="text-[11px] text-slate-500 mt-1">School transport routing</p></div></div>
      <nav aria-label="Administrator workspace" className="flex-1 overflow-y-auto py-4"><ul className="space-y-1 px-3">{navigation.map(({label,icon:Icon})=><li key={label}><button aria-current={tab===label?'page':undefined} onClick={()=>{setTab(label);setMenu(false);}} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${tab===label?'bg-[#176B87] text-white':'text-slate-600 hover:bg-slate-50 hover:text-[#176B87]'}`}><Icon size={18}/>{label}</button></li>)}</ul>
      <div className="mx-3 mt-6 border-t pt-4 space-y-1">{[{label:'Safety',icon:Shield},{label:'Camera',icon:Camera},{label:'RFID',icon:CreditCard},{label:'Emergency',icon:AlertTriangle}].map(({label,icon:Icon})=><button key={label} disabled className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-400"><Icon size={18}/><span className="flex-1 text-left">{label}</span><span className="text-[10px]">Not connected</span></button>)}</div></nav>
    </aside>
    <div className="flex-1 flex flex-col min-w-0"><WorkspaceHeader title={tab} subtitle={date} username={user.username} onLogout={logout} onMenu={()=>setMenu(!menu)}/>{failure}
      <main className="flex-1 p-4 md:p-8 min-w-0">{tab==='Overview'?<OperationsOverview onPlan={()=>setTab('Daily Plan')} onAlerts={()=>setTab('Notifications')}/>:tab==='Daily Plan'?<DailyPlan/>:tab==='Live Fleet'?<OperationsFleet/>:tab==='Notifications'?<PersistentNotifications recipient="admin"/>:<SetupWorkspace/>}</main>
    </div>
  </div>;
}

function SetupWorkspace(){
 const [section,setSection]=useState('Access');const [toolsOpen,setToolsOpen]=useState(false);
 return <section className="space-y-5"><div><h1 className="text-2xl font-bold text-[#176B87]">Settings</h1><p className="text-sm text-slate-500">Authorized assignments and transport records. Hasara integration remains provisional.</p></div><nav aria-label="Settings sections" className="flex gap-2">{['Access','Students'].map(label=><button key={label} aria-pressed={section===label} onClick={()=>setSection(label)} className={`px-4 py-2 rounded-lg ${section===label?'bg-[#176B87] text-white':'bg-white border'}`}>{label}</button>)}</nav><details className="bg-white border rounded-xl p-4" onToggle={event=>setToolsOpen(event.currentTarget.open)}><summary className="cursor-pointer font-semibold text-[#176B87]">Administrator tools</summary>{toolsOpen&&<ResearchWorkspace/>}</details>{section==='Access'?<AccountAccess/>:<StudentsPage/>}</section>;
}
function ResearchWorkspace(){
 const [section,setSection]=useState('Evaluation');
 return <section className="space-y-5"><div><h1 className="text-2xl font-bold text-[#176B87]">Research and evaluation tools</h1><p className="text-sm text-amber-800">Separate adult research, synthetic testing and provisional integration tools. Not student-trip evidence.</p></div><nav aria-label="Research sections" className="flex flex-wrap gap-2">{['Adult research','School test tools','Evaluation','Routes'].map(label=><button key={label} aria-pressed={section===label} onClick={()=>setSection(label)} className={`px-4 py-2 rounded-lg ${section===label?'bg-[#176B87] text-white':'bg-white border'}`}>{label}</button>)}</nav>{section==='Adult research'?<AdultResearch/>:section==='School test tools'?<DailyPlan researchTools/>:section==='Evaluation'?<><ModelEvaluation/><ResearchEvaluation/></>:<RouteOptimization/>}</section>;
}
