import { useEffect, useRef, useState } from 'react';
import { MapLoader as RouteMap } from './MapLoader';
import { geocodeAddress, InputSource, LocationMethod, MapPoint } from '../services/api';

export interface LocationDraft {
  address: string; latitude: string; longitude: string;
  confirmed: boolean; method: LocationMethod;
}
export function validLocation(location: LocationDraft) {
  return !!location.address.trim() && !!location.latitude.trim() && !!location.longitude.trim() &&
    Number.isFinite(Number(location.latitude)) && Math.abs(Number(location.latitude)) <= 90 &&
    Number.isFinite(Number(location.longitude)) && Math.abs(Number(location.longitude)) <= 180;
}
export const emptyLocation = (): LocationDraft => ({ address: '', latitude: '', longitude: '', confirmed: false, method: 'manual' });
const control = 'w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#2D9CDB]/40';

export function LocationPicker({ value, onChange, disabled = false, source = 'simulated', home = true }: {
  value: LocationDraft; onChange: (value: LocationDraft) => void; disabled?: boolean; source?: InputSource; home?: boolean;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState('');
  const requestId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { requestId.current += 1; controller.current?.abort(); }, []);
  const manualChange = (update: Partial<LocationDraft>) => {
    requestId.current += 1;
    controller.current?.abort();
    setLoading(false); setInfo('');
    onChange({ ...value, ...update, confirmed: false, method: value.method === 'google' || value.method === 'manual_correction' ? 'manual_correction' : 'manual' });
  };
  const geocode = async () => {
    controller.current?.abort();
    const id = ++requestId.current;
    const abort = new AbortController(); controller.current = abort;
    setLoading(true); setError(null); setInfo('');
    onChange({ ...value, confirmed: false });
    try {
      const result = await geocodeAddress(value.address, abort.signal);
      if (id !== requestId.current) return;
      onChange({ address: result.formatted_address, latitude: String(result.latitude), longitude: String(result.longitude), confirmed: false, method: 'google' });
      setInfo(`Google returned ${result.partial_match ? 'a partial match' : 'an address match'}. Check the pin and explicitly confirm it.`);
    } catch (failure) {
      if (id === requestId.current) setError(failure instanceof Error ? failure.message : 'Geocoding failed. Set the pin manually.');
    } finally { if (id === requestId.current) setLoading(false); }
  };
  const hasCoordinates = !!value.latitude.trim() && !!value.longitude.trim() && Number.isFinite(Number(value.latitude)) && Number.isFinite(Number(value.longitude)) && Math.abs(Number(value.latitude)) <= 90 && Math.abs(Number(value.longitude)) <= 180;
  const points: MapPoint[] = hasCoordinates ? [{ id: 'preview', location_id: 'preview', name: 'Selected location (preview)', kind: 'home', latitude: Number(value.latitude), longitude: Number(value.longitude), address: value.address, input_source: source, location_method: value.method }] : [];
  return <div className="space-y-3">
    <label className="block"><span className="text-sm font-medium text-slate-600 mb-1.5 block">Address</span>
      <input required maxLength={500} disabled={disabled} value={value.address} onChange={(event) => manualChange({ address: event.target.value })} className={control} />
    </label>
    <button type="button" disabled={disabled || loading || value.address.trim().length < 3} onClick={geocode} className="px-3 py-2 rounded-lg border border-slate-200 text-sm font-medium text-[#176B87] disabled:opacity-50">{loading ? 'Looking up address...' : 'Look up address'}</button>
    {error && <p role="alert" className="text-sm text-amber-800 bg-amber-50 rounded-lg p-3">{error} No coordinates were invented. You can enter coordinates or click the map.</p>}
    {info && <p role="status" className="text-sm text-slate-600">{info}</p>}
    <div className="grid grid-cols-2 gap-4">
      <label><span className="text-sm font-medium text-slate-600 mb-1.5 block">{home ? 'Home latitude' : 'Latitude'}</span><input required type="number" step="any" min={-90} max={90} disabled={disabled} value={value.latitude} onChange={(event) => manualChange({ latitude: event.target.value })} className={control} /></label>
      <label><span className="text-sm font-medium text-slate-600 mb-1.5 block">{home ? 'Home longitude' : 'Longitude'}</span><input required type="number" step="any" min={-180} max={180} disabled={disabled} value={value.longitude} onChange={(event) => manualChange({ longitude: event.target.value })} className={control} /></label>
    </div>
    <RouteMap points={points} editable={!disabled && !loading} height={300} onPositionChange={(latitude, longitude) => manualChange({ latitude: latitude.toFixed(7), longitude: longitude.toFixed(7) })} />
    <p className="text-xs text-slate-500">Location method: {value.method === 'google' ? 'Google automatic geocoding result' : value.method === 'manual_correction' ? 'Manually corrected after geocoding' : 'Manual coordinates / pin placement'}. Location input: {value.method === 'google' ? 'live provider' : source.replace('_', ' ')}. {hasCoordinates ? '' : 'The regional map view is not a selected location.'}</p>
    <label className="flex gap-2 items-start text-sm text-slate-700"><input type="checkbox" checked={value.confirmed} disabled={disabled || loading || !validLocation(value)} onChange={(event) => onChange({ ...value, confirmed: event.target.checked })} className="mt-1" />
      <span>I confirm this address and pin position are correct.</span>
    </label>
    <p className="text-xs text-slate-400">Changing the address or pin clears confirmation. Manual entry is not automatic geocoding.</p>
  </div>;
}
