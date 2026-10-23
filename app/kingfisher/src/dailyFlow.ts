import type { Attention, MorningBriefing } from './api';

/** Was auf Heute fehlt, in Sätzen, und der eine Weg dorthin (Paket U, H4). Fehlt nichts, steht nichts da. */
export function sourceStatus(briefing: Pick<MorningBriefing, 'partial_failures' | 'post_ausstehend'>) {
  const failures = briefing.partial_failures;
  const messages = failures.slice(0, 2).map(failure => failure.message);
  if (failures.length > 2) messages.push(failures.length === 3 ? 'Dazu ein weiterer Hinweis.' : `Dazu ${failures.length - 2} weitere Hinweise.`);
  if (briefing.post_ausstehend) messages.push('Die Post von heute ist noch nicht da. Kingfisher holt sie gerade.');
  const reviewOnly = failures.length > 0 && failures.every(failure => failure.section === 'source_review') && !briefing.post_ausstehend;
  const zugang = failures.some(failure => failure.section === 'mail' || failure.section === 'calendar');
  return {
    attention: messages.length > 0,
    text: messages.join(' '),
    // Nur ein Weg, der wirklich weiterhilft: zu den Zugängen, zu den Aufgaben, sonst keiner (Heute lädt von selbst neu).
    actionLabel: zugang ? 'Zugänge prüfen' : reviewOnly ? 'Aufgaben prüfen' : null,
    href: zugang ? '/settings#zugaenge' : reviewOnly ? '/vorhaben?view=mine' : null,
  };
}

export function activityAction(item: Pick<Attention, 'source' | 'source_ref'>) {
  return item.source === 'mail' && item.source_ref ? {uid: item.source_ref, label: 'Nachricht öffnen'} : null;
}

/** One in-flight request; automatic refresh is throttled even after failure. */
export function createDailyRefresh<T>(read: () => Promise<T>, apply: (value: T) => void, now = Date.now) {
  let active = true;
  let running = false;
  let lastAttempt = -Infinity;
  let followUp = false;
  const refresh = {
    async run(explicit = false): Promise<'updated' | 'failed' | 'skipped'> {
      if (!active) return 'skipped';
      if (running) { if (explicit) followUp = true; return 'skipped'; }
      if (!explicit && now() - lastAttempt < 60000) return 'skipped';
      running = true;
      lastAttempt = now();
      try {
        const value = await read();
        if (!active) return 'skipped';
        apply(value);
        return 'updated';
      } catch {
        return active ? 'failed' : 'skipped';
      } finally {
        running = false;
        if (followUp && active) { followUp = false; await refresh.run(true); }
      }
    },
    dispose() { active = false; },
  };
  return refresh;
}

export function dailyIntroduction(text: string, hasRows: boolean, incomplete: boolean) {
  return incomplete && !hasRows ? 'Dein Tag ist noch nicht vollständig erfasst.' : text;
}
