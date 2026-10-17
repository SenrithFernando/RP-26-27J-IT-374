import { FormEvent, useEffect, useState } from 'react';
import { MapPin, X } from 'lucide-react';
import { MapLoader as RouteMap } from './MapLoader';
import { emptyLocation, LocationDraft, LocationPicker, validLocation } from './LocationPicker';
import { fetchMapLocations, fetchSchools, fetchVehicles, MapLocations, RouteDirection,
  saveSchoolLocation, saveVehicleLocation, SchoolRecord, VehicleRecord } from '../services/api';

type Stop = { id: string; order: number; name: string };
const control = 'w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white';
export function RouteLocations({ direction, vehicleId, stops }: { direction: RouteDirection; vehicleId?: string; stops: Stop[] }) {
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [vehicles, setVehicles] = useState<VehicleRecord[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState('');
  const [revision, setRevision] = useState(0);
  const [setup, setSetup] = useState(false);
  const [directoryError, setDirectoryError] = useState<string | null>(null);
  const [directoryLoading, setDirectoryLoading] = useState(true);
  const [data, setData] = useState<{ vehicle: string; direction: RouteDirection; revision: number; response: MapLocations | null; error: string | null } | null>(null);
  const mapVehicle = selectedVehicle || vehicleId || vehicles[0]?.id || '';
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setDirectoryLoading(true); setDirectoryError(null);
    Promise.all([fetchSchools(controller.signal), fetchVehicles(controller.signal)])
      .then(([newSchools, newVehicles]) => { if (active) { setSchools(newSchools); setVehicles(newVehicles); } })
      .catch((error: unknown) => { if (active) { setSchools([]); setVehicles([]); setDirectoryError(error instanceof Error ? error.message : 'Unable to load locations.'); } })
      .finally(() => { if (active) setDirectoryLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [revision]);
  useEffect(() => {
    if (!mapVehicle) return;
    const controller = new AbortController(); let active = true;
    setData(null);
    fetchMapLocations(mapVehicle, direction, controller.signal)
      .then((response) => { if (active) setData({ vehicle: mapVehicle, direction, revision, response, error: null }); })
      .catch((error: unknown) => { if (active) setData({ vehicle: mapVehicle, direction, revision, response: null, error: error instanceof Error ? error.message : 'Unable to load confirmed map locations.' }); });
    return () => { active = false; controller.abort(); };
  }, [mapVehicle, direction, revision]);
  const current = data?.vehicle === mapVehicle && data.direction === direction && data.revision === revision ? data : null;
  return <div className="bg-white rounded-2xl p-1 border border-slate-200 shadow-sm flex flex-col">
    <div className="px-5 py-4 border-b border-slate-100 space-y-3">
      <h3 className="font-semibold text-[#17212B] flex items-center gap-2"><MapPin size={18} className="text-blue-500" /> Confirmed Locations Map</h3>
      <p className="text-xs text-slate-500">Confirmed homes, schools and vehicle endpoints. New homes are not automatically added to the optimized sequence.</p>
      <label className="block text-sm text-slate-600">Map vehicle<select aria-label="Map vehicle" value={mapVehicle} disabled={directoryLoading || !!directoryError} onChange={(event) => setSelectedVehicle(event.target.value)} className={control}>
        {!vehicles.length && <option value="">No vehicles available</option>}{vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.id}</option>)}
      </select></label>
      <div className="flex justify-between gap-2 text-sm"><button disabled={directoryLoading || !!directoryError || !vehicles.length} type="button" onClick={() => setSetup(true)} className="text-[#176B87] font-medium hover:underline disabled:opacity-50">Configure map locations</button>
        <button type="button" className="text-[#176B87] font-medium hover:underline" onClick={() => setRevision((value) => value + 1)}>Refresh locations</button></div>
      {mapVehicle && vehicleId && mapVehicle !== vehicleId && <p className="text-xs text-amber-800">No optimization result for this map vehicle. Markers show saved locations only.</p>}
    </div>
    <div className="p-2">
      <RouteMap points={current?.response?.points ?? []} orderedStops={mapVehicle === vehicleId ? stops : []}
        missingLocations={current?.response?.missing_locations} loading={directoryLoading || (!!mapVehicle && !current)} error={directoryError || current?.error} />
    </div>
    {setup && <LocationSetup schools={schools} vehicles={vehicles} defaultVehicle={mapVehicle} onClose={() => setSetup(false)} onSaved={() => { setSetup(false); setRevision((value) => value + 1); }} />}
  </div>;
}

export function LocationSetup({ schools, vehicles, defaultVehicle, onClose, onSaved }: {
  schools: SchoolRecord[]; vehicles: VehicleRecord[]; defaultVehicle: string; onClose: () => void; onSaved: () => void;
}) {
  const [target, setTarget] = useState(`vehicle:start:${defaultVehicle}`);
  const [location, setLocation] = useState<LocationDraft>(() => vehicleDraft(vehicles.find((vehicle) => vehicle.id === defaultVehicle), 'start'));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kind, position, id] = target.split(':');
  const changeTarget = (value: string) => {
    setTarget(value); setError(null);
    const [kind, position, id] = value.split(':');
    if (kind === 'school') {
      const school = schools.find((entry) => entry.id === id);
      setLocation(school ? { address: school.address, latitude: school.latitude?.toString() ?? '', longitude: school.longitude?.toString() ?? '', confirmed: school.location_confirmed, method: school.location_method } : emptyLocation());
    } else setLocation(vehicleDraft(vehicles.find((entry) => entry.id === id), position as 'start' | 'end'));
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (saving) return;
    if (!validLocation(location) || !location.confirmed) { setError('Enter an address and valid coordinates, then explicitly confirm the pin.'); return; }
    setSaving(true); setError(null);
    const payload = { address: location.address.trim(), latitude: Number(location.latitude), longitude: Number(location.longitude), location_confirmed: true, location_method: location.method };
    try {
      if (kind === 'school') await saveSchoolLocation(id, payload);
      else await saveVehicleLocation(id, position as 'start' | 'end', payload);
      onSaved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Location save failed.'); }
    finally { setSaving(false); }
  };
  const source = kind === 'school' ? schools.find((entry) => entry.id === id)?.input_source : vehicles.find((entry) => entry.id === id)?.input_source;
  return <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div className="absolute inset-0 bg-slate-900/40" onClick={() => { if (!saving) onClose(); }} />
    <section role="dialog" aria-modal="true" aria-labelledby="location-setup-title" className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
      <div className="flex justify-between items-start mb-4"><h3 id="location-setup-title" className="font-bold text-lg text-[#17212B]">Configure map locations</h3><button type="button" disabled={saving} onClick={onClose} aria-label="Close location setup" className="p-2"><X size={18} /></button></div>
      <form onSubmit={submit}><fieldset disabled={saving} className="space-y-4">
        <label className="block text-sm font-medium text-slate-600">Location to configure<select aria-label="Location to configure" value={target} onChange={(event) => changeTarget(event.target.value)} className={control}>
          {vehicles.flatMap((vehicle) => (['start', 'end'] as const).map((position) => <option key={`${vehicle.id}:${position}`} value={`vehicle:${position}:${vehicle.id}`}>{vehicle.id} · {position}</option>))}
          {schools.map((school) => <option key={school.id} value={`school:location:${school.id}`}>{school.name} · school</option>)}
        </select></label>
        <p className="text-xs text-slate-500">Input provenance: {source?.replace('_', ' ')}. Enter actual confirmed locations, or explicitly simulated coordinates for test records. Student homes are configured in Students.</p>
        <LocationPicker key={target} value={location} onChange={setLocation} disabled={saving} source={source} home={false} />
        {error && <p role="alert" className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</p>}
        <button type="submit" disabled={saving} className="w-full py-2.5 bg-[#176B87] text-white rounded-lg font-medium disabled:opacity-50">{saving ? 'Saving location...' : 'Save confirmed location'}</button>
      </fieldset></form>
    </section>
  </div>;
}

function vehicleDraft(vehicle: VehicleRecord | undefined, position: 'start' | 'end'): LocationDraft {
  if (!vehicle) return emptyLocation();
  return { address: vehicle[`${position}_address`], latitude: vehicle[`${position}_latitude`]?.toString() ?? '', longitude: vehicle[`${position}_longitude`]?.toString() ?? '', confirmed: vehicle[`${position}_confirmed`], method: vehicle[`${position}_method`] };
}
