import {MemoryEntityLink} from "./MemoryEntityLink";
import { useState } from "react";
import { ClaimEvidence } from "./ClaimEvidence";
import { ClaimCorrection } from "./ClaimCorrection";
import { api, type RegistryProfile } from "./api";
import { Rueckfrage } from "./grundlage";

type Claim = Record<string, unknown>;
function date(value: unknown) {
  if (typeof value !== "string") return "offen";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "nicht lesbar" : parsed.toLocaleString("de-DE");
}
function Details({claim, entities}: {claim: Claim; entities: RegistryProfile["related_entities"]}) {
  return <details><summary>Zeitraum, Kontext und Belege</summary>
    <p>Gültig ab: {date(claim.valid_from)} · Gültig bis (ausschließlich): {date(claim.valid_until)}</p>
    {[["subject_ref", "Betrifft"], ["target_ref", "Verbindung zu"], ["scope_ref", "Kontext"]].map(([key, label]) => {
      const ref = claim[key];
      const entity = typeof ref === "string" ? entities[ref] : undefined;
      return entity ? <p key={key}>{label}: <MemoryEntityLink kind={entity.workspace_project_id ? "project" : "person"} href={entity.workspace_project_id ? `/memory/projects/${encodeURIComponent(entity.workspace_project_id)}` : `/memory/registry/${encodeURIComponent(entity.id)}`}>{entity.label}</MemoryEntityLink></p> : key === "scope_ref" ? <p key={key}>Kontext: {typeof ref === "string" ? ref : "Kein gesonderter Kontext angegeben"}</p> : null;
    })}
    <ClaimEvidence claim={claim} />
  </details>;
}
export function ClaimControls({claims, history, entities, onChanged}: {claims: Claim[]; history: Claim[]; entities: RegistryProfile["related_entities"]; onChanged: () => void}) {
  const [correcting, setCorrecting] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  async function retract() {
    if (!selected || !reason.trim() || busy) return;
    setBusy(true); setError(false);
    try { await api.retractClaim(selected, reason.trim()); onChanged(); }
    catch { setError(true); setBusy(false); }
  }
  function row(claim: Claim, current: boolean) {
    const id = String(claim.id);
    const status = ({active: "Bestätigt, derzeit nicht als aktuelles Wissen nutzbar", retracted: "Widerrufen", superseded: "Ersetzt", disputed: "Grundlage fraglich"} as Record<string, string>)[String(claim.status)] || "Nicht aktuell nutzbar";
    return <article key={id}><strong>{String(claim.statement ?? "")}</strong><small>{current ? "Aktuell bestätigter Stand" : status}</small><Details claim={claim} entities={entities} />
      {claim.status === "active" && correcting !== id && <button className="secondary-action" disabled={busy} onClick={() => {setSelected(null);setCorrecting(id);}} type="button">Aussage korrigieren</button>}
      {correcting === id && <ClaimCorrection key={id} claim={claim} onChanged={onChanged} onCancel={() => setCorrecting(null)} />}
      {claim.status === "active" && correcting !== id && <button className="secondary-action" disabled={busy && selected !== id} onClick={() => {setCorrecting(null);setSelected(id);setReason("");setError(false);}} type="button">Aussage widerrufen</button>}
      {/* Die Rückfrage als Dialog (Paket B, B3); erst ist der Grund einzutragen, der allein nichts auslöst. */}
      {selected === id && <Rueckfrage frage="Aussage widerrufen?" satz="Diese Aussage wird nicht weiter als gültiges Wissen verwendet. Ihr Verlauf bleibt erhalten; abhängige Aussagen werden neu bewertet."
        bestaetigen="Widerruf bestätigen" start="feld" gesperrt={!reason.trim()} arbeitet={busy}
        fehler={error ? "Der Widerruf konnte nicht gespeichert werden. Bitte erneut versuchen." : null}
        onBestaetigen={() => void retract()} onAbbrechen={() => { setSelected(null); setError(false); }}>
        <label>Grund für den Widerruf<textarea data-rueckfrage-feld="" required maxLength={2000} value={reason} readOnly={busy} onChange={event => setReason(event.target.value)} /></label>
      </Rueckfrage>}
    </article>;
  }
  return <div className="profile-claims claim-controls">
    {claims.length ? claims.map(claim => row(claim, true)) : <p className="profile-empty">Noch keine aktuell bestätigte Aussage.</p>}
    {history.length > 0 && <details><summary>Weitere und frühere Aussagen ({history.length})</summary>{history.map(claim => row(claim, false))}</details>}
  </div>;
}
