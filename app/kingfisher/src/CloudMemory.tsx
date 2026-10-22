import {useEffect, useRef, useState} from "react";
import {api, type CloudMemoryJob, type CloudMemoryPreview, type CloudMemoryPurpose, type CloudMemoryProvider, type CloudAccessState} from "./api";
import {prepareCloudPreview} from "./cloud-preview";
import {ProfileSource} from "./ProfileSource";
import {listenForCloudAccessChange} from "./cloudAccessEvents";
import {cloudIssueText} from "./cloud-issues";

export function CloudMemory({model, connected}:{model:string;connected:boolean}) {
  const [job,setJob] = useState<CloudMemoryJob|null>(null);
  const [preview,setPreview] = useState<CloudMemoryPreview|null>(null);
  const [consent,setConsent] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [bulkCursor,setBulkCursor] = useState<number|undefined>();
  const [provider,setProvider] = useState<CloudMemoryProvider>("chatgpt");
  const [access,setAccess] = useState<CloudAccessState|null>(null);
  const anthropic = access?.providers.find(item=>item.id==="anthropic");
  const selectedModel = provider==="anthropic" ? anthropic?.model??"" : model;
  const providerLabel = provider==="anthropic" ? "Claude API" : "ChatGPT";
  const recipient = provider==="anthropic" ? "Anthropic" : "OpenAI";
  const alive = useRef(false);
  const locked = useRef(false);

  useEffect(() => {
    alive.current = true;
    let timer:ReturnType<typeof setTimeout>|undefined;
    const load = async () => {
      try {
        const next = await api.cloudMemoryStatus();
        if (alive.current && !locked.current) {setJob(next.job); setError("");}
      } catch {if(alive.current && !locked.current) setError("Der Arbeitsstand konnte nicht geladen werden.");}
      if(alive.current) timer=setTimeout(load,document.hidden ? 15000 : 3000);
    };
    void load();
    return () => {alive.current=false;clearTimeout(timer);};
  },[]);

  useEffect(() => {
    let cancelled=false;
    const load=async()=>{try{const next=await api.cloudAccess();if(!cancelled)setAccess(next);}catch{if(!cancelled)setAccess(null);}};
    void load();
    const stop=listenForCloudAccessChange(()=>{setPreview(null);setConsent(false);void load();});
    return()=>{cancelled=true;stop();};
  },[]);
  useEffect(() => {setConsent(false);setPreview(null);setBulkCursor(undefined);},[model,connected,provider,anthropic?.model]);

  async function action(work:()=>Promise<void>) {
    if(locked.current) return;
    locked.current=true;setBusy(true);setError("");
    try {await work();}
    catch(e) {if(alive.current)setError(e instanceof Error ? e.message : "Bitte erneut versuchen.");}
    finally {locked.current=false;if(alive.current)setBusy(false);}
  }

  function prepare(purpose:CloudMemoryPurpose,cursor?:number) {
    void action(async()=>{
      const next = await prepareCloudPreview((scope,nextCursor)=>api.cloudMemoryPreview(scope,nextCursor,provider),purpose,cursor??(purpose==="bulk"?bulkCursor:undefined));
      if(alive.current){setPreview(next.preview);setConsent(false);if(purpose==="bulk")setBulkCursor(next.cursor);}
    });
  }

  const running = job?.state === "running";
  const active = running || job?.state === "paused";
  const ready = provider==="anthropic" ? Boolean(anthropic?.import_available && selectedModel) : connected && Boolean(model);
  return <section className="cloud-memory" aria-label="Gedächtnis mit Cloud-Anbieter einordnen">
    <details className="cloud-memory-tools"><summary>Mails prüfen oder neu einordnen</summary>
    <label>Anbieter für dieses Paket<select value={provider} disabled={busy||running} onChange={event=>setProvider(event.target.value as CloudMemoryProvider)}>
      <option value="chatgpt">ChatGPT-Abo</option><option value="anthropic">Anthropic · Claude API</option>
    </select></label>
    {provider==="anthropic" ? <p className="source-hint">Claude API nutzt den unter Cloud-Zugänge gespeicherten Schlüssel und das dort gewählte Modell. Der Alltag läuft lokal, oder über die Cloud-Einordnung neuer Mails unter Was Kingfisher darf. Modell: {selectedModel||"noch nicht eingerichtet"}.</p>:null}
    <details className="quiet-details"><summary>Wie die Einordnung funktioniert</summary>
      <p>Der gewählte Anbieter prüft Aussagen, Themen und erwähnte Menschen anhand der Originalmails. Ergebnisse bleiben Quellenbefunde; sie werden nicht automatisch zu bestätigten Fakten oder erledigten Aufgaben.</p>
      <p>Deine Originale und bestätigten Korrekturen bleiben erhalten. Der bestehende Mailabruf und seine Pause werden hierdurch nicht geändert.</p>
      <p>Größere Pakete enthalten höchstens 1.000 Mails und werden erst nach einem vollständig verarbeiteten ersten Paket freigegeben. Nachprüfen kannst du auch bereits eingeordnete Mails.</p>
    </details>
    {!ready ? <p className="source-hint">Für die Auswertung den gewählten Zugang einrichten und ein Modell wählen. Vorschau ohne Cloud-Zugriff möglich.</p> : null}
    <div className="source-form-actions">
      <button type="button" className="primary-action" disabled={busy||active} onClick={()=>prepare("pilot")}>100 Mails prüfen</button>
      <button type="button" className="secondary-action" disabled={busy||active} onClick={()=>prepare("bulk")}>Größeren Bestand vorbereiten</button>
      <button type="button" className="secondary-action" disabled={busy||active} onClick={()=>prepare("recheck")}>Bestehende Einordnung nachprüfen</button>
    </div>
    </details>
    {preview ? <div className="cloud-memory-preview">
      <h4>{preview.purpose === "pilot" ? "Erstes Paket" : preview.purpose === "recheck" ? "Nachprüfung" : "Nächstes Paket"}: {preview.count} Mails</h4>
      <p>Diese Vorschau hat noch nichts an {recipient} gesendet.</p>
      {preview.request_limit!==undefined&&preview.count>0 ? <p className="source-hint">Für dieses Paket sind höchstens {preview.request_limit} Modellaufrufe freigegeben. Längere Mailverläufe werden in Abschnitten geprüft.</p>:null}
      {(preview.filtered_count||preview.review_count) ? <p className="source-hint">{preview.filtered_count||0} Mails durch Filter zurückgehalten{preview.review_count ? ` · ${preview.review_count} zur Prüfung zurückgestellt`:""}. Dafür erfolgt kein Cloud-Aufruf. Originalmails bleiben erhalten; gewünschte Absender kannst du im Mailfilter erlauben.</p>:null}
      {preview.sampling_note ? <p className="source-hint">{preview.sampling_note}</p> : null}
      {!preview.count ? <p>In diesem Quellenabschnitt stehen keine passenden Mails aus.{preview.next_cursor ? " Ältere Quellen können noch geprüft werden." : " Dieser Durchgang hat das Ende des Bestands erreicht."}</p>:null}
      {!preview.count&&preview.next_cursor ? <button type="button" className="secondary-action" disabled={busy} onClick={()=>prepare(preview.purpose,preview.next_cursor!)}>Nächsten Quellenabschnitt prüfen</button>:null}
      <ul>{preview.sources.slice(0,5).map(source=><li key={source.id}>{source.title||"Ohne Betreff"}{source.occurred_at ? ` · ${new Date(source.occurred_at).toLocaleDateString("de-DE")}`:" · Datum ungeklärt"}</li>)}</ul>
      {preview.count>5 ? <p className="source-hint">Und {preview.count-5} weitere Mails aus diesem Paket.</p>:null}
      <label className="chatgpt-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/><span>Ich erlaube, den Inhalt und die zugehörigen Metadaten dieser {preview.count} Mails an {recipient} zu senden. Die Verarbeitung ist nicht ausschließlich lokal oder auf die EU begrenzt.</span></label>
      <p className="source-hint">{provider==="anthropic" ? "Verwendet separat bezahltes Anthropic-API-Guthaben. Die Paket-, Anfrage- und Tokenlimits sind keine garantierte Euro-Obergrenze. Guthaben und Kosten vor Freigabe im Anthropic-Konto prüfen." : "Verwendet dein ChatGPT-Abo und dessen Kontingent. Kein Wechsel auf eine zusätzlich bezahlte API."} Der Lauf stoppt an der Paket- oder Anfragegrenze.</p>
      <p className="source-hint">Ein verarbeiteter Auftrag bestätigt noch keine fachliche Qualität. Ergebnisse anschließend unabhängig gegen Originalquellen prüfen.</p>
      <button type="button" className="primary-action" disabled={busy||!ready||!consent||!preview.count||active} onClick={()=>void action(async()=>{
        const next=await api.cloudMemoryStart(preview.preview_id,selectedModel,provider);
        if(alive.current){setJob(next.job);setPreview(null);setConsent(false);}
      })}>Diese {preview.count} Mails mit {providerLabel} auswerten</button>
    </div>:null}
    {job ? <div aria-live="polite" className="cloud-memory-progress">
      <h4>{job.state === "running" ? "Einordnung läuft" : job.state === "complete" ? "Paket durchgesehen" : job.state === "complete_with_gaps" ? "Paket mit offenen Quellen durchgesehen" : job.state === "paused" ? "Einordnung pausiert" : "Einordnung gestoppt"}</h4>
      <progress max={Math.max(1,job.selected)} value={job.position} aria-label="Durchgesehene Mails"/>
      <p>{job.position} von {job.selected} Mails durchgesehen · {job.completed} vollständig eingeordnet{job.failed ? ` · ${job.failed} offen oder fehlgeschlagen`:""}</p>
      <p className="source-hint">{job.requests} von höchstens {job.request_limit} Modellaufrufen · {job.provider==="anthropic" ? "Claude API" : "ChatGPT-Abo"} · Modell {job.model}</p>
      {job.stop_reason ? <p role="status">{job.stop_reason}</p>:null}
      {job.state === "complete_with_gaps" ? <p>Einige Quellen konnten nicht vollständig eingeordnet werden. Diese Probe gibt den größeren Lauf noch nicht frei.</p>:null}
      {job.issues?.length ? <details>
        <summary>{job.issue_count??job.issues.length} Mails brauchen eine Nachprüfung</summary>
        <p>Die betroffene Einordnung wurde nicht übernommen. Hier siehst du höchstens zehn offene Quellen; ihre Originale bleiben erhalten.</p>
        <ul>{job.issues.map((issue,index)=><li key={`${issue.episode_id}:${index}`}>
          <span>{cloudIssueText(issue)}</span>
          <ProfileSource kind="episode" id={issue.episode_id} label="Originalmail öffnen" readOnly allowIgnore={false}/>
        </li>)}</ul>
      </details>:null}
      {job.state === "paused"&&job.provider!=="anthropic"&&/Kontingent|Anfragelimit/i.test(job.stop_reason) ? <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">Nutzung in ChatGPT verwalten</a>:null}
      {job.state === "complete" && job.purpose === "pilot" ? <p>Die Probe ist verarbeitet. Prüfe jetzt Menschen, Themen und einige Antworten gegen die Originalmails. Erst danach den größeren Bestand freigeben.</p>:null}
      {job.state === "paused"&&ready&&(selectedModel!==job.model||(job.provider??"chatgpt")!==provider) ? <p>Wähle den Anbieter {job.provider==="anthropic"?"Claude API":"ChatGPT"} und das Modell {job.model}, um dieses Paket fortzusetzen. Für einen anderen Zugang oder ein anderes Modell widerrufe zuerst die bisherige Freigabe und bereite ein neues Paket vor.</p>:null}
      <div className="source-form-actions">
        {running ? <button type="button" disabled={busy} className="secondary-action" onClick={()=>void action(async()=>{const next=await api.cloudMemoryAction("pause",job.id);if(alive.current)setJob(next.job);})}>Pausieren</button>:null}
        {job.state === "paused" ? <button type="button" disabled={busy||!ready||selectedModel!==job.model||(job.provider??"chatgpt")!==provider} className="primary-action" onClick={()=>void action(async()=>{const next=await api.cloudMemoryAction("resume",job.id);if(alive.current)setJob(next.job);})}>Dieses Paket fortsetzen</button>:null}
        {active ? <button type="button" disabled={busy} className="secondary-action" onClick={()=>void action(async()=>{const next=await api.cloudMemoryAction("revoke",job.id);if(alive.current)setJob(next.job);})}>Freigabe widerrufen</button>:null}
        <a href="/memory?view=status">Gedächtnis und Quellen ansehen</a>
      </div>
    </div>:null}
    {error ? <p role="alert">{error}</p>:null}
    {busy ? <p role="status">Arbeitsgang wird vorbereitet …</p>:null}
  </section>;
}
