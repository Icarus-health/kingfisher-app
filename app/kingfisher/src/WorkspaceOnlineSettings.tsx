import {useEffect,useRef,useState} from 'react';
import { Schalter } from "./grundlage";
import {workspaceViewApi} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';

type Online={logos:boolean;maps:boolean};

// Einstellungen → Was Kingfisher darf → Bilder und Karte aus dem Internet: zwei Schalter wie die übrigen, beide aus,
// bis man sie einschaltet. Ein Umlegen gilt sofort (gespeichert mit dem Stand, den die Seite zuletzt gelesen hat);
// unter jedem Schalter steht, was dabei den Rechner verlässt.
export function WorkspaceOnlineSettings() {
  const {overview,error,refresh}=useWorkspaceMemoryView();
  const [draft,setDraft]=useState<Online>({logos:false,maps:false});
  const [revision,setRevision]=useState(0);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const pending=useRef(false);
  useEffect(()=>{if(overview){setDraft(overview.online);setRevision(overview.online_revision);}},[overview?.online_revision]);
  async function save(next:Online){
    if(!overview||pending.current) return;
    pending.current=true;setBusy(true);setMessage('');setDraft(next);
    try{await workspaceViewApi.save('preferences','online',next,revision);setMessage('Online-Auswahl gespeichert.');}
    catch{setDraft(draft);setMessage('Speichern nicht bestätigt. Bitte den aktuellen Stand neu laden und erneut prüfen.');}
    finally{pending.current=false;setBusy(false);}
  }
  return <section id="workspace-online" className="settings-section darf-gruppe" aria-labelledby="workspace-online-titel">
    <div className="g-gruppe-kopf"><h2 className="g-gruppe-titel" id="workspace-online-titel">Bilder und Karte aus dem Internet</h2></div>
    <fieldset className="darf darf-online" disabled={busy||!overview}>
      <div className="darf-zeile"><Schalter titel="Firmenbilder erlauben" an={draft.logos} onWechsel={logos=>void save({...draft,logos})}
        satz={<>Ein Firmenbild wird erst nach deiner Bestätigung einer öffentlichen Domain geladen und danach lokal gespeichert. Dabei sieht die Firmenseite deine Internetadresse. Es werden keine Mails, Namen oder Rechnungen übertragen.</>} /></div>
      <div className="darf-zeile"><Schalter titel="Onlinekarte erlauben" an={draft.maps} onWechsel={maps=>void save({...draft,maps})}
        satz={<>Beim Öffnen der Ortskarte erhält OpenStreetMap deine Internetadresse und den angezeigten Kartenausschnitt. Namen und Originalquellen bleiben lokal. Es findet keine automatische Adresssuche statt.</>} /></div>
    </fieldset>
    <p className="g-gruppe-fussnote">Eigene Bilder und Koordinaten funktionieren lokal.</p>
    {!overview&&!error&&<p role="status" className="g-gruppe-fussnote">Online-Auswahl wird geladen …</p>}
    {(error||message)&&<p role="status" className="g-gruppe-fussnote">{message||'Die Online-Auswahl konnte nicht geladen werden.'} {error||message.startsWith('Speichern nicht')?<button className="g-knopf-schlicht g-kompakt" disabled={busy} type="button" onClick={()=>void refresh()}>Aktuellen Stand laden</button>:null}</p>}
  </section>;
}
