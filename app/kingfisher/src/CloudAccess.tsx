import { useEffect, useRef, useState } from "react";
import { api, ApiError, type CloudAccessState, type CloudProviderAccess } from "./api";
import { ANDERES_MODELL, cloudAccessSaveBody, listenWert, vorbelegtesModell } from "./cloudAccessForm";
import { announceCloudAccessChange } from "./cloudAccessEvents";
import "./CloudAccess.css";

const failure = (error: unknown) => error instanceof ApiError && error.detail
  ? error.detail
  : "Die Änderung konnte nicht gespeichert werden. Bitte erneut versuchen.";

/** Stores provider credentials locally. It never connects to a provider or enables a cloud role. */
export function CloudAccess() {
  const [state, setState] = useState<CloudAccessState | null>(null);
  const [loadingError, setLoadingError] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, {apiKey: string; model: string}>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ok: boolean; text: string} | null>(null);
  // „Anderes Modell“ gewählt: Das Namensfeld bleibt offen, auch solange es noch leer ist.
  const [eigenesModell, setEigenesModell] = useState<Record<string, boolean>>({});
  const loadVersion = useRef(0);

  async function load() {
    const version = ++loadVersion.current;
    setLoadingError(false);
    try {
      const next = await api.cloudAccess();
      if (version !== loadVersion.current) return;
      setState(next);
      setDrafts(current => Object.fromEntries(next.providers.map(provider => [provider.id, {
        apiKey: "",
        model: current[provider.id]?.model ?? vorbelegtesModell(provider),
      }])));
    } catch {
      if (version === loadVersion.current) setLoadingError(true);
    }
  }

  useEffect(() => {
    void load();
    return () => { loadVersion.current++; };
  }, []);

  function change(provider: CloudProviderAccess, field: "apiKey" | "model", value: string) {
    setDrafts(current => ({...current, [provider.id]: {...current[provider.id], [field]: value}}));
  }

  async function save(provider: CloudProviderAccess) {
    const draft = drafts[provider.id] ?? {apiKey: "", model: vorbelegtesModell(provider)};
    setBusy(provider.id); setNotice(null);
    try {
      const next = await api.saveCloudAccess(provider.id, cloudAccessSaveBody(draft.apiKey, draft.model));
      loadVersion.current++;
      setState(next);
      setDrafts(current => ({...current, [provider.id]: {
        apiKey: "", model: vorbelegtesModell(next.providers.find(item => item.id === provider.id) ?? {model: draft.model}),
      }}));
      setNotice({ok: true, text: `${provider.label} Zugangsdaten gespeichert. Dadurch wurde keine Cloud-Nutzung eingeschaltet.`});
      announceCloudAccessChange();
    } catch (error) {
      setNotice({ok: false, text: failure(error)});
    } finally { setBusy(null); }
  }

  async function remove(provider: CloudProviderAccess) {
    setBusy(provider.id); setNotice(null);
    try {
      const next = await api.removeCloudAccess(provider.id);
      loadVersion.current++;
      setState(next);
      setDrafts(current => ({...current, [provider.id]: {apiKey: "", model: vorbelegtesModell(next.providers.find(item => item.id === provider.id) ?? provider)}}));
      setNotice({ok: true, text: `${provider.label} Schlüssel wurde von diesem Rechner entfernt. Dieser Zugang wird nicht mehr genutzt.`});
      announceCloudAccessChange();
    } catch (error) {
      setNotice({ok: false, text: failure(error)});
    } finally { setBusy(null); }
  }

  return <section className="source-section cloud-access" aria-labelledby="cloud-access-heading">
    <div className="compact-integration-heading"><div><h2 id="cloud-access-heading">Cloud-Zugänge</h2>
      <p>Anthropic, OpenAI, Mistral und OpenRouter · optional</p></div></div>
    <p className="source-hint">Speichern schaltet Cloud nicht ein und sendet keine Fragen oder Quellen. Dafür brauchst du eine gesonderte Zustimmung zur jeweiligen Rolle oder zum konkreten Importpaket.</p>
    {loadingError ? <p role="alert">Die Cloud-Einstellungen konnten nicht geladen werden. <button type="button" className="secondary-action" onClick={() => void load()}>Erneut versuchen</button></p> : null}
    {state && !state.storage_available ? <p className="model-rec-warn" role="status">Der sichere Schlüsselspeicher ist auf diesem Rechner nicht verfügbar. Schlüssel können hier nicht gespeichert werden.</p> : null}
    {state?.notice ? <p className="source-hint">{state.notice}</p> : null}
    {state?.providers.map(provider => {
      const draft = drafts[provider.id] ?? {apiKey: "", model: vorbelegtesModell(provider)};
      const disabled = busy !== null;
      const wert = eigenesModell?.[provider.id] ? ANDERES_MODELL : listenWert(draft.model, provider.modelle);
      return <details className="cloud-access-entry" key={provider.id}>
        <summary><strong>{provider.label}</strong><span>{draft.apiKey || (provider.key_present && draft.model !== provider.model) ? "Ungespeichert" : provider.key_present ? "Schlüssel hinterlegt" : "Nicht eingerichtet"}</span></summary>
        <fieldset className="cloud-access-provider">
        <legend>{provider.label}</legend>
        {provider.privacy ? <details className="quiet-details"><summary>Datenschutz, Region und Kosten</summary>
          <p>{provider.privacy.region}</p><p>{provider.privacy.training}</p><p>{provider.privacy.retention}</p><p>{provider.privacy.billing}</p>
          <p>Geprüft am {provider.privacy.checked_at}. {provider.privacy.sources.map(source=><span key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.label}</a>{" · "}</span>)}</p>
        </details>:null}
        {/* Paket S, Befund 5: eine Liste mit dem empfohlenen Modell vorbelegt statt eines leeren Feldes für den Namen. */}
        <label>Modell
          <select value={wert} disabled={disabled} onChange={event => {
            const gewaehlt = event.target.value;
            setEigenesModell(current => ({...current, [provider.id]: gewaehlt === ANDERES_MODELL}));
            if (gewaehlt !== ANDERES_MODELL) change(provider, "model", gewaehlt);
          }}>
            {(provider.modelle ?? []).map(modell => <option key={modell.id} value={modell.id}>{modell.titel}</option>)}
            <option value={ANDERES_MODELL}>Anderes Modell (für Techniker) …</option>
          </select>
        </label>
        {wert === ANDERES_MODELL ? <label>Name des Modells beim Anbieter
          <input value={draft.model} disabled={disabled} onChange={event => change(provider, "model", event.target.value)} autoComplete="off" spellCheck={false} />
        </label> : null}
        {/* „API-Schlüssel“ heißt er beim Anbieter; danach sucht der Mensch dort, deshalb steht das Wort in Klammern. */}
        <label>Zugangsschlüssel vom Anbieter <small>(dort „API-Schlüssel“ oder „API key“)</small>{provider.key_present ? <small> Bereits hinterlegt; leer lassen, um ihn zu behalten.</small> : null}
          <input type="password" value={draft.apiKey} disabled={disabled || !state.storage_available}
            onChange={event => change(provider, "apiKey", event.target.value)} autoComplete="new-password"
            placeholder={provider.key_present ? "Neuen Schlüssel eingeben, um ihn zu ersetzen" : "Schlüssel hier eingeben"} />
        </label>
        <details className="quiet-details"><summary>Für Techniker</summary>
          <p>Adresse des Anbieters: <code>{provider.endpoint}</code></p>
          {draft.model ? <p>Modell: <code>{draft.model}</code></p> : null}
        </details>
        <div className="source-form-actions">
          <button className="primary-action" type="button" disabled={disabled || !state.storage_available || (!provider.key_present && !draft.apiKey.trim())} onClick={() => void save(provider)}>Speichern</button>
          {provider.key_present ? <button className="secondary-action" type="button" disabled={disabled || !state.storage_available} onClick={() => void remove(provider)}>Schlüssel entfernen</button> : null}
        </div>
        </fieldset>
      </details>;
    })}
    {busy ? <p role="status">Wird lokal gespeichert …</p> : null}
    {notice ? <p role={notice.ok ? "status" : "alert"}>{notice.text}</p> : null}
  </section>;
}
