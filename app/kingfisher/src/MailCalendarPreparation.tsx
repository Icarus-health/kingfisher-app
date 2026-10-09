import {useEffect, useRef, useState} from 'react';
import {api, type CalendarActionDraft, type CalendarActionSource, type MailCalendarPreparationRecord, type MailThreadContext} from './api';
import {CalendarActionForm} from './CalendarActionForm';
import {buildIsoOffset, offsetOptions, splitIsoOffset} from './mailCalendarInput';

type TimeValue = {local:string; offset:string; original:string};
type PreviewInput = {stand:string;source_id:string;send_updates:'all'|'externalOnly'|'none'};
const emptyTime = ():TimeValue => ({local:'',offset:'',original:''});
function timeValue(value:string):TimeValue {
  if (!value) return emptyTime();
  try {return {...splitIsoOffset(value),original:value};}
  catch {return {local:'',offset:'',original:value};}
}
function timeField(value:TimeValue):string {
  if (!value.local) return '';
  return buildIsoOffset(value.local,value.offset,value.original || null);
}
function complete(fields:{title:string;start:string;end:string}):boolean {
  return Boolean(fields.title.trim()&&fields.start&&fields.end);
}

export function MailCalendarPreparation({uid,expectedBinding,onDone}: {uid:string;expectedBinding?:string;onDone?:()=>void}) {
  const [record,setRecord]=useState<MailCalendarPreparationRecord|null>(null);
  const [hasForm,setHasForm]=useState(false);
  const [title,setTitle]=useState('');
  const [start,setStart]=useState<TimeValue>(emptyTime);
  const [end,setEnd]=useState<TimeValue>(emptyTime);
  const [reviewed,setReviewed]=useState(false);
  const [dirty,setDirty]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [sources,setSources]=useState<CalendarActionSource[]>([]);
  const [sourceId,setSourceId]=useState('');
  const [sendUpdates,setSendUpdates]=useState<PreviewInput['send_updates']>('none');
  const [draft,setDraft]=useState<CalendarActionDraft|null>(null);
  const [calendarChoiceOpen,setCalendarChoiceOpen]=useState(false);
  const lock=useRef(false), lifecycle=useRef(0), recordRef=useRef<MailCalendarPreparationRecord|null>(null), freshnessCheck=useRef(0), identityRef=useRef('');
  identityRef.current=JSON.stringify([uid,expectedBinding??null]);
  recordRef.current=record;
  useEffect(()=>{
    const current=++lifecycle.current;
    setRecord(null);setHasForm(false);setTitle('');setStart(emptyTime());setEnd(emptyTime());setReviewed(false);setDirty(false);
    setError('');setSources([]);setSourceId('');setDraft(null);setCalendarChoiceOpen(false);
    return ()=>{if(lifecycle.current===current)lifecycle.current++;};
  },[uid]);

  useEffect(()=>{
    let active=true;
    setBusy(false);
    const verify=()=>{
      const saved=recordRef.current;
      if(!saved||saved.uid!==uid||!expectedBinding||saved.binding!==expectedBinding||lock.current)return;
      const sequence=++freshnessCheck.current;
      lock.current=true;setBusy(true);setError('');setRecord(null);setDraft(null);setSources([]);setCalendarChoiceOpen(false);const version=lifecycle.current;
      void api.mailCalendarRead(saved.id).then(value=>{
        if(!active||version!==lifecycle.current||sequence!==freshnessCheck.current)return;
        if(value.uid!==uid||value.binding!==expectedBinding)throw new Error('Die Mail oder ihr Verlauf hat sich geändert. Bitte neu öffnen.');
        setRecord(value);
        if(value.stand!==saved.stand){setDirty(true);setReviewed(false);setDraft(null);setSources([]);setCalendarChoiceOpen(false);}
      }).catch(e=>{
        if(active&&version===lifecycle.current&&sequence===freshnessCheck.current){setRecord(null);setDraft(null);setSources([]);setSourceId('');setCalendarChoiceOpen(false);
          setError(e instanceof Error?e.message:'Mail oder Verlauf konnten nicht erneut geprüft werden.');}
      }).finally(()=>{
        if(active&&version===lifecycle.current&&sequence===freshnessCheck.current){lock.current=false;setBusy(false);}
      });
    };
    window.addEventListener('focus',verify);
    return ()=>{active=false;window.removeEventListener('focus',verify);freshnessCheck.current++;lock.current=false;};
  },[uid,expectedBinding]);

  const currentRecord=record?.uid===uid&&Boolean(expectedBinding)&&record.binding===expectedBinding?record:null;
  const originalVisible=Boolean(currentRecord);
  async function run(action:(version:number,identity:string)=>Promise<void>) {
    if(lock.current)return;
    lock.current=true;setBusy(true);setError('');const version=lifecycle.current, identity=identityRef.current;
    try {await action(version,identity);}
    catch(e){if(version===lifecycle.current&&identity===identityRef.current){setRecord(null);setDraft(null);setSources([]);setSourceId('');setCalendarChoiceOpen(false);
      setError(e instanceof Error?e.message:'Die Vorbereitung konnte nicht abgeschlossen werden.');}}
    finally {lock.current=false;if(version===lifecycle.current&&identity===identityRef.current)setBusy(false);}
  }
  function changed(){setDirty(true);setReviewed(false);setDraft(null);}
  function applyRecord(value:MailCalendarPreparationRecord){
    setRecord(value);setHasForm(true);setTitle(value.fields.title);setStart(timeValue(value.fields.start));setEnd(timeValue(value.fields.end));
    setReviewed(value.reviewed);setDirty(false);setDraft(null);setSources([]);setSourceId('');setCalendarChoiceOpen(false);
  }
  function freshnessError(){
    if(!expectedBinding)return 'Die geöffnete Mail hat keine aktuelle Quellenbindung. Bitte neu öffnen.';
    if(record&&record.binding!==expectedBinding)return 'Mail oder Verlauf haben sich geändert. Bitte neu öffnen und erneut prüfen.';
    return '';
  }
  async function prepare(){
    if(!expectedBinding){setError('Die geöffnete Mail hat keine aktuelle Quellenbindung. Bitte neu öffnen.');setRecord(null);return;}
    await run(async (version,identity)=>{
      setRecord(null);setSources([]);setSourceId('');setDraft(null);setCalendarChoiceOpen(false);
      const value=await api.mailCalendarPrepare(uid,expectedBinding);
      if(version!==lifecycle.current||identity!==identityRef.current)return;
      if(value.uid!==uid||value.binding!==expectedBinding)throw new Error('Die Mail oder ihr Verlauf hat sich geändert. Bitte neu öffnen.');
      if(hasForm&&(dirty||reviewed!==(record?.reviewed??false))){
        setRecord(value);setDirty(true);setReviewed(false);setDraft(null);setSources([]);setSourceId('');setCalendarChoiceOpen(false);
      }else applyRecord(value);
    });
  }
  async function verifyCurrent(){
    const saved=currentRecord;
    const stale=freshnessError();if(stale){setError(stale);setRecord(null);setDraft(null);return;}
    if(!saved)return;
    await run(async (version,identity)=>{
      setRecord(null);setDraft(null);setSources([]);setSourceId('');setCalendarChoiceOpen(false);
      const value=await api.mailCalendarRead(saved.id);
      if(version!==lifecycle.current||identity!==identityRef.current)return;
      if(value.uid!==uid||value.binding!==expectedBinding)throw new Error('Die Mail oder ihr Verlauf hat sich geändert. Bitte neu öffnen.');
      setRecord(value);
      if(value.stand!==saved.stand){setDirty(true);setReviewed(false);setDraft(null);setSources([]);setCalendarChoiceOpen(false);}
    });
  }
  async function save(){
    const stale=freshnessError();if(stale){setError(stale);return;}
    if(!currentRecord){setError('Bitte zuerst die Mail öffnen und den gespeicherten Verlauf prüfen.');return;}
    let fields:{title:string;start:string;end:string};
    try {fields={title:title.trim(),start:timeField(start),end:timeField(end)};}
    catch(e){setError(e instanceof Error?e.message:'Bitte die Zeitzone ausdrücklich wählen.');return;}
    await run(async (version,identity)=>{
      const value=await api.mailCalendarSave(currentRecord.id,{stand:currentRecord.stand,fields,reviewed});
      if(version!==lifecycle.current||identity!==identityRef.current)return;
      if(value.uid!==uid||value.binding!==expectedBinding)throw new Error('Die Quellenbindung hat sich geändert. Bitte neu öffnen.');
      applyRecord(value);
    });
  }
  async function loadCalendars(){
    const stale=freshnessError();if(stale){setError(stale);return;}
    if(!currentRecord||dirty||!currentRecord.reviewed||!complete(currentRecord.fields)){
      setError('Speichere zuerst einen vollständigen, geprüften Termin.');return;
    }
    await run(async (version,identity)=>{
      const result=await api.calendarActionSources();
      if(version!==lifecycle.current||identity!==identityRef.current)return;
      setSources(result.sources);setSourceId(old=>result.sources.some(item=>item.id===old)?old:result.sources.find(item=>item.can_write)?.id||'');
      setCalendarChoiceOpen(true);
    });
  }
  async function preview(){
    const stale=freshnessError();if(stale){setError(stale);return;}
    if(!currentRecord||dirty||!currentRecord.reviewed||!complete(currentRecord.fields)){
      setError('Speichere zuerst einen vollständigen, ausdrücklich geprüften Termin.');return;
    }
    if(!sources.some(item=>item.id===sourceId&&item.can_write)){
      setError('Wähle einen verbundenen Kalender mit Schreibrecht.');return;
    }
    await run(async (version,identity)=>{
      setDraft(null);
      const value=await api.mailCalendarPreview(currentRecord.id,{stand:currentRecord.stand,source_id:sourceId,send_updates:sendUpdates});
      if(version!==lifecycle.current||identity!==identityRef.current)return;
      setDraft(value);
    });
  }
  const source=sources.find(item=>item.id===sourceId);
  const staleness=record&&!currentRecord?freshnessError():'';
  const updateTime=(which:'start'|'end',next:Partial<TimeValue>)=>{
    const setter=which==='start'?setStart:setEnd, previous=which==='start'?start:end;
    setter({...previous,...next});changed();
  };
  const originLabel=(which:'title'|'start'|'end')=>{
    if(!currentRecord)return '';
    const origin=currentRecord.origins[which];
    let changedHere=false;
    if(which==='title')changedHere=title!==currentRecord.fields.title;
    else {
      const value=which==='start'?start:end, saved=timeValue(currentRecord.fields[which]);
      changedHere=value.local!==saved.local||value.offset!==saved.offset;
    }
    return changedHere?'Deine Eingabe (noch nicht gespeichert)':origin.kind==='source'?'Originalmail':origin.kind==='user'?'Deine Eingabe':'Fehlt';
  };
  const renderTime=(which:'start'|'end',value:TimeValue)=>{
    const origin=originalVisible?currentRecord?.origins[which]:undefined;
    const options=offsetOptions(value.offset||null);
    return <div className="mail-calendar-time">
      <label>{which==='start'?'Beginn':'Ende'} <input id={`mail-calendar-${which}`} type="datetime-local" step="60" value={value.local}
        onChange={event=>updateTime(which,{local:event.target.value})}/></label>
      <label>Zeitzone für {which==='start'?'Beginn':'Ende'} <select id={`mail-calendar-${which}-offset`} value={value.offset}
        onChange={event=>updateTime(which,{offset:event.target.value})}>
        <option value="">Zeitzone ausdrücklich wählen</option>{options.map(item=><option key={item.value} value={item.value}>{item.label}</option>)}
      </select></label>
      {origin&&<p className="mail-reader-status">Herkunft: {originLabel(which)}{origin.quote?` · Originalbeleg: „${origin.quote}“`:''}</p>}
    </div>;
  };
  return <section className="source-section mail-calendar-preparation" aria-label="Terminentwurf aus Mail vorbereiten">
    <h2>Termin aus Mail vorbereiten</h2>
    <p>Der Entwurf bleibt lokal und ändert keinen Kalender. Zeiten und Zeitzonen bitte im Original prüfen. Ein begrenzter Mailverlauf kann spätere Absagen außerhalb des gespeicherten Bestands nicht ausschließen.</p>
    {error&&<p role="alert">{error}</p>}
    {staleness&&<p role="alert">{staleness}</p>}
    {!record&&<button type="button" className="secondary-action" disabled={busy} onClick={()=>void prepare()}>{busy?'Mail wird geprüft …':hasForm?'Quelle erneut prüfen':'Termin vorbereiten'}</button>}
    {record&&!currentRecord&&<button type="button" className="secondary-action" disabled={busy} onClick={()=>void prepare()}>Quelle erneut prüfen</button>}
    {currentRecord&&<button type="button" className="text-action" disabled={busy} onClick={()=>void verifyCurrent()}>Quelle erneut prüfen</button>}
    {hasForm&&<>
      {originalVisible&&currentRecord&&<>
        <p className="mail-reader-status">{currentRecord.context.detail}</p>
        {currentRecord.context.limited&&<p role="status">Der gespeicherte Verlauf ist begrenzt. Weitere Nachrichten oder spätere Absagen können fehlen.</p>}
        {currentRecord.context.warnings.map((warning,index)=><p role="status" key={`${index}:${warning}`}>{warning}</p>)}
        <details><summary>Originalmail und gespeicherten Verlauf ansehen · {currentRecord.context.items.length} Nachrichten</summary>
          <ol>{currentRecord.context.items.map((item,index)=><li key={item.episode_id??`current:${index}`}>
            <p><strong>{item.current?'Geöffnete Mail · ':''}{item.title}</strong></p>
            <p>{item.sender||'Absender nicht gespeichert'} · {item.occurred_at||'Quelldatum unbekannt'}</p>
            <pre>{item.text||'Kein lesbarer Originaltext verfügbar.'}</pre>
            {item.truncated&&<p role="status">Dieser Nachrichtentext ist gekürzt.</p>}
          </li>)}</ol>
        </details>
      </>}
      <form onSubmit={event=>{event.preventDefault();void save();}}>
        <fieldset disabled={busy}>
          <label>Titel <input id="mail-calendar-title" value={title} maxLength={500} onChange={event=>{setTitle(event.target.value);changed();}} /></label>
          {originalVisible&&currentRecord&&<p className="mail-reader-status">Herkunft: {originLabel('title')}{currentRecord.origins.title.quote?` · Originalbeleg: „${currentRecord.origins.title.quote}“`:''}</p>}
          {renderTime('start',start)}{renderTime('end',end)}
          <label><input id="mail-calendar-reviewed" type="checkbox" checked={reviewed} onChange={event=>{setReviewed(event.target.checked);setDraft(null);}} />
            Ich habe Original, bekannten Verlauf, Titel, Beginn, Ende und Zeitzonen geprüft.</label>
          <button type="submit" className="secondary-action">{busy?'Wird gespeichert …':'Speichern'}</button>
        </fieldset>
      </form>
      {dirty&&<p role="status">Änderungen sind noch nicht gespeichert. Nach jeder Feldänderung ist die ausdrückliche Prüfung erneut nötig.</p>}
      {currentRecord&&currentRecord.reviewed&&!dirty&&!complete(currentRecord.fields)&&<p role="status">Die Vorbereitung ist gespeichert, aber für eine Vorschau fehlen Titel, Beginn oder Ende.</p>}
      {currentRecord&&currentRecord.reviewed&&!dirty&&complete(currentRecord.fields)&&!calendarChoiceOpen&&<button type="button" className="secondary-action" disabled={busy} onClick={()=>void loadCalendars()}>
        {busy?'Kalender werden geladen …':'Kalender für Vorschau laden'}
      </button>}
      {calendarChoiceOpen&&currentRecord&&<fieldset disabled={busy||!currentRecord.reviewed||dirty}>
        <label>Kalender <select value={sourceId} onChange={event=>{setSourceId(event.target.value);setDraft(null);}}>
          <option value="">Kalender wählen</option>{sources.map(item=><option key={item.id} value={item.id}>{item.label} · {item.user}{item.can_write?'':' · nur lesen'}</option>)}
        </select></label>
        {source&&!source.can_write&&<p>{source.reason||'Dieser Kalender ist nur zum Lesen verbunden.'} <a href="/settings#zugaenge">Zugänge öffnen</a></p>}
        {!sources.some(item=>item.can_write)&&<p>Kein Kalender mit Schreibrecht verbunden. <a href="/settings#zugaenge">Kalenderzugang prüfen</a></p>}
        <label>Google-Benachrichtigungen <select value={sendUpdates} onChange={event=>{setSendUpdates(event.target.value as PreviewInput['send_updates']);setDraft(null);}}>
          <option value="none">Keine Benachrichtigungen angefordert</option><option value="all">Alle Gäste benachrichtigen</option><option value="externalOnly">Nur externe Gäste benachrichtigen</option>
        </select></label>
        <button type="button" className="secondary-action" disabled={!source?.can_write||busy} onClick={()=>void preview()}>{busy?'Vorschau wird geprüft …':'Kalendervorschau erstellen'}</button>
      </fieldset>}
    </>}
    {draft&&currentRecord&&<CalendarActionForm key={`${draft.id}:${draft.stand}`} preparedDraft={draft} onClose={()=>setDraft(null)} onDone={onDone??(()=>{})}/>}
  </section>;
}
