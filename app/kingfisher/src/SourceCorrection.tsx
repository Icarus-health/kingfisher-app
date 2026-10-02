import { useState } from "react";
import { ApiError, api, type WorkingMemoryCorrection } from "./api";

/** `knopf`: wie der Knopf heißt; unter der eigenen Frage „Wortlaut berichtigen“ (Fremdprobe, Befund 15). */
export function SourceCorrection({id, onChange, knopf = "Angabe berichtigen"}: {id: string; onChange?: () => void; knopf?: string}) {
  const [draft, setDraft] = useState<WorkingMemoryCorrection | null>(null);
  const [body, setBody] = useState("");
  const [review, setReview] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [saved, setSaved] = useState(false);

  async function load() {
    if (loading || saving) return;
    setLoading(true); setError(null); setConflict(false);
    try {
      const result = await api.workingMemoryCorrection(id);
      setDraft(result); setBody(result.body); setReview(false);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) {
        setConflict(true);
        setError("Dieses automatische Ergebnis lässt sich nicht direkt berichtigen. Prüfe den aktuellen Stand und korrigiere gegebenenfalls eine bestätigte Aussage.");
      } else setError("Der aktuelle Stand konnte nicht geladen werden. Bitte erneut versuchen.");
    } finally { setLoading(false); }
  }

  async function save() {
    if (!draft || saving || !body.trim() || body.length > 12000 || body === draft.body) return;
    setSaving(true); setError(null); setConflict(false);
    try {
      await api.saveWorkingMemoryCorrection(id, {fingerprint: draft.fingerprint, body});
      setSaved(true);
      onChange?.();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) {
        setConflict(true);
        setError("Die Quelle hat sich geändert oder ist nicht mehr verfügbar. Bitte öffne ihren aktuellen Stand. Dein Entwurf bleibt hier erhalten.");
      } else setError("Die Berichtigung konnte nicht gespeichert werden. Dein Entwurf bleibt erhalten.");
    } finally { setSaving(false); }
  }

  return <div>
    {!draft && !saved && <button className="secondary-action" type="button" disabled={loading || saving} onClick={() => void load()}>{loading ? "Aktuellen Stand laden …" : knopf}</button>}
    {error && <p role="alert">{error}</p>}
    {draft && !saved && <section aria-label="Angabe berichtigen">
      <p>Deine Fassung wird als eigene Angabe gespeichert. Die ursprüngliche Quelle bleibt erhalten und wird nicht weiter verwendet. Bitte Namen, Bedingungen und konkrete Datumsangaben prüfen.</p>
      <p>Ersetze relative Angaben wie „morgen“ durch ein konkretes Datum. Der Zeitbezug übernommener Sätze wird nicht auf heute verschoben.</p>
      {draft.source_time && <p>Datum der ursprünglichen Quelle: {new Date(draft.source_time).toLocaleString("de-DE")}</p>}
      {!review ? <>
        <label>Deine vollständige Fassung<textarea value={body} maxLength={12000} onChange={event => setBody(event.target.value)} /></label>
        <p>{body.length} / 12.000 Zeichen</p>
        <button className="primary-action" type="button" disabled={saving || !body.trim() || body.length > 12000 || body === draft.body} onClick={() => setReview(true)}>Fassung prüfen</button>
      </> : <div role="group" aria-label="Berichtigung prüfen">
        <h4>{draft.title}</h4>
        <p>Diese vollständige Fassung wird als Änderung behandelt. Das frühere Ergebnis für einzelne Sätze wird nicht übernommen.</p>
        <div className="task-source-body">{body}</div>
        <details><summary>Bisherige Fassung</summary><div className="task-source-body">{draft.body}</div></details>
        <button className="primary-action" type="button" disabled={saving || conflict} onClick={() => void save()}>{saving ? "Berichtigung wird gespeichert …" : "Berichtigung speichern"}</button>
        <button className="secondary-action" type="button" disabled={saving} onClick={() => setReview(false)}>Weiter bearbeiten</button>
      </div>}
      <button className="secondary-action" type="button" disabled={saving} onClick={() => {setDraft(null); setBody(""); setReview(false); setError(null); setConflict(false);}}>Abbrechen</button>
    </section>}
    {saved && <p role="status">Deine Berichtigung wurde als eigene Angabe gespeichert. Die ursprüngliche Quelle wird nicht weiter verwendet.</p>}
  </div>;
}
