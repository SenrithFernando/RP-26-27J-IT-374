import type { StoredRoute } from '../services/api';

const fields = [
  ['Driving', 'driving_seconds'], ['Service', 'service_seconds'],
  ['Waiting', 'waiting_seconds'], ['Total duration', 'total_duration_seconds'],
] as const;
export const savedSeconds = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? `${value} s` : 'Unknown';

/** Read saved totals verbatim. No freshness filter, inferred totals or live elapsed time. */
export function PlannedRouteDurations({ route, context = 'Saved plan' }: { route: StoredRoute | null; context?: string }) {
  const missing = !!route && fields.some(([, field]) => savedSeconds(route[field]) === 'Unknown');
  const terminal = route?.stops[route.stops.length - 1];
  return <section aria-label="Saved planned durations" className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 text-xs text-slate-600">
    <h3 className="font-semibold text-slate-800">Saved planned durations</h3>
    {route ? <p className="break-all" data-testid="duration-route">{context}: {route.route_id} / version {route.version} / {route.direction} / {route.service_date}</p> : <p>No authorized saved route for this selection.</p>}
    <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {fields.map(([label, field]) => <div key={field} className="rounded-lg bg-slate-50 p-2">
        <dt>{label}</dt><dd data-testid={`planned-${field}`} className="font-semibold text-slate-800">{savedSeconds(route?.[field])}</dd>
      </div>)}
    </dl>
    <p>Planned estimates in seconds, not actual elapsed trip time. Total includes driving, service and waiting.</p>
    {missing && <p>Older or incomplete saved snapshot: missing duration fields are unknown. This snapshot has not been recalculated.</p>}
    {route && <details><summary className="cursor-pointer">Duration accounting</summary>
      <p>Plan ends after service at the final saved stop. Final-stop service included: {savedSeconds(terminal?.service_seconds)}.</p>
      <p>{route.end_policy === 'last_school_no_depot_return' ? 'Morning ends at the last school; no depot-return leg.' : route.end_policy === 'SCH_B_then_SCH_A_then_homes_then_depot' ? 'Afternoon includes the final depot-return leg.' : 'Endpoint policy is not recorded for this snapshot; inspect its saved itinerary.'}</p>
      <p>Grouped school service is counted once per visit. The operational pickup window overlaps planned boarding service; its deadline is not added again.</p>
    </details>}
  </section>;
}
