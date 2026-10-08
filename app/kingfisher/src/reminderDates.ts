function parts(value: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

/** Display an ISO reminder as the machine's local datetime-local wall time. */
export function localReminderInput(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : parts(date);
}

/** Convert a datetime-local value to an ISO instant, rejecting invalid dates and DST gaps. */
export function reminderInputToIso(value: string): string | null {
  if (value === "") return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new Error("Bitte Datum und Uhrzeit prüfen.");
  const [, y, mo, d, h, mi] = match;
  const year = Number(y), month = Number(mo), day = Number(d), hour = Number(h), minute = Number(mi);
  const date = new Date(year, month - 1, day, hour, minute, 0, 0);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new Error("Bitte ein gültiges Datum wählen.");
  }
  if (date.getHours() !== hour || date.getMinutes() !== minute) {
    throw new Error("Diese Uhrzeit gibt es wegen der Zeitumstellung nicht. Bitte eine andere Uhrzeit wählen.");
  }
  return date.toISOString();
}

/** Tomorrow at 09:00 in local time, using calendar arithmetic across DST changes. */
export function tomorrowAtNine(now = new Date()): string {
  const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 9, 0, 0, 0);
  return date.toISOString();
}

export function reminderLabel(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
}

/** An untouched form retains its original instant, even after another view changes the task. */
export function reminderEditChanges(original: string | null, input: string): {remind_at?: string | null; expected_remind_at?: string | null} {
  return input === localReminderInput(original) ? {} : {remind_at: reminderInputToIso(input), expected_remind_at: original};
}
