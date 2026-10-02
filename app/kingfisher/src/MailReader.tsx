import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, type ConversationPayload, type MailDetail } from "./api";
import { navigate } from "./ui";
import { MailTaskForm } from "./MailTaskForm";
import { MailReplySuggestion, type Suggestion } from "./MailReplySuggestion";
import { ProfileSource } from "./ProfileSource";
import { MailStyle } from "./MailStyle";
import "./MailReader.css";

type MailReaderProps = { uid: string; onClose: () => void };

const draftKey = (uid: string) => `kingfisher-mail-draft:${uid}`;
const draftFormat = 1;

function readableDate(value: string | null) {
  if (!value) return "Datum unbekannt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function MailReader({ uid, onClose }: MailReaderProps) {
  const [detail, setDetail] = useState<MailDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [draftVisible, setDraftVisible] = useState(true);
  const [draftContext, setDraftContext] = useState<string | null>(null);
  const [draftValidationEpoch, setDraftValidationEpoch] = useState(0);
  const [draftSources, setDraftSources] = useState<Suggestion["sources"]>([]);
  const [draftNotice, setDraftNotice] = useState<string | null>(null);
  const [remembering, setRemembering] = useState(false);
  const [remembered, setRemembered] = useState(false);
  const [rememberNotice, setRememberNotice] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [replyNotice, setReplyNotice] = useState<string | null>(null);
  const [lastSuggestion, setLastSuggestion] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const validationVersion = useRef(0);

  async function load() {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    try {
      const value = await api.mailMessage(uid) as MailDetail;
      if (version !== requestVersion.current || uid !== value.uid) return;
      setDetail(value);
    } catch {
      if (version === requestVersion.current) setError("Diese Nachricht konnte gerade nicht geladen werden.");
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    const version = ++requestVersion.current;
    setDetail(null);
    setError(null);
    setRemembered(false);
    setRememberNotice(null);
    setDraftNotice(null);
    setReplyNotice(null);
    setLastSuggestion(null);
    setDraft("");
    setDraftVisible(true);
    setDraftContext(null);
    setDraftSources([]);
    api.mailMessage(uid).then((value) => {
      if (!active) return;
      if (version !== requestVersion.current) return;
      setDetail(value as MailDetail);
      setLoading(false);
    }).catch(() => {
      if (!active) return;
      if (version === requestVersion.current) setError("Diese Nachricht konnte gerade nicht geladen werden.");
      if (version === requestVersion.current) setLoading(false);
    });
    try {
      const saved = window.localStorage.getItem(draftKey(uid));
      if (active && saved) {
        try {
          const parsed = JSON.parse(saved) as {__kingfisherMailDraft?: unknown; body?: unknown; contextToken?: unknown; sources?: unknown};
          if (parsed?.__kingfisherMailDraft !== draftFormat || typeof parsed.body !== "string") throw new Error("legacy");
          const token = typeof parsed.contextToken === "string" ? parsed.contextToken : null;
          if ((parsed.contextToken != null && !token) || (!token && Array.isArray(parsed.sources) && parsed.sources.length)) {
            try {
              window.localStorage.removeItem(draftKey(uid));
              window.localStorage.removeItem(`${draftKey(uid)}:model`);
            } catch { /* Der alte Inhalt bleibt in dieser Ansicht verborgen. */ }
            setDraftNotice("Der Quellenbezug des gespeicherten Entwurfs fehlt. Bitte einen neuen Vorschlag erstellen.");
          } else {
            setDraft(parsed.body);
            setDraftContext(token);
            if (token) setDraftVisible(false);
            setDraftSources(Array.isArray(parsed.sources) ? parsed.sources.filter((source): source is Suggestion["sources"][number] =>
              typeof source?.episode_id === "string" && typeof source?.title === "string") : []);
          }
        } catch { setDraft(saved); }
      }
      if (active) setLastSuggestion(window.localStorage.getItem(`${draftKey(uid)}:model`));
    } catch {
      if (active) setDraftNotice("Der Entwurf bleibt nur für dieses Fenster erhalten, weil der lokale Speicher nicht verfügbar ist.");
    }
    return () => { active = false; requestVersion.current++; };
  }, [uid]);

  useEffect(() => {
    if (!draftContext) return;
    let active = true;
    async function validate() {
      const current = ++validationVersion.current;
      setDraftVisible(false);
      try {
        await api.validateMailReplyContext(uid, draftContext!);
        if (active && current === validationVersion.current) {
          setDraftVisible(true);
          setDraftNotice(null);
        }
      } catch (failure) {
        if (!active || current !== validationVersion.current) return;
        if (failure instanceof Error && ["HTTP 409", "HTTP 422"].includes(failure.message)) {
          setDraft("");
          setDraftSources([]);
          setDraftContext(null);
          setLastSuggestion(null);
          setDraftVisible(true);
          setDraftNotice("Die Grundlage des Entwurfs hat sich geändert oder die App wurde neu gestartet. Bitte einen neuen Vorschlag erstellen.");
          try {
            window.localStorage.removeItem(draftKey(uid));
            window.localStorage.removeItem(`${draftKey(uid)}:model`);
          } catch { /* Der alte Inhalt bleibt in dieser Ansicht verborgen. */ }
        } else {
          setDraftNotice("Der Quellenbezug konnte gerade nicht geprüft werden. Bitte das Fenster erneut öffnen oder aktivieren.");
        }
      }
    }
    void validate();
    const onFocus = () => { void validate(); };
    window.addEventListener("focus", onFocus);
    return () => { active = false; validationVersion.current++; window.removeEventListener("focus", onFocus); };
  }, [uid, draftContext, draftValidationEpoch]);

  function rememberSuggestion(value: string) {
    setLastSuggestion(value);
    try { window.localStorage.setItem(`${draftKey(uid)}:model`, value); } catch { /* Own-text confirmation remains required. */ }
  }

  function changeDraft(value: string, suggestion?: Suggestion) {
    const context = suggestion ? suggestion.context_token : draftContext;
    const sources = suggestion ? suggestion.sources : draftSources;
    setDraft(value);
    if (suggestion) {
      validationVersion.current++;
      setDraftVisible(!context);
      setDraftContext(context);
      setDraftValidationEpoch(current => current + 1);
      setDraftSources(sources);
      rememberSuggestion(suggestion.body);
    }
    try {
      if (value) window.localStorage.setItem(draftKey(uid), JSON.stringify({__kingfisherMailDraft: draftFormat, body: value, contextToken: context, sources}));
      else window.localStorage.removeItem(draftKey(uid));
      setDraftNotice(null);
    } catch {
      setDraftNotice("Der Entwurf konnte lokal nicht gespeichert werden. Dein Text bleibt hier erhalten.");
    }
  }

  const clearInvalidatedSuggestion = useCallback(() => {
    setLastSuggestion(null);
    try { window.localStorage.removeItem(`${draftKey(uid)}:model`); } catch { /* No saved model text to clear. */ }
  }, [uid]);

  async function remember() {
    if (remembering || remembered) return;
    setRemembering(true);
    setRememberNotice(null);
    try {
      const result = await api.rememberMail(uid);
      setRemembered(true);
      setRememberNotice(result.episode.state === "ignored"
        ? "Diese Fassung ist ausgeschlossen. Sie bleibt im Verlauf erhalten und wird nicht als Beleg verwendet."
        : result.changed ? "Geänderte Fassung gemerkt. Frühere Belege und davon abhängige Aussagen sind jetzt fraglich."
        : result.new ? "Als Rohmaterial gemerkt — noch kein bestätigter Fakt." : "Dieses Rohmaterial ist bereits gemerkt.");
    } catch {
      setRememberNotice("Das Rohmaterial konnte gerade nicht gemerkt werden.");
    } finally {
      setRemembering(false);
    }
  }

  async function prepareReply(event: FormEvent) {
    event.preventDefault();
    const body = draft.trim();
    if (!detail?.can_reply || !body || preparing || !draftVisible) return;
    setPreparing(true);
    setReplyNotice(null);
    try {
      const payload = await api.prepareMailReply(uid, { body, ...(draftContext ? {context_token: draftContext} : {}) }) as ConversationPayload;
      try { window.localStorage.removeItem(draftKey(uid)); } catch { /* Der Entwurf liegt jetzt im Gespräch. */ }
      navigate(`/conversations/${encodeURIComponent(payload.conversation.id)}`);
    } catch (failure) {
      setReplyNotice(failure instanceof Error && failure.message === "HTTP 409" && draftContext
        ? "Mail oder Rohquelle haben sich geändert, oder die lokale App wurde neu gestartet. Bitte einen neuen Vorschlag erstellen."
        : "Die Antwort konnte gerade nicht zur Freigabe vorbereitet werden.");
      setPreparing(false);
    }
  }

  return <article className="mail-reader" aria-label="Nachricht lesen">
    <header className="mail-reader-header">
      <button className="mail-reader-close" disabled={preparing} onClick={onClose} type="button">Schließen</button>
      <span className="mail-reader-source">Externe Quelle · Mail</span>
    </header>
    {loading ? <div className="mail-reader-loading" aria-live="polite">Nachricht wird geladen …</div> : null}
    {error ? <div className="mail-reader-error" role="alert"><p>{error}</p><button onClick={load} type="button">Wiederholen</button></div> : null}
    {detail ? <>
      <section className="mail-reader-meta">
        <p className="mail-reader-eyebrow">Eingegangene Nachricht</p>
        <h1>{detail.subject || "(Ohne Betreff)"}</h1>
        <dl>
          <div><dt>Von</dt><dd>{detail.from}</dd></div>
          <div><dt>Datum</dt><dd>{readableDate(detail.date)}</dd></div>
          <div><dt>Antwort an</dt><dd>{detail.answer_to || detail.from}</dd></div>
          {detail.account_label ? <div><dt>Postfach</dt><dd>{detail.account_label}</dd></div> : null}
        </dl>
      </section>
      <section className="mail-reader-body" aria-label="Nachrichtentext"><pre>{detail.body || detail.preview}</pre></section>
      {detail.truncated ? <p className="mail-reader-status">Die Nachricht ist sehr lang. Hier werden die ersten 20.000 Zeichen angezeigt.</p> : null}
      <section className="mail-reader-actions" aria-label="Nachrichtenaktionen">
        <button className="mail-reader-secondary" disabled={remembering || remembered} onClick={remember} type="button">{remembering ? "Wird gemerkt …" : remembered ? "Als Quelle gemerkt" : "Als Quelle merken"}</button>
        {rememberNotice ? <p className="mail-reader-status" role="status">{rememberNotice}</p> : null}
      </section>
      <MailTaskForm key={`task:${uid}`} uid={uid} subject={detail.subject} />
      <MailReplySuggestion key={`reply:${uid}`} uid={uid} disabled={preparing} onApply={suggestion => changeDraft(suggestion.body, suggestion)} hasDraft={draftVisible && Boolean(draft.trim())} onInvalidated={clearInvalidatedSuggestion} />
      <MailStyle uid={uid} draft={draftVisible && !draftContext ? draft : ""} originalSuggestion={draftVisible && !draftContext ? lastSuggestion : null} />
      {<form className="mail-reader-reply" onSubmit={prepareReply}>
        <label htmlFor="mail-reply">Antwort</label>
        <p className="mail-reader-reply-target">Antwort an {detail.answer_to || detail.from}{` · von ${detail.sending_account}`}</p>
        <textarea disabled={preparing || !draftVisible} id="mail-reply" onChange={(event) => changeDraft(event.target.value)} placeholder={draftVisible ? "Antwort schreiben …" : "Quellenbezug wird geprüft …"} value={draftVisible ? draft : ""} />
        {draftVisible && draftSources.length ? <div><p>Dieser Entwurf verwendet frühere Nachrichten. Du kannst die Originale hier prüfen. Zitierte Nachrichten werden nicht als eigener Schreibstil übernommen.</p>{draftSources.map(source => <ProfileSource key={source.episode_id} kind="episode" id={source.episode_id} label={source.title || "Originalquelle öffnen"} readOnly />)}</div> : null}
        <div className="mail-reader-reply-footer"><span>{draftNotice || (draftVisible ? "Wird erst nach deiner Freigabe versendet." : "Quellenbezug wird geprüft …")}</span><button className="mail-reader-primary" disabled={preparing || !draftVisible || !detail.can_reply || !draft.trim()} type="submit">{preparing ? "Wird vorbereitet …" : "Antwort zur Freigabe vorbereiten"}</button></div>
        {replyNotice ? <p className="mail-reader-error" role="alert">{replyNotice}</p> : null}
      </form>}
      {!detail.can_reply ? <p className="mail-reader-status">Für dieses Postfach ist kein Versand eingerichtet. Du kannst deinen Antwortentwurf hier bearbeiten und kopieren.</p> : null}
    </> : null}
  </article>;
}
