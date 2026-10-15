import type { MorningBriefing } from './api';
import { sourceStatus } from './dailyFlow';

export function TodaySourceStatus({briefing, refreshing, refreshError, onRefresh}: {
  briefing: MorningBriefing; refreshing: boolean; refreshError: boolean; onRefresh: () => void;
}) {
  const status = sourceStatus(briefing);
  const date = new Date(briefing.generated_at);
  let timestamp = 'Zeitpunkt unbekannt';
  if (!Number.isNaN(date.getTime())) {
    try { timestamp = new Intl.DateTimeFormat('de-DE', {dateStyle: 'short', timeStyle: 'short', timeZone: briefing.timezone}).format(date); }
    catch { timestamp = date.toLocaleString('de-DE'); }
  }
  return <details className="today-source-status" aria-label="Stand deines Überblicks">
    <summary><span>{status.attention || refreshError ? 'Überblick unvollständig' : 'Überblick erstellt'}</span><time dateTime={briefing.generated_at}>{timestamp}</time>{Boolean(briefing.historical_task_reviews) && <span>{briefing.historical_task_reviews} zeitlich zu prüfen</span>}</summary>
    <div>
      {briefing.partial_failures.length ? <ul>{briefing.partial_failures.map((failure,index)=><li key={`${failure.section}:${index}`}>{failure.message}</li>)}</ul> : <p>{status.text}</p>}
      {briefing.post_ausstehend && briefing.partial_failures.length > 0 && <p>Posteingang wird noch geladen.</p>}
      {refreshError && <p role="status">Aktualisierung fehlgeschlagen. Angezeigt wird der letzte geladene Stand.</p>}
    </div>
    <div className="today-source-actions">
      {Boolean(briefing.historical_task_reviews) && <a className="today-text-link" href="/vorhaben?view=mine&pruefen=1">{briefing.historical_task_reviews} zeitlich ungeklärte Vorschläge prüfen →</a>}
      {status.attention && <a className="today-text-link" href={status.href}>{status.actionLabel} →</a>}
      <button className="today-text-link" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Wird aktualisiert …' : 'Überblick aktualisieren'}</button>
    </div>
  </details>;
}
