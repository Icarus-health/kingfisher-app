import type { Attention, MorningBriefing } from './api';

export function sourceStatus(briefing: Pick<MorningBriefing, 'partial_failures' | 'post_ausstehend'>) {
  const failures = briefing.partial_failures;
  const messages = failures.slice(0, 2).map(failure => failure.message);
  if (failures.length > 2) messages.push(`${failures.length - 2} weitere Bereiche nicht verfügbar.`);
  if (briefing.post_ausstehend) messages.push('Posteingang wird noch geladen.');
  return {
    attention: messages.length > 0,
    text: messages.join(' ') || 'Überblick erstellt · Quellen können sich danach geändert haben.',
    href: failures.some(failure => failure.section === 'mail' || failure.section === 'calendar')
      ? '/settings#zugaenge' : '/settings',
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
