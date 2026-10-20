import { vehicleLabel } from '../services/uiFormat';
import { useState } from 'react';
import { retryRoutingEvent, RouteComparison, RoutingOutcome } from '../services/api';

export function RouteComparisonView({ value }: { value: Partial<RouteComparison> }) {
  if (!value.before && !value.after) return null;
  return <div className="space-y-2 text-xs">
    <p className="text-slate-600">Before: {value.before ? `version ${value.before.version}, roster ${value.before.roster_version} (${value.before.feasibility_status})` : 'No earlier route'}<br />
      After: {value.after ? `version ${value.after.version}, roster ${value.after.roster_version} (${value.after.feasibility_status})` : 'No new result available'}</p>
    <p className="text-slate-500">Duration source before: {value.before?.provider_source?.duration_source ?? 'Unavailable'}; after: {value.after?.provider_source?.duration_source ?? 'Unavailable'}. Historical results may use different inputs, scenarios or matrices; these deltas are not optimization savings.</p>
    <table className="w-full text-left border-collapse"><thead><tr className="text-slate-500"><th>Actual result</th><th>Before</th><th>After</th><th>After − before</th></tr></thead><tbody>
      {([
        ['distance_metres', 'Approx. distance (m)'], ['driving_seconds', 'Driving estimate (s)'],
        ['service_seconds', 'Service (s)'], ['waiting_seconds', 'Waiting (s)'], ['total_duration_seconds', 'Total (s)'],
      ] as const).map(([field, label]) => {
        const delta = value.delta_after_minus_before?.[field];
        return <tr key={field} className="border-t border-slate-200"><th className="py-1 font-normal">{label}</th><td>{value.before?.[field] ?? 'Unavailable'}</td><td>{value.after?.[field] ?? 'Unavailable'}</td><td>{delta == null ? 'Unavailable' : delta > 0 ? `+${delta}` : String(delta)}</td></tr>;
      })}
    </tbody></table>
    {value.itinerary_changed === false && <p className="font-medium text-slate-700">Itinerary unchanged. No positive savings are assumed.</p>}
    {value.itinerary_changed === true && <p className="text-slate-600">The itinerary changed. Deltas may increase, decrease, or stay zero.</p>}
  </div>;
}

export function RoutingOutcomeNotice({ outcome, title = 'Input saved' }: { outcome: RoutingOutcome; title?: string }) {
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState('');
  const failed = outcome.outcome === 'failed';
  const heading = failed ? `${title}; routing failed` : outcome.outcome === 'deferred' ? `${title}; active/completed trip unchanged` : outcome.outcome === 'unchanged' ? `${title}; inputs unchanged` : outcome.outcome === 'superseded' ? `${title}; a newer change owns the plan` : `${title}; pre-trip routes refreshed`;
  return <section role={failed ? 'alert' : 'status'} className={`rounded-xl p-4 border text-sm space-y-3 ${failed ? 'bg-amber-50 border-amber-200 text-amber-900' : 'bg-blue-50 border-blue-100 text-slate-700'}`}>
    <p className="font-semibold">{heading}</p>
    {outcome.errors.length > 0 && <ul className="list-disc pl-5">{outcome.errors.map((message) => <li key={message}>{message}</li>)}</ul>}
    <ul className="space-y-2">{outcome.plans.map(plan => <li key={`${plan.vehicle_id}:${plan.direction}`} className="border-t border-slate-200 pt-2">
      <p className="font-medium">{vehicleLabel(plan.vehicle_id)} · {plan.direction === 'morning' ? 'Morning' : 'Afternoon'} route · {plan.generation_status.replace(/_/g, ' ')}{plan.route_version != null ? ` · Version ${plan.route_version}` : ''}</p>
      {plan.errors?.map(message => <p key={message} className="mt-1 text-xs text-amber-900">{message}</p>)}
    </li>)}</ul>
    {failed && (outcome.generation_status === 'pending' || outcome.plans.some((plan) => plan.generation_status === 'error')) && <button type="button" disabled={retrying} className="font-medium underline disabled:opacity-50" onClick={async () => {
      setRetrying(true); setError('');
      try { await retryRoutingEvent(outcome.event_id); } catch (failure) { setError(failure instanceof Error ? failure.message : 'Routing retry failed.'); }
      finally { setRetrying(false); }
    }}>{retrying ? 'Retrying routing...' : 'Retry routing only'}</button>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
