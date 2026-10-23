import type { MorningBriefing } from './api';
import { sourceStatus } from './dailyFlow';

/** Unter dem Kopf von Heute nur, wenn etwas fehlt: ein Satz, *was* fehlt, und der eine Weg dorthin (Paket U, H4).
 * Ist alles da, steht hier nichts; der Zeitpunkt des Überblicks steht klein im Kopf. Kein Knopf zum Aktualisieren:
 * Heute lädt beim Zurückkommen und alle fünf Minuten von selbst neu. Scheitert das, sagt die Zeile es und bietet
 * „Erneut versuchen“ an. */
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
    {pruefen > 0 && <p>{pruefen === 1 ? 'Ein Vorschlag ist zeitlich ungeklärt.' : `${pruefen} Vorschläge sind zeitlich ungeklärt.`} <a className="today-text-link" href="/vorhaben?view=mine&pruefen=1">Prüfen →</a></p>}
  </div>;
}
