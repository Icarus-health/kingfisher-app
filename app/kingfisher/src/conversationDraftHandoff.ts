import {api,type ConversationDraftHandoff,type ConversationDraftBound,type ConversationPayload} from './api';
type HandoffTransport={
  start:(id:string,body:{instance_id:string;handoff_id:string})=>Promise<ConversationDraftBound>;
  send:(id:string,text:string,instance:string)=>Promise<ConversationPayload>;
  finish:(id:string,body:{instance_id:string;handoff_id:string})=>Promise<ConversationDraftBound>;
};
export type HandoffOutcome={state:'accepted'|'uncertain'|'finish_failed';payload?:ConversationPayload};
const flights=new Map<string,Promise<HandoffOutcome>>();
const transport:HandoffTransport={start:(id,body)=>api.startConversationDraftHandoff(id,body),
  send:(id,text,instance)=>api.sendMessage(id,text,undefined,instance),finish:(id,body)=>api.finishConversationDraftHandoff(id,body)};
/** A durable claim permits one ordinary message POST. Lost responses are never
 * interpreted as permission to send again, including across React remounts. */
export function runConversationHandoff(id:string,handoff:ConversationDraftHandoff,instance:string,io=transport):Promise<HandoffOutcome>{
  const key=JSON.stringify([instance,id,handoff.id]);const existing=flights.get(key);if(existing)return existing;
  const work=(async():Promise<HandoffOutcome>=>{
    const body={instance_id:instance,handoff_id:handoff.id};
    let claimed:ConversationDraftBound;
    try{claimed=await io.start(id,body);}catch{return{state:'uncertain'};}
    if(claimed.claimed!==true||claimed.instance_id!==instance||claimed.conversation_id!==id||claimed.handoff?.id!==handoff.id)return{state:'uncertain'};
    let payload:ConversationPayload;
    try{payload=await io.send(id,claimed.handoff.text,instance);}catch{return{state:'uncertain'};}
    try{const finished=await io.finish(id,body);if(finished.handoff.state!=='accepted')throw Error('unconfirmed');return{state:'accepted',payload};}
    catch{return{state:'finish_failed',payload};}
  })();flights.set(key,work);
  const forget=()=>{if(flights.get(key)===work)flights.delete(key);};
  void work.then(forget,forget);return work;
}
