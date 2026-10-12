import {useState} from 'react';
import {DocumentImport} from './DocumentImport';

export function ConversationCapture() {
  const [open,setOpen]=useState(false);
  return <section className="conversation-capture" aria-label="Gesprächsquellen aufnehmen">
    {open ? <DocumentImport initiallyExpanded showLibrary={false} title="Gespräch oder Datei aufnehmen" onClose={()=>setOpen(false)} />
      : <button className="secondary-action" type="button" onClick={()=>setOpen(true)}>Datei oder Transkript aufnehmen</button>}
    {open && <p className="health-help">Die Aufnahme speichert eine Gedächtnisquelle. Sie hängt den Text nicht automatisch an dieses Gespräch an. Du kannst anschließend im Gedächtnis nach dem Inhalt suchen. Audiodateien werden hier noch nicht transkribiert.</p>}
  </section>;
}
