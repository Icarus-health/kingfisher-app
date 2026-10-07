type TaskTarget = {id: string; status?: string; wartet_auf?: string | null; project_id?: string | null};

export function localTaskDay(value: string | null | undefined) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function taskHref(task: TaskTarget) {
  const view = task.status === 'done' ? 'done' : task.wartet_auf ? 'waiting' : 'mine';
  return `/vorhaben?view=${view}&task=${encodeURIComponent(task.id)}${task.project_id ? `&project=${encodeURIComponent(task.project_id)}` : ''}`;
}

function validDay(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00`);
  return !Number.isNaN(date.getTime()) && date.getFullYear() === Number(value.slice(0, 4))
    && date.getMonth() + 1 === Number(value.slice(5, 7)) && date.getDate() === Number(value.slice(8));
}

export function endOfTaskDay(value: string) {
  if (!value) return null;
  if (!validDay(value)) throw new Error('Ungültiger Fälligkeitstag');
  return new Date(`${value}T23:59:00`).toISOString();
}

export function candidateDeadline(source: {temporal_status?: string; valid_until?: string | null}, day: string) {
  if (day && source.temporal_status === 'recent' && source.valid_until && localTaskDay(source.valid_until) === day) return source.valid_until;
  return endOfTaskDay(day);
}

// A deliberately narrow typing aid, never a semantic deadline classifier.
// The user sees the full quote and must explicitly choose the suggested date.
export function explicitDeadline(quote: string): string | null {
  if (/\b(falls|wenn|sofern|voraussichtlich|nicht|kein|keine|alte|bisherige|entfällt|abgesagt|statt|verschoben)\b/i.test(quote)
      || /\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*Uhr\b/i.test(quote)) return null;
  const dates = quote.match(/\b(?:\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})\b/g);
  if (dates?.length !== 1) return null;
  const date = dates[0];
  if (!new RegExp(`\\bbis\\s+(?:(?:zum|spätestens)\\s+)?${date.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?!\\d)`, 'i').test(quote)) return null;
  const parts = date.split('.');
  const day = parts.length === 3 ? `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}` : date;
  return validDay(day) ? day : null;
}
