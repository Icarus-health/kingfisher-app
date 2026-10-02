import {useEffect, useState} from "react";
import {api, type MemoryAutomation} from "./api";

export function MemoryAutomationSettings({active}: {active:boolean}) {
  const [state,setState]=useState<MemoryAutomation|null>(null);
  const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  useEffect(()=>{if(!active)return;let current=true; api.memoryAutomation().then(value=>{if(current)setState(value);}).catch(()=>{if(current)setError("Status des Sortierens nicht erreichbar.");}); return ()=>{current=false;};},[active]);
  async function change(enabled:boolean){setBusy(true);setError("");try{setState(await api.setMemoryAutomation(enabled));}catch{setError("Das Sortieren konnte nicht geändert werden. Bitte die lokale KI prüfen.");}finally{setBusy(false);}}
  return <section className="source-section"><h2>Quellen automatisch sortieren</h2><p>{state ? state.state === "active" ? "Aktiv · freigegebene Quellen werden lokal sortiert." : state.state === "legacy_active" ? "Bisherige Automatik aktiv; lokale Ausführung noch nicht abgesichert." : state.requested ? "Angefordert, aber derzeit nicht aktiv. Bitte die lokale KI prüfen." : "Pausiert" : error ? "Status unbekannt" : "Status wird geladen …"}</p>
    <p className="source-hint">Aus vorhandenen und künftig freigegebenen Quellen entstehen Zusammenfassungen sowie Aufgaben- und Wissensvorschläge. Es werden keine neuen Quellen freigegeben, Nachrichten versendet oder Aussagen automatisch bestätigt.</p>
    <button className="secondary-action" type="button" disabled={busy||!state} onClick={()=>change(!(state?.requested || state?.state === "legacy_active"))}>{state?.requested || state?.state === "legacy_active" ? "Sortieren pausieren" : "Automatisches Sortieren einschalten"}</button>
    {state?.state === "legacy_active" && <button className="secondary-action" type="button" disabled={busy} onClick={()=>change(true)}>Lokal absichern</button>}
    {error&&<p role="alert">{error}</p>}</section>;
}
