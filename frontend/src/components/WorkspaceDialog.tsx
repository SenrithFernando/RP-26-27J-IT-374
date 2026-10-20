import { ReactNode, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/** Focused task surface. Closing hides rather than unmounts live GPS capture. */
export function WorkspaceDialog({title,open,onClose,children,keepMounted=false}:{title:string;open:boolean;onClose:()=>void;children:ReactNode;keepMounted?:boolean}) {
  const [visited,setVisited]=useState(open);
  const ref=useRef<HTMLDialogElement>(null),heading=useId();
  useEffect(()=>{
    if(open)setVisited(true);
    const dialog=ref.current;
    if(open&&!dialog?.open)dialog?.showModal();
    if(!open&&dialog?.open)dialog.close();
  },[open]);
  return createPortal(<dialog ref={ref} aria-labelledby={heading} onCancel={event=>{event.preventDefault();onClose();}} className="w-[calc(100%-1.5rem)] max-w-3xl max-h-[90dvh] rounded-2xl bg-white p-0 shadow-xl backdrop:bg-slate-900/40">
    <div className="sticky top-0 z-[1200] flex items-center justify-between gap-3 border-b bg-white px-5 py-4"><h2 id={heading} className="text-lg font-bold text-slate-900">{title}</h2><button type="button" onClick={onClose} aria-label={`Close ${title}`} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={20}/></button></div>
    <div className="p-5 space-y-4">{(open||(keepMounted&&visited))&&children}</div>
  </dialog>,document.body);
}
