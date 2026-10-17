import { useAppContext } from '../contexts/AppContext';
import { Sidebar } from '../components/Sidebar';
import { Header } from '../components/Header';
import { Bus, Users, AlertTriangle, ShieldAlert, Navigation } from 'lucide-react';
import { SafetyMonitoring } from './SafetyMonitoring';
import { RouteOptimization } from './RouteOptimization';
import { IncidentMonitoring } from './IncidentMonitoring';
import { StudentsPage } from './StudentsPage';
import { LiveFleetPage } from './LiveFleetPage';
import { VehiclesPage, DriversPage, NotificationsPage, SettingsPage } from './FleetAdminPages';

export function AdminDashboard() {
  const { activeTab } = useAppContext();

  return (
    <div className="flex min-h-screen bg-[#F7F9FC]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 p-8 overflow-y-auto">
          {activeTab === 'Overview' && <Overview />}
          {activeTab === 'Live Fleet' && <LiveFleetPage />}
          {activeTab === 'Students' && <StudentsPage />}
          {activeTab === 'Vehicles' && <VehiclesPage />}
          {activeTab === 'Drivers' && <DriversPage />}
          {activeTab === 'Routes' && <RouteOptimization />}
          {activeTab === 'Safety' && <SafetyMonitoring />}
          {activeTab === 'Incidents' && <IncidentMonitoring />}
          {activeTab === 'Notifications' && <NotificationsPage />}
          {activeTab === 'Settings' && <SettingsPage />}
        </main>
      </div>
    </div>);

}

function Overview() {
  const { vehicles, students, safetyState, emergency, notifications, routeState, setActiveTab } = useAppContext();

  const activeVehicles = vehicles.filter((v) => v.status === 'ACTIVE').length;
  const studentsTravelling = students.filter((s) => s.status === 'BOARDED').length;
  const safetyAlerts = (safetyState.level === 'LOW' ? 0 : 1) + (routeState.deviationAlert ? 1 : 0);
  const incidents = emergency.active && emergency.driverPhase !== 'SAFE' ? 1 : 0;

  const riskCounts = {
    LOW: vehicles.filter((v) => v.risk === 'LOW').length,
    MODERATE: vehicles.filter((v) => v.risk === 'MODERATE').length,
    HIGH: 0,
    CRITICAL: 0
  };
  if (safetyState.level === 'HIGH' || safetyState.level === 'CRITICAL') {
    riskCounts.LOW = Math.max(0, riskCounts.LOW - 1);
    riskCounts[safetyState.level] += 1;
  }

  const recent = notifications.slice(0, 5);

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="Active Vehicles" value={activeVehicles} icon={Bus} color="text-blue-600" bg="bg-blue-50" onClick={() => setActiveTab('Live Fleet')} />
        <StatCard title="Students Travelling" value={studentsTravelling} icon={Users} color="text-teal-600" bg="bg-teal-50" onClick={() => setActiveTab('Students')} />
        <StatCard title="Active Safety Alerts" value={safetyAlerts} icon={AlertTriangle} color="text-amber-600" bg="bg-amber-50" onClick={() => setActiveTab('Safety')} />
        <StatCard title="Emergency Incidents" value={incidents} icon={ShieldAlert} color="text-red-600" bg="bg-red-50" onClick={() => setActiveTab('Incidents')} />
      </div>

      {emergency.active && emergency.driverPhase !== 'SAFE' &&
      <button
        onClick={() => setActiveTab('Incidents')}
        className="w-full mb-8 text-left bg-red-600 text-white rounded-xl p-5 flex items-center gap-4 shadow-md hover:bg-red-700 transition-colors">
        
          <AlertTriangle size={26} />
          <div className="flex-1">
            <p className="font-bold">{emergency.severity} impact detected — {emergency.incidentId}</p>
            <p className="text-red-100 text-sm">Escalation stage: {emergency.stage.replace(/_/g, ' ')}</p>
          </div>
          <span className="text-sm font-semibold underline">Open incident</span>
        </button>
      }

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[400px] overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center">
              <h3 className="font-semibold text-[#17212B]">Live Fleet Map</h3>
              <button onClick={() => setActiveTab('Live Fleet')} className="text-xs font-medium text-[#176B87] hover:underline">Open full map</button>
            </div>
            <div className="flex-1 bg-slate-50 relative">
              <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
              <div className="absolute top-[30%] left-[26%] flex flex-col items-center">
                <span className="bg-[#22C55E] text-white p-2 rounded-full shadow-lg"><Bus size={18} /></span>
                <span className="mt-1 text-xs font-bold bg-white px-2 py-0.5 rounded shadow-sm">BUS-01</span>
              </div>
              <div className="absolute top-[54%] left-[62%] flex flex-col items-center">
                <span className="bg-[#F59E0B] text-white p-2 rounded-full shadow-lg"><Bus size={18} /></span>
                <span className="mt-1 text-xs font-bold bg-white px-2 py-0.5 rounded shadow-sm">VAN-02</span>
              </div>
              <div className="absolute bottom-4 left-4 text-xs text-slate-400 bg-white/80 px-2 py-1 rounded">Simulated GPS positions</div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h3 className="font-semibold text-[#17212B]">Active Trips</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-600 font-medium border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3">Vehicle</th>
                    <th className="px-6 py-3">Route</th>
                    <th className="px-6 py-3">Students</th>
                    <th className="px-6 py-3">Next Stop</th>
                    <th className="px-6 py-3">ETA</th>
                    <th className="px-6 py-3">Risk</th>
                    <th className="px-6 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {vehicles.map((v) => {
                    const onboard = students.filter((s) => s.assignedVehicle === v.id && (s.status === 'BOARDED' || s.status === 'DROPPED_OFF')).length;
                    const risk = v.id === 'BUS-01' ? safetyState.level : v.risk;
                    return (
                      <tr key={v.id} className="hover:bg-slate-50">
                        <td className="px-6 py-4 font-medium text-[#17212B]">{v.id}</td>
                        <td className="px-6 py-4 text-slate-600">Morning Pickup</td>
                        <td className="px-6 py-4 text-slate-600">{onboard} / {v.capacity}</td>
                        <td className="px-6 py-4 text-slate-600">{v.location}</td>
                        <td className="px-6 py-4 text-slate-600">07:43 AM</td>
                        <td className="px-6 py-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                          risk === 'LOW' ? 'bg-green-100 text-green-700' :
                          risk === 'MODERATE' ? 'bg-amber-100 text-amber-700' :
                          risk === 'HIGH' ? 'bg-orange-100 text-orange-700' :
                          'bg-red-100 text-red-700'}`
                          }>
                            {risk}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="flex items-center gap-1.5 text-blue-600 font-medium">
                            <Navigation size={14} /> Active
                          </span>
                        </td>
                      </tr>);

                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="font-semibold text-[#17212B] mb-4">Fleet Risk Overview</h3>
            <div className="space-y-4">
              <RiskBar label="Low" count={riskCounts.LOW} total={vehicles.length} color="bg-[#22C55E]" />
              <RiskBar label="Moderate" count={riskCounts.MODERATE} total={vehicles.length} color="bg-[#F59E0B]" />
              <RiskBar label="High" count={riskCounts.HIGH} total={vehicles.length} color="bg-[#F97316]" />
              <RiskBar label="Critical" count={riskCounts.CRITICAL} total={vehicles.length} color="bg-[#DC2626]" />
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-[#17212B]">Recent Activity</h3>
              <button onClick={() => setActiveTab('Notifications')} className="text-xs font-medium text-[#176B87] hover:underline">View all</button>
            </div>
            <ol className="space-y-4">
              {recent.map((n) =>
              <li key={n.id} className="flex gap-3">
                  <span className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                n.type === 'success' ? 'bg-green-500' :
                n.type === 'warning' ? 'bg-amber-500' :
                n.type === 'error' ? 'bg-red-500' : 'bg-blue-500'}`
                } />
                  <div>
                    <p className="text-sm text-slate-700 leading-snug">{n.message}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{n.time}</p>
                  </div>
                </li>
              )}
            </ol>
          </div>
        </div>
      </div>
    </>);

}

function StatCard({ title, value, icon: Icon, color, bg, onClick }: any) {
  return (
    <button onClick={onClick} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex items-center gap-4 text-left hover:border-[#2D9CDB] transition-colors">
      <span className={`w-12 h-12 rounded-full ${bg} ${color} flex items-center justify-center shrink-0`}>
        <Icon size={24} />
      </span>
      <span>
        <span className="text-sm font-medium text-slate-500 block">{title}</span>
        <span className="text-2xl font-bold text-[#17212B]">{value}</span>
      </span>
    </button>);

}

function RiskBar({ label, count, total, color }: any) {
  const percentage = total > 0 ? count / total * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="text-slate-600 font-medium">{label}</span>
        <span className="text-slate-900 font-bold">{count}</span>
      </div>
      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-[width] duration-300 ease-out`} style={{ width: `${percentage}%` }} />
      </div>
    </div>);

}