import { useEffect, useState } from 'react';
import { api } from './api';
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
  useEffect(() => {
    let active = true;
    let loading = false;
    setData(null); setEditing(false); setError(false);
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
    if (readOnly || busy) return;
    setBusy(true); setError(false);
    try { setData(await api.correctSourceCategories(id, selected)); setEditing(false); }
    catch { setError(true); }
    finally { setBusy(false); }
  }
  return <section aria-label="Themen">
    <h4>Themen und Zuordnungsvorschläge</h4>
    {error && <p role="alert">Die Themen konnten nicht geladen oder gespeichert werden.</p>}
    {!data && !error && <p role="status">Themen werden geladen …</p>}
    {data && <>
      {data.status === 'excluded' ? <p>Diese Quelle ist ausgeschlossen. Es werden keine Zuordnungen angezeigt.</p> : <>
        <p>Automatische Zuordnungen sind Vorschläge und keine bestätigten Fakten.</p>
        {data.status === 'failed' && <p role="status">Automatische Themenzuordnung fehlgeschlagen: {categoryFailureText(data.failure_code)}</p>}
        {data.categories.length ? <ul>{data.categories.map(category => <li key={category.id}><strong>{category.label}</strong> · {category.origin === 'user' ? 'Von dir zugeordnet' : 'Automatisch vorgeschlagen'}{category.evidence.map((proof, index) => <blockquote key={index}>{proof.quote}</blockquote>)}</li>)}</ul> : <p>{data.status === 'failed' ? 'Für diese Quelle liegen noch keine Themenhinweise vor.' : data.status === 'deferred' ? 'Diese Quelle konnte noch nicht vollständig sortiert werden.' : data.status === 'pending' ? 'Die Themen stehen noch aus.' : 'Noch keine Themen zugeordnet.'}</p>}
        {data.correction?.stale && <p role="status">Deine frühere Zuordnung bleibt gespeichert. Die Quelle hat sich geändert; bitte prüfe die Zuordnung erneut.</p>}
        {data.entities.length > 0 && <ul>{data.entities.map((entity, index) => <li key={index}><strong>{entity.name}</strong> · {{person: 'Person', organization: 'Organisation', project: 'Projekt', place: 'Ort'}[entity.kind] ?? entity.kind} · {entity.role === 'sender' ? 'Absenderhinweis' : 'Im Text erwähnt'}<blockquote>{entity.quote}</blockquote><small>Quellenhinweis · noch keiner bestehenden Identität zugeordnet</small></li>)}</ul>}
        {!readOnly && !editing && <button type="button" className="text-action" onClick={() => {setSelected(data.categories.map(c => c.id)); setEditing(true);}}>Themen korrigieren</button>}
        {!readOnly && editing && <form onSubmit={event => {event.preventDefault(); void save();}}>
          <fieldset disabled={busy}><legend>Deine Zuordnung</legend>{taxonomy?.items.map(category => <label className="mail-sync-check" key={category.id}><input type="checkbox" checked={selected.includes(category.id)} onChange={event => setSelected(current => event.target.checked ? [...current, category.id] : current.filter(value => value !== category.id))}/>{category.label}</label>)}</fieldset>
          <button type="submit" disabled={busy}>Zuordnung speichern</button><button type="button" disabled={busy} onClick={() => setEditing(false)}>Abbrechen</button>
        </form>}
      </>}
    </>}
  </section>;
}
