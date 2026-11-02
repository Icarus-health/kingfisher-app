import type {CloudAccessState,CloudMemoryProvider,SourceBudgetBinding,MistralSourceBudget} from './api';

/** Decimal digits → integer micro-USD. No floating-point billing arithmetic. */
export function parseBudgetUsd(value:string):number|null {
  const clean=value.trim();
  if(!/^(?:0|[1-9]\d{0,3})(?:[.,]\d{1,6})?$/.test(clean))return null;
  const [whole,fraction='']=clean.replace(',','.').split('.');
  const amount=Number(whole)*1_000_000+Number(fraction.padEnd(6,'0'));
  return Number.isSafeInteger(amount)&&amount<=1_000_000_000?amount:null;
}

export function formatBudgetUsd(amount:number|undefined,precise=false):string {
  if(!Number.isSafeInteger(amount)||amount===undefined||amount<0)return '—';
  return new Intl.NumberFormat('de-DE',{style:'currency',currency:'USD',currencyDisplay:'code',
    minimumFractionDigits:2,maximumFractionDigits:precise?6:2}).format(amount/1_000_000);
}

export function sourceProviderLabel(provider:CloudMemoryProvider|undefined):string {
  return provider==='mistral'?'Mistral · EU':provider==='anthropic'?'Claude API':'ChatGPT';
}

export function sourceImportModel(provider:CloudMemoryProvider,access:Pick<CloudAccessState,'providers'>|null,chatModel:string):string {
  if(provider==='chatgpt')return chatModel;
  const entry=access?.providers.find(item=>item.id===provider);
  return provider==='mistral'?entry?.import_model??'':entry?.model??'';
}

export function mistralBindingCurrent(job:SourceBudgetBinding&{provider?:CloudMemoryProvider},budget:Pick<MistralSourceBudget,'budget_id'|'revision'|'price_id'>|null):boolean {
  return job.provider!=='mistral'||Boolean(budget&&job.budget_id===budget.budget_id
    &&job.budget_revision===budget.revision&&job.price_id===budget.price_id);
}

export function budgetNotice(budget:Partial<MistralSourceBudget>):string {
  if(budget.reconciliation_required||budget.blocked_reason==='budget_uncertain')return 'Abrechnung noch offen · weitere Aufrufe pausiert.';
  if(budget.blocked_reason==='budget_busy')return 'Ein Aufruf ist bereits reserviert.';
  if(budget.blocked_reason==='pricing_changed')return 'Der Preisstand muss erneut geprüft werden.';
  if(budget.cap_microusd===0)return 'Mistral-Einordnung noch nicht freigegeben.';
  if(budget.blocked_reason==='budget_exhausted')return 'Das freigegebene Limit ist erreicht.';
  if(budget.blocked_reason)return 'Kostenstand prüfen, bevor Mistral weiterarbeitet.';
  return '';
}
