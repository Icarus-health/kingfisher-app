import { useEffect, useRef, useState } from "react";
import { api, type CalendarOverview } from "./api";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";
import { CalendarPreparation } from "./CalendarPreparation";
import { CalendarActionForm } from "./CalendarActionForm";
import { editableEventId } from "./calendarActionState";
import { CalendarFollowup } from "./CalendarFollowup";
import { calendarWindow, eventsInRange, findCalendarEvent, preparationView } from "./calendarRange";

type View = "Liste" | "Woche" | "Monat" | "Jahr";
const dateKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const midnight = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const plusDays = (d: Date, days: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);
const validDate = (value: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed : null;
};
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
  const initialParams = new URLSearchParams(window.location.search);
  const initialPrepareAt = validDate(initialParams.get("prepare_at"));
  const [view, setView] = useState<View>(() => { const saved = localStorage.getItem("kingfisher-calendar-view"); const selected: View = ["Liste", "Woche", "Monat", "Jahr"].includes(saved || "") ? saved as View : "Monat"; return preparationView(selected, initialPrepareAt, today); });
  const [focus, setFocus] = useState(midnight(initialPrepareAt || today));
  const [googleSources, setGoogleSources] = useState<string[]>([]);
  const [actionTarget, setActionTarget] = useState<CalendarOverview["items"][number] | "new" | null>(null);
  const [data, setData] = useState<CalendarOverview | null>(null);
  const [loadedRangeKey, setLoadedRangeKey] = useState("");
  const [legacyPreparation, setLegacyPreparation] = useState<CalendarOverview["items"][number] | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [loadedRevision, setLoadedRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [preparationUid, setPreparationUid] = useState<string | null>(() => initialParams.get("prepare"));
  const [preparationAt, setPreparationAt] = useState<string | null>(() => initialParams.get('prepare_at'));
  const [followup, setFollowup] = useState<string | null>(() => initialParams.get("nachbereiten"));
  const preparationPanel = useRef<HTMLDivElement>(null);
  const followupPanel = useRef<HTMLDivElement>(null);
  // Vorbereiten und Nachbereiten schließen einander aus: ein Fenster, ein Termin.
  function select(prepare: string | null, nachbereiten: string | null, prepareAt?: string | null) {
    setPreparationUid(prepare);
    setPreparationAt(prepareAt ?? null);
    setFollowup(nachbereiten);
    if (!prepare) setLegacyPreparation(null);
    const url = new URL(window.location.href);
    if (prepare) {
      url.searchParams.set("prepare", prepare);
      if (prepareAt) url.searchParams.set("prepare_at", prepareAt); else url.searchParams.delete("prepare_at");
    } else {
      url.searchParams.delete("prepare");
      url.searchParams.delete("prepare_at");
    }
    if (nachbereiten) url.searchParams.set("nachbereiten", nachbereiten); else url.searchParams.delete("nachbereiten");
    window.history.replaceState(window.history.state, "", url);
  }
  const visibleWindow = calendarWindow(focus, view, today);
  const rangeKey = `${visibleWindow.from.toISOString()}|${visibleWindow.until.toISOString()}`;
  const visibleData = loadedRangeKey === rangeKey ? data : null;
  const selectPreparation = (uid: string | null, start?: string | null) => {
    const event = uid ? findCalendarEvent(visibleData?.items ?? [], uid, start) : null;
    if (event) setLegacyPreparation(event);
    select(uid, null, event?.start);
  };
  const followupTarget = splitFollowup(followup);
  useEffect(() => {
    if (followupTarget) followupPanel.current?.scrollIntoView({block: "start"});
  }, [followup]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const sync = () => {
      const params = new URLSearchParams(window.location.search);
      setPreparationUid(params.get("prepare")); setFollowup(params.get("nachbereiten"));
      setPreparationAt(params.get('prepare_at'));
      const at = validDate(params.get("prepare_at"));
      if (at) {setFocus(midnight(at)); setView(old => preparationView(old, at, new Date()));}
    };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  useEffect(() => {
    let active = true;
    api.calendarActionSources().then(result => {if (active) setGoogleSources(result.sources.map(s => s.id));}).catch(() => {});
    return () => {active = false;};
  }, []);
  useEffect(() => { localStorage.setItem("kingfisher-calendar-view", view); }, [view]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    api.calendar(visibleWindow.from.toISOString(), visibleWindow.until.toISOString())
      .then(next => { if (active) { setData(next); setLoadedRangeKey(rangeKey); setLoadedRevision(revision); } })
      .catch(() => { if (active) setError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision, rangeKey]);
  useEffect(() => {
    if (!preparationUid || validDate(preparationAt)) return;
    let active = true;
    // Older shared links contain only the event UID. The no-argument API keeps
    // its annual compatibility window so this one-time lookup can find it.
    api.calendar().then(result => {
      if (!active) return;
      const event = findCalendarEvent(result.items, preparationUid);
      if (!event) return;
      setLegacyPreparation(event);
      if (event.start) {
        const start = new Date(event.start);
        if (Number.isFinite(start.getTime())) {
          if (dateKey(start) !== dateKey(focus)) setFocus(midnight(start));
          setView(old => preparationView(old, start, new Date()));
          const url = new URL(window.location.href);
          url.searchParams.set("prepare_at", event.start);
          window.history.replaceState(window.history.state, "", url);
          setPreparationAt(event.start);
        }
      }
    }).catch(() => { /* The normal range request reports its own error. */ });
    return () => { active = false; };
  // Only legacy links need this lookup; a dated link goes straight to its range.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preparationUid, preparationAt]);
  useEffect(() => {
    const timer = window.setInterval(() => setRevision(value => value + 1), 15000);
    return () => window.clearInterval(timer);
  }, []);
  const items = visibleData?.items || [];
  const onDay = (day: Date) => eventsInRange(items, midnight(day), plusDays(day, 1));
  const weekStart = plusDays(focus, -(focus.getDay() + 6) % 7);
  const time = (value: string) => new Date(value).toLocaleTimeString("de-DE", {hour:"2-digit", minute:"2-digit"});
  function grid(month: number, small = false, gridYear = focus.getFullYear()) {
    const first = new Date(gridYear, month, 1), offset = (first.getDay() + 6) % 7;
    const count = new Date(gridYear, month + 1, 0).getDate();
    return <div className={`month-grid ${small ? "mini-month" : ""}`}>
      {["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => <span className="weekday" key={d}>{d}</span>)}
      {Array.from({length: offset}, (_, i) => <span key={`blank-${i}`} />)}
      {Array.from({length: count}, (_, i) => {
        const day = new Date(gridYear, month, i + 1), events = onDay(day);
        return <button key={i} className={`month-day ${dateKey(day) === dateKey(today) ? "is-today" : ""} ${dateKey(day) === dateKey(focus) ? "is-selected" : ""}`} aria-label={`${day.toLocaleDateString("de-DE")}, ${events.length} Termine`} aria-pressed={dateKey(day) === dateKey(focus)} onClick={() => {setFocus(day); if (small) setView("Monat");}}>
          <strong>{i + 1}</strong>{small ? events.length > 0 && <span className="event-dot" /> : <>{events.slice(0, 2).map(e => <span className="day-event" key={`${e.uid}|${e.start}`}>{e.all_day ? "" : e.start ? `${time(e.start)} ` : ""}{e.summary}</span>)}{events.length > 2 && <small>+{events.length - 2} weitere</small>}</>}
        </button>;
      })}
    </div>;
  }
  const shown = view === "Liste" ? eventsInRange(items, midnight(today), plusDays(today, 7)) : onDay(focus);
  function shift(direction: number) {
    const next = view === "Woche" ? plusDays(focus, direction * 7)
      : view === "Jahr" ? new Date(focus.getFullYear() + direction, 0, 1)
        : new Date(focus.getFullYear(), focus.getMonth() + direction, 1);
    setFocus(next);
  }
  const selectedAt = validDate(preparationAt);
  const selectedInRange = selectedAt && selectedAt >= visibleWindow.from && selectedAt < visibleWindow.until;
  const preparationEvent = preparationUid ? findCalendarEvent(visibleData?.items ?? [], preparationUid, preparationAt)
    || (!(visibleData && selectedInRange) ? findCalendarEvent(legacyPreparation ? [legacyPreparation] : [], preparationUid, preparationAt) : null) : null;
  useEffect(() => {
    if (preparationEvent?.start) {
      const start = new Date(preparationEvent.start);
      if (!Number.isNaN(start.getTime()) && dateKey(start) !== dateKey(focus)) setFocus(midnight(start));
    }
    preparationPanel.current?.scrollIntoView({block: "start"});
  }, [preparationEvent?.uid, preparationEvent?.start]);
  return <div className="shell tasks-shell"><Sidebar active="Kalender" recentConversation={recentConversation} />
    <main className="tasks-page calendar-page">
      <header className="settings-heading"><p className="eyebrow">DEINE ZEIT</p><h1>Kalender</h1><p>{focus.getFullYear()} · Zeiten auf diesem Gerät</p></header>
      <section className="calendar-board" aria-label="Kalenderübersicht">
      <div className="calendar-actions"><div role="group" aria-label="Kalenderansicht" className="view-switch">{(["Liste", "Woche", "Monat", "Jahr"] as View[]).map(v => <button key={v} aria-pressed={v === view} onClick={() => setView(v)}>{v}</button>)}</div><button className="secondary-action" disabled={loading} onClick={() => setRevision(value => value + 1)}>{loading ? "Wird geladen …" : "Ansicht aktualisieren"}</button><button className="secondary-action" onClick={() => setActionTarget("new")}>Termin anlegen</button><button className="secondary-action" onClick={() => navigate("/settings#zugaenge")}>Kalender verwalten</button></div>
      {error && <p role="alert">Termine konnten nicht geladen werden. Bitte erneut versuchen.</p>}
      {loading && <p role="status">Kalenderzeitraum wird geladen …</p>}
      {visibleData?.errors.map((message, index) => <p className="settings-error" role="alert" key={index}>{message}</p>)}
      {visibleData && !visibleData.configured && <p>Noch kein Kalender verbunden. Wähle unter „Kalender verwalten“ deine Quellen aus.</p>}
      {visibleData?.configured && !loading && visibleData.items.length === 0 && visibleData.errors.length === 0 && <p role="status">Keine Termine in diesem Zeitraum.</p>}
      {(view === "Monat" || view === "Woche" || view === "Jahr") && <div className="calendar-period"><button aria-label="Vorheriger Zeitraum" onClick={() => shift(-1)}>←</button><h2>{view === "Monat" ? focus.toLocaleDateString("de-DE", {month:"long", year:"numeric"}) : view === "Jahr" ? `${focus.getFullYear()}` : `${weekStart.toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric"})} – ${plusDays(weekStart, 6).toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric"})}`}</h2><button aria-label="Nächster Zeitraum" onClick={() => shift(1)}>→</button><button onClick={() => setFocus(midnight(today))}>Heute</button></div>}
      {view === "Monat" && grid(focus.getMonth())}
      {view === "Jahr" && <div className="year-grid">{Array.from({length: 12}, (_, month) => <section key={month}><h2>{new Date(focus.getFullYear(), month, 1).toLocaleDateString("de-DE", {month:"long"})}</h2>{grid(month, true, focus.getFullYear())}</section>)}</div>}
      {view === "Woche" && <div className="week-grid">{Array.from({length:7}, (_,i) => {const day=plusDays(weekStart,i);return <section key={i}><button className="week-date" onClick={() => setFocus(day)}>{day.toLocaleDateString("de-DE",{weekday:"short",day:"2-digit",month:"2-digit"})}</button>{onDay(day).map(e=><div className="week-event" key={`${e.uid}|${e.start}`}><small>{e.all_day ? "Ganztägig" : e.start ? time(e.start) : ""}</small><strong>{e.summary}</strong></div>)}</section>;})}</div>}
      {view !== "Jahr" && <><h2 className="agenda-heading">{view === "Liste" ? "Nächste sieben Tage" : focus.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long"})}</h2>
        <div className="calendar-list">{shown.map(item => <article className="calendar-entry" key={`${item.uid}|${item.start}`}><div>{item.start && <><strong>{new Date(item.start).toLocaleDateString("de-DE", {weekday:"short", day:"2-digit", month:"short"})}</strong><p>{item.all_day ? "Ganztägig" : `${time(item.start)}${item.end ? ` – ${time(item.end)}` : ""}`}</p></>}</div><div><h2>{item.summary}</h2>{item.location && <p>{item.location}</p>}<small>{item.source_label || "Verbundener Kalender"}</small>{item.source_id && googleSources.includes(item.source_id) && editableEventId(item) && <button type="button" className="secondary-action calendar-prepare-button" onClick={() => setActionTarget(item)}>Bearbeiten / absagen</button>}{item.art !== "geburtstag" && (!item.end || new Date(item.end) > new Date()) && <button className="secondary-action calendar-prepare-button" type="button" onClick={() => selectPreparation(item.uid, item.start)}>Vorbereiten</button>}{!item.all_day && item.start && new Date(item.start) <= new Date() && <button className="secondary-action calendar-prepare-button" type="button" onClick={() => select(null, followupKey(item.uid, item.start!))}>Nachbereiten</button>}</div></article>)}</div>
      </>}
      </section>
      {actionTarget && <CalendarActionForm key={actionTarget === "new" ? "new" : `${actionTarget.uid}|${actionTarget.start}`} event={actionTarget === "new" ? undefined : actionTarget} onClose={() => setActionTarget(null)} onDone={() => setRevision(n => n + 1)} />}
      {preparationEvent && <div ref={preparationPanel}><CalendarPreparation key={preparationEvent.uid} event={preparationEvent} revision={loadedRevision} onClose={() => selectPreparation(null)} /></div>}
      {followupTarget && <div ref={followupPanel}><CalendarFollowup key={followup!} uid={followupTarget.uid} start={followupTarget.start} onClose={() => select(null, null)} /></div>}
      {preparationUid && visibleData && !loading && !error && !preparationEvent && <p role="status">Der ausgewählte Termin ist in den aktuell geladenen Kalendern nicht verfügbar. <button className="text-action" onClick={() => selectPreparation(null)}>Auswahl schließen</button></p>}
    </main></div>;
}
