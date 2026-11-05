import {useEffect,useId,useRef,useState,type FormEvent} from 'react';
import {api,type MistralSourceBudget as Budget} from './api';
import {budgetNotice,formatBudgetUsd,parseBudgetUsd} from './cloud-budget';

/** A zero allowance stays zero until this explicit form is submitted. */
export function MistralSourceBudget({refreshKey,disabled=false,onChange}:{refreshKey?:number;disabled?:boolean;onChange:(budget:Budget|null)=>void}) {
  const [budget,setBudget]=useState<Budget|null>(null);
  const [editing,setEditing]=useState(false);
  const [draft,setDraft]=useState('');
  const [error,setError]=useState('');
  const [loadError,setLoadError]=useState(false);
  const [saving,setSaving]=useState(false);
  const requestVersion=useRef(0);
  const mounted=useRef(false);
  const busy=useRef(false);
  const focusAfterSave=useRef(false);
  const input=useRef<HTMLInputElement>(null);
  const notify=useRef(onChange);notify.current=onChange;
  const id=useId();

  async function load() {
    const version=++requestVersion.current;
    try {
      const next=await api.mistralSourceBudget();
      if(mounted.current&&version===requestVersion.current&&!busy.current){setBudget(next);setLoadError(false);notify.current(next);}
    }catch {
      if(mounted.current&&version===requestVersion.current&&!busy.current){setLoadError(true);notify.current(null);}
    }
  }
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;requestVersion.current++;};},[]);
  useEffect(()=>{void load();},[refreshKey]);
  useEffect(()=>{
    if(!saving&&focusAfterSave.current){focusAfterSave.current=false;input.current?.focus();}
  },[saving,error]);

  function validation(value:string) {
    const cap=parseBudgetUsd(value);
    if(cap===null)return 'Bitte einen Betrag von 0 bis 1.000 USD eingeben, zum Beispiel 1,00.';
    if(budget&&cap<budget.spent_microusd+budget.held_microusd)return `Mindestens ${formatBudgetUsd(budget.spent_microusd+budget.held_microusd,true)} sind bereits verbraucht oder reserviert.`;
    return '';
  }
  async function save(event:FormEvent) {
    event.preventDefault();
    if(busy.current||disabled||!budget)return;
    const problem=validation(draft),cap=parseBudgetUsd(draft);
    if(problem||cap===null){setError(problem);input.current?.focus();return;}
    busy.current=true;requestVersion.current++;setSaving(true);setError('');notify.current(null);
    try {
      const next=await api.setMistralSourceBudget(cap,budget.revision);
      if(mounted.current){setBudget(next);setLoadError(false);setDraft('');setEditing(false);notify.current(next);}
    }catch {
      if(mounted.current){focusAfterSave.current=true;setError('Das Limit konnte nicht gespeichert werden. Der Kostenstand wird neu geladen; deine Eingabe bleibt erhalten.');}
    }finally {
      busy.current=false;
      if(mounted.current){setSaving(false);void load();}
    }
  }
  const cap=parseBudgetUsd(draft);
  const notice=budget&&budget.cap_microusd!==0&&budget.blocked_reason!=='budget_busy'?budgetNotice(budget):'';
  return <div className="mistral-source-budget" aria-label="Mistral-Kostenlimit für Quellen und Abläufe">
    {loadError?<p role="status">Der Mistral-Kostenstand ist gerade nicht erreichbar. <button type="button" className="g-knopf-schlicht" disabled={saving} onClick={()=>void load()}>Erneut laden</button></p>
      :budget?<p><strong>{budget.cap_microusd===0?'Noch kein Kostenlimit freigegeben':`${formatBudgetUsd(budget.remaining_microusd)} verfügbar`}</strong> · Quellen und Abläufe</p>
      :<p role="status">Mistral-Kostenstand wird geladen …</p>}
    {notice?<p className="source-hint" role="status">{notice}</p>:null}
    <details className="quiet-details" open={editing} onToggle={event=>setEditing(event.currentTarget.open)}>
      <summary>Limit und Kosten</summary>
      {budget?<p className="source-hint">Gesamtlimit {formatBudgetUsd(budget.cap_microusd)} · verbraucht {formatBudgetUsd(budget.spent_microusd,true)} · reserviert {formatBudgetUsd(budget.held_microusd,true)}</p>:null}
      <p>Das Gesamtlimit gilt gemeinsam für Quellen und Abläufe über alle Mistral-Pakete. Bereits verbrauchte oder reservierte Beträge bleiben erhalten. Modellkosten in USD zum angezeigten Preisstand, ohne Steuern; kein Guthaben beim Anbieter.</p>
      <form onSubmit={event=>void save(event)}>
        <label htmlFor={id}>Neues Gesamtlimit (USD)</label>
        <div className="source-form-actions">
          <input ref={input} id={id} inputMode="decimal" value={draft} placeholder="Zum Beispiel 1,00" disabled={disabled||saving||!budget||loadError}
            aria-invalid={Boolean(error)} aria-describedby={error?`${id}-error`:undefined}
            onChange={event=>{setDraft(event.target.value);if(error)setError('');}} onBlur={()=>{if(draft.trim())setError(validation(draft));}}/>
          <button type="submit" className="secondary-action" disabled={disabled||saving||!budget||loadError||cap===null}>
            {saving?'Wird gespeichert …':cap===null?'Limit freigeben':`${formatBudgetUsd(cap,true)} freigeben`}
          </button>
        </div>
        {error?<p id={`${id}-error`} role="alert">{error}</p>:null}
      </form>
      {budget?<small>Preisstand gültig bis {new Date(`${budget.price_valid_until}T00:00:00Z`).toLocaleDateString('de-DE',{timeZone:'UTC'})}. Ein geändertes Limit braucht eine neue Paketvorschau.</small>:null}
    </details>
  </div>;
}
