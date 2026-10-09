type TimedEvent = { start?: string | null; end?: string | null };

export function findCalendarEvent<T extends TimedEvent & {uid: string; source_copies?: Array<{uid: string; source_id: string; source_label: string}>}>(items: T[], uid: string, start?: string | null): T | null {
  const stamp = start ? new Date(start).getTime() : null;
  const matches = items.flatMap(item => {
    if (stamp !== null && !(item.start && new Date(item.start).getTime() === stamp)) return [];
    if (item.uid === uid) return [item];
    const copy = item.source_copies?.find(copy => copy.uid === uid);
    return copy ? [{...item, ...copy}] : [];
  });
  return matches.length === 1 ? matches[0] : null;
}
export type CalendarView = "Liste" | "Woche" | "Monat" | "Jahr";

/** Return the exact local-time interval rendered by a calendar view. `until` is exclusive. */
export function calendarWindow(focus: Date, view: CalendarView, today = new Date()): {from: Date; until: Date} {
  const day = (value: Date) => new Date(value.getFullYear(), value.getMonth(), value.getDate());
  const plusDays = (value: Date, count: number) => new Date(value.getFullYear(), value.getMonth(), value.getDate() + count);
  if (view === "Liste") {
    const from = day(today);
    return {from, until: plusDays(from, 7)};
  }
  if (view === "Woche") {
    const from = day(focus);
    from.setDate(from.getDate() - ((from.getDay() + 6) % 7));
    return {from, until: plusDays(from, 7)};
  }
  if (view === "Monat") {
    return {
      from: new Date(focus.getFullYear(), focus.getMonth(), 1),
      until: new Date(focus.getFullYear(), focus.getMonth() + 1, 1),
    };
  }
  return {from: new Date(focus.getFullYear(), 0, 1), until: new Date(focus.getFullYear() + 1, 0, 1)};
}

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

export function preparationView<T extends string>(view: T, at: Date | null, today: Date): T | 'Monat' {
  if (view !== 'Liste' || !at) return view;
  const from = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const until = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7);
  return at >= from && at < until ? view : 'Monat';
}

/** Preserve the source-specific destination for each action on a proven copy. */
export function calendarSourceVersions<T extends {uid: string; source_copies?: Array<{uid: string; source_id: string; source_label: string}>}>(item: T): T[] {
  return item.source_copies?.length ? item.source_copies.map(copy => ({...item, ...copy})) : [item];
}
