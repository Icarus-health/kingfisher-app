import {useEffect,useRef,useState} from "react";
import {api,type ChatGPTState,type ChatGPTModel} from "./api";
import {CloudMemory} from "./CloudMemory";
import "./ChatGPTAccess.css";

export function ChatGPTAccess() {
  const [state,setState]=useState<ChatGPTState|null>(null);
  const [models,setModels]=useState<ChatGPTModel[]>([]);
  const [model,setModel]=useState("");
  const [consent,setConsent]=useState(false);
  const [flow,setFlow]=useState<{session_id:string;url:string}|null>(null);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");
  const [account,setAccount]=useState("");
  const [welcome,setWelcome]=useState(false);
  const welcomeDialog=useRef<HTMLDialogElement>(null);
  const alive=useRef(false);
  const version=useRef(0);
  function dismissWelcome(){
    try{localStorage.setItem("kingfisher-chatgpt-welcome","seen");}catch{}
    welcomeDialog.current?.close();setWelcome(false);
  }
  useEffect(()=>{
    const dialog=welcomeDialog.current;
    if(welcome&&state?.available&&dialog&&!dialog.open) dialog.showModal();
  },[welcome,state?.available]);

  async function load() {
    const current=++version.current;
    const next=await api.chatgpt();
    if(!alive.current||version.current!==current)return;
    setState(next);
    if(next.available){
      try {setWelcome(localStorage.getItem("kingfisher-chatgpt-welcome")!=="seen");}
      catch {setWelcome(true);}
    }
    if(next.available){
      const result=await api.chatgptModels();
      if(!alive.current||version.current!==current)return;
      setModels(result.models);
      setModel(old=>result.models.some(m=>m.id===old)?old:(result.models[0]?.id??""));
    }else{setModels([]);setModel("");}
  }

  useEffect(()=>{
    alive.current=true;
    void load().catch(()=>{if(alive.current)setError("ChatGPT-Einrichtung konnte nicht geladen werden.");});
    return()=>{alive.current=false;version.current++;};
  },[]);

  useEffect(()=>{
    if(!flow)return;
    let cancelled=false,timer:ReturnType<typeof setTimeout>|undefined;
    const poll=async()=>{
      try{
        const result=await api.chatgptSession(flow.session_id);
        if(cancelled||!alive.current)return;
        if(result.status==="ready"){
          setFlow(null);setNotice("Du verwendest dein ChatGPT-Abo. Die Mailverarbeitung ist noch nicht gestartet.");
          await load();return;
        }
        if(["failed","expired"].includes(result.status)){
          setFlow(null);setError("Die Anmeldung wurde nicht abgeschlossen. Bitte erneut versuchen.");return;
        }
      }catch{if(!cancelled&&alive.current)setError("Der Anmeldestatus ist gerade nicht erreichbar. Wir prüfen weiter.");}
      if(!cancelled)timer=setTimeout(poll,2000);
    };
    void poll();
    return()=>{cancelled=true;clearTimeout(timer);};
  },[flow?.session_id]);

  async function begin(){
    setBusy(true);setError("");setNotice("");
    try{
      const next=await api.chatgptBegin(account||undefined);
      if(!alive.current)return;
      setFlow(next);
      // Native Kingfisher opens external destinations in the system browser;
      // the visible link remains available if a browser blocks the new window.
      window.open(next.url,"_blank","noopener,noreferrer");
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:"Anmeldung fehlgeschlagen.");}
    finally{if(alive.current)setBusy(false);}
  }

  async function disconnect(){
    setBusy(true);setError("");version.current++;
    try{
      const result=await api.chatgptDisconnect();
      if(alive.current){setNotice(result.notice);setFlow(null);setConsent(false);await load();}
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:"Trennen fehlgeschlagen.");}
    finally{if(alive.current)setBusy(false);}
  }

  const active=state?.accounts.find(a=>a.id===state.active_account);
  return <section className="source-section chatgpt-access" aria-labelledby="chatgpt-title">
    <header><h2 id="chatgpt-title">ChatGPT für dein Gedächtnis</h2><p>Nutze ein berechtigtes ChatGPT-Abo für die Einordnung deiner Mails. Du brauchst dafür keinen zusätzlichen API-Schlüssel.</p></header>
    <p className="source-hint">Optional: Ohne diese Verbindung arbeitet Kingfisher weiter mit den lokalen Einstellungen. Die Anmeldung gewährt keinen Zugriff auf deine bisherigen ChatGPT-Gespräche.</p>
    {state?.connected ? <div className="chatgpt-connected">
      <strong>{state.plan_usage ? "ChatGPT-Abo verbunden" : "Konto verbunden · Abo-Nutzung nicht freigegeben"}</strong>
      <span>{active?.label??"ChatGPT-Konto"}</span>
      <p>Die Nutzung zählt gegen dein ChatGPT-Kontingent. Bei einem Limit pausiert Kingfisher; es verwendet keine zusätzlich bezahlte API als Ersatz.</p>
      <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">Nutzung in ChatGPT verwalten</a>
      <button type="button" className="secondary-action" disabled={busy} onClick={()=>void disconnect()}>ChatGPT trennen und Verarbeitung widerrufen</button>
    </div>:null}
    <details open={!state?.connected}>
      <summary>{state?.connected ? "Konto wechseln oder erneut anmelden" : "Mit deinem ChatGPT-Konto verbinden"}</summary>
      {state?.accounts.length ? <label>ChatGPT-Konto<select value={account} disabled={busy} onChange={e=>setAccount(e.target.value)}><option value="">Anderes Konto oder neuer Arbeitsbereich</option>{state.accounts.map(a=><option key={a.id} value={a.id}>{a.label} · {a.id.slice(0,6)}</option>)}</select></label>:null}
      <label className="chatgpt-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/><span>Ich möchte OpenAI nutzen. Ausgewählte Inhalte können an OpenAI und außerhalb der EU, auch in den USA, verarbeitet werden. Welche Mails übertragen werden, gebe ich anschließend gesondert frei.</span></label>
      <button type="button" className="primary-action" disabled={busy||!consent||!state?.secure_storage} onClick={()=>void begin()}>Continue with ChatGPT</button>
      {state&&!state.secure_storage ? <p role="alert">Der geschützte Zugangsspeicher fehlt. Bitte die Kingfisher-Einrichtung prüfen.</p>:null}
    </details>
    {flow ? <p role="status">Anmeldung läuft im Browser. Kingfisher aktualisiert sich automatisch. <a href={flow.url} target="_blank" rel="noopener noreferrer">Anmeldung im Browser öffnen</a></p>:null}
    {notice ? <p role="status">{notice}</p>:null}
    {welcome&&state?.available ? <dialog ref={welcomeDialog} aria-labelledby="chatgpt-welcome" className="cloud-memory-preview chatgpt-welcome" onCancel={dismissWelcome}>
      <h3 id="chatgpt-welcome">Du verwendest dein ChatGPT-Abo</h3>
      <p>Freigegebene Auswertungen nutzen dein ChatGPT-Kontingent. Du kannst die Nutzung in den ChatGPT-Einstellungen verwalten. Deine Mails werden erst nach gesonderter Freigabe verarbeitet.</p>
      <button type="button" className="primary-action" onClick={dismissWelcome}>Verstanden</button>
    </dialog>:null}
    {error ? <p role="alert">{error} <button type="button" className="secondary-action" disabled={busy} onClick={()=>void load().catch(()=>setError("Bitte erneut versuchen."))}>Erneut prüfen</button></p>:null}
    {state?.available ? <label>Modell für die Einordnung<select value={model} disabled={busy} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>:null}
    <CloudMemory model={model} connected={Boolean(state?.available)}/>
  </section>;
}
