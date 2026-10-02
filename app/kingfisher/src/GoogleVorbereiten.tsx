import { useEffect, useState } from "react";
import { api } from "./api";

// Hinter „Für Techniker“: die einmalige Vorbereitung der Google-Anmeldung (Desktop-Client aus dem eigenen Cloud-Projekt).
// Bis sie getan ist, sagt die Karte „Gmail“ vorne nur, dass ein Techniker sie erledigt. Die Anmeldung selbst steht in
// GoogleSignIn.tsx.
export function GoogleVorbereiten() {
  const [config, setConfig] = useState<{ configured: boolean; secure_storage: boolean } | null>(null);
  const [client, setClient] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.googleConfig().then(value => { if (aktiv) setConfig(value); }).catch(() => { if (aktiv) setMessage("Google-Einrichtung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);
  async function speichern() {
    setBusy(true); setMessage("");
    try {
      setConfig(await api.saveGoogleConfig(JSON.parse(client)));
      setClient(""); setMessage("Google-Konfiguration lokal gespeichert.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Bitte erneut versuchen."); }
    finally { setBusy(false); }
  }
  return <section className="source-section" aria-label="Google-Anmeldung vorbereiten">
    <p className="source-hint">{config ? (config.configured ? "Die Vorbereitung ist erledigt." : "Noch nicht vorbereitet.") : "Wird geladen …"}</p>
    <p>Im eigenen Google-Cloud-Projekt einen OAuth-Client vom Typ Desktop-App anlegen, die gewünschten Google-Dienste freischalten und im Testbetrieb deine Konten als Testnutzer eintragen. Google kann eine spätere Verifizierung verlangen. Konfiguration nur hier lokal eingeben, nicht im Chat.</p>
    <p><a href="https://developers.google.com/identity/protocols/oauth2/native-app" target="_blank" rel="noopener noreferrer">Offizielle Google-Anleitung</a></p>
    <label>Desktop-Client-JSON<textarea rows={4} value={client} autoComplete="off" spellCheck={false} onChange={event => setClient(event.target.value)} /></label>
    <button type="button" className="secondary-action" disabled={busy || !config?.secure_storage || !client.trim()} onClick={() => void speichern()}>Konfiguration lokal speichern</button>
    <p className="source-hint">Zugänge werden im geschützten lokalen Schlüsselspeicher abgelegt.</p>
    {message && <p role="status">{message}</p>}
  </section>;
}
