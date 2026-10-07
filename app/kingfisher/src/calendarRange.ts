type TimedEvent = { start?: string | null; end?: string | null };

/** Calendar end timestamps are exclusive; missing ends describe point events. */
export function eventsInRange<T extends TimedEvent>(items: T[], from: Date, until: Date): T[] {
  const lower = from.getTime(), upper = until.getTime();
  return items.filter(event => {
    const start = event.start ? new Date(event.start).getTime() : NaN;
    if (!Number.isFinite(start) || start >= upper) return false;
    const end = event.end ? new Date(event.end).getTime() : NaN;
    return Number.isFinite(end) && end > start ? end > lower : start >= lower;
  });
}
