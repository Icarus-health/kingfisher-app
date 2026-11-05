import {useEffect, useId, useMemo, useRef, useState, type FormEvent} from 'react';
import {api, ApiError, type ResponsibilityContact, type Task, type TaskResponsibilityCommand, type TaskResponsibilitySnapshot} from './api';
import {newTaskRequestId} from './taskSaveAttempt';
import {responsibilityAttempt, responsibilityChange, responsibilityDraft, responsibilityFailure, responsibilityLabel} from './taskResponsibilityModel';

export function TaskResponsibility({task, refreshKey, disabled, beginMutation, onSnapshot}: {
  task: Task;
  refreshKey: number;
  disabled: boolean;
  beginMutation: () => (() => void) | null;
  onSnapshot: (snapshot: TaskResponsibilitySnapshot, changed: boolean, generation: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<TaskResponsibilitySnapshot | null>(null);
  const [draft, setDraft] = useState(() => responsibilityDraft(task.responsibility));
  const [review, setReview] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<TaskResponsibilityCommand | null>(null);
  const [contacts, setContacts] = useState<ResponsibilityContact[] | null>(null);
  const [contactError, setContactError] = useState(false);
  const [contactRetry, setContactRetry] = useState(0);
  const datalistId = useId();
  const active = useRef(true);
  const inFlight = useRef(false);
  const latest = useRef<TaskResponsibilitySnapshot | null>(null);
  const loadedGeneration = useRef<number | undefined>(undefined);
  const currentGeneration = useRef(refreshKey);
  currentGeneration.current = refreshKey;
  const updateParent = useRef(onSnapshot);
  updateParent.current = onSnapshot;

  function publish(value: TaskResponsibilitySnapshot, changed: boolean, generation: number) {
    if (generation !== currentGeneration.current || (latest.current && value.revision < latest.current.revision)) {
      return latest.current;
    }
    latest.current = value;
    loadedGeneration.current = generation;
    setSnapshot(value);
    updateParent.current(value, changed, generation);
    return value;
  }

  useEffect(() => {
    active.current = true;
    return () => {active.current = false;};
  }, []);
  useEffect(() => {
    let current = true;
    setLoading(true);
    api.taskResponsibility(task.id).then(value => {
      if (!current || refreshKey !== currentGeneration.current) return;
      if (publish(value, retry > 0, refreshKey) !== value) {
        setError('Der geladene Stand ist älter als die angezeigte Aufgabe.');
        return;
      }
      setReview(false);
      setError('');
    }).catch(() => {
      if (current && refreshKey === currentGeneration.current) setError('Die Zuständigkeit konnte gerade nicht geladen werden.');
    }).finally(() => {
      if (current && refreshKey === currentGeneration.current) setLoading(false);
    });
    return () => {current = false;};
  }, [task.id, refreshKey, retry]);

  const showContacts = open && draft.choice === 'person';
  useEffect(() => {
    if (!showContacts || contacts) return;
    let current = true;
    setContactError(false);
    api.responsibilityContacts().then(value => {
      if (current) setContacts(value);
    }).catch(() => {
      if (current) setContactError(true);
    });
    return () => {current = false;};
  }, [showContacts, contacts, contactRetry]);

  function toggle() {
    if (!open && !pending && !review) setDraft(responsibilityDraft(snapshot ? snapshot.task.responsibility : task.responsibility));
    setOpen(value => !value);
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || disabled || loading || review || loadedGeneration.current !== refreshKey) return;
    const command = responsibilityAttempt(snapshot, draft, pending, newTaskRequestId);
    if (!command) return;
    const release = beginMutation();
    if (!release) return;
    inFlight.current = true;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await api.changeTaskResponsibility(task.id, command);
      if (!active.current) return;
      const current = publish(result, true, refreshKey);
      setPending(null);
      const displayed = current && current.revision >= result.revision ? current : result;
      setDraft(responsibilityDraft(displayed.task.responsibility));
      setNotice(current !== result || (result.replayed && result.applied_event_sequence !== result.responsibility_event_sequence)
        ? 'Speicherung bestätigt.' : 'Zuständigkeit gespeichert.');
    } catch (cause) {
      if (!active.current) return;
      const failure = responsibilityFailure(cause instanceof ApiError ? cause.status : undefined);
      setPending(failure === 'retry' ? command : null);
      setReview(failure === 'review');
      setError(failure === 'review' ? 'Die Aufgabe wurde geändert. Lade den aktuellen Stand und prüfe deine Eingaben erneut.'
        : failure === 'edit' ? (cause as ApiError).detail ?? 'Bitte prüfe die Eingaben.'
        : 'Die Speicherung ist unklar. Erneut versuchen prüft denselben Auftrag.');
    } finally {
      inFlight.current = false;
      release();
      if (active.current) setBusy(false);
    }
  }

  const locked = disabled || busy || loading || loadedGeneration.current !== refreshKey;
  const owner = snapshot ? snapshot.task.responsibility : task.responsibility;
  const choices = useMemo(() => {
    const byAddress = new Map<string, string>();
    for (const contact of contacts ?? []) {
      for (const address of contact.adressen ?? []) if (!byAddress.has(address)) byAddress.set(address, contact.name);
    }
    return [...byAddress];
  }, [contacts]);
  const outdatedUndo = draft.choice === 'undo' && draft.undoTarget !== snapshot?.responsibility_event_sequence;
  const canConfirm = !review && (pending !== null || Boolean(responsibilityChange(snapshot, draft)));
  return <section className="task-responsibility" aria-label="Zuständigkeit">
    <button className="task-aufklapper" type="button" aria-expanded={open} disabled={busy} onClick={toggle}>
      Zuständigkeit · {responsibilityLabel(owner)}
    </button>
    {snapshot?.own_address_overlap && <p role="status">Die bestätigte Personenadresse gehört inzwischen zu deinen Konten. Bitte prüfe die Zuständigkeit.</p>}
    {open && <form onSubmit={confirm}>
      {loading && <p role="status">Zuständigkeit wird geladen …</p>}
      {error && <p role="alert">{error} {(review || loadedGeneration.current !== refreshKey) && !loading &&
        <button className="text-action" type="button" onClick={() => setRetry(value => value + 1)}>Aktuellen Stand laden</button>}</p>}
      {notice && <p role="status">{notice}</p>}
      {outdatedUndo && <p role="status">Diese Änderung lässt sich nicht mehr zurücknehmen. Du kannst die letzte Änderung auswählen.</p>}
      <label>Ausführung<select value={draft.choice === 'undo' ? owner?.decision ?? '' : draft.choice}
        disabled={locked || Boolean(pending)}
        onChange={event => {setNotice(''); setDraft({...draft, choice: event.target.value as typeof draft.choice});}}>
        <option value="" disabled>Auswählen</option>
        <option value="self">Ich</option>
        <option value="person">Person</option>
        <option value="unknown">Ungeklärt</option>
      </select></label>
      {showContacts && <div className="task-responsibility-person">
        <label>Vollständige Mailadresse<input value={draft.address} maxLength={254} autoComplete="off" list={datalistId}
          disabled={locked || Boolean(pending)} onChange={event => setDraft({...draft, address: event.target.value})} /></label>
        <datalist id={datalistId}>{choices.map(([address, name]) => <option key={address} value={address} label={name} />)}</datalist>
        <label>Bestätigter Anzeigename (optional)<input value={draft.label} maxLength={120} autoComplete="off"
          disabled={locked || Boolean(pending)} onChange={event => setDraft({...draft, label: event.target.value})} /></label>
        {contactError && <p>Kontakte sind gerade nicht verfügbar. Die Adresse kannst du direkt eingeben. <button className="text-action" type="button"
          onClick={() => setContactRetry(value => value + 1)}>Kontakte erneut laden</button></p>}
      </div>}
      {draft.choice === 'unknown' && owner?.decision !== 'unknown' && <p>Die Zuständigkeit wird ausdrücklich auf Ungeklärt gesetzt.</p>}
      {draft.choice === 'undo' && !outdatedUndo && <p>Die letzte Zuständigkeitsänderung wird zurückgenommen.</p>}
      <div className="task-responsibility-actions">
        <button className="secondary-action" type="submit" disabled={locked || !canConfirm}>
          {pending ? 'Erneut versuchen' : draft.choice === 'undo' ? 'Rückgängig bestätigen' : draft.choice === 'unknown' ? 'Zurücksetzen bestätigen' : 'Zuständigkeit bestätigen'}
        </button>
        {snapshot?.responsibility_event_sequence != null && draft.choice !== 'undo' &&
          <button className="text-action" type="button" disabled={locked || Boolean(pending) || review}
            onClick={() => setDraft({...draft, choice: 'undo', undoTarget: snapshot.responsibility_event_sequence!})}>Letzte Änderung rückgängig machen</button>}
        {draft.choice === 'undo' && <button className="text-action" type="button" disabled={locked || Boolean(pending)}
          onClick={() => setDraft(responsibilityDraft(owner))}>Rückgängig abbrechen</button>}
        {outdatedUndo && snapshot?.responsibility_event_sequence != null &&
          <button className="text-action" type="button" disabled={locked || Boolean(pending) || review}
            onClick={() => setDraft({...draft, undoTarget: snapshot.responsibility_event_sequence!})}>Letzte Änderung auswählen</button>}
      </div>
    </form>}
  </section>;
}
