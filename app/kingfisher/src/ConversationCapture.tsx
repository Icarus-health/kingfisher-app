import {useState} from 'react';
import {DocumentImport} from './DocumentImport';

export function ConversationCapture() {
  const [open,setOpen]=useState(false);
  return <section className="conversation-capture" aria-label="Gesprächsquellen aufnehmen">
    {open ? <DocumentImport initiallyExpanded showLibrary={false} title="Gespräch oder Datei aufnehmen" onClose={()=>setOpen(false)} />
      : <button className="g-knopf-schlicht conversation-capture-knopf" type="button" onClick={()=>setOpen(true)}>Datei oder Transkript aufnehmen</button>}
    {open && <p className="health-help conversation-capture-fuss">Die Datei wird eine Quelle im Gedächtnis, nicht Teil dieses Gesprächs. Audio wird hier noch nicht umgeschrieben.</p>}
  </section>;
}
