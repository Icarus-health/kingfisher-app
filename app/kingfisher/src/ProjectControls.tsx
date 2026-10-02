import { useState, type FormEvent } from "react";
import { api, type Project } from "./api";
import "./ProjectControls.css";

type ProjectStatus = "idea" | "active" | "paused" | "done" | "dropped";

const PROJECT_STATUSES: Array<{ value: ProjectStatus; label: string }> = [
  { value: "idea", label: "Idee" },
  { value: "active", label: "Aktiv" },
  { value: "paused", label: "Pausiert" },
  { value: "done", label: "Erledigt" },
  { value: "dropped", label: "Verworfen" },
];

export function ProjectControls({ projects, selectedId, onSelect, onChanged }: {
  projects: Project[];
  selectedId: string;
  onSelect: (id: string) => void;
  onChanged: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedProject = projects.find((project) => project.id === selectedId);

  function clearCreateForm() {
    setCreating(false);
    setName("");
    setDescription("");
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName || busy) return;

    setBusy(true);
    setError(null);
    try {
      const project = await api.addProject({ name: cleanName, description: description.trim() });
      onChanged();
      onSelect(project.id);
      clearCreateForm();
    } catch {
      setError("Das Projekt konnte nicht angelegt werden. Bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: ProjectStatus) {
    if (!selectedProject || status === selectedProject.status || busy) return;

    setBusy(true);
    setError(null);
    try {
      await api.updateProject(selectedProject.id, { status });
      onChanged();
    } catch {
      setError("Der Status konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Projekt steuern" className="project-controls">
      <div className="project-controls-toolbar">
        <label className="project-select-field">
          <span>Projekt</span>
          <select disabled={busy} onChange={(event) => onSelect(event.target.value)} value={selectedId}>
            <option value="">Alle Projekte</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
        <button
          aria-expanded={creating}
          className="secondary-action"
          disabled={busy}
          onClick={() => { setError(null); setCreating((open) => !open); }}
          type="button"
        >
          Neues Projekt
        </button>
      </div>

      {creating ? (
        <form aria-label="Projekt anlegen" className="project-create-form" onSubmit={createProject}>
          <label>
            Name
            <input autoFocus disabled={busy} onChange={(event) => setName(event.target.value)} placeholder="Name des Projekts" required value={name} />
          </label>
          <label>
            Beschreibung <small>(optional)</small>
            <textarea disabled={busy} onChange={(event) => setDescription(event.target.value)} placeholder="Worum geht es?" value={description} />
          </label>
          <div className="project-form-actions">
            <button className="secondary-action" disabled={busy} onClick={clearCreateForm} type="button">Abbrechen</button>
            <button className="primary-action" disabled={busy || !name.trim()} type="submit">{busy ? "Wird gespeichert …" : "Projekt anlegen"}</button>
          </div>
        </form>
      ) : null}

      {selectedProject ? (
        <div className="project-status-control">
          <div>
            <strong>{selectedProject.name}</strong>
            {selectedProject.description ? <small>{selectedProject.description}</small> : null}
          </div>
          <label>
            Status
            <select disabled={busy} onChange={(event) => void changeStatus(event.target.value as ProjectStatus)} value={selectedProject.status}>
              {PROJECT_STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
            </select>
          </label>
        </div>
      ) : (
        <p className="project-selection-hint">Ohne Projektauswahl werden alle Einträge angezeigt.</p>
      )}

      {error ? <p aria-live="polite" className="project-controls-error" role="alert">{error}</p> : null}
    </section>
  );
}
