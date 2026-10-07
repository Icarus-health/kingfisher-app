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
  return <section className="today-source-status" aria-label="Stand deines Überblicks">
    <div><strong>{status.attention || refreshError ? 'Dein Überblick ist noch unvollständig' : 'Stand deines Überblicks'}</strong>
      <p>{status.text}</p>
      <p className="today-context-note"><time dateTime={briefing.generated_at}>{timestamp}</time></p>
      {refreshError && <p role="status">Aktualisierung fehlgeschlagen. Angezeigt wird der letzte geladene Stand.</p>}
    </div>
    <div className="today-source-actions">
      {status.attention && <a className="today-text-link" href={status.href}>Quellen prüfen →</a>}
      <button className="today-text-link" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Wird aktualisiert …' : 'Überblick aktualisieren'}</button>
    </div>
  </section>;
}
