import { useState, useEffect } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { Activity, Users, AlertTriangle, Info, Camera, Unlock, Video, ClipboardCheck, Eye } from 'lucide-react';
import { getRiskColor } from '../data/safetyScenarios';

export function SafetyMonitoring() {
  const { safetyState, addNotification, vehicles, students, selectedVehicleId, setSelectedVehicleId } = useAppContext();
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === selectedVehicleId) || vehicles[0];
  const selectedOccupancy = students.filter((student) => student.assignedVehicle === selectedVehicle?.id && (student.status === 'BOARDED' || student.status === 'DROPPED_OFF')).length;
  const vehicleSafety = selectedVehicle?.id === 'BUS-01' ? safetyState : {
    score: 32,
    level: 'MODERATE' as const,
    sensors: { rfid: selectedOccupancy, ir: selectedOccupancy, pressure: selectedOccupancy, ultrasonic: selectedOccupancy, confidence: 88, speed: selectedVehicle?.speed || 0, standing: 'None', standingDuration: 0, doorDensity: selectedOccupancy > selectedVehicle.capacity * 0.8 ? 'Moderate' : 'Normal', occupancy: selectedOccupancy },
    breakdown: { occupancy: 12, behaviour: 0, door: 8, speed: 7, sensor: 5 },
    cameraState: safetyState.cameraState
  };
  const { score, level, sensors, breakdown, cameraState } = vehicleSafety;
  const colors = getRiskColor(level);
  const [secondsLeft, setSecondsLeft] = useState(300);
  const [adminCameraViewing, setAdminCameraViewing] = useState(false);
  const [accessReason, setAccessReason] = useState('Routine safety supervision');

  useEffect(() => {
    if (!adminCameraViewing) {setSecondsLeft(300);return;}
    if (secondsLeft <= 0) {
      setAdminCameraViewing(false);
      addNotification({ role: 'ADMIN', message: 'Administrator camera session expired and was recorded in the access log.', type: 'info' });
      return;
    }
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [adminCameraViewing, secondsLeft]);

  const mmss = `${Math.floor(secondsLeft / 60).toString().padStart(2, '0')}:${(secondsLeft % 60).toString().padStart(2, '0')}`;

  const handleCameraRequest = () => {
    setSecondsLeft(300);
    setAdminCameraViewing(true);
    addNotification({ role: 'ADMIN', message: `Live camera opened for ${selectedVehicle.id} by Transport Admin · Reason: ${accessReason} · Session limited to 5 min.`, type: 'warning' });
  };

  const revokeCamera = () => {
    setAdminCameraViewing(false);
    addNotification({ role: 'ADMIN', message: `Administrator camera access ended for ${selectedVehicle.id} · Reason: ${accessReason}.`, type: 'info' });
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-[#17212B]">Vehicle Safety Intelligence</h2>
          <p className="text-slate-500">Real-time multi-sensor risk prediction</p>
        </div>
        <div className="bg-white px-4 py-2 rounded-lg border border-slate-200 shadow-sm flex items-center gap-3">
          <label htmlFor="safety-vehicle" className="text-sm text-slate-500 font-medium">Selected Vehicle:</label>
          <select id="safety-vehicle" value={selectedVehicle.id} onChange={(event) => {setSelectedVehicleId(event.target.value);setAdminCameraViewing(false);}} className="font-bold text-[#176B87] bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#2D9CDB]/40">
            {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.id} · {vehicle.registrationNumber}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Primary Risk Visualization */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col items-center justify-center text-center relative overflow-hidden">
          <div className={`absolute top-0 left-0 w-full h-2 ${colors.bg}`}></div>
          <h3 className="font-semibold text-slate-500 mb-6">Safety Risk Score</h3>
          
          <div className="relative w-48 h-48 flex items-center justify-center mb-6">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke="#f1f5f9" strokeWidth="10" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke="currentColor" strokeWidth="10"
                strokeDasharray="283"
                strokeDashoffset={283 - 283 * score / 100}
                className={`${colors.text} transition-all duration-1000 ease-out`} />
              
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-5xl font-bold ${colors.text}`}>{score}</span>
              <span className="text-slate-400 text-sm font-medium">/ 100</span>
            </div>
          </div>
          
          <div className={`px-6 py-2 rounded-full font-bold text-lg tracking-wide ${colors.bgSoft} ${colors.text} border ${colors.border}`}>
            {level}
          </div>
        </div>

        {/* Why this score? */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-[#17212B] mb-4 flex items-center gap-2">
            <Info size={18} className="text-blue-500" />
            Risk Factor Breakdown
          </h3>
          <div className="space-y-4">
            <BreakdownItem label="Occupancy risk" value={breakdown.occupancy} />
            <BreakdownItem label="Behaviour risk" value={breakdown.behaviour} />
            <BreakdownItem label="Door crowding" value={breakdown.door} />
            <BreakdownItem label="Vehicle speed" value={breakdown.speed} />
            <BreakdownItem label="Sensor disagreement" value={breakdown.sensor} />
            
            <div className="pt-4 border-t border-slate-100 flex justify-between items-center font-bold text-[#17212B]">
              <span>Total Score</span>
              <span>{score} / 100</span>
            </div>
          </div>
        </div>

        {/* Live Sensor Values */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-[#17212B] mb-4 flex items-center gap-2">
            <Activity size={18} className="text-blue-500" />
            Live Sensor Telemetry
          </h3>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <SensorItem label="RFID Count" value={sensors.rfid} />
            <SensorItem label="IR Count" value={sensors.ir} />
            <SensorItem label="Pressure Est." value={sensors.pressure} />
            <SensorItem label="Ultrasonic Est." value={sensors.ultrasonic} />
            
            <div className="col-span-2 my-1 border-t border-slate-50"></div>
            
            <SensorItem label="Confidence" value={`${sensors.confidence}%`} highlight={sensors.confidence < 80} />
            <SensorItem label="Speed" value={`${sensors.speed} km/h`} highlight={sensors.speed > 50} />
            <SensorItem label="Standing" value={sensors.standing} highlight={sensors.standing !== 'None'} />
            <SensorItem label="Duration" value={`${sensors.standingDuration}s`} highlight={sensors.standingDuration > 5} />
            <SensorItem label="Door Density" value={sensors.doorDensity} highlight={sensors.doorDensity !== 'Normal'} />
            <SensorItem label="Occupancy" value={`${sensors.occupancy} / ${selectedVehicle.capacity}`} highlight={sensors.occupancy >= selectedVehicle.capacity} />
          </div>
        </div>

      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Passenger Density Heatmap */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
          <h3 className="font-semibold text-[#17212B] mb-4 flex items-center gap-2">
            <Users size={18} className="text-blue-500" />
            Passenger Density Heatmap
          </h3>
          
          <div className="bg-slate-50 rounded-xl p-8 flex items-center justify-center relative border border-slate-100">
            {/* Bus Outline */}
            <div className={`${selectedVehicle.type === 'School van' ? 'w-56 h-[340px]' : 'w-72 h-[440px]'} border-4 border-slate-300 rounded-[3rem] relative bg-white shadow-inner transition-all duration-300`}>
              {/* Driver Seat */}
              <div className="absolute top-6 right-6 w-8 h-8 rounded bg-slate-200"></div>
              {/* Steering Wheel */}
              <div className="absolute top-4 right-6 w-8 h-2 rounded-full bg-slate-400"></div>
              
              {/* Door Zone Highlight */}
              <div className={`absolute top-20 left-0 w-16 h-24 border-r-2 border-dashed transition-colors duration-500 ${
              sensors.doorDensity === 'High' ? 'bg-red-100/50 border-red-400' :
              sensors.doorDensity === 'Moderate' ? 'bg-amber-100/50 border-amber-400' :
              'bg-blue-50/30 border-blue-200'}`
              }>
                <div className="absolute -left-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-400 -rotate-90 tracking-widest">DOOR</div>
              </div>

              <SeatHeatmap vehicle={selectedVehicle} occupancy={sensors.occupancy} level={level} />
            </div>
          </div>
          <div className="text-center mt-3"><p className="text-sm font-semibold text-slate-700">{selectedVehicle.manufacturer} {selectedVehicle.model}</p><p className="text-xs text-slate-400">{selectedVehicle.seatLayout.left} + {selectedVehicle.seatLayout.right} seating · {selectedVehicle.seatLayout.rows} rows · {selectedVehicle.capacity} seats</p></div>
          
          <div className="flex justify-center gap-6 mt-4 text-sm font-medium text-slate-500">
            <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-green-400"></div> Safe</span>
            <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-amber-400"></div> Moderate</span>
            <span className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500"></div> Crowded</span>
          </div>
        </div>

        {/* Privacy-Aware Camera */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col">
          <h3 className="font-semibold text-[#17212B] mb-4 flex items-center gap-2">
            <Camera size={18} className="text-blue-500" />
            Privacy-Aware Camera Access
          </h3>
          
          <div className="flex-1 bg-slate-900 rounded-xl overflow-hidden relative flex flex-col items-center justify-center border border-slate-800 p-6 text-center">
            
            {!adminCameraViewing &&
            <>
                <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${cameraState === 'AVAILABLE' ? 'bg-red-900/50 text-red-400' : 'bg-slate-800 text-blue-400'}`}>
                  {cameraState === 'AVAILABLE' ? <AlertTriangle size={32} /> : <Eye size={32} />}
                </div>
                <h4 className={`text-lg font-bold mb-2 ${cameraState === 'AVAILABLE' ? 'text-red-400' : 'text-white'}`}>
                  {cameraState === 'AVAILABLE' ? 'Safety Event Detected' : 'Admin Live View Available'}
                </h4>
                <p className="text-slate-400 text-sm max-w-sm mb-4">
                  Authorized administrators may view the live cabin feed at any time. Every session is time-limited and added to the audit log.
                </p>
                <label className="w-full max-w-sm text-left mb-4">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1.5"><ClipboardCheck size={13} /> Access purpose</span>
                  <select value={accessReason} onChange={(e) => setAccessReason(e.target.value)} className="w-full px-3 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option>Routine safety supervision</option>
                    <option>Investigating safety alert</option>
                    <option>Passenger welfare check</option>
                    <option>Incident verification</option>
                  </select>
                </label>
                <button
                onClick={handleCameraRequest}
                className={`px-6 py-3 text-white rounded-lg font-semibold shadow-lg transition-colors flex items-center gap-2 ${cameraState === 'AVAILABLE' ? 'bg-red-600 hover:bg-red-500' : 'bg-[#176B87] hover:bg-[#12546b]'}`}>
                
                  <Unlock size={18} /> Open Live Camera
                </button>
              </>
            }

            {adminCameraViewing &&
            <div className="absolute inset-0 bg-slate-800 flex flex-col">
                <div className="p-3 bg-black/50 flex justify-between items-center text-xs font-mono text-white">
                  <span className="flex items-center gap-2 text-red-400 font-bold"><div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div> LIVE</span>
                  <span>{selectedVehicle.id} • Prototype Simulated Stream</span>
                  <span className="text-slate-300 tabular-nums">Admin session: {mmss}</span>
                </div>
                <div className="flex-1 relative bg-black">
                  {selectedVehicle.id === 'BUS-01' ?
                    <iframe
                      src="http://192.168.0.53:8889/bus01"
                      title="BUS-01 live camera"
                      width="100%"
                      height="100%"
                      allow="autoplay; fullscreen"
                      style={{ border: 0, position: 'absolute', inset: 0 }} /> :
                    <div className="absolute inset-0 flex items-center justify-center"><Video size={48} className="text-slate-700" /><p className="absolute bottom-3 text-xs text-slate-500">No stream URL configured for {selectedVehicle.id}</p></div>}
                </div>
                <div className="p-3 bg-black/50 text-xs text-slate-400 flex justify-between items-center">
                  <span className="truncate mr-3">Authorized: Transport Admin • {accessReason} • Audit logging active</span>
                  <button onClick={revokeCamera} className="px-3 py-1 rounded bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors font-medium">
                    End access
                  </button>
                </div>
              </div>
            }

          </div>
        </div>

      </div>
    </div>);

}

function BreakdownItem({ label, value }: {label: string;value: number;}) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-slate-600">{label}</span>
      <span className="font-semibold text-slate-800">+{value}</span>
    </div>);

}

function SensorItem({ label, value, highlight = false }: {label: string;value: string | number;highlight?: boolean;}) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-slate-50 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={`font-semibold ${highlight ? 'text-amber-600' : 'text-slate-800'}`}>{value}</span>
    </div>);

}

function SeatHeatmap({ vehicle, occupancy, level }: {vehicle: ReturnType<typeof useAppContext>['vehicles'][number];occupancy: number;level: string}) {
  const { left, right, rows } = vehicle.seatLayout;
  let seatIndex = 0;
  const seat = () => {
    const index = seatIndex++;
    let color = 'bg-slate-100 border-slate-200';
    if (index < occupancy) {
      color = 'bg-green-400 border-green-500 shadow-sm shadow-green-200';
      if (level === 'MODERATE' && index % 3 === 0) color = 'bg-amber-400 border-amber-500 shadow-sm shadow-amber-200';
      if ((level === 'HIGH' || level === 'CRITICAL') && index % 2 === 0) color = 'bg-red-500 border-red-600 shadow-sm shadow-red-200';
    }
    return <span key={index} title={`Seat ${index + 1}${index < occupancy ? ' · occupied' : ' · empty'}`} className={`w-5 h-6 rounded-md border transition-colors duration-500 ${color}`} />;
  };

  const regularSeats = (left + right) * rows;
  const remaining = Math.max(0, vehicle.capacity - regularSeats);
  return <div className="absolute top-20 bottom-7 left-8 right-5 flex flex-col justify-end gap-1.5 overflow-hidden">{Array.from({ length: rows }).map((_, row) => <div key={row} className="flex justify-between items-center"><div className="flex gap-1">{Array.from({ length: left }).map(() => seat())}</div><span className="text-[7px] text-slate-300 uppercase">aisle</span><div className="flex gap-1">{Array.from({ length: right }).map(() => seat())}</div></div>)}{remaining > 0 && <div className="flex justify-center gap-1 pt-1 border-t border-dashed border-slate-200">{Array.from({ length: remaining }).map(() => seat())}</div>}</div>;
}
