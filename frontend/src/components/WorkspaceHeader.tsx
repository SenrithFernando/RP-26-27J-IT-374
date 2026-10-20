import { ReactNode } from 'react';
import { LogOut, Menu } from 'lucide-react';
import { BrandLogo } from './BrandLogo';

/** Proposal header structure with the authenticated account, never demo status. */
export function WorkspaceHeader({title,subtitle,username,onLogout,onMenu,actions,driver=false}:{title:string;subtitle?:string;username?:string;onLogout?:()=>void;onMenu?:()=>void;actions?:ReactNode;driver?:boolean}) {
  return <header className={`shrink-0 px-4 md:px-8 py-3 md:py-5 flex items-center justify-between gap-3 relative z-20 ${driver?'bg-[#176B87] text-white rounded-b-2xl shadow-md':'bg-white border-b border-slate-200'}`}>
    <div className="flex items-center gap-3 min-w-0">{driver&&<BrandLogo decorative className="hidden sm:block w-11 h-11 rounded-xl shadow-sm"/>}{onMenu&&<button aria-label="Open navigation" onClick={onMenu} className="md:hidden p-2 -ml-2 text-[#176B87]"><Menu size={22}/></button>}<div className="min-w-0"><h1 className={`text-lg md:text-xl font-semibold truncate ${driver?'text-white':'text-[#17212B]'}`}>{title}</h1>{subtitle&&<p className={`text-xs md:text-sm mt-1 ${driver?'text-blue-100':'text-slate-500'}`}>{subtitle}</p>}</div></div>
    <div className="flex items-center gap-2 md:gap-4 shrink-0">{actions}{username&&<span className={`hidden md:block text-sm ${driver?'text-blue-100':'text-slate-600'}`}>{username}</span>}{onLogout&&<button onClick={onLogout} aria-label="Log out" title="Log out" className={`flex items-center gap-2 text-sm p-2 ${driver?'text-white hover:bg-white/10 rounded-lg':'text-slate-600 hover:text-[#176B87]'}`}><span className="hidden md:inline">Log out</span><LogOut size={18}/></button>}{username&&<span title={username} className={`hidden sm:flex w-10 h-10 rounded-full items-center justify-center font-semibold ${driver?'bg-white/20 text-white':'bg-[#176B87] text-white'}`}>{username.slice(0,2).toUpperCase()}</span>}</div>
  </header>;
}
