import { useEffect, useRef, useState } from 'react';
import { api } from './api';

export function MailQuickTask({uid, title, quote, sourceDigest, disabled, onSaved}: {
  uid: string; title: string; quote: string; sourceDigest: string; disabled: boolean; onSaved?: () => void;
}) {
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle');
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => {alive.current = false;}; }, []);
  async function accept() {
    if (pending.current || disabled || state === 'saved') return;
    pending.current = true; setState('saving');
    try {
      await api.addMailTask(uid, {title, source_quote: quote, source_digest: sourceDigest,
        project_id: null, due: null, waiting_for: null, quick_accept: true});
      if (alive.current) {setState('saved'); onSaved?.();}
    } catch { if (alive.current) setState('failed'); }
    finally {pending.current = false;}
  }
  return <div className="mail-quick-task">
    <button className="mail-reader-primary" type="button" disabled={disabled || state === 'saving' || state === 'saved'} onClick={() => void accept()}>
      {state === 'saved' ? 'Aufgabe übernommen' : state === 'saving' ? 'Wird übernommen …' : 'Als Aufgabe übernehmen'}
    </button>
    {state === 'saved' && <p className="mail-reader-status" role="status">Ohne Datum und weitere Zuordnung gespeichert. <a href="/vorhaben?view=mine">Aufgabe ansehen</a></p>}
    {state === 'failed' && <p className="mail-reader-error" role="alert">Übernahme fehlgeschlagen. Bei geänderter Quelle bitte die Nachricht neu öffnen; sonst erneut versuchen.</p>}
  </div>;
}
