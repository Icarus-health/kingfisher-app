import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type MailBriefing as MailBriefingResult } from "./api";
import { mailBriefingFailure } from "./mailBriefingState";
import "./MailBriefing.css";

export type MailTaskSuggestion = { title: string; quote: string; source_digest: string };

type MailBriefingProps = {
  uid: string;
  expectedSourceDigest?: string;
  taskSelectionDisabled?: boolean;
  onNeedsOriginal: () => void;
  onPrepareTask: (suggestion: MailTaskSuggestion) => void;
};

type ViewState =
  | { kind: "loading" }
  | { kind: "cancelled" }
  | { kind: "failed"; detail: string }
  | { kind: "stale" }
  | { kind: "result"; value: MailBriefingResult };

export function MailBriefing({ uid, expectedSourceDigest, taskSelectionDisabled = false, onNeedsOriginal, onPrepareTask }: MailBriefingProps) {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const requestVersion = useRef(0);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback((refresh = false) => {
    controller.current?.abort();
    const version = ++requestVersion.current;
    const currentController = new AbortController();
    controller.current = currentController;
    setState({ kind: "loading" });
    void api.mailBriefing(uid, currentController.signal, refresh).then((value) => {
      if (version !== requestVersion.current || currentController.signal.aborted || value.uid !== uid) return;
      if (!expectedSourceDigest || value.source_digest !== expectedSourceDigest) {
        onNeedsOriginal();
        setState({ kind: "stale" });
        return;
      }
      const showsOriginalQuote = value.available
        && (value.status === "ready" || value.status === "incomplete")
        && value.quotes.slice(0, 3).length > 0;
      if (!showsOriginalQuote) onNeedsOriginal();
      setState({ kind: "result", value });
    }).catch((error: unknown) => {
      if (version !== requestVersion.current || currentController.signal.aborted) return;
      onNeedsOriginal();
      setState({ kind: "failed", detail: mailBriefingFailure(error instanceof ApiError ? error.status : undefined) });
    });
  }, [expectedSourceDigest, onNeedsOriginal, uid]);

  useEffect(() => {
    if (!expectedSourceDigest) {
      onNeedsOriginal();
      setState({ kind: "stale" });
      return;
    }
    load();
    return () => {
      requestVersion.current++;
      controller.current?.abort();
      controller.current = null;
    };
  }, [expectedSourceDigest, load, onNeedsOriginal]);

  function cancel() {
    requestVersion.current++;
    controller.current?.abort();
    controller.current = null;
    onNeedsOriginal();
    setState({ kind: "cancelled" });
  }

  const result = state.kind === "result" ? state.value : null;
  const showsQuotes = Boolean(result?.available && (result.status === "ready" || result.status === "incomplete"));
  const tasks = result?.status === "ready" && result.available && result.source_digest
    ? result.tasks.slice(0, 3)
    : [];

  return <section className="mail-briefing" aria-labelledby="mail-briefing-title">
    <div className="mail-briefing-heading">
      <div>
        <p className="mail-reader-eyebrow">Externe Quelle · Mail</p>
        <h2 id="mail-briefing-title">Auf einen Blick</h2>
      </div>
      {state.kind === "loading" ? <button className="mail-reader-secondary" onClick={cancel} type="button">Abbrechen</button> : null}
    </div>
    {state.kind === "loading" ? <p className="mail-reader-status" role="status">Originalstellen werden lokal ausgewählt …</p> : null}
    {state.kind === "cancelled" ? <div className="mail-briefing-state" role="status"><p>Die Auswertung wurde abgebrochen.</p><button className="mail-reader-secondary" onClick={() => load(true)} type="button">Wiederholen</button></div> : null}
    {state.kind === "failed" ? <div className="mail-briefing-state" role="status"><p>{state.detail}</p><button className="mail-reader-secondary" onClick={() => load(true)} type="button">Wiederholen</button></div> : null}
    {state.kind === "stale" ? <p className="mail-reader-status" role="status">Die Nachricht hat sich geändert. Bitte neu öffnen oder aktualisieren.</p> : null}
    {result && result.status !== "ready" ? <div className="mail-briefing-state" role="status">
      <p>{result.detail || (result.status === "empty"
        ? "Keine passenden Originalstellen gefunden."
        : result.status === "incomplete" ? "Die Auswertung ist unvollständig." : "Die lokale Auswertung ist gerade nicht verfügbar.")}</p>
      {result.status === "incomplete" && !showsQuotes ? <p>Die Auswertung ist unvollständig. Angezeigt werden nur passende Originalauszüge; Aufgaben werden hier nicht vorgeschlagen.</p> : null}
      {result.status === "unavailable" || result.status === "incomplete" ? <button className="mail-reader-secondary" onClick={() => load(true)} type="button">Wiederholen</button> : null}
    </div> : null}
    {result && showsQuotes ? <>
      <p className="mail-briefing-source">Auszüge aus der Originalnachricht</p>
      {result.quotes.slice(0, 3).length ? <ul className="mail-briefing-quotes">
        {result.quotes.slice(0, 3).map((quote, index) => <li key={`${index}:${quote}`}>„{quote}“</li>)}
      </ul> : <p className="mail-reader-status">Keine passenden Originalstellen gefunden.</p>}
      {result.status === "incomplete" || result.truncated ? <p className="mail-reader-status">Die Auswertung ist unvollständig. Es werden nur übernommene Originalauszüge gezeigt.</p> : null}
      {tasks.length ? <div className="mail-briefing-tasks">
        <p className="mail-briefing-source">Mögliche nächste Schritte</p>
        {tasks.map((task, index) => <article className="mail-briefing-task" key={`${index}:${task.title}`}>
          <div><p className="mail-briefing-task-title">{task.title}</p><p className="mail-briefing-task-quote">„{task.quote}“</p></div>
          <button className="mail-reader-secondary" disabled={taskSelectionDisabled} onClick={() => onPrepareTask({ ...task, source_digest: result.source_digest! })} type="button">Als Aufgabe vorbereiten</button>
        </article>)}
        {taskSelectionDisabled ? <p className="mail-reader-status">Die Aufgabe wurde bearbeitet oder gespeichert. Weitere Vorschläge überschreiben deine Eingaben nicht.</p> : null}
      </div> : null}
    </> : null}
  </section>;
}
