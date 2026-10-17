import { useAppContext } from '../contexts/AppContext';
import { Settings, Play, CheckCircle, AlertTriangle, Map, ShieldAlert, Activity, RefreshCw } from 'lucide-react';
import { SAFETY_SCENARIOS, SafetyEventKey } from '../data/safetyScenarios';
import { BrandLogo } from '../components/BrandLogo';

export function DemoControlCenter() {
  const {
    setRole,
    setWrongVehicleAttempt,
    setGeofenceReached,
    addNotification,
    setStudents,
    students,
    safetyState,
    setSafetyState,
    setActiveTab,
    routeState,
    setRouteState,
    setPickupWindow,
    emergency,
    triggerCrash,
    resolveDriverSafe,
    driverTimeout,
    driverRequestHelp,
    acknowledgeStage,
    tripState,
    startTrip,
    endTrip,
    resetAll
  } = useAppContext();

  const handleWrongVehicle = () => {
    setWrongVehicleAttempt({ studentName: 'Dilan Silva', assignedVehicle: 'VAN-02', attemptedVehicle: 'BUS-01' });
    addNotification({ role: 'PARENT', message: 'Boarding attempt detected on an unassigned vehicle.', type: 'error', studentId: 'ST005', vehicleId: 'VAN-02' });
    addNotification({ role: 'ADMIN', message: 'Wrong vehicle boarding attempt: Dilan Silva on BUS-01', type: 'error' });
    setRole('DRIVER');
  };

  const handleCorrectScan = () => {
    const next = students.find((s) => s.assignedVehicle === 'BUS-01' && s.status === 'PLANNED');
    if (!next) {
      addNotification({ role: 'ADMIN', message: 'All BUS-01 students are already verified.', type: 'info' });
      return;
    }
    setStudents(students.map((s) => s.id === next.id ? { ...s, status: 'BOARDED' } : s));
    addNotification({ role: 'PARENT', message: `${next.name} boarded BUS-01.`, type: 'success', studentId: next.id, vehicleId: 'BUS-01' });
    addNotification({ role: 'ADMIN', message: `${next.name} verified via RFID on BUS-01.`, type: 'success' });
  };

  const handleCheckOut = () => {
    const boarded = students.filter((s) => s.assignedVehicle === 'BUS-01' && s.status === 'BOARDED');
    if (boarded.length === 0) {
      addNotification({ role: 'ADMIN', message: 'No boarded students to check out on BUS-01.', type: 'info' });
      return;
    }
    setStudents(students.map((s) => s.status === 'BOARDED' && s.assignedVehicle === 'BUS-01' ? { ...s, status: 'DROPPED_OFF' } : s));
    boarded.forEach((student) => addNotification({ role: 'PARENT', message: `${student.name} checked out at ${student.school}.`, type: 'success', studentId: student.id, vehicleId: 'BUS-01' }));
    addNotification({ role: 'ADMIN', message: `${boarded.length} student(s) checked out from BUS-01.`, type: 'success' });
  };

  const triggerSafetyEvent = (key: SafetyEventKey) => {
    const scenario = SAFETY_SCENARIOS[key];
    setSafetyState({
      score: scenario.score,
      level: scenario.level,
      sensors: {
        rfid: scenario.sensors.rfidCount,
        ir: scenario.sensors.irCount,
        pressure: scenario.sensors.pressureEstimate,
        ultrasonic: scenario.sensors.ultrasonicEstimate,
        confidence: scenario.sensors.confidence,
        speed: scenario.sensors.speed,
        standing: scenario.sensors.standingStudent,
        standingDuration: scenario.sensors.standingDuration,
        doorDensity: scenario.sensors.doorDensity,
        occupancy: scenario.sensors.occupancy
      },
      breakdown: {
        occupancy: scenario.breakdown.occupancy,
        behaviour: scenario.breakdown.behaviour,
        door: scenario.breakdown.doorCrowding,
        speed: scenario.breakdown.speed,
        sensor: scenario.breakdown.sensorDisagreement
      },
      cameraState: scenario.level === 'HIGH' || scenario.level === 'CRITICAL' ? 'AVAILABLE' : 'LOCKED'
    });

    if (scenario.alertTitle) {
      addNotification({
        role: 'ALL',
        vehicleId: 'BUS-01',
        message: `${scenario.alertTitle}: ${scenario.alertBody}`,
        type: scenario.level === 'CRITICAL' || scenario.level === 'HIGH' ? 'error' : 'warning'
      });
    }
    setActiveTab('Safety');
  };

  const handleTraffic = (level: 'Normal' | 'Heavy') => {
    setRouteState((prev) => ({
      ...prev,
      trafficLevel: level === 'Heavy' ? 'Heavy' : 'Moderate',
      trafficEtaMin: level === 'Heavy' ? 95 : 78,
      mlEtaMin: level === 'Heavy' ? 90 : 81,
      combinedEtaMin: level === 'Heavy' ? 92 : 79
    }));
    addNotification({
      role: 'ADMIN',
      message: level === 'Heavy' ? 'Heavy traffic detected — ETA extended to 92 min.' : 'Traffic returned to normal — ETA 79 min.',
      type: level === 'Heavy' ? 'warning' : 'info'
    });
    setActiveTab('Routes');
  };

  const handleOptimizeRoute = () => {
    setRouteState((prev) => ({ ...prev, isOptimizing: true, optimizationStep: 0, lastOptimization: null }));
    setActiveTab('Routes');
  };

  const handleRouteDeviation = () => {
    setRouteState((prev) => ({
      ...prev,
      deviationAlert: {
        vehicleId: 'BUS-01',
        expectedRoute: 'Kaduwela → Malabe',
        distanceFromRoute: 1.3,
        currentLocation: 'Battaramulla Road'
      }
    }));
    addNotification({ role: 'ADMIN', message: 'Route deviation detected: BUS-01 is 1.3 km off the planned route.', type: 'error' });
    addNotification({ role: 'DRIVER', message: 'You have deviated from the optimized route.', type: 'warning' });
    setActiveTab('Routes');
  };

  const handleUnexpectedStop = () => {
    setRouteState((prev) => ({
      ...prev,
      deviationAlert: {
        vehicleId: 'BUS-01',
        expectedRoute: 'Kaduwela → Battaramulla',
        distanceFromRoute: 0.4,
        currentLocation: 'Unscheduled stop · Malabe Junction (4 min stationary)'
      }
    }));
    addNotification({ role: 'ADMIN', message: 'Unexpected stop: BUS-01 stationary for 4 min at an unscheduled location.', type: 'warning' });
    setActiveTab('Routes');
  };

  const handleExpirePickupWindow = () => {
    setPickupWindow((prev) => ({ ...prev, expired: true, remainingSeconds: 0 }));
    setStudents(students.map((s) => s.id === 'ST004' ? { ...s, status: 'MISSED' } : s));
    addNotification({ role: 'PARENT', message: 'Missed pickup alert: Kavindu was not picked up within the scheduled window.', type: 'error', studentId: 'ST004', vehicleId: 'BUS-01' });
    addNotification({ role: 'ADMIN', message: 'Pickup window expired for Kavindu Perera (Stop 4).', type: 'warning' });
  };

  const stage = emergency.stage;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-300 p-6 md:p-8 font-mono">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-wrap gap-4 justify-between items-center mb-8 border-b border-slate-800 pb-6">
          <div className="flex items-center gap-4">
            <BrandLogo className="w-14 h-14 rounded-2xl" decorative />
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3">
                <Settings className="text-blue-500" />
                SafeRide-LK Research Prototype Simulator
              </h1>
              <p className="text-slate-400 mt-2 text-sm">All events below are simulated. No IoT hardware or emergency service is connected.</p>
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={resetAll} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded flex items-center gap-2 transition-colors">
              <RefreshCw size={16} /> Reset Demo
            </button>
            <button onClick={() => setRole(null)} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors font-sans font-medium">
              Exit Simulator
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

          <ControlSection title="Trip" icon={Play} color="text-emerald-400">
            <ControlButton label="Start Morning Trip" onClick={() => startTrip('MORNING')} active={tripState === 'MORNING'} />
            <ControlButton label="Start Afternoon Trip" onClick={() => startTrip('AFTERNOON')} active={tripState === 'AFTERNOON'} />
            <ControlButton label="End Trip" variant="danger" onClick={endTrip} active={tripState === 'ENDED'} />
          </ControlSection>

          <ControlSection title="Student Verification (C1)" icon={CheckCircle} color="text-blue-400">
            <ControlButton label="Scan Correct RFID" onClick={handleCorrectScan} />
            <ControlButton label="Scan Wrong Vehicle" variant="warning" onClick={handleWrongVehicle} />
            <ControlButton label="Student Check-Out" onClick={handleCheckOut} />
            <ControlButton label="Enter School Geofence" onClick={() => {setGeofenceReached(true);setRole('DRIVER');}} />
            <ControlButton label="Confirm Destination" onClick={() => {setGeofenceReached(true);setRole('DRIVER');}} />
          </ControlSection>

          <ControlSection title="Safety (C2)" icon={Activity} color="text-amber-400">
            <ControlButton label="Normal" onClick={() => triggerSafetyEvent('NORMAL')} active={safetyState.score === 18} />
            <ControlButton label="Overcrowding" variant="warning" onClick={() => triggerSafetyEvent('OVERCROWDING')} />
            <ControlButton label="Standing 2 sec" variant="warning" onClick={() => triggerSafetyEvent('STANDING_2S')} />
            <ControlButton label="Standing 12 sec" variant="danger" onClick={() => triggerSafetyEvent('STANDING_12S')} />
            <ControlButton label="Door Crowding" variant="warning" onClick={() => triggerSafetyEvent('DOOR_CROWDING')} />
            <ControlButton label="Sensor Conflict" variant="warning" onClick={() => triggerSafetyEvent('SENSOR_CONFLICT')} />
            <ControlButton label="High Speed" variant="danger" onClick={() => triggerSafetyEvent('HIGH_SPEED')} />
            <ControlButton label="Critical Risk" variant="danger" onClick={() => triggerSafetyEvent('CRITICAL')} />
          </ControlSection>

          <ControlSection title="Route (C3)" icon={Map} color="text-indigo-400">
            <ControlButton label="Normal Traffic" onClick={() => handleTraffic('Normal')} active={routeState.trafficLevel !== 'Heavy'} />
            <ControlButton label="Heavy Traffic" variant="warning" onClick={() => handleTraffic('Heavy')} active={routeState.trafficLevel === 'Heavy'} />
            <ControlButton label="Optimize Route" onClick={handleOptimizeRoute} />
            <ControlButton label="Register student (database)" onClick={() => { setRole('ADMIN'); setActiveTab('Students'); }} />
            <ControlButton label="Route Deviation" variant="warning" onClick={handleRouteDeviation} />
            <ControlButton label="Unexpected Stop" variant="warning" onClick={handleUnexpectedStop} />
            <ControlButton label="Expire Pickup Window" variant="danger" onClick={handleExpirePickupWindow} />
          </ControlSection>

          <ControlSection title="Emergency (C4)" icon={ShieldAlert} color="text-red-500">
            <ControlButton label="Minor Impact" variant="warning" onClick={() => triggerCrash('MINOR')} />
            <ControlButton label="Moderate Crash" variant="danger" onClick={() => triggerCrash('MODERATE')} />
            <ControlButton label="Critical Crash" variant="danger" onClick={() => triggerCrash('CRITICAL')} />
          </ControlSection>

          <ControlSection title="Driver Response" icon={AlertTriangle} color="text-orange-400">
            <ControlButton label="Driver Safe" onClick={resolveDriverSafe} disabled={emergency.driverPhase !== 'COUNTDOWN'} />
            <ControlButton label="Driver Does Not Respond" variant="danger" onClick={driverTimeout} disabled={emergency.driverPhase !== 'COUNTDOWN'} />
            <ControlButton label="Request Help" variant="danger" onClick={driverRequestHelp} disabled={emergency.driverPhase !== 'COUNTDOWN'} />
          </ControlSection>

          <ControlSection title="Emergency Acknowledgements" icon={ShieldAlert} color="text-rose-400">
            <ControlButton label="EMS Acknowledge" onClick={() => acknowledgeStage('EMS')} disabled={stage !== 'EMS_NOTIFIED'} />
            <ControlButton label="Police Acknowledge" onClick={() => acknowledgeStage('POLICE')} disabled={stage !== 'POLICE_NOTIFIED'} />
            <ControlButton label="Fire Acknowledge" onClick={() => acknowledgeStage('FIRE')} disabled={stage !== 'FIRE_NOTIFIED'} />
            <ControlButton label="Hospital Acknowledge" onClick={() => acknowledgeStage('HOSPITAL')} disabled={stage !== 'HOSPITAL_NOTIFIED'} />
          </ControlSection>

          <ControlSection title="Jump to Interface" icon={Play} color="text-sky-400">
            <ControlButton label="Administrator" onClick={() => setRole('ADMIN')} />
            <ControlButton label="Driver" onClick={() => setRole('DRIVER')} />
            <ControlButton label="Parent" onClick={() => setRole('PARENT')} />
            <ControlButton label="EMS / Doctor" onClick={() => setRole('EMS')} />
            <ControlButton label="Police" onClick={() => setRole('POLICE')} />
            <ControlButton label="Fire Brigade" onClick={() => setRole('FIRE')} />
            <ControlButton label="Hospital" onClick={() => setRole('HOSPITAL')} />
          </ControlSection>

          <div className="md:col-span-2 lg:col-span-1 bg-slate-800 rounded-lg p-5 border border-slate-700">
            <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
              <Activity size={18} className="text-blue-400" />
              Global Prototype State
            </h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <StateItem label="Trip State" value={tripState} />
              <StateItem label="Vehicle" value="BUS-01" />
              <StateItem
                label="Risk Score"
                value={`${safetyState.score} ${safetyState.level}`}
                color={
                safetyState.level === 'LOW' ? 'text-emerald-400' :
                safetyState.level === 'MODERATE' ? 'text-amber-400' :
                safetyState.level === 'HIGH' ? 'text-orange-400' : 'text-red-500'
                } />
              
              <StateItem
                label="Route Status"
                value={routeState.deviationAlert ? 'Deviated' : routeState.isOptimizing ? 'Optimizing' : routeState.trafficLevel === 'Heavy' ? 'Heavy traffic' : 'On track'}
                color={routeState.deviationAlert ? 'text-red-400' : 'text-white'} />
              
              <StateItem
                label="Crash Status"
                value={emergency.active ? String(emergency.severity) : 'Normal'}
                color={emergency.active ? 'text-red-500' : 'text-emerald-400'} />
              
              <StateItem label="Emergency Stage" value={stage.replace(/_/g, ' ')} />
            </div>
          </div>

        </div>
      </div>
    </div>);

}

function ControlSection({ title, icon: Icon, color, children }: any) {
  return (
    <section className="bg-slate-800/50 rounded-lg p-5 border border-slate-700/50">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <Icon size={18} className={color} />
        {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>);

}

function ControlButton({ label, variant = 'default', onClick, disabled = false, active = false





}: {label: string;variant?: 'default' | 'warning' | 'danger';onClick?: () => void;disabled?: boolean;active?: boolean;}) {
  const variants = {
    default: 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-slate-300 hover:text-white',
    warning: 'bg-amber-900/20 border-amber-700/30 hover:bg-amber-900/40 text-amber-200/80 hover:text-amber-200',
    danger: 'bg-red-900/20 border-red-700/30 hover:bg-red-900/40 text-red-200/80 hover:text-red-200'
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full text-left px-3 py-2 rounded text-sm border transition-colors ${variants[variant]} ${active ? 'ring-1 ring-blue-500/60' : ''} ${disabled ? 'opacity-35 cursor-not-allowed hover:bg-slate-800' : ''}`}>
      
      {label}
    </button>);

}

function StateItem({ label, value, color = 'text-white' }: any) {
  return (
    <div className="bg-slate-900/50 p-3 rounded border border-slate-800">
      <div className="text-slate-500 text-xs mb-1">{label}</div>
      <div className={`font-semibold ${color}`}>{value}</div>
    </div>);

}
