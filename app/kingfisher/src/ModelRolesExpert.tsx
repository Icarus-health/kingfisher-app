import {useEffect, useState} from "react";
import {api, ApiError, type ModelRecommendationRow, type ModelRoles, type ModelRoleState} from "./api";
import {cloudReady} from "./modelSetup";

const failure = (error: unknown) => error instanceof ApiError && error.detail ? error.detail
  : "Das konnte gerade nicht gespeichert werden. Bitte erneut versuchen.";

const since = (iso: string) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : ` seit ${date.toLocaleDateString("de-DE")}`;
};

// „Passend“ heißt: passt einzeln und ist nicht das größere Modell, das die Vorauswahl eben ersetzt hat, weil alles zusammen nicht passte.
const suitable = (row: ModelRecommendationRow | undefined) => row
  ? row.alternativen.filter(item => item.passt && !(row.orchester_hinweis && item.speicher_gb > row.empfohlen.speicher_gb)).map(item => item.name) : [];

/** Expertenebene: Modell je Aufgabe wählen, Cloud je Aufgabe mit ausdrücklicher Einwilligung zuschalten. */
export function ModelRolesExpert({installed, rows, onChanged}: {installed: string[]; rows: ModelRecommendationRow[]; onChanged: () => void}) {
  const [roles, setRoles] = useState<ModelRoles | null>(null);
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState<{ok: boolean; text: string} | null>(null);

  useEffect(() => {
    let active = true;
    api.modelRoles().then(next => { if (active) setRoles(next); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);

  async function save(rolle: string, body: Parameters<typeof api.saveModelRole>[1], success: string) {
    setMessage(null);
    try { setRoles(await api.saveModelRole(rolle, body)); setMessage({ok: true, text: success}); onChanged(); }
    catch (error) { setMessage({ok: false, text: failure(error)}); }
  }

  if (failed) return <p role="alert">Die Aufgabenwahl ist gerade nicht erreichbar.</p>;
  if (!roles) return <p className="source-hint" role="status">Wird geladen …</p>;
  return <div className="model-roles">
    <p className="source-hint">Ohne eigene Wahl nutzt jede Aufgabe das Modell, das du oben unter „Lokales Modell“ eingerichtet hast. Cloud-Modelle senden Inhalte an einen Anbieter im Internet und sind nur mit deiner Einwilligung für genau diese Aufgabe möglich.</p>
    {roles.rollen.map(role => <RoleCard key={role.rolle} role={role} roles={roles} installed={installed}
      alternatives={suitable(rows.find(row => row.rolle === role.rolle))} save={save} />)}
    {message ? <p role={message.ok ? "status" : "alert"} className="model-rec-note">{message.text}</p> : null}
  </div>;
}

function RoleCard({role, roles, installed, alternatives, save}: {
  role: ModelRoleState; roles: ModelRoles; installed: string[]; alternatives: string[];
  save: (rolle: string, body: Parameters<typeof api.saveModelRole>[1], success: string) => Promise<void>;
}) {
  const [asking, setAsking] = useState(false);
  const [provider, setProvider] = useState(role.wahl.anbieter || "");
  const [consent, setConsent] = useState(false);
  const chosen = role.wahl.modell;
  const options = [...new Set([...installed, ...(chosen && !installed.includes(chosen) ? [chosen] : [])])];
  const inCloud = role.wirksam.quelle === "cloud";
  const [cloudModel, setCloudModel] = useState("");
  const ollamaCloud = roles.ollama_cloud?.modelle ?? [];
  const viaOllama = provider === "ollama-cloud";
  const anbieter = roles.anbieter.find(item => item.id === provider);
  const others = alternatives.filter(name => !options.includes(name));
  return <fieldset className="model-role-card">
    <legend>{role.titel}</legend>
    <p className="source-hint">{role.beschreibung}{role.wirksam.modell ? ` Gerade genutzt: ${role.wirksam.modell} (${role.wirksam.lokal ? "auf diesem Rechner" : role.wirksam.cloud_ueber_ollama ? "läuft in Ollamas Cloud" : "Cloud"}).` : " Gerade ist kein Modell eingerichtet."}</p>
    {role.blockiert ? <p className="model-rec-warn" role="status">{role.blockiert}</p> : null}
    {!inCloud ? <label>Modell
      <select value={chosen} onChange={event => void save(role.rolle, {modell: event.target.value}, event.target.value ? "Gespeichert." : "Diese Aufgabe nutzt wieder das Standardmodell.")}>
        <option value="">Wie Standard</option>
        {options.map(name => <option key={name} value={name}>{name}</option>)}
      </select></label> : null}
    {!inCloud && others.length ? <p className="source-hint">Nicht installiert, aber für diesen Rechner passend: {others.join(", ")}. Über „Einrichten“ oben laden.</p> : null}
    {role.cloud_moeglich ? (inCloud ? <div>
      <p>Cloud ist zugeschaltet{since(role.wahl.cloud_einwilligung)}: {role.wirksam.modell}.</p>
      <button className="secondary-action" type="button" onClick={() => void save(role.rolle, {cloud: false}, "Diese Aufgabe läuft wieder auf diesem Rechner.")}>Wieder auf diesem Rechner</button>
    </div> : asking ? <div className="model-rec-confirm" role="group" aria-label={`Cloud für ${role.titel}`}>
      <label>Anbieter
        <select value={provider} onChange={event => setProvider(event.target.value)}>
          <option value="">Bitte wählen</option>
          {roles.anbieter.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          {ollamaCloud.length ? <option value="ollama-cloud">Ollama Cloud (Modell auf deinem Ollama, läuft in den USA)</option> : null}
        </select></label>
      {viaOllama ? <label>Cloud-Modell
        <select value={cloudModel} onChange={event => setCloudModel(event.target.value)}>
          <option value="">Bitte wählen</option>
          {ollamaCloud.map(name => <option key={name} value={name}>{name}</option>)}
        </select></label> : null}
      {viaOllama && roles.ollama_cloud ? <p className="model-rec-warn">{roles.ollama_cloud.hinweis}</p> : null}
      {anbieter && !anbieter.schluessel_da ? <p className="model-rec-warn">Für {anbieter.label} ist auf diesem Rechner noch kein Zugangsschlüssel hinterlegt.</p> : null}
      <label className="model-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
        <span>{role.cloud_satz} Ich willige ein.</span></label>
      <button className="primary-action" type="button" disabled={!cloudReady(provider, Boolean(anbieter?.schluessel_da) || (viaOllama && Boolean(cloudModel)), consent)}
        onClick={() => void save(role.rolle, viaOllama ? {modell: cloudModel, cloud: true, anbieter: provider, einwilligung: true} : {cloud: true, anbieter: provider, einwilligung: true}, "Cloud ist für diese Aufgabe zugeschaltet.").then(() => { setAsking(false); setConsent(false); })}>Cloud zuschalten</button>
      <button className="secondary-action" type="button" onClick={() => { setAsking(false); setConsent(false); }}>Abbrechen</button>
    </div> : <button className="secondary-action" type="button" onClick={() => setAsking(true)}>Cloud statt dieses Rechners nutzen …</button>)
      : <p className="source-hint">{role.cloud_satz}</p>}
  </fieldset>;
}
