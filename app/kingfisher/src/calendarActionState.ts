export function localDateTime(value?: string | null): string {
  if (!value || !value.includes('T')) return '';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const two = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${two(date.getMonth()+1)}-${two(date.getDate())}T${two(date.getHours())}:${two(date.getMinutes())}`;
}

export function editableEventId(event: {uid: string; source_id?: string}): string | null {
  const prefix = event.source_id ? `${event.source_id}:` : '';
  return prefix && event.uid.startsWith(prefix) && event.uid.length > prefix.length ? event.uid.slice(prefix.length) : null;
}

export function calendarActionState(status: string): {canExecute: boolean; message: string} {
  if (status === 'draft') return {canExecute:true, message:'Entwurf geprüft. Es wurde noch nichts im Kalender geändert.'};
  if (status === 'done') return {canExecute:false, message:'Änderung von Google bestätigt.'};
  if (status === 'uncertain') return {canExecute:false, message:'Ergebnis unklar. Bitte den Termin bei Google prüfen. Kingfisher führt die Änderung nicht erneut aus.'};
  if (status === 'running') return {canExecute:false, message:'Ausführung läuft oder wurde unterbrochen. Bitte den Status prüfen; nicht erneut anlegen.'};
  return {canExecute:false, message:'Dieser Entwurf kann nicht ausgeführt werden. Bitte den Kalender prüfen und bei Bedarf einen neuen Entwurf erstellen.'};
}

export function calendarInputInstant(value: string, original?: string | null): string {
  // An unchanged input must retain the provider's exact instant, particularly
  // the second occurrence of a repeated clock hour and existing seconds.
  if (original && localDateTime(original) === value) return original;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime()) || localDateTime(date.toISOString()) !== value) throw new Error('Bitte gültige lokale Zeiten angeben. Prüfe auch die Zeitumstellung.');
  for (let minutes = 15; minutes <= 180; minutes += 15) {
    if ([-1, 1].some(sign => localDateTime(new Date(date.getTime() + sign * minutes * 60000).toISOString()) === value)) throw new Error('Diese lokale Zeit kommt bei der Zeitumstellung zweimal vor. Bitte den Termin mit eindeutiger Zeitzone direkt bei Google festlegen.');
  }
  return date.toISOString();
}
