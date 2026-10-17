import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react';
import { Search, Plus, X, Loader2, UserRound } from 'lucide-react';
import {
  fetchSchools, fetchStudents, fetchVehicles, setStudentActive,
  transferStudent, updateStudent, InputSource, SchoolRecord, StudentRecord,
  StudentWrite, StudentMutation, VehicleRecord,
} from '../services/api';

import { useAppContext } from '../contexts/AppContext';
import { RoutingOutcomeNotice } from '../components/RoutingOutcomeNotice';
import { LocationPicker, LocationDraft, validLocation } from '../components/LocationPicker';

type Directory = { students: StudentRecord[]; schools: SchoolRecord[]; vehicles: VehicleRecord[] };
type Dialog = { mode: 'add' } | { mode: 'edit' | 'transfer' | 'status' | 'view'; student: StudentRecord };
const control = 'w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#2D9CDB]/40';
const primary = 'px-4 py-2.5 bg-[#176B87] text-white rounded-lg font-medium hover:bg-[#12546b] transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const sourceLabels: Record<InputSource, string> = {
  simulated: 'Simulated input', live_provider: 'Live provider input', measured: 'Measured observation',
};
const message = (error: unknown) => error instanceof Error ? error.message : 'Unable to complete the request.';

export function StudentsPage() {
  const { routingRevision, lastRoutingOutcome } = useAppContext();
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState('');
  const [school, setSchool] = useState('');
  const [vehicle, setVehicle] = useState('');
  const [status, setStatus] = useState('');
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setDirectory(null);
    Promise.all([fetchStudents(controller.signal), fetchSchools(controller.signal), fetchVehicles(controller.signal)])
      .then(([students, schools, vehicles]) => {
        if (active) setDirectory({ students, schools, vehicles });
      })
      .catch((failure: unknown) => { if (active) setError(message(failure)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [reload, routingRevision]);

  const schools = directory?.schools ?? [];
  const vehicles = directory?.vehicles ?? [];
  const students = directory?.students ?? [];
  const schoolName = (id: string) => schools.find((entry) => entry.id === id)?.name ?? id;
  const filtered = students.filter((student) =>
    (!school || student.school_id === school) && (!vehicle || student.vehicle_id === vehicle) &&
    (!status || student.active === (status === 'active')) &&
    `${student.name} ${student.id}`.toLowerCase().includes(query.toLowerCase())
  );
  const saved = (student: StudentMutation) => {
    setDirectory((prev) => prev && ({ ...prev, students: [
      ...prev.students.filter((entry) => entry.id !== student.id), student,
    ].sort((a, b) => a.id.localeCompare(b.id)) }));
    setDialog(null);
    setNotice(`Saved ${student.name} to PostgreSQL.`);
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-wrap gap-4 justify-between items-end mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[#17212B]">Students</h2>
          <p className="text-slate-500">{directory ? `${students.length} registered · PostgreSQL routing records` : 'PostgreSQL routing records'}</p>
          <p className="text-xs text-slate-400 mt-1">The backend refreshes affected pre-trip plans after saving. Active/completed trips remain unchanged.</p>
        </div>
        <button disabled={!directory || loading || !schools.length || !vehicles.length} onClick={() => { setNotice(''); setDialog({ mode: 'add' }); }} className={`${primary} flex items-center gap-2`}>
          <Plus size={18} /> Add Student
        </button>
      </div>
      {notice && lastRoutingOutcome ? <div className="mb-4"><RoutingOutcomeNotice title="Student saved" outcome={lastRoutingOutcome} /></div> : notice && <p role="status" className="mb-4 p-3 rounded-lg bg-blue-50 text-slate-700 text-sm">{notice}</p>}
      {error && <div role="alert" className="mb-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
        {error} <button onClick={() => setReload((value) => value + 1)} className="ml-3 font-semibold underline">Retry loading</button>
      </div>}
      {directory && (!schools.length || !vehicles.length) && <p className="mb-4 p-3 bg-amber-50 text-amber-800 rounded-lg text-sm">Create or seed a school and vehicle in the database before adding students.</p>}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 flex flex-wrap gap-3 border-b border-slate-100">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input aria-label="Search students" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name or ID" className={`${control} pl-9`} />
          </div>
          <select aria-label="Filter school" value={school} onChange={(event) => setSchool(event.target.value)} className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
            <option value="">All schools</option>{schools.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
          </select>
          <select aria-label="Filter vehicle" value={vehicle} onChange={(event) => setVehicle(event.target.value)} className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
            <option value="">All vehicles</option>{vehicles.map((entry) => <option key={entry.id} value={entry.id}>{entry.id}</option>)}
          </select>
          <select aria-label="Filter status" value={status} onChange={(event) => setStatus(event.target.value)} className="px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
            <option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option>
          </select>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200"><tr>
              {['ID', 'Name', 'School', 'Vehicle', 'Status', 'Actions'].map((heading) => <th key={heading} className="px-6 py-3 font-medium">{heading}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {loading && <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-500"><span role="status" className="inline-flex gap-2 items-center"><Loader2 size={18} className="animate-spin" /> Loading students...</span></td></tr>}
              {!loading && error && <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-400">Students unavailable. Retry loading.</td></tr>}
              {!loading && !error && filtered.map((student) => <tr key={student.id} className="hover:bg-slate-50">
                <td className="px-6 py-3 font-mono text-xs text-slate-500 break-all max-w-[150px]">{student.id}</td>
                <td className="px-6 py-3 font-medium text-[#17212B]">{student.name}<span className="block text-xs font-normal text-slate-400">{sourceLabels[student.input_source]}</span></td>
                <td className="px-6 py-3 text-slate-600">{schoolName(student.school_id)}</td>
                <td className="px-6 py-3 text-slate-600">{student.vehicle_id}</td>
                <td className="px-6 py-3"><span className={`px-2.5 py-1 rounded-full text-xs font-medium ${student.active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>{student.active ? 'Active' : 'Inactive'}</span></td>
                <td className="px-6 py-3 text-right"><div className="flex flex-wrap justify-end gap-x-4 gap-y-2">
                  {(['view', 'edit', 'transfer', 'status'] as const).map((mode) => <button key={mode} onClick={() => { setNotice(''); setDialog({ mode, student }); }} className="text-[#176B87] font-medium hover:underline">
                    {mode === 'view' ? 'View profile' : mode === 'edit' ? 'Edit' : mode === 'transfer' ? 'Transfer' : student.active ? 'Deactivate' : 'Reactivate'}
                  </button>)}
                </div></td>
              </tr>)}
              {!loading && !error && !filtered.length && <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-400">No students match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      {dialog && directory && <StudentDialog key={dialog.mode + ('student' in dialog ? dialog.student.id : '')} dialog={dialog} schools={schools} vehicles={vehicles} onClose={() => setDialog(null)} onSaved={saved} />}
    </div>
  );
}

function StudentDialog({ dialog, schools, vehicles, onClose, onSaved }: {
  dialog: Dialog; schools: SchoolRecord[]; vehicles: VehicleRecord[];
  onClose: () => void; onSaved: (student: StudentMutation) => void;
}) {
  const { addStudentAndReoptimize } = useAppContext();
  const requestKey = useRef(crypto.randomUUID());
  const student = 'student' in dialog ? dialog.student : null;
  const [name, setName] = useState(student?.name ?? '');
  const [school, setSchool] = useState(student?.school_id ?? schools[0]?.id ?? '');
  const [vehicle, setVehicle] = useState(student?.vehicle_id ?? vehicles[0]?.id ?? '');
  const [location, setLocation] = useState<LocationDraft>({
    address: student?.home_address ?? '', latitude: student?.home_latitude?.toString() ?? '',
    longitude: student?.home_longitude?.toString() ?? '', confirmed: student?.location_confirmed ?? false,
    method: student?.location_method ?? 'manual',
  });
  const [source, setSource] = useState<InputSource>(student?.input_source ?? 'simulated');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const title = dialog.mode === 'add' ? 'Add student' : dialog.mode === 'edit' ? 'Edit student' : dialog.mode === 'transfer' ? 'Transfer student' : dialog.mode === 'status' ? `${student?.active ? 'Deactivate' : 'Reactivate'} student` : 'Student profile';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;
    setError(null);
    if (dialog.mode === 'add' || dialog.mode === 'edit') {
      if (!name.trim() || !school || !vehicle || !validLocation(location) || !location.confirmed) {
        setError('Enter a name, school, vehicle, valid address and coordinates, then explicitly confirm the location.');
        return;
      }
    }
    setSaving(true);
    try {
      let response: StudentMutation;
      if (dialog.mode === 'transfer' && student) response = await transferStudent(student.id, vehicle, requestKey.current);
      else if (dialog.mode === 'status' && student) response = await setStudentActive(student.id, !student.active, requestKey.current);
      else {
        const payload: StudentWrite = { name: name.trim(), school_id: school, vehicle_id: vehicle, home_latitude: Number(location.latitude), home_longitude: Number(location.longitude), input_source: source, home_address: location.address.trim(), location_confirmed: true, location_method: location.method };
        response = student ? await updateStudent(student.id, payload, requestKey.current) : await addStudentAndReoptimize(payload, requestKey.current);
      }
      onSaved(response);
    } catch (failure) { setError(`Student save failed: ${message(failure)}`); }
    finally { setSaving(false); }
  };

  const view = dialog.mode === 'view';
  return <div className={`fixed inset-0 z-50 flex ${view ? 'justify-end' : 'items-center justify-center p-4'}`}>
    <div className="absolute inset-0 bg-slate-900/40" onClick={() => { if (!saving) onClose(); }} />
    <section role="dialog" aria-modal="true" aria-labelledby="student-dialog-title" className={`relative bg-white shadow-2xl w-full max-w-2xl overflow-y-auto ${view ? 'h-full p-6' : 'rounded-2xl p-6 max-h-[90vh]'}`}>
      <header className="flex justify-between items-start mb-6">
        <div><h3 id="student-dialog-title" className="text-lg font-bold text-[#17212B]">{title}</h3><p className="text-sm text-slate-500">{student?.name ?? 'Save a new PostgreSQL routing record.'}</p></div>
        <button disabled={saving} aria-label="Close student form" onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 disabled:opacity-50"><X size={18} /></button>
      </header>
      {view && student ? <div className="space-y-6">
        <h4 className="font-semibold text-[#17212B] flex items-center gap-2"><UserRound size={17} /> Student details</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            ['ID', student.id], ['Name', student.name],
            ['School', schools.find((entry) => entry.id === student.school_id)?.name ?? student.school_id],
            ['Vehicle', student.vehicle_id], ['Status', student.active ? 'Active' : 'Inactive'],
            ['Home ID', student.home_id], ['Address', student.home_address || 'Unavailable'], ['Location confirmation', student.location_confirmed ? 'Confirmed' : 'Not confirmed'], ['Location method', student.location_method], ['Home latitude', student.home_latitude?.toString() ?? 'Unavailable'],
            ['Home longitude', student.home_longitude?.toString() ?? 'Unavailable'], ['Input source', sourceLabels[student.input_source]],
          ].map(([label, value]) => <div key={label} className="p-3 rounded-lg border border-slate-100 bg-slate-50 break-all"><p className="text-xs text-slate-400 mb-1">{label}</p><p className="font-medium text-slate-800 text-sm">{value}</p></div>)}
        </div>
        <p className="text-sm text-slate-500">This profile shows persisted routing data. Trip history is unavailable for these records.</p>
      </div> : <form onSubmit={submit}>
        <fieldset disabled={saving} className="space-y-4">
          {(dialog.mode === 'add' || dialog.mode === 'edit') && <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Name"><input required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} className={control} /></Field>
            <Field label="School"><select aria-label="School" required value={school} onChange={(event) => setSchool(event.target.value)} className={control}><option value="">Select school</option>{schools.map((entry) => <option key={entry.id} value={entry.id}>{entry.name} ({entry.id})</option>)}</select></Field>
            <VehicleField vehicles={vehicles} value={vehicle} onChange={setVehicle} />
            <Field label="Input source"><select aria-label="Input source" value={source} onChange={(event) => setSource(event.target.value as InputSource)} className={control}>{Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
            <div className="sm:col-span-2"><LocationPicker value={location} onChange={setLocation} disabled={saving} source={source} /></div>
            <p className="sm:col-span-2 text-xs text-slate-500">Input provenance describes your data: simulated input, live provider input, or measured observation. No ML prediction is created.</p>
          </div>}
          {dialog.mode === 'transfer' && <><p className="text-sm text-slate-600">Current vehicle: {student?.vehicle_id}. Select the destination vehicle.</p><VehicleField vehicles={vehicles} value={vehicle} onChange={setVehicle} /></>}
          {dialog.mode === 'status' && <p className="text-sm text-slate-600">{student?.active ? 'Deactivate this student? The record and vehicle assignment will be retained.' : 'Reactivate this student? The existing vehicle assignment will be retained.'}</p>}
          {error && <p role="alert" className="text-sm p-3 rounded-lg bg-red-50 text-red-700">{error}</p>}
          <p className="text-xs text-slate-400">Saving also refreshes affected pre-trip routes on the backend. Routing failures do not undo the student save.</p>
          <div className="flex gap-3 pt-4">
            <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-slate-200 text-slate-600 font-medium hover:bg-slate-50">Cancel</button>
            <button type="submit" disabled={saving || (dialog.mode === 'transfer' && vehicle === student?.vehicle_id)} className={`${primary} flex-1 flex items-center justify-center gap-2`}>
              {saving && <Loader2 size={16} className="animate-spin" />}{saving ? 'Saving and planning...' : dialog.mode === 'transfer' ? 'Save transfer' : dialog.mode === 'status' ? student?.active ? 'Deactivate student' : 'Reactivate student' : 'Save student'}
            </button>
          </div>
        </fieldset>
      </form>}
    </section>
  </div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block"><span className="text-sm font-medium text-slate-600 mb-1.5 block">{label}</span>{children}</label>;
}
function VehicleField({ vehicles, value, onChange }: { vehicles: VehicleRecord[]; value: string; onChange: (value: string) => void }) {
  return <Field label="Vehicle"><select aria-label="Vehicle" required value={value} onChange={(event) => onChange(event.target.value)} className={control}><option value="">Select vehicle</option>{vehicles.map((entry) => <option key={entry.id} value={entry.id}>{entry.id} (capacity {entry.capacity})</option>)}</select></Field>;
}
