import { useState } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { AlertTriangle, MapPin, Users, Activity, CheckCircle2, LogOut, Camera, Video, Lock, Eye, Phone, UserCircle } from 'lucide-react';
import { BrandLogo } from '../components/BrandLogo';

const RESPONDER_PROFILES = {
  EMS: { name: 'Dr. Anjali Perera', title: 'Emergency Medical Officer', id: 'SLMC-28491', unit: '1990 Suwa Seriya · Unit EMS-14', phone: '1990' },
  POLICE: { name: 'Inspector R. Wijesinghe', title: 'Traffic Police Incident Lead', id: 'POL-5742', unit: 'Kaduwela Police Station', phone: '119' },
  FIRE: { name: 'Station Officer M. Silva', title: 'Fire & Rescue Commander', id: 'FR-2081', unit: 'Colombo Fire Brigade · Rescue 03', phone: '110' },
  HOSPITAL: { name: 'Dr. N. Fernando', title: 'Trauma Team Coordinator', id: 'HSP-TR-118', unit: 'National Hospital Emergency Unit', phone: '011-2691111' }
};

export function EmergencyResponderDashboard({ role }: {role: 'EMS' | 'POLICE' | 'FIRE' | 'HOSPITAL';}) {
  const { emergency, acknowledgeStage, setRole, addNotification } = useAppContext();
  const { active, crashData, stage } = emergency;
  const [cameraViewing, setCameraViewing] = useState(false);
  const profile = RESPONDER_PROFILES[role];

  if (!active || stage === 'NONE') {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6 relative">
        <button
          onClick={() => setRole(null)}
          className="absolute top-6 right-6 px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-sm font-medium hover:bg-slate-700 transition-colors flex items-center gap-2">
          
          <LogOut size={16} /> Switch role
        </button>
        <div className="text-center text-slate-500">
          <BrandLogo className="w-20 h-20 mx-auto mb-5 rounded-2xl opacity-90" />
          <Activity size={48} className="mx-auto mb-4 opacity-50" />
          <h2 className="text-2xl font-bold mb-2">SafeRide-LK {role} Portal</h2>
          <p>Standing by — no active dispatch. Trigger a crash from the Demo Control Center.</p>
        </div>
      </div>);

  }

  const handleAck = () => {
    acknowledgeStage(role);
  };

  const isAcked =
  role === 'EMS' && (stage === 'POLICE_NOTIFIED' || stage === 'FIRE_NOTIFIED' || stage === 'HOSPITAL_NOTIFIED' || stage === 'HOSPITAL_ACK') ||
  role === 'POLICE' && (stage === 'FIRE_NOTIFIED' || stage === 'HOSPITAL_NOTIFIED' || stage === 'HOSPITAL_ACK') ||
  role === 'FIRE' && (stage === 'HOSPITAL_NOTIFIED' || stage === 'HOSPITAL_ACK') ||
  role === 'HOSPITAL' && stage === 'HOSPITAL_ACK';

  const isMyTurn =
  role === 'EMS' && stage === 'EMS_NOTIFIED' ||
  role === 'POLICE' && stage === 'POLICE_NOTIFIED' ||
  role === 'FIRE' && stage === 'FIRE_NOTIFIED' ||
  role === 'HOSPITAL' && stage === 'HOSPITAL_NOTIFIED';
  const cameraAuthorized = isMyTurn || isAcked;

  const openCamera = () => {
    if (!cameraAuthorized) return;
    setCameraViewing(true);
    addNotification({ role: 'ADMIN', message: `${role} responder ${profile.name} opened the secure BUS-01 incident camera.`, type: 'warning', vehicleId: 'BUS-01' });
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-200 p-6 md:p-12 font-sans">
      <div className="max-w-4xl mx-auto">
        
        <header className="flex justify-between items-center mb-8 border-b border-slate-800 pb-6">
          <div className="flex items-center gap-4">
            <BrandLogo className="w-14 h-14 rounded-2xl" decorative />
            <div>
              <h1 className="text-2xl font-bold text-white">{role} DISPATCH DASHBOARD</h1>
              <p className="text-slate-400">SafeRide-LK Emergency Network</p>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-sm text-slate-500">Incident ID</p>
              <p className="font-mono text-white font-bold">{emergency.incidentId}</p>
            </div>
            <button
              onClick={() => setRole(null)}
              className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-sm font-medium hover:bg-slate-700 transition-colors flex items-center gap-2">
              
              <LogOut size={16} /> Switch role
            </button>
          </div>
        </header>

        <section className="mb-6 bg-slate-800 rounded-xl border border-slate-700 p-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <span className="w-14 h-14 rounded-full bg-slate-700 text-slate-300 flex items-center justify-center shrink-0"><UserCircle size={30} /></span>
          <div className="flex-1"><p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Assigned responder profile</p><h2 className="font-bold text-white text-lg">{profile.name}</h2><p className="text-sm text-slate-400">{profile.title} · {profile.id}</p><p className="text-xs text-slate-500 mt-1">{profile.unit}</p></div>
          <a href={`tel:${profile.phone}`} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-semibold flex items-center justify-center gap-2"><Phone size={16} /> {profile.phone}</a>
        </section>

        <div className="bg-slate-800 rounded-2xl overflow-hidden border border-slate-700 shadow-2xl">
          <div className="bg-red-600 p-6 text-white flex items-center gap-4">
            <AlertTriangle size={32} className="animate-pulse" />
            <div>
              <h2 className="text-2xl font-bold tracking-wide">CRITICAL INCIDENT • BUS-01</h2>
              <p className="text-red-200 font-medium">School Bus Crash • {crashData?.classification} Severity</p>
            </div>
          </div>

          <div className="p-8 grid grid-cols-1 md:grid-cols-2 gap-8">
            
            <div className="space-y-6">
              <div className="bg-slate-900 p-5 rounded-xl border border-slate-700">
                <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
                  <MapPin size={16} /> Location Details
                </h3>
                <p className="text-xl font-bold text-white mb-1">{crashData?.location}</p>
                <p className="text-slate-400">Coordinates: 6.9044° N, 79.9547° E</p>
                {role === 'EMS' && <p className="text-amber-400 font-bold mt-3">ETA: 8 min</p>}
                {role === 'POLICE' && <p className="text-amber-400 font-bold mt-3">Traffic Impact: High • Suggested Diversion: Route B</p>}
              </div>

              <div className="bg-slate-900 p-5 rounded-xl border border-slate-700">
                <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
                  <Users size={16} /> Occupant Status
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-500 text-sm">Total Passengers</p>
                    <p className="text-2xl font-bold text-white">8</p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-sm">Estimated Injured</p>
                    <p className="text-2xl font-bold text-red-400">3</p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-sm">Critical</p>
                    <p className="text-xl font-bold text-red-500">1</p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-sm">Moderate</p>
                    <p className="text-xl font-bold text-amber-500">2</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
                <div className="p-4 border-b border-slate-700 flex justify-between items-center"><h3 className="text-slate-300 text-sm font-bold uppercase tracking-wider flex items-center gap-2"><Camera size={16} /> Secure Incident Camera</h3>{cameraAuthorized && <span className="text-[10px] font-bold px-2 py-1 rounded-full bg-green-900/40 text-green-400">AUTHORIZED</span>}</div>
                <div className="h-52 relative flex items-center justify-center bg-black/40 text-center p-5">
                  {!cameraAuthorized && <div><Lock size={32} className="mx-auto text-slate-600 mb-3" /><p className="font-semibold text-slate-400">Camera access locked</p><p className="text-xs text-slate-600 mt-1">Unlocks when {role} is notified.</p></div>}
                  {cameraAuthorized && !cameraViewing && <div><Eye size={34} className="mx-auto text-blue-400 mb-3" /><p className="text-white font-semibold mb-1">Incident live view available</p><p className="text-xs text-slate-500 mb-4">Access is logged and restricted to this active incident.</p><button onClick={openCamera} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-bold">Open live camera</button></div>}
                  {cameraAuthorized && cameraViewing && <div className="absolute inset-0 bg-slate-800 flex flex-col"><div className="px-3 py-2 bg-black/60 flex justify-between text-[10px] font-mono"><span className="text-red-400 font-bold flex items-center gap-1"><span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" /> LIVE</span><span>BUS-01 · {emergency.incidentId}</span></div><div className="flex-1 relative flex items-center justify-center"><Video size={40} className="text-slate-600" /><div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #000 2px, #000 4px)' }} /></div><div className="px-3 py-2 bg-black/60 flex justify-between items-center text-[10px] text-slate-400"><span>{role} · {profile.id} · Audit active</span><button onClick={() => setCameraViewing(false)} className="text-white bg-slate-700 px-2 py-1 rounded">Close view</button></div></div>}
                </div>
              </div>

              {role === 'FIRE' &&
              <div className="bg-orange-900/20 p-5 rounded-xl border border-orange-700/50">
                  <h3 className="text-orange-400 text-sm font-bold uppercase tracking-wider mb-3">Extraction Assessment</h3>
                  <p className="text-white mb-2">Vehicle Roll: <span className="font-bold text-orange-400">{crashData?.vehicleRoll}°</span></p>
                  <p className="text-white mb-2">Rollover: <span className="font-bold text-orange-400">Possible</span></p>
                  <p className="text-white mb-2">Extraction Risk: <span className="font-bold text-red-400">High</span></p>
                  <p className="text-white">Possible trapped occupants: <span className="font-bold text-red-400">2</span></p>
                </div>
              }

              {role === 'HOSPITAL' &&
              <div className="bg-rose-900/20 p-5 rounded-xl border border-rose-700/50">
                  <h3 className="text-rose-400 text-sm font-bold uppercase tracking-wider mb-3">Hospital Preparation</h3>
                  <p className="text-white mb-2">Incoming Ambulance ETA: <span className="font-bold text-rose-400">11 min</span></p>
                  <ul className="text-slate-300 space-y-2 mt-4 list-disc list-inside pl-2">
                    <li>Trauma Team Activation Required</li>
                    <li>Emergency Bed Allocation (3)</li>
                    <li>Pediatric Support Required</li>
                  </ul>
                </div>
              }

              <div className="pt-4">
                {isAcked ?
                <div className="w-full py-4 bg-green-900/30 border border-green-700 text-green-400 rounded-xl font-bold text-lg flex items-center justify-center gap-2">
                    <CheckCircle2 size={24} /> ACKNOWLEDGED & DISPATCHED
                  </div> :
                isMyTurn ?
                <button
                  onClick={handleAck}
                  className="w-full py-4 bg-red-600 hover:bg-red-500 text-white rounded-xl font-bold text-lg shadow-lg transition-colors animate-pulse">
                  
                    {role === 'HOSPITAL' ? '[ACKNOWLEDGE & PREPARE]' : '[ACKNOWLEDGE INCIDENT]'}
                  </button> :

                <div className="w-full py-4 bg-slate-800 border border-slate-700 text-slate-500 rounded-xl font-bold text-lg flex items-center justify-center text-center">
                    Awaiting prior stage acknowledgement...
                  </div>
                }
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>);

}
