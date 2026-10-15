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
import './CalendarPage.css';
type View = WorkspaceCalendarView;
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
  const [navigatorOpen, setNavigatorOpen] = useState(() => window.matchMedia?.('(min-width: 701px)').matches ?? true);
  useEffect(() => {
    const media = window.matchMedia?.('(min-width: 701px)');
    if (!media) return;
    const resize = () => setNavigatorOpen(media.matches);
    media.addEventListener('change', resize);
    return () => media.removeEventListener('change', resize);
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
      <div className="calendar-time-corner">Ganztägig</div>{days.map(day=><section className="calendar-all-day" key={dateKey(day)}><button className="calendar-grid-date" type="button" onClick={()=>{setFocus(day);setView('Tag');}}>{day.toLocaleDateString('de-DE',{weekday:'short',day:'2-digit',month:'2-digit'})}</button>{(+plusDays(day,1)-+midnight(day))/3600000!==24&&<small className="calendar-clock-change">Zeitumstellung · {(+plusDays(day,1)-+midnight(day))/3600000} Std.</small>}{onDay(day).filter(event=>event.all_day).map(event=><button className="calendar-all-day-event" style={{borderLeftColor:eventColor(event)}} key={calendarEventKey(event)} type="button" onClick={()=>setDetailsKey(calendarEventKey(event))}>{event.summary}</button>)}</section>)}
      <div className="calendar-hours">{Array.from({length:24},(_,hour)=><div className="calendar-hour" key={hour}>{`${String(hour).padStart(2,'0')}:00`}</div>)}</div>
      {days.map(day=><div className="calendar-time-day" key={dateKey(day)} aria-label={day.toLocaleDateString('de-DE',{weekday:'long',day:'numeric',month:'long'})}>{calendarDayLayout(onDay(day),day).map(placement=><button type="button" className="calendar-time-event" key={calendarPlacementKey(placement)} style={{top:`${placement.startMinute/1440*100}%`,height:`${(placement.endMinute-placement.startMinute)/1440*100}%`,left:`${placement.column/placement.columns*100}%`,width:`${100/placement.columns}%`,borderLeftColor:eventColor(placement.event)}} aria-label={`${placement.event.summary}, ${placement.timeLabel}, ${placement.event.source_label||'Kalender'}`} title={`${placement.event.summary} · ${placement.timeLabel} · ${placement.event.source_label||'Kalender'}`} onClick={()=>setDetailsKey(calendarEventKey(placement.event))}><small>{placement.continuesBefore?'↤ ':''}{placement.timeLabel.split('–')[0]}{placement.continuesAfter?' ↦':''}</small><strong>{placement.event.summary}</strong></button>)}</div>)}
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
        return <div key={i} className={`month-day ${dateKey(day) === dateKey(today) ? "is-today" : ""} ${dateKey(day) === dateKey(focus) ? "is-selected" : ""}`}>
          <button type="button" className="calendar-month-date" aria-label={`${day.toLocaleDateString("de-DE")}, ${events.length} Termine im geladenen Zeitraum`} aria-pressed={dateKey(day) === dateKey(focus)} onClick={() => {setFocus(day); if (small && view==='Jahr') setView('Monat');}}><strong>{i + 1}</strong>{small && events.length>0 && <span className="event-dot" />}</button>
          {!small && <>{events.slice(0,2).map(event=><button type="button" className="calendar-month-event" style={{borderLeftColor:eventColor(event)}} key={calendarEventKey(event)} onClick={()=>setDetailsKey(calendarEventKey(event))}>{event.all_day?'':event.start?`${time(event.start)} `:''}{event.summary}</button>)}{events.length>2 && <button className="calendar-month-more" type="button" onClick={()=>{setFocus(day);setView('Tag');}}>+{events.length-2} weitere</button>}</>}
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
  function agenda() {return <> <h2 className="agenda-heading">{view === "Liste" ? "Sieben Tage ab gewähltem Datum" : focus.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long"})}</h2>
        <div className="calendar-list">{shown.map(item => <article className="calendar-entry" key={calendarEventKey(item)}><div>{item.start && <><strong>{new Date(item.start).toLocaleDateString("de-DE", {weekday:"short", day:"2-digit", month:"short"})}</strong><p>{item.all_day ? "Ganztägig" : `${time(item.start)}${item.end ? ` – ${time(item.end)}` : ""}`}</p></>}</div><div><h2><button type="button" className="calendar-entry-open" style={{borderLeftColor:eventColor(item)}} onClick={()=>setDetailsKey(calendarEventKey(item))}>{item.summary}</button></h2>{item.location && <p>{item.location}</p>}<small>{item.source_copies?.length ? item.source_copies.map(copy => copy.source_label).join(" · ") : item.source_label || "Verbundener Kalender"}</small>{eventActions(item)}</div></article>)}</div>
       </>; }
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
      <header className="settings-heading"><h1>Kalender</h1><p>Zeiten auf diesem Gerät</p></header>
      <div className="calendar-workspace-layout"><details className="calendar-navigator" aria-label="Datum und Kalender" open={navigatorOpen} onToggle={event=>setNavigatorOpen(event.currentTarget.open)}><summary>Datum & Kalender <span>{sourceOptions.filter(source=>!hiddenSources.has(source.id)).length} ausgewählt</span></summary><div className="calendar-navigator-content"><h2>{focus.toLocaleDateString('de-DE',{month:'long',year:'numeric'})}</h2>{grid(focus.getMonth(),true)}<label className="calendar-date-picker">Datum wählen<input type="date" value={`${focus.getFullYear()}-${String(focus.getMonth()+1).padStart(2,'0')}-${String(focus.getDate()).padStart(2,'0')}`} onChange={event=>{const [year,month,day]=event.target.value.split('-').map(Number);if(year&&month&&day)setFocus(new Date(year,month-1,day));}} /></label><h2>Kalender</h2>{sourceOptions.map(source=><label className="calendar-source-choice" key={source.id}><input type="checkbox" checked={!hiddenSources.has(source.id)} onChange={event=>{const checked=event.target.checked;setHiddenSources(old=>{const next=new Set(old);if(checked)next.delete(source.id);else next.add(source.id);return next;});}} /><i style={{background:calendarColor(source.id)}} /><span>{source.label}</span></label>)}{!sourceOptions.length&&<p>Quellen erscheinen mit den geladenen Kalendern.</p>}</div></details>
      <section className="calendar-board" aria-label="Kalenderübersicht">
      <div className="calendar-actions"><div role="group" aria-label="Kalenderansicht" className="view-switch">{(["Tag", "Woche", "Monat", "Liste", "Jahr"] as View[]).map(v => <button key={v} aria-pressed={v === view} onClick={() => setView(v)}>{v}</button>)}</div><button className="primary-action" onClick={() => {setDetailsKey(null);setActionTarget("new");}}>＋ Termin</button><details className="calendar-options quiet-details"><summary>Weitere Aktionen</summary><button className="secondary-action" disabled={loading} onClick={() => setRevision(value => value + 1)}>{loading ? "Wird geladen …" : "Ansicht aktualisieren"}</button><button className="secondary-action" onClick={() => navigate("/settings#zugaenge")}>Kalender verwalten</button></details></div>
      {error && <p role="alert">Termine konnten nicht geladen werden. Bitte erneut versuchen.</p>}
      {loading && <p role="status">Kalenderzeitraum wird geladen …</p>}
      {visibleData?.errors.map((message, index) => <p className="settings-error" role="alert" key={index}>{message}</p>)}
      {visibleData?.warnings?.map((message, index) => <p role="status" key={index}>{message}</p>)}
      {visibleData && !visibleData.configured && <p>Noch kein Kalender verbunden. Wähle unter „Kalender verwalten“ deine Quellen aus.</p>}
      {visibleData?.configured && !loading && items.length === 0 && visibleData.errors.length === 0 && <p role="status">{visibleData.items.length?'Keine Termine in den ausgewählten Kalendern.':'Keine Termine in diesem Zeitraum.'}</p>}
      <div className="calendar-period"><button aria-label="Vorheriger Zeitraum" onClick={() => shift(-1)}>←</button><h2>{view === "Monat" ? focus.toLocaleDateString("de-DE", {month:"long", year:"numeric"}) : view === "Jahr" ? `${focus.getFullYear()}` : view === "Tag" ? focus.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long",year:"numeric"}) : view === "Liste" ? `${focus.toLocaleDateString("de-DE")} – ${plusDays(focus,6).toLocaleDateString("de-DE")}` : `${weekStart.toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric"})} – ${plusDays(weekStart, 6).toLocaleDateString("de-DE", {day:"2-digit", month:"2-digit", year:"numeric"})}`}</h2><button aria-label="Nächster Zeitraum" onClick={() => shift(1)}>→</button><button onClick={() => setFocus(midnight(today))}>Heute</button></div>
      {view === "Monat" && grid(focus.getMonth())}
      {view === "Jahr" && <div className="year-grid">{Array.from({length: 12}, (_, month) => <section key={month}><h2>{new Date(focus.getFullYear(), month, 1).toLocaleDateString("de-DE", {month:"long"})}</h2>{grid(month, true, focus.getFullYear())}</section>)}</div>}
      {(view === 'Woche' || view === 'Tag') && timeGrid()}
      {view !== "Jahr" && (view === "Liste" ? <section aria-label="Terminliste">{agenda()}</section> : <details className="calendar-agenda quiet-details"><summary>{shown.length} {shown.length === 1 ? 'Termin' : 'Termine'} am {focus.toLocaleDateString('de-DE',{day:'numeric',month:'long'})} · als Liste ansehen</summary>{agenda()}</details>)}
      </section></div>
      {detailsEvent && <DetailPanel title="Termindetails" onClose={()=>setDetailsKey(null)}><h3>{detailsEvent.summary}</h3><p>{detailsEvent.all_day?`Ganztägig · ${detailsEvent.start?new Date(detailsEvent.start).toLocaleDateString('de-DE',{dateStyle:'full'}):'Beginn unbekannt'}`:detailsEvent.start?new Date(detailsEvent.start).toLocaleString('de-DE',{dateStyle:'full',timeStyle:'long'}):'Beginn unbekannt'}{detailsEvent.end?` – ${new Date(detailsEvent.end).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'long'})}`:''}</p>{detailsEvent.all_day&&detailsEvent.end&&<p>Die Endangabe bezeichnet den ersten Tag nach dem Termin.</p>}{detailsEvent.location&&<p>{detailsEvent.location}</p>}<details className="quiet-details"><summary>Kalender & Teilnehmende{detailsEvent.source_copies?.length ? ` · ${detailsEvent.source_copies.length} Kalenderkopien` : ''}</summary><p>{calendarSourceVersions(detailsEvent).map(copy=>copy.source_label||copy.source_id||'Kalender').join(' · ')}</p>{detailsEvent.attendees?.length?<p>{detailsEvent.attendees.join(', ')}</p>:<p>Keine Teilnehmenden angegeben.</p>}</details>{eventActions(detailsEvent)}{preparationEvent&&calendarEventKey(preparationEvent)===calendarEventKey(detailsEvent)&&<CalendarPreparation key={calendarEventKey(preparationEvent)} event={preparationEvent} revision={loadedRevision} onClose={()=>selectPreparation(null)} />}</DetailPanel>}
      {actionTarget && <CalendarActionForm key={actionTarget === "new" ? "new" : `${actionTarget.uid}|${actionTarget.start}`} event={actionTarget === "new" ? undefined : actionTarget} onClose={() => setActionTarget(null)} onDone={() => setRevision(n => n + 1)} />}
      {preparationEvent && (!detailsEvent || calendarEventKey(preparationEvent)!==calendarEventKey(detailsEvent)) && <div ref={preparationPanel}><CalendarPreparation key={calendarEventKey(preparationEvent)} event={preparationEvent} revision={loadedRevision} onClose={() => selectPreparation(null)} /></div>}
      {followupTarget && <div ref={followupPanel}><CalendarFollowup key={followup!} uid={followupTarget.uid} start={followupTarget.start} onClose={() => select(null, null)} /></div>}
      {preparationUid && visibleData && !loading && !error && !preparationEvent && <p role="status">Der ausgewählte Termin ist in den aktuell geladenen Kalendern nicht verfügbar. <button className="text-action" onClick={() => selectPreparation(null)}>Auswahl schließen</button></p>}
    </main></div>;
}
