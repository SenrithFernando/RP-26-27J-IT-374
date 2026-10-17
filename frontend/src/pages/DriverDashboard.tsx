import { useEffect, useRef, useState } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { CheckCircle2, Circle, AlertTriangle, MapPin, ShieldCheck, Clock, Phone, ShieldAlert, LogOut, SkipForward, XCircle, Route, PhoneIncoming, PhoneCall, PhoneOff, Siren } from 'lucide-react';
import { EmergencyCallPanel } from '../components/EmergencyCallPanel';
import { BrandLogo } from '../components/BrandLogo';
import { DriverStoredRoute } from '../components/DriverStoredRoute';
import type { RouteDirection } from '../services/api';

export function DriverDashboard() {
  const {
    students, setStudents, driverVehicleId,
    recentScan, setRecentScan,
    wrongVehicleAttempt, setWrongVehicleAttempt,
    geofenceReached, setGeofenceReached,
    addNotification,
    pickupWindow, setPickupWindow,
    emergency, resolveDriverSafe, driverRequestHelp,
    safetyState, routeState,
    setRole,
    vehicleCall, answerVehicleCall, endVehicleCall
  } = useAppContext();

  const [toast, setToast] = useState<string | null>(null);
  const [showRoute, setShowRoute] = useState(false);
  const [routeVehicleId, setRouteVehicleId] = useState('');
  const [routeDirection, setRouteDirection] = useState<RouteDirection>('morning');
  const [criticalAlertOpen, setCriticalAlertOpen] = useState(false);
  const [showEmergencyCalls, setShowEmergencyCalls] = useState(false);
  const alertAudioRef = useRef<{ context: AudioContext; timer: number } | null>(null);
  const callAudioRef = useRef<{ context: AudioContext; timer: number } | null>(null);

  useEffect(() => {
    const incoming = vehicleCall?.vehicleId === driverVehicleId && vehicleCall.status === 'RINGING';
    if (!incoming) return;
    if ('vibrate' in navigator) navigator.vibrate([300, 250, 300, 900]);
    const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const context = new AudioContextClass();
    const ring = () => {
      if (context.state === 'suspended') void context.resume();
      [660, 880].forEach((frequency, index) => {
        const oscillator = context.createOscillator(); const gain = context.createGain();
        oscillator.frequency.value = frequency; gain.gain.value = 0.12;
        oscillator.connect(gain); gain.connect(context.destination);
        oscillator.start(context.currentTime + index * 0.18); oscillator.stop(context.currentTime + index * 0.18 + 0.16);
      });
    };
    ring();
    const timer = window.setInterval(ring, 1800);
    callAudioRef.current = { context, timer };
    return () => { window.clearInterval(timer); void context.close(); callAudioRef.current = null; if ('vibrate' in navigator) navigator.vibrate(0); };
  }, [vehicleCall?.id, vehicleCall?.status, vehicleCall?.vehicleId, driverVehicleId]);

  useEffect(() => {
    const isCriticalEvent = safetyState.level === 'HIGH' || safetyState.level === 'CRITICAL';
    if (!isCriticalEvent) {
      setCriticalAlertOpen(false);
      return;
    }

    setCriticalAlertOpen(true);
    if ('vibrate' in navigator) navigator.vibrate([500, 200, 500, 200, 800]);

    const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass || alertAudioRef.current) return;
    const context = new AudioContextClass();
    const beep = () => {
      if (context.state === 'suspended') void context.resume();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'square';
      oscillator.frequency.setValueAtTime(880, context.currentTime);
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.22, context.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.35);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.36);
    };
    beep();
    const timer = window.setInterval(beep, 850);
    alertAudioRef.current = { context, timer };

    return () => {
      window.clearInterval(timer);
      void context.close();
      alertAudioRef.current = null;
      if ('vibrate' in navigator) navigator.vibrate(0);
    };
  }, [safetyState.level, safetyState.score]);

  const acknowledgeCriticalAlert = () => {
    setCriticalAlertOpen(false);
    if (alertAudioRef.current) {
      window.clearInterval(alertAudioRef.current.timer);
      void alertAudioRef.current.context.close();
      alertAudioRef.current = null;
    }
    if ('vibrate' in navigator) navigator.vibrate(0);
    addNotification({ role: 'ADMIN', message: `Driver acknowledged ${safetyState.level} cabin safety alert on ${driverVehicleId}.`, type: 'warning' });
    showToast('Safety alert acknowledged — drive with caution');
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  const vehicleStudents = students.filter((s) => s.assignedVehicle === driverVehicleId);
  const boardedCount = vehicleStudents.filter((s) => s.status === 'BOARDED' || s.status === 'DROPPED_OFF').length;
  const nextStudent = vehicleStudents.find((s) => s.status === 'PLANNED');
  const primaryRisk = getPrimaryRisk(safetyState);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const simulateScan = () => {
    if (!nextStudent) {
      showToast('All students already verified');
      return;
    }
    setStudents(students.map((s) => s.id === nextStudent.id ? { ...s, status: 'BOARDED' } : s));
    setRecentScan(nextStudent);
    addNotification({ role: 'PARENT', message: `${nextStudent.name} boarded ${driverVehicleId}.`, type: 'success', studentId: nextStudent.id, vehicleId: driverVehicleId });
    addNotification({ role: 'ADMIN', message: `${nextStudent.name} verified via RFID on ${driverVehicleId}.`, type: 'success' });
    setTimeout(() => setRecentScan(null), 2600);
  };

  const markWindowStudentBoarded = () => {
    setStudents(students.map((s) => s.id === pickupWindow.studentId ? { ...s, status: 'BOARDED' } : s));
    setPickupWindow((prev) => ({ ...prev, expired: false, remainingSeconds: 0 }));
    addNotification({ role: 'PARENT', message: `${pickupWindow.studentName} boarded ${driverVehicleId}.`, type: 'success', studentId: pickupWindow.studentId, vehicleId: driverVehicleId });
    addNotification({ role: 'ADMIN', message: `${pickupWindow.studentName} boarded at Stop ${pickupWindow.stopNumber}.`, type: 'success' });
    showToast(`${pickupWindow.studentName} marked boarded`);
  };

  const skipStop = () => {
    addNotification({ role: 'ADMIN', message: `Driver skipped Stop ${pickupWindow.stopNumber} (${pickupWindow.studentName}).`, type: 'warning' });
    addNotification({ role: 'PARENT', message: `Stop skipped — ${pickupWindow.studentName} was not collected.`, type: 'warning', studentId: pickupWindow.studentId, vehicleId: driverVehicleId });
    setPickupWindow((prev) => ({ ...prev, expired: false, remainingSeconds: 0 }));
    showToast('Stop skipped — admin notified');
  };

  const markMissed = () => {
    setStudents(students.map((s) => s.id === pickupWindow.studentId ? { ...s, status: 'MISSED' } : s));
    addNotification({ role: 'ADMIN', message: `${pickupWindow.studentName} marked as missed pickup.`, type: 'error' });
    addNotification({ role: 'PARENT', message: `${pickupWindow.studentName} was recorded as a missed pickup.`, type: 'error', studentId: pickupWindow.studentId, vehicleId: driverVehicleId });
    setPickupWindow((prev) => ({ ...prev, expired: false, remainingSeconds: 0 }));
    showToast('Missed pickup recorded');
  };

  const callParent = () => {
    addNotification({ role: 'ADMIN', message: `Driver called the parent of ${pickupWindow.studentName}.`, type: 'info' });
    showToast(`Calling parent of ${pickupWindow.studentName}…`);
  };

  const contactAdmin = () => {
    addNotification({ role: 'ADMIN', message: `Driver escalated a wrong-vehicle scan for ${wrongVehicleAttempt?.studentName}.`, type: 'error' });
    setWrongVehicleAttempt(null);
    showToast('Admin contacted');
  };

  const confirmDropOff = (studentId: string) => {
    const student = students.find((s) => s.id === studentId);
    setStudents(students.map((s) => s.id === studentId ? { ...s, status: 'DROPPED_OFF' } : s));
    if (student) {
      addNotification({ role: 'PARENT', message: `${student.name} safely arrived at ${student.school}.`, type: 'success', studentId: student.id, vehicleId: driverVehicleId });
      addNotification({ role: 'ADMIN', message: `Destination verified for ${student.name}.`, type: 'success' });
    }
  };

  const confirmAll = () => {
    const pending = vehicleStudents.filter((s) => s.status === 'BOARDED');
    setStudents(students.map((s) => s.assignedVehicle === driverVehicleId && s.status === 'BOARDED' ? { ...s, status: 'DROPPED_OFF' } : s));
    pending.forEach((s) => addNotification({ role: 'PARENT', message: `${s.name} safely arrived at ${s.school}.`, type: 'success', studentId: s.id, vehicleId: driverVehicleId }));
    addNotification({ role: 'ADMIN', message: `Destination verification complete for ${pending.length} student(s).`, type: 'success' });
    setTimeout(() => setGeofenceReached(false), 900);
  };

  const pendingAtSchool = vehicleStudents.filter((s) => s.status === 'BOARDED' && s.school === 'Horizon College');

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col max-w-md mx-auto shadow-xl relative overflow-hidden">
      <header className="bg-[#176B87] text-white p-5 pb-6 rounded-b-2xl shadow-md z-10">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <BrandLogo className="w-11 h-11 rounded-xl shadow-sm" decorative />
            <div className="min-w-0">
              <h1 className="text-xl font-bold truncate">{driverVehicleId} Morning Trip</h1>
              <p className="text-blue-100 text-xs mt-0.5">Cabin / pickup demo · {vehicleStudents.length} demo students</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="bg-white/20 px-3 py-1 rounded-full text-sm font-medium">{boardedCount} / {vehicleStudents.length}</span>
            <button onClick={() => setShowEmergencyCalls(true)} aria-label="Emergency calls" className="p-2 rounded-full bg-red-500 text-white hover:bg-red-400 transition-colors shadow-sm"><Siren size={16} /></button>
            <button onClick={() => setRole(null)} aria-label="Switch role" className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
        <div className="bg-white/10 rounded-xl p-4 flex items-center gap-3">
          <span className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center shrink-0"><MapPin size={20} /></span>
          <div className="min-w-0 flex-1">
            <p className="text-blue-100 text-sm">Next Stop</p>
            <p className="font-semibold text-lg truncate">
              {nextStudent ? nextStudent.name : 'All students collected'}
              {nextStudent && <span className="text-blue-200 text-sm font-normal ml-2">ETA 07:08</span>}
            </p>
          </div>
          <button onClick={() => setShowRoute(true)} className="shrink-0 px-3 py-2 bg-white text-[#176B87] rounded-lg text-sm font-semibold flex items-center gap-1.5 hover:bg-blue-50 transition-colors">
            <Route size={16} /> Route
          </button>
        </div>
      </header>

      <main className="flex-1 p-5 overflow-y-auto space-y-6">

        {safetyState.level !== 'LOW' &&
        <div className={`rounded-xl p-4 border flex items-start gap-3 ${
        safetyState.level === 'MODERATE' ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-red-50 border-red-200 text-red-800'}`
        }>
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <div>
              <p className="font-bold text-sm">Cabin risk {safetyState.level} · score {safetyState.score}</p>
              <p className="text-xs mt-0.5"><strong>{primaryRisk.title}:</strong> {primaryRisk.detail}</p>
            </div>
          </div>
        }

        {routeState.deviationAlert &&
        <div className="rounded-xl p-4 border bg-red-50 border-red-200 text-red-800 flex items-start gap-3">
            <MapPin size={18} className="mt-0.5 shrink-0" />
            <div>
              <p className="font-bold text-sm">Route deviation</p>
              <p className="text-xs mt-0.5">{routeState.deviationAlert.distanceFromRoute} km off {routeState.deviationAlert.expectedRoute}</p>
            </div>
          </div>
        }

        {pickupWindow.expired ?
        <section className="bg-red-50 border border-red-200 rounded-xl p-4">
            <h2 className="flex items-center gap-2 text-red-700 font-bold mb-2 text-sm">
              <AlertTriangle size={18} /> PICKUP WINDOW EXPIRED
            </h2>
            <p className="text-red-900 font-medium">{pickupWindow.studentName}</p>
            <p className="text-red-800 text-sm mb-4">Status: Not boarded</p>
            <div className="flex gap-3">
              <button onClick={callParent} className="flex-1 py-2 bg-white border border-red-200 text-red-700 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 hover:bg-red-100 transition-colors">
                <Phone size={16} /> Call Parent
              </button>
              <button onClick={markMissed} className="flex-1 py-2 bg-red-600 text-white rounded-lg font-semibold text-sm hover:bg-red-700 transition-colors flex items-center justify-center gap-2">
                <XCircle size={16} /> Mark Missed
              </button>
            </div>
          </section> :

        <section className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <h2 className="text-blue-900 font-bold mb-1 text-sm">STOP {pickupWindow.stopNumber} · {pickupWindow.studentName}</h2>
            <div className="flex justify-between text-xs text-blue-800 mb-3">
              <span>Scheduled {pickupWindow.scheduledTime}</span>
              <span>Window {pickupWindow.windowStart}–{pickupWindow.windowEnd}</span>
            </div>
            <div className="flex items-center justify-between bg-white rounded-lg p-3 border border-blue-100 mb-4">
              <span className="text-slate-500 text-sm font-medium flex items-center gap-2"><Clock size={16} /> Remaining</span>
              <span className="font-mono font-bold text-lg text-blue-600 tabular-nums">{formatTime(pickupWindow.remainingSeconds)}</span>
            </div>
            <div className="flex gap-2">
              <button onClick={markWindowStudentBoarded} className="flex-1 py-2 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 transition-colors">
                Student Boarded
              </button>
              <button onClick={callParent} aria-label="Call parent" className="px-3 py-2 bg-white border border-blue-200 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors">
                <Phone size={18} />
              </button>
              <button onClick={skipStop} aria-label="Skip stop" className="px-3 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
                <SkipForward size={18} />
              </button>
            </div>
          </section>
        }

        <section>
          <h2 className="font-semibold text-slate-800 mb-3">Student Checklist</h2>
          <ul className="bg-white rounded-xl shadow-sm border border-slate-200 divide-y divide-slate-100 overflow-hidden">
            {vehicleStudents.map((student) =>
            <li key={student.id} className="p-4 flex items-center justify-between">
                <div>
                  <p className={`font-medium ${student.status === 'PLANNED' ? 'text-slate-800' : student.status === 'MISSED' ? 'text-red-600' : 'text-slate-500 line-through'}`}>
                    {student.name}
                  </p>
                  <p className="text-xs text-slate-400">{student.school}</p>
                </div>
                {student.status === 'MISSED' ? <XCircle className="text-red-500" size={22} /> :
              student.status === 'PLANNED' ? <Circle className="text-slate-300" size={22} /> :
              <CheckCircle2 className="text-green-500" size={22} />}
              </li>
            )}
          </ul>
        </section>

        <button
          onClick={simulateScan}
          className="w-full py-4 bg-slate-800 text-white rounded-xl font-semibold shadow-md hover:bg-slate-700 transition-colors flex items-center justify-center gap-2">
          
          <ShieldCheck size={20} /> Simulate RFID Scan
        </button>
      </main>

      {toast &&
      <div className="absolute bottom-6 left-5 right-5 bg-slate-900 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-lg z-[60] animate-in fade-in slide-in-from-bottom-2 duration-200">
          {toast}
        </div>
      }

      {showRoute && <DriverStoredRoute
        vehicleId={routeVehicleId} direction={routeDirection}
        onVehicleChange={setRouteVehicleId} onDirectionChange={setRouteDirection}
        onBack={() => setShowRoute(false)} />}

      {emergency.active && emergency.driverPhase === 'COUNTDOWN' &&
      <div className="absolute inset-0 bg-red-900/95 backdrop-blur-md z-[100] flex flex-col items-center justify-center p-6 text-center animate-in fade-in duration-200">
          <span className="w-24 h-24 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mb-6 animate-pulse">
            <ShieldAlert size={48} />
          </span>
          <h2 className="text-3xl font-bold text-white mb-2">POSSIBLE CRASH DETECTED</h2>
          <p className="text-red-200 mb-8">Emergency escalation begins in:</p>
          <p className="text-7xl font-mono font-bold text-white mb-12 tabular-nums">
            00:{emergency.driverCountdown.toString().padStart(2, '0')}
          </p>
          <div className="w-full space-y-4 max-w-sm">
            <button onClick={resolveDriverSafe} className="w-full py-4 bg-white text-red-900 rounded-xl font-bold text-lg shadow-lg hover:bg-red-50 transition-colors">
              I'M SAFE — CANCEL
            </button>
            <button onClick={driverRequestHelp} className="w-full py-4 bg-red-600 border-2 border-red-400 text-white rounded-xl font-bold text-lg shadow-lg hover:bg-red-500 transition-colors">
              REQUEST HELP NOW
            </button>
          </div>
        </div>
      }

      {criticalAlertOpen && !(emergency.active && emergency.driverPhase === 'COUNTDOWN') &&
      <div className="absolute inset-0 bg-red-950/95 backdrop-blur-md z-[95] flex flex-col items-center justify-center p-6 text-center animate-in fade-in duration-200">
        <div className="absolute inset-0 border-[8px] border-red-500/60 animate-pulse pointer-events-none" />
        <span className="w-24 h-24 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mb-6 animate-pulse">
          <AlertTriangle size={52} />
        </span>
        <p className="text-red-300 text-sm font-bold tracking-[0.2em] mb-2">SAFETY EVENT DETECTED</p>
        <h2 className="text-4xl font-black text-white mb-3">{safetyState.level} ALERT</h2>
        <p className="text-white text-xl font-bold mb-2">{primaryRisk.title}</p>
        <p className="text-red-200 text-sm mb-3">{primaryRisk.detail}</p>
        <p className="text-red-100 font-semibold text-lg mb-2">Cabin risk score {safetyState.score} / 100</p>
        <div className="w-full max-w-sm bg-black/25 border border-red-400/25 rounded-xl p-4 text-left text-sm text-red-100 space-y-2 mb-8">
          {safetyState.sensors.standing !== 'None' && <p><strong>Standing:</strong> {safetyState.sensors.standing} · {safetyState.sensors.standingDuration}s</p>}
          <p><strong>Door density:</strong> {safetyState.sensors.doorDensity}</p>
          <p><strong>Occupancy:</strong> {safetyState.sensors.occupancy} passengers</p>
          <p><strong>Speed:</strong> {safetyState.sensors.speed} km/h</p>
        </div>
        <p className="text-red-300 text-sm mb-4">Reduce speed and stop safely if required.</p>
        <button onClick={acknowledgeCriticalAlert} className="w-full max-w-sm py-4 bg-white text-red-800 rounded-xl font-black text-lg shadow-xl hover:bg-red-50 transition-colors">
          ACKNOWLEDGE ALERT
        </button>
      </div>}

      {vehicleCall?.vehicleId === driverVehicleId && vehicleCall.status === 'RINGING' && !criticalAlertOpen && !(emergency.active && emergency.driverPhase === 'COUNTDOWN') &&
      <div className="absolute inset-0 z-[90] bg-slate-900/95 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center">
        <span className="w-24 h-24 rounded-full bg-green-500/20 text-green-400 flex items-center justify-center mb-6 animate-pulse"><PhoneIncoming size={48} /></span>
        <p className="text-slate-400 text-sm uppercase tracking-widest mb-2">Incoming vehicle call</p>
        <h2 className="text-3xl font-bold text-white mb-2">{vehicleCall.callerName}</h2>
        <p className="text-slate-300">{vehicleCall.callerRole === 'ADMIN' ? 'Transport Administrator' : 'Parent / Guardian'} · {driverVehicleId}</p>
        {vehicleCall.callerRole === 'PARENT' && vehicleCall.studentName && <p className="mt-2 mb-12 px-4 py-2 rounded-full bg-white/10 text-white text-sm font-semibold">Student: {vehicleCall.studentName}</p>}
        {vehicleCall.callerRole === 'ADMIN' && <div className="mb-12" />}
        <div className="flex gap-8">
          <button onClick={() => endVehicleCall('Driver declined the call')} className="flex flex-col items-center gap-2 text-white"><span className="w-16 h-16 rounded-full bg-red-600 flex items-center justify-center"><PhoneOff size={27} /></span><span className="text-sm">Decline</span></button>
          <button onClick={answerVehicleCall} className="flex flex-col items-center gap-2 text-white"><span className="w-16 h-16 rounded-full bg-green-600 flex items-center justify-center"><PhoneCall size={27} /></span><span className="text-sm">Answer</span></button>
        </div>
      </div>}

      {vehicleCall?.vehicleId === driverVehicleId && vehicleCall.status === 'CONNECTED' &&
      <div className="absolute top-0 inset-x-0 z-[85] bg-green-600 text-white px-4 py-3 flex items-center gap-3 shadow-lg">
        <span className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center"><PhoneCall size={18} /></span>
        <div className="flex-1"><p className="text-sm font-bold">Connected · {vehicleCall.callerName}</p><p className="text-xs text-green-100">In-app vehicle call</p></div>
        <button onClick={() => endVehicleCall('Driver ended the call')} className="px-3 py-2 bg-red-600 rounded-lg text-xs font-bold flex items-center gap-1.5"><PhoneOff size={14} /> End</button>
      </div>}

      {showEmergencyCalls && <EmergencyCallPanel context={`Driver · ${driverVehicleId} · Current location: Kaduwela Road`} onClose={() => setShowEmergencyCalls(false)} />}

      {emergency.active && emergency.driverPhase !== 'COUNTDOWN' && emergency.stage !== 'NONE' &&
      <div className="absolute top-0 inset-x-0 bg-red-600 text-white text-sm font-semibold px-5 py-2 z-[70] text-center">
          Emergency escalation in progress · {emergency.stage.replace(/_/g, ' ')}
        </div>
      }

      {recentScan &&
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-5 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl text-center animate-in zoom-in-95 duration-200">
            <span className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 size={40} />
            </span>
            <h2 className="text-2xl font-bold text-slate-800 mb-1">Student Verified</h2>
            <p className="text-lg font-medium text-slate-600">{recentScan.name}</p>
            <p className="text-sm text-slate-500 mb-6">{recentScan.id} · {driverVehicleId}</p>
            <div className="bg-slate-50 rounded-lg p-4 text-sm text-slate-600 space-y-2 text-left">
              <p className="flex justify-between"><span>Boarded at</span> <span className="font-medium text-slate-800">07:08 AM</span></p>
              <p className="flex justify-between items-center"><span>RFID verification</span> <CheckCircle2 size={16} className="text-green-500" /></p>
              <p className="flex justify-between items-center"><span>Correct vehicle</span> <CheckCircle2 size={16} className="text-green-500" /></p>
            </div>
          </div>
        </div>
      }

      {wrongVehicleAttempt &&
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-5 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl text-center border-t-4 border-red-500">
            <span className="w-20 h-20 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={40} />
            </span>
            <h2 className="text-2xl font-bold text-red-600 mb-4">WRONG VEHICLE</h2>
            <div className="bg-red-50 rounded-lg p-4 mb-6 text-sm text-left space-y-3">
              <p className="flex justify-between"><span className="text-red-800/70">Student</span> <span className="font-semibold text-red-900">{wrongVehicleAttempt.studentName}</span></p>
              <p className="flex justify-between"><span className="text-red-800/70">Assigned vehicle</span> <span className="font-semibold text-red-900">{wrongVehicleAttempt.assignedVehicle}</span></p>
              <p className="flex justify-between"><span className="text-red-800/70">Attempted vehicle</span> <span className="font-semibold text-red-900">{wrongVehicleAttempt.attemptedVehicle}</span></p>
            </div>
            <p className="text-red-600 font-medium mb-6">Boarding verification failed.</p>
            <div className="space-y-3">
              <button onClick={contactAdmin} className="w-full py-3 bg-red-600 text-white rounded-xl font-semibold shadow-md hover:bg-red-700 transition-colors">
                Contact Admin
              </button>
              <button onClick={() => setWrongVehicleAttempt(null)} className="w-full py-3 bg-slate-100 text-slate-700 rounded-xl font-semibold hover:bg-slate-200 transition-colors">
                Dismiss
              </button>
            </div>
          </div>
        </div>
      }

      {geofenceReached &&
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-5 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
            <div className="bg-[#176B87] p-6 text-center text-white">
              <MapPin size={40} className="mx-auto mb-3 opacity-80" />
              <h2 className="text-xl font-bold mb-1">DESTINATION REACHED</h2>
              <p className="text-blue-100">Horizon College</p>
            </div>
            <div className="p-5 overflow-y-auto flex-1">
              {pendingAtSchool.length > 0 ?
            <>
                  <p className="text-sm font-medium text-slate-500 mb-4">Students requiring destination confirmation:</p>
                  <ul className="space-y-3 mb-6">
                    {pendingAtSchool.map((student) =>
                <li key={student.id} className="flex items-center justify-between bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="font-medium text-slate-800">{student.name}</span>
                        <button onClick={() => confirmDropOff(student.id)} className="px-4 py-1.5 bg-blue-100 text-blue-700 rounded-md text-sm font-semibold hover:bg-blue-200 transition-colors">
                          Confirm
                        </button>
                      </li>
                )}
                  </ul>
                  <button onClick={confirmAll} className="w-full py-3 bg-[#176B87] text-white rounded-xl font-semibold shadow-md hover:bg-[#12546b] transition-colors">
                    Confirm All Students
                  </button>
                </> :

            <div className="text-center py-6">
                  <CheckCircle2 size={40} className="mx-auto text-green-500 mb-3" />
                  <p className="font-semibold text-slate-800 mb-1">Destination verification complete</p>
                  <p className="text-sm text-slate-500 mb-6">RFID check-out ✓ · Geofence ✓ · Driver confirmation ✓</p>
                  <button onClick={() => setGeofenceReached(false)} className="w-full py-3 bg-slate-100 text-slate-700 rounded-xl font-semibold hover:bg-slate-200 transition-colors">
                    Close
                  </button>
                </div>
            }
            </div>
          </div>
        </div>
      }
    </div>);

}

function getPrimaryRisk(state: { sensors: {speed: number;standing: string;standingDuration: number;doorDensity: string;occupancy: number;confidence: number};breakdown: {occupancy: number;behaviour: number;door: number;speed: number;sensor: number} }) {
  const factors = [
    { key: 'speed', value: state.breakdown.speed },
    { key: 'behaviour', value: state.breakdown.behaviour },
    { key: 'door', value: state.breakdown.door },
    { key: 'occupancy', value: state.breakdown.occupancy },
    { key: 'sensor', value: state.breakdown.sensor }
  ].sort((a, b) => b.value - a.value);

  switch (factors[0].key) {
    case 'speed': return { title: 'High speed detected', detail: `${state.sensors.speed} km/h is above the safe threshold` };
    case 'behaviour': return { title: 'Unsafe passenger behaviour', detail: state.sensors.standing !== 'None' ? `${state.sensors.standing} standing for ${state.sensors.standingDuration}s while moving` : 'Unsafe movement detected inside the cabin' };
    case 'door': return { title: 'Door area crowding', detail: `${state.sensors.doorDensity} passenger density near the door` };
    case 'occupancy': return { title: 'High occupancy', detail: `${state.sensors.occupancy} passengers detected` };
    default: return { title: 'Sensor disagreement', detail: `Sensor confidence reduced to ${state.sensors.confidence}%` };
  }
}
