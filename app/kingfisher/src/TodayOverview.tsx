import "./TodayOverview.css";
import { TodayTaskActions } from "./TodayTaskActions";
import { taskHref } from "./taskWorkflow";
import { zaehlerText } from "./heute";
import { type Attention, type MorningBriefing } from "./api";
import { BriefingSuggestion } from "./BriefingSuggestion";
import { ProfileSource } from "./ProfileSource";
import { TagesLage } from "./TagesLage";
import { ASSET } from "./ui";
import { activityAction } from "./dailyFlow";
import { MemoryQuestions } from "./MemoryQuestions";
import { KnowledgeQuestions } from "./KnowledgeQuestions";
import { TaskReminders } from "./TaskReminders";
import { navigate } from "./ui";

// A calendar reminder already shown with its preparation belongs with the
// day's appointments. Keep unmatched reminders visible in the attention list.
export function todayAttention(briefing: MorningBriefing) {
  return briefing.needs_you.filter(item => !(item.source === "termin" && item.source_ref
    && briefing.later_today.filter(event => event.source_ref === item.source_ref).length === 1
    && briefing.needs_you.filter(note => note.source === "termin" && note.source_ref === item.source_ref).length === 1));
}

function actionFor(item: Attention) {
  const project = item.project_id ? `&project=${encodeURIComponent(item.project_id)}` : "";
  if (item.source === "nachbereitung" && item.source_ref) return { label: "Ergebnis festhalten", href: `/calendar?nachbereiten=${encodeURIComponent(item.source_ref)}` };
  if (item.source === "termin" && item.source_ref) return { label: "Termin vorbereiten", href: `/calendar?prepare=${encodeURIComponent(item.source_ref)}` };
  if (item.source === "aufgabe") return { label: "Aufgabe ansehen", href: item.source_ref ? taskHref({id: item.source_ref, project_id: item.project_id}) : `/vorhaben?view=mine${project}` };
  if (item.source === "wartet") return { label: "Offenen Punkt ansehen", href: item.source_ref ? taskHref({id: item.source_ref, wartet_auf: "waiting", project_id: item.project_id}) : `/vorhaben?view=waiting${project}` };
  if (item.source === "entscheidung") return { label: "Entscheidung ansehen", href: `/vorhaben?view=decisions${project}` };
  if (item.source === "knowledge") return {label: "Angaben prüfen", href: "#memory-questions"};
  return null;
}

function kindLabel(item: Attention) {
  return ({ nachbereitung: "Nach dem Termin", termin: "Termin", aufgabe: "Aufgabe", wartet: "Wartet auf Antwort", entscheidung: "Entscheidung", zusage: "Vorschlag aus einer Quelle" } as Record<string, string>)[item.source ?? ""] ?? "Offener Punkt";
}

function activityTimestamp(value: string | null | undefined, timezone: string) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  try { return new Intl.DateTimeFormat("de-DE", {dateStyle: "medium", timeStyle: "short", timeZone: timezone}).format(date); }
  catch { return date.toLocaleString("de-DE"); }
}

function activityDates(item: Attention, timezone: string) {
  const occurred = activityTimestamp(item.occurred_at, timezone);
  const recorded = activityTimestamp(item.recorded_at, timezone);
  const sameMoment = item.occurred_at && item.recorded_at
    && new Date(item.occurred_at).getTime() === new Date(item.recorded_at).getTime();
  return <p>Quelldatum: {occurred ?? "unbekannt"}{recorded && !sameMoment ? <> · Erfasst: {recorded}</> : null}</p>;
}

export function TodayPersonal() {
  return <section className="today-panel today-personal" aria-labelledby="today-personal-title">
      <header className="today-panel-heading"><h2 id="today-personal-title">Für dich</h2></header>
      <nav className="development-links" aria-label="Persönlicher Arbeitsbereich">
        <a className="today-text-link" href="/development">Ziele, Gewohnheiten & Lernen →</a>
        <a className="today-text-link" href="/memory?area=health">Gesundheit →</a>
        <a className="today-text-link" href="/review">Gedächtnis prüfen →</a>
      </nav>
    </section>;
}

export function TodayOverview({ briefing, onChange, taskNotice, onTaskDone, correctionSaved, onOpenMail }: {
  briefing: MorningBriefing;
  onChange: (change?: "correction") => void;
  taskNotice: string;
  onTaskDone: (message: string) => void;
  correctionSaved: boolean;
  onOpenMail: (uid: string) => void;
}) {
  const attention = todayAttention(briefing);
  const calendarUnavailable = briefing.partial_failures.some(failure => failure.section === "calendar");
  return <div className="today-overview">
    <TagesLage sourcesIncomplete={briefing.partial_failures.length > 0 || Boolean(briefing.post_ausstehend)} />
    <section className="today-panel today-attention" aria-labelledby="today-attention-title">
      <header className="today-panel-heading"><h2 id="today-attention-title">Braucht dich</h2><img className="today-flight" src={`${ASSET.media}kingfisher-flight-clean-v1.png`} alt="" />{zaehlerText(attention.length) ? <span className="today-count">{zaehlerText(attention.length)}</span> : null}</header>
      {attention.length ? <ul className="today-attention-list">{attention.map(item => {
        const action = actionFor(item);
        return <li className="today-attention-item" key={item.id}>
          <div className="today-item-meta"><span>{kindLabel(item)}</span>{item.priority && <span>{item.priority}</span>}</div>
          <h3>{item.title}</h3><p>{item.reason && item.reason !== item.title ? item.reason : item.detail}</p>
          {item.source === "zusage" ? <BriefingSuggestion item={item} onDone={onTaskDone} /> : (item.source === "aufgabe" || item.source === "wartet") && item.source_ref ? <TodayTaskActions key={item.source_ref} item={item} onChanged={onChange} /> : action ? <a className="today-action" href={action.href}>{action.label}<span aria-hidden="true">→</span></a> : null}
        </li>;
      })}</ul> : <div className="today-empty"><h3>{briefing.partial_failures.length ? "Noch kein offener Punkt sichtbar." : "Gerade braucht dich nichts."}</h3><p>In den verfügbaren Quellen sind keine offenen Punkte für dich aufgeführt.</p></div>}
      {taskNotice && <p className="today-notice" role="status">{taskNotice} <a href="/vorhaben?view=mine">Aufgaben ansehen</a></p>}
    </section>

    <section className="today-panel today-calendar" aria-labelledby="today-calendar-title">
      <header className="today-panel-heading"><img className="today-calendar-scene" src={`${ASSET.media}calendar-lakeside-header-v1.png`} alt="" /><h2 id="today-calendar-title">Deine Termine</h2></header>
      {briefing.later_today.length ? <ul className="today-calendar-list">{briefing.later_today.map(item => {
        const matching = briefing.needs_you.filter(note => note.source === "termin" && note.source_ref && note.source_ref === item.source_ref);
        const preparation = matching.length === 1 && briefing.later_today.filter(event => event.source_ref === item.source_ref).length === 1 ? matching[0] : undefined;
        return <li key={item.id}><time>{item.time}</time><div><h3>{item.title}</h3>
          {(preparation?.reason || item.detail) && <p>{preparation?.reason || item.detail}</p>}
          {item.source_ref && <a className="today-text-link" href={`/calendar?prepare=${encodeURIComponent(item.source_ref)}`}>Vorbereitung öffnen <span aria-hidden="true">→</span></a>}
        </div></li>;
      })}</ul> : <div className="today-empty"><h3>{calendarUnavailable ? "Deine Termine fehlen noch." : "Keine weiteren Termine angezeigt."}</h3><p>{calendarUnavailable ? "Der Kalender konnte nicht gelesen werden. Das bedeutet nicht, dass du keine Termine hast." : "Heute sind keine weiteren Termine in diesem Überblick aufgeführt."}</p>{calendarUnavailable && <a className="today-text-link" href="/settings#zugaenge">Kalender verbinden oder prüfen →</a>}</div>}
      <a className="today-text-link today-calendar-open" href="/calendar">Kalender öffnen <span aria-hidden="true">→</span></a>
    </section>

    <div className="today-followups">
      <TaskReminders onChanged={onChange} />
      <div id="memory-questions">
        <h2>Deine Rückfragen</h2>
        <p>Prüfe widersprüchliche Angaben und wichtige Hinweise mit ihren Originalstellen. <a className="today-text-link" href="/review">Alle Rückfragen prüfen →</a></p>
        <KnowledgeQuestions active onChanged={onChange} />
        <MemoryQuestions active onOpenAll={() => navigate('/review')} />
      </div>
    </div>

    <section className="today-panel today-memory" aria-labelledby="today-memory-title">
      <header className="today-panel-heading"><h2 id="today-memory-title">Neu im Blick</h2><a className="today-text-link" href="/memory">Gedächtnis öffnen <span aria-hidden="true">→</span></a></header>
      {briefing.happening_now.length ? <div className="today-source-grid">{briefing.happening_now.map(item => <article className="today-source" key={item.id}>
        <div className="today-source-heading"><h3>{item.title}</h3><p>{item.detail}</p>{(item.source === "mail" || item.source === "working_memory") && activityDates(item, briefing.timezone)}</div>
        {activityAction(item) && <button className="today-text-link" type="button" onClick={() => onOpenMail(item.source_ref!)}>Nachricht öffnen →</button>}
        {item.source === "working_memory" && item.source_ref ? <ProfileSource kind="episode" id={item.source_ref} label="Quelle ansehen" allowDismiss onChange={onChange} /> : null}
      </article>)}</div> : <p className="today-notice">Gerade gibt es keine neuen Hinweise aus deinen Quellen.</p>}
      {briefing.working_memory_more && <p className="today-context-note">Dieser Überblick zeigt eine Auswahl. Weitere Quellen können noch aufs Sortieren warten.</p>}
      {correctionSaved && <p className="today-notice" role="status">Berichtigung gespeichert. Die frühere Angabe wird nicht mehr verwendet. Frage erneut nach dem aktuellen Stand.</p>}
    </section>
  </div>;
}
