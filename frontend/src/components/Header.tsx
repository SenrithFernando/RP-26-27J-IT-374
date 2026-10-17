import { useState } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { Siren } from 'lucide-react';
import { EmergencyCallPanel } from './EmergencyCallPanel';

export function Header() {
  const { tripState, emergency, safetyState } = useAppContext();
  const formattedDate = new Date('2026-08-24T08:00:00').toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  });
  const [showEmergencyCalls, setShowEmergencyCalls] = useState(false);

  const status = emergency.active && emergency.driverPhase !== 'SAFE' ?
  { label: 'Emergency active', tone: 'bg-red-100 text-red-700' } :
  safetyState.level !== 'LOW' ?
  { label: `Safety ${safetyState.level.toLowerCase()}`, tone: 'bg-amber-100 text-amber-800' } :
  { label: 'All systems normal', tone: 'bg-green-100 text-green-700' };

  return (
    <header className="bg-white border-b border-slate-200 px-8 py-5 flex justify-between items-center sticky top-0 z-20">
      <div>
        <h2 className="text-xl font-semibold text-[#17212B]">Good Morning, Transport Admin</h2>
        <p className="text-sm text-slate-500 mt-1">{formattedDate}</p>
      </div>
      <div className="flex items-center gap-4">
        <button onClick={() => setShowEmergencyCalls(true)} className="px-3 py-2 rounded-lg bg-red-600 text-white text-sm font-bold flex items-center gap-2 hover:bg-red-700 shadow-sm"><Siren size={17} /> Emergency</button>
        <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-slate-100 text-slate-600">
          Trip: {tripState === 'MORNING' ? 'Morning pickup' : tripState === 'AFTERNOON' ? 'Afternoon drop-off' : tripState === 'ENDED' ? 'Ended' : 'Idle'}
        </span>
        <span className={`text-xs font-medium px-3 py-1.5 rounded-full ${status.tone}`}>{status.label}</span>
        <span className="w-10 h-10 rounded-full bg-[#176B87] text-white flex items-center justify-center font-semibold">TA</span>
      </div>
      {showEmergencyCalls && <EmergencyCallPanel context="Transport Admin · SafeRide-LK fleet" onClose={() => setShowEmergencyCalls(false)} />}
    </header>);

}
