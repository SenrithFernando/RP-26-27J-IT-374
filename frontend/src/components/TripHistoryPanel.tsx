import { useMemo, useState } from 'react';
import { ArrowLeft, Bus, CalendarDays, CheckCircle2, Clock, MapPin, XCircle } from 'lucide-react';
import { Student } from '../types';
import { getStudentTripHistory, TripHistoryStatus } from '../data/tripHistory';

export function TripHistoryPanel({ student, onClose, mode = 'overlay' }: {student: Student;onClose: () => void;mode?: 'overlay' | 'page';}) {
  const [filter, setFilter] = useState<'ALL' | TripHistoryStatus>('ALL');
  const records = useMemo(() => getStudentTripHistory(student), [student]);
  const visible = records.filter((record) => filter === 'ALL' || record.status === filter);
  const completed = records.filter((record) => record.status === 'COMPLETED').length;
  const missed = records.filter((record) => record.status === 'MISSED').length;

  return (
    <div className={`${mode === 'overlay' ? 'fixed inset-0 z-[90] flex justify-end' : 'absolute inset-0 z-[80]'} bg-slate-900/35`}>
      {mode === 'overlay' && <button aria-label="Close history" className="absolute inset-0 cursor-default" onClick={onClose} />}
      <section className={`relative bg-slate-50 h-full shadow-2xl flex flex-col ${mode === 'overlay' ? 'w-full max-w-2xl' : 'w-full'}`}>
        <header className="bg-white border-b border-slate-200 px-5 py-4 flex items-center gap-3 shrink-0">
          <button onClick={onClose} aria-label="Back" className="p-2 -ml-2 rounded-lg text-slate-500 hover:bg-slate-100"><ArrowLeft size={20} /></button>
          <div className="min-w-0 flex-1">
            <h2 className="font-bold text-slate-800 text-lg truncate">Trip history</h2>
            <p className="text-sm text-slate-500 truncate">{student.name} · {student.id}</p>
          </div>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">Last 6 days</span>
        </header>

        <div className="p-5 overflow-y-auto flex-1">
          <div className="grid grid-cols-3 gap-3 mb-5">
            <Summary label="Total trips" value={records.length} tone="blue" />
            <Summary label="Completed" value={completed} tone="green" />
            <Summary label="Missed" value={missed} tone="red" />
          </div>

          <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
            {(['ALL', 'COMPLETED', 'MISSED'] as const).map((value) =>
              <button key={value} onClick={() => setFilter(value)} className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap ${filter === value ? 'bg-[#176B87] text-white' : 'bg-white border border-slate-200 text-slate-600'}`}>
                {value === 'ALL' ? 'All trips' : value.charAt(0) + value.slice(1).toLowerCase()}
              </button>
            )}
          </div>

          <div className="space-y-3">
            {visible.map((record) =>
              <article key={record.id} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <div className="flex justify-between gap-3 mb-3">
                  <div>
                    <p className="font-semibold text-slate-800">{record.trip}</p>
                    <p className="text-xs text-slate-500 flex items-center gap-1 mt-1"><CalendarDays size={12} /> {record.date}</p>
                  </div>
                  <Status status={record.status} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <Info icon={MapPin} label="From" value={record.pickupLocation} />
                  <Info icon={MapPin} label="To" value={record.destination} />
                  <Info icon={Clock} label="Boarded" value={record.boardedAt} />
                  <Info icon={Clock} label="Arrived" value={record.arrivedAt} />
                </div>
                <p className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 flex items-center gap-1.5"><Bus size={13} /> {record.vehicle} · Driver {record.driver}</p>
              </article>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function Summary({ label, value, tone }: {label: string;value: number;tone: 'blue' | 'green' | 'red';}) {
  const colors = { blue: 'bg-blue-50 text-blue-700', green: 'bg-green-50 text-green-700', red: 'bg-red-50 text-red-700' };
  return <div className={`rounded-xl p-3 ${colors[tone]}`}><p className="text-xl font-bold">{value}</p><p className="text-[11px] font-medium opacity-80">{label}</p></div>;
}

function Status({ status }: {status: TripHistoryStatus}) {
  const complete = status === 'COMPLETED';
  return <span className={`h-fit px-2 py-1 rounded-full text-[10px] font-bold flex items-center gap-1 ${complete ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
    {complete ? <CheckCircle2 size={11} /> : <XCircle size={11} />} {status}
  </span>;
}

function Info({ icon: Icon, label, value }: {icon: any;label: string;value: string}) {
  return <div><p className="text-slate-400 flex items-center gap-1"><Icon size={11} /> {label}</p><p className="text-slate-700 font-medium mt-0.5 truncate">{value}</p></div>;
}
