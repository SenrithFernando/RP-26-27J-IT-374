import { useEffect, useState } from 'react';
import { LatestPosition } from '../services/api';
export const localTime = (value?: string | null) => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Asia/Colombo' }) : 'Unavailable';
export function PositionStatus({ data, error }: { data: LatestPosition | null; error: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const position = error ? null : data?.position;
  const age = position ? (now - new Date(position.recorded_at).getTime()) / 1000 : null;
  const fresh = !!position && data?.status === 'fresh' && age != null && Number.isFinite(age) && age >= 0 && age <= data.stale_after_seconds;
  const poor = position?.accuracy_quality === 'poor';
  const label = error ? 'Unavailable' : !position ? 'Waiting for GPS' : !fresh ? 'Signal out of date' : poor ? 'Low accuracy' : 'Location updated';
  return <section aria-label="Vehicle GPS status" className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold text-slate-900">Live location</h3><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${fresh && !poor ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>{label}</span></div>
    {error && <p role="alert" className="text-red-700">Could not update location. {error}</p>}
    {!position && !error && <p className="text-slate-500">Waiting for the tracking phone to send its position.</p>}
    {position && <><p className="text-xs text-slate-500">Last update: {localTime(position.recorded_at)}</p>
      <dl className="space-y-2"><div className="flex justify-between gap-2"><dt className="text-slate-500">GPS accuracy</dt><dd>{position.accuracy_m != null && Number.isFinite(position.accuracy_m) ? `${Math.round(position.accuracy_m)} m` : 'Unavailable'}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-slate-500">Speed</dt><dd>{fresh && !poor && position.speed_mps != null && Number.isFinite(position.speed_mps) ? `${Math.round(position.speed_mps * 3.6)} km/h` : 'Unavailable'}</dd></div></dl>
      {position.source === 'simulation' && <p className="text-xs font-medium text-amber-800">Simulated GPS · test movement</p>}
      {position.source === 'actual_device' && <p className="text-xs text-slate-500">Reported device GPS</p>}
      {!fresh && <p className="text-xs text-amber-900">Current movement is unknown. Check the tracking phone and connection.</p>}
      {poor && <p className="text-xs text-amber-900">This sample is not used to confirm arrival.</p>}
    </>}
    <p className="text-xs text-slate-500">Missing GPS is not evidence of a stopped vehicle. Planned ETAs are separate.</p>
  </section>;
}
