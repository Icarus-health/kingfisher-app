import { useEffect, useState } from "react";
import { api } from "./api";

function text(value: unknown) { return typeof value === "string" ? value : ""; }
function localDate(value: unknown) {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return adjusted.toISOString().slice(0, 16);
}
export function ClaimCorrection({claim, onChanged, onCancel}: {claim: Record<string, unknown>; onChanged: () => void; onCancel: () => void}) {
  const [value, setValue] = useState(text(claim.value));
  const [statement, setStatement] = useState(text(claim.statement));
  const [reason, setReason] = useState("");
  const [scope, setScope] = useState(text(claim.scope_ref));
  const [target, setTarget] = useState(text(claim.target_ref));
  const [from, setFrom] = useState(localDate(claim.valid_from));
  const [until, setUntil] = useState(localDate(claim.valid_until));
  const [identities, setIdentities] = useState<Array<{id: string; label: string; kind: string}>>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; api.identities().then(result => {if (active) {setIdentities(result.entities);setLoaded(true);}}).catch(() => {if (active) setError("Die Identitäten konnten nicht geladen werden. Bitte den Dialog erneut öffnen.");}); return () => {active = false;}; }, []);
  const invalidInterval = !!from && !!until && new Date(until) <= new Date(from);
  function identityLabel(item: {id: string; label: string; kind: string}) {
    const kind = ({person: "Person", project: "Projekt", organization: "Organisation", topic: "Thema", place: "Ort", document: "Dokument"} as Record<string, string>)[item.kind] || "Eintrag";
    const ambiguous = identities.some(other => other.id !== item.id && other.kind === item.kind && other.label === item.label);
    return `${item.label} · ${kind}${ambiguous ? ` · ${item.id.slice(-8)}` : ""}`;
  }
  function options(current: string) {
    return <><option value="">Keine gesonderte Zuordnung</option>{current && !identities.some(item => item.id === current) && <option value={current}>{current} (bestehende Zuordnung)</option>}{identities.map(item => <option key={item.id} value={item.id}>{identityLabel(item)}</option>)}</>;
  }
  function label(id: string) {
    const item = identities.find(item => item.id === id);
    return item ? identityLabel(item) : id || "Keine gesonderte Zuordnung";
  }
  async function save() {
    if (busy || !review) return;
    setBusy(true); setError("");
    try {
      await api.correctClaim(String(claim.id), {value: value.trim(), statement: statement.trim(), reason: reason.trim(), scope_ref: scope || null, target_ref: target || null, valid_from: from === localDate(claim.valid_from) ? text(claim.valid_from) || null : from ? new Date(from).toISOString() : null, valid_until: until === localDate(claim.valid_until) ? text(claim.valid_until) || null : until ? new Date(until).toISOString() : null});
      onChanged();
    } catch {setError("Die Korrektur konnte nicht übernommen werden. Möglicherweise wurde die Aussage inzwischen geändert oder steht im Konflikt mit anderem Wissen. Bitte den aktuellen Stand prüfen.");setBusy(false);}
  }
  return <form aria-label="Aussage korrigieren" onSubmit={event => {event.preventDefault(); if (review) void save(); else if (!invalidInterval) setReview(true);}}>
    <p>Deine Korrektur wird als neue Nutzerangabe belegt. Der bisherige Stand bleibt im Verlauf erhalten. Person und Beziehungsart bleiben gleich.</p>
    {!review ? <>
      <label>Neuer Wert<input required maxLength={2000} value={value} onChange={event => setValue(event.target.value)} /></label>
      <label>Neue Aussage<textarea required maxLength={8000} value={statement} onChange={event => setStatement(event.target.value)} /></label>
      <label>Bezug zu<select aria-label="Bezug zu" value={target} disabled={!loaded} onChange={event => setTarget(event.target.value)}>{options(target)}</select></label>
      <label>Kontext<select aria-label="Kontext" value={scope} disabled={!loaded} onChange={event => setScope(event.target.value)}>{options(scope)}</select></label>
      <label>Gültig ab (Ortszeit)<input type="datetime-local" value={from} onChange={event => setFrom(event.target.value)} /></label>
      <label>Gültig bis (ausschließlich, Ortszeit)<input type="datetime-local" value={until} onChange={event => setUntil(event.target.value)} /></label>
      <label>Grund der Korrektur<textarea required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></label>
      {invalidInterval && <p role="alert">Das Ende muss nach dem Beginn liegen.</p>}
      <button className="primary-action" disabled={!loaded || !value.trim() || !statement.trim() || !reason.trim() || invalidInterval} type="submit">Korrektur prüfen</button>
    </> : <div aria-label="Korrektur prüfen">
      <p>Bisher: {text(claim.statement)}</p><p>Neu: {statement}</p><p>Wert: {value} · Bezug: {label(target)} · Kontext: {label(scope)}</p>
      <p>Gültig ab: {from.replace("T", " ") || "offen"} · bis: {until.replace("T", " ") || "offen"} (Ortszeit)</p><p>Grund: {reason}</p>
      <button className="primary-action" disabled={busy} type="submit">Korrektur bestätigen</button>
      <button className="secondary-action" disabled={busy} onClick={() => setReview(false)} type="button">Bearbeiten</button>
    </div>}
    <button className="secondary-action" type="button" disabled={busy} onClick={onCancel}>Abbrechen</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}
