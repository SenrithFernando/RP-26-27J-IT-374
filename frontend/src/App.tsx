import { AppProvider, useAppContext } from './contexts/AppContext';
import { RoleSelection } from './pages/RoleSelection';
import { AdminDashboard } from './pages/AdminDashboard';
import { DemoControlCenter } from './pages/DemoControlCenter';
import { DriverDashboard } from './pages/DriverDashboard';
import { ParentDashboard } from './pages/ParentDashboard';
import { EmergencyResponderDashboard } from './pages/EmergencyResponderDashboard';

function AppContent() {
  const { role, setRole } = useAppContext();

  if (!role) return <RoleSelection />;
  if (role === 'DEMO_CONTROL') return <DemoControlCenter />;
  if (role === 'ADMIN') return <AdminDashboard />;
  if (role === 'DRIVER') return <DriverDashboard />;
  if (role === 'PARENT') return <ParentDashboard />;
  if (role === 'EMS' || role === 'POLICE' || role === 'FIRE' || role === 'HOSPITAL') {
    return <EmergencyResponderDashboard role={role} />;
  }

  // Fallback for other roles not yet implemented
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 p-8 text-center">
      <h1 className="text-2xl font-bold text-slate-800 mb-4">{role} Dashboard</h1>
      <p className="text-slate-600 mb-8">This interface is planned for the next implementation phase.</p>
      <button
        onClick={() => setRole(null)}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium">
        
        Back to Role Selection
      </button>
    </div>);

}

export function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>);

}