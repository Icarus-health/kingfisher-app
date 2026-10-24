import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type Project } from "./api";
import "./ProjectControls.css";

type ProjectStatus = "idea" | "active" | "paused" | "done" | "dropped";

const PROJECT_STATUSES: Array<{ value: ProjectStatus; label: string }> = [
  { value: "idea", label: "Idee" },
  { value: "active", label: "Aktiv" },
  { value: "paused", label: "Pausiert" },
  { value: "done", label: "Erledigt" },
  { value: "dropped", label: "Verworfen" },
];

/**
 * Projekte anlegen und den Stand des gewählten Projekts ändern. Steht im Reiter „Projekte“; die Auswahl, welches
 * Projekt die Liste zeigt, ist ein kleiner Filter neben der Suche (`Tasks` in App.tsx).
 */
export function ProjectControls({ projects, selectedId, onSelect, onChanged, contextRevision=0, onFormular }: {
  projects: Project[];
  selectedId: string;
  onSelect: (id: string) => void;
  onChanged: () => void | Promise<void>;
  contextRevision?: number;
  /** Meldet, ob das Formular „Neues Projekt“ offen ist (dann ist sein Knopf der eine gefüllte der Ansicht). */
  onFormular?: (offen: boolean) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const requestId = useRef<string | null>(null);
  useEffect(()=>setError(null),[selectedId,contextRevision]);
  const selectedProject = projects.find((project) => project.id === selectedId);
  const meldeFormular = useRef(onFormular);
  meldeFormular.current = onFormular;
  useEffect(() => { meldeFormular.current?.(creating); }, [creating]);

  function clearCreateForm() {
    requestId.current = null;
    setCreating(false);
    setName("");
    setDescription("");
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName || busy || pending.current) return;

    setBusy(true);
    pending.current = true;
    requestId.current ??= crypto.randomUUID();
    setError(null);
    try {
      const project = await api.addProject({ name: cleanName, description: description.trim(), request_id: requestId.current });
      await onChanged();
      onSelect(project.id);
      clearCreateForm();
    } catch (failure) {
      setError(failure instanceof ApiError && failure.detail ? failure.detail : "Speichern wurde nicht bestätigt. Prüfe vorhandene Projekte oder wiederhole mit denselben Angaben.");
    } finally {
      setBusy(false);
      pending.current = false;
    }
  }

  async function changeStatus(status: ProjectStatus) {
    if (!selectedProject || status === selectedProject.status || busy || pending.current) return;

    setBusy(true);
    pending.current = true;
    setError(null);
    try {
      await api.updateProject(selectedProject.id, { status });
      await onChanged();
    } catch (failure) {
      setError(failure instanceof ApiError && failure.detail ? failure.detail : "Der aktuelle Projektstand konnte nicht bestätigt werden. Bitte erneut laden.");
    } finally {
      setBusy(false);
      pending.current = false;
    }
  }

  return (
    <section aria-label="Projekt steuern" className="project-controls">
      <div className="project-controls-toolbar">
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
            Beschreibung
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
      ) : null}

      {error ? <p aria-live="polite" className="project-controls-error" role="alert">{error}</p> : null}
    </section>
  );
}
