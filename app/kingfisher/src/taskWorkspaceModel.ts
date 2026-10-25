type Dated = {due?: string | null};
type BoardTask = {status?: string; wartet_auf?: string | null};

export function groupTasks<T extends Dated>(tasks: T[], now = new Date()) {
  const groups: Array<{label: string; items: T[]}> = [
    {label:'Überfällig',items:[]}, {label:'Heute',items:[]},
    {label:'Demnächst',items:[]}, {label:'Ohne Termin',items:[]},
  ];
  const start = new Date(now.getFullYear(),now.getMonth(),now.getDate()).getTime();
  const end = new Date(now.getFullYear(),now.getMonth(),now.getDate()+1).getTime();
  for (const task of tasks) {
    const time = task.due ? new Date(task.due).getTime() : NaN;
    groups[Number.isNaN(time) ? 3 : time < start ? 0 : time < end ? 1 : 2].items.push(task);
  }
  return groups;
}

/** Was die Liste zeigt: nur Gruppen mit Aufgaben. Eine leere Gruppe ist Lärm, keine Auskunft. */
export function visibleTaskGroups<T extends Dated>(tasks: T[], now = new Date()) {
  return groupTasks(tasks, now).filter(group => group.items.length > 0);
}

export function projectColumns<T extends BoardTask>(tasks: T[]) {
  return [
    {label:'Offen',items:tasks.filter(t=>t.status==='open' && !t.wartet_auf)},
    {label:'Wartend',items:tasks.filter(t=>t.status==='open' && Boolean(t.wartet_auf))},
    {label:'Erledigt',items:tasks.filter(t=>t.status==='done')},
  ];
}

/** Fälligkeit, wie man sie sagt: „Heute“, „Morgen“, „Gestern“, sonst „2. Okt.“ (mit Jahr, wenn es ein anderes ist). */
export function dueLabel(value: string | null, now = new Date()) {
  if (!value) return "Ohne Termin";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Termin nicht lesbar";
  const start = (item: Date) => new Date(item.getFullYear(), item.getMonth(), item.getDate()).getTime();
  const days = Math.round((start(date) - start(now)) / 86_400_000);
  if (days === 0) return "Heute";
  if (days === 1) return "Morgen";
  if (days === -1) return "Gestern";
  return new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short", ...(date.getFullYear() !== now.getFullYear() ? {year: "numeric"} : {}) }).format(date);
}

/** Die Zeile unter „Aufgaben“: wie viele Aufgaben heute dran oder überfällig sind.
 *
 * Gezählt werden die geladenen Zeilen; die Liste kommt nach Fälligkeit sortiert und seitenweise. Ist die erste Seite bis
 * zur letzten Zeile fällig und gibt es weitere Seiten, wäre die Zahl die Seitengröße (bei 300 Aufgaben stand „50“).
 * Dann steht „Mehr als …“. Auf späteren Seiten lässt sich nichts zählen, die Zeile entfällt. */
export function heuteKopfZeile(dran: number, geladen: number, {seite, weitere}: {seite: number; weitere: boolean}): string | undefined {
  if (seite > 1 || dran < 1) return undefined;
  if (weitere && dran >= geladen) return `Mehr als ${dran} Aufgaben brauchen dich heute.`;
  return dran === 1 ? "Eine Aufgabe braucht dich heute." : `${dran} Aufgaben brauchen dich heute.`;
}
