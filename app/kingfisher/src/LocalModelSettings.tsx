import { useEffect, useState, type FormEvent } from "react";

import { api, type LokaleKi, type MemoryAutomation } from "./api";
import { fuerSystem } from "./system";
import { useSystem } from "./useSystem";
import { navigate } from "./ui";

const LOCAL_ENDPOINT = "http://host.docker.internal:11434/v1";

export function LocalModelSettings() {
  const system = useSystem();
  const [expanded, setExpanded] = useState(true);
  const [configured, setConfigured] = useState("");
  const [model, setModel] = useState("");
  const [manual, setManual] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [cloudModels, setCloudModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [connected, setConnected] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // Was die eine Statusquelle sagt (lokale_ki.py); Kopfzeile und Hinweise lesen nur sie (Befund 9).
  const [lage, setLage] = useState<LokaleKi | null>(null);
  // Einordnung ist eine eigene Zustimmung. Sie wird dort angeboten, wo der
  // Nutzer gerade das Modell verbunden hat, statt dass er sie suchen muss.
  const [offer, setOffer] = useState<MemoryAutomation | null>(null);
  const [offerBusy, setOfferBusy] = useState(false);
  const [offerNote, setOfferNote] = useState<{ok: boolean; text: string} | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(false);
    Promise.all([api.modelSetup(), api.localModels().catch(() => ({ modelle: [] as string[] })),
      api.modelRoles().then(roles => roles.ollama_cloud?.modelle ?? []).catch(() => [] as string[])]).then(([setup, result, cloud]) => {
      if (!active) return;
      // Modelle, die Ollama an seinen Server weiterreicht, sind keine lokale KI und werden hier nicht angeboten.
      const installed = result.modelle.filter(name => !cloud.includes(name));
      setCloudModels(cloud.filter(name => result.modelle.includes(name)));
      const saved = setup.settings.provider === "ollama" ? setup.settings.model : "";
      // Das auf diesem Prototyp geprüfte Modell nur anbieten, wenn es wirklich
      // installiert ist. Keine Downloads und kein ungefragter Modellwechsel.
      const suggested = installed.includes("qwen3.5:4b") ? "qwen3.5:4b" : installed.length === 1 ? installed[0] : "";
      setConfigured(setup.status.model || "");
      setLage(setup.status.lokale_ki ?? null);
      if (attempt === 0) setExpanded(!setup.status.model);
      setModels(installed);
      setModel(saved || suggested);
      setManual(Boolean(saved && !installed.includes(saved)) || installed.length === 0);
      setMessage(setup.status.lokale_ki && setup.status.lokale_ki.zustand !== "keins" ? setup.status.lokale_ki.satz : suggested ? "Installiertes Modell gefunden. Ein Klick verbindet es mit Kingfisher." : "Bitte ein installiertes Modell auswählen.");
    }).catch(() => { if (active) setLoadError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attempt]);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selected = model.trim();
    if (busy || !selected) return;
    setBusy(true);
    setConnected(false);
    setOffer(null);
    setMessage("Modell wird gespeichert und aus Kingfisher heraus geprüft …");
    try {
      const ziel = (lage?.endpunkt ?? LOCAL_ENDPOINT).replace(/\/$/, "");
      const setup = await api.saveLocalModel(selected, ziel);
      // Gespeicherte Auswahl und bestätigte Verbindung sind getrennte Zustände.
      setConfigured(setup.status.model || "");
      if (setup.status.provider !== "ollama" || setup.status.model !== selected || setup.status.endpoint?.replace(/\/$/, "") !== ziel) {
        setMessage("Die Auswahl wurde gespeichert, aber die Startkonfiguration gibt ein anderes Modell oder eine andere Adresse vor. Bitte die Modellvorgaben beim Docker-Start prüfen.");
        return;
      }
      const started = performance.now();
      const result = await api.testModel();
      const elapsed = ((performance.now() - started) / 1000).toFixed(1);
      // HTTP 200 allein ist kein erfolgreicher Modelltest.
      if (result.ok !== true) {
        setMessage("Die Auswahl wurde gespeichert, aber das Modell antwortet nicht. Bitte Ollama starten, das Modell prüfen und erneut verbinden.");
        return;
      }
      setConnected(true);
      setMessage(`${selected} ist verbunden. Verbindungstest: ${elapsed} Sekunden. Das prüft die Erreichbarkeit, nicht die Gedächtnisqualität.`);
      setOfferNote(null);
      api.memoryAutomation().then(state => setOffer(state.state === "paused" && !state.requested ? state : null)).catch(() => setOffer(null));
    } catch {
      setMessage("Die Verbindung konnte nicht bestätigt werden. Bitte Kingfisher und Ollama prüfen und erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function startClassification() {
    if (offerBusy) return;
    setOfferBusy(true);
    try {
      const next = await api.setMemoryAutomation(true);
      if (next.state === "active") {
        setOffer(null);
        setOfferNote({ok: true, text: "Das Sortieren läuft. Den Fortschritt siehst du unter Gedächtnis → Verarbeitung & Verlauf."});
      } else {
        setOfferNote({ok: false, text: "Das Sortieren konnte nicht starten, weil die KI nicht als lokal bestätigt wurde. Bitte erneut verbinden."});
      }
    } catch {
      setOfferNote({ok: false, text: "Das Sortieren konnte nicht gestartet werden. Bitte erneut versuchen."});
    } finally { setOfferBusy(false); }
  }

  return <section className="source-section compact-model" aria-label="Lokale KI">
    <div className="compact-integration-heading"><div><h2>Lokale KI</h2><p>{loading ? "Wird geladen …" : loadError ? "Status gerade nicht erreichbar" : lage ? lage.kurz : configured ? `Eingerichtet: ${configured}` : "Noch kein Modell eingerichtet"}</p></div><button className="secondary-action" type="button" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Schließen" : "Modell verwalten"}</button></div>
    {expanded && <form className="source-form" onSubmit={connect} aria-label="Lokales Modell einrichten">
    <p className="source-hint">{fuerSystem("Ollama auf deinem {Rechner}.", system)} Der Verbindungstest sendet nur eine kurze Bereitschaftsfrage, keine persönlichen Inhalte.</p>
    {loadError ? <p role="alert">Die Modelleinrichtung ist gerade nicht erreichbar. <button type="button" onClick={() => setAttempt(attempt + 1)}>Wiederholen</button></p> : null}
    <label>Installiertes Ollama-Modell<select value={manual ? "__manual__" : model} disabled={loading || busy || loadError} onChange={(event) => {
      const value = event.target.value;
      setManual(value === "__manual__");
      setModel(value === "__manual__" ? "" : value);
      setConnected(false);
      setOffer(null);
      setMessage("Auswahl geändert. Bitte verbinden.");
    }}>
      <option value="">Modell auswählen</option>
      {models.map((name) => <option key={name} value={name}>{name}</option>)}
      <option value="__manual__">Modellnamen selbst eingeben</option>
    </select></label>
    {manual ? <label>Ollama-Modell<input value={model} required disabled={loading || busy || loadError} onChange={(event) => { setModel(event.target.value); setConnected(false); setOffer(null); setMessage("Auswahl geändert. Bitte verbinden."); }} /></label> : null}
    {cloudModels.length ? <p className="source-hint" role="status">Läuft in Ollamas Cloud, nicht auf diesem Rechner: {cloudModels.join(", ")}. Diese Modelle werden hier nicht angeboten; die Anfragen gingen über Ollama an dessen Server in den USA.</p> : null}
    <p className="source-hint">{loading ? "Installierte Modelle werden gesucht …" : models.length ? `${models.length} installierte Modelle gefunden. Es wird nichts heruntergeladen.` : lage?.erreichbar ? "Ollama läuft, hat aber noch kein Modell. Die Vorauswahl oben lädt die passenden mit einem Klick." : "Ollama antwortet gerade nicht. Starte Ollama und suche erneut."}</p>
    <p role="status" aria-live="polite">{loading ? "Modelleinrichtung wird geladen …" : message}</p>
    <div className="source-form-actions">
      <button className="secondary-action" disabled={loading || busy} type="button" onClick={() => { setConnected(false); setAttempt(attempt + 1); }}>Erneut suchen</button>
      {connected ? <button className="secondary-action" onClick={() => navigate("/today")} type="button">Zum Gespräch</button> : null}
      <button className="primary-action" disabled={loading || busy || loadError || !model.trim()} type="submit">{busy ? "Verbindung wird geprüft …" : "Speichern und verbinden"}</button>
    </div>
    {offer && connected && configured === model.trim() && <div className="classification-offer">
      <p>Soll Kingfisher deine Quellen jetzt lokal mit {configured} sortieren? Erst dann beantwortet das Gedächtnis Fragen aus Mails und Dokumenten und schlägt Aufgaben vor. Es wird nichts versendet und nichts automatisch bestätigt; pausieren kannst du jederzeit.{offer.pending === 1 ? " Eine Quelle wartet." : offer.pending > 1 ? ` ${offer.pending} Quellen warten.` : ""}</p>
      <button className="primary-action" disabled={offerBusy} type="button" onClick={() => void startClassification()}>{offerBusy ? "Wird gestartet …" : "Sortieren starten"}</button>
    </div>}
    {offerNote && <p className="classification-offer-note" role={offerNote.ok ? "status" : "alert"}>{offerNote.text}{offerNote.ok ? <>{" "}<button className="secondary-action" type="button" onClick={() => navigate("/memory")}>Fortschritt ansehen</button></> : null}</p>}
  </form>}
    {!expanded && loadError && <p role="alert">Die Modelleinrichtung konnte nicht geladen werden. Öffne „Modell verwalten“, um es erneut zu versuchen.</p>}
  </section>;
}
