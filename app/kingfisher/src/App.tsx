import {useConversationVoice, VoiceDraftControls, VoiceDraftStatus, VoiceReply, recordingVoice, type ConversationVoice} from "./ConversationVoice";
import { TodayOverview, TodayPersonal, todayAttention } from "./TodayOverview";
import { FassungHeute } from "./Fassung";
import { InterfaceIcon } from "./InterfaceIcon";
import { AudioBriefing } from "./AudioBriefing";
import { Erststart } from "./Einrichtung/Erststart";
import { HeuteLeer } from "./Einrichtung/HeuteLeer";
import { useErststartWeiterleitung } from "./Einrichtung/useErststartWeiterleitung";
import { TaskSuggestions } from "./TaskSuggestions";
import { BriefingSuggestion } from "./BriefingSuggestion";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ApiError,
  type ConversationPayload,
  type ConversationSummary,
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
import { verbindungenPruefen } from "./verbindungen";
import { Verweis } from "./VerweisLink";
import { tastenHinweis } from "./system";
import { useEingabegeraet } from "./useSystem";
import { zaehlerText } from "./heute";
import { PostfachStand } from "./PostfachStand";
import { TodaySourceStatus } from "./TodaySourceStatus";
import { createDailyRefresh } from "./dailyFlow";
import { MailReader } from "./MailReader";



function dateParts(value: string, timeZone?: string) {
  const date = new Date(value);
  // In der Zeitzone des Briefings (der eingestellten), nicht der des Browsers; eine unbekannte Zone fällt zurück.
  const zone = timeZone && (() => { try { new Intl.DateTimeFormat("de-DE", { timeZone }); return timeZone; } catch { return undefined; } })();
  const weekday = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: zone }).format(date).replace(".", "");
  const day = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "long", year: "numeric", timeZone: zone }).format(date);
  const time = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: zone }).format(date);
  return { date: `${weekday}, ${day}`, time };
}


function conversationTime(value: string) {
  const date = new Date(value);
  const today = new Date();
  const start = (item: Date) => new Date(item.getFullYear(), item.getMonth(), item.getDate()).getTime();
  const days = Math.round((start(today) - start(date)) / 86_400_000);
  const time = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
  if (days === 0) return time;
  if (days === 1) return "Gestern";
  return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "short" }).format(date).replace(".", "");
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

function CommandBar({ onSubmit, busy = false, conversation = false, disabled = false, placeholder, voice }: {
  onSubmit: (message: string) => Promise<void>;
  busy?: boolean;
  conversation?: boolean;
  disabled?: boolean;
  placeholder?: string;
  voice?: ConversationVoice;
}) {
  const [message, setMessage] = useState("");
  const recording = voice ? recordingVoice(voice.state) : false;
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if ((busy || disabled) && recording) voice?.cancel(); }, [busy, disabled, recording, voice]);
  // Der Hinweis passt zum Gerät: „⌘ K“ auf dem Mac, „Strg K“ sonst, keiner auf dem Telefon (Fremdprobe 2, Befund 11).
  const taste = tastenHinweis(useEingabegeraet());

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const clean = message.trim();
    if (!clean || busy || disabled || recording) return;
    voice?.cancel();
    try {
      await onSubmit(clean);
      setMessage("");
    } catch {
      // Der aufrufende Screen zeigt den Fehler in der bestehenden Fläche.
    }
  }

  return (
    <form className={`command-bar ${conversation ? "conversation-command" : ""}`} onSubmit={submit}>
      {!conversation ? <InterfaceIcon name="search" /> : null}
      <input
        aria-label="Kingfisher fragen"
        disabled={busy || disabled || recording}
        onChange={(event) => setMessage(event.target.value)}
        placeholder={placeholder ?? (conversation ? "Nachricht oder Befehl …" : "Frag Kingfisher etwas …    z. B. „Bereite mich auf meinen Termin um 11:30 vor“")}
        ref={input}
        value={message}
      />
      {!conversation && taste ? <kbd>{taste}</kbd> : null}
      {voice ? <VoiceDraftControls voice={voice} disabled={busy || disabled} base={message} onDraft={setMessage} /> : null}
      <button aria-label="Nachricht senden" className="send-button" disabled={!message.trim() || busy || disabled || recording} type="submit">
        <InterfaceIcon name="arrow-up" />
      </button>
    </form>
  );
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


function BriefingDrawer({ briefing, open, onClose, onChange }: {
  briefing: MorningBriefing;
  open: boolean;
  onClose: () => void;
  onChange: (change?: "correction") => void;
}) {
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
      <button aria-label="Briefing schließen" className={`scrim ${open ? "open" : ""}`} onClick={onClose} type="button" />
      <section aria-hidden={!open} aria-label="Briefing" className={`briefing-drawer ${open ? "open" : ""}`}>
        <button className="drawer-close" onClick={onClose} type="button">
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
                  <span><strong>{item.title}</strong>{item.reason && item.reason !== item.title && <small>{item.reason}</small>}<small>{item.detail}</small></span><em>{item.priority}</em>
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
      <Sidebar active="Heute" briefingOpen={briefingOpen} onToday={() => setBriefingOpen(true)} recentConversation={recentConversation} />
      <main className="morning-page today-page">
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
          {briefing.post_ausstehend ? <p className="today-post-laedt" role="status">Deine Post wird gerade geholt …</p> : <PostfachStand />}
          {briefing.partial_failures.length > 0 && <details className="today-connection-note"><summary>Quellen teilweise nicht verfügbar ({briefing.partial_failures.length})</summary>
            {briefing.partial_failures.map(failure => <p key={failure.section}>{failure.message}</p>)}
            <a className="today-text-link" href={verbindungenPruefen(briefing.partial_failures)}>Verbindungen prüfen →</a>
          </details>}
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
  const [data, setData] = useState<ConversationPayload | null>(null);
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
      <main className="conversation-page">
        <aside className="context-panel">
          <p className="eyebrow">KONTEXT</p><h2>{data?.conversation.title ?? "Gespräch"}</h2><p className="context-caption">Lokales Gedächtnis</p>
          <div className="context-list">{contextLines.length ? contextLines.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : data?.context.source_links?.length ? <p>{data.context.source_links.length} Originalquelle(n) zur Prüfung. Keine bestätigte Aussage.</p> : <p>{kontextLeerSatz(data?.messages ?? [])}</p>}</div>
        </aside>
        <section className="thread">
          <header className="thread-header"><div><p className="eyebrow">GESPRÄCH</p><h1>{data?.conversation.title ?? "Gespräch"}</h1></div><span className="local-status"><i /> Lokal gespeichert</span></header>
          <div className="messages">
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
                {message.metadata?.context?.satzantwort ? <SatzAntwort daten={message.metadata.context.satzantwort} onChange={load} /> : <p>{message.content}</p>}
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
                {message.status === "error" && !message.metadata?.resolved_approval_id ? <small>Antwort fehlgeschlagen.{" "}<button disabled={sending} onClick={() => retry(message.id)} type="button">Wiederholen</button></small> : null}
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
          {sendError ? <p className="partial-error thread-send-error">Die Nachricht konnte nicht gesendet werden. Bitte erneut versuchen.</p> : null}
          {memoryError ? <p className="partial-error memory-send-error" role="alert">Die Gedächtnisänderung konnte nicht bestätigt werden. Bitte erneut versuchen.</p> : null}
          <div className="thread-command"><VoiceDraftStatus voice={voice} /><CommandBar key={id} voice={voice} busy={sending} conversation disabled={error || !data || !chatAvailable} onSubmit={send} placeholder={chatPlaceholder} /></div>
        </section>
      </main>
    </div>
  );
}

function ConversationHistory({ recentConversation, rememberConversation }: {
  recentConversation: string | null;
  rememberConversation: (id: string) => void;
}) {
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);

  function load() {
    setError(false);
    api.listConversations().then(({ conversations }) => setItems(conversations)).catch(() => setError(true));
  }

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("de-DE");
    if (!needle) return items ?? [];
    return (items ?? []).filter((item) => `${item.title} ${item.preview}`.toLocaleLowerCase("de-DE").includes(needle));
  }, [items, query]);

  async function create() {
    if (creating) return;
    setCreating(true);
    try {
      const data = await api.createConversation();
      rememberConversation(data.conversation.id);
      navigate(`/conversations/${data.conversation.id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="shell conversation-list-shell">
      <Sidebar active="Gespräche" recentConversation={recentConversation} />
      <main className="conversation-history">
        <header className="history-heading"><h1>Gespräche</h1><p>Gedanken weiterführen. Zusammenhänge wiederfinden.</p></header>
        <header className="history-tools">
          <label className="history-search">
            <img src={icon("search", "Outline")} alt="" />
            <input aria-label="Gespräche durchsuchen" onChange={(event) => setQuery(event.target.value)} placeholder="Suche in Gesprächen…" value={query} />
          </label>
          <button aria-label="Neues Gespräch" className="history-create" disabled={creating} onClick={create} type="button"><InterfaceIcon name="plus" />Neues Gespräch</button>
        </header>
        <section className="history-list" aria-label="Gesprächshistorie">
          {error ? <div className="history-error"><p>Die Gesprächshistorie ist gerade nicht erreichbar.</p><button onClick={load} type="button">Wiederholen</button></div> : null}
          {!error && !items ? Array.from({ length: 6 }, (_, index) => <div className="history-row history-skeleton" key={index}><i /><i /></div>) : null}
          {!error ? filtered.map((item) => <button className="history-row" key={item.id} onClick={() => navigate(`/conversations/${item.id}`)} type="button">
            <span className="history-copy"><strong>{item.title}</strong>{item.preview ? <small>{item.preview}</small> : null}</span>
            <span className="history-meta"><time dateTime={item.updated_at}>{conversationTime(item.updated_at)}</time><small>{item.message_count} {item.message_count === 1 ? "Nachricht" : "Nachrichten"}</small></span>
          </button>) : null}
          {!error && items && !filtered.length ? <div className="history-empty">
            {items.length ? <p>Kein Gespräch passt zu „{query.trim()}“.</p>
              : <><p>Noch keine Gespräche. Frag Kingfisher etwas, es antwortet mit Quellen aus deinem Bestand.</p>
                <button className="secondary-action" disabled={creating} onClick={create} type="button">Neues Gespräch beginnen</button></>}
          </div> : null}
        </section>
      </main>
    </div>
  );
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
  const [view, setView] = useState<TaskView>(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    return requested === "waiting" || requested === "done" || requested === "decisions" || requested === "goals" ? requested : "mine";
  });
  const [selectedTask, setSelectedTask] = useState(() => new URLSearchParams(window.location.search).get("task"));
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
  const [completing, setCompleting] = useState<string | null>(null);

  const currentView = useRef(view);
  currentView.current = view;

  function loadProjects() {
    const version = ++projectRequestVersion.current;
    setProjectError(false);
    api.projects().then(items => {
      if (version === projectRequestVersion.current) setProjects(items);
    }).catch(() => {
      if (version === projectRequestVersion.current) setProjectError(true);
    });
  }
  useEffect(() => { loadProjects(); return () => { projectRequestVersion.current++; }; }, []);

  function load(nextView = currentView.current) {
    setOverviewRevision(n=>n+1);
    setError("");
    if (nextView === "decisions" || nextView === "goals") { pager.current!.cancel(); setTaskPage({...initialTaskPage(), tasks: []}); return; }
    void pager.current!.select({view: nextView, projectId: currentProject.current, q: currentSearch.current});
  }

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
    if (submitting || !title.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const task = await api.addTask({ title: title.trim(), ...(newTaskProject ? { project_id: newTaskProject } : {}), ...(due ? { due: endOfTaskDay(due) } : {}) });
      setSelectedTask(task.id);
      setProjectId(newTaskProject);
      setTitle("");
      setDue("");
      setCreating(false);
      if (view === "mine") load("mine");
      else setView("mine");
    } catch {
      setError("Die Aufgabe konnte nicht gespeichert werden. Bitte erneut versuchen.");
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

  function startTask() { if (view === "decisions") setView("mine"); setNewTaskProject(projectId); setCreating(true); }
  function openProjectView(nextView: "mine" | "waiting" | "done", taskId: string | null = null) {
    currentSearch.current = '';
    setSearchInput(''); setSearch(''); setSelectedTask(taskId); setView(nextView);
    load(nextView);
  }
  const visibleTasks = tasks?.filter(task => task.id !== selectedTask && (!projectId || task.project_id === projectId));

  const heading = TASK_VIEWS.find((item) => item.id === view)?.label ?? "Meine Aufgaben";
  return <div className="shell tasks-shell">
    <Sidebar active="Aufgaben" recentConversation={recentConversation} />
    <main className="tasks-page">
      <header className="tasks-heading"><p className="eyebrow">AUFGABEN</p><h1>{heading}</h1>{view !== "decisions" && view !== "goals" ? <button className="tasks-add" onClick={startTask} type="button"><img src={icon("plus", "Outline")} alt="" />Aufgabe</button> : null}</header>
      {selectedTask && <section className="task-selected" aria-label="Ausgewählte Aufgabe">
        <h2>Ausgewählte Aufgabe</h2>
        <TaskDetail key={selectedTask} taskId={selectedTask} onChanged={() => load()} />
        <button type="button" className="secondary-action" onClick={() => {setSelectedTask(null); const url = new URL(window.location.href); url.searchParams.delete("task"); window.history.replaceState(window.history.state, "", url);}}>Zur Aufgabenliste</button>
      </section>}
      <nav aria-label="Aufgabenansichten" className="task-tabs">{TASK_VIEWS.map((item) => <button aria-pressed={view === item.id} className={view === item.id ? "active" : ""} key={item.id} onClick={() => setView(item.id)} type="button">{item.label}</button>)}</nav>
      {view !== "goals" && (projectError ? <p className="tasks-error">Projekte sind gerade nicht erreichbar. <button type="button" onClick={loadProjects}>Erneut laden</button></p> : <ProjectControls projects={projects} selectedId={projectId} onSelect={setProjectId} onChanged={loadProjects} />)}
      {(view === "mine" || view === "waiting") && <TaskSuggestions projects={projects} initiallyExpanded={new URLSearchParams(window.location.search).get("pruefen") === "1"} onAccepted={task => { setSelectedTask(task.id); setProjectId(task.project_id ?? ""); setView(task.wartet_auf ? "waiting" : "mine"); load(task.wartet_auf ? "waiting" : "mine"); }} />}
      {(view === "mine" || view === "waiting" || view === "done") && <ProjectOverview key={projectId} projectId={projectId} revision={overviewRevision} onView={nextView=>openProjectView(nextView)} onTask={(id,nextView)=>openProjectView(nextView,id)} />}
      {error ? <p className="tasks-error">{error} <button onClick={() => load()} type="button">Wiederholen</button></p> : null}
      {(view === 'mine' || view === 'waiting' || view === 'done') && <>
        <form className="task-search" role="search" onSubmit={event => {event.preventDefault(); setSearch(searchInput.trim());}}>
          <label>Aufgaben durchsuchen<input type="search" maxLength={200} value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Titel, Notiz oder wartende Person" /></label>
          <button type="submit" className="secondary-action">Suchen</button>
          {search && <button type="button" className="text-action" onClick={() => {setSearchInput(''); setSearch('');}}>Suche löschen</button>}
          <button type="button" className="text-action" disabled={taskPage.loading} onClick={() => load()}>Liste aktualisieren</button>
        </form>
        {taskPage.error && <p role="alert" className="tasks-error">{taskPage.error} <button type="button" onClick={() => load()}>Erneut laden</button></p>}
        {taskPage.notice && <p role="status">{taskPage.notice}</p>}
        {tasks && <p role="status">{taskPage.total} {search ? 'passende' : ''} Aufgaben · Seite {taskPage.page}{search ? ` · Suche: ${search}` : ''}</p>}
      </>}
      {view === "goals" ? <><GoalControls /><HabitControls /></> : view === "decisions" ? <DecisionControls key={projectId} projectId={projectId} /> : <section className="task-table" aria-label={heading}>
        <header><span>Aufgabe</span><span>Fällig</span></header>
        {creating ? <form className="task-create" onSubmit={create}><label>Aufgabe<input autoFocus onChange={(event) => setTitle(event.target.value)} placeholder="Was möchtest du erledigen?" required value={title} /></label><label>Fällig am <small>(optional)</small><input onChange={(event) => setDue(event.target.value)} type="date" value={due} /></label><label className="task-project-create">Projekt <small>(optional)</small><select value={newTaskProject} onChange={event => setNewTaskProject(event.target.value)} disabled={submitting || projectError}><option value="">Ohne Projekt</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}{!project.open ? " (geschlossen)" : ""}</option>)}</select></label><div><button className="secondary-action" disabled={submitting} onClick={() => setCreating(false)} type="button">Abbrechen</button><button className="primary-action" disabled={submitting || !title.trim()} type="submit">Lokal speichern</button></div></form> : null}
        {!tasks && !error && taskPage.loading ? <div className="task-loading" role="status" aria-label="Aufgaben werden geladen"><i /><i /><i /></div> : null}
        {visibleTasks?.map((task) => <TaskRow projects={projects} onProjectChange={id => assignProject(task.id, id)} onEdit={data => editTask(task.id, data)} completing={completing !== null} key={task.id} onWait={(name) => wait(task.id, name)} onComplete={() => complete(task.id, task.status === "done")} task={task} view={view} />)}
        {visibleTasks && visibleTasks.length === 0 ? <div className="task-empty"><p>{search ? 'Keine passenden Aufgaben für diese Suche.' : selectedTask ? "Keine weiteren Aufgaben auf dieser Seite." : view === "mine" ? "Keine offenen Aufgaben für dich." : view === "waiting" ? "Aktuell wartest du auf niemanden." : "Noch keine erledigten Aufgaben."}</p>{view === "mine" && !creating ? <button onClick={startTask} type="button">Aufgabe anlegen</button> : null}</div> : null}
        {(taskPage.canPrevious || taskPage.canNext) && <nav aria-label="Aufgabenseiten"><button type="button" className="secondary-action" disabled={!taskPage.canPrevious || completing !== null} onClick={() => void pager.current!.previous()}>Vorherige Seite</button><button type="button" className="secondary-action" disabled={!taskPage.canNext || completing !== null} onClick={() => void pager.current!.next()}>Nächste Seite</button></nav>}
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
  if (match) return <Conversation chatAvailable={chatAvailable !== null} chatPlaceholder={chatPlaceholder} id={decodeURIComponent(match[1])} recentConversation={recentConversation} rememberConversation={rememberConversation} />;
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
