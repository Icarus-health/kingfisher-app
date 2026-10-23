import { useEffect, useRef, useState } from "react";
import { api, type CalendarOverview } from "./api";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";
import { CalendarPreparation } from "./CalendarPreparation";
import { CalendarActionForm } from "./CalendarActionForm";
import { editableEventId } from "./calendarActionState";
import { CalendarFollowup } from "./CalendarFollowup";
import { calendarSourceVersions, eventsInRange, findCalendarEvent, preparationView } from "./calendarRange";

import {calendarColor, calendarDayLayout, calendarDisplaySource, calendarEventKey, calendarPlacementKey, calendarVisibleEvents, calendarWorkspaceWindow, type WorkspaceCalendarView} from './calendarLayout';
import {DetailPanel} from './DetailPanel';
import {Leer, Seitenkopf, Segmente} from './grundlage';
import {ganztaegig, nachTagen, terminZeit} from './calendarAnzeige';
import './CalendarPage.css';
type View = WorkspaceCalendarView;
const ANSICHTEN: View[] = ["Tag", "Woche", "Monat", "Liste", "Jahr"];
// Schmal stehen im Monat nur Punkte; die Termine des gewählten Tages stehen gleich darunter (wie am iPhone).
const schmal = () => typeof window !== "undefined" && Boolean(window.matchMedia?.("(max-width: 700px)").matches);
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
  const [view, setView] = useState<View>(() => { let saved:string|null=null;try {saved=localStorage.getItem("kingfisher-calendar-view");} catch { /* The calendar remains usable without browser storage. */ } const selected: View = ["Tag", "Woche", "Monat", "Liste", "Jahr"].includes(saved || "") ? saved as View : "Monat"; return preparationView(selected, initialPrepareAt, today); });
  const [focus, setFocus] = useState(midnight(initialPrepareAt || today));
  const [googleSources, setGoogleSources] = useState<string[]>([]);
  const [configuredSources, setConfiguredSources] = useState<Array<{id:string;label:string}>>([]);
  const [macSources, setMacSources] = useState<Array<{id:string;label:string}>>([]);
  const [hiddenSources, setHiddenSources] = useState<Set<string>>(new Set());
  const [detailsKey, setDetailsKey] = useState<string|null>(null);
  const [agendaOpen, setAgendaOpen] = useState(schmal);
  const [navigatorOpen, setNavigatorOpen] = useState(() => window.matchMedia?.('(min-width: 701px)').matches ?? true);
  useEffect(() => {
    const media = window.matchMedia?.('(min-width: 701px)');
    if (!media) return;
    const resize = () => setNavigatorOpen(media.matches);
    media.addEventListener('change', resize);
    return () => media.removeEventListener('change', resize);
  }, []);
  useEffect(() => {
    const media = window.matchMedia?.('(max-width: 700px)');
    if (!media) return;
    const wechsel = () => {if (media.matches) setAgendaOpen(true);};
    media.addEventListener('change', wechsel);
    return () => media.removeEventListener('change', wechsel);
  }, []);
  const timeScroll = useRef<HTMLDivElement>(null);
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
  const visibleWindow = calendarWorkspaceWindow(focus, view);
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
    api.integrations().then(result => {if (active) setConfiguredSources(result.calendar_sources.filter(source=>source.configured&&source.enabled&&source.id!=='mac-calendar').map(source=>({id:source.id,label:source.label})));}).catch(()=>{});
    api.macCalendar().then(result=>{if(active)setMacSources(result.enabled?result.calendars.filter(calendar=>result.selected.includes(calendar.id)).map(calendar=>({id:`mac-calendar:${calendar.id}`,label:calendar.name})):[]);}).catch(()=>{});
    api.calendarActionSources().then(result => {if (active) setGoogleSources(result.sources.map(s => s.id));}).catch(() => {});
    return () => {active = false;};
  }, [revision]);
  useEffect(() => {try {localStorage.setItem("kingfisher-calendar-view", view);} catch { /* This view remains usable for the current session. */ }}, [view]);
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
  // Derive one merged universe on the same render as the events. Independent
  // metadata responses cannot overwrite another provider's calendars.
  const sourceUniverse = new Map<string,{id:string;label:string}>();
  for(const item of visibleData?.items||[])for(const copy of calendarSourceVersions(item)){
    const id=calendarDisplaySource(copy);
    if(id!=='mac-calendar')sourceUniverse.set(id,{id,label:copy.source_label||'Gespeicherter Kalender'});
  }
  for(const source of [...configuredSources,...macSources])sourceUniverse.set(source.id,source);
  const sourceOptions=[...sourceUniverse.values()].sort((a,b)=>a.label.localeCompare(b.label,'de'));
  useEffect(() => {if(timeScroll.current && (view==='Woche'||view==='Tag')) timeScroll.current.scrollTop=7*48;},[view,rangeKey]);
  const selectedSources = new Set(sourceOptions.filter(source=>!hiddenSources.has(source.id)).map(source=>source.id));
  const items = calendarVisibleEvents(visibleData?.items || [], sourceOptions.length?selectedSources:null);
  const detailsEvent = items.find(item=>calendarEventKey(item)===detailsKey) || null;
  const eventColor = (item:CalendarOverview['items'][number]) => calendarColor(calendarDisplaySource(calendarSourceVersions(item).find(copy=>!hiddenSources.has(calendarDisplaySource(copy)))||item));
  function eventActions(item:CalendarOverview['items'][number]) {
    return <div className="calendar-detail-actions">{calendarSourceVersions(item).filter(copy => copy.source_id && googleSources.includes(copy.source_id) && editableEventId(copy)).map(copy => <button key={calendarEventKey(copy)} type="button" className="secondary-action" onClick={() => {setDetailsKey(null);setActionTarget(copy);}}>Bearbeiten / absagen{item.source_copies?.length ? ` · ${copy.source_label}` : ''}</button>)}
      {item.art !== 'geburtstag' && (!item.end || new Date(item.end) > new Date()) && <button className="secondary-action" type="button" onClick={()=>selectPreparation(item.uid,item.start)}>Vorbereiten</button>}
      {!item.all_day && item.start && new Date(item.start)<=new Date() && <button className="secondary-action" type="button" onClick={()=>{setDetailsKey(null);select(null,followupKey(item.uid,item.start!));}}>Nachbereiten</button>}
    </div>;
  }
  function timeGrid() {
    const days=Array.from({length:view==='Tag'?1:7},(_,index)=>plusDays(view==='Tag'?focus:weekStart,index));
    return <div className="calendar-time-scroll" ref={timeScroll} aria-label={view==='Tag'?'Tageszeitraster':'Wochenzeitraster'}><div className={`calendar-time-grid ${view==='Tag'?'single-day':''}`}>
      <div className="calendar-time-corner">Ganztägig</div>{days.map(day=><section className="calendar-all-day" key={dateKey(day)}><button className={`calendar-grid-date ${dateKey(day)===dateKey(today)?'is-today':''}`} type="button" aria-label={day.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long'})} onClick={()=>{setFocus(day);setView('Tag');}}><span>{day.toLocaleDateString('de-DE',{weekday:'short'})}</span><strong>{day.getDate()}</strong></button>{(+plusDays(day,1)-+midnight(day))/3600000!==24&&<small className="calendar-clock-change">Zeitumstellung · {(+plusDays(day,1)-+midnight(day))/3600000} Std.</small>}{onDay(day).filter(ganztaegig).map(event=><button className="calendar-all-day-event" style={{borderLeftColor:eventColor(event)}} title={event.summary} key={calendarEventKey(event)} type="button" onClick={()=>setDetailsKey(calendarEventKey(event))}>{event.summary}</button>)}</section>)}
      <div className="calendar-hours">{Array.from({length:24},(_,hour)=><div className="calendar-hour" key={hour}>{`${String(hour).padStart(2,'0')}:00`}</div>)}</div>
      {days.map(day=><div className="calendar-time-day" key={dateKey(day)} aria-label={day.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long'})}>{calendarDayLayout(onDay(day).filter(event=>!ganztaegig(event)),day).map(placement=><button type="button" className="calendar-time-event" key={calendarPlacementKey(placement)} style={{top:`${placement.startMinute/1440*100}%`,height:`${(placement.endMinute-placement.startMinute)/1440*100}%`,left:`${placement.column/placement.columns*100}%`,width:`${100/placement.columns}%`,borderLeftColor:eventColor(placement.event)}} aria-label={`${placement.event.summary}, ${placement.timeLabel}, ${placement.event.source_label||'Kalender'}`} title={`${placement.event.summary} · ${placement.timeLabel} · ${placement.event.source_label||'Kalender'}`} onClick={()=>setDetailsKey(calendarEventKey(placement.event))}><small>{placement.continuesBefore?'↤ ':''}{placement.timeLabel.split('–')[0]}{placement.continuesAfter?' ↦':''}</small><strong>{placement.event.summary}</strong></button>)}</div>)}
    </div></div>;
  }
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
        return <div key={i} className={`month-day ${dateKey(day) === dateKey(today) ? "is-today" : ""} ${dateKey(day) === dateKey(focus) ? "is-selected" : ""} ${events.length ? "has-events" : ""}`}>
          <button type="button" className="calendar-month-date" aria-label={`${day.toLocaleDateString("de-DE")}, ${events.length} Termine im geladenen Zeitraum`} aria-pressed={dateKey(day) === dateKey(focus)} onClick={() => {setFocus(day); if (small && view==='Jahr') setView('Monat');}}><strong>{i + 1}</strong>{small && events.length>0 && <span className="event-dot" />}</button>
          {!small && <div className="calendar-month-events">{events.slice(0,3).map(event=><button type="button" className="calendar-month-event" key={calendarEventKey(event)} title={event.summary} onClick={()=>setDetailsKey(calendarEventKey(event))}><span className="calendar-vorne"><i className="calendar-punkt" style={{background:eventColor(event)}} />{!ganztaegig(event) && event.start ? <span className="calendar-zeit">{time(event.start)}</span> : null}</span><span className="calendar-titel">{event.summary}</span></button>)}{events.length>3 && <button className="calendar-month-more" type="button" onClick={()=>{setFocus(day);setView('Tag');}}>{events.length-3} weitere</button>}</div>}
        </div>;
      })}
    </div>;
  }
  const shown = view === "Liste" ? eventsInRange(items, midnight(focus), plusDays(focus, 7)) : onDay(focus);
  function shift(direction: number) {
    const next = view === "Tag" ? plusDays(focus,direction) : view === "Liste" ? plusDays(focus,direction*7) : view === "Woche" ? plusDays(focus, direction * 7)
      : view === "Jahr" ? new Date(focus.getFullYear() + direction, 0, 1)
        : new Date(focus.getFullYear(), focus.getMonth() + direction, 1);
    setFocus(next);
  }
  function agenda() {return <div className="calendar-list">{nachTagen(shown).map(gruppe => <section className="calendar-tag" key={gruppe.tag ? dateKey(gruppe.tag) : 'ohne'}>
        <h3>{gruppe.tag ? gruppe.tag.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long"}) : "Ohne Datum"}</h3>
        <div className="calendar-tag-zeilen">{gruppe.termine.map(item => <button type="button" className="calendar-entry" key={calendarEventKey(item)} onClick={()=>setDetailsKey(calendarEventKey(item))}>
          <span className="calendar-entry-zeit">{ganztaegig(item) || !item.start ? "Ganztägig" : <>{time(item.start)}{item.end ? <small>{time(item.end)}</small> : null}</>}</span>
          <i className="calendar-punkt" style={{background:eventColor(item)}} />
          <span className="calendar-entry-text"><strong>{item.summary}</strong>{item.location ? <small>{item.location}</small> : null}</span>
          <span className="g-zeile-pfeil" aria-hidden="true" />
        </button>)}</div>
      </section>)}</div>; }
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
  const periodTitle = view === "Monat" ? focus.toLocaleDateString("de-DE", {month:"long", year:"numeric"}) : view === "Jahr" ? `${focus.getFullYear()}` : view === "Tag" ? focus.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long",year:"numeric"}) : view === "Liste" ? `${focus.toLocaleDateString("de-DE",{day:"numeric",month:"short"})} – ${plusDays(focus,6).toLocaleDateString("de-DE",{day:"numeric",month:"short",year:"numeric"})}` : `${weekStart.toLocaleDateString("de-DE", {day:"numeric", month:"short"})} – ${plusDays(weekStart, 6).toLocaleDateString("de-DE", {day:"numeric", month:"short", year:"numeric"})}`;
  const ohneKalender = Boolean(visibleData && !visibleData.configured);
  // Genau ein gefüllter Knopf: „＋ Termin“, solange kein Formular offen ist und es einen Kalender gibt.
  const formOffen = Boolean(actionTarget || preparationEvent || followupTarget);
  const kalenderLink = (inhalt: string, klasse: string) => <a className={klasse} href="/settings#zugaenge" onClick={event=>{event.preventDefault();navigate("/settings#zugaenge");}}>{inhalt}</a>;
  return <div className="shell tasks-shell"><Sidebar active="Kalender" recentConversation={recentConversation} />
    <main className="tasks-page calendar-page">
      <Seitenkopf titel="Kalender" className="calendar-heading" aktionen={<>
        {kalenderLink("Kalender verwalten", "g-knopf-schlicht")}
        <button type="button" className={formOffen || ohneKalender ? "g-knopf-getoent" : "g-knopf"} onClick={() => {setDetailsKey(null);setActionTarget("new");}}>＋ Termin</button>
      </>} />
      {/* Links steht nur die Kalenderauswahl, und nur, wenn es etwas auszuwählen gibt; Monat und Pfeile stehen rechts. */}
      <div className={`calendar-workspace-layout ${sourceOptions.length>1?'':'ohne-auswahl'}`}>{sourceOptions.length>1 && <details className="calendar-navigator" aria-label="Kalender" open={navigatorOpen} onToggle={event=>setNavigatorOpen(event.currentTarget.open)}><summary>Kalender <span>{sourceOptions.filter(source=>!hiddenSources.has(source.id)).length} von {sourceOptions.length}</span></summary><div className="calendar-navigator-content">{sourceOptions.map(source=><label className="calendar-source-choice" key={source.id}><input type="checkbox" checked={!hiddenSources.has(source.id)} onChange={event=>{const checked=event.target.checked;setHiddenSources(old=>{const next=new Set(old);if(checked)next.delete(source.id);else next.add(source.id);return next;});}} style={{accentColor:calendarColor(source.id)}} /><span>{source.label}</span></label>)}</div></details>}
      <div className="calendar-main">
      {error && <p className="calendar-hinweis calendar-hinweis-fehler" role="alert">Termine konnten nicht geladen werden. <button type="button" className="g-knopf-schlicht" onClick={() => setRevision(n => n + 1)}>Erneut versuchen</button></p>}
      {visibleData?.errors.map((message, index) => <p className="calendar-hinweis calendar-hinweis-fehler" role="alert" key={index}>{message}</p>)}
      {visibleData?.warnings?.map((message, index) => <p className="calendar-hinweis" role="status" key={index}>{message}</p>)}
      {ohneKalender ? <Leer className="calendar-leer" satz="Noch kein Kalender verbunden." aktion={kalenderLink("Kalender verbinden", formOffen ? "g-knopf-getoent" : "g-knopf")} /> : <>
      <div className="calendar-actions"><Segmente label="Kalenderansicht" className="calendar-ansicht" optionen={ANSICHTEN.map(v => ({wert: v, titel: v}))} wert={view} onWahl={setView} /></div>
      <div className="calendar-period"><h2>{periodTitle}</h2><span className="calendar-period-nav"><button type="button" className="g-knopf-getoent g-kompakt calendar-pfeil" aria-label="Vorheriger Zeitraum" onClick={() => shift(-1)}>‹</button><button type="button" className="g-knopf-getoent g-kompakt" onClick={() => setFocus(midnight(today))}>Heute</button><button type="button" className="g-knopf-getoent g-kompakt calendar-pfeil" aria-label="Nächster Zeitraum" onClick={() => shift(1)}>›</button></span></div>
      <section className={`calendar-board calendar-board-${view.toLowerCase()}`} aria-label="Kalenderübersicht" aria-busy={loading}>
      {loading && !visibleData && !error && <p className="calendar-hinweis" role="status">Termine werden geladen …</p>}
      {view === "Monat" && grid(focus.getMonth())}
      {view === "Jahr" && <div className="year-grid">{Array.from({length: 12}, (_, month) => <section key={month}><h3>{new Date(focus.getFullYear(), month, 1).toLocaleDateString("de-DE", {month:"long"})}</h3>{grid(month, true, focus.getFullYear())}</section>)}</div>}
      {(view === 'Woche' || view === 'Tag') && timeGrid()}
      {view === "Liste" && <section aria-label="Terminliste">{shown.length ? agenda() : visibleData && !loading ? <Leer satz="Keine Termine in diesen sieben Tagen." /> : null}</section>}
      </section>
      {visibleData?.configured && !loading && items.length === 0 && visibleData.items.length > 0 && <p className="calendar-fussnote" role="status">Die Termine dieses Zeitraums stehen in ausgeblendeten Kalendern.</p>}
      {view !== "Jahr" && view !== "Liste" && shown.length > 0 && <div className="calendar-agenda"><button type="button" className="text-action" aria-expanded={agendaOpen} onClick={()=>setAgendaOpen(open=>!open)}>{shown.length} {shown.length === 1 ? 'Termin' : 'Termine'} am {focus.toLocaleDateString('de-DE',{day:'numeric',month:'long'})} als Liste</button>{agendaOpen && agenda()}</div>}
      </>}
      </div></div>
      {detailsEvent && <DetailPanel title="Termin" onClose={()=>setDetailsKey(null)}><div className="calendar-detail">
        <h3>{detailsEvent.summary}</h3>
        <p className="calendar-detail-zeit">{terminZeit(detailsEvent)}</p>
        {detailsEvent.location ? <p className="calendar-detail-ort">{detailsEvent.location}</p> : null}
        <dl className="calendar-detail-fakten">
          <div><dt>Kalender</dt><dd>{calendarSourceVersions(detailsEvent).map(copy=>copy.source_label||copy.source_id||'Kalender').join(' · ')}</dd></div>
          {detailsEvent.attendees?.length ? <div><dt>Mit</dt><dd>{detailsEvent.attendees.join(', ')}</dd></div> : null}
        </dl>
        {eventActions(detailsEvent)}
        {preparationEvent&&calendarEventKey(preparationEvent)===calendarEventKey(detailsEvent)&&<CalendarPreparation key={calendarEventKey(preparationEvent)} event={preparationEvent} revision={loadedRevision} onClose={()=>selectPreparation(null)} />}
      </div></DetailPanel>}
      {actionTarget && <CalendarActionForm key={actionTarget === "new" ? "new" : `${actionTarget.uid}|${actionTarget.start}`} event={actionTarget === "new" ? undefined : actionTarget} onClose={() => setActionTarget(null)} onDone={() => setRevision(n => n + 1)} />}
      {preparationEvent && (!detailsEvent || calendarEventKey(preparationEvent)!==calendarEventKey(detailsEvent)) && <div ref={preparationPanel}><CalendarPreparation key={calendarEventKey(preparationEvent)} event={preparationEvent} revision={loadedRevision} onClose={() => selectPreparation(null)} /></div>}
      {followupTarget && <div ref={followupPanel}><CalendarFollowup key={followup!} uid={followupTarget.uid} start={followupTarget.start} onClose={() => select(null, null)} /></div>}
      {preparationUid && visibleData && !loading && !error && !preparationEvent && <p className="calendar-hinweis" role="status">Der ausgewählte Termin ist in den geladenen Kalendern nicht zu finden. <button type="button" className="g-knopf-schlicht" onClick={() => selectPreparation(null)}>Auswahl schließen</button></p>}
    </main></div>;
}
