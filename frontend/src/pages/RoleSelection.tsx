import { useAppContext } from '../contexts/AppContext';
import { Shield, Bus, Users, Stethoscope, ShieldAlert, Flame, Building2, Settings } from 'lucide-react';
import { BrandLogo } from '../components/BrandLogo';

export function RoleSelection() {
  const { setRole } = useAppContext();

  const roles = [
  { id: 'ADMIN', label: 'Administrator', icon: Shield, color: 'bg-blue-600' },
  { id: 'DRIVER', label: 'Driver', icon: Bus, color: 'bg-teal-600' },
  { id: 'PARENT', label: 'Parent', icon: Users, color: 'bg-indigo-600' },
  { id: 'EMS', label: 'EMS / Doctor', icon: Stethoscope, color: 'bg-red-600' },
  { id: 'POLICE', label: 'Police', icon: ShieldAlert, color: 'bg-blue-800' },
  { id: 'FIRE', label: 'Fire Brigade', icon: Flame, color: 'bg-orange-600' },
  { id: 'HOSPITAL', label: 'Hospital', icon: Building2, color: 'bg-rose-600' }];


  return (
    <div className="min-h-screen bg-[#F7F9FC] flex flex-col items-center justify-center p-6">
      <div className="max-w-4xl w-full">
        <div className="text-center mb-12">
          <BrandLogo className="w-28 h-28 mx-auto mb-5 rounded-[1.75rem] shadow-lg" />
          <h1 className="text-4xl font-bold text-[#176B87] mb-4">SafeRide-LK</h1>
          <p className="text-lg text-slate-600">A Privacy-Aware IoT Framework for Multi-Vehicle School Transport Safety</p>
          <p className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-amber-800 bg-amber-100 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Research prototype · all data and sensor events are simulated
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
          <h2 className="text-2xl font-semibold text-[#17212B] mb-8 text-center">Choose Interface</h2>
          
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
            {roles.map((r) =>
            <button
              key={r.id}
              onClick={() => setRole(r.id as any)}
              className="flex flex-col items-center p-6 rounded-xl border border-slate-100 hover:border-blue-200 hover:bg-blue-50 transition-all group">
              
                <div className={`w-14 h-14 rounded-full ${r.color} text-white flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <r.icon size={28} />
                </div>
                <span className="font-medium text-slate-700">{r.label}</span>
              </button>
            )}
          </div>

          <div className="pt-8 border-t border-slate-100 flex justify-center">
            <button
              onClick={() => setRole('DEMO_CONTROL')}
              className="flex items-center gap-2 px-6 py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors font-medium">
              
              <Settings size={20} />
              Open Demo Control Center
            </button>
          </div>
        </div>
      </div>
    </div>);

}
