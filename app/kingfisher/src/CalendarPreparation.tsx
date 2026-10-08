import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type CalendarOverview, type CalendarPreparation as Preparation, type Project, type TerminZuordnung } from "./api";
import { displayLabel } from "./displayIdentity";
import { ProfileSource } from "./ProfileSource";
import { navigate } from "./ui";
import { Herkunft } from "./HerkunftAnzeige";

const WORKING_KIND_LABELS: Record<string, string> = {
  request: "Bitte", commitment: "Zusage", conditional: "Bedingte Aussage",
  change: "Änderung", status: "Statusmeldung", fact: "Angabe",
  uncertain: "Unklar zugeordnet", historical: "Frühere Aussage",
};

type Props = {
  event: CalendarOverview["items"][number];
  revision: number;
  onClose: () => void;
};

export function CalendarPreparation({ event, revision, onClose }: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [personId, setPersonId] = useState("");
  const [people, setPeople] = useState<Array<{id: string; label: string}>>([]);
  const [peopleError, setPeopleError] = useState(false);
  const [preparationState, setPreparationState] = useState<{context: string; value: Preparation} | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [expandedSources, setExpandedSources] = useState<string[]>([]);
  const [sourceRevision, setSourceRevision] = useState(0);
  const [correctionSaved, setCorrectionSaved] = useState(false);
  const [projectsError, setProjectsError] = useState(false);
  const [zuordnung, setZuordnung] = useState<TerminZuordnung | null>(null);
  const [zuordnungFehler, setZuordnungFehler] = useState(false);
  const contextKey = JSON.stringify([event.uid, event.start, projectId, personId]);
  const preparation = preparationState?.context === contextKey ? preparationState.value : null;

  useEffect(() => {
    let active = true;
    setProjectsError(false);
    setPeopleError(false);
    api.identities().then(next => { if (active) setPeople(next.entities.filter(item => item.kind === "person")); }).catch(() => { if (active) { setPeople([]); setPeopleError(true); } });
    api.projects().then(next => { if (active) setProjects(next); }).catch(() => { if (active) { setProjects([]); setProjectsError(true); } });
    return () => { active = false; };
  }, [revision]);

  // Wer kommt und worum es geht, ohne dass jemand wählen muss: Das Projekt
  // ist festgelegt oder vorgeschlagen und wird beim Öffnen einmal eingestellt.
  // Späteres Nachladen ändert die Auswahl nicht mehr unter der Hand.
  const zuordnungFolge = useRef(0);
  useEffect(() => {
    let active = true;
    const folge = ++zuordnungFolge.current;
    setZuordnungFehler(false);
    api.calendarAssignment(event.uid, event.start)
      .then(next => { if (!active || folge !== zuordnungFolge.current) return; setZuordnung(next); setProjectId(next.projekt?.id ?? ""); })
      .catch(() => { if (active && folge === zuordnungFolge.current) { setZuordnung(null); setZuordnungFehler(true); } });
    return () => { active = false; };
  }, [event.uid, event.start]);

  const projektWaehlen = (value: string) => {
    const vorher = zuordnung?.projekt?.id ?? "";
    const folge = ++zuordnungFolge.current;
    setProjectId(value);
    setExpandedSources([]);
    // Die Wahl gilt dauerhaft für diesen Termin, auch im Briefing. Scheitert
    // das Speichern, zeigt die Auswahl wieder den gespeicherten Stand, und
    // der Hinweis bleibt stehen, bis ein Speichern gelingt.
    api.setCalendarAssignment(event.uid, value || null, event.start)
      .then(next => { if (folge !== zuordnungFolge.current) return; setZuordnung(next); setZuordnungFehler(false); })
      .catch(() => { if (folge !== zuordnungFolge.current) return; setProjectId(vorher); setZuordnungFehler(true); });
  };

  useEffect(() => {
    setPreparationState(current => current?.context === contextKey ? current : null);
    setExpandedSources([]);
    setCorrectionSaved(false);
  }, [contextKey]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    api.calendarPreparation(event.uid, projectId, personId, event.start)
      .then(next => { if (active) setPreparationState({context: contextKey, value: next}); })
      .catch(() => { if (active) { setPreparationState(null); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [event.uid, projectId, personId, revision, sourceRevision, contextKey]);

  const openTasks = preparation?.tasks.filter(task => task.status === "open" && !task.wartet_auf) ?? [];
  const waitingTasks = preparation?.tasks.filter(task => task.status === "open" && Boolean(task.wartet_auf)) ?? [];
  const decisions = preparation?.decisions ?? [];
  const nameCounts = new Map<string, number>();
  for (const person of people) nameCounts.set(person.label, (nameCounts.get(person.label) ?? 0) + 1);
  const selectedPerson = people.find(person => person.id === personId);

  return <section className="calendar-preparation" aria-label="Termin vorbereiten">
    <div className="calendar-preparation-heading">
      <div><p className="eyebrow">VORBEREITEN</p><h2>{event.summary}</h2><p>Kontext zur Vorbereitung · Die Projektwahl gilt dauerhaft für diesen Termin</p></div>
      <button className="secondary-action" type="button" aria-label="Vorbereitung schließen" onClick={onClose}>Schließen</button>
    </div>
    {correctionSaved && <p role="status">Berichtigung gespeichert. Die frühere Angabe wird nicht mehr verwendet. Frage erneut nach dem aktuellen Stand.</p>}
    {zuordnung?.teilnehmer.length ? <div className="calendar-preparation-people"><h3 id="termin-mit-wem">Mit wem</h3>
      <ul aria-labelledby="termin-mit-wem">{zuordnung.teilnehmer.map((person, index) => <li key={`${index}:${person.eingabe}`}>
        {person.person ? <a href={`/memory/people/${encodeURIComponent(person.person)}`} onClick={e => { e.preventDefault(); navigate(`/memory/people/${encodeURIComponent(person.person!)}`); }}>{displayLabel(person.person).name}</a> : <strong>{person.name}</strong>}
        <small>{person.person ? `${person.kontakte === 1 ? "eine Quelle" : `${person.kontakte} Quellen`}${person.zuletzt ? ` · zuletzt ${new Date(person.zuletzt).toLocaleDateString("de-DE")}` : ""}` : person.adresse ? "noch keine Quelle mit dieser Adresse" : "ohne Mailadresse, nicht zuzuordnen"}</small>
      </li>)}</ul>
    </div> : <p>{event.attendees?.length ? `Im Kalender genannte Teilnehmer: ${event.attendees.join(", ")}` : "Der Kalender liefert keine Teilnehmerangaben."}</p>}
    {zuordnungFehler && <p role="alert">Die Projektwahl konnte nicht geladen oder gespeichert werden. Es gilt der zuletzt gespeicherte Stand.</p>}
    {zuordnung?.projekt?.herkunft === "vorschlag" && zuordnung.projekt.id === projectId && <p className="calendar-preparation-empty">Vorgeschlagen: {zuordnung.projekt.grund} Stimmt es nicht, wähle ein anderes Projekt oder „Kein Projekt ausgewählt“.</p>}
    <label className="calendar-preparation-project">Projektkontext
      <select value={projectId} onChange={e => projektWaehlen(e.target.value)} aria-label="Projektkontext auswählen">
        <option value="">Kein Projekt ausgewählt</option>
        {projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}
        {zuordnung?.projekt && !projects.some(project => project.id === zuordnung.projekt!.id) && <option value={zuordnung.projekt.id}>{zuordnung.projekt.name}</option>}
      </select>
    </label>
    <label className="calendar-preparation-project">Person aus dem Gedächtnis
      <select value={personId} onChange={e => { setPersonId(e.target.value); setExpandedSources([]); }} aria-label="Personenkontext auswählen">
        <option value="">Keine Person ausgewählt</option>
        {people.map((person, index) => <option value={person.id} key={person.id}>{person.label}{(nameCounts.get(person.label) ?? 0) > 1 ? ` · Profil ${index + 1}` : ""}</option>)}
      </select>
    </label>
    {peopleError && <p role="alert">Personen konnten nicht geladen werden. Bitte die Ansicht aktualisieren.</p>}
    {selectedPerson && (nameCounts.get(selectedPerson.label) ?? 0) > 1 && <p className="calendar-preparation-empty">Mehrere Personen heißen {selectedPerson.label}. Bitte die Personenakte prüfen.</p>}
    {projectsError && <p role="alert">Projekte konnten nicht geladen werden. Bitte die Ansicht aktualisieren.</p>}
    {loading && <p aria-live="polite">Vorbereitung wird geladen …</p>}
    {error && <p className="settings-error" role="alert">Vorbereitung konnte nicht geladen werden. Bitte erneut versuchen.</p>}
    {!loading && !error && !projectId && !personId && <p className="calendar-preparation-empty">Wähle ein Projekt oder eine Person, um vorhandenen Kontext einzublenden.</p>}
    {!error && (projectId || personId) && preparation && <div aria-busy={loading} hidden={loading} style={{display: loading ? "none" : undefined}}>
      {preparation.project && <p className="calendar-preparation-project-name">Projekt: <strong>{preparation.project.name}</strong></p>}
      {preparation.person && <p className="calendar-preparation-project-name">Person: <a href={`/memory/registry/${encodeURIComponent(preparation.person.id)}`}>{preparation.person.label} · Personenakte öffnen</a></p>}
      {projectId && !preparation.project && <p className="calendar-preparation-empty">Für dieses Projekt ist kein Kontext verfügbar.</p>}
      {(preparation.project || preparation.person) && <div className="calendar-preparation-grid">
        {preparation.project && <>
        <PreparationSection title="Offene Aufgaben" empty="Keine offenen Aufgaben.">
          {openTasks.map(task => <a href={`/vorhaben?project=${encodeURIComponent(projectId)}`} key={task.id} onClick={e => { e.preventDefault(); navigate(`/vorhaben?project=${encodeURIComponent(projectId)}`); }}>{task.title}</a>)}
        </PreparationSection>
        <PreparationSection title="Wartet auf" empty="Nichts wartet auf Rückmeldung.">
          {waitingTasks.map(task => <a href={`/vorhaben?view=waiting&project=${encodeURIComponent(projectId)}`} key={task.id} onClick={e => { e.preventDefault(); navigate(`/vorhaben?view=waiting&project=${encodeURIComponent(projectId)}`); }}>{task.title}{task.wartet_auf ? ` · ${task.wartet_auf}` : ""}</a>)}
        </PreparationSection>
        <PreparationSection title="Entscheidungen" empty="Keine aktiven Entscheidungen.">
          {decisions.map(decision => <a href={`/vorhaben?view=decisions&project=${encodeURIComponent(projectId)}`} key={decision.id} onClick={e => { e.preventDefault(); navigate(`/vorhaben?view=decisions&project=${encodeURIComponent(projectId)}`); }}>{decision.satz}{decision.erschuettert && <small>Grundlage hat sich geändert – bitte prüfen.</small>}{decision.ohne_grundlage && <small>Ohne dokumentierte Grundlage.</small>}</a>)}
        </PreparationSection>
        </>}
        <PreparationSection title="Aussagen mit Beleg" empty="Keine Aussagen mit Beleg.">
          {preparation.claims.map(claim => <div className="calendar-preparation-item" key={claim.id}><strong>{claim.statement}</strong>{claim.evidence.map(evidence => <small key={`${claim.id}-${evidence.episode_id}`}>{evidence.quote}</small>)}</div>)}
        </PreparationSection>
        <PreparationSection title="Quellen zur Vorbereitung" empty="Keine aufgenommenen Quellen für diese Auswahl.">
          {preparation.sources.map(source => <details className="calendar-preparation-item" key={source.id} open={expandedSources.includes(source.id)} onToggle={e => {
            const open = e.currentTarget.open;
            setExpandedSources(ids => open ? ids.includes(source.id) ? ids : [...ids, source.id] : ids.filter(id => id !== source.id));
          }}>
            <summary>{source.title || "Quelle ohne Titel"}</summary>
            {source.working_kinds?.length ? <small>Quelle berichtet · automatisch sortiert · {source.working_kinds.map(kind => WORKING_KIND_LABELS[kind]).filter(Boolean).join(", ")}</small>
              : <small>{source.reason} · Rohmaterial, keine bestätigte Aussage</small>}
            <small>Aufgenommen: {new Date(source.recorded_at).toLocaleString("de-DE")}</small>
            {source.participants.length > 0 && <small>In dieser Quelle genannt: {source.participants.join(", ")}</small>}
            <Herkunft provenance={source.provenance} klein />
            <p className="calendar-source-body">{source.body}</p>
            {source.truncated && <p>Auszug: Die Quelle ist länger als die hier angezeigten 20.000 Zeichen.</p>}
            {source.working_kinds?.length ? <ProfileSource key={`${source.id}:${source.body}`} kind="episode" id={source.id} label="Quelle ansehen" allowDismiss onChange={change => {if (change === "correction") setCorrectionSaved(true); setSourceRevision(value => value + 1);}} /> : null}
          </details>)}
        </PreparationSection>
        {preparation.sources_more && <p>Es gibt weitere Quellen. Angezeigt werden bis zu 100 Quellen, Belege zuerst.</p>}
        {preparation.working_memory_more && <p>Nicht alle Quellen dieser Auswahl sind automatisch sortiert oder in diesem begrenzten Überblick enthalten.</p>}
        {preparation.project && <PreparationSection title="Arbeitsnotizen" empty="Keine Arbeitsnotizen.">
          {preparation.notes.map(note => <div className="calendar-preparation-item" key={note.id}><strong>{note.title}</strong><span>{note.body}</span></div>)}
        </PreparationSection>}
      </div>}
    </div>}
  </section>;
}

function PreparationSection({ title, empty, children }: { title: string; empty: string; children: ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return <section className="calendar-preparation-section"><h3>{title}</h3>{hasChildren ? <div className="calendar-preparation-items">{children}</div> : <p>{empty}</p>}</section>;
}
