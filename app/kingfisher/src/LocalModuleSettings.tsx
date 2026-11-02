import {useEffect, useRef, useState} from 'react';
import {createLocalModuleSetup, emptyLocalModuleSetup, localModuleCanStart, localModulesPost, type LocalModuleSetupSession} from './localModuleSetup';

const statusText = {
  checking: 'Stand wird geprüft …',
  downloading: 'Öffentliche Laufzeit wird geladen …',
  installing: 'Laufzeit wird eingerichtet …',
  verifying: 'Einrichtung wird geprüft …',
  ready: 'Lokale Werkzeuge sind eingerichtet.',
  cancelled: 'Einrichtung abgebrochen.',
  failed: 'Einrichtung fehlgeschlagen. Bitte erneut versuchen.',
  unavailable: 'Noch nicht eingerichtet.',
  unsupported: 'Mac-App aktualisieren.',
  unknown: 'Der Stand der Einrichtung ist noch unklar. Bitte Status prüfen.',
  cancelling: 'Abbruch angefragt. Die Einrichtung kann noch auslaufen …',
};
export function LocalModuleSettings() {
  const [state, setState] = useState({...emptyLocalModuleSetup});
  const owner = useRef<LocalModuleSetupSession | null>(null);
  const startButton = useRef<HTMLButtonElement | null>(null);
  const statusButton = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    const session = createLocalModuleSetup({post: message => localModulesPost(message, window), changed: setState});
    owner.current = session;
    const event = (event: Event) => session.event((event as CustomEvent).detail);
    window.addEventListener('kingfisher:local-modules', event);
    session.probe();
    return () => {window.removeEventListener('kingfisher:local-modules', event); owner.current = null; session.dispose();};
  }, []);
  useEffect(() => {
    if (state.phase === 'unknown') statusButton.current?.focus();
    if (state.phase === 'failed') startButton.current?.focus();
  }, [state.phase]);
  const reconcile = ['unknown', 'unsupported', 'failed', 'cancelled', 'unavailable', 'ready'].includes(state.phase);
  return <div className="source-section" aria-label="Lokale Werkzeuge">
    <p>Eine ausgewählte Quelle lokal mit Qwen 3.5 prüfen. Nur Lesen.</p>
    <p className="source-hint">Einrichten lädt ausschließlich öffentliche Laufzeitdateien herunter.</p>
    <p role={state.phase === 'failed' ? 'alert' : 'status'}>{statusText[state.phase]}</p>
    <div className="source-form-actions">
      {reconcile && <button ref={statusButton} type="button" className="secondary-action" onClick={() => owner.current?.probe()}>Status erneut prüfen</button>}
      {state.pending && <button type="button" className="secondary-action" disabled={state.phase === 'cancelling'} onClick={() => owner.current?.cancel()}>Abbrechen</button>}
      {!['ready', 'unsupported'].includes(state.phase) && <button ref={startButton} type="button" className="primary-action" disabled={!localModuleCanStart(state)} onClick={() => owner.current?.start()}>Einrichten</button>}
    </div>
    <details>
      <summary>Umfang der Einrichtung</summary>
      <p className="source-hint">Die Laufzeit arbeitet später nur mit einer ausdrücklich ausgewählten Quelle und deinem lokalen Qwen-Modell. Sie verändert keine bestätigten Angaben oder Aufgaben. Modell, Cloud-Einstellungen und die Aufnahme deiner Quellen bleiben unverändert.</p>
    </details>
  </div>;
}
