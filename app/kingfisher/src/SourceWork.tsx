import {useEffect, useId, useRef, useState} from 'react';
import {api, type LocalSourceRun} from './api';
import {emptySourceWorkState, SourceWorkSession, sourceWorkEnter, sourceWorkOccupied, visibleSourceWorkRun} from './sourceWorkState';
import './SourceWork.css';

const errors = {
  source_changed: 'Die Quelle hat sich geändert. Bitte die aktuelle Fassung prüfen.',
  prepare: 'Die Prüfung konnte nicht vorbereitet werden. Deine Frage bleibt erhalten.',
  start_unknown: 'Der Start ist noch unklar. Prüfe denselben Start erneut.',
  poll: 'Der aktuelle Stand ist nicht erreichbar. Er wird erneut geprüft.',
  cancel: 'Der Abbruch ist noch nicht bestätigt. Bitte erneut versuchen.',
  busy: 'Eine lokale Prüfung läuft noch.',
  unavailable: 'Die lokale Prüfung ist gerade nicht erreichbar.',
  capacity: 'Zu viele unbestätigte Starts. Bitte später erneut versuchen.',
  expired: 'Die frühere Prüfung ist nicht mehr verfügbar. Du kannst neu starten.',
};
function runStatus(run: LocalSourceRun | null) {
  if (!run) return '';
  if (run.execution_pending && run.status !== 'running') return 'Rechenarbeit läuft noch aus …';
  return {running: 'Lokale Prüfung läuft …', completed: '', cancelled: 'Prüfung abgebrochen.', stale: 'Die Grundlage hat sich geändert. Bitte erneut prüfen.', timed_out: 'Das Zeitlimit wurde erreicht.', failed: 'Die Prüfung konnte nicht abgeschlossen werden.', restarted: 'Die Prüfung wurde durch einen Neustart beendet.'}[run.status];
}

/** A local question and its unverified answer stay in this source pane only. */
export function SourceWork({id, fingerprint, title}: {id: string; fingerprint: string; title: string}) {
  const [state, setState] = useState({...emptySourceWorkState});
  const [expanded, setExpanded] = useState(false);
  const [question, setQuestion] = useState('');
  const current = useRef({id, fingerprint});
  current.current = {id, fingerprint};
  const session = useRef<SourceWorkSession | null>(null);
  const input = useRef<HTMLTextAreaElement | null>(null);
  const retry = useRef<HTMLButtonElement | null>(null);
  const composing = useRef(false);
  const fieldId = useId();
  const blocked = sourceWorkOccupied(state);
  // Compare during render: source polling must hide an old draft before effects.
  const run = visibleSourceWorkRun(state, current.current);
  useEffect(() => {
    const owner = new SourceWorkSession(api, () => current.current, setState);
    session.current = owner; void owner.open();
    return () => {session.current = null; owner.dispose();};
  }, [id]);
  useEffect(() => {session.current?.sourceChanged();}, [id, fingerprint]);
  useEffect(() => {if (state.pendingQuestion !== null) setQuestion(state.pendingQuestion);}, [state.pendingQuestion]);
  useEffect(() => {if (expanded && !blocked) input.current?.focus();}, [expanded]);
  useEffect(() => {
    if (!expanded || !state.error) return;
    if (state.phase === 'uncertain') retry.current?.focus();
    else if (!blocked) input.current?.focus();
  }, [state.error, state.phase]);
  if (!state.available) return null;
  const waiting = state.phase === 'preparing' ? 'Quelle wird geprüft …'
    : state.phase === 'starting' ? 'Prüfung wird gestartet …'
    : state.phase === 'cancelling' ? 'Abbruch wird angefragt …'
    : state.phase === 'uncertain' ? 'Start noch unklar.'
    : runStatus(run ?? state.run);
  const evidence = run?.evidence?.filter(item => item.id === id && item.fingerprint === fingerprint && typeof item.quote === 'string' && item.quote.length > 0) ?? [];
  const draft = run?.status === 'completed' && run.label === 'DRAFT' && run.verified === false && !!run.text?.trim() && evidence.length > 0;
  function submit() {if (!composing.current) void session.current?.start(question);}
  return <div className="source-work">
    <button className="secondary-action" type="button" aria-expanded={expanded} aria-controls={`${fieldId}-panel`} onClick={() => setExpanded(value => !value)}>Lokal mit KI prüfen</button>
    {!expanded && waiting && <p role="status">{waiting}</p>}
    {expanded && <div id={`${fieldId}-panel`} className="source-work-panel" role="group" aria-label="Lokal mit KI prüfen">
      <p id={`${fieldId}-scope`} className="source-work-scope">{title} · Qwen 3.5 · lokal</p>
      <form onSubmit={event => {event.preventDefault(); submit();}}>
        <label htmlFor={fieldId}>Deine Frage</label>
        <textarea ref={input} id={fieldId} value={question} rows={2} maxLength={1200} disabled={blocked}
          aria-describedby={`${fieldId}-scope ${fieldId}-keys${state.error ? ` ${fieldId}-error` : ''}`}
          aria-invalid={state.error === 'prepare' || state.error === 'source_changed' ? true : undefined}
          onChange={event => setQuestion(event.target.value)}
          onCompositionStart={() => {composing.current = true;}}
          onCompositionEnd={() => {composing.current = false;}}
          onKeyDown={event => {if (sourceWorkEnter({key: event.key, shiftKey: event.shiftKey, isComposing: composing.current || event.nativeEvent.isComposing, keyCode: event.nativeEvent.keyCode})) {event.preventDefault(); submit();}}} />
        <p id={`${fieldId}-keys`}>Nur diese Quelle · Enter startet, Umschalt + Enter fügt eine Zeile ein.</p>
        <div className="source-work-actions">
          <button type="submit" className="primary-action" disabled={blocked || state.externalBusy || !question.trim()}>Lokal prüfen</button>
          {state.phase === 'uncertain' && <button ref={retry} type="button" className="secondary-action" onClick={() => void session.current?.retryStart()}>Start erneut prüfen</button>}
          {state.run && (state.run.status === 'running' || state.run.execution_pending) && <button type="button" className="secondary-action" disabled={state.phase === 'cancelling'} onClick={() => void session.current?.cancel()}>Abbrechen</button>}
          {state.externalBusy && !blocked && <button type="button" className="secondary-action" onClick={() => void session.current?.open()}>Belegung erneut prüfen</button>}
        </div>
      </form>
      {waiting && <p role="status">{waiting}</p>}
      {state.externalBusy && !blocked && <p role="status">Eine lokale Prüfung läuft noch.</p>}
      {state.error && <p id={`${fieldId}-error`} className="source-work-error" role="alert">{errors[state.error]}</p>}
      {draft && <div className="source-work-result">
        <strong>Entwurf · ungeprüft</strong>
        {run.coverage?.complete_text_opened !== true && <p>Nur ein Teil der Quelle wurde gelesen{run.coverage ? ` (${run.coverage.opened_characters} von ${run.coverage.source_characters} Zeichen)` : ''}.</p>}
        <div className="source-work-draft">{run.text}</div>
        <details>
          <summary>Originalbelege ({evidence.length})</summary>
          {evidence.map((item, index) => <blockquote key={`${item.start}:${item.end}:${index}`}>{item.quote}</blockquote>)}
        </details>
      </div>}
    </div>}
  </div>;
}
