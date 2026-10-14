import {useEffect,useRef,useState} from 'react';
import {workspaceViewApi} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';

export function WorkspaceOnlineSettings() {
  const {overview,error,refresh}=useWorkspaceMemoryView();
  const [draft,setDraft]=useState({logos:false,maps:false});
  const [revision,setRevision]=useState(0);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const pending=useRef(false);
  useEffect(()=>{if(overview){setDraft(overview.online);setRevision(overview.online_revision);}},[overview?.online_revision]);
  async function save(){
    if(!overview||pending.current) return;
    pending.current=true;setBusy(true);setMessage('');
    try{await workspaceViewApi.save('preferences','online',draft,revision);setMessage('Online-Auswahl gespeichert.');}
    catch{setMessage('Speichern nicht bestätigt. Bitte den aktuellen Stand neu laden und erneut prüfen.');}
    finally{pending.current=false;setBusy(false);}
  }
  return <section id="workspace-online" className="settings-section"><h2>Bilder und Karte aus dem Internet</h2>
    <p>Eigene Bilder und Koordinaten funktionieren lokal. Beide Online-Funktionen sind zunächst ausgeschaltet.</p>
    <fieldset disabled={busy||!overview}><label><input type="checkbox" checked={draft.logos} onChange={e=>setDraft({...draft,logos:e.target.checked})}/>Firmenbilder erlauben</label>
      <p>Ein Firmenbild wird erst nach deiner Bestätigung einer öffentlichen Domain geladen und danach lokal gespeichert. Dabei sieht die Firmenseite deine Internetadresse. Es werden keine Mails, Namen oder Rechnungen übertragen.</p>
      <label><input type="checkbox" checked={draft.maps} onChange={e=>setDraft({...draft,maps:e.target.checked})}/>Onlinekarte erlauben</label>
      <p>Beim Öffnen der Ortskarte erhält OpenStreetMap deine Internetadresse und den angezeigten Kartenausschnitt. Namen und Originalquellen bleiben lokal. Es findet keine automatische Adresssuche statt.</p>
      <button type="button" onClick={()=>void save()}>Auswahl speichern</button>
    </fieldset>
    {!overview&&!error&&<p role="status">Online-Auswahl wird geladen …</p>}
    {(error||message)&&<p role="status">{message||'Die Online-Auswahl konnte nicht geladen werden.'} <button disabled={busy} type="button" onClick={()=>void refresh()}>Aktuellen Stand laden</button></p>}
  </section>;
}
