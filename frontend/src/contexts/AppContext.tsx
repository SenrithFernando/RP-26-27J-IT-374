import React, { createContext, useContext, useState, ReactNode, useEffect, useRef } from 'react';
import { Role, Vehicle, Student, Notification, SafetyState, RouteState, PickupWindowState, EmergencyState, CrashSeverity, CrashData, Driver, Assistant, CrewAssignment, VehicleCall } from '../types';
import { MOCK_VEHICLES, MOCK_STUDENTS, MOCK_DRIVERS, MOCK_ASSISTANTS, MOCK_CREW_ASSIGNMENTS } from '../data/mockData';
import { MORNING_STOPS } from '../data/routeData';
import { useAuth } from './AuthContext';
import { createStudent, fetchStudents, RoutingOutcome, StudentMutation, StudentRecord, StudentWrite } from '../services/api';

export type TripState = 'IDLE' | 'MORNING' | 'AFTERNOON' | 'ENDED';

type NewStudentInput = StudentWrite;

interface AppContextType {
  role: Role;
  setRole: (role: Role) => void;
  vehicles: Vehicle[];
  setVehicles: React.Dispatch<React.SetStateAction<Vehicle[]>>;
  students: Student[];
  setStudents: React.Dispatch<React.SetStateAction<Student[]>>;
  demoMode: boolean;
  setDemoMode: (mode: boolean) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedVehicleId: string;
  setSelectedVehicleId: (id: string) => void;
  drivers: Driver[];
  assistants: Assistant[];
  crewAssignments: CrewAssignment[];
  addDriver: (driver: Omit<Driver, 'id' | 'status'>) => void;
  addAssistant: (assistant: Omit<Assistant, 'id' | 'status'>) => void;
  assignCrew: (assignment: Omit<CrewAssignment, 'id' | 'date' | 'status'>) => void;
  vehicleCall: VehicleCall | null;
  startVehicleCall: (vehicleId: string, callerRole: 'ADMIN' | 'PARENT', callerName: string, studentName?: string) => void;
  answerVehicleCall: () => void;
  endVehicleCall: (reason?: string) => void;

  notifications: Notification[];
  addNotification: (notif: Omit<Notification, 'id' | 'time'>) => void;

  driverVehicleId: string;
  geofenceReached: boolean;
  setGeofenceReached: (val: boolean) => void;
  wrongVehicleAttempt: any;
  setWrongVehicleAttempt: (val: any) => void;
  recentScan: any;
  setRecentScan: (val: any) => void;

  parentChildId: string;

  safetyState: SafetyState;
  setSafetyState: (state: SafetyState | ((prev: SafetyState) => SafetyState)) => void;

  routeState: RouteState;
  setRouteState: (state: RouteState | ((prev: RouteState) => RouteState)) => void;

  pickupWindow: PickupWindowState;
  setPickupWindow: (state: PickupWindowState | ((prev: PickupWindowState) => PickupWindowState)) => void;

  emergency: EmergencyState;
  setEmergency: (state: EmergencyState | ((prev: EmergencyState) => EmergencyState)) => void;
  triggerCrash: (severity: CrashSeverity) => void;
  resolveDriverSafe: () => void;
  driverTimeout: () => void;
  driverRequestHelp: () => void;
  acknowledgeStage: (stage: 'EMS' | 'POLICE' | 'FIRE' | 'HOSPITAL') => void;
  resetEmergency: () => void;

  tripState: TripState;
  startTrip: (kind: 'MORNING' | 'AFTERNOON') => void;
  endTrip: () => void;
  addStudentAndReoptimize: (input: NewStudentInput, requestKey?: string) => Promise<StudentMutation>;
  routingStudents: StudentRecord[];
  routingRevision: number;
  lastRoutingOutcome: RoutingOutcome | null;
  resetAll: () => void;
}

const defaultSafetyState: SafetyState = {
  score: 18,
  level: 'LOW',
  sensors: {
    rfid: 8, ir: 8, pressure: 9, ultrasonic: 8,
    confidence: 94, speed: 34, standing: 'None',
    standingDuration: 0, doorDensity: 'Normal', occupancy: 8
  },
  breakdown: { occupancy: 5, behaviour: 0, door: 0, speed: 8, sensor: 5 },
  cameraState: 'LOCKED'
};

const defaultRouteState: RouteState = {
  routeTab: 'MORNING',
  vehicleId: 'BUS-01',
  stops: MORNING_STOPS,
  distanceKm: 28.4,
  trafficEtaMin: 78,
  mlEtaMin: 81,
  combinedEtaMin: 79,
  trafficLevel: 'Moderate',
  isOptimizing: false,
  optimizationStep: 0,
  lastOptimization: null,
  deviationAlert: null
};

const defaultPickupWindow: PickupWindowState = {
  studentId: 'ST004',
  studentName: 'Kavindu Perera',
  stopNumber: 4,
  scheduledTime: '07:10',
  windowStart: '07:10',
  windowEnd: '07:25',
  remainingSeconds: 332,
  expired: false
};

const defaultEmergencyState: EmergencyState = {
  incidentId: 'INC-2026-0081',
  active: false,
  severity: null,
  crashData: null,
  driverPhase: 'NONE',
  driverCountdown: 30,
  stage: 'NONE',
  timeline: []
};

const CRASH_PRESETS: Record<CrashSeverity, Omit<CrashData, 'time'>> = {
  MINOR: { peakG: 2.1, vehicleRoll: 8, impactPressure: 22, classification: 'MINOR', location: 'Kaduwela Road' },
  MODERATE: { peakG: 4.8, vehicleRoll: 28, impactPressure: 55, classification: 'MODERATE', location: 'Kaduwela Road' },
  CRITICAL: { peakG: 8.7, vehicleRoll: 67, impactPressure: 92, classification: 'CRITICAL', location: 'Kaduwela Road' }
};

const initialNotifications: Notification[] = [
{ id: 'seed-1', role: 'PARENT', message: 'Nethmi boarded BUS-01', time: '07:08 AM', type: 'success', studentId: 'ST001', vehicleId: 'BUS-01' }];


const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: {children: ReactNode;}) {
  const {user}=useAuth();
  const simulationWorkspace=user?.mode==='demo';
  const [role, setRole] = useState<Role>(null);
  const [vehicles, setVehicles] = useState<Vehicle[]>(MOCK_VEHICLES);
  const [students, setStudents] = useState<Student[]>(MOCK_STUDENTS);
  const [routingStudents, setRoutingStudents] = useState<StudentRecord[]>([]);
  const [routingRevision, setRoutingRevision] = useState(0);
  const [lastRoutingOutcome, setLastRoutingOutcome] = useState<RoutingOutcome | null>(null);
  const observedEvents = useRef(new Set<string>());
  useEffect(() => {
    const onSaved = (event: Event) => {
      const outcome = (event as CustomEvent<RoutingOutcome>).detail;
      const signature = `${outcome.event_id}:${outcome.outcome}:${outcome.plans.map((plan) => `${plan.vehicle_id}:${plan.direction}:${plan.generation_status}:${plan.route_version ?? ''}`).join('|')}`;
      if (observedEvents.current.has(signature)) return;
      observedEvents.current.add(signature);
      setLastRoutingOutcome(outcome);
      setRoutingRevision((value) => value + 1);
    };
    window.addEventListener('routing-input-saved', onSaved);
    return () => window.removeEventListener('routing-input-saved', onSaved);
  }, []);
  const [demoMode, setDemoMode] = useState(true);
  const [activeTab, setActiveTab] = useState('Overview');
  const [selectedVehicleId, setSelectedVehicleId] = useState('BUS-01');
  const [drivers, setDrivers] = useState<Driver[]>(MOCK_DRIVERS);
  const [assistants, setAssistants] = useState<Assistant[]>(MOCK_ASSISTANTS);
  const [crewAssignments, setCrewAssignments] = useState<CrewAssignment[]>(MOCK_CREW_ASSIGNMENTS);
  const [vehicleCall, setVehicleCall] = useState<VehicleCall | null>(null);

  const [notifications, setNotifications] = useState<Notification[]>(initialNotifications);

  const [driverVehicleId] = useState('BUS-01');
  const [geofenceReached, setGeofenceReached] = useState(false);
  const [wrongVehicleAttempt, setWrongVehicleAttempt] = useState<any>(null);
  const [recentScan, setRecentScan] = useState<any>(null);

  const [parentChildId] = useState('ST001');

  const [safetyState, setSafetyState] = useState<SafetyState>(defaultSafetyState);
  const [routeState, setRouteState] = useState<RouteState>(defaultRouteState);
  const [pickupWindow, setPickupWindow] = useState<PickupWindowState>(defaultPickupWindow);
  const [emergency, setEmergency] = useState<EmergencyState>(defaultEmergencyState);
  const [tripState, setTripState] = useState<TripState>('MORNING');

  const addNotification = (notif: Omit<Notification, 'id' | 'time'>) => {
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    setNotifications((prev) => [{ ...notif, id: `${Date.now()}-${Math.random()}`, time }, ...prev]);
  };

  const addDriver = (input: Omit<Driver, 'id' | 'status'>) => {
    const id = `DRV-${(drivers.length + 1).toString().padStart(3, '0')}`;
    setDrivers((prev) => [...prev, { ...input, id, status: 'AVAILABLE' }]);
    addNotification({ role: 'ADMIN', message: `Driver added: ${input.name}.`, type: 'success' });
  };

  const addAssistant = (input: Omit<Assistant, 'id' | 'status'>) => {
    const id = `AST-${(assistants.length + 1).toString().padStart(3, '0')}`;
    setAssistants((prev) => [...prev, { ...input, id, status: 'AVAILABLE' }]);
    addNotification({ role: 'ADMIN', message: `Assistant added: ${input.name}.`, type: 'success' });
  };

  const assignCrew = (input: Omit<CrewAssignment, 'id' | 'date' | 'status'>) => {
    const driver = drivers.find((item) => item.id === input.driverId);
    const assignment: CrewAssignment = { ...input, id: `ASN-${Date.now()}`, date: '24 Aug 2026', status: 'ASSIGNED' };
    setCrewAssignments((prev) => [assignment, ...prev.map((item) => item.date === assignment.date && item.status === 'ASSIGNED' && (item.vehicleId === assignment.vehicleId || item.driverId === assignment.driverId || (Boolean(input.assistantId) && item.assistantId === assignment.assistantId)) ? { ...item, status: 'REASSIGNED' as const } : item)]);
    setDrivers((prev) => prev.map((item) => ({ ...item, status: item.id === input.driverId ? 'ON_TRIP' : item.status })));
    if (input.assistantId) setAssistants((prev) => prev.map((item) => ({ ...item, status: item.id === input.assistantId ? 'ON_TRIP' : item.status })));
    if (driver) setVehicles((prev) => prev.map((vehicle) => vehicle.id === input.vehicleId ? { ...vehicle, driver: driver.name } : vehicle));
    addNotification({ role: 'ADMIN', message: `${driver?.name || 'Driver'} assigned to ${input.vehicleId} for today.`, type: 'success' });
  };

  const startVehicleCall = (vehicleId: string, callerRole: 'ADMIN' | 'PARENT', callerName: string, studentName?: string) => {
    setVehicleCall({ id: `CALL-${Date.now()}`, vehicleId, callerRole, callerName, studentName, status: 'RINGING', startedAt: getTimeStr() });
    addNotification({ role: 'ADMIN', message: `${callerName} started an in-app call to ${vehicleId}.`, type: 'info' });
  };

  const answerVehicleCall = () => {
    setVehicleCall((prev) => prev ? { ...prev, status: 'CONNECTED' } : null);
    addNotification({ role: 'ADMIN', message: 'Driver answered the vehicle call.', type: 'success' });
  };

  const endVehicleCall = (reason = 'Call ended') => {
    if (vehicleCall) addNotification({ role: 'ADMIN', message: `${reason} · ${vehicleCall.vehicleId}.`, type: 'info' });
    setVehicleCall(null);
  };

  const getTimeStr = (offsetSec = 0) => {
    const d = new Date();
    d.setSeconds(d.getSeconds() + offsetSec);
    return d.toLocaleTimeString('en-US', { hour12: false });
  };

  const driverTimeout = () => {
    setEmergency((prev) => {
      if (!prev.active || prev.driverPhase === 'SAFE' || prev.stage !== 'NONE') return prev;
      return {
        ...prev,
        driverPhase: 'TIMEOUT',
        driverCountdown: 0,
        stage: 'EMS_NOTIFIED',
        timeline: [
        ...prev.timeline,
        { time: getTimeStr(), label: 'Driver did not respond', status: 'done' },
        { time: getTimeStr(1), label: 'Doctor / EMS notified', status: 'done' }]

      };
    });
    addNotification({ role: 'ADMIN', message: 'Driver unresponsive — escalating to EMS.', type: 'error' });
    addNotification({ role: 'PARENT', message: 'Emergency detected on BUS-01. Responders have been dispatched.', type: 'error', vehicleId: 'BUS-01', persistent: true });
  };

  // Driver 30 second override countdown
  useEffect(() => {
    if (!simulationWorkspace || emergency.driverPhase !== 'COUNTDOWN') return;
    if (emergency.driverCountdown <= 0) {
      driverTimeout();
      return;
    }
    const timer = setTimeout(() => {
      setEmergency((prev) => prev.driverPhase === 'COUNTDOWN' ?
      { ...prev, driverCountdown: prev.driverCountdown - 1 } :
      prev);
    }, 1000);
    return () => clearTimeout(timer);
  }, [simulationWorkspace, emergency.driverPhase, emergency.driverCountdown]);

  // Pickup window countdown
  useEffect(() => {
    if (!simulationWorkspace || pickupWindow.expired || pickupWindow.remainingSeconds <= 0) return;
    const timer = setTimeout(() => {
      setPickupWindow((prev) => ({ ...prev, remainingSeconds: Math.max(0, prev.remainingSeconds - 1) }));
    }, 1000);
    return () => clearTimeout(timer);
  }, [simulationWorkspace, pickupWindow.expired, pickupWindow.remainingSeconds]);

  const triggerCrash = (severity: CrashSeverity) => {
    const time = getTimeStr();
    setEmergency({
      incidentId: 'INC-2026-0081',
      active: true,
      severity,
      crashData: { ...CRASH_PRESETS[severity], time },
      driverPhase: severity === 'MINOR' ? 'NONE' : 'COUNTDOWN',
      driverCountdown: 30,
      stage: 'NONE',
      timeline: [{ time, label: `${severity} impact detected`, status: 'done' }]
    });
    addNotification({ role: 'ADMIN', message: `${severity} impact detected on BUS-01 (Kaduwela Road)`, type: 'error' });
    setActiveTab('Incidents');
  };

  const resolveDriverSafe = () => {
    setEmergency((prev) => prev.active ? {
      ...prev,
      driverPhase: 'SAFE',
      driverCountdown: 0,
      timeline: [...prev.timeline, { time: getTimeStr(), label: 'Driver confirmed safe — escalation cancelled', status: 'done' }]
    } : prev);
    addNotification({ role: 'ADMIN', message: 'Driver confirmed safe. Escalation cancelled.', type: 'success' });
  };

  const driverRequestHelp = () => {
    setEmergency((prev) => prev.active ? {
      ...prev,
      driverPhase: 'HELP_REQUESTED',
      driverCountdown: 0,
      stage: 'EMS_NOTIFIED',
      timeline: [
      ...prev.timeline,
      { time: getTimeStr(), label: 'Driver requested help', status: 'done' },
      { time: getTimeStr(1), label: 'Doctor / EMS notified', status: 'done' }]

    } : prev);
    addNotification({ role: 'ADMIN', message: 'Driver requested immediate help — EMS notified.', type: 'error' });
  };

  const acknowledgeStage = (stage: 'EMS' | 'POLICE' | 'FIRE' | 'HOSPITAL') => {
    setEmergency((prev) => {
      const expected: Record<typeof stage, string> = {
        EMS: 'EMS_NOTIFIED',
        POLICE: 'POLICE_NOTIFIED',
        FIRE: 'FIRE_NOTIFIED',
        HOSPITAL: 'HOSPITAL_NOTIFIED'
      };
      if (prev.stage !== expected[stage]) return prev;

      const time = getTimeStr();
      const timeline = [...prev.timeline];
      let nextStage = prev.stage;

      if (stage === 'EMS') {
        timeline.push({ time, label: 'EMS acknowledged', status: 'done' });
        timeline.push({ time: getTimeStr(1), label: 'Police notified', status: 'done' });
        nextStage = 'POLICE_NOTIFIED';
      } else if (stage === 'POLICE') {
        timeline.push({ time, label: 'Police acknowledged', status: 'done' });
        timeline.push({ time: getTimeStr(1), label: 'Fire Brigade notified', status: 'done' });
        nextStage = 'FIRE_NOTIFIED';
      } else if (stage === 'FIRE') {
        timeline.push({ time, label: 'Fire Brigade acknowledged', status: 'done' });
        timeline.push({ time: getTimeStr(1), label: 'Hospital notified', status: 'done' });
        nextStage = 'HOSPITAL_NOTIFIED';
      } else {
        timeline.push({ time, label: 'Hospital acknowledged — all responders engaged', status: 'done' });
        nextStage = 'HOSPITAL_ACK';
      }

      return { ...prev, stage: nextStage, timeline };
    });
  };

  const resetEmergency = () => setEmergency(defaultEmergencyState);

  const startTrip = (kind: 'MORNING' | 'AFTERNOON') => {
    setTripState(kind);
    setStudents((prev) => prev.map((s) => ({ ...s, status: 'PLANNED' })));
    setRouteState((prev) => ({ ...prev, routeTab: kind, deviationAlert: null }));
    setPickupWindow({ ...defaultPickupWindow });
    addNotification({
      role: 'ADMIN',
      message: `${kind === 'MORNING' ? 'Morning pickup' : 'Afternoon drop-off'} trip started for BUS-01.`,
      type: 'info'
    });
  };

  const endTrip = () => {
    setTripState('ENDED');
    addNotification({ role: 'ADMIN', message: 'Trip ended for BUS-01. All students accounted for.', type: 'info' });
  };

  const addStudentAndReoptimize = async (input: NewStudentInput, requestKey?: string): Promise<StudentMutation> => {
    const response = await createStudent(input, requestKey);
    // Routing records stay separate from simulated boarding/safety state. Never
    // reset a trip, completed stop, or RFID state while saving a registration.
    setRoutingStudents((prev) => [...prev.filter((student) => student.id !== response.id), response]);
    try { setRoutingStudents(await fetchStudents()); }
    catch { /* The API save succeeded; a read failure must not be reported as a save failure. */ }
    addNotification({ role: 'ADMIN', message: response.routing.outcome === 'failed'
      ? `Student saved; routing failed: ${response.name}. See the reported planning constraints.`
      : `Student saved: ${response.name}. Backend planning status: ${response.routing.outcome}.`,
      type: response.routing.outcome === 'failed' ? 'warning' : 'info' });
    return response;
  };

  const resetAll = () => {
    setStudents(MOCK_STUDENTS);
    setVehicles(MOCK_VEHICLES);
    setSafetyState(defaultSafetyState);
    setRouteState(defaultRouteState);
    setPickupWindow({ ...defaultPickupWindow });
    setEmergency(defaultEmergencyState);
    setGeofenceReached(false);
    setWrongVehicleAttempt(null);
    setRecentScan(null);
    setNotifications(initialNotifications);
    setTripState('MORNING');
    setActiveTab('Overview');
    setSelectedVehicleId('BUS-01');
    setDrivers(MOCK_DRIVERS);
    setAssistants(MOCK_ASSISTANTS);
    setCrewAssignments(MOCK_CREW_ASSIGNMENTS);
    setVehicleCall(null);
  };

  return (
    <AppContext.Provider value={{
      role, setRole,
      vehicles, setVehicles,
      students, setStudents,
      demoMode, setDemoMode,
      activeTab, setActiveTab,
      selectedVehicleId, setSelectedVehicleId,
      drivers, assistants, crewAssignments, addDriver, addAssistant, assignCrew,
      vehicleCall, startVehicleCall, answerVehicleCall, endVehicleCall,
      notifications, addNotification,
      driverVehicleId, geofenceReached, setGeofenceReached,
      wrongVehicleAttempt, setWrongVehicleAttempt,
      recentScan, setRecentScan,
      parentChildId,
      safetyState, setSafetyState,
      routeState, setRouteState,
      pickupWindow, setPickupWindow,
      emergency, setEmergency,
      triggerCrash, resolveDriverSafe, driverTimeout, driverRequestHelp, acknowledgeStage, resetEmergency,
      tripState, startTrip, endTrip, addStudentAndReoptimize, routingStudents, routingRevision, lastRoutingOutcome, resetAll
    }}>
      {children}
    </AppContext.Provider>);

}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useAppContext must be used within AppProvider');
  return context;
}
