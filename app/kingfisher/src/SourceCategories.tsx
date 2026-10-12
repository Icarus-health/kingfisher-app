import { useEffect, useState } from 'react';
import { api, ApiError } from './api';
import { categoryFailureText } from './categoryFailureText';

type Annotations = Awaited<ReturnType<typeof api.sourceCategories>>;
type Taxonomy = Awaited<ReturnType<typeof api.categoryTaxonomy>>;

export function SourceCategories({ id, readOnly = false }: { id: string; readOnly?: boolean }) {
  const [data, setData] = useState<Annotations | null>(null);
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [reviewedRevision, setReviewedRevision] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let loading = false;
    setData(null); setEditing(false); setError(false); setConflict(false); setReviewedRevision(null);
    const refresh = async () => {
      if (loading || document.hidden) return;
      loading = true;
      try {
        const [annotations, types] = await Promise.all([api.sourceCategories(id), api.categoryTaxonomy()]);
        if (active) { setData(annotations); setTaxonomy(types); setError(false); }
      } catch { if (active) setError(true); }
      finally { loading = false; }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [id]);
  async function save() {
    if (readOnly || busy || conflict || !data?.revision || !reviewedRevision) return;
    setBusy(true); setError(false);
    try { setData(await api.correctSourceCategories(id, selected, reviewedRevision)); setEditing(false); }
    catch (failure) { setError(true); if (failure instanceof ApiError && failure.status === 409) setConflict(true); }
    finally { setBusy(false); }
  }
  return <section aria-label="Themen">
    <h4>Themen und Zuordnungsvorschläge</h4>
    {error && <p role="alert">Die Themen konnten nicht geladen oder gespeichert werden.</p>}
    {conflict && <p role="alert">Quelle, Bereiche oder deine Zuordnung haben sich geändert. Bitte abbrechen und den aktuellen Stand erneut prüfen.</p>}
    {!data && !error && <p role="status">Themen werden geladen …</p>}
    {data && <>
      {data.status === 'excluded' ? <p>Diese Quelle ist ausgeschlossen. Es werden keine Zuordnungen angezeigt.</p> : <>
        <p>Automatische Zuordnungen sind Vorschläge und keine bestätigten Fakten.</p>
        {data.status === 'failed' && <p role="status">Automatische Themenzuordnung fehlgeschlagen: {categoryFailureText(data.failure_code)}</p>}
        {data.categories.length ? <ul>{data.categories.map(category => <li key={category.id}><strong>{category.label}</strong> · {category.origin === 'user' ? 'Von dir zugeordnet' : 'Automatisch vorgeschlagen'}{category.evidence.map((proof, index) => <blockquote key={index}>{proof.quote}</blockquote>)}</li>)}</ul> : <p>{data.status === 'failed' ? 'Für diese Quelle liegen noch keine Themenhinweise vor.' : data.status === 'deferred' ? 'Diese Quelle konnte noch nicht vollständig sortiert werden.' : data.status === 'pending' ? 'Die Themen stehen noch aus.' : 'Noch keine Themen zugeordnet.'}</p>}
        {data.correction?.stale && <p role="status">Deine frühere Zuordnung bleibt gespeichert. Die Quelle hat sich geändert; bitte prüfe die Zuordnung erneut.</p>}
        {data.entities.length > 0 && <ul>{data.entities.map((entity, index) => <li key={index}><strong>{entity.name}</strong> · {{person: 'Person', organization: 'Organisation', project: 'Projekt', place: 'Ort'}[entity.kind] ?? entity.kind} · {entity.role === 'sender' ? 'Absenderhinweis' : 'Im Text erwähnt'}<blockquote>{entity.quote}</blockquote><small>Quellenhinweis · noch keiner bestehenden Identität zugeordnet</small></li>)}</ul>}
        {!readOnly && !editing && <button type="button" className="text-action" disabled={!data.revision} onClick={() => {setSelected(data.categories.map(c => c.id)); setReviewedRevision(data.revision ?? null); setConflict(false); setEditing(true);}}>Themen korrigieren</button>}
        {!readOnly && editing && <form onSubmit={event => {event.preventDefault(); void save();}}>
          <fieldset disabled={busy}><legend>Deine Zuordnung</legend>{taxonomy?.items.map(category => <label className="mail-sync-check" key={category.id}><input type="checkbox" checked={selected.includes(category.id)} onChange={event => setSelected(current => event.target.checked ? [...current, category.id] : current.filter(value => value !== category.id))}/>{category.label}</label>)}</fieldset>
          <button type="submit" disabled={busy || conflict || !data.revision || !reviewedRevision}>Zuordnung speichern</button><button type="button" disabled={busy} onClick={() => {setEditing(false); setConflict(false); setReviewedRevision(null);}}>Abbrechen</button>
        </form>}
      </>}
    </>}
  </section>;
}
