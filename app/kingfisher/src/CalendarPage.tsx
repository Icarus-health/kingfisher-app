import { useEffect, useRef, useState } from "react";
import { api, type CalendarOverview } from "./api";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";
import { CalendarPreparation } from "./CalendarPreparation";
import { CalendarFollowup } from "./CalendarFollowup";
import { eventsInRange } from "./calendarRange";

type View = "Liste" | "Woche" | "Monat" | "Jahr";
const dateKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const midnight = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const plusDays = (d: Date, days: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
// „uid|Beginn“: Eine Serie teilt sich die Kennung, erst der Beginn bestimmt den Termin.
// Der Beginn bleibt, wie der Kalender ihn liefert; über Date gerundet träfe er
// den Termin nicht mehr.
const followupKey = (uid: string, start: string) => `${uid}|${start}`;
function splitFollowup(key: string | null) {
  const cut = key ? key.lastIndexOf("|") : -1;
  return key && cut > 0 ? { uid: key.slice(0, cut), start: key.slice(cut + 1) } : null;
}

export function CalendarPage({ recentConversation }: {recentConversation: string | null}) {
  const today = new Date();
  const year = today.getFullYear();
  const [view, setView] = useState<View>(() => { const saved = localStorage.getItem("kingfisher-calendar-view"); return ["Liste", "Woche", "Monat", "Jahr"].includes(saved || "") ? saved as View : "Monat"; });
  const [focus, setFocus] = useState(midnight(today));
  const [data, setData] = useState<CalendarOverview | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [loadedRevision, setLoadedRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [preparationUid, setPreparationUid] = useState<string | null>(() => new URLSearchParams(window.location.search).get("prepare"));
  const [followup, setFollowup] = useState<string | null>(() => new URLSearchParams(window.location.search).get("nachbereiten"));
  const preparationPanel = useRef<HTMLDivElement>(null);
  const followupPanel = useRef<HTMLDivElement>(null);
  // Vorbereiten und Nachbereiten schließen einander aus: ein Fenster, ein Termin.
  function select(prepare: string | null, nachbereiten: string | null) {
    setPreparationUid(prepare);
    setFollowup(nachbereiten);
    const url = new URL(window.location.href);
    if (prepare) url.searchParams.set("prepare", prepare); else url.searchParams.delete("prepare");
    if (nachbereiten) url.searchParams.set("nachbereiten", nachbereiten); else url.searchParams.delete("nachbereiten");
    window.history.replaceState(window.history.state, "", url);
  }
  const selectPreparation = (uid: string | null) => select(uid, null);
  const followupTarget = splitFollowup(followup);
  useEffect(() => {
    if (followupTarget) followupPanel.current?.scrollIntoView({block: "start"});
  }, [followup]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const sync = () => { const params = new URLSearchParams(window.location.search); setPreparationUid(params.get("prepare")); setFollowup(params.get("nachbereiten")); };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  useEffect(() => { localStorage.setItem("kingfisher-calendar-view", view); }, [view]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    api.calendar().then(next => { if (active) { setData(next); setLoadedRevision(revision); } })
      .catch(() => { if (active) { setError(true); setData(null); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  useEffect(() => {
    const timer = window.setInterval(() => setRevision(value => value + 1), 15000);
    return () => window.clearInterval(timer);
  }, []);
  const items = data?.items || [];
  const onDay = (day: Date) => eventsInRange(items, midnight(day), plusDays(day, 1));
  const weekStart = plusDays(focus, -(focus.getDay() + 6) % 7);
  const time = (value: string) => new Date(value).toLocaleTimeString("de-DE", {hour:"2-digit", minute:"2-digit"});
  function grid(month: number, small = false) {
    const first = new Date(year, month, 1), offset = (first.getDay() + 6) % 7;
    const count = new Date(year, month + 1, 0).getDate();
    return <div className={`month-grid ${small ? "mini-month" : ""}`}>
      {["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => <span className="weekday" key={d}>{d}</span>)}
      {Array.from({length: offset}, (_, i) => <span key={`blank-${i}`} />)}
      {Array.from({length: count}, (_, i) => {
        const day = new Date(year, month, i + 1), events = onDay(day);
        return <button key={i} className={`month-day ${dateKey(day) === dateKey(today) ? "is-today" : ""} ${dateKey(day) === dateKey(focus) ? "is-selected" : ""}`} aria-label={`${day.toLocaleDateString("de-DE")}, ${events.length} Termine`} aria-pressed={dateKey(day) === dateKey(focus)} onClick={() => {setFocus(day); if (small) setView("Monat");}}>
          <strong>{i + 1}</strong>{small ? events.length > 0 && <span className="event-dot" /> : <>{events.slice(0, 2).map(e => <span className="day-event" key={e.uid}>{e.all_day ? "" : e.start ? `${time(e.start)} ` : ""}{e.summary}</span>)}{events.length > 2 && <small>+{events.length - 2} weitere</small>}</>}
        </button>;
      })}
    </div>;
  }
  const shown = view === "Liste" ? eventsInRange(items, midnight(today), plusDays(today, 7)) : onDay(focus);
  function shift(direction: number) {
    const next = view === "Woche" ? plusDays(focus, direction * 7) : new Date(year, focus.getMonth() + direction, 1);
    if (next.getFullYear() === year) setFocus(next);
  }
  const previous = view === "Woche" ? plusDays(focus, -7) : new Date(year, focus.getMonth() - 1, 1);
  const next = view === "Woche" ? plusDays(focus, 7) : new Date(year, focus.getMonth() + 1, 1);
  const preparationEvent = preparationUid && data ? data.items.find(item => item.uid === preparationUid) : null;
  useEffect(() => {
    if (preparationEvent?.start) {
      const start = new Date(preparationEvent.start);
      if (!Number.isNaN(start.getTime())) setFocus(midnight(start));
    }
    preparationPanel.current?.scrollIntoView({block: "start"});
  }, [preparationEvent?.uid, preparationEvent?.start]);
  return <div className="shell tasks-shell"><Sidebar active="Kalender" recentConversation={recentConversation} />
    <main className="tasks-page calendar-page">
      <header className="settings-heading"><p className="eyebrow">DEINE ZEIT</p><h1>Kalender</h1><p>{year} · Zeiten auf diesem Gerät</p></header>
      <section className="calendar-board" aria-label="Kalenderübersicht">
      <div className="calendar-actions"><div role="group" aria-label="Kalenderansicht" className="view-switch">{(["Liste", "Woche", "Monat", "Jahr"] as View[]).map(v => <button key={v} aria-pressed={v === view} onClick={() => setView(v)}>{v}</button>)}</div><button className="secondary-action" disabled={loading} onClick={() => setRevision(value => value + 1)}>{loading ? "Wird geladen …" : "Ansicht aktualisieren"}</button><button className="secondary-action" onClick={() => navigate("/settings#zugaenge")}>Kalender verwalten</button></div>
      {error && <p role="alert">Termine konnten nicht geladen werden. Bitte erneut versuchen.</p>}
      {data?.errors.map((message, index) => <p className="settings-error" role="alert" key={index}>{message}</p>)}
      {data && !data.configured && <p>Noch kein Kalender verbunden. Wähle unter „Kalender verwalten“ deine Quellen aus.</p>}
      {(view === "Monat" || view === "Woche") && <div className="calendar-period"><button aria-label="Vorheriger Zeitraum" disabled={previous.getFullYear() !== year} onClick={() => shift(-1)}>←</button><h2>{view === "Monat" ? focus.toLocaleDateString("de-DE", {month:"long", year:"numeric"}) : `${weekStart.toLocaleDateString("de-DE")} – ${plusDays(weekStart, 6).toLocaleDateString("de-DE")}`}</h2><button aria-label="Nächster Zeitraum" disabled={next.getFullYear() !== year} onClick={() => shift(1)}>→</button><button onClick={() => setFocus(midnight(today))}>Heute</button></div>}
      {view === "Monat" && grid(focus.getMonth())}
      {view === "Jahr" && <div className="year-grid">{Array.from({length: 12}, (_, month) => <section key={month}><h2>{new Date(year, month, 1).toLocaleDateString("de-DE", {month:"long"})}</h2>{grid(month, true)}</section>)}</div>}
      {view === "Woche" && <div className="week-grid">{Array.from({length:7}, (_,i) => {const day=plusDays(weekStart,i);return <section key={i}><button className="week-date" onClick={() => setFocus(day)}>{day.toLocaleDateString("de-DE",{weekday:"short",day:"2-digit",month:"2-digit"})}</button>{onDay(day).map(e=><div className="week-event" key={e.uid}><small>{e.all_day ? "Ganztägig" : e.start ? time(e.start) : ""}</small><strong>{e.summary}</strong></div>)}</section>;})}</div>}
      {view !== "Jahr" && <><h2 className="agenda-heading">{view === "Liste" ? "Nächste sieben Tage" : focus.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long"})}</h2>
        {data && !loading && shown.length === 0 && data.errors.length === 0 && <p>Keine Termine für diesen Zeitraum geladen.</p>}
        <div className="calendar-list">{shown.map(item => <article className="calendar-entry" key={item.uid}><div>{item.start && <><strong>{new Date(item.start).toLocaleDateString("de-DE", {weekday:"short", day:"2-digit", month:"short"})}</strong><p>{item.all_day ? "Ganztägig" : `${time(item.start)}${item.end ? ` – ${time(item.end)}` : ""}`}</p></>}</div><div><h2>{item.summary}</h2>{item.location && <p>{item.location}</p>}<small>{item.source_label || "Verbundener Kalender"}</small>{item.art !== "geburtstag" && (!item.end || new Date(item.end) > new Date()) && <button className="secondary-action calendar-prepare-button" type="button" onClick={() => selectPreparation(item.uid)}>Vorbereiten</button>}{!item.all_day && item.start && new Date(item.start) <= new Date() && <button className="secondary-action calendar-prepare-button" type="button" onClick={() => select(null, followupKey(item.uid, item.start!))}>Nachbereiten</button>}</div></article>)}</div>
      </>}
      </section>
      {preparationEvent && <div ref={preparationPanel}><CalendarPreparation key={preparationEvent.uid} event={preparationEvent} revision={loadedRevision} onClose={() => selectPreparation(null)} /></div>}
      {followupTarget && <div ref={followupPanel}><CalendarFollowup key={followup!} uid={followupTarget.uid} start={followupTarget.start} onClose={() => select(null, null)} /></div>}
      {preparationUid && data && !loading && !error && !preparationEvent && <p role="status">Der ausgewählte Termin ist in den aktuell geladenen Kalendern nicht verfügbar. <button className="text-action" onClick={() => selectPreparation(null)}>Auswahl schließen</button></p>}
    </main></div>;
}
