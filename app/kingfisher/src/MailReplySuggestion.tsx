import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { ProfileSource } from "./ProfileSource";
import "./MailReplySuggestion.css";

export type Suggestion = { body: string; basis: "message_and_instruction" | "source_quotes"; context_token: string | null; source_status: string; sources: {episode_id: string; title: string}[] };
type Props = { uid: string; onApply: (suggestion: Suggestion) => void; disabled?: boolean; hasDraft: boolean; onInvalidated?: () => void };

export function MailReplySuggestion({ uid, onApply, disabled = false, hasDraft, onInvalidated }: Props) {
  const [instruction, setInstruction] = useState("");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggestionVisible, setSuggestionVisible] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const validationVersion = useRef(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { generation.current += 1; validationVersion.current += 1; controller.current?.abort(); }, [uid]);
  useEffect(() => {
    const token = suggestion?.context_token;
    if (!token) return;
    let active = true;
    async function validate() {
      const current = ++validationVersion.current;
      setSuggestionVisible(false);
      try {
        await api.validateMailReplyContext(uid, token!);
        if (active && current === validationVersion.current) setSuggestionVisible(true);
      } catch {
        if (!active || current !== validationVersion.current) return;
        setSuggestion(null);
        setSuggestionVisible(true);
        setError("Die Grundlage des Vorschlags hat sich geändert oder kann gerade nicht geprüft werden. Bitte neu vorschlagen.");
        onInvalidated?.();
      }
    }
    void validate();
    const onFocus = () => { void validate(); };
    window.addEventListener("focus", onFocus);
    return () => { active = false; validationVersion.current++; window.removeEventListener("focus", onFocus); };
  }, [uid, suggestion?.context_token, onInvalidated]);
  async function suggest() {
    if (loading || disabled) return;
    controller.current?.abort();
    const current = ++generation.current;
    const requestController = new AbortController();
    controller.current = requestController;
    let timedOut = false;
    const timeout = window.setTimeout(() => { timedOut = true; requestController.abort(); }, 90000);
    setLoading(true); setError(""); setSuggestion(null);
    try {
      const response = await fetch(`/api/v1/messages/${encodeURIComponent(uid)}/reply-suggestion`, {
        method: "POST", credentials: "same-origin", signal: requestController.signal,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ instruction: instruction.trim() }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? "stale" : "request");
      const next = await response.json() as Suggestion;
      if (current === generation.current) { setSuggestionVisible(!next.context_token); setSuggestion(next); }
    } catch (failure) {
      if (current === generation.current && (timedOut || !requestController.signal.aborted)) setError(failure instanceof Error && failure.message === "stale"
        ? "Mail oder Rohquelle haben sich geändert. Bitte einen neuen Vorschlag erstellen."
        : "Der lokale Antwortvorschlag konnte nicht erstellt werden. Bitte erneut versuchen.");
    } finally {
      window.clearTimeout(timeout);
      if (current === generation.current) { setLoading(false); controller.current = null; }
    }
  }
  function cancel() { generation.current += 1; controller.current?.abort(); controller.current = null; setLoading(false); }
  return <section className="mail-reply-suggestion" aria-label="Lokalen Antwortvorschlag erstellen">
    <p className="mail-reply-suggestion-label">Lokaler Vorschlag für diese Mail. Falls frühere Nachrichten passen, werden sie wörtlich zitiert. Bitte prüfen.</p>
    <label>Was soll die Antwort sagen? (optional)<input maxLength={1500} disabled={disabled || loading} value={instruction} onChange={event => setInstruction(event.target.value)} /></label>
    {!loading ? <button className="mail-reader-secondary" type="button" disabled={disabled} onClick={() => void suggest()}>Antwort vorschlagen</button> : <button className="mail-reader-secondary" type="button" onClick={cancel}>Vorschlag abbrechen</button>}
    {loading ? <p role="status">Lokaler Antwortvorschlag wird erstellt …</p> : null}
    {error ? <p className="mail-reader-error" role="alert">{error} <button type="button" onClick={() => void suggest()}>Erneut versuchen</button></p> : null}
    {suggestion && !suggestionVisible ? <p role="status">Quellenbezug des Vorschlags wird geprüft …</p> : null}
    {suggestion && suggestionVisible ? <div className="mail-reply-suggestion-result"><label htmlFor={`reply-suggestion-${uid}`}>Vorschlag</label><textarea id={`reply-suggestion-${uid}`} readOnly value={suggestion.body} />
      {suggestion.basis === "source_quotes" ? <p>Frühere Angaben werden hier wörtlich zitiert. Du kannst den Entwurf bearbeiten.</p> : null}
      {suggestion.sources.length ? <div><p>Frühere Nachrichten für diesen Vorschlag. Bitte prüfe Aussagen und Bedingungen im Original.</p>{suggestion.sources.map(source => <ProfileSource key={source.episode_id} kind="episode" id={source.episode_id} label={source.title || "Originalquelle öffnen"} readOnly />)}</div> : <p>{({
        person: "Die Zuordnung einer früheren Mail ist unklar. Es wurde keine Rohquelle verwendet.",
        recipient_scope: "Diese Antwort geht an eine andere oder nicht eindeutige Adresse. Frühere Nachrichten werden deshalb nicht einbezogen.",
        time: "Der Zeitbezug früherer Mails ist unklar. Es wurde keine Rohquelle verwendet.",
        conflict: "Frühere Mails widersprechen sich. Es wurde keine Rohquelle verwendet.",
        limited: "Die Quellenauswahl ist unvollständig. Es wurde keine Rohquelle verwendet.",
        confirmed_overlap: "Zu diesem Thema liegen auch bestätigte Angaben vor. Es wurde keine unbestätigte Rohquelle verwendet.",
        unavailable: "Eine Rohquelle ist nicht mehr aktuell. Es wurde keine Rohquelle verwendet.",
        selection_failed: "Die Rohquellen konnten nicht zuverlässig ausgewählt werden.",
        subject_too_broad: "Der Betreff grenzt den Vorgang nicht ausreichend ein. Es wurde keine frühere Rohquelle verwendet.",
      } as Record<string, string>)[suggestion.source_status] || "Keine eindeutig passenden aktuellen Rohquellen verwendet."}</p>}
      <button className="mail-reader-primary" type="button" disabled={disabled} onClick={() => onApply(suggestion)}>{hasDraft ? "Antwortentwurf ersetzen" : "Als Antwort übernehmen"}</button></div> : null}
  </section>;
}
