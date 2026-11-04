import {hasDraftRecording, setDraftLeaveLock} from './conversationDraftActivity';
import {api, type ConversationDraftPayload, type ConversationDraftBound} from './api';

export type DraftStatus = 'loading'|'saved'|'dirty'|'saving'|'error'|'conflict'|'instance_changed'|'clear_error';
export type DraftSnapshot = {
  text:string; revision:number; savedRevision:number; remoteRevision:number|null; instanceId:string|null;
  status:DraftStatus; cleanupPending:boolean; handoff?:ConversationDraftPayload['handoff']; binding?:ConversationDraftPayload['binding']; remoteText:string|null; legacyText:string|null; recoveryText:string|null;
};
type DraftEntry = DraftSnapshot & {timer:ReturnType<typeof setTimeout>|null; running:Promise<void>|null;
  loading:Promise<void>|null; loadGeneration:number; cleanupPending:boolean; legacyAdopted:boolean};
export type DraftTransport = {
  load:(id:string)=>Promise<ConversationDraftPayload>;
  bind?:(body:{instance_id:string;expected_revision:number})=>Promise<ConversationDraftBound>;
  save:(id:string,body:{text:string;expected_revision:number;instance_id:string})=>Promise<ConversationDraftPayload>;
};
const blocked = (status:DraftStatus)=>['conflict','instance_changed','error','clear_error'].includes(status);
function valid(value:ConversationDraftPayload) {
  if(typeof value?.text!=='string'||value.text.length>20000||!Number.isSafeInteger(value.revision)||value.revision<0
    ||typeof value.instance_id!=='string'||!value.instance_id||value.instance_id.length>128) throw Error('Ungültiger Entwurfsstand');
  return value;
}

/** Only unsent user text. The backend is authoritative; browser storage is never
 * silently imported into a newly connected instance. One write at a time per composer. */
export class ConversationDraftStore {
  private entries=new Map<string,DraftEntry>();
  private listeners=new Map<string,Set<()=>void>>();
  private instance:string|null=null;
  private epoch=0;
  private disposed=false;
  private leaving=false;
  private leaveOwner=Symbol();
  editingLocked(){return this.leaving;}
  cancelLeave(){this.leaving=false;setDraftLeaveLock(this.leaveOwner,false);for(const id of this.entries.keys())this.changed(id);}
  constructor(private transport:DraftTransport,private legacy:(id:string)=>string=()=>'',private clearLegacy:(id:string)=>void=()=>{}) {}
  private entry(id:string) {
    let value=this.entries.get(id);
    if(!value){let legacyText='';try{legacyText=this.legacy(id);}catch{/* unavailable legacy storage */}
      value={text:'',revision:0,savedRevision:0,remoteRevision:null,instanceId:null,status:'loading',remoteText:null,
        legacyText:legacyText||null,recoveryText:null,timer:null,running:null,loading:null,loadGeneration:0,cleanupPending:false,legacyAdopted:false};
      this.entries.set(id,value);
    }return value;
  }
  read(id:string):DraftSnapshot{return this.entry(id);}
  subscribe(id:string,listener:()=>void){const set=this.listeners.get(id)??new Set();set.add(listener);this.listeners.set(id,set);
    return()=>{set.delete(listener);if(!set.size)this.listeners.delete(id);};}
  private changed(id:string){this.listeners.get(id)?.forEach(listener=>listener());}
  private cancel(value:DraftEntry){if(value.timer!==null)clearTimeout(value.timer);value.timer=null;}
  private schedule(id:string){const value=this.entry(id);this.cancel(value);
    if(value.status!=='dirty'||this.disposed)return;
    value.timer=setTimeout(()=>{value.timer=null;void this.flush(id).catch(()=>undefined);},250);
  }
  private detach(id:string,value:DraftEntry){this.cancel(value);const unsaved=value.revision>value.savedRevision||blocked(value.status);if(unsaved&&value.text)value.recoveryText=value.text;
    value.text='';value.revision++;value.savedRevision=value.revision;value.remoteRevision=null;value.instanceId=null;
    value.remoteText=null;value.handoff=undefined;value.binding=undefined;value.status=value.recoveryText||value.legacyText?'instance_changed':'loading';value.cleanupPending=false;this.changed(id);
  }
  private acceptInstance(id:string,instance:string){
    if(this.instance&&this.instance!==instance){this.epoch++;for(const [other,value] of this.entries){if(other!==id)this.detach(other,value);}}
    this.instance=instance;
  }
  async load(id:string):Promise<void>{const value=this.entry(id);this.cancel(value);
    if(value.running)await value.running.catch(()=>undefined);
    const generation=++value.loadGeneration,epoch=this.epoch,startRevision=value.revision,oldInstance=value.instanceId,
      wasConflict=value.status==='conflict',oldRemote=value.remoteRevision,dirty=value.revision>value.savedRevision,oldText=value.text;
    value.status='loading';this.changed(id);
    const task=(async()=>{try{const remote=valid(await this.transport.load(id));
      if(generation!==value.loadGeneration||this.disposed||epoch!==this.epoch&&remote.instance_id!==this.instance)return;
      this.acceptInstance(id,remote.instance_id);
      if(oldInstance&&oldInstance!==remote.instance_id){if(oldText&&oldText!==remote.text)value.recoveryText=oldText;value.text=remote.text;
        value.revision++;value.savedRevision=value.revision;value.status=value.recoveryText?'instance_changed':'saved';value.cleanupPending=false;
      }else if(dirty||value.revision!==startRevision){
        if(value.text===remote.text){value.savedRevision=value.revision;value.status='saved';}
        else if(!wasConflict&&(oldRemote===remote.revision||oldRemote===null&&!remote.text)){value.status='dirty';}
        else{value.status='conflict';value.remoteText=remote.text;}
      }else{if(value.text!==remote.text)value.revision++;value.text=remote.text;value.savedRevision=value.revision;value.status=value.recoveryText?'instance_changed':'saved';}
      value.remoteRevision=remote.revision;value.instanceId=remote.instance_id;value.handoff=remote.handoff;value.binding=remote.binding;
      if(value.status!=='conflict')value.remoteText=null;
      this.changed(id);this.schedule(id);
    }catch{if(generation===value.loadGeneration){value.status=value.cleanupPending?'clear_error':'error';this.changed(id);}}
    })();value.loading=task;await task;if(value.loading===task)value.loading=null;
  }
  write(id:string,text:string){const value=this.entry(id);if(this.leaving)return value;value.text=text;value.revision++;value.cleanupPending=false;
    if(!blocked(value.status)&&value.status!=='loading')value.status='dirty';
    this.changed(id);this.schedule(id);return this.read(id);
  }
  private async save(id:string){const value=this.entry(id);if(value.running)return value.running;
    if(blocked(value.status)||value.instanceId===null||value.remoteRevision===null||value.text.length>20000){
      if(value.text.length>20000){value.status='error';this.changed(id);}throw Error('Entwurf nicht gesichert');}
    const localRevision=value.revision,text=value.text,remoteRevision=value.remoteRevision,instance=value.instanceId,epoch=this.epoch;
    value.status='saving';this.changed(id);
    const task=(async()=>{try{const remote=valid(await this.transport.save(id,{text,expected_revision:remoteRevision,instance_id:instance}));
      if(epoch!==this.epoch||value.instanceId!==instance||remote.instance_id!==instance)throw {status:409,grund:'draft_instance_changed'};
      if(remote.text!==text)throw Error('Entwurf nicht bestätigt');
      value.remoteRevision=remote.revision;value.savedRevision=localRevision;value.handoff=remote.handoff;value.binding=remote.binding;
      value.status=value.revision===localRevision?'saved':'dirty';value.remoteText=null;
      if(value.legacyAdopted){value.legacyAdopted=false;try{this.clearLegacy(id);}catch{/* keep harmless legacy copy */}}
      if(value.revision===localRevision)value.cleanupPending=false;
    }catch(error){const problem=error as {status?:number;grund?:string};
      if(problem.status===409){value.status=problem.grund==='draft_instance_changed'?'instance_changed':'conflict';
        try{const remote=valid(await this.transport.load(id));
          if(remote.instance_id!==instance){this.acceptInstance(id,remote.instance_id);if(value.text)value.recoveryText=value.text;
            value.text=remote.text;value.revision++;value.savedRevision=value.revision;value.status='instance_changed';value.cleanupPending=false;
          }else{value.remoteText=remote.text;}
          value.instanceId=remote.instance_id;value.remoteRevision=remote.revision;
        }catch{/* keep local text and unresolved state */}
      }else value.status=value.cleanupPending?'clear_error':'error';
      throw Error('Entwurf nicht gesichert');
    }finally{this.changed(id);}
    })();value.running=task;
    try{await task;}finally{if(value.running===task)value.running=null;this.schedule(id);}
  }
  async flush(id:string,revision=this.entry(id).revision):Promise<void>{const value=this.entry(id);this.cancel(value);
    if(value.loading)await value.loading;
    if(value.instanceId===null&&value.status==='loading')await this.load(id);
    if(blocked(value.status))throw Error('Entwurf nicht gesichert');
    while(value.savedRevision<revision){if(value.running)await value.running;else await this.save(id);}
  }
  async retry(id:string){const value=this.entry(id);
    if(value.status==='conflict'||value.status==='instance_changed'){await this.load(id);return;}
    if(value.instanceId===null){await this.load(id);return;}
    value.status='dirty';this.changed(id);await this.flush(id).catch(()=>undefined);
  }
  resolveConflict(id:string,useLocal:boolean){const value=this.entry(id);if(this.leaving)return;if(value.status!=='conflict'||value.remoteText===null)return;
    if(!useLocal){value.text=value.remoteText;value.revision++;value.savedRevision=value.revision;value.status='saved';}
    else{value.revision++;value.status='dirty';}
    value.remoteText=null;this.changed(id);this.schedule(id);
  }
  adoptRecovery(id:string){if(this.leaving)return;const value=this.entry(id),text=value.recoveryText??value.legacyText;if(text===null||value.instanceId===null)return;
    value.recoveryText=null;value.legacyText=null;value.legacyAdopted=true;value.status='dirty';this.write(id,text);
  }
  dismissRecovery(id:string){if(this.leaving)return;const value=this.entry(id);value.recoveryText=null;value.legacyText=null;
    // The old browser entry remains available; declining does not upload or erase it.
    if(value.status==='instance_changed')value.status='saved';this.changed(id);
  }
  async clearSubmitted(id:string,revision:number){const value=this.entry(id);if(value.revision!==revision)return false;
    value.text='';value.revision++;this.changed(id);const clearingRevision=value.revision;value.cleanupPending=true;value.status='dirty';
    try{await this.flush(id);}catch{if(value.cleanupPending&&this.read(id).status==='error'){value.status='clear_error';this.changed(id);}}
    return value.revision===clearingRevision;
  }
  async bindNew(){const value=this.entry('new');await this.flush('new');
    if(!this.transport.bind||!value.instanceId||value.remoteRevision===null||!value.text.trim()||blocked(value.status))throw Error('Entwurf nicht bereit');
    const instance=value.instanceId;
    let bound:ConversationDraftBound;
    try{bound=await this.transport.bind({instance_id:instance,expected_revision:value.remoteRevision});}
    catch(error){if((error as {status?:number}).status===409){value.revision++;value.status='conflict';await this.load('new');}throw error;}
    if(bound.instance_id!==instance||!bound.conversation_id||!bound.handoff?.id)throw Error('Gesprächsbindung nicht bestätigt');
    await this.load('new');
    if(value.instanceId!==instance)throw Error('Verbindung gewechselt');
    return bound;
  }
  unsafe(){return hasDraftRecording()||[...this.entries.values()].some(value=>value.legacyText!==null||value.recoveryText!==null||blocked(value.status)
    ||value.revision>value.savedRevision||value.running!==null);}
  async prepareToLeave(){if(hasDraftRecording())return false;this.leaving=true;setDraftLeaveLock(this.leaveOwner,true);for(const id of this.entries.keys())this.changed(id);await Promise.all([...this.entries].filter(([,value])=>value.status==='dirty'||value.status==='saving')
    .map(([id])=>this.flush(id).catch(()=>undefined)));return !this.unsafe();}
  dispose(){this.disposed=true;this.cancelLeave();for(const value of this.entries.values())this.cancel(value);this.listeners.clear();}
}
const prefix='kingfisher-chat-draft:';
const store=new ConversationDraftStore({load:id=>api.getConversationDraft(id),save:(id,body)=>api.saveConversationDraft(id,body),bind:body=>api.bindNewConversationDraft(body)},
  id=>sessionStorage.getItem(prefix+id)??'',id=>sessionStorage.removeItem(prefix+id));
const sending=new Set<string>(),sendListeners=new Map<string,Set<()=>void>>();
export const conversationDraft=(id:string)=>store.read(id);
export const bindNewConversationDraft=()=>store.bindNew();
export const conversationDraftEditingLocked=()=>store.editingLocked();
export const loadConversationDraft=(id:string)=>store.load(id);
export const writeConversationDraft=(id:string,text:string)=>store.write(id,text);
export const flushConversationDraft=(id:string,revision?:number)=>store.flush(id,revision);
export const clearSubmittedDraft=(id:string,revision:number)=>store.clearSubmitted(id,revision);
export const retryConversationDraft=(id:string)=>store.retry(id);
export const resolveConversationDraft=(id:string,local:boolean)=>store.resolveConflict(id,local);
export const adoptConversationDraft=(id:string)=>store.adoptRecovery(id);
export const dismissConversationDraft=(id:string)=>store.dismissRecovery(id);
export const conversationSending=(id:string)=>sending.has(id);
export function beginConversationSend(id:string){if(sending.has(id))return false;sending.add(id);sendListeners.get(id)?.forEach(fn=>fn());return true;}
export function endConversationSend(id:string){sending.delete(id);sendListeners.get(id)?.forEach(fn=>fn());}
export function subscribeConversationDraft(id:string,listener:()=>void){const entries=sendListeners.get(id)??new Set();entries.add(listener);sendListeners.set(id,entries);
  const stop=store.subscribe(id,listener);return()=>{stop();entries.delete(listener);if(!entries.size)sendListeners.delete(id);};}
declare global {interface Window{kingfisherDraftsPrepareToLeave?:()=>Promise<boolean>;kingfisherDraftsCancelLeave?:()=>void;}}
export function installConversationDraftLeaveGuard(){window.kingfisherDraftsPrepareToLeave=async()=>await store.prepareToLeave()&&!sending.size;window.kingfisherDraftsCancelLeave=()=>store.cancelLeave();
  const guard=(event:BeforeUnloadEvent)=>{if(store.unsafe()){event.preventDefault();event.returnValue='';}};
  window.addEventListener('beforeunload',guard);return()=>{window.removeEventListener('beforeunload',guard);delete window.kingfisherDraftsPrepareToLeave;delete window.kingfisherDraftsCancelLeave;};}
