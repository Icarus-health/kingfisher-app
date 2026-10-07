import {useEffect, useState} from 'react';
import {api, type MailThreadContext} from './api';
import {ProfileSource} from './ProfileSource';

export function MailThread({uid, expectedDigest}: {uid: string; expectedDigest?: string}) {
  const [result, setResult] = useState<MailThreadContext | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    let controller: AbortController | null = null;
    let version = 0;
    async function refresh() {
      controller?.abort();
      const current = ++version;
      controller = new AbortController();
      setResult(null); setError(''); setLoading(true);
      try {
        const value = await api.mailThread(uid, controller.signal);
        if (!active || current !== version) return;
        if (value.uid !== uid || !expectedDigest || value.source_digest !== expectedDigest) {
          setError('Die Nachricht hat sich geändert. Bitte neu öffnen, bevor du den Verlauf verwendest.');
          return;
        }
        setResult(value);
      } catch {
        if (active && current === version) setError('Der gespeicherte Verlauf konnte nicht geprüft werden. Bitte erneut laden.');
      } finally {if (active && current === version) setLoading(false);}
    }
    void refresh();
    const onFocus = () => {void refresh();};
    window.addEventListener('focus', onFocus);
    return () => {active = false; version++; controller?.abort(); window.removeEventListener('focus', onFocus);};
  }, [uid, expectedDigest, revision]);
  return <section className="mail-thread" aria-label="Gespeicherter Mailverlauf">
    <div className="mail-task-form-heading"><h2>Zusammengehörige Nachrichten</h2><button className="mail-reader-secondary" type="button" disabled={loading} onClick={() => setRevision(value => value + 1)}>Aktualisieren</button></div>
    {loading && <p role="status">Gespeicherte Quellen werden zugeordnet …</p>}
    {error && <p className="mail-reader-error" role="alert">{error}</p>}
    {result && <>
      <p className="mail-reader-status">{result.detail}</p>
      {result.limited && <p className="mail-reader-status" role="status">Begrenzter Ausschnitt: Weitere Nachrichten oder Textteile können fehlen. Daraus lässt sich kein abschließender Stand ableiten.</p>}
      {result.items.length === 1 && <p>Keine weitere passende Nachricht im gespeicherten Ausschnitt gefunden. Im Postfach können weitere Nachrichten liegen.</p>}
      {result.items.length > 0 && <details><summary>Verlauf ansehen · {result.items.length} {result.items.length === 1 ? 'Nachricht' : 'Nachrichten'}</summary>
        <p className="mail-reader-status">Nach Originaldatum geordnet; undatierte Quellen stehen separat am Ende. Stand beim letzten Abruf. Änderungen und Absagen bitte im Wortlaut prüfen.</p>
        <ol className="mail-thread-list">{result.items.map((item, index) => <li key={item.episode_id ?? `current:${index}`}>
          <p><strong>{item.current ? 'Geöffnete Nachricht · ' : ''}{item.title}</strong></p>
          <p className="mail-reader-status">{item.sender || 'Absender nicht gespeichert'} · Quelldatum: {item.occurred_at ? new Date(item.occurred_at).toLocaleString('de-DE', {dateStyle: 'medium', timeStyle: 'short'}) : 'unbekannt'}</p>
          <details><summary>Originaltext lesen{item.truncated ? ' · Ausschnitt' : ''}</summary><pre>{item.text || 'Kein lesbarer Text vorhanden.'}</pre>{item.truncated && <p>Text gekürzt. Bedingungen können außerhalb dieses Ausschnitts stehen.</p>}</details>
          {item.episode_id && <ProfileSource kind="episode" id={item.episode_id} label="Gespeicherte Originalquelle prüfen" readOnly />}
        </li>)}</ol>
      </details>}
    </>}
  </section>;
}
