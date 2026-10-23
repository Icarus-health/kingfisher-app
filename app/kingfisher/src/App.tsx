import {useConversationVoice, VoiceDraftStatus, VoiceReply} from "./ConversationVoice";
import {CommandBar} from "./CommandBar";
import {ConversationCapture} from "./ConversationCapture";
import {ConversationNavigation} from "./ConversationNavigation";
import {MessageText} from "./MessageText";
import { TodayOverview, TodayPersonal, todayAttention } from "./TodayOverview";
import { FassungHeute } from "./Fassung";
import { InterfaceIcon } from "./InterfaceIcon";
import { AudioBriefing } from "./AudioBriefing";
import { Erststart } from "./Einrichtung/Erststart";
import { HeuteLeer } from "./Einrichtung/HeuteLeer";
import { useErststartWeiterleitung } from "./Einrichtung/useErststartWeiterleitung";
import { TaskSuggestions } from "./TaskSuggestions";
import { AufgabenPostVorschlaege } from "./AufgabenPostVorschlaege";
import { BriefingSuggestion } from "./BriefingSuggestion";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ApiError,
  type ConversationPayload,
  type MorningBriefing,
  type Task as LocalTask,
  type Project,
} from "./api";
import { Sidebar } from "./chrome";
import { ActionApprovalCard } from "./ActionApprovalCard";
import { ProjectControls } from "./ProjectControls";
import {ProjectOverview} from "./ProjectOverview";
import { DecisionControls } from "./DecisionControls";
import { GoalControls } from "./GoalControls";
import { DevelopmentPage } from "./DevelopmentPage";
import {HealthPage} from "./HealthPage";
import { TaskRow } from "./TaskRow";
import {DetailPanel} from "./DetailPanel";
import {ProjectBoard} from "./ProjectBoard";
import {visibleTaskGroups} from "./taskWorkspaceModel";
import {TaskPager, initialTaskPage, type TaskPageState} from './taskPager';
import {ReviewPage} from './ReviewPage';
import { TaskDetail } from "./TaskDetail";
import { endOfTaskDay } from "./taskWorkflow";
import { ProfileSource } from "./ProfileSource";
import { MemoryGraph } from "./MemoryGraph";
import { MemoryProfile, RegistryProfile } from "./MemoryProfile";
import { SachenAkte } from "./AkteAbschnitte";
import { CalendarPage } from "./CalendarPage";
import { HabitControls } from "./HabitControls";
import { WorldRadar } from "./WorldControls";
import { WorldPage } from "./WorldPage";
import { Messages } from "./Messages";
import { SatzAntwort } from "./SatzAntwort";
import { BelegQuellen } from "./BelegQuellen";
import { nachrichtAusAdresse } from "./quellenWeg";
import { StimmtNicht } from "./RueckmeldungAnsicht";
import { InDieAkte } from "./UebernehmenKarte";
import { uebernehmbar } from "./uebernehmen";
import { meldbar } from "./rueckmeldung";
import { GESTUETZT_AUF, OHNE_BELEG, belegStand, kontextLeerSatz } from "./beleg";
import { AntwortZeile } from "./AntwortZeiten";
import { ASSET, icon, navigate } from "./ui";
import { EinstellungenSeite } from "./Einstellungen/Seite";
import { Verweis } from "./VerweisLink";
import { zaehlerText } from "./heute";
import { PostfachStand } from "./PostfachStand";
import { TodaySourceStatus } from "./TodaySourceStatus";
import { createDailyRefresh } from "./dailyFlow";
import { MailReader } from "./MailReader";
import {TaskSaveAttempt, TaskSavePreparationError, MANUAL_TASK_REQUEST_KEY, TASK_SAVE_UNCONFIRMED, TASK_SAVE_PENDING} from './taskSaveAttempt';
import {TaskRetryReview} from './TaskRetryReview';



function dateParts(value: string, timeZone?: string) {
  const date = new Date(value);
  // In der Zeitzone des Briefings (der eingestellten), nicht der des Browsers; eine unbekannte Zone fällt zurück.
  const zone = timeZone && (() => { try { new Intl.DateTimeFormat("de-DE", { timeZone }); return timeZone; } catch { return undefined; } })();
  const weekday = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: zone }).format(date).replace(".", "");
  const day = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "long", year: "numeric", timeZone: zone }).format(date);
  const time = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: zone }).format(date);
  return { date: `${weekday}, ${day}`, time };
}


// Antwort auf eine Zeitrückfrage: ein Datum wählen statt ein Format zu tippen.
function SourceDateForm({busy, onSubmit}: {busy: boolean; onSubmit: (value: string) => void}) {
  const [value, setValue] = useState("");
  const today = new Date();
  const max = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return <form className="memory-actions clarification-date" onSubmit={(event) => { event.preventDefault(); if (value) onSubmit(value); }}>
    <label>Datum der Nachricht<input max={max} onChange={(event) => setValue(event.target.value)} required type="date" value={value} /></label>
    <button className="memory-reject" disabled={busy || !value} type="submit">Datum übernehmen</button>
  </form>;
}

/** Der Zähler einer Kachel im Briefing; bei null keiner (Fremdprobe 2, Befund 10). */
function Zaehler({ anzahl, className }: { anzahl: number; className?: string }) {
  const text = zaehlerText(anzahl);
  return text ? <b className={className}>{text}</b> : null;
}

function LoadingMorning() {
  return (
    <div className="morning-page loading" aria-label="Briefing wird geladen">
      <div className="hero skeleton-hero" />
      <div className="card-grid">
        {[0, 1, 2].map((item) => <div className="brief-card skeleton-card" key={item}><i /><i /><i /></div>)}
      </div>
    </div>
  );
}


export function BriefingDrawer({ briefing, open, onClose, onChange }: {
  briefing: MorningBriefing;
  open: boolean;
  onClose: () => void;
  onChange: (change?: "correction") => void;
}) {
  const panel = useRef<HTMLElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus({preventScroll:true});
    return () => {
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({preventScroll:true});
    };
  }, [open]);
  const sourceLabels: Record<string,string> = {termin:"Kalender",aufgabe:"Aufgabe",wartet:"Rückmeldung",zusage:"Zusage",mail:"Mail",working_memory:"gespeicherte Quelle",akte:"Gedächtnis"};
  const [correctionSaved, setCorrectionSaved] = useState(false);
  function sourceChanged(change?: "correction") {
    if (change === "correction") setCorrectionSaved(true);
    onChange(change);
  }
  const stamp = dateParts(briefing.generated_at, briefing.timezone);
  const meeting = briefing.later_today.find((item) => /^Termin:/i.test(item.title)) ?? briefing.later_today[0];
  const meetingTitle = meeting?.title.replace(/^Termin:\s*/i, "");
  const fixtureNews = briefing.fixture ? [
    ["aurora-network-tile.png", "Wirtschaft", "Neue Impulse für Europas Märkte", "Reuters · 06:45"],
    ["ice-abstract-tile.png", "Technologie", "KI-Forschung erreicht neuen Meilenstein", "Handelsblatt · 06:15"],
    ["network-constellation-tile.png", "Gesellschaft", "Digitale Zusammenarbeit verändert den Alltag", "Tagesschau · 05:30"],
  ] : [];

  return (
    <>
      <button aria-label="Briefing schließen" aria-hidden={!open} inert={!open} tabIndex={-1} className={`scrim ${open ? "open" : ""}`} onClick={onClose} type="button" />
      <section ref={panel} role="dialog" aria-modal={open || undefined} inert={!open} aria-hidden={!open} aria-label="Briefing" className={`briefing-drawer ${open ? "open" : ""}`} onKeyDown={event => {
        if (event.key === "Escape") {event.preventDefault();onClose();return;}
        if (event.key !== "Tab" || !panel.current) return;
        const fields = Array.from(panel.current.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex]')).filter(node => node.tabIndex >= 0 && node.getClientRects().length > 0);
        const first=fields[0],last=fields.at(-1);
        if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
      }}>
        <button ref={closeButton} className="drawer-close" onClick={onClose} type="button">
          <img src={icon("house", "Outline")} alt="" /><span>Zurück zu Heute</span>
        </button>
        <div className="drawer-hero">
          <img className="drawer-landscape" src={`${ASSET.media}morning-lake-panorama-approved-v1.png`} alt="" />
          <div className="drawer-heading">
            {/* Deutsch und ohne Tageszeit: Es heißt morgens wie abends „Briefing“ (Fremdprobe, Befund 20). */}
            <p>BRIEFING</p><h2>{briefing.greeting}</h2>
            <span>{stamp.date} · {briefing.weather?.location ?? briefing.timezone}</span>
          </div>
          <img className="drawer-bird" src={`${ASSET.media}Freigestellter Eisvogel auf Zweig.png`} alt="" />
        </div>
        <div className="drawer-content">
          {open ? <AudioBriefing briefing={briefing} /> : null}
          <div className="drawer-grid">
            <article className="drawer-card">
              <header><span>HEUTIGE TOP-PRIORITÄTEN</span><Zaehler anzahl={briefing.needs_you.length} /></header>
              {briefing.needs_you.length ? briefing.needs_you.map((item) => (
                <div className="drawer-row" key={item.id}>
                  <span><strong>{item.title}</strong>{[...new Set([item.reason,item.detail])].filter((line):line is string=>Boolean(line)&&line!==item.title).map(line=><small key={line}>{line===`Quelle: ${item.source}`?`Quelle: ${sourceLabels[item.source??""]??"gespeicherte Quelle"}`:line}</small>)}</span><em>{item.priority}</em>
                </div>
              )) : <p className="drawer-empty">Keine offenen Prioritäten</p>}
            </article>

            <article className="drawer-card meeting-card">
              <header><span>MEETING-VORBEREITUNG</span></header>
              {meeting ? (
                <>
                  <h3>{meetingTitle}</h3><p className="meeting-time">{meeting.detail || "Heute"} · {meeting.time}</p>
                  <div className="meeting-context"><strong>Worum es geht</strong><p>{meeting.reason || meeting.detail}</p></div>
                  {meeting.source_ref && <a className="secondary-action" href={`/calendar?prepare=${encodeURIComponent(meeting.source_ref)}`}>Termin vorbereiten</a>}
                </>
              ) : <p className="drawer-empty">Heute ist kein Termin vorzubereiten.</p>}
            </article>

            <article className="drawer-card">
              <header><span>RELEVANTE NACHRICHTEN</span><Zaehler anzahl={briefing.happening_now.length} className="teal" /></header>
              {correctionSaved && <p role="status">Berichtigung gespeichert. Die frühere Angabe wird nicht mehr verwendet. Frage erneut nach dem aktuellen Stand.</p>}
              {briefing.happening_now.length ? briefing.happening_now.map((item) => (
                <div className="message-row" key={item.id}><span><strong>{item.title}</strong><small>{item.detail}</small></span>
                  {item.source === "working_memory" && item.source_ref ? <ProfileSource kind="episode" id={item.source_ref} label="Quelle ansehen" allowDismiss onChange={sourceChanged} /> : null}
                </div>
              )) : <p className="drawer-empty">Keine neuen relevanten Nachrichten</p>}
              {briefing.working_memory_more && <p className="drawer-empty">Nicht alle Quellen dieser Auswahl sind automatisch sortiert oder in diesem begrenzten Überblick enthalten.</p>}
            </article>

            <article className="drawer-card weather-route-card">
              <header><span>WETTER & WEG</span></header>
              {briefing.weather ? (
                <div className="weather-route">
                  <div><strong>{briefing.weather.temperature_c}°</strong><span>{briefing.weather.condition}<br />{briefing.weather.location}</span></div>
                  <div className="route-state"><strong>Arbeitsweg</strong><span>Noch keine Route verbunden.</span></div>
                </div>
              ) : <p className="drawer-empty">Wetter ist nicht eingeschaltet. Du findest es unter <Verweis ziel="darf" />.</p>}
              {briefing.weather?.attribution ? <a className="weather-attribution" href={briefing.weather.attribution_url} rel="noreferrer" target="_blank">Open-Meteo</a> : null}
            </article>

            <article className="drawer-card world-card">
              <header><span>RELEVANTES AUS DER WELT</span><Zaehler anzahl={fixtureNews.length} /></header>
              {fixtureNews.length ? (
                <div className="news-grid">
                  {fixtureNews.map(([image, section, title, source]) => (
                    <div key={image}>
                      <img src={`${ASSET.media}${image}`} alt="" />
                      <span><small>{section}</small><strong>{title}</strong><em>{source}</em></span>
                    </div>
                  ))}
                </div>
              ) : <p className="drawer-empty">Noch keine Nachrichtenquelle gewählt. Du findest sie unter <Verweis ziel="darf" />.</p>}
            </article>
          </div>
        </div>
      </section>
    </>
  );
}

function Morning({ recentConversation, rememberConversation, chatAvailable, chatPlaceholder }: {
  recentConversation: string | null;
  rememberConversation: (id: string) => void;
  chatAvailable: boolean;
  chatPlaceholder?: string;
}) {
  const [briefing, setBriefing] = useState<MorningBriefing | null>(null);
  const [error, setError] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState(false);
  // „Zum Briefing“ am Ende der Einrichtung öffnet es direkt (/today?briefing=1, Befund 23); die Adresse wird danach wieder schlicht.
  const [briefingOpen, setBriefingOpen] = useState(() => new URLSearchParams(window.location.search).get("briefing") === "1");
  useEffect(() => { if (briefingOpen && window.location.search) window.history.replaceState({}, "", "/today"); }, [briefingOpen]);
  const [pendingConversation, setPendingConversation] = useState<string | null>(null);
  const [correctionSaved, setCorrectionSaved] = useState(false);
  const [taskNotice, setTaskNotice] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const refresher = useRef<ReturnType<typeof createDailyRefresh<MorningBriefing>> | null>(null);
  const [mailUid, setMailUid] = useState<string | null>(null);
  const mailDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (mailUid && !mailDialog.current?.open) mailDialog.current?.showModal(); }, [mailUid]);

  function load(change?: "correction") {
    if (change === "correction") setCorrectionSaved(true);
    void refresher.current?.run(true);
  }

  // Der Gruß kommt sofort, die Post danach (Fremdprobe, Befund 22): erst ohne Posteingang, dann vollständig. Ein
  // schweigendes Postfach hält so nie die ganze Startseite auf; scheitert nur der zweite Abruf, bleibt der erste stehen.
  useEffect(() => {
    let active = true;
    let fullReceived = false;
    let fullFailed = false;
    let quickFailed = false;
    const lastKnown = (result: MorningBriefing) => fullFailed ? {...result, post_ausstehend: false,
      partial_failures: [...result.partial_failures, {section: "mail", message: "Posteingang konnte nicht vollständig geladen werden."}]} : result;
    const refresh = createDailyRefresh(async () => {
      if (active) setRefreshing(true);
      try { return await api.morning(); }
      catch (problem) {
        fullFailed = true;
        if (active) {
          setRefreshError(true);
          setBriefing(current => current ? lastKnown(current) : current);
          if (quickFailed && !fullReceived) setError(true);
        }
        throw problem;
      } finally { if (active) setRefreshing(false); }
    }, result => {
      fullReceived = true; fullFailed = false;
      setBriefing(result); setError(false); setRefreshError(false);
    });
    refresher.current = refresh;
    api.morning(false).then(result => {
      if (active && !fullReceived) { setBriefing(lastKnown(result)); setError(false); }
    }).catch(() => { quickFailed = true; if (active && fullFailed && !fullReceived) setError(true); });
    void refresh.run(true);
    const automatic = () => { if (document.visibilityState === "visible") void refresh.run(); };
    const timer = window.setInterval(automatic, 300000);
    window.addEventListener("focus", automatic);
    document.addEventListener("visibilitychange", automatic);
    return () => {
      active = false; refresh.dispose(); refresher.current = null;
      window.clearInterval(timer); window.removeEventListener("focus", automatic);
      document.removeEventListener("visibilitychange", automatic);
    };
  }, []);

  async function begin(message: string) {
    if (!chatAvailable) return;
    setSending(true);
    setSendError(false);
    try {
      const conversationId = pendingConversation ?? (await api.createConversation()).conversation.id;
      setPendingConversation(conversationId);
      rememberConversation(conversationId);
      await api.sendMessage(conversationId, message);
      setPendingConversation(null);
      navigate(`/conversations/${conversationId}`);
    } catch (problem) {
      setSendError(true);
      throw problem;
    } finally {
      setSending(false);
    }
  }

  if (!briefing && !error) return <div className="shell"><Sidebar active="Heute" recentConversation={recentConversation} /><main><LoadingMorning /></main></div>;
  if (error || !briefing) return (
    <div className="shell"><Sidebar active="Heute" recentConversation={recentConversation} /><main className="state-page"><section className="brief-card error-state"><p>Das Briefing ist gerade nicht erreichbar.</p><button onClick={() => load()}>Wiederholen</button></section></main></div>
  );

  const attentionCount = todayAttention(briefing).length;
  return (
    <div className="shell">
      <Sidebar active="Heute" navigationDisabled={briefingOpen} briefingOpen={briefingOpen} onToday={() => setBriefingOpen(true)} recentConversation={recentConversation} />
      <main inert={briefingOpen} className="morning-page today-page">
        <div className="today-landscape" aria-hidden="true" />
        <section className="hero">
          <img className="hero-bird" src={`${ASSET.media}Freigestellter Eisvogel auf Zweig.png`} alt="" />
          <div className="hero-copy"><p className="today-hero-label">DEIN TAG MIT KINGFISHER</p><h1>{briefing.greeting}</h1>
            <p className="today-hero-summary">{attentionCount === 0 ? "Dein Überblick ist da." : attentionCount === 1 ? "Ein Punkt braucht deine Aufmerksamkeit." : `${attentionCount} Punkte brauchen deine Aufmerksamkeit.`}</p>
            <button className="today-briefing-button" onClick={() => setBriefingOpen(true)} type="button">Briefing öffnen <span aria-hidden="true">→</span></button>
          </div>
          {/* Eine Uhr reicht: die in der Seitenleiste (Fremdprobe 2, Befund 11). */}
          {briefing.weather ? (
            <div className="weather">
              <span className="weather-location">{briefing.weather.location}</span><strong>{briefing.weather.temperature_c}°</strong><small>{briefing.weather.condition}</small>
              {briefing.weather.attribution ? <a href={briefing.weather.attribution_url} rel="noreferrer" target="_blank">Open-Meteo</a> : null}
            </div>
          ) : null}
        </section>

        <section className="briefing-area">
          <TodaySourceStatus briefing={briefing} refreshing={refreshing} refreshError={refreshError} onRefresh={() => load()} />
          <div className="today-command">
            <CommandBar busy={sending} disabled={!chatAvailable} onSubmit={begin} placeholder={chatPlaceholder} />
            {sendError ? <p className="partial-error command-error">Die Frage konnte nicht gesendet werden. Bitte erneut versuchen.</p> : null}
          </div>
          <HeuteLeer leer={!briefing.needs_you.length && !briefing.later_today.length && !briefing.happening_now.length}>
            <TodayOverview briefing={briefing} onChange={load} taskNotice={taskNotice} correctionSaved={correctionSaved} onOpenMail={setMailUid} onTaskDone={message => { setTaskNotice(message); load(); }} />
            <WorldRadar />
          </HeuteLeer>
          <TodayPersonal />
          <FassungHeute />
          <PostfachStand ausstehend={Boolean(briefing.post_ausstehend)} />
        </section>
      </main>
      <BriefingDrawer briefing={briefing} onClose={() => setBriefingOpen(false)} onChange={load} open={briefingOpen} />
      {mailUid && <dialog ref={mailDialog} className="today-mail-dialog" aria-label="Nachricht bearbeiten" onCancel={() => setMailUid(null)} onClose={() => setMailUid(null)}>
        <MailReader key={mailUid} uid={mailUid} onClose={() => setMailUid(null)} onTaskSaved={() => load()} />
      </dialog>}
    </div>
  );
}

function Conversation({ id, recentConversation, rememberConversation, chatAvailable, chatPlaceholder }: {
  id: string;
  recentConversation: string | null;
  rememberConversation: (id: string) => void;
  chatAvailable: boolean;
  chatPlaceholder?: string;
}) {
  const [data, updateData] = useState<ConversationPayload | null>(null);
  const live = useRef(true);
  const messagesElement = useRef<HTMLDivElement | null>(null);
  const followBottom = useRef(true);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  function setData(value: ConversationPayload) { if (live.current) updateData(value); }
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  const [error, setError] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const [memoryError, setMemoryError] = useState(false);
  const [correctionSaved, setCorrectionSaved] = useState(false);
  const voice = useConversationVoice(id, data, sending || error || !data);

  function load(change?: "correction") {
    if (change === "correction") setCorrectionSaved(true);
    setError(false);
    api.getConversation(id).then(setData).catch(() => setError(true));
  }

  useEffect(() => {
    let active = true;
    setCorrectionSaved(false);
    api.getConversation(id).then((conversation) => {
      if (active) {
        setData(conversation);
        rememberConversation(conversation.conversation.id);
      }
    }).catch(() => {
      if (active) setError(true);
    });
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    const element = messagesElement.current;
    if (!element || !data || !followBottom.current || window.location.hash) return;
    element.scrollTop = element.scrollHeight;
  }, [data?.messages.length, sending]);

  async function create() {
    const created = await api.createConversation();
    if (!live.current) return;
    rememberConversation(created.conversation.id);
    navigate(`/conversations/${created.conversation.id}`);
  }

  const contextLines = useMemo(
    () => data?.context.items.slice(0, 5).map((item) => item.basis?.state === "review"
      ? `${item.statement} — Grundlage prüfen` : item.statement) ?? [],
    [data],
  );
  const memoryCards = useMemo(
    () => new Map(data?.memory_candidates.map((card) => [card.message_id, card]) ?? []),
    [data],
  );

  async function send(message: string, clarification?: { choice?: number; date?: string; newQuestion?: boolean }) {
    if (!message.trim() || !chatAvailable) return;
    setSending(true);
    setSendError(false);
    setRefreshNotice(null);
    try {
      setData(await api.sendMessage(id, message, clarification));
      setCorrectionSaved(false);
      if (clarification?.newQuestion) setRefreshNotice("Mit dem aktuellen Stand der Quellen neu beantwortet.");
    } catch (problem) {
      // Haben sich die Quellen seit der Rückfrage geändert, passt die Auswahl
      // nicht mehr. Statt eines Fehlers wird die ursprüngliche Frage mit dem
      // aktuellen Stand neu gestellt; der Nutzer muss nichts wiederholen.
      const original = data?.messages[data.messages.length - 1]?.metadata?.context?.original_question;
      const stale = problem instanceof ApiError && problem.status === 409
        && (clarification?.choice !== undefined || clarification?.date !== undefined) && original;
      if (stale) {
        try {
          setData(await api.sendMessage(id, original, { newQuestion: true }));
          setRefreshNotice("Die Quellen haben sich seit der Rückfrage geändert. Die Frage wurde mit dem aktuellen Stand neu beantwortet.");
          return;
        } catch (second) {
          setSendError(true);
          throw second;
        }
      }
      setSendError(true);
      throw problem;
    } finally {
      setSending(false);
    }
  }

  async function retry(messageId: string) {
    setSending(true);
    setSendError(false);
    try {
      setData(await api.retryMessage(id, messageId));
    } catch (problem) {
      setSendError(true);
      throw problem;
    } finally {
      setSending(false);
    }
  }

  async function decideMemory(candidateId: string, replaceConflicts = false) {
    setSending(true);
    setMemoryError(false);
    try {
      setData(await api.acceptMemoryCandidate(id, candidateId, replaceConflicts));
    } catch {
      setMemoryError(true);
    } finally {
      setSending(false);
    }
  }

  async function resolveAction(approvalId: string, granted: boolean, confirmation: string) {
    setSending(true);
    try {
      setData(await api.resolveAction(id, approvalId, granted, confirmation));
    } catch (problem) {
      // Ein verlorener Antwortweg darf keine zweite Ausführung anbieten.
      try { setData(await api.getConversation(id)); } catch { /* Fehler bleibt an der Karte sichtbar. */ }
      throw problem;
    } finally {
      setSending(false);
    }
  }

  async function rejectMemory(candidateId: string) {
    setSending(true);
    setMemoryError(false);
    try {
      setData(await api.rejectMemoryCandidate(id, candidateId));
    } catch {
      setMemoryError(true);
    } finally {
      setSending(false);
    }
  }

  async function retractMemory(candidateId: string) {
    setSending(true);
    setMemoryError(false);
    try {
      setData(await api.retractMemoryCandidate(id, candidateId));
    } catch {
      setMemoryError(true);
    } finally {
      setSending(false);
    }
  }

  function showMemorySource(messageId: string) {
    const source = document.getElementById(`message-${messageId}`);
    source?.scrollIntoView({ block: "center" });
    source?.focus({ preventScroll: true });
  }

  // Ein Quellenverweis aus einem anderen Gespräch kommt mit `#message-…`: die Nachricht einmal anspringen.
  const angesprungen = useRef<string | null>(null);
  useEffect(() => {
    const nachricht = nachrichtAusAdresse(window.location.hash);
    if (!data || !nachricht || angesprungen.current === `${id}:${nachricht}`) return;
    if (!data.messages.some((item) => item.id === nachricht)) return;
    angesprungen.current = `${id}:${nachricht}`;
    window.setTimeout(() => showMemorySource(nachricht), 0);
  }, [data, id]);

  return (
    <div className="shell conversation-shell">
      <Sidebar active="Gespräche" recentConversation={recentConversation} />
      <main className={`conversation-page workspace-chat ${navigationOpen ? 'navigation-open' : ''}`}>
        <ConversationNavigation activeId={id} revision={data?.conversation.updated_at} onCreate={create} onSelect={selected => navigate(`/conversations/${selected}`)} />
        <section className="thread">
          <header className="thread-header"><button className="conversation-navigation-toggle" aria-expanded={navigationOpen} type="button" onClick={() => setNavigationOpen(open => !open)}>Gespräche</button><h1>{data?.conversation.title ?? "Gespräch"}</h1><button className="conversation-sources-toggle" aria-expanded={sourcesOpen} aria-controls="conversation-sources" type="button" onClick={() => setSourcesOpen(open => !open)}>Verwendete Quellen</button></header>
          {sourcesOpen && <aside className="conversation-sources" id="conversation-sources" aria-label="Verwendete Quellen">
            {contextLines.length ? contextLines.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : data?.context.source_links?.length ? <p>{data.context.source_links.length} Originalquelle(n) zur Prüfung. Keine bestätigte Aussage.</p> : <p>{kontextLeerSatz(data?.messages ?? [])}</p>}
          </aside>}
          <div className="messages" ref={messagesElement} onScroll={event => {
            const element = event.currentTarget;
            followBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 96;
          }}>
            {!error && data && !data.messages.length && <div className="conversation-empty"><h2>Womit möchtest du beginnen?</h2><p>Stelle eine Frage oder halte einen Gedanken fest.</p></div>}

            {error ? <div className="message assistant error-message"><p>Das Gespräch ist gerade nicht erreichbar.</p><button onClick={() => load()}>Wiederholen</button></div> : null}
            {!error && !data ? <div className="message assistant skeleton-message"><i /><i /><i /></div> : null}
            {data?.messages.map((message, messageIndex) => {
              const card = memoryCards.get(message.id);
              const beleg = belegStand(message);
              const candidate = card?.candidate;
              const requiresReplacement = Boolean(card?.conflicts.length);
              const memoryDecision = card?.claim_usable ? "Als Wissen bestätigt."
                : card?.claim?.status === "retracted" ? "Widerrufen. Wird nicht mehr als Wissen verwendet."
                : card?.claim?.status === "superseded" ? "Durch einen anderen bestätigten Stand ersetzt."
                : card?.claim?.status === "disputed" ? "Grundlage geändert. Muss erneut geprüft werden."
                : "Derzeit nicht als Wissen verwendbar.";
              return <article className={`message ${message.role} ${message.status}`} id={`message-${message.id}`} tabIndex={-1} key={message.id}>
                <span>{message.role === "user" ? "DU" : "KINGFISHER"}</span>
                {message.metadata?.context?.satzantwort ? <SatzAntwort daten={message.metadata.context.satzantwort} onChange={load} /> : <MessageText content={message.content} />}
                {message.role === "assistant" ? <VoiceReply voice={voice} message={message} disabled={sending || error} /> : null}
                {message.role === "assistant" ? <AntwortZeile zeiten={message.metadata?.context?.zeiten} /> : null}
                {message.role === "assistant" && message.metadata?.context?.quellen ? <BelegQuellen quellen={message.metadata.context.quellen} gespraech={data.conversation.id} zeigeNachricht={showMemorySource} onChange={load} /> : null}
                {message.metadata?.context?.satzantwort || message.role !== "user" ? null : message.metadata?.context?.source_links?.map((source) => <ProfileSource key={source.episode_id} kind="episode" id={source.episode_id} label={source.label} allowDismiss={source.automatic_memory === true} onChange={load} quiet eigeneFrage />)}
                {beleg.art === "quellenlinks" ? <div className="beleg-links" role="group" aria-label="Worauf die Antwort sich stützt"><p className="beleg-kopf">{GESTUETZT_AUF}</p>
                  {message.metadata?.context?.source_links?.map((source) => <ProfileSource key={source.episode_id} kind="episode" id={source.episode_id} label={source.label} allowDismiss={source.automatic_memory === true} onChange={load} quiet={false} />)}
                </div> : null}
                {beleg.art === "ohne" ? <p className="beleg-ohne">{OHNE_BELEG}</p> : null}
                {meldbar(message) ? <div className="antwort-rueckkanal">
                  <StimmtNicht conversationId={data.conversation.id} messageId={message.id} />
                  {uebernehmbar(message) ? <InDieAkte conversationId={data.conversation.id} messageId={message.id} /> : null}
                </div> : null}
                {messageIndex === data.messages.length - 1 && message.metadata?.context?.clarification_choices?.length ? <div className="memory-actions clarification-choices" role="group" aria-label="Antwort auswählen">
                  {message.metadata.context.clarification_choices.map((choice, index) => <button className="memory-reject" disabled={sending || !chatAvailable} key={choice.label} onClick={() => void send(choice.label, { choice: index }).catch(() => undefined)} type="button">{choice.label}</button>)}
                </div> : null}
                {/* Nur unter der letzten Antwort: Ältere Antworten sind Verlauf, danach wurde schon weitergefragt. */}
                {messageIndex === data.messages.length - 1 && message.metadata?.context?.refresh_available && message.metadata.context.original_question ? <div className="memory-actions"><button className="memory-reject" disabled={sending || !chatAvailable} onClick={() => void send(message.metadata!.context!.original_question!, { newQuestion: true }).catch(() => undefined)} type="button">Mit aktuellem Stand neu beantworten</button></div> : null}
                {messageIndex === data.messages.length - 1 && message.metadata?.context?.clarification_date ? <SourceDateForm busy={sending || !chatAvailable} onSubmit={(value) => { const [year, month, day] = value.split("-"); void send(`Die Nachricht stammt vom ${day}.${month}.${year}.`, { date: value }).catch(() => undefined); }} /> : null}
                {message.metadata?.context?.routing && <details><summary>Modell und Arbeitsweise</summary><p>{message.metadata.context.routing.to === "research" ? "Recherche mit begrenzten Lesewerkzeugen" : "Persönlicher Assistent"}</p><p>{message.metadata.context.routing.reason}</p>{message.metadata.context.routing.trace.map((step, index) => <p key={index}>{step.model} · {step.outcome === "success" ? "Antwort erhalten" : step.outcome === "failed" ? "Nicht erreichbar, Alternative geprüft" : "Ausgewählt"}</p>)}</details>}
                {message.status === "error" && !message.metadata?.resolved_approval_id ? <small>Antwort fehlgeschlagen.{" "}<button disabled={sending} onClick={() => void retry(message.id).catch(() => undefined)} type="button">Wiederholen</button></small> : null}
                {data.action_requests?.filter((action) => action.message_id === message.id).map((action) => <ActionApprovalCard key={action.id} action={action} busy={sending} onResolve={resolveAction} />)}
                {candidate ? <section className="memory-candidate" aria-label="Gedächtnisvorschlag">
                  <span>GEDÄCHTNISVORSCHLAG</span>
                  <strong>{candidate.statement}</strong>
                  {candidate.evidence[0] ? <p className="memory-source">Aus diesem Gespräch: „{candidate.evidence[0].quote}“</p> : null}
                  {requiresReplacement ? <div className="memory-conflict"><p>Bestehender Stand:</p>{card?.conflicts.map((conflict) => <p key={conflict.id}>{conflict.statement}</p>)}</div> : null}
                  {candidate.state === "pending" && card?.competing_count ? <p className="memory-notice">Ein abweichender offener Vorschlag wird erst durch deine Entscheidung zurückgestellt.</p> : null}
                  {candidate.state === "accepted" ? <p className="memory-decision" role="status">{memoryDecision}</p> : null}
                  {candidate.state === "rejected" ? <p className="memory-decision">Nicht gespeichert.</p> : null}
                  {candidate.state === "superseded" ? <p className="memory-decision">Durch einen anderen bestätigten Stand ersetzt.</p> : null}
                  <div className="memory-actions">
                    {candidate.state === "pending" ? <>
                    <button className="memory-confirm" disabled={sending} onClick={() => decideMemory(candidate.id, requiresReplacement)} type="button">{requiresReplacement ? "Bestehenden Stand ersetzen" : card?.competing_count ? "Diesen Stand bestätigen" : "Bestätigen"}</button>
                    <button className="memory-reject" disabled={sending} onClick={() => rejectMemory(candidate.id)} type="button">Nicht speichern</button>
                    </> : null}
                    {candidate.state === "accepted" && (card?.claim?.status === "active" || card?.claim?.status === "disputed") ? <button className="memory-reject" disabled={sending} onClick={() => retractMemory(candidate.id)} type="button">Als falsch widerrufen</button> : null}
                    {card?.source_message_id && data.messages.some((item) => item.id === card.source_message_id) ? <button className="memory-reject" onClick={() => showMemorySource(card.source_message_id!)} type="button">Quelle anzeigen</button> : null}
                  </div>
                </section> : null}
              </article>;
            })}
            {correctionSaved && <p className="memory-decision thread-notice" role="status">Berichtigung gespeichert. Die frühere Angabe wird nicht mehr verwendet. Frage erneut nach dem aktuellen Stand.</p>}
            {refreshNotice ? <p className="memory-decision thread-notice" role="status">{refreshNotice}</p> : null}
          </div>
          <div className="thread-command">
            {sendError ? <p className="partial-error thread-send-error" role="alert">Die Nachricht konnte nicht gesendet werden. Bitte erneut versuchen.</p> : null}
            {memoryError ? <p className="partial-error memory-send-error" role="alert">Die Gedächtnisänderung konnte nicht bestätigt werden. Bitte erneut versuchen.</p> : null}
            {sending && <p className="conversation-waiting" role="status" aria-live="polite">Kingfisher antwortet …</p>}
            {!error && data && <ConversationCapture key={`capture-${id}`} />}
            <VoiceDraftStatus voice={voice} /><CommandBar key={id} conversationId={id} voice={voice} busy={sending} conversation disabled={error || !data || !chatAvailable} onSubmit={send} placeholder={chatPlaceholder} />
          </div>
        </section>
      </main>
    </div>
  );
}

function ConversationHistory({ recentConversation, rememberConversation }: {
  recentConversation: string | null;
  rememberConversation: (id: string) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(false);
  const createPending = useRef(false);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  async function create() {
    if (createPending.current) return;
    createPending.current = true;
    setCreating(true); setCreateError(false);
    try {
      const created = await api.createConversation();
      if (!live.current) return;
      rememberConversation(created.conversation.id);
      navigate(`/conversations/${created.conversation.id}`);
    } catch (problem) {
      if (live.current) setCreateError(true);
      throw problem;
    } finally { createPending.current = false; if (live.current) setCreating(false); }
  }
  return <div className="shell conversation-shell">
    <Sidebar active="Gespräche" recentConversation={recentConversation} />
    <main className="conversation-page workspace-chat workspace-chat-start">
      <ConversationNavigation onCreate={create} onSelect={id => navigate(`/conversations/${id}`)} />
      <section className="thread"><div className="conversation-empty"><h1>Was beschäftigt dich?</h1><p>Beginne ein Gespräch oder führe einen Gedanken aus der Liste weiter.</p><button className="secondary-action" type="button" disabled={creating} onClick={() => void create().catch(() => undefined)}>Neues Gespräch beginnen</button>{createError && <p role="alert">Das neue Gespräch konnte nicht angelegt werden. Bitte erneut versuchen.</p>}</div></section>
    </main>
  </div>;
}

type TaskView = "mine" | "waiting" | "done" | "decisions" | "goals";

const TASK_VIEWS: Array<{ id: TaskView; label: string }> = [
  { id: "mine", label: "Meine Aufgaben" },
  { id: "waiting", label: "Warte auf andere" },
  { id: "done", label: "Erledigt" },
  { id: "decisions", label: "Entscheidungen" },
  { id: "goals", label: "Ziele" },
];

function Tasks({ recentConversation }: { recentConversation: string | null }) {
  // Die Aufgabenseite zeigt Aufgaben, nicht Bedienung: Suche filtert beim Tippen, die Liste lädt selbst nach, leere
  // Gruppen und Nullzähler entfallen, „Zur Prüfung“ erscheint nur, wenn etwas zu prüfen ist.
  const [panel,setPanel] = useState<"tasks"|"projects"|"review">(() => new URLSearchParams(window.location.search).get("pruefen") === "1" ? "review" : "tasks");
  const [board,setBoard] = useState(false);
  const [groupTime,setGroupTime] = useState(()=>new Date());
  useEffect(()=>{const id=window.setInterval(()=>setGroupTime(new Date()),60000);return()=>window.clearInterval(id);},[]);
  const [view, setView] = useState<TaskView>(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    return requested === "waiting" || requested === "done" || requested === "decisions" || requested === "goals" ? requested : "mine";
  });
  const [selectedTask, setSelectedTask] = useState(() => new URLSearchParams(window.location.search).get("task"));
  // 0: Aufgabe nur öffnen; sonst eine fortlaufende Nummer, damit jeder Klick auf einen Titel das Bearbeiten öffnet.
  const [detailEdit, setDetailEdit] = useState(0);
  const editRequests = useRef(0);
  const [reviewTotal, setReviewTotal] = useState<number | null>(null);
  const [taskPage, setTaskPage] = useState<TaskPageState>(initialTaskPage);
  const [overviewRevision, setOverviewRevision] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const currentSearch = useRef(search);
  currentSearch.current = search;
  const pager = useRef<TaskPager | null>(null);
  if (!pager.current) pager.current = new TaskPager((selection, cursor) => api.tasks(selection.view, selection.projectId, {q: selection.q, cursor}), setTaskPage);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(() => new URLSearchParams(window.location.search).get("project") ?? "");
  const tasks = taskPage.selectionKey === JSON.stringify({view, projectId, q: search}) ? taskPage.tasks : null;
  // Während Suche oder Änderung neu laden, bleibt die bisherige Liste derselben Ansicht stehen statt zu flackern.
  const listKey = JSON.stringify({view, projectId});
  const shownTasks = useRef<{key: string; tasks: LocalTask[]} | null>(null);
  if (tasks) shownTasks.current = {key: listKey, tasks};
  const listTasks = tasks ?? (taskPage.loading && shownTasks.current?.key === listKey ? shownTasks.current.tasks : null);
  const [newTaskProject, setNewTaskProject] = useState("");
  const [projectError, setProjectError] = useState(false);
  const currentProject = useRef(projectId);
  currentProject.current = projectId;
  const projectRequestVersion = useRef(0);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const taskSave = useRef(new TaskSaveAttempt(undefined, MANUAL_TASK_REQUEST_KEY));
  const [createError, setCreateError] = useState("");
  const [createReviewed, setCreateReviewed] = useState(false);
  const [completing, setCompleting] = useState<string | null>(null);
  const lastLoad = useRef(0);

  const currentView = useRef(view);
  currentView.current = view;

  function openTask(id: string | null, edit = false) {
    setDetailEdit(edit ? ++editRequests.current : 0);
    setSelectedTask(id);
  }

  function loadProjects() {
    const version = ++projectRequestVersion.current;
    setProjectError(false);
    return api.projects().then(items => {
      if (version === projectRequestVersion.current) setProjects(items);
    }).catch(() => {
      if (version === projectRequestVersion.current) setProjectError(true);
    });
  }
  useEffect(() => { loadProjects(); return () => { projectRequestVersion.current++; }; }, []);

  function load(nextView = currentView.current) {
    lastLoad.current = Date.now();
    setOverviewRevision(n=>n+1);
    setError("");
    if (nextView === "decisions" || nextView === "goals") { pager.current!.cancel(); setTaskPage({...initialTaskPage(), tasks: []}); return; }
    void pager.current!.select({view: nextView, projectId: currentProject.current, q: currentSearch.current});
  }

  // Kein Knopf „Liste aktualisieren“: Kommt das Fenster wieder in den Blick, lädt die Liste still nach (wie Heute).
  useEffect(() => {
    const again = () => {
      if (document.visibilityState === "hidden" || Date.now() - lastLoad.current < 15000) return;
      if (currentView.current === "decisions" || currentView.current === "goals") return;
      lastLoad.current = Date.now();
      void pager.current!.reload();
    };
    window.addEventListener("focus", again);
    document.addEventListener("visibilitychange", again);
    return () => { window.removeEventListener("focus", again); document.removeEventListener("visibilitychange", again); };
  }, []);

  // Die Suche filtert beim Tippen (entprellt); Enter sucht sofort.
  useEffect(() => {
    const next = searchInput.trim();
    if (next === currentSearch.current) return;
    const id = window.setTimeout(() => setSearch(next), 300);
    return () => window.clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("view", view);
    if (selectedTask) url.searchParams.set("task", selectedTask);
    else url.searchParams.delete("task");
    if (projectId) url.searchParams.set("project", projectId);
    else url.searchParams.delete("project");
    window.history.replaceState(window.history.state, "", url);
  }, [view, projectId, selectedTask]);

  useEffect(() => { load(view); return () => { pager.current!.cancel(); }; }, [view, projectId, search]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const attempt = taskSave.current;
    if (submitting || attempt.inFlight || attempt.succeeded || !title.trim()) return;
    setSubmitting(true);
    setCreateError("");
    setCreateReviewed(false);
    try {
      const task = await attempt.save({ title: title.trim(), ...(newTaskProject ? { project_id: newTaskProject } : {}), ...(due ? { due: endOfTaskDay(due) } : {}) }, api.addTask);
      if (!task) return;
      openTask(task.id);
      setProjectId(newTaskProject);
      setTitle("");
      setDue("");
      setCreating(false);
      if (view === "mine") load("mine");
      else setView("mine");
    } catch (cause) {
      setCreateError(cause instanceof TaskSavePreparationError ? `${cause.message} Es wurde keine Aufgabe gesendet.` : cause instanceof ApiError && cause.status === 409 ? (cause.detail ?? TASK_SAVE_UNCONFIRMED) : TASK_SAVE_UNCONFIRMED);
    } finally {
      setSubmitting(false);
    }
  }

  async function complete(taskId: string, reopen = false) {
    if (completing) return;
    setCompleting(taskId);
    setError("");
    try {
      if (reopen) await api.reopenTask(taskId);
      else await api.completeTask(taskId);
      load();
    } catch {
      setError("Der Aufgabenstatus konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setCompleting(null);
    }
  }

  async function rueckgaengig(taskId: string) {
    if (completing) return;
    setCompleting(taskId); setError("");
    try { await api.taskRueckgaengig(taskId); load(); }
    catch { setError("Das ließ sich gerade nicht zurücknehmen. Bitte erneut versuchen."); }
    finally { setCompleting(null); }
  }

  async function wait(taskId: string, name?: string) {
    if (completing) return;
    setCompleting(taskId); setError("");
    try {
      if (name) await api.waitTask(taskId, name);
      else await api.unwaitTask(taskId);
      load();
    } catch { setError("Der Wartestatus konnte nicht gespeichert werden."); }
    finally { setCompleting(null); }
  }

  async function assignProject(taskId: string, selectedProject: string) {
    if (completing) return;
    setCompleting(taskId); setError("");
    try { await api.assignTaskProject(taskId, selectedProject || null); load(); }
    catch { setError("Die Projektzuordnung konnte nicht gespeichert werden."); }
    finally { setCompleting(null); }
  }

  async function editTask(taskId: string, data: {title?: string; due?: string | null; remind_at?: string | null; expected_remind_at?: string | null; notes?: string | null}) {
    if (completing) return false;
    setCompleting(taskId); setError("");
    try { await api.editTask(taskId, data); load(); return true; }
    catch { setError("Die Aufgabenänderung konnte nicht gespeichert werden."); return false; }
    finally { setCompleting(null); }
  }

  function startTask() {
    if (creating || taskSave.current.inFlight) { setPanel("tasks"); return; }
    taskSave.current = new TaskSaveAttempt(undefined, MANUAL_TASK_REQUEST_KEY);
    setTitle(""); setDue(""); setCreateReviewed(false);
    try {setCreateError(taskSave.current.restore() ? TASK_SAVE_PENDING : "");}
    catch (cause) {setCreateError(`${cause instanceof Error ? cause.message : 'Der lokale Speicher ist nicht verfügbar.'} Es wurde keine Aufgabe gesendet.`);}
    if (view === "decisions") setView("mine"); setPanel("tasks"); setNewTaskProject(projectId); setCreating(true);
  }
  function prepareNewTaskRequest() {
    if (!createReviewed || submitting || taskSave.current.inFlight) return;
    try {taskSave.current.resetAfterReview(); setCreateReviewed(false); setCreateError("");}
    catch {setCreateError('Der neue Speicherauftrag konnte nicht vorbereitet werden. Bitte den lokalen Speicher und andere offene Aufgabenfenster prüfen. Es wurde keine Aufgabe gesendet.');}
  }
  function openProjectView(nextView: "mine" | "waiting" | "done", taskId: string | null = null) {
    currentSearch.current = '';
    setSearchInput(''); setSearch(''); openTask(taskId); setView(nextView);
    load(nextView);
  }
  const visibleTasks = listTasks?.filter(task => (!projectId || task.project_id === projectId));
  const listView = view === "mine" || view === "waiting" || view === "done";

  const heading = TASK_VIEWS.find((item) => item.id === view)?.label ?? "Meine Aufgaben";
  // Reiter bleiben alle erreichbar; „Zur Prüfung“ nur, wenn etwas zu prüfen ist (sonst über „Gedächtnis prüfen“).
  const tabs: Array<{id: string; label: string; count?: number}> = [...TASK_VIEWS, {id: "projects", label: "Projekte"},
    ...(panel === "review" || (reviewTotal ?? 0) > 0 ? [{id: "review", label: "Zur Prüfung", count: reviewTotal ?? 0}] : [])];
  const activeTab = panel === "tasks" ? view : panel;
  function chooseTab(id: string) {
    if (id === "projects") { setView("mine"); setPanel("projects"); }
    else if (id === "review") { openTask(null); setView("mine"); setPanel("review"); }
    else { setPanel("tasks"); setView(id as TaskView); }
  }
  // Rollt die Reiterzeile, bleibt der gewählte Reiter im Blick.
  const tabBar = useRef<HTMLElement | null>(null);
  useEffect(() => { tabBar.current?.querySelector<HTMLElement>('[aria-pressed="true"]')?.scrollIntoView?.({block: "nearest", inline: "nearest"}); }, [activeTab]);
  const row = (task: LocalTask) => <TaskRow compact onOpen={() => openTask(task.id, true)} showProjectName={!projectId} projects={projects} onProjectChange={id => assignProject(task.id, id)} onEdit={data => editTask(task.id, data)} completing={completing !== null} key={task.id} onWait={name=>wait(task.id,name)} onComplete={()=>complete(task.id,task.status==="done")} onRueckgaengig={()=>void rueckgaengig(task.id)} task={task} view={view as "mine" | "waiting" | "done"} />;
  const emptyText = search ? 'Keine passenden Aufgaben für diese Suche.' : selectedTask ? "Keine weiteren Aufgaben auf dieser Seite." : view === "mine" ? "Keine offenen Aufgaben für dich." : view === "waiting" ? "Aktuell wartest du auf niemanden." : "Noch keine erledigten Aufgaben.";
  return <div className="shell tasks-shell">
    <Sidebar active="Aufgaben" recentConversation={recentConversation} />
    <main className="tasks-page workspace-tasks">
      <header className="tasks-heading"><p className="eyebrow">AUFGABEN</p><h1>{panel === "projects" ? "Projekte" : panel === "review" ? "Zur Prüfung" : heading}</h1>{view !== "decisions" && view !== "goals" ? <button className="tasks-add" disabled={submitting} onClick={startTask} type="button"><img src={icon("plus", "Outline")} alt="" />Aufgabe</button> : null}</header>
      {selectedTask && <DetailPanel title="Aufgabe" onClose={() => openTask(null)}>
        <TaskDetail key={`${selectedTask}:${detailEdit}`} taskId={selectedTask} editing={detailEdit > 0} onChanged={() => load()} />
      </DetailPanel>}
      <nav ref={tabBar} aria-label="Aufgabenansichten" className="task-tabs">{tabs.map((item) => <button aria-pressed={activeTab === item.id} className={activeTab === item.id ? "active" : ""} key={item.id} onClick={() => chooseTab(item.id)} type="button">{item.label}{item.count ? ` · ${item.count}` : ""}</button>)}</nav>
      <section className="workspace-projects" aria-label="Projekte" hidden={panel !== "projects"}>
        {panel === "projects" && (projects.length ? <div className="workspace-project-list">{projects.map(project=><button type="button" key={project.id} aria-pressed={projectId===project.id} onClick={()=>setProjectId(project.id)}><strong>{project.name}</strong><span>{project.status === "done" ? "Erledigt" : project.status === "dropped" ? "Verworfen" : project.status === "paused" ? "Pausiert" : project.status === "idea" ? "Idee" : "Aktiv"}</span>{project.description && <small>{project.description}</small>}</button>)}</div> : projectError ? null : <p className="task-empty">Noch keine Projekte.</p>)}
        {projectError ? <p className="tasks-error">Projekte sind gerade nicht erreichbar. <button type="button" onClick={loadProjects}>Erneut laden</button></p> : <ProjectControls contextRevision={overviewRevision} projects={projects} selectedId={projectId} onSelect={setProjectId} onChanged={loadProjects} />}
        {panel === "projects" && projectId && <div className="workspace-project-actions"><button type="button" aria-pressed={!board} onClick={()=>setBoard(false)}>Liste</button><button type="button" aria-pressed={board} onClick={()=>setBoard(true)}>Board</button><a href={`/memory/projects/${encodeURIComponent(projectId)}`}>Im Gedächtnis öffnen</a></div>}
        {panel === "projects" && projectId && board && <ProjectBoard projectId={projectId} revision={overviewRevision} onTask={task=>openTask(task.id)} />}
      </section>
      <div className="task-review" hidden={panel !== "review"}>
        <TaskSuggestions projects={projects} onTotal={setReviewTotal} onPreview={()=>openTask(null)} onAccepted={task => { loadProjects(); setPanel("tasks"); openTask(task.id); setProjectId(task.project_id ?? ""); setView(task.wartet_auf ? "waiting" : "mine"); load(task.wartet_auf ? "waiting" : "mine"); }} />
        {panel === "review" && reviewTotal === 0 ? <p className="task-empty">Nichts zu prüfen.</p> : null}
      </div>
      {panel === "tasks" && (view === "mine" || view === "waiting") && <AufgabenPostVorschlaege onChanged={task => { load(); if (task) openTask(task.id); }} />}
      {error ? <p className="tasks-error">{error} <button onClick={() => load()} type="button">Wiederholen</button></p> : null}
      {panel !== "review" && (listView || (view === "decisions" && (projects.length > 0 || projectError))) && <form className="task-search" role="search" onSubmit={event => {event.preventDefault(); setSearch(searchInput.trim());}}>
        {listView && <input type="search" aria-label="Aufgaben durchsuchen" maxLength={200} value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Aufgaben durchsuchen" />}
        {panel === "projects" ? null : projectError ? <p className="tasks-error">Projekte sind gerade nicht erreichbar. <button type="button" onClick={loadProjects}>Erneut laden</button></p> : projects.length > 0 && <select aria-label="Projekt" className="task-project-filter" value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Alle Projekte</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>}
      </form>}
      {panel !== "review" && listView && <ProjectOverview key={projectId} projectId={projectId} revision={overviewRevision} onView={nextView=>openProjectView(nextView)} onTask={(id,nextView)=>openProjectView(nextView,id)} />}
      {panel !== 'review' && listView && <>
        {taskPage.error && <p role="alert" className="tasks-error">{taskPage.error} <button type="button" onClick={() => load()}>Erneut laden</button></p>}
        {taskPage.notice && <p role="status">{taskPage.notice}</p>}
        {search && tasks && tasks.length > 0 ? <p role="status" className="task-count">{taskPage.total} Treffer</p> : null}
      </>}
      {view === "goals" ? <><GoalControls /><HabitControls /></> : view === "decisions" ? <DecisionControls key={projectId} projectId={projectId} kopf={false} /> : <section className="task-table" aria-label={heading} hidden={panel === "review" || (panel === "projects" && board && Boolean(projectId))}>
        {creating ? <form className="task-create" onSubmit={create}>{createError && <p className="tasks-error" role="alert">{createError} <button disabled={submitting} type="submit">Wiederholen</button></p>}{createError && <TaskRetryReview reviewed={createReviewed} busy={submitting} onReviewed={setCreateReviewed} onPrepareNew={prepareNewTaskRequest} />}<label>Aufgabe<input autoFocus disabled={submitting} onChange={(event) => setTitle(event.target.value)} placeholder="Was möchtest du erledigen?" required value={title} /></label><label>Fällig am<input disabled={submitting} onChange={(event) => setDue(event.target.value)} type="date" value={due} /></label>{projects.some(project => project.open) && <label className="task-project-create">Projekt<select value={newTaskProject} onChange={event => setNewTaskProject(event.target.value)} disabled={submitting || projectError}><option value="">Ohne Projekt</option>{projects.filter(project=>project.open).map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}<div><button className="secondary-action" disabled={submitting} onClick={() => setCreating(false)} type="button">Abbrechen</button><button className="primary-action" disabled={submitting || !title.trim()} type="submit">Lokal speichern</button></div></form> : null}
        {!listTasks && !error && taskPage.loading ? <div className="task-loading" role="status" aria-label="Aufgaben werden geladen"><i /><i /><i /></div> : null}
        {visibleTasks && visibleTasks.length > 0 && (view === "mine"
          ? visibleTaskGroups(visibleTasks,groupTime).map(group=><section className="workspace-task-group" key={group.label} aria-label={group.label}><h2>{group.label} <small>{group.items.length}</small></h2>{group.items.map(row)}</section>)
          : <section className="workspace-task-group" aria-label={heading}>{visibleTasks.map(row)}</section>)}
        {visibleTasks && visibleTasks.length === 0 && !creating ? <p className="task-empty">{emptyText}</p> : null}
        {(taskPage.canPrevious || taskPage.canNext) && <nav aria-label="Aufgabenseiten"><button type="button" className="secondary-action" disabled={!taskPage.canPrevious || completing !== null} onClick={() => void pager.current!.previous()}>Vorherige Seite</button><span className="task-page-number">Seite {taskPage.page}</span><button type="button" className="secondary-action" disabled={!taskPage.canNext || completing !== null} onClick={() => void pager.current!.next()}>Nächste Seite</button></nav>}
      </section>}
    </main>
  </div>;
}

export function App() {
  const [path, setPath] = useState(window.location.pathname);
  const erstePruefung = useErststartWeiterleitung(path);
  const [chatAvailable, setChatAvailable] = useState<boolean | null>(null);
  const [recentConversation, setRecentConversation] = useState<string | null>(
    () => localStorage.getItem("kingfisher-last-conversation"),
  );
  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  useEffect(() => {
    let active = true;
    api.status().then(({ chat }) => {
      if (active) setChatAvailable(chat);
    }).catch(() => {
      if (active) setChatAvailable(false);
    });
    return () => { active = false; };
  }, [path]);

  useEffect(() => {
    let active = true;
    api.latestConversation().then(({ conversation }) => {
      if (!active) return;
      setRecentConversation(conversation?.id ?? null);
      if (conversation) localStorage.setItem("kingfisher-last-conversation", conversation.id);
      else localStorage.removeItem("kingfisher-last-conversation");
    }).catch(() => {
      // Bei einem kurzfristigen Verbindungsfehler bleibt der zuletzt bekannte
      // SQLite-Einstieg sichtbar; beim nächsten Laden wird er erneut geprüft.
    });
    return () => { active = false; };
  }, []);

  function rememberConversation(id: string) {
    setRecentConversation(id);
    localStorage.setItem("kingfisher-last-conversation", id);
  }

  const chatPlaceholder = chatAvailable === true ? undefined : chatAvailable === null
    ? "Kingfisher wird verbunden …"
    : "Frage nach Projekten und Quellen. Für freie Gespräche ein Modell verbinden.";

  if (path === "/willkommen") return <Erststart />;
  if (erstePruefung) return <div className="shell"><main className="state-page" aria-busy="true" /></div>;
  if (path === "/calendar") return <CalendarPage recentConversation={recentConversation} />;
  if (path === '/review') return <ReviewPage recentConversation={recentConversation} />;
  if (path === '/wellbeing') return <HealthPage recentConversation={recentConversation} />;
  if (path === '/development') return <DevelopmentPage recentConversation={recentConversation} />;
  if (path === "/settings") return <EinstellungenSeite recentConversation={recentConversation} />;
  if (path === "/world") return <WorldPage recentConversation={recentConversation} />;
  if (path === "/vorhaben") return <Tasks recentConversation={recentConversation} />;
  if (path === "/nachrichten") return <Messages recentConversation={recentConversation} />;
  if (path === "/conversations") return <ConversationHistory recentConversation={recentConversation} rememberConversation={rememberConversation} />;
  const match = path.match(/^\/conversations\/([^/]+)$/);
  if (match) return <Conversation key={decodeURIComponent(match[1])} chatAvailable={chatAvailable !== null} chatPlaceholder={chatPlaceholder} id={decodeURIComponent(match[1])} recentConversation={recentConversation} rememberConversation={rememberConversation} />;
  const personMatch = path.match(/^\/memory\/people\/([^/]+)$/);
  if (personMatch) return <MemoryProfile identifier={decodeURIComponent(personMatch[1])} kind="person" recentConversation={recentConversation} />;
  const projectMatch = path.match(/^\/memory\/projects\/([^/]+)$/);
  if (projectMatch) return <MemoryProfile identifier={decodeURIComponent(projectMatch[1])} kind="project" recentConversation={recentConversation} />;
  const akteMatch = path.match(/^\/memory\/akte\/([^/]+)$/);
  if (akteMatch) return <SachenAkte sache={decodeURIComponent(akteMatch[1])} recentConversation={recentConversation} />;
  const registryMatch = path.match(/^\/memory\/registry\/([^/]+)$/);
  if (registryMatch) return <RegistryProfile key={registryMatch[1]} identifier={decodeURIComponent(registryMatch[1])} recentConversation={recentConversation} />;
  if (path === "/memory") return <MemoryGraph recentConversation={recentConversation} />;
  if (path !== "/today") window.history.replaceState({}, "", "/today");
  return <Morning chatAvailable={chatAvailable !== null} chatPlaceholder={chatPlaceholder} recentConversation={recentConversation} rememberConversation={rememberConversation} />;
}
