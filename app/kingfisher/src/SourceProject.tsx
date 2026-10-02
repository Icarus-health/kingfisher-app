import { useEffect, useState } from "react";
import { api, type Project, type ProjectSuggestion } from "./api";

// Ablage, kein Fakt: Die Zuordnung ändert weder Einordnung noch Belege und
// lässt sich jederzeit zurückstellen. Deshalb speichert die Auswahl sofort
// und ohne Rückfrage, sagt aber, was passiert ist. Vorschläge stammen nur aus
// den eigenen Zuordnungen des Nutzers und werden nie selbst angewendet.
export function SourceProject({id, projectId}: {id: string; projectId: string | null}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [value, setValue] = useState(projectId ?? "");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ok: boolean; text: string} | null>(null);
  const [hint, setHint] = useState<ProjectSuggestion | null>(null);
  const [offer, setOffer] = useState<{projectId: string; name: string; count: number; sender: string} | null>(null);
  const [moved, setMoved] = useState<{ids: string[]; projectId: string; name: string} | null>(null);
  useEffect(() => {
    let active = true;
    api.projects().then(items => {if (active) setProjects(items);}).catch(() => {if (active) setProjects([]);});
    api.projectSuggestion(id).then(found => {if (active) setHint(found);}).catch(() => undefined);
    return () => {active = false;};
  }, [id]);
  if (projects === null) return null;
  const options = projects.filter(project => project.open || project.id === value);
  if (options.length === 0) return null;
  const nameOf = (projectId: string) => projects.find(project => project.id === projectId)?.name ?? "";

  async function choose(next: string) {
    const previous = value;
    setValue(next); setSaving(true); setResult(null); setOffer(null); setMoved(null);
    try {
      await api.linkSourceProject(id, next || null);
      const name = nameOf(next);
      setResult({ok: true, text: name ? `Dem Projekt „${name}“ zugeordnet.` : "Keinem Projekt mehr zugeordnet."});
      if (next && hint?.unassigned_peers && hint.sender) {
        setOffer({projectId: next, name, count: hint.unassigned_peers, sender: hint.sender});
      }
    } catch {
      setValue(previous);
      setResult({ok: false, text: "Die Zuordnung konnte nicht gespeichert werden. Bitte erneut versuchen."});
    } finally { setSaving(false); }
  }

  async function applyToSender() {
    if (!offer) return;
    setSaving(true);
    try {
      const {changed} = await api.linkSameSender(id, offer.projectId);
      setMoved({ids: changed, projectId: offer.projectId, name: offer.name});
      setOffer(null);
      setResult({ok: true, text: changed.length === 1 ? `Eine weitere Mail dem Projekt „${offer.name}“ zugeordnet.`
        : `${changed.length} weitere Mails dem Projekt „${offer.name}“ zugeordnet.`});
      setHint(current => current ? {...current, unassigned_peers: 0} : current);
    } catch {
      setResult({ok: false, text: "Die weiteren Mails konnten nicht zugeordnet werden. Bitte erneut versuchen."});
    } finally { setSaving(false); }
  }

  async function undoSender() {
    if (!moved) return;
    setSaving(true);
    try {
      const {changed} = await api.linkSourceProjects(moved.ids, null, moved.projectId);
      setResult({ok: true, text: `Rückgängig gemacht: ${changed.length === 1 ? "Eine Mail ist" : `${changed.length} Mails sind`} wieder keinem Projekt zugeordnet.`});
      setHint(current => current ? {...current, unassigned_peers: changed.length} : current);
      setMoved(null);
    } catch {
      setResult({ok: false, text: "Das Rückgängigmachen hat nicht geklappt. Bitte erneut versuchen."});
    } finally { setSaving(false); }
  }

  const suggestion = !value && hint?.suggestion && options.some(project => project.id === hint.suggestion?.project_id) ? hint.suggestion : null;
  return <div className="source-project">
    <label htmlFor={`source-project-${id}`}>Projekt</label>
    <select id={`source-project-${id}`} value={value} disabled={saving} onChange={event => void choose(event.target.value)}>
      <option value="">Kein Projekt</option>
      {options.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
    </select>
    {suggestion && <p className="source-project-hint">Vorschlag: {suggestion.name}. Die bisherigen {suggestion.count} Mails von {hint?.sender} liegen dort.{" "}
      <button type="button" className="secondary-action" disabled={saving} onClick={() => void choose(suggestion.project_id)}>Übernehmen</button></p>}
    {result && <p role={result.ok ? "status" : "alert"}>{result.text}</p>}
    {offer && <p className="source-project-hint">{offer.count === 1 ? `Auch die weitere Mail von ${offer.sender} ohne Projekt` : `Auch die ${offer.count} weiteren Mails von ${offer.sender} ohne Projekt`} dem Projekt „{offer.name}“ zuordnen?{" "}
      <button type="button" className="secondary-action" disabled={saving} onClick={() => void applyToSender()}>Ja, zuordnen</button></p>}
    {moved && moved.ids.length > 0 && <p className="source-project-hint"><button type="button" className="secondary-action" disabled={saving} onClick={() => void undoSender()}>Rückgängig</button></p>}
  </div>;
}
