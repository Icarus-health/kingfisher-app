import { useState } from "react";
import { api, type RegistryProfile, type IdentitySource } from "./api";
import { navigate } from "./ui";

export function IdentityControls({data, onChanged}: {data: RegistryProfile; onChanged: () => void}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(data.entity.label);
  const [removing, setRemoving] = useState<IdentitySource | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  async function change(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true); setError(false);
    try { await action(); onChanged(); }
    catch { setError(true); setBusy(false); }
  }
  return <section className="profile-card identity-controls" aria-label="Identität klären">
    <details><summary>Profil verwalten{data.same_name_entities.length > 0 ? ` · Weitere gleichnamige Einträge: ${data.same_name_entities.length}` : ""}</summary>
    <p>Die Kennung bleibt beim Umbenennen erhalten. Gleichnamige Einträge werden getrennt geführt.</p>
    {!editing ? <button className="secondary-action" type="button" disabled={busy} onClick={() => {setName(data.entity.label);setEditing(true);}}>Name bearbeiten</button> : <form onSubmit={event => {event.preventDefault();void change(() => api.renameIdentity(data.entity.id, name.trim()));}}>
      <label>Anzeigename<input value={name} onChange={event => setName(event.target.value)} maxLength={500} disabled={busy} required /></label>
      <button className="primary-action" disabled={busy || !name.trim()} type="submit">Name speichern</button>
      <button className="secondary-action" disabled={busy} type="button" onClick={() => setEditing(false)}>Abbrechen</button>
    </form>}
    {data.same_name_entities.length > 0 && <div><h3>Weitere Einträge mit diesem Namen</h3><p>Dies sind eigenständige Identitäten. Öffne einen Eintrag zum Vergleich.</p>{data.same_name_entities.map(entity => <p key={entity.id}><a href={`/memory/registry/${encodeURIComponent(entity.id)}`} onClick={event => {event.preventDefault();navigate(`/memory/registry/${encodeURIComponent(entity.id)}`);}}>{entity.label} · {entity.id.slice(-8)}</a></p>)}</div>}
    <h3>Verknüpfte Quellenkennungen</h3>
    {data.sources.length === 0 && <p>Keine Quellenkennung ausdrücklich zugeordnet.</p>}
    {data.sources.map(source => <div className="identity-source" key={JSON.stringify(source)}><p>{source.source} · {source.account} · {source.native_id}</p><button className="secondary-action" disabled={busy} type="button" onClick={() => setRemoving(source)}>Zuordnung lösen</button></div>)}
    {removing && <div role="group" aria-label="Quellenzuordnung lösen"><p>Zuordnung von {removing.native_id} zu {data.entity.label} lösen?</p><p>Gilt für diese Quellenkennung. Bestehende Aussagen bitte separat prüfen.</p><button className="primary-action" disabled={busy} type="button" onClick={() => void change(() => api.unlinkIdentitySource(data.entity.id, removing))}>Zuordnung jetzt lösen</button><button className="secondary-action" disabled={busy} type="button" onClick={() => setRemoving(null)}>Abbrechen</button></div>}
    {error && <p role="alert">Die Änderung konnte nicht gespeichert werden. Bitte erneut versuchen.</p>}
    </details>
  </section>;
}
