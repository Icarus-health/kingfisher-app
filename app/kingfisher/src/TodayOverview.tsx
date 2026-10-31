import "./TodayOverview.css";
import { Zeile } from "./grundlage";
import {useState} from "react";
import { TodayTaskRow } from "./TodayTaskRow";
import { DetailPanel } from "./DetailPanel";
import { TaskDetail } from "./TaskDetail";
import { InterfaceIcon } from "./InterfaceIcon";
import { taskHref } from "./taskWorkflow";
import { eingangZeile, naechsterTerminText, zaehlerText } from "./heute";
import { type Attention, type MorningBriefing } from "./api";
import { BriefingSuggestion } from "./BriefingSuggestion";
import { AufgabenVonSelbstZeile } from "./AufgabenSelbstHeute";
import { AkteVorschlagKnoepfe } from "./AkteVorschlagKnoepfe";
import { NeueProjekte } from "./NeueProjekte";
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

/** Das leise Zeichen vor einem Punkt, der keine Aufgabe ist: dieselbe Spalte wie der Kreis einer Aufgabe (V1). */
function kindSymbol(item: Attention): Parameters<typeof InterfaceIcon>[0]["name"] {
  return ({ nachbereitung: "calendar-days", termin: "calendar-days", entscheidung: "check", zusage: "mail", akte_vorschlag: "project", knowledge: "brain" } as Record<string, Parameters<typeof InterfaceIcon>[0]["name"]>)[item.source ?? ""] ?? "document";
}

export function istAufgabe(item: Attention) {
  return (item.source === "aufgabe" || item.source === "wartet") && Boolean(item.source_ref);
}

function kindLabel(item: Attention) {
  return ({ nachbereitung: "Nach dem Termin", termin: "Termin", aufgabe: "Aufgabe", wartet: "Wartet auf Antwort", entscheidung: "Entscheidung", zusage: "Vorschlag aus einer Quelle", akte_vorschlag: "Neue Akte?" } as Record<string, string>)[item.source ?? ""] ?? "Offener Punkt";
}

/** Der ruhige Fuß von Heute: die übrigen Bereiche als Zeilen einer Fläche, ohne eigene Überschrift (H6, H13). */
export function TodayPersonal() {
  return <nav className="g-gruppe today-personal" aria-label="Weitere Bereiche">
    <div className="g-flaeche">
      <Zeile href="/development" titel="Ziele, Gewohnheiten & Lernen" />
      <Zeile href="/world" titel="Öffentliches Wissen & Quellen" />
      <Zeile href="/wellbeing" titel="Gesundheit" />
      <Zeile href="/review" titel="Gedächtnis prüfen" />
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
  // Eine Aufgabe unter „Braucht dich“ öffnet sich wie in der Liste im Seitenpaneel; erledigt antwortet der Hinweis unten
  // mit „Rückgängig“ (V4, TodayTaskRow).
  const [offeneAufgabe, setOffeneAufgabe] = useState<Attention | null>(null);
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
        // Aufgaben in derselben Zeile wie die Aufgabenliste (V1): Kreis, Titel, eine leise Zeile; die Zeile öffnet sie.
        if (istAufgabe(item)) return <li className="today-attention-task" key={item.id}>
          <TodayTaskRow key={item.source_ref} item={item} onOpen={() => setOffeneAufgabe(item)} onChanged={() => onChange()} />
        </li>;
        const action = actionFor(item);
        return <li className="today-attention-item" key={item.id}>
          <span className="today-item-symbol"><InterfaceIcon name={kindSymbol(item)} /></span>
          <div className="today-item-text">
            <h3>{item.title}</h3>
            <div className="today-item-zeile">
              <p className="today-item-meta"><span>{kindLabel(item)}</span>{item.priority && <span>{item.priority}</span>}{(item.action === 'Verlauf prüfen' || item.review_required) && <span className="today-review-badge">{item.action === 'Verlauf prüfen' ? 'Verlauf ungeprüft' : 'Original prüfen'}</span>}</p>
              {/* Der Hintergrund steht leise am Ende der Zeile, nicht in einer eigenen Zeile darunter (V1). */}
              {(item.reason || item.detail) && <details className="quiet-details today-hintergrund"><summary>Hintergrund</summary><p>{item.reason && item.reason !== item.title ? item.reason : item.detail}</p></details>}
            </div>
          </div>
          <div className="today-item-actions">
            {item.source === "zusage" ? <BriefingSuggestion item={item} onDone={onTaskDone} /> : item.source === "akte_vorschlag" ? <AkteVorschlagKnoepfe key={item.source_ref ?? item.id} item={item} onDone={() => onChange()} /> : action ? <a className="today-action" href={action.href}>{action.label}</a> : null}
          </div>
        </li>;
      })}</ul> : <p className="today-empty">{briefing.partial_failures.length ? "Gerade ist nichts Offenes zu sehen." : "Nichts wartet auf dich."}</p>}
      <NeueProjekte onChange={() => onChange()} />
      {taskNotice && <p className="today-notice" role="status">{taskNotice} <a href="/vorhaben?view=mine">Aufgaben ansehen</a></p>}
      <AufgabenVonSelbstZeile onChanged={() => onChange()} />
      </div>
      {offeneAufgabe?.source_ref && <DetailPanel title="Aufgabe" onClose={() => setOffeneAufgabe(null)}>
        <div className="today-aufgabe-offen">
          {/* Warum sie heute dasteht, und bei ungeprüftem Verlauf die weitere Nachricht: wie früher unter „Details“. */}
          {offeneAufgabe.reason && offeneAufgabe.reason !== offeneAufgabe.title && <p className="today-aufgabe-grund">{offeneAufgabe.reason}</p>}
          {offeneAufgabe.episode_id && <ProfileSource kind="episode" id={offeneAufgabe.episode_id} label="Weitere Nachricht im Verlauf ansehen" originalOnly />}
          <TaskDetail key={offeneAufgabe.source_ref} taskId={offeneAufgabe.source_ref} onChanged={onChange} />
          <a className="g-knopf-schlicht today-aufgabe-liste" href={taskHref({id: offeneAufgabe.source_ref, wartet_auf: offeneAufgabe.source === "wartet" ? "waiting" : null, project_id: offeneAufgabe.project_id})}>In Aufgaben öffnen</a>
        </div>
      </DetailPanel>}
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
        // Sammelzähler führen zu vorhandenen Prüfwegen. Unbekannte Arten erhalten kein geratenes Ziel.
        const href = item.source === "episodes" ? "/memory?view=status" : item.source === "proposals" ? "/review" : null;
        // Eine Mail ist ein Klick auf die ganze Zeile; eine Quelle aus dem Gedächtnis öffnet sich unter ihr.
        return <li className="today-source" key={item.id}>
          {activityAction(item) ? <button className="g-zeile" type="button" aria-label={`Nachricht öffnen: ${item.title}`} onClick={() => onOpenMail(item.source_ref!)}>{text}<span className="g-zeile-pfeil" aria-hidden="true" /></button>
            : href ? <a className="g-zeile" href={href}>{text}<span className="g-zeile-pfeil" aria-hidden="true" /></a>
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
