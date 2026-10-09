import {useEffect, useRef, useState} from 'react';
import {api, type CalendarActionDraft, type CalendarActionInput, type CalendarActionSource, type CalendarOverview} from './api';
import {GoogleSignIn} from './GoogleSignIn';
import {calendarActionState, calendarInputInstant, editableEventId, localDateTime} from './calendarActionState';

const recoveryKey = 'kingfisher.calendar-action.last.v1';
function savedDraft(): string | null { try {return localStorage.getItem(recoveryKey);} catch {return null;} }
function remember(id: string) { try {localStorage.setItem(recoveryKey, id);} catch { /* The server retains the draft regardless. */ } }
const when = (value?: {dateTime?: string; date?: string} | null) => value?.dateTime
  ? `${new Date(value.dateTime).toLocaleString('de-DE')} (${value.dateTime})` : value?.date || 'Nicht angegeben';
const updates = {all:'Alle Gäste benachrichtigen', externalOnly:'Nur externe Gäste benachrichtigen', none:'Keine Google-Benachrichtigungen angefordert'};

export function CalendarActionForm({event, preparedDraft, onClose, onDone}: {
  event?: CalendarOverview['items'][number]; preparedDraft?: CalendarActionDraft; onClose: () => void; onDone: () => void;
}) {
  const [sources, setSources] = useState<CalendarActionSource[]>([]);
  const [sourceId, setSourceId] = useState(event?.source_id || '');
  const [kind, setKind] = useState<CalendarActionInput['kind']>(event ? 'edit' : 'create');
  const [title, setTitle] = useState(event?.summary || '');
  const [start, setStart] = useState(localDateTime(event?.start));
  const [end, setEnd] = useState(localDateTime(event?.end));
  const [sendUpdates, setSendUpdates] = useState<CalendarActionInput['send_updates']>('all');
  const [draft, setDraft] = useState<CalendarActionDraft | null>(preparedDraft ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mustRead, setMustRead] = useState(false);
  const [showRights, setShowRights] = useState(false);
  const [revision, setRevision] = useState(0);
  const [recovery, setRecovery] = useState(savedDraft);
  const heading = useRef<HTMLHeadingElement>(null);
  const lock = useRef(false), lifecycle = useRef(0);
  useEffect(() => {heading.current?.focus(); heading.current?.scrollIntoView({block:"start"});}, []);
  useEffect(() => {
    const current = ++lifecycle.current;
    api.calendarActionSources().then(result => {
      if (current !== lifecycle.current) return;
      setSources(result.sources);
      if (!event) setSourceId(old => result.sources.some(s => s.id === old) ? old : result.sources[0]?.id || '');
    }).catch(() => {if (current === lifecycle.current) setError('Kalenderrechte konnten nicht geladen werden. Bitte erneut versuchen.');});
    return () => {lifecycle.current++;};
  }, [revision, event]);
  async function run(action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    const current = lifecycle.current;
    try {await action();} catch (e) {if (current === lifecycle.current) setError(e instanceof Error ? e.message : 'Aktion fehlgeschlagen.');}
    finally {lock.current = false; if (current === lifecycle.current) setBusy(false);}
  }
  const source = sources.find(s => s.id === sourceId);
  const status = draft ? calendarActionState(draft.status) : null;
  const clear = () => {setDraft(null); setMustRead(false); setError('');};
  const readDraft = (id: string) => run(async () => {
    const current = lifecycle.current;
    const result = await api.calendarActionRead(id);
    if (current !== lifecycle.current) return;
    setDraft(result); setMustRead(false);
    if (result.status === 'done') onDone();
  });
  return <section className="source-section calendar-action-form" aria-label="Terminänderung vorbereiten">
    <h2 ref={heading} tabIndex={-1}>{preparedDraft ? 'Termin aus der Mail prüfen' : event ? 'Termin bearbeiten oder absagen' : 'Neuen Termin vorbereiten'}</h2>
    <p>{preparedDraft ? 'Prüfe diese Vorschau einschließlich Kalender und Zeitangaben. Die Mailgrundlage wird vor dem verbindlichen Schreiben erneut geprüft.' : 'Zeiten auf diesem Gerät. Erst die bestätigte Vorschau ändert deinen Google-Kalender. Serientermine und fremde Einladungen bearbeitest du vorerst direkt bei Google. Absagen sind hier nur für die bestätigte Organisator-Kopie möglich.'}</p>
    <button type="button" className="text-action" disabled={busy} onClick={onClose}>Schließen</button>
    {error && <p role="alert">{error}</p>}
    {!draft && <form onSubmit={e => {
      e.preventDefault();
      void run(async () => {
        const current = lifecycle.current;
        const input: CalendarActionInput = {kind, source_id:sourceId, send_updates:sendUpdates};
        if (kind !== 'cancel') {
          input.title = title;
          input.start = calendarInputInstant(start, event?.start);
          input.end = calendarInputInstant(end, event?.end);
        }
        if (event) {const id = editableEventId(event); if (!id) throw new Error('Dieser Termin hat keine eindeutige Google-Kennung.'); input.event_id = id;}
        const result = await api.calendarActionDraft(input);
        remember(result.id);
        if (current !== lifecycle.current) return;
        setRecovery(result.id); setDraft(result); setMustRead(false);
      });
    }}>
      <fieldset disabled={busy}>
        <label>Kalender <select value={sourceId} disabled={!!event} onChange={e => {setSourceId(e.target.value); clear();}} required>
          <option value="">Kalender wählen</option>{sources.map(s => <option key={s.id} value={s.id}>{s.label} · {s.user}{s.can_write ? '' : ' · nur lesen'}</option>)}
        </select></label>
        {event && <label>Aktion <select value={kind} onChange={e => {setKind(e.target.value as CalendarActionInput['kind']); clear();}}><option value="edit">Termin ändern</option><option value="cancel">Termin absagen</option></select></label>}
        {kind !== 'cancel' && <>
          <label>Titel <input value={title} required maxLength={500} onChange={e => setTitle(e.target.value)} /></label>
          <label>Beginn <input type="datetime-local" value={start} required onChange={e => setStart(e.target.value)} /></label>
          <label>Ende <input type="datetime-local" value={end} required onChange={e => setEnd(e.target.value)} /></label>
        </>}
        <label>Gäste informieren <select value={sendUpdates} onChange={e => setSendUpdates(e.target.value as CalendarActionInput['send_updates'])}>{Object.entries(updates).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <p>Google kann auch bei „keine angefordert“ einzelne Systemnachrichten senden. Gäste werden hier nicht neu hinzugefügt.</p>
        {source && !source.can_write && <p>{source.reason || 'Dieser Kalender ist bisher nur zum Lesen verbunden.'} <button type="button" className="text-action" onClick={() => setShowRights(true)}>Änderungen erlauben</button></p>}
        {!sources.length && <p>Verbinde zuerst einen Google-Kalender unter <a href="/settings#zugaenge">Zugänge</a>.</p>}
        <button type="submit" className="secondary-action" disabled={!source?.can_write}>{busy ? 'Wird geprüft …' : 'Vorschau erstellen'}</button>
      </fieldset>
    </form>}
    {showRights && <GoogleSignIn kind="calendar_write" active onConnected={() => {setShowRights(false); setRevision(n => n+1);}} />}
    {draft && <div aria-live="polite">
      <h3>{draft.kind === 'cancel' ? 'Absage prüfen' : 'Termin prüfen'}</h3>
      <p><strong>{draft.preview.calendar}</strong> · {draft.preview.account}</p>
      {draft.preview.current && <div><h4>Bisher</h4><p>{draft.preview.current.summary}</p><p>{when(draft.preview.current.start)} bis {when(draft.preview.current.end)}</p>{draft.preview.current.location && <p>{draft.preview.current.location}</p>}</div>}
      {draft.kind !== 'cancel' && <div><h4>Vorgesehener Stand</h4><p>{draft.preview.title}</p><p>{when(draft.preview.start)} bis {when(draft.preview.end)}</p></div>}
      <p>Gäste: {draft.preview.attendees.join(', ') || 'Keine'}</p>
      <p>{updates[draft.preview.send_updates]}</p>
      <p role="status">{mustRead ? 'Antwort nicht erhalten. Prüfe zuerst den gespeicherten Status; die Änderung wird nicht automatisch wiederholt.' : status?.message}</p>
      {status?.canExecute && !mustRead && <button type="button" className="secondary-action" disabled={busy} onClick={() => run(async () => {
        const current = lifecycle.current;
        // Persist the ID before requesting any external effect. A lost response
        // must go through status recovery instead of a second blind submit.
        remember(draft.id); setMustRead(true);
        const result = await api.calendarActionExecute(draft);
        if (current !== lifecycle.current) return;
        setDraft(result); setMustRead(false);
        if (result.status === 'done') onDone();
      })}>{draft.kind === 'cancel' ? 'Absage verbindlich bestätigen' : 'Änderung verbindlich bestätigen'}</button>}
      {(mustRead || draft.status === 'running' || draft.status === 'uncertain') && <button type="button" className="secondary-action" disabled={busy} onClick={() => readDraft(draft.id)}>Gespeicherten Status prüfen</button>}
      <p><a href="https://calendar.google.com/" target="_blank" rel="noopener noreferrer">Google-Kalender öffnen</a></p>
      <button type="button" className="text-action" disabled={busy || mustRead || draft.status === 'running' || draft.status === 'uncertain'} onClick={preparedDraft ? onClose : clear}>{preparedDraft ? 'Angaben im Mailentwurf ändern' : 'Neuen Entwurf vorbereiten'}</button>
    </div>}
    {!draft && recovery && <button type="button" className="text-action" disabled={busy} onClick={() => readDraft(recovery)}>Letzten gespeicherten Entwurf prüfen</button>}
  </section>;
}
