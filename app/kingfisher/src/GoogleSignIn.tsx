import { useEffect, useRef, useState } from "react";
import { api, type GoogleSession } from "./api";
import { watchGoogleSignIn } from "./googleSignInProgress";

type Flow = {session_id:string; url?:string};
const storageKey = (kind: "mail"|"calendar") => `kingfisher.google-signin.${kind}.v1`;
function rememberFlow(kind: "mail"|"calendar", id?: string) {
  try {
    if (id) sessionStorage.setItem(storageKey(kind), id);
    else sessionStorage.removeItem(storageKey(kind));
  } catch { /* Recovery is optional when browser storage is unavailable. */ }
}
function restoreFlow(kind: "mail"|"calendar"): Flow|null {
  try {
    const id = sessionStorage.getItem(storageKey(kind));
    if (id && /^[A-Za-z0-9_-]{32}$/.test(id)) return {session_id:id};
    rememberFlow(kind);
  } catch { /* Keep sign-in usable without browser storage. */ }
  return null;
}

export function GoogleSignIn({kind, active, onConnected}: {kind: "mail"|"calendar"; active: boolean; onConnected: () => void}) {
  const [config, setConfig] = useState<{configured:boolean; secure_storage:boolean}|null>(null);
  const [flow, setFlow] = useState<Flow|null>(() => restoreFlow(kind));
  const [session, setSession] = useState<GoogleSession|null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const progress = useRef<ReturnType<typeof watchGoogleSignIn>|null>(null);
  const lifecycle = useRef(0);
  const actionBusy = useRef(false);
  const connectedCallback = useRef(onConnected);
  connectedCallback.current = onConnected;
  useEffect(() => {
    setBusy(false);
    if (!active) return;
    let current = true;
    api.googleConfig().then(value => {if(current) setConfig(value);}).catch(() => {
      if(current) {setConfig(null); setMessage("Google-Einrichtung konnte nicht geladen werden.");}
    });
    return () => {current = false; lifecycle.current += 1;};
  }, [active, kind]);
  useEffect(() => {
    if (!active || !flow) return;
    const watcher = watchGoogleSignIn({
      read: () => api.googleSession(flow.session_id),
      onSession: next => {
        if (next.kind && next.kind !== kind) {
          progress.current?.stop(); rememberFlow(kind); setSession({status:"failed"});
          return;
        }
        setSession(next); setMessage("");
        if (!["waiting", "processing", "ready"].includes(next.status)) rememberFlow(kind);
        if (next.status === "connected") connectedCallback.current();
      },
      onError: () => setMessage("Status konnte gerade nicht geladen werden. Wir versuchen es automatisch erneut; du kannst auch „Jetzt prüfen“ wählen."),
      onTimeout: () => {rememberFlow(kind); setSession({status:"expired"}); setMessage("");},
    });
    progress.current = watcher;
    const refresh = () => { void watcher.refresh(); };
    const visible = () => {if (document.visibilityState === "visible") refresh();};
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {
      watcher.stop();
      if (progress.current === watcher) progress.current = null;
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [active, flow?.session_id, kind]);
  async function run(action: (current: () => boolean) => Promise<void>) {
    if(actionBusy.current) return;
    actionBusy.current = true;
    const version = lifecycle.current;
    const current = () => lifecycle.current === version;
    setBusy(true); setMessage("");
    try { await action(current); }
    catch(error) {if (current()) setMessage(error instanceof Error ? error.message : "Bitte erneut versuchen.");}
    finally {actionBusy.current = false; if (current()) setBusy(false);}
  }
  const pending = flow && (!session || session.status === "waiting" || session.status === "processing");
  const terminal = session && ["expired", "failed", "connected"].includes(session.status);
  return <section className="source-section" aria-label={kind === "mail" ? "Google Mail verbinden" : "Google Kalender verbinden"}>
    <h2>{kind === "mail" ? "Gmail" : "Google-Kalender"}</h2>
    <p className="source-hint">{kind === "mail" ? "Die Anmeldung erfolgt bei Google im Browser. Dafür verlangt Google vollen Zugriff auf dein Postfach. Kingfisher versendet weiterhin nur nach deiner ausdrücklichen Freigabe. Automatischen Abruf richtest du anschließend separat ein." : "Melde dich bei Google im Browser an und wähle anschließend die Kalender aus. Kingfisher fordert ausschließlich Lesezugriff an."}</p>
    {config && !config.configured && <p>Noch nicht freigeschaltet: Google verlangt eine einmalige Vorbereitung, die ein Techniker unter <a href="/settings#technik-google">Für Techniker</a> erledigt. Bis dahin kannst du dein Postfach oder deinen Kalender auch anders verbinden.</p>}
    {config && !config.secure_storage && <p role="alert">Auf diesem Rechner fehlt der geschützte Speicher für Zugänge. Die Google-Anmeldung ist deshalb gesperrt.</p>}
    <button type="button" className="secondary-action" disabled={busy || !config?.configured || !config.secure_storage} onClick={() => run(async current => {
      progress.current?.stop(); setFlow(null); setSession(null); setSelected([]); rememberFlow(kind);
      const next = await api.googleBegin(kind);
      if (!current()) return;
      rememberFlow(kind, next.session_id); setFlow(next);
    })}>{flow && session?.status !== "connected" ? "Anmeldung neu starten" : "Mit Google anmelden"}</button>
    {flow && <div>
      {pending && <div>
        <p><strong>1. Bei Google anmelden</strong></p>
        {flow.url ? <p><a href={flow.url} target="_blank" rel="noopener noreferrer">Anmeldung im Browser öffnen</a></p> : <p>Eine laufende Anmeldung wurde wiedergefunden. Schließe sie im bereits geöffneten Browser ab. Falls der Browser nicht mehr offen ist, wähle „Anmeldung neu starten“.</p>}
        <p role="status">{session?.status === "processing" ? "Anmeldung erhalten. Google-Konto wird geprüft …" : "Wir warten auf deine Anmeldung bei Google. Der Status aktualisiert sich automatisch. Kehre danach zu Kingfisher zurück."}</p>
        <button type="button" className="secondary-action" disabled={busy} onClick={() => {void progress.current?.refresh();}}>Jetzt prüfen</button>
      </div>}
      {session?.status === "ready" && <div>
        <p role="status"><strong>2. Anmeldung erfolgreich — jetzt Verbindung bestätigen</strong></p>
        <p>Google-Konto: <strong>{session.email}</strong></p>
        {kind === "calendar" && <p>Wähle die Kalender aus, die Kingfisher lesen darf, und bestätige unten.</p>}
        {kind === "calendar" && (session.calendars?.length ? session.calendars.map(item => <label key={item.id} className="mail-sync-check"><input type="checkbox" checked={selected.includes(item.id)} onChange={event => setSelected(values => event.target.checked ? [...values, item.id] : values.filter(value => value !== item.id))} />{item.name}</label>) : <p>Keine lesbaren Kalender gefunden.</p>)}
        <button type="button" className="secondary-action" disabled={busy || (kind === "calendar" && !selected.length)} onClick={() => run(async current => {
          await api.googleConnect(flow.session_id, selected);
          rememberFlow(kind);
          if (!current()) return;
          setFlow(null); setSession(null);
          setMessage(kind === "mail" ? "Gmail verbunden. Automatischen Mailabruf kannst du anschließend separat einschalten." : "Ausgewählte Google-Kalender verbunden. Du kannst ihre Termine jetzt abrufen.");
          onConnected();
        })}>{kind === "mail" ? "Dieses Konto verbinden" : "Ausgewählte Kalender verbinden"}</button>
      </div>}
      {terminal && <p role={session.status === "connected" ? "status" : "alert"}>{session.status === "connected" ? "Diese Verbindung wurde bereits gespeichert." : session.status === "failed" ? "Google-Anmeldung wurde nicht abgeschlossen. Starte sie erneut und bestätige die benötigten Berechtigungen bei Google." : "Diese Anmeldung ist abgelaufen. Wähle „Anmeldung neu starten“."}</p>}
    </div>}
    <p className="source-hint">Trennen beendet die Nutzung durch Kingfisher; die Freigabe kannst du zusätzlich in deinem Google-Konto widerrufen.</p>
    {message && <p role="status">{message}</p>}
  </section>;
}
