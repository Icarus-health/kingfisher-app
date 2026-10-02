import { useEffect, useState } from "react";
import { api } from "./api";

type RoutingProfile = { model: string; verified: boolean; latency_ms: number; checked_at: string };
type RoutingState = { enabled: boolean; ready?: boolean; profiles: RoutingProfile[] };

export function RoutingControls() {
  const [state, setState] = useState<RoutingState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.routingStatus().then(next => { if (active) setState(next); })
      .catch(() => { if (active) setError("Modellauswahl konnte nicht geladen werden."); });
    return () => { active = false; };
  }, []);

  async function run(action: () => Promise<RoutingState>) {
    setBusy(true); setError("");
    try { setState(await action()); }
    catch { setError("Die Modellauswahl konnte nicht aktualisiert werden. Bitte erneut versuchen."); }
    finally { setBusy(false); }
  }

  const verified = state?.profiles.filter(profile => profile.verified) ?? [];
  return <section className="source-section" aria-label="Lokale Modellauswahl">
    <details>
      <summary>Lokale Modellauswahl</summary>
      <p className="source-hint">Kingfisher prüft nur die Bereitschaft und Werkzeugfähigkeit der ausdrücklich eingerichteten Modelle. Dabei werden keine persönlichen Inhalte gesendet; die Prüfung kann einige Minuten dauern. Das Ergebnis ist keine allgemeine Qualitätsbewertung.</p>
      {!state ? <p role="status">Status wird geladen …</p> : <>
        <p role="status">{state.enabled && state.ready !== false ? "Automatische Auswahl ist aktiv." : state.enabled ? "Automatische Auswahl ist eingerichtet, benötigt aber eine erneute Modellprüfung." : "Ein fest eingerichtetes Modell wird verwendet."}</p>
        {state.profiles.length === 0 ? <p>Keine Modelle eingerichtet.</p> : <ul>
          {state.profiles.map(profile => <li key={profile.model}>
            <strong>{profile.model}</strong>{" "}{profile.verified ? "· geprüft" : "· nicht geprüft"}
          </li>)}
        </ul>}
        <div className="source-form-actions">
          <button className="secondary-action" type="button" disabled={busy} onClick={() => void run(api.verifyRouting)}>{busy ? "Modelle werden geprüft …" : "Modelle prüfen"}</button>
          {state.enabled
            ? <button className="secondary-action" type="button" disabled={busy} onClick={() => void run(() => api.setRouting(false))}>Automatische Auswahl deaktivieren</button>
            : <button className="primary-action" type="button" disabled={busy || verified.length === 0} onClick={() => void run(() => api.setRouting(true))}>Automatisch auswählen</button>}
        </div>
      </>}
      {error ? <p role="alert" className="settings-error">{error}</p> : null}
    </details>
  </section>;
}
