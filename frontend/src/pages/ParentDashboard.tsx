import { PersistentNotifications } from '../components/PersistentNotifications';
import { useEffect, useState } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { MapPin, CheckCircle2, Circle, AlertTriangle, Map, ShieldCheck, Camera, Lock, Video, LogOut, X, History, ChevronRight, PhoneCall, PhoneOff, Users, Bell, ArrowLeft, Siren } from 'lucide-react';
import { TripHistoryPanel } from '../components/TripHistoryPanel';
import { EmergencyCallPanel } from '../components/EmergencyCallPanel';
import { BrandLogo } from '../components/BrandLogo';

export function ParentDashboard() {
  const { students, vehicles, parentChildId, notifications, safetyState, setRole, emergency, vehicleCall, startVehicleCall, endVehicleCall, tripState } = useAppContext();
  const [showMap, setShowMap] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [notificationVisible, setNotificationVisible] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [readNotificationIds, setReadNotificationIds] = useState<Set<string>>(() => new Set());
  const [showEmergencyCalls, setShowEmergencyCalls] = useState(false);

  const child = students.find((s) => s.id === parentChildId);
  const parentNotifications = notifications.filter((notification) =>
    (notification.role === 'PARENT' || notification.role === 'ALL') &&
    (notification.studentId ? notification.studentId === parentChildId : notification.vehicleId === child?.assignedVehicle)
  );
  const latestParentNotification = parentNotifications[0];
  const unreadCount = parentNotifications.filter((notification) => !readNotificationIds.has(notification.id)).length;

  const openNotifications = () => {
    setShowNotifications(true);
    setNotificationVisible(false);
    setReadNotificationIds(new Set(parentNotifications.map((notification) => notification.id)));
  };

  useEffect(() => {
    if (!latestParentNotification) return;
    setNotificationVisible(true);
    if (latestParentNotification.type === 'error' || latestParentNotification.persistent) return;
    const timer = window.setTimeout(() => setNotificationVisible(false), 7000);
    return () => window.clearTimeout(timer);
  }, [latestParentNotification?.id, latestParentNotification?.type, latestParentNotification?.persistent]);

  if (!child) return null;

  const isBoarded = child.status === 'BOARDED' || child.status === 'DROPPED_OFF';
  const isDroppedOff = child.status === 'DROPPED_OFF';
  const childOnVehicle = child.status === 'BOARDED';
  const onboardCount = students.filter((student) => student.assignedVehicle === child.assignedVehicle && student.status === 'BOARDED').length;
  const vehicleCapacity = vehicles.find((vehicle) => vehicle.id === child.assignedVehicle)?.capacity || 0;
  const tripLabel = tripState === 'AFTERNOON' ? 'Afternoon drop-off' : 'Morning pickup';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col max-w-md mx-auto shadow-xl relative">
      {latestParentNotification && notificationVisible &&
      <div className={`absolute top-3 left-3 right-3 z-[110] rounded-2xl border shadow-2xl p-4 flex gap-3 animate-in slide-in-from-top duration-300 ${
        latestParentNotification.type === 'error' ? 'bg-red-50 border-red-200' :
        latestParentNotification.type === 'warning' ? 'bg-amber-50 border-amber-200' :
        latestParentNotification.type === 'success' ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'}`}>
        <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
          latestParentNotification.type === 'error' ? 'bg-red-100 text-red-600' :
          latestParentNotification.type === 'warning' ? 'bg-amber-100 text-amber-600' :
          latestParentNotification.type === 'success' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'}`}>
          {latestParentNotification.type === 'error' || latestParentNotification.type === 'warning' ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-wide font-bold text-slate-500">{latestParentNotification.studentId ? `${child.name} update` : `${child.assignedVehicle} update`}</p>
          <p className="text-sm font-semibold text-slate-800 mt-0.5">{latestParentNotification.message}</p>
          <p className="text-xs text-slate-500 mt-1">{latestParentNotification.time} · {latestParentNotification.type === 'error' || latestParentNotification.persistent ? 'Red alert remains until dismissed' : 'Hides automatically'}</p>
        </div>
        <button onClick={() => setNotificationVisible(false)} aria-label="Dismiss notification" className="p-1 h-fit text-slate-400 hover:text-slate-600"><X size={16} /></button>
      </div>}
      <header className="bg-white p-6 pb-8 rounded-b-3xl shadow-sm border-b border-slate-200 z-10">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <BrandLogo className="w-11 h-11 rounded-xl shadow-sm" decorative />
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-slate-800 truncate">Good Morning, Kamal</h1>
              <p className="text-slate-500 text-sm mt-1">SafeRide-LK · Parent portal</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowEmergencyCalls(true)} aria-label="Emergency calls" className="p-2.5 rounded-full bg-red-100 text-red-600 hover:bg-red-200 transition-colors"><Siren size={18} /></button>
            <button onClick={openNotifications} aria-label="Open notifications" className="relative p-2.5 rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 transition-colors">
              <Bell size={18} />
              {unreadCount > 0 && <span className="absolute -top-1 -right-1 min-w-[19px] h-[19px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center border-2 border-white">{unreadCount > 9 ? '9+' : unreadCount}</span>}
            </button>
            <button onClick={() => setRole(null)} aria-label="Switch role" className="p-2.5 rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 transition-colors"><LogOut size={18} /></button>
          </div>
        </div>

        <button onClick={() => setShowHistory(true)} className="w-full text-left bg-[#176B87] rounded-2xl p-5 text-white shadow-lg relative overflow-hidden hover:bg-[#12546b] transition-colors group">
          <ShieldCheck size={100} className="absolute -top-2 -right-2 opacity-10" />
          <p className="text-blue-100 text-sm font-medium mb-1">Child</p>
          <h2 className="text-2xl font-bold mb-1">{child.name}</h2>
          <p className="text-blue-100 text-sm">Grade {child.grade} · {child.school}</p>
          <span className="mt-4 pt-3 border-t border-white/15 flex items-center justify-between text-sm font-semibold">
            <span className="flex items-center gap-2"><History size={16} /> View trip history</span>
            <ChevronRight size={18} className="group-hover:translate-x-0.5 transition-transform" />
          </span>
        </button>
      </header>

      <main className="flex-1 p-5 -mt-4 space-y-6 overflow-y-auto">

        {emergency.active && emergency.driverPhase !== 'SAFE' && emergency.stage !== 'NONE' &&
        <section className="bg-red-600 text-white rounded-2xl p-5 shadow-lg">
            <h3 className="font-bold flex items-center gap-2 mb-1"><AlertTriangle size={18} /> Emergency on {child.assignedVehicle}</h3>
            <p className="text-red-100 text-sm">Responders dispatched · stage {emergency.stage.replace(/_/g, ' ')}</p>
          </section>
        }

        <section className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-bold text-slate-800 text-lg">Current trip</h3>
              <p className="text-[#176B87] font-medium text-sm flex items-center gap-1.5 mt-1">
                <span className="w-2 h-2 rounded-full bg-[#176B87] animate-pulse" />
                {child.assignedVehicle} trip active
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">School ETA</p>
              <p className="text-xl font-bold text-slate-800">07:43 AM</p>
            </div>
          </div>

          <div className="flex items-center gap-3 mb-5 bg-slate-50 p-3 rounded-xl border border-slate-100">
            <span className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center shrink-0"><MapPin size={16} /></span>
            <div>
              <p className="text-xs text-slate-500">Current location</p>
              <p className="font-medium text-slate-800">Battaramulla</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button onClick={() => setShowMap(true)} className="py-3 bg-slate-800 text-white rounded-xl font-semibold shadow-md hover:bg-slate-700 transition-colors flex items-center justify-center gap-2"><Map size={18} /> Live Map</button>
            {vehicleCall?.vehicleId === child.assignedVehicle && vehicleCall.callerRole === 'PARENT' ?
              <button onClick={() => endVehicleCall('Parent ended the call')} className="py-3 bg-red-600 text-white rounded-xl font-semibold flex items-center justify-center gap-2"><PhoneOff size={18} /> {vehicleCall.status === 'RINGING' ? 'Cancel call' : 'End call'}</button> :
              <button onClick={() => startVehicleCall(child.assignedVehicle, 'PARENT', child.parentName, child.name)} disabled={Boolean(vehicleCall)} className="py-3 bg-green-600 disabled:bg-slate-300 text-white rounded-xl font-semibold flex items-center justify-center gap-2"><PhoneCall size={18} /> Call Vehicle</button>}
          </div>
          {vehicleCall?.vehicleId === child.assignedVehicle && vehicleCall.callerRole === 'PARENT' && <p className="text-center mt-2 text-xs font-semibold text-slate-500">{vehicleCall.status === 'RINGING' ? 'Calling driver…' : 'Connected to driver'}</p>}
        </section>

        <section className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
          <h3 className="font-bold text-slate-800 mb-6">Trip progress</h3>
          <ol className="space-y-6 relative before:absolute before:inset-0 before:ml-[11px] before:-translate-x-px before:h-full before:w-0.5 before:bg-slate-100">
            <TimelineItem completed title="Vehicle assigned" desc={child.assignedVehicle} />
            <TimelineItem completed={isBoarded} active={!isBoarded} title="Student picked up" desc={isBoarded ? '07:08 AM' : 'Pending'} />
            <TimelineItem completed={isDroppedOff} active={isBoarded && !isDroppedOff} title="Travelling" desc="En route to school" />
            <TimelineItem completed={isDroppedOff} title="School reached" desc={isDroppedOff ? '07:43 AM' : 'Pending'} />
            <TimelineItem completed={isDroppedOff} title="Driver confirmed" desc={isDroppedOff ? 'Destination verified' : 'Pending'} />
          </ol>
        </section>

        <section className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2"><Camera size={18} className="text-[#176B87]" /> Live camera</h3>
            <span className={`px-2 py-1 rounded-full text-[10px] font-bold ${childOnVehicle ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>{childOnVehicle ? 'AUTO LIVE' : 'OFF'}</span>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="p-3 rounded-xl bg-blue-50 border border-blue-100"><p className="text-xs text-blue-600 flex items-center gap-1"><Users size={13} /> People onboard</p><p className="text-2xl font-bold text-blue-800 mt-1">{onboardCount} <span className="text-sm font-medium text-blue-500">/ {vehicleCapacity}</span></p></div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-100"><p className="text-xs text-slate-500">Current service</p><p className="text-sm font-bold text-slate-800 mt-2">{tripLabel}</p></div>
          </div>

          <div className="bg-slate-900 rounded-xl overflow-hidden relative flex flex-col items-center justify-center border border-slate-800 p-6 text-center min-h-[170px]">
            {!childOnVehicle &&
            <>
                <span className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mb-3 text-slate-500"><Lock size={24} /></span>
                <p className="text-white font-semibold mb-1">Camera not active</p>
                <p className="text-slate-400 text-xs">The live view starts automatically after {child.name} boards and closes after check-out.</p>
              </>
            }

            {childOnVehicle &&
            <div className="absolute inset-0 bg-slate-800 flex flex-col">
                <div className="p-2 bg-black/50 flex justify-between items-center text-[10px] font-mono text-white">
                  <span className="flex items-center gap-1 text-red-400 font-bold"><span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" /> LIVE</span>
                  <span className="text-slate-300">{child.assignedVehicle} · {onboardCount} onboard</span>
                </div>
                <div className="flex-1 flex items-center justify-center relative">
                  <Video size={32} className="text-slate-600" />
                  <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #000 2px, #000 4px)' }} />
                  <p className="absolute bottom-2 text-[10px] text-slate-400">{tripLabel} · Prototype simulated camera stream</p>
                </div>
                <div className="p-2 bg-black/50 text-[10px] text-slate-400 text-left leading-tight">
                  Authorized parent: {child.parentName} · Assigned student: {child.name} · Risk: {safetyState.level}
                </div>
              </div>
            }
          </div>
        </section>

      </main>

      {showMap &&
      <div className="absolute inset-0 z-50 flex flex-col bg-slate-50 animate-in slide-in-from-bottom duration-200">
          <div className="p-4 flex justify-between items-center bg-white border-b border-slate-200">
            <div>
              <h3 className="font-bold text-slate-800">Live map · {child.assignedVehicle}</h3>
              <p className="text-xs text-slate-400">Simulated GPS position</p>
            </div>
            <button onClick={() => setShowMap(false)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"><X size={18} /></button>
          </div>
          <div className="flex-1 relative bg-slate-100">
            <div className="absolute inset-0 opacity-25" style={{ backgroundImage: 'radial-gradient(#94a3b8 1px, transparent 1px)', backgroundSize: '22px 22px' }} />
            <div className="absolute top-[30%] left-[24%] flex flex-col items-center">
              <span className="w-3 h-3 rounded-full bg-slate-400 ring-4 ring-slate-300/40" />
              <span className="text-[11px] text-slate-500 mt-1">Battaramulla</span>
            </div>
            <div className="absolute top-[34%] left-[40%] flex flex-col items-center transition-all duration-1000">
              <span className="bg-[#176B87] text-white p-2 rounded-full shadow-lg"><Map size={16} /></span>
              <span className="mt-1 text-xs font-bold bg-white px-2 py-0.5 rounded shadow-sm">{child.assignedVehicle}</span>
            </div>
            <div className="absolute top-[64%] left-[62%] flex flex-col items-center">
              <span className="w-3 h-3 rounded-full bg-[#176B87] ring-4 ring-[#176B87]/20" />
              <span className="text-[11px] text-slate-600 mt-1 font-medium">{child.school}</span>
            </div>
          </div>
          <div className="p-4 bg-white border-t border-slate-200 flex justify-between text-sm">
            <span className="text-slate-500">Arriving at {child.school}</span>
            <span className="font-bold text-slate-800">07:43 AM</span>
          </div>
        </div>
      }
      {showHistory && <TripHistoryPanel student={child} onClose={() => setShowHistory(false)} mode="page" />}
      {showNotifications && <ParentNotificationsPage notifications={parentNotifications} childName={child.name} vehicleId={child.assignedVehicle} onClose={() => setShowNotifications(false)} />}
      {showEmergencyCalls && <EmergencyCallPanel context={`${child.name} · ${child.assignedVehicle}`} onClose={() => setShowEmergencyCalls(false)} />}
    </div>);

}

function ParentNotificationsPage({ notifications, childName, vehicleId, onClose }: {notifications: ReturnType<typeof useAppContext>['notifications'];childName: string;vehicleId: string;onClose: () => void}) {
  return (
    <div className="absolute inset-0 z-[100] bg-slate-50 flex flex-col animate-in slide-in-from-right duration-200">
      <header className="bg-white border-b border-slate-200 p-5 flex items-center gap-3 shrink-0">
        <button onClick={onClose} aria-label="Back to parent dashboard" className="p-2 -ml-2 rounded-lg text-slate-500 hover:bg-slate-100"><ArrowLeft size={20} /></button>
        <div><h2 className="text-lg font-bold text-slate-800">Notifications</h2><p className="text-xs text-slate-500">{childName} · {vehicleId}</p></div>
      </header>
      <main className="flex-1 overflow-y-auto p-5">
        <PersistentNotifications recipient="parent" />
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">Separate demonstration updates ({notifications.length})</p>
        <div className="space-y-3">
          {notifications.map((notification) => <ParentNotificationCard key={notification.id} notification={notification} childName={childName} vehicleId={vehicleId} />)}
          {notifications.length === 0 && <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center"><Bell size={32} className="mx-auto text-slate-300 mb-3" /><p className="font-semibold text-slate-700">No notifications yet</p><p className="text-sm text-slate-400 mt-1">Child and vehicle updates will appear here.</p></div>}
        </div>
      </main>
    </div>
  );
}

function ParentNotificationCard({ notification, childName, vehicleId }: {notification: ReturnType<typeof useAppContext>['notifications'][number];childName: string;vehicleId: string}) {
  const tone = notification.type === 'error' ? 'bg-red-50 border-red-100 text-red-600' : notification.type === 'warning' ? 'bg-amber-50 border-amber-100 text-amber-600' : notification.type === 'success' ? 'bg-green-50 border-green-100 text-green-600' : 'bg-blue-50 border-blue-100 text-blue-600';
  return <article className={`rounded-xl border p-4 flex gap-3 ${tone}`}><span className="mt-0.5 shrink-0">{notification.type === 'error' || notification.type === 'warning' ? <AlertTriangle size={19} /> : <CheckCircle2 size={19} />}</span><div className="min-w-0"><p className="text-[10px] font-bold uppercase tracking-wide opacity-70">{notification.studentId ? `${childName} update` : `${vehicleId} update`}</p><p className="text-sm font-semibold text-slate-800 mt-1">{notification.message}</p><p className="text-xs text-slate-500 mt-1.5">{notification.time}</p></div></article>;
}

function TimelineItem({ active, completed, title, desc }: {active?: boolean;completed?: boolean;title: string;desc: string;}) {
  return (
    <li className="relative flex items-start gap-4">
      <span className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 z-10 border-2 ${
      completed ? 'bg-green-500 border-green-500 text-white' :
      active ? 'bg-white border-blue-500 text-blue-500' :
      'bg-white border-slate-200 text-slate-300'}`
      }>
        {completed ? <CheckCircle2 size={14} /> : <Circle size={10} className={active ? 'fill-current' : ''} />}
      </span>
      <span className="pt-0.5">
        <span className={`font-semibold text-sm block ${active || completed ? 'text-slate-800' : 'text-slate-400'}`}>{title}</span>
        <span className="text-xs text-slate-500">{desc}</span>
      </span>
    </li>);

}
