import { useEffect, useRef, useState } from "react";
import { api, type Project, type ProjectSuggestion } from "./api";
import { zeigeHinweis } from "./grundlage";

// Ablage, kein Fakt: Die Zuordnung ändert weder Einordnung noch Belege und
// lässt sich jederzeit zurückstellen. Deshalb speichert die Auswahl sofort
// und ohne Rückfrage, sagt aber im Hinweis unten, was passiert ist, mit „Rückgängig“ (V4). Vorschläge stammen nur aus
// den eigenen Zuordnungen des Nutzers. Neue Mails ordnet Kingfisher selbst zu, wenn alle früheren Mails des Absenders in
// einem Projekt liegen (Paket P, sidecar: projekt_automatik.py); das steht dann sichtbar da: „Zugeordnet nach Absender ·
// Ändern · Rückgängig“. „Rückgängig“ wird gemerkt, die Mail kommt nicht wieder dorthin.
export function SourceProject({id, projectId}: {id: string; projectId: string | null}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [value, setValue] = useState(projectId ?? "");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<{ok: boolean; text: string} | null>(null);
  const [hint, setHint] = useState<ProjectSuggestion | null>(null);
  const [offer, setOffer] = useState<{projectId: string; name: string; count: number; sender: string} | null>(null);
  const auswahl = useRef<HTMLSelectElement | null>(null);
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
    setValue(next); setSaving(true); setResult(null); setOffer(null);
    // Was der Nutzer wählt, gilt; die automatische Zuordnung ist damit keine mehr (der Sidecar vergisst sie ebenso).
    setHint(current => current ? {...current, automatisch: null} : current);
    try {
      await api.linkSourceProject(id, next || null);
      const name = nameOf(next);
      const vorherName = nameOf(previous);
      zeigeHinweis({text: name ? `Dem Projekt „${name}“ zugeordnet.` : "Keinem Projekt mehr zugeordnet.",
        rueckgaengig: async () => {
          await api.linkSourceProject(id, previous || null);
          setValue(previous); setOffer(null);
          return vorherName ? `Wieder dem Projekt „${vorherName}“ zugeordnet.` : "Wieder keinem Projekt zugeordnet.";
        }});
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
      const moved = {ids: changed, projectId: offer.projectId};
      setOffer(null);
      setHint(current => current ? {...current, unassigned_peers: 0} : current);
      zeigeHinweis({text: changed.length === 1 ? `Eine weitere Mail dem Projekt „${offer.name}“ zugeordnet.`
        : `${changed.length} weitere Mails dem Projekt „${offer.name}“ zugeordnet.`, ...(changed.length ? {rueckgaengig: () => undoSender(moved)} : {})});
    } catch {
      setResult({ok: false, text: "Die weiteren Mails konnten nicht zugeordnet werden. Bitte erneut versuchen."});
    } finally { setSaving(false); }
  }

  // „Rückgängig“ im Hinweis: nur die eben zugeordneten Mails, und nur, solange sie noch bei diesem Projekt liegen.
  async function undoSender(moved: {ids: string[]; projectId: string}) {
    setSaving(true);
    try {
      const {changed} = await api.linkSourceProjects(moved.ids, null, moved.projectId);
      setHint(current => current ? {...current, unassigned_peers: changed.length} : current);
      return `Rückgängig gemacht: ${changed.length === 1 ? "Eine Mail ist" : `${changed.length} Mails sind`} wieder keinem Projekt zugeordnet.`;
    } finally { setSaving(false); }
  }

  // „Rückgängig“ einer automatischen Zuordnung: gelöst und gemerkt; der Satz des Sidecars sagt es.
  async function undoAutomatic() {
    setSaving(true); setResult(null);
    try {
      const antwort = await api.projektZuordnungZuruecknehmen(id);
      setValue(""); setHint(current => current ? {...current, automatisch: null} : current);
      zeigeHinweis({text: antwort.satz});
    } catch {
      setResult({ok: false, text: "Das ließ sich gerade nicht zurücknehmen. Bitte die Auswahl oben ändern."});
    } finally { setSaving(false); }
  }

  const automatisch = hint?.automatisch && hint.automatisch.projekt_id === value ? hint.automatisch : null;
  const suggestion = !value && hint?.suggestion && options.some(project => project.id === hint.suggestion?.project_id) ? hint.suggestion : null;
  return <div className="source-project">
    <label htmlFor={`source-project-${id}`}>Projekt</label>
    <select ref={auswahl} id={`source-project-${id}`} value={value} disabled={saving} onChange={event => void choose(event.target.value)}>
      <option value="">Kein Projekt</option>
      {options.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
    </select>
    {automatisch && <p className="source-project-hint source-project-auto">{automatisch.satz}{" · "}
      <button type="button" className="text-action" disabled={saving} onClick={() => auswahl.current?.focus()}>Ändern</button>{" · "}
      <button type="button" className="text-action" disabled={saving} onClick={() => void undoAutomatic()}>Rückgängig</button></p>}
    {suggestion && <p className="source-project-hint">Vorschlag: {suggestion.name}. Die bisherigen {suggestion.count} Mails von {hint?.sender} liegen dort.{" "}
      <button type="button" className="secondary-action" disabled={saving} onClick={() => void choose(suggestion.project_id)}>Übernehmen</button></p>}
    {result && <p role={result.ok ? "status" : "alert"}>{result.text}</p>}
    {offer && <p className="source-project-hint">{offer.count === 1 ? `Auch die weitere Mail von ${offer.sender} ohne Projekt` : `Auch die ${offer.count} weiteren Mails von ${offer.sender} ohne Projekt`} dem Projekt „{offer.name}“ zuordnen?{" "}
      <button type="button" className="secondary-action" disabled={saving} onClick={() => void applyToSender()}>Ja, zuordnen</button></p>}
  </div>;
}
