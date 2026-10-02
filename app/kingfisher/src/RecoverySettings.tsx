import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type RecoveryStatus } from "./api";
import { sicherungWeg } from "./sicherung";
import { fuerSystem, nurAufDemMac } from "./system";
import { useSystem } from "./useSystem";

// Einstellungen → Sicherung. Mit dem Sicherungshelfer auf dem Mac hält der Helfer Kingfisher kurz an und legt das Archiv
// in den Sicherungsordner. Ohne Helfer (Docker, Browser) schreibt Kingfisher das Archiv selbst, prüft es und gibt es dem
// Browser als Datei (Befund 8); dann gibt es kein Formular, das ins Leere führt. Das Passwort steht einmal da, mit
// „anzeigen“ (Befund 31), und wird nirgends gespeichert.
export function RecoverySettings() {
  const system = useSystem();
  const [state, setState] = useState<RecoveryStatus | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [password, setPassword] = useState("");
  const [zeigen, setZeigen] = useState(false);
  const [sending, setSending] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [message, setMessage] = useState("");
  const [fertig, setFertig] = useState("");
  const version = useRef(0);
  const pending = state?.job?.status === "queued" || state?.job?.status === "running";
  const weg = sicherungWeg(state);
  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    async function poll() {
      const requestVersion = version.current;
      try {
        const next = await api.recoveryStatus();
        if (active && requestVersion === version.current) { setState(next); setUnreachable(false); }
      } catch { if (active) setUnreachable(true); }
      if (active) timer = window.setTimeout(poll, expanded || pending ? 2000 : 15000);
    }
    void poll();
    return () => { active = false; window.clearTimeout(timer); };
  }, [expanded, pending]);

  async function start(event: FormEvent) {
    event.preventDefault();
    if (sending || pending || password.length < 16) return;
    setSending(true); setMessage(""); setFertig(""); version.current += 1;
    try {
      if (weg === "helfer") {
        const job = await api.startRecovery(password);
        setState({online: true, job});
      } else {
        const {datei, name} = await api.recoveryHerunterladen(password);
        const adresse = URL.createObjectURL(datei);
        const link = document.createElement("a");
        link.href = adresse; link.download = name; document.body.appendChild(link); link.click(); link.remove();
        window.setTimeout(() => URL.revokeObjectURL(adresse), 60_000);
        setFertig(`Gesichert und geprüft. Dein Browser speichert die Datei „${name}“, meist im Ordner „Downloads“. Bewahre sie und das Passwort getrennt auf.`);
      }
    } catch (problem) {
      setMessage(problem instanceof ApiError && problem.detail ? problem.detail : "Die Sicherung konnte nicht erstellt werden. Bitte versuche es noch einmal.");
    }
    finally { setPassword(""); setZeigen(false); setSending(false); }
  }

  const kopf = sending || pending ? "Sicherung läuft …" : state?.job?.status === "completed" ? "Letzte Sicherung erstellt und geprüft."
    : state?.job?.status === "failed" ? "Letzte Sicherung nicht abgeschlossen." : "Alles, was Kingfisher über dich weiß, verschlüsselt sichern.";
  return <section className="source-section compact-model" aria-label="Vollständige Sicherung">
    <div className="compact-integration-heading"><div><h2>Vollständige Sicherung</h2><p>{kopf}</p></div><button className="secondary-action" type="button" aria-expanded={expanded} onClick={() => { setExpanded(value => !value); if (expanded) { setPassword(""); setZeigen(false); } }}>{expanded ? "Schließen" : "Sicherung öffnen"}</button></div>
    {expanded && <div>
      {weg === "helfer"
        ? <p className="source-hint">{fuerSystem("Sichert Gespräche, Gedächtnis, Aufgaben, Quellen, Einstellungen und Schlüssel verschlüsselt auf diesem {Rechner}.", system)} Kingfisher wird dafür kurz angehalten und wieder gestartet.</p>
        : <p className="source-hint">{fuerSystem("Sichert Gespräche, Gedächtnis, Aufgaben, Quellen, Einstellungen und Schlüssel verschlüsselt in eine Datei, die dein Browser speichert. Kingfisher prüft sie vorher; auf dem {Rechner} bleibt keine Kopie zurück.", system)}</p>}
      {/* Auf dem Mac schweigt der Helfer gerade: sagen, wie er wiederkommt. Der Download geht trotzdem. Ohne Mac gibt es
          keinen Helfer zu vermissen, also auch keinen Satz dazu. */}
      {weg === "download" && state && system.art === "mac" ? <p className="source-hint">{nurAufDemMac(system, "Die Sicherung")} Bis dahin lädst du sie hier herunter.</p> : null}
      <p className="source-hint">Bewahre das Sicherungspasswort getrennt auf. Ohne dieses Passwort lässt sich die Sicherung nicht wiederherstellen. Es wird nicht gespeichert.</p>
      {!state && !unreachable && <p role="status">Sicherungsstatus wird geladen …</p>}
      {unreachable && <p role="status">{pending ? "Kingfisher ist während der Sicherung kurz nicht erreichbar. Der Status wird automatisch erneut geprüft." : "Sicherungsstatus gerade nicht erreichbar. Wird erneut geprüft."}</p>}
      {!sending && weg === "helfer" && state?.job && <div role="status"><p>{state.job.message}</p>{state.job.status === "completed" && state.job.path && <p className="source-hint" style={{overflowWrap:"anywhere"}}>Gespeichert unter: {state.job.path}</p>}</div>}
      {state ? <form className="source-form" aria-label="Sicherung erstellen" onSubmit={start}>
        {/* Ein Feld mit „anzeigen“ statt doppelter Eingabe (Befund 31): Wer das Passwort sieht, vertippt sich nicht. */}
        <label className="sicherung-passwort">Sicherungspasswort
          <span><input id="sicherung-passwort" type={zeigen ? "text" : "password"} autoComplete="new-password" spellCheck={false} required minLength={16} maxLength={256} value={password} onChange={e => setPassword(e.target.value)} disabled={sending || pending} aria-describedby="sicherung-passwort-hinweis" />
          <button className="secondary-action" type="button" aria-pressed={zeigen} onClick={() => setZeigen(value => !value)}>{zeigen ? "verbergen" : "anzeigen"}</button></span></label>
        <p className="source-hint" id="sicherung-passwort-hinweis">{password.length >= 16 ? "Lang genug. Schreib es dir auf, bevor du sicherst." : `Mindestens 16 Zeichen${password.length ? `, noch ${16 - password.length}` : ""}.`}</p>
        <button className="primary-action" type="submit" disabled={unreachable || sending || pending || password.length < 16}>{sending || pending ? "Sicherung läuft …" : weg === "helfer" ? "Verschlüsselt sichern" : "Sicherung herunterladen"}</button>
      </form> : null}
      {fertig && <p role="status" className="erststart-ok">{fertig}</p>}
      {message && <p role="alert">{message}</p>}
    </div>}
  </section>;
}
