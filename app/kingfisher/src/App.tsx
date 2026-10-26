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
import {Bestaetigung, Seitenkopf, Segmente, Gruppe, Zeile, Leer, zeigeHinweis, type Segment} from "./grundlage";
import { erledigtHinweis, POST_ZURUECK, wartetHinweis, wiederOffenHinweis, zurueckZuMirHinweis } from "./aufgabenHinweis";
import {ProjectBoard} from "./ProjectBoard";
import {heuteKopfZeile, visibleTaskGroups} from "./taskWorkspaceModel";
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
import { PostfachStand } from "./PostfachStand";
import { TodaySourceStatus } from "./TodaySourceStatus";
import { createDailyRefresh } from "./dailyFlow";
import { MailReader } from "./MailReader";
import {TaskSaveAttempt, TaskSavePreparationError, MANUAL_TASK_REQUEST_KEY, TASK_SAVE_UNCONFIRMED, TASK_SAVE_PENDING} from './taskSaveAttempt';
import {TaskRetryReview} from './TaskRetryReview';



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

function LoadingMorning() {
  // Das Skelett hat die Form der fertigen Seite: Kopf, Eingabe, zwei Flächen. Nichts springt, wenn der Überblick kommt.
  return (
    <div className="morning-page today-page loading" aria-label="Heute wird geladen" aria-busy="true">
      <div className="hero skeleton-hero"><i /><i /></div>
      <div className="briefing-area">
        <div className="skeleton-command" />
        <div className="today-overview">
          {[0, 1].map((item) => <div className="today-panel skeleton-card" key={item}><i /><i /><i /></div>)}
        </div>
      </div>
    </div>
  );
}

/** Wann der Überblick entstand, klein im Kopf von Heute (Paket U, H4); in der Zeitzone des Briefings. */
function standText(briefing: MorningBriefing) {
  const date = new Date(briefing.generated_at);
  if (Number.isNaN(date.getTime())) return null;
  try { return new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: briefing.timezone }).format(date); }
  catch { return new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false }).format(date); }
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
  // Heute ist das Briefing (Paket U, H1): „Zum Briefing“ am Ende der Einrichtung (/today?briefing=1, Befund 23) zeigt
  // einfach Heute, und die Adresse wird wieder schlicht.
  useEffect(() => { if (new URLSearchParams(window.location.search).has("briefing")) window.history.replaceState({}, "", "/today"); }, []);
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
    // Erst der Gruß, dann der Rest (V7, Tempo): Gleichzeitig teilten sich beide Abrufe den Sidecar und der Gruß kam
    // erst mit dem vollen Briefing. Die volle Fassung startet, sobald die schnelle da ist oder scheitert.
    api.morning(false).then(result => {
      if (active && !fullReceived) { setBriefing(lastKnown(result)); setError(false); }
    }).catch(() => { quickFailed = true; if (active && fullFailed && !fullReceived) setError(true); })
      .finally(() => { if (active) void refresh.run(true); });
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
    <div className="shell"><Sidebar active="Heute" recentConversation={recentConversation} /><main className="state-page today-state"><div className="g-flaeche today-fehler error-state" role="alert"><Leer zeichen="house" satz="Dein Überblick ist gerade nicht erreichbar." aktion={<button className="g-knopf-getoent" type="button" onClick={() => load()}>Wiederholen</button>} /></div></main></div>
  );

  const attentionCount = todayAttention(briefing).length;
  const stand = standText(briefing);
  return (
    <div className="shell">
      <Sidebar active="Heute" recentConversation={recentConversation} />
      <main className="morning-page today-page">
        <div className="today-landscape" aria-hidden="true" />
        {/* Der Eisvogel steht nur hier im Kopf, nicht noch einmal in einer Karte (Paket U, H2). */}
        <section className="hero">
          <img className="hero-bird" src={`${ASSET.media}Freigestellter Eisvogel auf Zweig.png`} alt="" />
          {/* Ein großer Titel, eine Zeile darunter (Nachtrag 23.10.: wenig Text, Verständnis auf einen Blick). */}
          <div className="hero-copy"><h1>{briefing.greeting}</h1>
            <p className="today-hero-summary">
              <span>{attentionCount === 0 ? "Dein Überblick ist da." : attentionCount === 1 ? "Ein Punkt braucht dich." : `${attentionCount} Punkte brauchen dich.`}</span>
              {/* Ein Zeitpunkt, keine zweite Uhr: Die Uhr steht nur in der Seitenleiste (Fremdprobe 2, Befund 11). */}
              {/* Während das volle Briefing kommt, atmet „Stand“ leise, statt Text anzuhängen: Der angehängte Text brach
                  bei 390 px die Zeile um und schob beim Verschwinden die ganze Seite hoch (V7, CLS 0,18). */}
              {stand ? <span className="today-stand" aria-busy={refreshing || undefined}>Stand {stand}{refreshing ? <span className="visually-hidden"> · wird aktualisiert …</span> : null}</span> : null}
              <AudioBriefing briefing={briefing} />
            </p>
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
          <PostfachStand ausstehend={Boolean(briefing.post_ausstehend)} />
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
        </section>
      </main>
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

  // Ein neues Gespräch entsteht erst mit der ersten Frage: „Neues Gespräch“ führt zum leeren Eingabefeld.
  async function create() {
    navigate("/conversations");
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
          <header className="thread-header"><button className="conversation-navigation-toggle" aria-label="Gespräche" aria-expanded={navigationOpen} type="button" onClick={() => setNavigationOpen(open => !open)}><span className="nur-breit">Gespräche</span></button><h1>{data?.conversation.title ?? "Gespräch"}</h1><button className="conversation-sources-toggle" aria-expanded={sourcesOpen} aria-controls="conversation-sources" type="button" onClick={() => setSourcesOpen(open => !open)}><span className="nur-breit">Verwendete </span>Quellen</button></header>
          {sourcesOpen && <aside className="conversation-sources" id="conversation-sources" aria-label="Verwendete Quellen">
            {contextLines.length ? contextLines.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : data?.context.source_links?.length ? <p>{data.context.source_links.length} Originalquelle(n) zur Prüfung. Keine bestätigte Aussage.</p> : <p>{kontextLeerSatz(data?.messages ?? [])}</p>}
          </aside>}
          <div className="messages" ref={messagesElement} onScroll={event => {
            const element = event.currentTarget;
            followBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 96;
          }}>
            {!error && data && !data.messages.length && <div className="conversation-empty"><h2>Womit möchtest du beginnen?</h2></div>}

            {error ? <div className="message assistant error-message" role="alert"><Leer zeichen="message-circle" satz="Das Gespräch ist gerade nicht erreichbar." aktion={<button className="g-knopf-getoent" type="button" onClick={() => load()}>Wiederholen</button>} /></div> : null}
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
                <span className="message-wer">{message.role === "user" ? "Du" : "Kingfisher"}</span>
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
                {message.metadata?.context?.routing && <details className="antwort-arbeitsweise"><summary>Modell und Arbeitsweise</summary><p>{message.metadata.context.routing.to === "research" ? "Recherche mit begrenzten Lesewerkzeugen" : "Persönlicher Assistent"}</p><p>{message.metadata.context.routing.reason}</p>{message.metadata.context.routing.trace.map((step, index) => <p key={index}>{step.model} · {step.outcome === "success" ? "Antwort erhalten" : step.outcome === "failed" ? "Nicht erreichbar, Alternative geprüft" : "Ausgewählt"}</p>)}</details>}
                {message.status === "error" && !message.metadata?.resolved_approval_id ? <small className="antwort-fehler">Antwort fehlgeschlagen.{" "}<button className="g-knopf-schlicht" disabled={sending} onClick={() => void retry(message.id).catch(() => undefined)} type="button">Wiederholen</button></small> : null}
                {data.action_requests?.filter((action) => action.message_id === message.id).map((action) => <ActionApprovalCard key={action.id} action={action} busy={sending} onResolve={resolveAction} />)}
                {candidate ? <Bestaetigung className="memory-candidate" label="Gedächtnisvorschlag" titel="Gedächtnisvorschlag">
                  <strong>{candidate.statement}</strong>
                  {candidate.evidence[0] ? <p className="memory-source">Aus diesem Gespräch: „{candidate.evidence[0].quote}“</p> : null}
                  {requiresReplacement ? <div className="memory-conflict"><p>Bestehender Stand:</p>{card?.conflicts.map((conflict) => <p key={conflict.id}>{conflict.statement}</p>)}</div> : null}
                  {candidate.state === "pending" && card?.competing_count ? <p className="memory-notice">Ein abweichender offener Vorschlag wird erst durch deine Entscheidung zurückgestellt.</p> : null}
                  {candidate.state === "accepted" ? <p className="memory-decision" role="status">{memoryDecision}</p> : null}
                  {candidate.state === "rejected" ? <p className="memory-decision">Nicht gespeichert.</p> : null}
                  {candidate.state === "superseded" ? <p className="memory-decision">Durch einen anderen bestätigten Stand ersetzt.</p> : null}
                  <div className="memory-actions g-bestaetigung-knoepfe">
                    {candidate.state === "pending" ? <>
                    <button className="memory-confirm" disabled={sending} onClick={() => decideMemory(candidate.id, requiresReplacement)} type="button">{requiresReplacement ? "Bestehenden Stand ersetzen" : card?.competing_count ? "Diesen Stand bestätigen" : "Bestätigen"}</button>
                    <button className="memory-reject" disabled={sending} onClick={() => rejectMemory(candidate.id)} type="button">Nicht speichern</button>
                    </> : null}
                    {candidate.state === "accepted" && (card?.claim?.status === "active" || card?.claim?.status === "disputed") ? <button className="memory-reject" disabled={sending} onClick={() => retractMemory(candidate.id)} type="button">Als falsch widerrufen</button> : null}
                    {card?.source_message_id && data.messages.some((item) => item.id === card.source_message_id) ? <button className="memory-reject" onClick={() => showMemorySource(card.source_message_id!)} type="button">Quelle anzeigen</button> : null}
                  </div>
                </Bestaetigung> : null}
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

function ConversationHistory({ recentConversation, rememberConversation, chatAvailable, chatPlaceholder }: {
  recentConversation: string | null;
  rememberConversation: (id: string) => void;
  chatAvailable: boolean;
  chatPlaceholder?: string;
}) {
  // Kein leeres Gespräch auf Vorrat: Die Mitte ist gleich das Eingabefeld, das Gespräch entsteht mit der ersten Frage.
  const [sending, setSending] = useState(false);
  const [question, setQuestion] = useState<string | null>(null);
  const [sendError, setSendError] = useState(false);
  const created = useRef<string | null>(null);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  async function begin(message: string) {
    if (!chatAvailable) return;
    setSending(true); setSendError(false); setQuestion(message);
    try {
      // Schlug nur das Senden fehl, nimmt der zweite Versuch dasselbe Gespräch; es entsteht kein zweites.
      const id = created.current ?? (await api.createConversation()).conversation.id;
      created.current = id;
      if (!live.current) return;
      rememberConversation(id);
      await api.sendMessage(id, message);
      created.current = null;
      if (live.current) navigate(`/conversations/${id}`);
    } catch (problem) {
      if (live.current) setSendError(true);
      throw problem;
    } finally { if (live.current) setSending(false); }
  }
  async function focusInput() {
    document.querySelector<HTMLTextAreaElement>(".workspace-chat-start .thread-command textarea")?.focus();
  }
  return <div className="shell conversation-shell">
    <Sidebar active="Gespräche" recentConversation={recentConversation} />
    <main className="conversation-page workspace-chat workspace-chat-start">
      <ConversationNavigation onCreate={focusInput} onSelect={id => navigate(`/conversations/${id}`)} />
      <section className="thread">
        <div className="messages">
          {question ? <article className="message user"><span className="message-wer">Du</span><MessageText content={question} /></article> : <div className="conversation-empty"><h1>Was beschäftigt dich?</h1></div>}
        </div>
        <div className="thread-command">
          {sendError ? <p className="partial-error thread-send-error" role="alert">Die Nachricht konnte nicht gesendet werden. Bitte erneut versuchen.</p> : null}
          {sending && <p className="conversation-waiting" role="status" aria-live="polite">Kingfisher antwortet …</p>}
          <CommandBar busy={sending} conversation disabled={!chatAvailable} onSubmit={begin} placeholder={chatPlaceholder} />
        </div>
      </section>
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
  const [projektFormular, setProjektFormular] = useState(false);
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
  // Zahlen an den Segmenten (nur über null): offene eigene und wartende Aufgaben, wie die Liste gefiltert.
  const [zahlen, setZahlen] = useState<{mine?: number; waiting?: number}>({});
  const [zahlenStand, setZahlenStand] = useState(0);
  useEffect(() => {
    let aktiv = true;
    Promise.all([api.tasks("mine", projectId, {limit: 1}), api.tasks("waiting", projectId, {limit: 1})])
      .then(([mine, waiting]) => { if (aktiv) setZahlen({mine: mine.total, waiting: waiting.total}); })
      .catch(() => { if (aktiv) setZahlen({}); });
    return () => { aktiv = false; };
  }, [projectId, zahlenStand]);

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
    setZahlenStand(n=>n+1);
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
      setZahlenStand(n=>n+1);
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

  // Jeder Klick am Kreis antwortet mit dem Hinweis unten, und „Rückgängig“ nimmt ihn über die Gegenroute zurück (V4).
  const aufgabeVon = (taskId: string) => listTasks?.find(task => task.id === taskId) ?? { id: taskId, title: "Aufgabe" };
  async function complete(taskId: string, reopen = false) {
    if (completing) return;
    setCompleting(taskId);
    setError("");
    const aufgabe = aufgabeVon(taskId);
    try {
      if (reopen) await api.reopenTask(taskId);
      else await api.completeTask(taskId);
      load();
      zeigeHinweis(reopen ? wiederOffenHinweis(aufgabe, async () => { await api.completeTask(taskId); load(); })
        : erledigtHinweis(aufgabe, async () => { await api.reopenTask(taskId); load(); }));
    } catch {
      setError("Der Aufgabenstatus konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setCompleting(null);
    }
  }

  async function rueckgaengig(taskId: string) {
    if (completing) return;
    setCompleting(taskId); setError("");
    try { await api.taskRueckgaengig(taskId); load(); zeigeHinweis({ text: POST_ZURUECK }); }
    catch { setError("Das ließ sich gerade nicht zurücknehmen. Bitte erneut versuchen."); }
    finally { setCompleting(null); }
  }

  async function wait(taskId: string, name?: string) {
    if (completing) return;
    setCompleting(taskId); setError("");
    const aufgabe = aufgabeVon(taskId);
    try {
      if (name) await api.waitTask(taskId, name);
      else await api.unwaitTask(taskId);
      load();
      zeigeHinweis(name ? wartetHinweis(aufgabe, name, async () => { await api.unwaitTask(taskId); load(); })
        : zurueckZuMirHinweis(aufgabe, "wartet_auf" in aufgabe ? aufgabe.wartet_auf : null, async vorher => { await api.waitTask(taskId, vorher); load(); }));
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
  // Segmente statt Reiter: alle bleiben erreichbar; „Zur Prüfung“ nur, wenn etwas zu prüfen ist (sonst über „Gedächtnis
  // prüfen“). Zahlen nur über null: offene eigene, wartende und zu prüfende.
  const tabs: Segment<string>[] = [
    ...TASK_VIEWS.map(item => ({wert: item.id, titel: item.label, zahl: item.id === "mine" ? zahlen.mine : item.id === "waiting" ? zahlen.waiting : undefined})),
    {wert: "projects", titel: "Projekte"},
    ...(panel === "review" || (reviewTotal ?? 0) > 0 ? [{wert: "review", titel: "Zur Prüfung", zahl: reviewTotal ?? 0}] : [])];
  const activeTab = panel === "tasks" ? view : panel;
  function chooseTab(id: string) {
    if (id === "projects") { setView("mine"); setPanel("projects"); }
    else if (id === "review") { openTask(null); setView("mine"); setPanel("review"); }
    else { setPanel("tasks"); setView(id as TaskView); }
  }
  // Rollt die Segmentleiste (schmales Fenster), steht der gewählte Abschnitt auch beim Öffnen per Adresse im Blick.
  useEffect(() => { document.querySelector?.<HTMLElement>('.aufgaben-segmente [aria-selected="true"]')?.scrollIntoView?.({block: "nearest", inline: "nearest"}); }, [activeTab]);
  // Eine Zeile unter dem Titel, nur wenn sie etwas sagt: wie viele Aufgaben heute dran oder überfällig sind.
  const heuteDran = panel === "tasks" && view === "mine" && !search && listTasks ? visibleTaskGroups(listTasks, groupTime).filter(group => group.label === "Überfällig" || group.label === "Heute").reduce((sum, group) => sum + group.items.length, 0) : 0;
  const kopfZeile = heuteKopfZeile(heuteDran, listTasks?.length ?? 0, {seite: taskPage.page, weitere: taskPage.canNext});
  const row = (task: LocalTask) => <TaskRow compact onOpen={() => openTask(task.id, true)} showProjectName={!projectId} projects={projects} onProjectChange={id => assignProject(task.id, id)} onEdit={data => editTask(task.id, data)} completing={completing !== null} key={task.id} onWait={name=>wait(task.id,name)} onComplete={()=>complete(task.id,task.status==="done")} onRueckgaengig={()=>void rueckgaengig(task.id)} task={task} view={view as "mine" | "waiting" | "done"} />;
  const emptyText = search ? 'Keine passenden Aufgaben für diese Suche.' : selectedTask ? "Keine weiteren Aufgaben auf dieser Seite." : view === "mine" ? "Keine offenen Aufgaben für dich." : view === "waiting" ? "Aktuell wartest du auf niemanden." : "Noch keine erledigten Aufgaben.";
  // Genau ein gefüllter Knopf: Steht ein Formular offen, ist dessen Knopf der gefüllte und „Aufgabe“ tritt zurück; unter
  // „Zur Prüfung“ ist das Prüfen die Hauptsache, dort ist „Aufgabe“ ebenfalls nur getönt.
  const formOffen = (creating && panel === "tasks" && listView) || (panel === "projects" && projektFormular) || panel === "review";
  const projectsFailedLine = <p className="tasks-error" role="alert">Projekte sind gerade nicht erreichbar. <button type="button" className="text-action" onClick={loadProjects}>Erneut laden</button></p>;
  return <div className="shell tasks-shell">
    <Sidebar active="Aufgaben" recentConversation={recentConversation} />
    <main className="tasks-page workspace-tasks aufgaben">
      <Seitenkopf className="tasks-heading" titel="Aufgaben" zeile={kopfZeile}
        aktionen={view !== "decisions" && view !== "goals" ? <button className={formOffen ? "g-knopf-getoent" : "tasks-add"} disabled={submitting} onClick={startTask} type="button"><img src={icon("plus", "Outline")} alt="" />Aufgabe</button> : undefined} />
      {selectedTask && <DetailPanel title="Aufgabe" onClose={() => openTask(null)}>
        <TaskDetail key={`${selectedTask}:${detailEdit}`} taskId={selectedTask} editing={detailEdit > 0} onChanged={() => load()} />
      </DetailPanel>}
      <Segmente className="aufgaben-segmente" label="Aufgabenansichten" optionen={tabs} wert={activeTab} onWahl={chooseTab} />
      <section className="workspace-projects" aria-label="Projekte" hidden={panel !== "projects"}>
        {panel === "projects" && (projects.length ? <Gruppe className="workspace-project-list">{projects.map(project=><Zeile key={project.id} onClick={()=>setProjectId(project.id)} aktiv={projectId===project.id} titel={project.name} neben={project.description || undefined} wert={project.status === "done" ? "Erledigt" : project.status === "dropped" ? "Verworfen" : project.status === "paused" ? "Pausiert" : project.status === "idea" ? "Idee" : "Aktiv"} />)}</Gruppe> : projectError ? null : <Leer className="task-empty" zeichen="project" satz="Noch keine Projekte." />)}
        {projectError ? projectsFailedLine : <ProjectControls contextRevision={overviewRevision} projects={projects} selectedId={projectId} onSelect={setProjectId} onChanged={loadProjects} onFormular={setProjektFormular} />}
        {panel === "projects" && projectId && <div className="workspace-project-actions"><Segmente kompakt label="Darstellung" optionen={[{wert: "liste", titel: "Liste"}, {wert: "board", titel: "Board"}]} wert={board ? "board" : "liste"} onWahl={wert => setBoard(wert === "board")} /><a className="g-knopf-schlicht" href={`/memory/projects/${encodeURIComponent(projectId)}`}>Im Gedächtnis öffnen</a></div>}
        {panel === "projects" && projectId && board && <ProjectBoard projectId={projectId} revision={overviewRevision} onTask={task=>openTask(task.id)} />}
      </section>
      <div className="task-review" hidden={panel !== "review"}>
        <TaskSuggestions projects={projects} onTotal={setReviewTotal} onPreview={()=>openTask(null)} onAccepted={task => { loadProjects(); setPanel("tasks"); openTask(task.id); setProjectId(task.project_id ?? ""); setView(task.wartet_auf ? "waiting" : "mine"); load(task.wartet_auf ? "waiting" : "mine"); }} />
        {panel === "review" && reviewTotal === 0 ? <Leer className="task-empty" zeichen="check" satz="Nichts zu prüfen." /> : null}
      </div>
      {panel === "tasks" && (view === "mine" || view === "waiting") && <AufgabenPostVorschlaege onChanged={task => { load(); if (task) openTask(task.id); }} />}
      {error ? <p className="tasks-error" role="alert">{error} <button className="text-action" onClick={() => load()} type="button">Wiederholen</button></p> : null}
      {panel !== "review" && (listView || (view === "decisions" && (projects.length > 0 || projectError))) && <form className="task-search" role="search" onSubmit={event => {event.preventDefault(); setSearch(searchInput.trim());}}>
        {listView && <input type="search" aria-label="Aufgaben durchsuchen" maxLength={200} value={searchInput} onChange={event => setSearchInput(event.target.value)} placeholder="Suchen" />}
        {panel === "projects" ? null : projectError ? projectsFailedLine : projects.length > 0 && <select aria-label="Projekt" className="task-project-filter" value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Alle Projekte</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>}
      </form>}
      {panel !== "review" && listView && <ProjectOverview key={projectId} projectId={projectId} revision={overviewRevision} onView={nextView=>openProjectView(nextView)} onTask={(id,nextView)=>openProjectView(nextView,id)} />}
      {panel !== 'review' && listView && <>
        {taskPage.error && <p role="alert" className="tasks-error">{taskPage.error} <button type="button" className="text-action" onClick={() => load()}>Erneut laden</button></p>}
        {taskPage.notice && <p role="status" className="task-hinweis">{taskPage.notice}</p>}
        {search && tasks && tasks.length > 0 ? <p role="status" className="task-count">{taskPage.total === 1 ? "1 Treffer" : `${taskPage.total} Treffer`}</p> : null}
      </>}
      {view === "goals" ? <><GoalControls /><HabitControls /></> : view === "decisions" ? <DecisionControls key={projectId} projectId={projectId} kopf={false} /> : <section className="task-table" aria-label={heading} hidden={panel === "review" || (panel === "projects" && board && Boolean(projectId))}>
        {creating ? <form className="task-create" onSubmit={create}>{createError && <p className="tasks-error" role="alert">{createError} <button className="text-action" disabled={submitting} type="submit">Wiederholen</button></p>}{createError && <TaskRetryReview reviewed={createReviewed} busy={submitting} onReviewed={setCreateReviewed} onPrepareNew={prepareNewTaskRequest} />}<label className="task-create-title">Aufgabe<input autoFocus disabled={submitting} onChange={(event) => setTitle(event.target.value)} placeholder="Was möchtest du erledigen?" required value={title} /></label><label>Fällig am<input disabled={submitting} onChange={(event) => setDue(event.target.value)} type="date" value={due} /></label>{projects.some(project => project.open) && <label className="task-project-create">Projekt<select value={newTaskProject} onChange={event => setNewTaskProject(event.target.value)} disabled={submitting || projectError}><option value="">Ohne Projekt</option>{projects.filter(project=>project.open).map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}<div className="task-create-actions"><button className="g-knopf-schlicht" disabled={submitting} onClick={() => setCreating(false)} type="button">Abbrechen</button><button className="primary-action" disabled={submitting || !title.trim()} type="submit">Lokal speichern</button></div></form> : null}
        {!listTasks && !error && taskPage.loading ? <div className="task-loading" role="status" aria-label="Aufgaben werden geladen"><i /><i /><i /></div> : null}
        {visibleTasks && visibleTasks.length > 0 && (view === "mine"
          ? visibleTaskGroups(visibleTasks,groupTime).map(group=><Gruppe className="workspace-task-group" key={group.label} titel={group.label}>{group.items.map(row)}</Gruppe>)
          : <Gruppe className="workspace-task-group">{visibleTasks.map(row)}</Gruppe>)}
        {visibleTasks && visibleTasks.length === 0 && !creating ? <Leer className="task-empty" zeichen={search ? "search" : "check"} satz={emptyText} /> : null}
        {(taskPage.canPrevious || taskPage.canNext) && <nav className="task-seiten" aria-label="Aufgabenseiten"><button type="button" className="g-knopf-getoent g-kompakt" disabled={!taskPage.canPrevious || completing !== null} onClick={() => void pager.current!.previous()}>Vorherige Seite</button><span className="task-page-number">Seite {taskPage.page}</span><button type="button" className="g-knopf-getoent g-kompakt" disabled={!taskPage.canNext || completing !== null} onClick={() => void pager.current!.next()}>Nächste Seite</button></nav>}
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
    // Ohne Modell sagt die Antwort selbst, wenn eine Frage eines bräuchte; der Platzhalter nennt nur, was geht (H5).
    : "Frag nach Menschen, Projekten, Terminen …";

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
  if (path === "/conversations") return <ConversationHistory chatAvailable={chatAvailable !== null} chatPlaceholder={chatPlaceholder} recentConversation={recentConversation} rememberConversation={rememberConversation} />;
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
