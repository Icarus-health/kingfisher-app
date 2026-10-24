import "./TodayOverview.css";
import {useState} from "react";
import { TodayTaskActions } from "./TodayTaskActions";
import { taskHref } from "./taskWorkflow";
import { eingangZeile, naechsterTerminText, zaehlerText } from "./heute";
import { type Attention, type MorningBriefing } from "./api";
import { BriefingSuggestion } from "./BriefingSuggestion";
import { AkteVorschlagKnoepfe } from "./AkteVorschlagKnoepfe";
import { ProfileSource } from "./ProfileSource";
import { TagesLage } from "./TagesLage";
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
  return ({ nachbereitung: "Nach dem Termin", termin: "Termin", aufgabe: "Aufgabe", wartet: "Wartet auf Antwort", entscheidung: "Entscheidung", zusage: "Vorschlag aus einer Quelle", akte_vorschlag: "Neue Akte?" } as Record<string, string>)[item.source ?? ""] ?? "Offener Punkt";
}

/** Der ruhige Fuß von Heute: die übrigen Bereiche als Zeilen einer Fläche, ohne eigene Überschrift (H6, H13). */
export function TodayPersonal() {
  return <nav className="g-gruppe today-personal" aria-label="Weitere Bereiche">
    <div className="g-flaeche">
      <a className="g-zeile" href="/development"><span className="g-zeile-text"><span className="g-zeile-titel">Ziele, Gewohnheiten & Lernen</span></span><span className="g-zeile-pfeil" aria-hidden="true" /></a>
      <a className="g-zeile" href="/world"><span className="g-zeile-text"><span className="g-zeile-titel">Öffentliches Wissen & Quellen</span></span><span className="g-zeile-pfeil" aria-hidden="true" /></a>
      <a className="g-zeile" href="/wellbeing"><span className="g-zeile-text"><span className="g-zeile-titel">Gesundheit</span></span><span className="g-zeile-pfeil" aria-hidden="true" /></a>
      <a className="g-zeile" href="/review"><span className="g-zeile-text"><span className="g-zeile-titel">Gedächtnis prüfen</span></span><span className="g-zeile-pfeil" aria-hidden="true" /></a>
    </div>
  </nav>;
}

export function TodayOverview({ briefing, onChange, taskNotice, onTaskDone, correctionSaved, onOpenMail }: {
  briefing: MorningBriefing;
  onChange: (change?: "correction") => void;
  taskNotice: string;
  onTaskDone: (message: string) => void;
  correctionSaved: boolean;
  onOpenMail: (uid: string) => void;
}) {
  const [activityLoaded,setActivityLoaded] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  // Die Antwort auf „Akte anlegen“ oder „Nein danke“ bleibt stehen, wenn der Punkt danach aus dem Briefing geht.
  const [akteNotice, setAkteNotice] = useState<{ satz: string; link: string } | null>(null);
  const attention = todayAttention(briefing);
  const calendarUnavailable = briefing.partial_failures.some(failure => failure.section === "calendar");
  const reviewStatus = briefing.partial_failures.find(failure => failure.section === "source_review");
  const naechster = naechsterTerminText(briefing.naechster_termin, briefing.timezone);
  function toggleActivity() {
    // Erst beim ersten Öffnen gelesen (die Tageslage setzt die Marke „seit dem letzten Blick“); danach bleibt sie
    // eingehängt, damit Entwürfe darin das Zuklappen überstehen.
    setActivityLoaded(true);
    setActivityOpen(open => !open);
  }
  // Große, ruhige Flächen (P1): je Bereich ein Titel über einer weißen Fläche mit Zeilen. Bilder nur im Seitenkopf, die
  // Zahl leise neben der Überschrift, leere Bereiche in einem Satz (Paket U, H2 und H8).
  return <div className="today-overview">
    <section className="today-panel today-attention" aria-labelledby="today-attention-title">
      <header className="today-panel-heading"><h2 id="today-attention-title">Braucht dich</h2>{zaehlerText(attention.length) ? <span className="today-count">{zaehlerText(attention.length)}</span> : null}</header>
      <div className="today-flaeche">
      {reviewStatus && <p className="today-notice" role="status">{reviewStatus.message} <a href="/vorhaben?view=mine">Aufgaben prüfen →</a></p>}
      {attention.length ? <ul className="today-attention-list">{attention.map(item => {
        const action = actionFor(item);
        return <li className="today-attention-item" key={item.id}>
          <div className="today-item-text">
            <h3>{item.title}</h3>
            <p className="today-item-meta"><span>{kindLabel(item)}</span>{item.priority && <span>{item.priority}</span>}</p>
            {(item.action === 'Verlauf prüfen' || item.review_required) && <span className="today-review-badge">{item.action === 'Verlauf prüfen' ? 'Verlauf ungeprüft' : 'Original prüfen'}</span>}
          </div>
          <div className="today-item-actions">
            {item.source === "zusage" ? <BriefingSuggestion item={item} onDone={onTaskDone} /> : item.source === "akte_vorschlag" ? <AkteVorschlagKnoepfe key={item.source_ref ?? item.id} item={item} onDone={antwort => { setAkteNotice(antwort); onChange(); }} /> : (item.source === "aufgabe" || item.source === "wartet") && item.source_ref ? <TodayTaskActions key={item.source_ref} item={item} onChanged={onChange} /> : action ? <a className="today-action" href={action.href}>{action.label}</a> : null}
          </div>
          {item.source !== 'aufgabe' && item.source !== 'wartet' && (item.reason || item.detail) && <details className="quiet-details today-hintergrund"><summary>Hintergrund</summary><p>{item.reason && item.reason !== item.title ? item.reason : item.detail}</p></details>}
        </li>;
      })}</ul> : <p className="today-empty">{briefing.partial_failures.length ? "Gerade ist nichts Offenes zu sehen." : "Nichts wartet auf dich."}</p>}
      {taskNotice && <p className="today-notice" role="status">{taskNotice} <a href="/vorhaben?view=mine">Aufgaben ansehen</a></p>}
      {akteNotice && <p className="today-notice" role="status">{akteNotice.satz} <a href={akteNotice.link}>Akte öffnen</a></p>}
      </div>
    </section>

    <div className="today-side">
    <section className="today-panel today-calendar" aria-labelledby="today-calendar-title">
      <header className="today-panel-heading"><h2 id="today-calendar-title">Deine Termine</h2><a className="today-text-link today-calendar-open" href="/calendar">Kalender</a></header>
      <div className="today-flaeche">
      {/* Die Vorbereitung steht am Termin selbst; die ganze Zeile führt dorthin (H1). */}
      {briefing.later_today.length ? <ul className="today-calendar-list">{briefing.later_today.map(item => {
        const matching = briefing.needs_you.filter(note => note.source === "termin" && note.source_ref && note.source_ref === item.source_ref);
        const preparation = matching.length === 1 && briefing.later_today.filter(event => event.source_ref === item.source_ref).length === 1 ? matching[0] : undefined;
        const neben = preparation?.reason || item.detail;
        const inhalt = <><time>{item.time}</time><span className="g-zeile-text"><span className="g-zeile-titel">{item.title}</span>{neben ? <span className="g-zeile-neben">{neben}</span> : null}</span></>;
        return <li key={item.id}>{item.source_ref
          ? <a className="g-zeile today-termin" href={`/calendar?prepare=${encodeURIComponent(item.source_ref)}`} title="Vorbereitung öffnen">{inhalt}<span className="g-zeile-pfeil" aria-hidden="true" /></a>
          : <div className="g-zeile today-termin">{inhalt}</div>}</li>;
      })}</ul> : calendarUnavailable ? <p className="today-empty">Termine fehlen, der Kalender ist nicht lesbar. <a className="today-text-link" href="/settings#zugaenge">Kalender prüfen</a></p>
        : <p className="today-empty">Heute keine Termine.{naechster ? <> <span className="today-next-event">Nächster: {naechster}</span></> : null}</p>}
      </div>
    </section>

    {briefing.happening_now.length > 0 && <section className="today-panel today-news" aria-labelledby="today-news-title">
      <header className="today-panel-heading"><h2 id="today-news-title">Neu eingegangen</h2>{briefing.working_memory_more ? <a className="today-text-link" href="/memory">Mehr</a> : null}</header>
      <div className="today-flaeche">
      <ul className="today-news-list">{briefing.happening_now.map(item => {
        const {zeile, titel} = eingangZeile(item, briefing.timezone, briefing.generated_at);
        const text = <span className="g-zeile-text"><span className="g-zeile-titel">{item.title}</span>{zeile ? <span className="g-zeile-neben" title={titel}>{zeile}</span> : null}</span>;
        // Eine Mail ist ein Klick auf die ganze Zeile; eine Quelle aus dem Gedächtnis öffnet sich unter ihr.
        return <li className="today-source" key={item.id}>
          {activityAction(item) ? <button className="g-zeile" type="button" aria-label={`Nachricht öffnen: ${item.title}`} onClick={() => onOpenMail(item.source_ref!)}>{text}<span className="g-zeile-pfeil" aria-hidden="true" /></button>
            : <div className="g-zeile">{text}</div>}
          {item.source === "working_memory" && item.source_ref ? <ProfileSource kind="episode" id={item.source_ref} label="Quelle ansehen" allowDismiss quiet onChange={onChange} /> : null}
        </li>;
      })}</ul>
      </div>
    </section>}
    </div>

    <div className="today-followups">
      <TaskReminders compact onChanged={onChange} />
      <div id="memory-questions">
        <KnowledgeQuestions active compact onChanged={onChange} />
        <MemoryQuestions active compact onOpenAll={() => navigate('/review')} />
      </div>
    </div>

    {correctionSaved && <p className="today-notice today-correction" role="status">Berichtigung gespeichert. Die frühere Angabe wird nicht mehr verwendet. Frage erneut nach dem aktuellen Stand.</p>}
    {/* Tageslage als ruhige Zeile statt Dreieck (P1); sie wird erst beim Öffnen gelesen. */}
    <section className="g-gruppe today-activity" aria-label="Tageslage und Verlauf">
      <div className="g-flaeche">
        <button className="g-zeile today-activity-zeile" type="button" aria-expanded={activityOpen} aria-controls="today-activity-inhalt" onClick={toggleActivity}>
          <span className="g-zeile-text"><span className="g-zeile-titel">Tageslage & Verlauf</span></span><span className="g-zeile-pfeil" aria-hidden="true" />
        </button>
        {activityLoaded && <div className="today-activity-inhalt" id="today-activity-inhalt" hidden={!activityOpen}><TagesLage sourcesIncomplete={briefing.partial_failures.length > 0 || Boolean(briefing.post_ausstehend)} /></div>}
      </div>
    </section>
  </div>;
}
