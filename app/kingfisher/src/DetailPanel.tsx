import {useEffect, useRef, type ReactNode} from 'react';
import './DetailPanel.css';

export function DetailPanel({title, children, onClose}: {title:string; children:ReactNode; onClose:()=>void}) {
  const button = useRef<HTMLButtonElement>(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(()=>{
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    button.current?.focus({preventScroll:true});
    const escape = (event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();close.current();}};
    window.addEventListener('keydown',escape);
    return ()=>{window.removeEventListener('keydown',escape);if(previous?.isConnected) previous.focus({preventScroll:true});};
  },[]);
  return <aside className="workspace-detail" role="dialog" aria-label={title}>
    <header><h2>{title}</h2><button ref={button} type="button" onClick={onClose} aria-label={`${title} schließen`}>Schließen</button></header>
    <div className="workspace-detail-body">{children}</div>
  </aside>;
}
