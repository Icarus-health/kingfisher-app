import type {Message} from './api.ts';
import {belegStand, OHNE_BELEG} from './beleg.ts';
import {gueltigeQuellen} from './quellenWeg.ts';
import {nebensatz, verworfenPruefmodell} from './pruefHinweis.ts';

/** Read the displayed answer, not its hidden raw model text or collapsed quotes. */
export function spokenAnswer(message: Message): string {
  if (message.role !== 'assistant' || message.status !== 'complete') return '';
  const context=message.metadata?.context, data=context?.satzantwort;
  const lines: string[]=data ? [
    ...data.saetze.map(s=>`${s.text}${nebensatz(s) ? ` (${nebensatz(s)})` : ''}`),
    ...(data.hinweise ?? []),
    verworfenPruefmodell(data.verworfen_pruefmodell) ? `${verworfenPruefmodell(data.verworfen_pruefmodell)}.` : '',
    data.verworfen ? `${data.verworfen===1 ? 'Ein Satz' : `${data.verworfen} Sätze`} verworfen, weil die Belege ${data.verworfen===1 ? 'ihn' : 'sie'} nicht getragen haben.` : '',
  ] : [message.content];
  if (belegStand(message).art==='ohne') lines.push(OHNE_BELEG);
  if (context?.quellen) lines.push(...gueltigeQuellen(context.quellen).map(q=>`Quelle ${q.nummer}: ${q.text}`));
  const text=lines.filter(Boolean).join('\n').trim();
  return text.length<=8000 ? text : ''; // Never truncate an uncertainty/coverage warning.
}
// Include source identity and notices in the comparison even when answer wording is unchanged.
export function voiceAnswerKey(message: Message | undefined): string {
  if (!message) return '';
  function stable(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(stable);
    if (value && typeof value==='object') return Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,stable(item)]));
    return value;
  }
  return JSON.stringify(stable(message));
}
export type VoiceState={phase:'idle'|'authorizing'|'listening'|'finishing'|'checking'|'speaking';partial:string;notice:string;dictationAvailable:boolean;speechAvailable:boolean;messageId:string|null};
export const emptyVoice: VoiceState={phase:'idle',partial:'',notice:'',dictationAvailable:false,speechAvailable:false,messageId:null};
type Request={aktion:string;id:string;text?:string};
type Options={post:(body:Request)=>boolean;newId:()=>string;active:()=>boolean;changed:(state:VoiceState)=>void};
export function createVoiceSession(options:Options) {
  let state={...emptyVoice}, alive=true, query='', id='', mode:'draft'|'read'|null=null, generation=0;
  let base='', accept:((text:string)=>void)|null=null;
  let fetchAbort:AbortController|null=null;
  const change=(patch:Partial<VoiceState>)=>{state={...state,...patch};if(alive)options.changed({...state});};
  const post=(aktion:string,text?:string)=>options.post({aktion,id,...(text!==undefined ? {text} : {})});
  function cancel(){
    generation++;fetchAbort?.abort();fetchAbort=null;
    const previousMode=mode; mode=null;accept=null;
    if(id && previousMode) post(previousMode==='draft' ? 'spracheAbbrechen' : 'spracheStopp');
    id='';change({phase:'idle',partial:'',messageId:null,notice:''});
  }
  function fail(notice:string){cancel();change({notice});}
  return {
    probe(){if(!alive || !options.active())return;query=options.newId();options.post({aktion:'spracheStatus',id:query});},
    startDraft(value:string,commit:(text:string)=>void){
      if(!alive || !options.active() || !state.dictationAvailable)return;
      cancel();id=options.newId();mode='draft';base=value;accept=commit;change({phase:'authorizing'});
      if(!post('spracheStart'))fail('Diktieren ist in diesem Fenster nicht verfügbar.');
    },
    finish(){if(alive && mode==='draft' && state.phase==='listening'){change({phase:'finishing'});if(!post('spracheEnde'))fail('Die Aufnahme konnte nicht beendet werden. Bitte abbrechen.');}},
    cancel,
    event(value:unknown){
      if(!alive || !options.active() || !value || typeof value!=='object')return;
      const event=value as Record<string,unknown>;
      if(typeof event.id!=='string' || typeof event.state!=='string' || typeof event.text!=='string' || event.text.length>4000 || typeof event.dictationAvailable!=='boolean' || typeof event.speechAvailable!=='boolean')return;
      if(event.id===query && event.state==='ready'){change({dictationAvailable:event.dictationAvailable,speechAvailable:event.speechAvailable});return;}
      if(event.id!==id || !mode)return;
      if(['canceled','failed','unavailable'].includes(event.state)){
        change({dictationAvailable:event.dictationAvailable,speechAvailable:event.speechAvailable});
        const notice=event.state==='canceled' ? '' : 'Sprache gerade nicht verfügbar. Dein bisheriger Entwurf bleibt erhalten. Du kannst weiter tippen.';
        cancel();change({notice});return;
      }
      if(mode==='draft'){
        if(['authorizing','listening','finishing'].includes(event.state)){change({phase:event.state as VoiceState['phase'],partial:event.text});return;}
        if(event.state==='completed'){
          const commit=accept,addition=event.text.trim(),original=base;
          mode=null;accept=null;id='';change({phase:'idle',partial:'',notice:addition ? 'Entwurf ergänzt. Bitte prüfen und selbst senden.' : 'Kein Text erkannt. Dein Entwurf bleibt erhalten.'});
          if(addition)commit?.(`${original}${original && !/\s$/.test(original) ? ' ' : ''}${addition}`);
        }
      }else if(event.state==='speaking')change({phase:'speaking'});
      else if(event.state==='completed'){mode=null;id='';change({phase:'idle',messageId:null});}
    },
    async read(message:Message,refresh:(signal:AbortSignal)=>Promise<Message|undefined>,current:()=>Message|undefined){
      if(!alive || !options.active() || !state.speechAvailable || !spokenAnswer(message))return;
      cancel();const token=generation, key=voiceAnswerKey(message);id=options.newId();mode='read';
      const controller=new AbortController();fetchAbort=controller;change({phase:'checking',messageId:message.id});
      try{
        const fresh=await refresh(controller.signal);
        if(!alive || token!==generation || !options.active())return;
        if(voiceAnswerKey(fresh)!==key || voiceAnswerKey(current())!==key){fail('Antwort oder Quellen haben sich geändert. Bitte das Gespräch neu laden.');return;}
        const text=spokenAnswer(fresh!);
        if(!text){fail('Diese Antwort kann nicht vollständig vorgelesen werden. Bitte die Textansicht verwenden.');return;}
        change({phase:'speaking'});if(!post('spracheVorlesen',text))fail('Lokales Vorlesen ist in diesem Fenster nicht verfügbar.');
      }catch{if(alive && token===generation)fail('Antwort und Quellen ließen sich nicht frisch prüfen. Bitte erneut versuchen.');}
      finally{if(fetchAbort===controller)fetchAbort=null;}
    },
    dispose(){cancel();alive=false;query='';},
  };
}
export type VoiceSession=ReturnType<typeof createVoiceSession>;
export function nativeVoicePost(body:Request,environment:unknown=globalThis):boolean {
  try{
    const bridge=(environment as {webkit?:{messageHandlers?:{kingfisher?:{postMessage:(message:unknown)=>void}}}})?.webkit?.messageHandlers?.kingfisher;
    if(typeof bridge?.postMessage!=='function')return false;
    bridge.postMessage(body);return true;
  }catch{return false;}
}

/** No browser microphones, no capability request if the real native bridge is absent. */
export function nativeVoiceAvailable(environment:unknown):boolean {
  const value=environment as {webkit?:{messageHandlers?:{kingfisher?:{postMessage?:unknown}}};crypto?:{randomUUID?:unknown;getRandomValues?:unknown}};
  return typeof value?.webkit?.messageHandlers?.kingfisher?.postMessage==='function'
    && (typeof value.crypto?.randomUUID==='function' || typeof value.crypto?.getRandomValues==='function');
}
export function voiceRequestId(environment:unknown=globalThis):string {
  const crypto=(environment as {crypto:Crypto}).crypto;
  if(typeof crypto.randomUUID==='function')return crypto.randomUUID();
  const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
