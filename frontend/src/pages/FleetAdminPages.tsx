import { PersistentNotifications } from '../components/PersistentNotifications';
import React, { useState } from 'react';
import { useAppContext } from '../contexts/AppContext';
import { Bus, User, Settings as SettingsIcon, CheckCircle2, AlertTriangle, Info, XCircle, X, Gauge, MapPin, Fuel, CalendarDays, Wrench, Satellite, Camera, ShieldCheck, Users, FileCheck2, ChevronRight, Plus, History, Phone, Mail, IdCard, HeartPulse, UserPlus, PhoneCall, PhoneOff } from 'lucide-react';
import { Assistant, Driver, Vehicle } from '../types';
import { VEHICLE_CATALOG } from '../data/vehicleCatalog';

export function VehiclesPage() {
  const { vehicles, setVehicles, students, setActiveTab, setSelectedVehicleId, vehicleCall, startVehicleCall, endVehicleCall, addNotification } = useAppContext();
  const [selected, setSelected] = useState<Vehicle | null>(null);
  const [showAddVehicle, setShowAddVehicle] = useState(false);

  const checkSafety = (vehicleId: string) => {
    setSelectedVehicleId(vehicleId);
    setActiveTab('Safety');
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex justify-between items-end gap-4 mb-6"><div><h2 className="text-2xl font-bold text-[#17212B] mb-1">Vehicles</h2><p className="text-slate-500">Fleet registry · model-specific seating layouts</p></div><button onClick={() => setShowAddVehicle(true)} className="px-4 py-2.5 bg-[#176B87] text-white rounded-lg font-semibold flex items-center gap-2 hover:bg-[#12546b]"><Plus size={17} /> Add vehicle</button></div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {vehicles.map((v) => {
          const assigned = students.filter((s) => s.assignedVehicle === v.id).length;
          const load = Math.round(assigned / v.capacity * 100);
          return (
            <button key={v.id} onClick={() => setSelected(v)} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 text-left hover:border-[#2D9CDB] hover:shadow-md transition-all group">
              <div className="flex justify-between items-start mb-5">
                <div className="flex items-center gap-3">
                  <span className="w-11 h-11 rounded-lg bg-blue-50 text-[#176B87] flex items-center justify-center"><Bus size={22} /></span>
                  <div>
                    <h3 className="font-bold text-[#17212B]">{v.id}</h3>
                    <p className="text-sm text-slate-500">{v.driver}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${v.risk === 'LOW' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{v.risk} RISK</span>
              </div>

              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1.5">
                  <span className="text-slate-500">Assigned load</span>
                  <span className="font-semibold text-slate-800">{assigned} / {v.capacity}</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${load > 90 ? 'bg-[#F97316]' : 'bg-[#176B87]'}`} style={{ width: `${Math.min(load, 100)}%` }} />
                </div>
              </div>

              <dl className="grid grid-cols-3 gap-3 text-sm">
                <Stat label="Status" value={v.status} />
                <Stat label="Speed" value={`${v.speed} km/h`} />
                <Stat label="Location" value={v.location} />
              </dl>
              <span className="mt-5 pt-4 border-t border-slate-100 text-sm font-semibold text-[#176B87] flex items-center justify-between">
                View all vehicle details <ChevronRight size={17} className="group-hover:translate-x-0.5 transition-transform" />
              </span>
            </button>);

        })}
      </div>
      {selected && <VehicleDetailPanel vehicle={selected} students={students.filter((student) => student.assignedVehicle === selected.id)} callStatus={vehicleCall?.vehicleId === selected.id ? vehicleCall.status : null} onCall={() => startVehicleCall(selected.id, 'ADMIN', 'Transport Admin')} onEndCall={() => endVehicleCall('Administrator ended the call')} onClose={() => setSelected(null)} onCheckSafety={() => checkSafety(selected.id)} />}
      {showAddVehicle && <AddVehicleModal vehicleCount={vehicles.length} onClose={() => setShowAddVehicle(false)} onSave={(vehicle) => {setVehicles((prev) => [...prev, vehicle]);addNotification({ role: 'ADMIN', message: `Vehicle added: ${vehicle.id} · ${vehicle.makeModel}.`, type: 'success' });setShowAddVehicle(false);}} />}
    </div>);

}

function AddVehicleModal({ vehicleCount, onClose, onSave }: {vehicleCount: number;onClose: () => void;onSave: (vehicle: Vehicle) => void}) {
  const [type, setType] = useState<'School van' | 'School bus'>('School van');
  const [manufacturer, setManufacturer] = useState(VEHICLE_CATALOG['School van'][0].manufacturer);
  const availableModels = VEHICLE_CATALOG[type].filter((item) => item.manufacturer === manufacturer);
  const [model, setModel] = useState(availableModels[0].model);
  const [registration, setRegistration] = useState('WP PA-');
  const [year, setYear] = useState('2026');
  const [color, setColor] = useState('White');
  const selectedPreset = VEHICLE_CATALOG[type].find((item) => item.manufacturer === manufacturer && item.model === model) || VEHICLE_CATALOG[type][0];

  const changeType = (value: string) => { const nextType = value as typeof type; const first = VEHICLE_CATALOG[nextType][0]; setType(nextType); setManufacturer(first.manufacturer); setModel(first.model); };
  const changeManufacturer = (value: string) => { const first = VEHICLE_CATALOG[type].find((item) => item.manufacturer === value)!; setManufacturer(value); setModel(first.model); };
  const save = () => {
    const prefix = type === 'School bus' ? 'BUS' : 'VAN';
    onSave({ id: `${prefix}-${(vehicleCount + 1).toString().padStart(2, '0')}`, driver: 'Not assigned', capacity: selectedPreset.seats, students: 0, status: 'INACTIVE', risk: 'LOW', speed: 0, location: 'Depot', registrationNumber: registration, type, manufacturer, model, makeModel: `${manufacturer} ${model}`, year: Number(year), color, fuelType: 'Diesel', mileageKm: 0, insuranceExpiry: 'Not provided', revenueLicenceExpiry: 'Not provided', lastService: 'New vehicle', nextServiceKm: 5000, gpsDeviceId: `GPS-LK-${1000 + vehicleCount + 1}`, cameraCount: type === 'School bus' ? 3 : 2, emergencyKit: 'Inspection pending', seatLayout: selectedPreset.layout });
  };

  const manufacturers = Array.from(new Set(VEHICLE_CATALOG[type].map((item) => item.manufacturer)));
  return <ModalShell title="Add vehicle" subtitle="Choose a van or bus model and its matching seat arrangement." onClose={onClose}><div className="grid grid-cols-1 sm:grid-cols-2 gap-4"><CrewField label="Vehicle type" value={type} onChange={changeType} options={[{label:'Van',value:'School van'},{label:'Bus',value:'School bus'}]} /><CrewField label="Company / manufacturer" value={manufacturer} onChange={changeManufacturer} options={manufacturers.map((value) => ({label:value,value}))} /><CrewField label="Vehicle model" value={model} onChange={setModel} options={availableModels.map((item) => ({label:`${item.model} · ${item.seats} seats`,value:item.model}))} /><CrewField label="Number of seats" value={String(selectedPreset.seats)} onChange={() => {}} /><CrewField label="Registration number" value={registration} onChange={setRegistration} /><CrewField label="Manufactured year" value={year} onChange={setYear} type="number" /><CrewField label="Colour" value={color} onChange={setColor} /></div><div className="mt-5 p-4 bg-blue-50 border border-blue-100 rounded-xl"><p className="text-sm font-semibold text-blue-800">Seating arrangement</p><p className="text-xs text-blue-600 mt-1">{selectedPreset.layout.left} seats left + aisle + {selectedPreset.layout.right} seats right · {selectedPreset.layout.rows} rows · {selectedPreset.seats} passenger capacity</p></div><FormActions onClose={onClose} onSave={save} /></ModalShell>;
}

function VehicleDetailPanel({ vehicle, students, callStatus, onCall, onEndCall, onClose, onCheckSafety }: {vehicle: Vehicle;students: ReturnType<typeof useAppContext>['students'];callStatus: 'RINGING' | 'CONNECTED' | null;onCall: () => void;onEndCall: () => void;onClose: () => void;onCheckSafety: () => void;}) {
  const riskTone = vehicle.risk === 'LOW' ? 'bg-green-100 text-green-700' : vehicle.risk === 'MODERATE' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700';
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button aria-label="Close vehicle details" className="absolute inset-0 bg-slate-900/35" onClick={onClose} />
      <aside className="relative w-full max-w-2xl h-full bg-slate-50 shadow-2xl flex flex-col">
        <header className="bg-white border-b border-slate-200 p-6 flex justify-between items-start shrink-0">
          <div className="flex gap-4 items-center">
            <span className="w-14 h-14 rounded-xl bg-blue-50 text-[#176B87] flex items-center justify-center"><Bus size={28} /></span>
            <div>
              <div className="flex items-center gap-2"><h3 className="text-xl font-bold text-[#17212B]">{vehicle.id}</h3><span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${riskTone}`}>{vehicle.risk} RISK</span></div>
              <p className="text-sm text-slate-500 mt-1">{vehicle.registrationNumber} · {vehicle.makeModel}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"><X size={19} /></button>
        </header>

        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          <DetailSection title="Current operation">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <VehicleDetail icon={Gauge} label="Status" value={vehicle.status} />
              <VehicleDetail icon={Gauge} label="Speed" value={`${vehicle.speed} km/h`} />
              <VehicleDetail icon={MapPin} label="Location" value={vehicle.location} />
              <VehicleDetail icon={Users} label="Assigned" value={`${students.length} / ${vehicle.capacity}`} />
            </div>
          </DetailSection>

          <DetailSection title="Registration & specification">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <VehicleDetail icon={FileCheck2} label="Registration" value={vehicle.registrationNumber} />
              <VehicleDetail icon={Bus} label="Vehicle type" value={vehicle.type} />
              <VehicleDetail icon={Bus} label="Make and model" value={vehicle.makeModel} />
              <VehicleDetail icon={CalendarDays} label="Manufactured" value={String(vehicle.year)} />
              <VehicleDetail icon={Info} label="Colour" value={vehicle.color} />
              <VehicleDetail icon={Fuel} label="Fuel type" value={vehicle.fuelType} />
              <VehicleDetail icon={Gauge} label="Mileage" value={`${vehicle.mileageKm.toLocaleString()} km`} />
              <VehicleDetail icon={Users} label="Seat capacity" value={`${vehicle.capacity} passengers`} />
            </div>
          </DetailSection>

          <DetailSection title="Driver & compliance">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <VehicleDetail icon={User} label="Assigned driver" value={vehicle.driver} />
              <VehicleDetail icon={ShieldCheck} label="Insurance expires" value={vehicle.insuranceExpiry} />
              <VehicleDetail icon={FileCheck2} label="Revenue licence expires" value={vehicle.revenueLicenceExpiry} />
              <VehicleDetail icon={Wrench} label="Last service" value={vehicle.lastService} />
              <VehicleDetail icon={Gauge} label="Next service" value={`${vehicle.nextServiceKm.toLocaleString()} km`} />
              <VehicleDetail icon={ShieldCheck} label="Emergency kit" value={vehicle.emergencyKit} />
            </div>
          </DetailSection>

          <DetailSection title="Connected safety equipment">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <VehicleDetail icon={Satellite} label="GPS device" value={vehicle.gpsDeviceId} />
              <VehicleDetail icon={Camera} label="Cabin cameras" value={`${vehicle.cameraCount} connected`} />
            </div>
          </DetailSection>

          <DetailSection title={`Assigned students (${students.length})`}>
            <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100">
              {students.map((student) => <div key={student.id} className="px-4 py-3 flex justify-between text-sm"><span className="font-medium text-slate-800">{student.name}</span><span className="text-slate-500">Grade {student.grade} · {student.school}</span></div>)}
            </div>
          </DetailSection>
        </div>

        <div className="p-5 bg-white border-t border-slate-200 grid grid-cols-2 gap-3">
          {callStatus ? <button onClick={onEndCall} className="py-3 bg-red-600 text-white rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-red-700"><PhoneOff size={18} /> {callStatus === 'RINGING' ? 'Cancel call' : 'End call'}</button> : <button onClick={onCall} className="py-3 bg-green-600 text-white rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-green-700"><PhoneCall size={18} /> Call vehicle</button>}
          <button onClick={onCheckSafety} className="py-3 bg-[#176B87] text-white rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-[#12546b] transition-colors"><ShieldCheck size={18} /> Check safety</button>
        </div>
      </aside>
    </div>
  );
}

function DetailSection({ title, children }: {title: string;children: React.ReactNode}) {
  return <section><h4 className="font-semibold text-[#17212B] mb-3">{title}</h4>{children}</section>;
}

function VehicleDetail({ icon: Icon, label, value }: {icon: any;label: string;value: string}) {
  return <div className="p-3 rounded-lg border border-slate-200 bg-white"><p className="text-xs text-slate-400 flex items-center gap-1.5 mb-1"><Icon size={13} /> {label}</p><p className="font-semibold text-slate-800 text-sm">{value}</p></div>;
}

export function DriversPage() {
  const { vehicles, drivers, assistants, crewAssignments, addDriver, addAssistant, assignCrew } = useAppContext();
  const [tab, setTab] = useState<'DRIVERS' | 'ASSISTANTS' | 'HISTORY'>('DRIVERS');
  const [selectedDriver, setSelectedDriver] = useState<Driver | null>(null);
  const [selectedAssistant, setSelectedAssistant] = useState<Assistant | null>(null);
  const [modal, setModal] = useState<'DRIVER' | 'ASSISTANT' | 'ASSIGN' | null>(null);
  const todayAssignments = crewAssignments.filter((item) => item.date === '24 Aug 2026' && item.status === 'ASSIGNED');

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-wrap justify-between items-end gap-4 mb-6">
        <div><h2 className="text-2xl font-bold text-[#17212B] mb-1">Drivers & Assistants</h2><p className="text-slate-500">Crew profiles, daily bus assignments and history</p></div>
        <div className="flex gap-2">
          <button onClick={() => setModal('ASSIGN')} className="px-4 py-2.5 border border-[#176B87] text-[#176B87] bg-white rounded-lg font-semibold flex items-center gap-2 hover:bg-blue-50"><Bus size={17} /> Assign today</button>
          <button onClick={() => setModal(tab === 'ASSISTANTS' ? 'ASSISTANT' : 'DRIVER')} className="px-4 py-2.5 bg-[#176B87] text-white rounded-lg font-semibold flex items-center gap-2 hover:bg-[#12546b]"><Plus size={17} /> Add {tab === 'ASSISTANTS' ? 'assistant' : 'driver'}</button>
        </div>
      </div>

      <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit mb-6">
        <TabButton active={tab === 'DRIVERS'} onClick={() => setTab('DRIVERS')} icon={User} label={`Drivers (${drivers.length})`} />
        <TabButton active={tab === 'ASSISTANTS'} onClick={() => setTab('ASSISTANTS')} icon={UserPlus} label={`Assistants (${assistants.length})`} />
        <TabButton active={tab === 'HISTORY'} onClick={() => setTab('HISTORY')} icon={History} label="Assignment history" />
      </div>

      {tab !== 'HISTORY' && <section className="mb-7"><h3 className="font-semibold text-slate-800 mb-3">Today’s vehicle crew</h3><div className="grid grid-cols-1 md:grid-cols-2 gap-3">{vehicles.map((vehicle) => {const assignment = todayAssignments.find((item) => item.vehicleId === vehicle.id);const driver = drivers.find((item) => item.id === assignment?.driverId);const assistant = assistants.find((item) => item.id === assignment?.assistantId);return <div key={vehicle.id} className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-4"><span className="w-10 h-10 bg-blue-50 text-[#176B87] rounded-lg flex items-center justify-center"><Bus size={20} /></span><div className="flex-1 min-w-0"><p className="font-bold text-slate-800">{vehicle.id} <span className="font-normal text-xs text-slate-400">· {assignment?.shift || 'Unassigned'}</span></p><p className="text-sm text-slate-500 truncate">Driver: {driver?.name || 'Not assigned'} · Assistant: {assistant?.name || 'None — driver only'}</p></div><button onClick={() => setModal('ASSIGN')} className="text-xs font-semibold text-[#176B87]">Change</button></div>;})}</div></section>}

      {tab === 'DRIVERS' && <div className="grid grid-cols-1 md:grid-cols-2 gap-5">{drivers.map((driver) => <CrewCard key={driver.id} imageUrl={driver.imageUrl} name={driver.name} subtitle={`${driver.licenceNumber} · ${driver.experienceYears} years`} phone={driver.phone} status={driver.status} onClick={() => setSelectedDriver(driver)} />)}</div>}
      {tab === 'ASSISTANTS' && <div className="grid grid-cols-1 md:grid-cols-2 gap-5">{assistants.map((assistant) => <CrewCard key={assistant.id} imageUrl={assistant.imageUrl} name={assistant.name} subtitle={`${assistant.firstAidTrained ? 'First-aid trained' : 'No first-aid certificate'} · Joined ${assistant.joinedDate}`} phone={assistant.phone} status={assistant.status} onClick={() => setSelectedAssistant(assistant)} />)}</div>}
      {tab === 'HISTORY' && <AssignmentHistory assignments={crewAssignments} drivers={drivers} assistants={assistants} />}

      {selectedDriver && <CrewProfile title="Driver profile" person={selectedDriver} details={[['Licence', `${selectedDriver.licenceNumber} · ${selectedDriver.licenceClass}`], ['Licence expiry', selectedDriver.licenceExpiry], ['NIC', selectedDriver.nic], ['Date of birth', selectedDriver.dateOfBirth], ['Experience', `${selectedDriver.experienceYears} years`], ['Email', selectedDriver.email], ['Address', selectedDriver.address], ['Blood group', selectedDriver.bloodGroup], ['Medical', selectedDriver.medicalNotes], ['Emergency contact', selectedDriver.emergencyContact]]} onClose={() => setSelectedDriver(null)} />}
      {selectedAssistant && <CrewProfile title="Assistant profile" person={selectedAssistant} details={[['NIC', selectedAssistant.nic], ['Joined', selectedAssistant.joinedDate], ['First aid', selectedAssistant.firstAidTrained ? 'Certified' : 'Not certified'], ['Address', selectedAssistant.address], ['Emergency contact', selectedAssistant.emergencyContact]]} onClose={() => setSelectedAssistant(null)} />}
      {modal === 'DRIVER' && <AddDriverModal onClose={() => setModal(null)} onSave={(value) => {addDriver(value);setModal(null);}} />}
      {modal === 'ASSISTANT' && <AddAssistantModal onClose={() => setModal(null)} onSave={(value) => {addAssistant(value);setModal(null);}} />}
      {modal === 'ASSIGN' && <AssignCrewModal vehicles={vehicles} drivers={drivers} assistants={assistants} onClose={() => setModal(null)} onSave={(value) => {assignCrew(value);setModal(null);}} />}
    </div>);

}

function TabButton({ active, onClick, icon: Icon, label }: {active: boolean;onClick: () => void;icon: any;label: string}) { return <button onClick={onClick} className={`px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 ${active ? 'bg-white text-[#176B87] shadow-sm' : 'text-slate-500'}`}><Icon size={15} /> {label}</button>; }

function CrewCard({ imageUrl, name, subtitle, phone, status, onClick }: {imageUrl: string;name: string;subtitle: string;phone: string;status: string;onClick: () => void}) {
  return <button onClick={onClick} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 text-left flex gap-4 hover:border-[#2D9CDB] transition-colors"><img src={imageUrl} alt={name} className="w-16 h-16 rounded-xl object-cover bg-slate-100" /><div className="flex-1 min-w-0"><div className="flex justify-between gap-2"><h3 className="font-bold text-slate-800 truncate">{name}</h3><span className={`text-[10px] font-bold px-2 py-1 rounded-full h-fit ${status === 'ON_TRIP' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>{status.replace('_', ' ')}</span></div><p className="text-xs text-slate-500 mt-1 truncate">{subtitle}</p><p className="text-sm text-slate-600 mt-3 flex items-center gap-1.5"><Phone size={13} /> {phone}</p><p className="text-xs font-semibold text-[#176B87] mt-2">View full profile</p></div></button>;
}

function CrewProfile({ title, person, details, onClose }: {title: string;person: Driver | Assistant;details: string[][];onClose: () => void}) {
  return <div className="fixed inset-0 z-50 flex justify-end"><button className="absolute inset-0 bg-slate-900/35" onClick={onClose} /><aside className="relative w-full max-w-xl h-full bg-slate-50 shadow-2xl overflow-y-auto"><header className="bg-white p-6 border-b border-slate-200 flex justify-between"><div className="flex gap-4"><img src={person.imageUrl} alt={person.name} className="w-20 h-20 rounded-xl object-cover bg-slate-100" /><div><p className="text-xs font-semibold text-[#176B87] uppercase">{title}</p><h3 className="text-xl font-bold text-slate-800 mt-1">{person.name}</h3><p className="text-sm text-slate-500 mt-1">{person.id} · {person.status.replace('_', ' ')}</p></div></div><button onClick={onClose} className="p-2 h-fit rounded-lg hover:bg-slate-100"><X size={18} /></button></header><div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-3"><VehicleDetail icon={Phone} label="Phone" value={person.phone} />{details.map(([label, value]) => <VehicleDetail key={label} icon={label === 'Email' ? Mail : label === 'Address' ? MapPin : label === 'Medical' || label === 'Blood group' ? HeartPulse : IdCard} label={label} value={value} />)}</div></aside></div>;
}

function AssignmentHistory({ assignments, drivers, assistants }: {assignments: ReturnType<typeof useAppContext>['crewAssignments'];drivers: Driver[];assistants: Assistant[]}) {
  return <div className="bg-white border border-slate-200 rounded-xl overflow-hidden"><table className="w-full text-sm text-left"><thead className="bg-slate-50 text-slate-600"><tr><th className="px-5 py-3">Date</th><th className="px-5 py-3">Vehicle</th><th className="px-5 py-3">Driver</th><th className="px-5 py-3">Assistant</th><th className="px-5 py-3">Shift / route</th><th className="px-5 py-3">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{assignments.map((item) => <tr key={item.id}><td className="px-5 py-4 text-slate-600">{item.date}</td><td className="px-5 py-4 font-semibold text-slate-800">{item.vehicleId}</td><td className="px-5 py-4">{drivers.find((driver) => driver.id === item.driverId)?.name}</td><td className="px-5 py-4">{assistants.find((assistant) => assistant.id === item.assistantId)?.name || 'None — driver only'}</td><td className="px-5 py-4"><p>{item.shift}</p><p className="text-xs text-slate-400">{item.route}</p></td><td className="px-5 py-4"><span className={`px-2 py-1 rounded-full text-xs font-semibold ${item.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{item.status}</span></td></tr>)}</tbody></table></div>;
}

function ModalShell({ title, subtitle, onClose, children }: {title: string;subtitle: string;onClose: () => void;children: React.ReactNode}) { return <div className="fixed inset-0 z-[60] flex items-center justify-center p-4"><button className="absolute inset-0 bg-slate-900/40" onClick={onClose} /><div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto"><div className="flex justify-between mb-5"><div><h3 className="text-xl font-bold text-slate-800">{title}</h3><p className="text-sm text-slate-500">{subtitle}</p></div><button onClick={onClose} className="p-2 h-fit rounded-lg hover:bg-slate-100"><X size={18} /></button></div>{children}</div></div>; }

function CrewField({ label, value, onChange, type = 'text', options }: {label: string;value: string;onChange: (value: string) => void;type?: string;options?: {label: string;value: string}[]}) { return <label className="block"><span className="text-sm font-medium text-slate-600 mb-1.5 block">{label}</span>{options ? <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full px-3 py-2.5 border border-slate-200 rounded-lg bg-white text-sm">{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm" />}</label>; }

function AddDriverModal({ onClose, onSave }: {onClose: () => void;onSave: (value: Omit<Driver, 'id' | 'status'>) => void}) {
  const [form, setForm] = useState({ name: '', imageUrl: 'https://i.pravatar.cc/200?img=15', phone: '', email: '', address: '', nic: '', dateOfBirth: '', licenceNumber: '', licenceClass: 'B, D1', licenceExpiry: '', experienceYears: '1', emergencyContact: '', bloodGroup: 'O+', medicalNotes: 'Fit for duty' });
  const field = (key: keyof typeof form) => (value: string) => setForm((prev) => ({ ...prev, [key]: value }));
  return <ModalShell title="Add driver" subtitle="Create a detailed driver profile using an image URL." onClose={onClose}><div className="grid grid-cols-1 sm:grid-cols-2 gap-4"><CrewField label="Full name" value={form.name} onChange={field('name')} /><CrewField label="Image URL" value={form.imageUrl} onChange={field('imageUrl')} /><CrewField label="Phone" value={form.phone} onChange={field('phone')} /><CrewField label="Email" value={form.email} onChange={field('email')} type="email" /><CrewField label="NIC" value={form.nic} onChange={field('nic')} /><CrewField label="Date of birth" value={form.dateOfBirth} onChange={field('dateOfBirth')} /><CrewField label="Licence number" value={form.licenceNumber} onChange={field('licenceNumber')} /><CrewField label="Licence class" value={form.licenceClass} onChange={field('licenceClass')} /><CrewField label="Licence expiry" value={form.licenceExpiry} onChange={field('licenceExpiry')} /><CrewField label="Experience years" value={form.experienceYears} onChange={field('experienceYears')} type="number" /><CrewField label="Blood group" value={form.bloodGroup} onChange={field('bloodGroup')} /><CrewField label="Emergency contact" value={form.emergencyContact} onChange={field('emergencyContact')} /><div className="sm:col-span-2"><CrewField label="Address" value={form.address} onChange={field('address')} /></div><div className="sm:col-span-2"><CrewField label="Medical notes" value={form.medicalNotes} onChange={field('medicalNotes')} /></div></div><FormActions onClose={onClose} onSave={() => onSave({ ...form, experienceYears: Number(form.experienceYears) })} /></ModalShell>;
}

function AddAssistantModal({ onClose, onSave }: {onClose: () => void;onSave: (value: Omit<Assistant, 'id' | 'status'>) => void}) {
  const [form, setForm] = useState({ name: '', imageUrl: 'https://i.pravatar.cc/200?img=48', phone: '', nic: '', address: '', emergencyContact: '', joinedDate: '24 August 2026', firstAidTrained: 'Yes' });
  const field = (key: keyof typeof form) => (value: string) => setForm((prev) => ({ ...prev, [key]: value }));
  return <ModalShell title="Add assistant" subtitle="Add a bus assistant and welfare contact details." onClose={onClose}><div className="grid grid-cols-1 sm:grid-cols-2 gap-4"><CrewField label="Full name" value={form.name} onChange={field('name')} /><CrewField label="Image URL" value={form.imageUrl} onChange={field('imageUrl')} /><CrewField label="Phone" value={form.phone} onChange={field('phone')} /><CrewField label="NIC" value={form.nic} onChange={field('nic')} /><CrewField label="Joined date" value={form.joinedDate} onChange={field('joinedDate')} /><CrewField label="Emergency contact" value={form.emergencyContact} onChange={field('emergencyContact')} /><CrewField label="First-aid trained" value={form.firstAidTrained} onChange={field('firstAidTrained')} options={[{label:'Yes',value:'Yes'},{label:'No',value:'No'}]} /><div className="sm:col-span-2"><CrewField label="Address" value={form.address} onChange={field('address')} /></div></div><FormActions onClose={onClose} onSave={() => onSave({ ...form, firstAidTrained: form.firstAidTrained === 'Yes' })} /></ModalShell>;
}

function AssignCrewModal({ vehicles, drivers, assistants, onClose, onSave }: {vehicles: Vehicle[];drivers: Driver[];assistants: Assistant[];onClose: () => void;onSave: (value: {vehicleId: string;driverId: string;assistantId: string;shift: 'Morning' | 'Afternoon' | 'Full day';route: string}) => void}) {
  const [vehicleId, setVehicleId] = useState(vehicles[0]?.id || ''); const [driverId, setDriverId] = useState(drivers[0]?.id || ''); const [assistantId, setAssistantId] = useState(''); const [shift, setShift] = useState<'Morning' | 'Afternoon' | 'Full day'>('Full day'); const [route, setRoute] = useState('Morning and afternoon school route');
  return <ModalShell title="Assign today’s crew" subtitle="Choose the driver and optional assistant responsible for a vehicle today." onClose={onClose}><div className="space-y-4"><CrewField label="Vehicle" value={vehicleId} onChange={setVehicleId} options={vehicles.map((item) => ({label:`${item.id} · ${item.registrationNumber}`,value:item.id}))} /><CrewField label="Driver" value={driverId} onChange={setDriverId} options={drivers.map((item) => ({label:`${item.name} · ${item.licenceNumber}`,value:item.id}))} /><CrewField label="Assistant (optional)" value={assistantId} onChange={setAssistantId} options={[{label:'None — driver only',value:''}, ...assistants.map((item) => ({label:item.name,value:item.id}))]} /><CrewField label="Shift" value={shift} onChange={(value) => setShift(value as typeof shift)} options={['Morning','Afternoon','Full day'].map((value) => ({label:value,value}))} /><CrewField label="Route" value={route} onChange={setRoute} /></div><FormActions onClose={onClose} onSave={() => onSave({ vehicleId, driverId, assistantId, shift, route })} /></ModalShell>;
}

function FormActions({ onClose, onSave }: {onClose: () => void;onSave: () => void}) { return <div className="flex gap-3 mt-7"><button onClick={onClose} className="flex-1 py-2.5 border border-slate-200 rounded-lg font-semibold text-slate-600">Cancel</button><button onClick={onSave} className="flex-1 py-2.5 bg-[#176B87] text-white rounded-lg font-semibold">Save</button></div>; }

export function NotificationsPage() {
  const { notifications } = useAppContext();
  const icons = { success: CheckCircle2, warning: AlertTriangle, error: XCircle, info: Info };
  const tones = {
    success: 'text-green-600 bg-green-50 border-green-100',
    warning: 'text-amber-600 bg-amber-50 border-amber-100',
    error: 'text-red-600 bg-red-50 border-red-100',
    info: 'text-blue-600 bg-blue-50 border-blue-100'
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="text-2xl font-bold text-[#17212B] mb-1">Notifications</h2>
      <p className="text-slate-500 mb-6">Database pickup events and separate component demonstrations</p>
      <PersistentNotifications recipient="admin" />
      <h3 className="text-sm font-semibold text-slate-500 mb-3">Other component demonstration notifications</h3>

      <ol className="space-y-3">
        {notifications.map((n) => {
          const Icon = icons[n.type];
          return (
            <li key={n.id} className={`flex gap-4 items-start p-4 rounded-xl border ${tones[n.type]}`}>
              <Icon size={20} className="shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-800">{n.message}</p>
                <p className="text-xs text-slate-500 mt-1">{n.time} · to {n.role}</p>
              </div>
            </li>);

        })}
        {notifications.length === 0 &&
        <li className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">No notifications yet.</li>
        }
      </ol>
    </div>);

}

export function SettingsPage() {
  const { demoMode, setDemoMode, resetAll } = useAppContext();

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-[#17212B] mb-1">Settings</h2>
      <p className="text-slate-500 mb-6">Prototype configuration</p>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100">
        <div className="p-6 flex justify-between items-center">
          <div>
            <h3 className="font-semibold text-[#17212B]">Demo mode</h3>
            <p className="text-sm text-slate-500 mt-1">Shows the research-prototype badge and enables simulated events.</p>
          </div>
          <button
            onClick={() => setDemoMode(!demoMode)}
            role="switch"
            aria-checked={demoMode}
            className={`w-12 h-7 rounded-full p-1 transition-colors ${demoMode ? 'bg-[#176B87]' : 'bg-slate-300'}`}>
            
            <span className={`block w-5 h-5 bg-white rounded-full transition-transform ${demoMode ? 'translate-x-5' : ''}`} />
          </button>
        </div>

        <div className="p-6 flex justify-between items-center">
          <div>
            <h3 className="font-semibold text-[#17212B]">Reset prototype state</h3>
            <p className="text-sm text-slate-500 mt-1">Restores all students, routes, safety and incident state.</p>
          </div>
          <button onClick={resetAll} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 transition-colors">
            Reset demo
          </button>
        </div>

        <div className="p-6">
          <h3 className="font-semibold text-[#17212B] mb-2 flex items-center gap-2"><SettingsIcon size={16} /> Data notice</h3>
          <p className="text-sm text-slate-500">
            All students, vehicles, sensor readings, GPS positions and emergency contacts in this build are synthetic demo data
            generated for the university proposal. No real hardware, personal data, or emergency service is connected.
          </p>
        </div>
      </div>
    </div>);

}

function Stat({ label, value }: {label: string;value: string;}) {
  return (
    <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
      <dt className="text-xs text-slate-400 mb-0.5">{label}</dt>
      <dd className="font-semibold text-slate-800 text-sm">{value}</dd>
    </div>);

}
