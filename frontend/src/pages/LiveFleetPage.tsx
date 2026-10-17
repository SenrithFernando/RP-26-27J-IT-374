import { useState, useEffect } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { Bus, X, Gauge, Users, Route as RouteIcon, MapPin, Satellite } from 'lucide-react';

export function LiveFleetPage() {
  const { vehicles, students, safetyState, routeState } = useAppContext();
  const [selected, setSelected] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 2000);
    return () => clearInterval(t);
  }, []);

  const positions: Record<string, {top: string;left: string;}> = {
    'BUS-01': { top: `${32 + tick % 3 * 1.5}%`, left: `${28 + tick % 4 * 1.2}%` },
    'VAN-02': { top: `${54 - tick % 3 * 1.2}%`, left: `${58 + tick % 3 * 1.5}%` }
  };

  const vehicle = vehicles.find((v) => v.id === selected);
  const onboard = students.filter((s) => s.assignedVehicle === selected && (s.status === 'BOARDED' || s.status === 'DROPPED_OFF')).length;

  return (
    <div className="h-[calc(100vh-9rem)] flex gap-6">
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center">
          <h2 className="font-semibold text-[#17212B]">Live Fleet</h2>
          <span className="text-xs font-medium px-2 py-1 bg-slate-100 text-slate-600 rounded flex items-center gap-1.5">
            <Satellite size={12} /> Simulated GPS feed
          </span>
        </div>
        <div className="flex-1 relative bg-slate-50">
          <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)', backgroundSize: '24px 24px' }} />

          {/* School markers */}
          <Marker top="22%" left="62%" label="Horizon College" tone="school" />
          <Marker top="70%" left="38%" label="Central College" tone="school" />
          <Marker top="46%" left="18%" label="Malabe pickup" tone="stop" />

          {vehicles.map((v) =>
          <button
            key={v.id}
            onClick={() => setSelected(v.id)}
            style={positions[v.id]}
            className="absolute flex flex-col items-center transition-[top,left] duration-[1800ms] ease-out focus:outline-none">
            
              <span className={`p-2 rounded-full shadow-lg text-white ${v.risk === 'LOW' ? 'bg-[#22C55E]' : v.risk === 'MODERATE' ? 'bg-[#F59E0B]' : 'bg-[#DC2626]'} ${selected === v.id ? 'ring-4 ring-blue-200' : ''}`}>
                <Bus size={18} />
              </span>
              <span className="mt-1 text-xs font-bold bg-white px-2 py-0.5 rounded shadow-sm">{v.id}</span>
            </button>
          )}
        </div>
      </div>

      {vehicle &&
      <aside className="w-80 bg-white rounded-xl border border-slate-200 shadow-sm p-6 overflow-y-auto">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-lg font-bold text-[#17212B]">{vehicle.id}</h3>
              <p className="text-sm text-slate-500">{vehicle.driver}</p>
            </div>
            <button onClick={() => setSelected(null)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500"><X size={16} /></button>
          </div>

          <dl className="space-y-3 text-sm">
            <Row icon={Gauge} label="Speed" value={`${vehicle.speed} km/h`} />
            <Row icon={Users} label="Students onboard" value={`${onboard} / ${vehicle.capacity}`} />
            <Row icon={RouteIcon} label="Current route" value="Morning pickup" />
            <Row icon={MapPin} label="Next stop" value={vehicle.location} />
            <Row icon={MapPin} label="ETA" value="07:43 AM" />
            <Row icon={Gauge} label="Risk score" value={vehicle.id === 'BUS-01' ? `${safetyState.score} (${safetyState.level})` : '32 (MODERATE)'} />
            <Row icon={Satellite} label="Last GPS update" value="2 s ago" />
          </dl>

          {routeState.deviationAlert?.vehicleId === vehicle.id &&
        <div className="mt-6 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              Route deviation — {routeState.deviationAlert.distanceFromRoute} km off planned path.
            </div>
        }
        </aside>
      }
    </div>);

}

function Marker({ top, left, label, tone }: {top: string;left: string;label: string;tone: 'school' | 'stop';}) {
  return (
    <div className="absolute flex flex-col items-center" style={{ top, left }}>
      <span className={`w-3 h-3 rounded-full ring-4 ${tone === 'school' ? 'bg-[#176B87] ring-[#176B87]/15' : 'bg-slate-400 ring-slate-300/40'}`} />
      <span className="mt-1 text-[11px] font-medium text-slate-500 bg-white/80 px-1.5 rounded">{label}</span>
    </div>);

}

function Row({ icon: Icon, label, value }: {icon: any;label: string;value: string;}) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-slate-50 last:border-0">
      <dt className="text-slate-500 flex items-center gap-2"><Icon size={14} /> {label}</dt>
      <dd className="font-semibold text-slate-800">{value}</dd>
    </div>);

}