import { Ambulance, Flame, PhoneCall, ShieldAlert, X } from 'lucide-react';

const EMERGENCY_SERVICES = [
  { name: 'Police Emergency', number: '119', description: 'Immediate police assistance', icon: ShieldAlert, tone: 'bg-blue-600 hover:bg-blue-700' },
  { name: 'Fire & Rescue', number: '110', description: 'Fire Brigade and rescue service', icon: Flame, tone: 'bg-orange-600 hover:bg-orange-700' },
  { name: 'Hospital Ambulance', number: '1990', description: 'Suwa Seriya emergency ambulance', icon: Ambulance, tone: 'bg-green-600 hover:bg-green-700' }
];

export function EmergencyCallPanel({ onClose, context }: {onClose: () => void;context: string}) {
  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-4">
      <button aria-label="Close emergency contacts" className="absolute inset-0 bg-red-950/65 backdrop-blur-sm" onClick={onClose} />
      <section className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border-t-4 border-red-600">
        <header className="p-5 border-b border-slate-100 flex justify-between items-start">
          <div><p className="text-xs font-bold text-red-600 uppercase tracking-wider">Emergency assistance</p><h2 className="text-xl font-bold text-slate-800 mt-1">Call emergency service</h2><p className="text-sm text-slate-500 mt-1">{context}</p></div>
          <button onClick={onClose} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"><X size={18} /></button>
        </header>
        <div className="p-5 space-y-3">
          {EMERGENCY_SERVICES.map((service) => <a key={service.number} href={`tel:${service.number}`} className={`w-full p-4 rounded-xl text-white flex items-center gap-4 shadow-sm transition-colors ${service.tone}`}><span className="w-11 h-11 rounded-full bg-white/20 flex items-center justify-center"><service.icon size={23} /></span><span className="flex-1"><span className="font-bold block">{service.name}</span><span className="text-xs text-white/80">{service.description}</span></span><span className="text-right"><span className="font-black text-xl block">{service.number}</span><PhoneCall size={15} className="ml-auto mt-1" /></span></a>)}
        </div>
        <p className="px-5 pb-5 text-xs text-center text-slate-500">Use emergency numbers only when immediate assistance is required.</p>
      </section>
    </div>
  );
}
