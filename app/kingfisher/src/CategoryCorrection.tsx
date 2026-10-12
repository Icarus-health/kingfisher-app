import { useEffect, useRef, useState } from "react";
import { api, ApiError, type SourceCategoriesResult } from "./api";

type Taxonomy = Awaited<ReturnType<typeof api.categoryTaxonomy>>;

export function CategoryCorrection({ id, title, onSaved }: {
  id: string;
  title: string;
  onSaved?: (result: SourceCategoriesResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<SourceCategoriesResult | null>(null);
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    ++requestVersion.current;
    setOpen(false); setData(null); setTaxonomy(null); setSelected([]);
    setLoading(false); setSaving(false); setConflict(false); setError(null);
    return () => { ++requestVersion.current; };
  }, [id]);

  async function load() {
    const version = ++requestVersion.current;
    setOpen(true); setLoading(true); setError(null); setConflict(false);
    setData(null); setTaxonomy(null);
    try {
      const [source, types] = await Promise.all([api.sourceCategories(id), api.categoryTaxonomy()]);
      if (version !== requestVersion.current) return;
      if (source.episode_id !== id) throw new Error("Quelle stimmt nicht überein");
      setData(source); setTaxonomy(types);
      const available = new Set(types.items.map(item => item.id));
      setSelected(source.categories.map(item => item.id).filter(value => available.has(value)));
    } catch {
      if (version === requestVersion.current) setError("Die aktuelle Zuordnung konnte nicht geladen werden.");
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }

  function cancel() {
    ++requestVersion.current;
    setOpen(false); setData(null); setError(null); setLoading(false);
  }

  async function save() {
    if (!data?.revision || data.episode_id !== id || data.status === "excluded" || saving || loading || conflict) return;
    const version = requestVersion.current;
    setSaving(true); setError(null);
    try {
      const result = await api.correctSourceCategories(id, selected, data.revision);
      if (version !== requestVersion.current) return;
      if (result.episode_id !== id) throw new Error("Quelle stimmt nicht überein");
      setOpen(false); setData(null);
      onSaved?.(result);
    } catch (failure) {
      if (version !== requestVersion.current) return;
      if (failure instanceof ApiError && failure.status === 409) {
        setConflict(true);
        setError("Quelle, Bereiche oder deine Zuordnung haben sich geändert. Deine Auswahl bleibt hier erhalten. Bitte den aktuellen Stand prüfen.");
      } else setError("Die Zuordnung konnte nicht gespeichert werden. Deine Auswahl bleibt erhalten.");
    } finally {
      if (version === requestVersion.current) setSaving(false);
    }
  }

  if (!open) return <button type="button" className="memory-area-edit" onClick={() => void load()}
    aria-label={`Zuordnung für ${title || "diese Quelle"} ändern`}>Zuordnung ändern</button>;

  return <section className="memory-area-feedback" aria-label={`Zuordnung für ${title || "diese Quelle"}`}>
    <h4>Wo gehört diese Quelle hin?</h4>
    <p>Deine Auswahl bleibt für diese Quelle gespeichert. Automatische Wiederprüfung überschreibt sie nicht. Originaltext und Fakten bleiben unverändert.</p>
    {loading && <p role="status">Aktuelle Zuordnung wird geladen …</p>}
    {error && <p role="alert">{error}</p>}
    {data?.status === "excluded" ? <p role="status">Diese Quelle ist nicht mehr verfügbar. Eine Zuordnung kann nicht gespeichert werden.</p>
      : data && !data.revision ? <p role="status">Der Dienst unterstützt die sichere Zuordnung noch nicht. Bitte App und Dienst gemeinsam aktualisieren.</p>
      : data && taxonomy && <form onSubmit={event => { event.preventDefault(); void save(); }}>
        {data.correction?.stale && <p role="status">Deine frühere Zuordnung gehört zu einer älteren Fassung. Prüfe die aktuelle Originalquelle vor dem Speichern.</p>}
        <fieldset disabled={saving || conflict}><legend>Bereiche auswählen</legend>
          {taxonomy.items.map(item => <label className="mail-sync-check" key={item.id}>
            <input type="checkbox" value={item.id} checked={selected.includes(item.id)} onChange={event => {
              const checked = event.target.checked;
              setSelected(current => checked ? [...current, item.id] : current.filter(value => value !== item.id));
            }} />{item.label}
          </label>)}
        </fieldset>
        <p>Mehrere Bereiche sind möglich. Ohne Auswahl entfernst du nur die Themenzuordnung, nicht die Quelle.</p>
        <button type="submit" className="memory-area-edit" disabled={saving || conflict}>{saving ? "Wird gespeichert …" : "Zuordnung speichern"}</button>
      </form>}
    {conflict && <button type="button" className="memory-area-edit" onClick={() => void load()}>Aktuellen Stand prüfen</button>}
    {error && !data && <button type="button" className="memory-area-edit" onClick={() => void load()}>Erneut versuchen</button>}
    <button type="button" className="memory-area-edit" disabled={saving} onClick={cancel}>Abbrechen</button>
  </section>;
}
