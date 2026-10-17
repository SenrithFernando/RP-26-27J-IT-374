import { useAppContext } from '../contexts/AppContext';
import { LayoutDashboard, Map, Users, Bus, UserCircle, Route, ShieldCheck, AlertTriangle, Bell, Settings, LogOut, SlidersHorizontal } from 'lucide-react';
import { BrandLogo } from './BrandLogo';

export function Sidebar() {
  const { activeTab, setActiveTab, setRole, demoMode, notifications, emergency, safetyState } = useAppContext();

  const navItems = [
  { id: 'Overview', icon: LayoutDashboard },
  { id: 'Live Fleet', icon: Map },
  { id: 'Students', icon: Users },
  { id: 'Vehicles', icon: Bus },
  { id: 'Drivers', icon: UserCircle },
  { id: 'Routes', icon: Route },
  { id: 'Safety', icon: ShieldCheck, badge: safetyState.level !== 'LOW' ? '!' : undefined },
  { id: 'Incidents', icon: AlertTriangle, badge: emergency.active && emergency.driverPhase !== 'SAFE' ? '!' : undefined },
  { id: 'Notifications', icon: Bell, badge: notifications.length > 0 ? String(notifications.length) : undefined },
  { id: 'Settings', icon: Settings }];


  return (
    <div className="w-64 bg-white border-r border-slate-200 flex flex-col h-screen sticky top-0 shrink-0">
      <div className="p-6 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <BrandLogo className="h-12 w-12 rounded-xl shadow-sm" />
          <div>
            <h1 className="text-xl font-bold text-[#176B87] leading-tight">SafeRide-LK</h1>
            <p className="text-[11px] text-slate-500 mt-0.5">School transport safety</p>
          </div>
        </div>
        {demoMode &&
        <span className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            Demo Mode
          </span>
        }
      </div>

      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-3">
          {navItems.map((item) =>
          <li key={item.id}>
              <button
              onClick={() => setActiveTab(item.id)}
              aria-current={activeTab === item.id ? 'page' : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === item.id ?
              'bg-[#176B87] text-white' :
              'text-slate-600 hover:bg-slate-50 hover:text-[#176B87]'}`
              }>
              
                <item.icon size={18} />
                <span className="flex-1 text-left">{item.id}</span>
                {item.badge &&
              <span className={`px-1.5 min-w-[20px] text-[11px] font-bold rounded-full ${
              activeTab === item.id ? 'bg-white/20 text-white' : 'bg-red-100 text-red-600'}`
              }>
                    {item.badge}
                  </span>
              }
              </button>
            </li>
          )}
        </ul>
      </nav>

      <div className="p-4 border-t border-slate-100 space-y-1">
        <button
          onClick={() => setRole('DEMO_CONTROL')}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-[#176B87] transition-colors">
          
          <SlidersHorizontal size={18} />
          Demo Control Center
        </button>
        <button
          onClick={() => setRole(null)}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors">
          
          <LogOut size={18} />
          Switch Role
        </button>
      </div>
    </div>);

}
