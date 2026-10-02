import { useEffect, useState } from "react";
import { ausstattungQuelle, ausstattungSatz, ausstattungUnbekannt } from "./system";
import { useSystem } from "./useSystem";
import { api, type DeviceProfile } from "./api";

/** Read-only device capacity and installed models; never changes model selection. */
export function DeviceModelHelp() {
  const system = useSystem();
  const [profile, setProfile] = useState<DeviceProfile | null>(null);
  const [models, setModels] = useState<string[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    // Independent failures: an offline Ollama should not hide the hardware report.
    void api.deviceProfile().then(value => {
      if (active) setProfile(value);
    }).catch(() => {
      if (active) { setProfile(null); setFailed(true); }
    }).finally(() => {
      if (active) setLoading(false);
    });
    void api.localModels().then(value => {
      if (active) setModels(value.modelle);
    }).catch(() => {
      if (active) setModels(null);
    });
    return () => { active = false; };
  }, [reload]);

  const smallModelInstalled = models?.includes("qwen3.5:4b") ?? false;
  // Dieselbe Aussage wie bei der Modellwahl darüber (Fremdprobe 2, Befund 27).
  const satz = profile ? ausstattungSatz({ chip: profile.chip, gb: profile.memory_gb, quelle: ausstattungQuelle(profile.source) }) : null;
  return <section className="source-card" aria-label="Gerät und lokale Modelle">
    <h3>Gerät und lokale Modelle</h3>
    {loading ? <p className="source-hint" role="status">Geräteangaben werden geladen …</p> : null}
    {failed ? <p className="source-hint" role="status">Die Geräteangaben sind gerade nicht erreichbar.</p> : null}
    {profile ? <>
      {satz ? <p><strong>{satz}</strong></p> : <p>{ausstattungUnbekannt(system)}</p>}
      <p className="source-hint">{profile.guidance.note}</p>
      {profile.guidance.model_budget_gb !== null ? <p className="source-hint">
        Schätzung: rund {profile.guidance.headroom_gb?.toLocaleString("de-DE")} GB für das Betriebssystem und andere Apps freihalten.
        {" "}Verbleibender Planungsrahmen für das Modell: rund {profile.guidance.model_budget_gb.toLocaleString("de-DE")} GB.
        {" "}Das ist keine Messung des aktuell freien Speichers.
      </p> : null}
    </> : null}
    {models === null ? <p className="source-hint">Installierte lokale Modelle konnten noch nicht geprüft werden. Prüfe, ob Ollama läuft.</p>
      : models.length === 0 ? <p className="source-hint">Ollama läuft, hat aber noch kein Modell. Die Vorauswahl oben lädt die passenden mit einem Klick.</p>
      : smallModelInstalled ? <p className="source-hint">
        qwen3.5:4b ist installiert und ein kleiner Einstieg für die vorhandene Einrichtung.
        {profile?.memory_gb !== null && profile?.memory_gb !== undefined && profile.memory_gb < 16
          ? " Bei wenig RAM andere große Apps schließen und mit kurzem Kontext beginnen."
          : " Prüfe die Antworten mit deinen eigenen Aufgaben."}
        {" "}Mehr RAM allein bedeutet keine besseren Antworten.
      </p> : <p className="source-hint">Nutze zunächst eines deiner installierten Modelle und prüfe die Antworten mit deinen eigenen Aufgaben.</p>}
    {models && models.length > 0 ? <details>
      <summary>Installierte Modelle ({models.length})</summary>
      <ul>{models.map(model => <li key={model}>{model}</li>)}</ul>
    </details> : null}
    <button type="button" className="secondary-action" disabled={loading}
      onClick={() => setReload(value => value + 1)}>Angaben erneut prüfen</button>
  </section>;
}
