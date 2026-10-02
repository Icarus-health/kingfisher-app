import { useEffect, useState } from "react";
import { api, ApiError, type MicrosoftStand } from "./api";

// Hinter „Für Techniker“: die Kennung der App (Client-ID) für „Mit Microsoft anmelden“. Ohne sie sagt die Karte vorne
// nur, dass ein Techniker sie einträgt. Die Anleitung zur Registrierung steht in docs/50-microsoft-365.md.
export function MicrosoftVorbereiten() {
  const [stand, setStand] = useState<MicrosoftStand | null>(null);
  const [kennung, setKennung] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [satz, setSatz] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.microsoftConfig().then(wert => { if (aktiv) setStand(wert); }).catch(() => { if (aktiv) setSatz("Der Stand der Microsoft-Anmeldung ist gerade nicht lesbar."); });
    return () => { aktiv = false; };
  }, []);
  async function speichern(wert: string) {
    setArbeitet(true); setSatz("");
    try {
      setStand(await api.microsoftConfigSetzen(wert));
      setKennung("");
      setSatz(wert ? "Kennung gespeichert. „Mit Microsoft anmelden“ ist jetzt bereit." : "Kennung entfernt.");
    } catch (problem) {
      setSatz(problem instanceof ApiError && problem.detail ? problem.detail : "Die Kennung ließ sich nicht speichern.");
    } finally { setArbeitet(false); }
  }
  const quelle = stand?.quelle === "einstellung" ? "hier eingetragen" : stand?.quelle === "umgebung" ? "aus der Umgebungsvariable KINGFISHER_MS_CLIENT_ID" : "";
  return <section className="source-section" aria-label="Microsoft-Anmeldung vorbereiten">
    <p className="source-hint">{stand ? (stand.configured ? `Bereit: App-Kennung ${stand.client_id} (${quelle}).` : "Noch nicht vorbereitet.") : "Wird geladen …"}</p>
    <p>In Microsoft Entra eine App registrieren (Kontotyp: Konten in einem beliebigen Organisationsverzeichnis), unter „Authentifizierung“ die öffentlichen Clientflows zulassen und als delegierte Microsoft-Graph-Berechtigungen nur User.Read, Mail.Read, Calendars.Read, OnlineMeetings.Read und offline_access eintragen; für Teams-Mitschriften zusätzlich OnlineMeetingTranscript.Read.All, dem die IT der Hochschule zustimmen muss. Kein geheimer Clientschlüssel, keine Umleitungsadresse.</p>
    <label>App-Kennung (Client-ID)<input value={kennung} autoComplete="off" spellCheck={false} placeholder="00000000-0000-0000-0000-000000000000" onChange={event => setKennung(event.target.value)} /></label>
    <div className="ms-knoepfe">
      <button type="button" className="secondary-action" disabled={arbeitet || !stand?.secure_storage || !kennung.trim()} onClick={() => void speichern(kennung.trim())}>Kennung speichern</button>
      {stand?.quelle === "einstellung" ? <button type="button" className="text-action" disabled={arbeitet} onClick={() => void speichern("")}>Kennung entfernen</button> : null}
    </div>
    <p className="source-hint">Die Kennung ist kein Geheimnis. Anmeldungen der Menschen liegen nur im Schlüsselbund dieses Rechners.</p>
    {satz ? <p role="status">{satz}</p> : null}
  </section>;
}
