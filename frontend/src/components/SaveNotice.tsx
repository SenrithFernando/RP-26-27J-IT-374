import { CheckCircle2, AlertCircle } from 'lucide-react';
export function SaveNotice({ message }: { message: string }) {
  const published = message === 'Dated route version published with recorded review.' || message === 'Route published';
  const needsAttention = /blocked|failed|unavailable/i.test(message);
  const Icon = needsAttention ? AlertCircle : CheckCircle2;
  return <div role="status" aria-live="polite" className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${needsAttention ? 'border-amber-200 bg-amber-50 text-amber-900' : 'border-emerald-200 bg-emerald-50 text-emerald-900'}`}>
    <Icon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
    <div><p className="text-sm font-semibold">{published ? 'Route published' : message}</p>
      {published && <p className="mt-0.5 text-sm text-emerald-800">Your review has been saved. The published plan is available to the assigned driver.</p>}
    </div>
  </div>;
}
