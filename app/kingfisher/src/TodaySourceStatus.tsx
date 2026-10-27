import type { MorningBriefing } from './api';
import { sourceStatus } from './dailyFlow';

/** Unter dem Kopf von Heute nur, wenn etwas fehlt: ein Satz, *was* fehlt, und der eine Weg dorthin (Paket U, H4).
 * Ist alles da, steht hier nichts; der Zeitpunkt des Überblicks steht klein im Kopf. Kein Knopf zum Aktualisieren:
 * Heute lädt beim Zurückkommen und alle fünf Minuten von selbst neu. Scheitert das, sagt die Zeile es und bietet
 * „Erneut versuchen“ an. */
/** Vorschläge aus älterer Post, ohne Datum oder mit späterer Mail im Verlauf: ob sie noch gelten, sagt die Post nicht. */
export function pruefSatz(anzahl: number): string {
  return anzahl === 1 ? 'Bei einem Vorschlag ist unklar, ob er noch gilt.' : `Bei ${anzahl} Vorschlägen ist unklar, ob sie noch gelten.`;
}

export function TodaySourceStatus({briefing, refreshing, refreshError, onRefresh}: {
  briefing: MorningBriefing; refreshing: boolean; refreshError: boolean; onRefresh: () => void;
}) {
  const status = sourceStatus(briefing);
  const pruefen = briefing.historical_task_reviews ?? 0;
  if (!status.attention && !refreshError && !pruefen) return null;
  return <div className="today-source-status" role="status" aria-label="Was im Überblick fehlt">
    {status.attention && <p>{status.text}{status.href ? <> <a className="today-text-link" href={status.href}>{status.actionLabel} →</a></>
      : briefing.partial_failures.length > 0 && !refreshError ? <> <button className="today-text-link" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Wird geladen …' : 'Erneut laden'}</button></> : null}</p>}
    {refreshError && <p>Aktualisierung fehlgeschlagen. Angezeigt wird der letzte geladene Stand. <button className="today-text-link" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Wird versucht …' : 'Erneut versuchen'}</button></p>}
    {/* Befund A5: kein „zeitlich ungeklärt“, sondern was unklar ist; „Braucht dich“ sagt dazu „Nichts Neues“. */}
    {pruefen > 0 && <p>{pruefSatz(pruefen)} <a className="today-text-link" href="/vorhaben?view=mine&pruefen=1">Prüfen →</a></p>}
  </div>;
}
