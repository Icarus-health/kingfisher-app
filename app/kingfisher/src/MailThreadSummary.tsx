import {useEffect, useRef, useState} from 'react';
import {api, type MailThreadContext, type MailThreadSummary as Summary} from './api';
import {ProfileSource} from './ProfileSource';
import {summaryBelongsToContext} from './threadSummary';

export function MailThreadSummary({context, onPrepareTask, taskDisabled}: {context: MailThreadContext;
  onPrepareTask?: (value: {title: string; quote: string; source_digest: string}) => void; taskDisabled?: boolean}) {
  const [result, setResult] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const version = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true; version.current++; pending.current = false;
    setResult(null); setError(''); setBusy(false);
    return () => {alive.current = false; version.current++; controller.current?.abort();};
  }, [context.context_fingerprint]);
  async function create() {
    if (pending.current || context.status !== 'ready') return;
    pending.current = true; setBusy(true); setResult(null); setError('');
    const request = ++version.current;
    controller.current = new AbortController();
    try {
      const value = await api.mailThreadSummary(context.uid, context.context_fingerprint, controller.current.signal);
      if (!alive.current || request !== version.current) return;
      if (!summaryBelongsToContext(value, context)) throw new Error('changed');
      setResult(value);
    } catch {
      if (alive.current && request === version.current) setError('Der Überblick konnte nicht bestätigt werden. Bitte den Verlauf aktualisieren und erneut versuchen.');
    } finally {
      if (request === version.current) {pending.current = false; if (alive.current) setBusy(false);}
    }
  }
  return <section className="mail-thread-summary" aria-label="Kurzüberblick aus Originalstellen">
    <h3>Kurzüberblick</h3>
    <p className="mail-reader-status">Das lokale Modell wählt Originalstellen aus und ordnet sie vorläufig ein. Daraus entsteht kein bestätigter aktueller Stand.</p>
    <button type="button" className="mail-reader-secondary" disabled={busy || context.status !== 'ready'} onClick={() => void create()}>{busy ? 'Originalstellen werden ausgewählt …' : result ? 'Überblick erneut erstellen' : 'Überblick erstellen'}</button>
    {error && <p role="alert" className="mail-reader-error">{error}</p>}
    {result && <>
      <p className="mail-reader-status" role="status">{result.detail}</p>
      {result.warnings.map((warning, index) => <p className="mail-reader-status" key={index}>{warning}</p>)}
      {result.items.map(item => <article key={item.passage_id}>
        <h4>{item.label} · vorläufige Einordnung</h4>
        <blockquote>{item.quote}</blockquote>
        <p className="mail-reader-status">{item.sender || 'Absender unbekannt'} · {item.title} · Quelldatum: {item.occurred_at ? new Date(item.occurred_at).toLocaleString('de-DE') : 'unbekannt'}</p>
        {item.episode_id && <ProfileSource kind="episode" id={item.episode_id} label="Originalquelle prüfen" readOnly />}
        {item.current && item.quote.length >= 8 && onPrepareTask && <>
          <button type="button" className="mail-reader-secondary" disabled={taskDisabled} onClick={() => onPrepareTask({title: `Verlauf prüfen: ${item.title}`, quote: item.quote, source_digest: context.source_digest})}>Verlauf zur Prüfung vormerken</button>
          <p className="mail-reader-status">Bereitet nur einen Prüfauftrag vor. Zusagen und Absagen werden nicht als Aufgaben übernommen. Erst nach deiner Prüfung speichern.</p>
        </>}
      </article>)}
      {!result.items.length && result.available && <p>Keine passende Originalstelle ausgewählt. Das bedeutet nicht, dass keine Aufgabe oder Vereinbarung vorliegt.</p>}
    </>}
  </section>;
}
