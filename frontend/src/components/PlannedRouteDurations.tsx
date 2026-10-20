import { durationLabel, serviceDateLabel } from '../services/uiFormat';
import type { StoredRoute } from '../services/api';

const fields = [
  ['Driving', 'driving_seconds'], ['Service', 'service_seconds'],
  ['Waiting', 'waiting_seconds'], ['Total duration', 'total_duration_seconds'],
] as const;
export const savedSeconds = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? `${value} s` : 'Unknown';

export const savedMinutes = durationLabel;

/** Read saved totals verbatim. No freshness filter, inferred totals or live elapsed time. */
export function PlannedRouteDurations({ route, context = 'Saved plan' }: { route: StoredRoute | null; context?: string }) {
  const missing = !!route && fields.some(([, field]) => savedSeconds(route[field]) === 'Unknown');
  return <section aria-label="Saved planned durations" className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 text-xs text-slate-600">
    <h3 className="font-semibold text-slate-800">Estimated duration</h3>
    {route ? <p className="break-all" data-testid="duration-route">{context} / Version {route.version} / {serviceDateLabel(route.service_date)}</p> : <p>No authorized saved route for this selection.</p>}
    <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {fields.map(([label, field]) => <div key={field} className="rounded-lg bg-slate-50 p-2">
        <dt>{label}</dt><dd data-testid={`planned-${field}`} className="font-semibold text-slate-800">{durationLabel(route?.[field])}</dd>
      </div>)}
    </dl>
    <p>Planned journey time, including stops and waiting. Actual travel may differ.</p>
    {missing && <p>Some estimates are unavailable for this saved plan.</p>}
  </section>;
}
