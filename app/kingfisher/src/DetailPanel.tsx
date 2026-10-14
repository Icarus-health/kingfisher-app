import {useEffect, useRef, useState, type ReactNode} from 'react';
import './DetailPanel.css';

export function DetailPanel({title, children, onClose}: {title:string; children:ReactNode; onClose:()=>void}) {
  const button = useRef<HTMLButtonElement>(null);
  const panel=useRef<HTMLElement>(null);
  const [narrow,setNarrow]=useState(()=>typeof window!=='undefined' && Boolean(window.matchMedia?.('(max-width:900px)').matches));
  useEffect(()=>{const media=window.matchMedia?.('(max-width:900px)');if(!media)return;const changed=()=>setNarrow(media.matches);media.addEventListener('change',changed);return()=>media.removeEventListener('change',changed);},[]);
  const close = useRef(onClose); close.current = onClose;
  useEffect(()=>{
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    button.current?.focus({preventScroll:true});
    const escape = (event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();close.current();}};
    window.addEventListener('keydown',escape);
    return ()=>{window.removeEventListener('keydown',escape);if(previous?.isConnected) previous.focus({preventScroll:true});else {const fallback=document.querySelector<HTMLElement>('main button');fallback?.focus({preventScroll:true});}};
  },[]);
  return <aside ref={panel} className="workspace-detail" role="dialog" aria-label={title} aria-modal={narrow||undefined} onKeyDown={event=>{
    if(!narrow||event.key!=='Tab'||!panel.current)return;
    const fields=Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(node=>node.getClientRects().length>0);
    const first=fields[0],last=fields.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  }}>
    <header><h2>{title}</h2><button ref={button} type="button" onClick={onClose} aria-label={`${title} schließen`}>Schließen</button></header>
    <div className="workspace-detail-body">{children}</div>
  </aside>;
}
