import {useRef, useState} from 'react';
import {api, type HealthObservation} from './api';
import {deviceOffsets, healthFormFromObservation, healthPayload, HealthSaveRequest, type HealthForm, type HealthPayload} from './healthObservationForm';

const empty = (): HealthForm => ({own:false,metric:'',value:'',unit:'',localTime:'',offset:'',note:''});

export function HealthObservationEditor({observation=null,onSaved,onCancel}: {observation?: HealthObservation | null; onSaved: (value: HealthObservation) => void; onCancel: () => void}) {
  const [form,setForm]=useState<HealthForm>(()=>observation ? healthFormFromObservation(observation) : empty());
  const [preview,setPreview]=useState<HealthPayload | null>(null);
  const [error,setError]=useState('');
  const [saving,setSaving]=useState(false);
  const busy=useRef(false);
  const request=useRef(new HealthSaveRequest());
  const deviceZone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  function edit<K extends keyof HealthForm>(key: K, value: HealthForm[K]) {
    if(busy.current) return;
    setForm(old=> {
      const next={...old,[key]:value};
      if(key==='localTime') {const offsets=deviceOffsets(String(value));next.offset=offsets.length===1 ? offsets[0] : '';}
      return next;
    });
    setPreview(null);setError('');
  }
  function review(event: React.FormEvent) {
    event.preventDefault();if(busy.current) return;
    try {setPreview(healthPayload(form));setError('');}
    catch(failure) {setError(failure instanceof Error ? failure.message : 'Bitte die Eingabe prüfen.');}
  }
  async function save() {
    if(busy.current || !preview) return;
    busy.current=true;setSaving(true);setError('');
    try {
      if(observation && !observation.support_fingerprint) throw Object.assign(new Error(), {status:409});
      const correction=observation ? {id:observation.id,expected_support_fingerprint:observation.support_fingerprint!} : undefined;
      const payload=request.current.for(preview,correction);
      const result=observation ? await api.correctHealthObservation(observation.id,{...payload,expected_support_fingerprint:observation.support_fingerprint!}) : await api.saveHealthObservation(payload);
      request.current.done();setPreview(null);setForm(empty());onSaved(result);
    } catch(failure) {
      const status=(failure as {status?: number})?.status;
      setError(status===409 ? `${(failure as {detail?: string}).detail || 'Die Angabe ist inzwischen geändert oder nicht verfügbar.'} Deine Eingabe bleibt hier; lade den Verlauf neu, bevor du erneut korrigierst.`
        : 'Speichern konnte nicht bestätigt werden. Deine Eingabe bleibt hier. Erneut speichern prüft denselben Vorgang und legt keinen doppelten Eintrag an.');
    } finally {busy.current=false;setSaving(false);}
  }
  return <section className="health-editor" aria-label={observation ? 'Angabe korrigieren' : 'Eigene Angabe festhalten'}>
    <h2>{observation ? 'Angabe korrigieren' : 'Eigene Angabe festhalten'}</h2>
    {observation && <p>Die neue Fassung ersetzt diesen Eintrag. Das Original bleibt im Verlauf erhalten.</p>}
    <form onSubmit={review}>
      <fieldset disabled={saving}>
        <div className="health-fields">
          <label htmlFor="health-metric">Messgröße<input id="health-metric" value={form.metric} onChange={e=>edit('metric',e.target.value)} maxLength={100} placeholder="z. B. Gewicht" required /></label>
          <label htmlFor="health-value">Wert<input id="health-value" value={form.value} onChange={e=>edit('value',e.target.value)} inputMode="decimal" maxLength={32} placeholder="z. B. 72,5" required /></label>
          <label htmlFor="health-unit">Einheit<input id="health-unit" value={form.unit} onChange={e=>edit('unit',e.target.value)} maxLength={40} placeholder="z. B. kg" required /></label>
          <label htmlFor="health-time">Gemessen am<input id="health-time" type={/\.\d{4,6}$/.test(form.localTime) ? 'text' : 'datetime-local'} value={form.localTime} onChange={e=>edit('localTime',e.target.value)} step="any" required /></label>
          <label htmlFor="health-offset">UTC-Zeitversatz<input id="health-offset" value={form.offset} onChange={e=>edit('offset',e.target.value)} placeholder="z. B. +02:00" maxLength={6} required /></label>
        </div>
        <p className="health-help">Gerätezeitzone: {deviceZone}. Der Zeitversatz wird für eindeutige Gerätezeiten vorgeschlagen. Bei einer doppelten Stunde zur Zeitumstellung bitte bewusst wählen. Ein anderer Zeitversatz ist möglich und steht in der Vorschau.</p>
        <label htmlFor="health-note">Notiz (optional)<textarea id="health-note" value={form.note} onChange={e=>edit('note',e.target.value)} maxLength={4000} rows={2} /></label>
        <label className="health-own" htmlFor="health-own"><input id="health-own" type="checkbox" checked={form.own} onChange={e=>edit('own',e.target.checked)} />Meine eigene Angabe, keine Angabe zu einer anderen Person</label>
        <div className="health-actions"><button className="primary" type="submit">Angabe prüfen</button><button type="button" onClick={onCancel}>Abbrechen</button></div>
      </fieldset>
    </form>
    {preview && <div className="health-preview" role="status">
      <p><strong>{preview.metric}: {preview.value} {preview.unit}</strong></p>
      <p>Eigene Angabe · {preview.observed_at.replace('T',' · ')}</p>
      {preview.note && <p>{preview.note}</p>}
      <button className="primary" type="button" disabled={saving} onClick={save}>{saving ? 'Speichern …' : 'Quelle speichern'}</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
