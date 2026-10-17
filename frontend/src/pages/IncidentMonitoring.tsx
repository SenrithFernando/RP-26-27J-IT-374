import { useAppContext } from '../contexts/AppContext';
import { ShieldAlert, Activity, AlertTriangle, CheckCircle2, Clock, MapPin, ActivitySquare, Shield } from 'lucide-react';

export function IncidentMonitoring() {
  const { emergency, students } = useAppContext();
  const onboard = students.filter((s) => s.assignedVehicle === 'BUS-01' && s.status === 'BOARDED').length;

  if (!emergency.active) {
    return (
      <div className="space-y-6 max-w-6xl mx-auto">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-[#17212B]">Crash & Incident Monitoring</h2>
            <p className="text-slate-500">DMA-based multi-sensor crash detection</p>
          </div>
          <div className="bg-green-50 text-green-700 px-4 py-2 rounded-lg border border-green-200 shadow-sm font-bold flex items-center gap-2">
            <CheckCircle2 size={18} /> NORMAL
          </div>
        </div>

        <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm flex flex-col items-center justify-center min-h-[400px] text-center">
          <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-6 border-4 border-slate-100">
            <ShieldAlert size={32} className="text-slate-400" />
          </div>
          <h3 className="text-xl font-bold text-slate-700 mb-2">No Active Incidents</h3>
          <p className="text-slate-500 max-w-md mb-8">All vehicle telemetry is within normal parameters. The DMA data buffer is actively monitoring for impact signatures.</p>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-3xl">
            <SensorBadge label="Accelerometer" value="0.12 G" />
            <SensorBadge label="Gyroscope" value="3.1°/s" />
            <SensorBadge label="Impact Sensor" value="Normal" />
            <SensorBadge label="DMA Buffer" value="Active" />
          </div>
          <p className="text-[10px] text-slate-400 mt-8 uppercase tracking-wider">Simulated Prototype Sensor Values</p>
        </div>
      </div>);

  }

  const { crashData, severity, stage, timeline, driverPhase } = emergency;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="bg-red-600 text-white p-6 rounded-2xl shadow-lg flex flex-col md:flex-row justify-between items-center gap-4 animate-in slide-in-from-top-4">
        <div className="flex items-center gap-4">
          <div className="bg-white/20 p-3 rounded-full animate-pulse">
            <AlertTriangle size={32} />
          </div>
          <div>
            <h2 className="text-2xl font-bold">{severity} IMPACT DETECTED</h2>
            <p className="text-red-100">Incident ID: {emergency.incidentId} • BUS-01</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-red-200 text-sm font-medium">Time of Impact</p>
          <p className="text-xl font-bold">{crashData?.time}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Telemetry & Status */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
            <h3 className="font-semibold text-[#17212B] mb-6 flex items-center gap-2">
              <ActivitySquare size={18} className="text-red-500" /> Impact Telemetry Snapshot
            </h3>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <MetricCard label="Peak G-Force" value={`${crashData?.peakG} G`} danger />
              <MetricCard label="Vehicle Roll" value={`${crashData?.vehicleRoll}°`} danger={crashData!.vehicleRoll > 45} />
              <MetricCard label="Impact Pressure" value={`${crashData?.impactPressure}%`} danger />
              <MetricCard label="Classification" value={crashData?.classification} danger />
            </div>

            <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 flex items-start gap-4">
              <MapPin className="text-slate-400 shrink-0 mt-1" />
              <div>
                <p className="text-sm font-medium text-slate-500">Last Known Location</p>
                <p className="font-bold text-slate-800">{crashData?.location}</p>
                <p className="text-xs text-slate-400 mt-1">Passengers onboard: {onboard} • Driver: D. Perera</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
            <h3 className="font-semibold text-[#17212B] mb-4 flex items-center gap-2">
              <Shield size={18} className="text-blue-500" /> Driver Response Status
            </h3>
            
            <div className="flex items-center gap-4 p-4 rounded-xl border border-slate-100 bg-slate-50">
              {driverPhase === 'COUNTDOWN' &&
              <>
                  <div className="w-12 h-12 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center font-bold text-xl shrink-0">
                    {emergency.driverCountdown}
                  </div>
                  <div>
                    <p className="font-bold text-amber-700">Awaiting Driver Override</p>
                    <p className="text-sm text-amber-600/80">If no response, emergency escalation begins automatically.</p>
                  </div>
                </>
              }
              {driverPhase === 'NONE' &&
              <>
                  <div className="w-12 h-12 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center shrink-0">
                    <Shield size={24} />
                  </div>
                  <div>
                    <p className="font-bold text-slate-700">No driver override required</p>
                    <p className="text-sm text-slate-500">Impact classified below the escalation threshold — logged for review only.</p>
                  </div>
                </>
              }
              {driverPhase === 'SAFE' &&
              <>
                  <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center shrink-0">
                    <CheckCircle2 size={24} />
                  </div>
                  <div>
                    <p className="font-bold text-green-700">Driver Confirmed Safe</p>
                    <p className="text-sm text-green-600/80">Emergency escalation cancelled.</p>
                  </div>
                </>
              }
              {driverPhase === 'TIMEOUT' &&
              <>
                  <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                    <Clock size={24} />
                  </div>
                  <div>
                    <p className="font-bold text-red-700">Driver Unresponsive</p>
                    <p className="text-sm text-red-600/80">Timeout reached. Escalation protocols activated.</p>
                  </div>
                </>
              }
              {driverPhase === 'HELP_REQUESTED' &&
              <>
                  <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0">
                    <AlertTriangle size={24} />
                  </div>
                  <div>
                    <p className="font-bold text-red-700">Driver Requested Help</p>
                    <p className="text-sm text-red-600/80">Immediate escalation protocols activated.</p>
                  </div>
                </>
              }
            </div>
          </div>
        </div>

        {/* Right Column: Escalation Timeline */}
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col h-full">
          <h3 className="font-semibold text-[#17212B] mb-6 flex items-center gap-2">
            <Activity size={18} className="text-red-500" /> Five-Stage Escalation
          </h3>
          
          <div className="flex-1 relative before:absolute before:inset-0 before:ml-[11px] before:-translate-x-px before:h-full before:w-0.5 before:bg-slate-100 space-y-6">
            {timeline.map((event, idx) =>
            <div key={idx} className="relative flex items-start gap-4">
                <div className="w-6 h-6 rounded-full bg-red-500 border-4 border-white shadow-sm flex items-center justify-center shrink-0 z-10"></div>
                <div className="pt-0.5">
                  <p className="text-xs font-bold text-red-500 mb-0.5">{event.time}</p>
                  <p className="font-medium text-slate-800 text-sm">{event.label}</p>
                </div>
              </div>
            )}
            
            {/* Pending states based on current stage */}
            {stage !== 'NONE' && stage !== 'HOSPITAL_ACK' && driverPhase !== 'SAFE' &&
            <div className="relative flex items-start gap-4 opacity-50">
                <div className="w-6 h-6 rounded-full bg-slate-200 border-4 border-white shadow-sm flex items-center justify-center shrink-0 z-10"></div>
                <div className="pt-0.5">
                  <p className="text-xs font-bold text-slate-400 mb-0.5">Pending</p>
                  <p className="font-medium text-slate-500 text-sm">
                    {stage === 'EMS_NOTIFIED' ? 'Awaiting EMS Acknowledgement' :
                  stage === 'POLICE_NOTIFIED' ? 'Awaiting Police Acknowledgement' :
                  stage === 'FIRE_NOTIFIED' ? 'Awaiting Fire Brigade Acknowledgement' :
                  stage === 'HOSPITAL_NOTIFIED' ? 'Awaiting Hospital Acknowledgement' : 'Next Stage'}
                  </p>
                </div>
              </div>
            }
          </div>
        </div>

      </div>
    </div>);

}

function SensorBadge({ label, value }: {label: string;value: string;}) {
  return (
    <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
      <p className="text-slate-400 text-xs mb-1">{label}</p>
      <p className="font-semibold text-slate-700">{value}</p>
    </div>);

}

function MetricCard({ label, value, danger = false }: {label: string;value: any;danger?: boolean;}) {
  return (
    <div className={`rounded-xl p-4 border ${danger ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'}`}>
      <p className={`text-xs mb-1 ${danger ? 'text-red-700/70' : 'text-slate-500'}`}>{label}</p>
      <p className={`text-xl font-bold ${danger ? 'text-red-700' : 'text-slate-800'}`}>{value}</p>
    </div>);

}