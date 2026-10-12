import {useEffect, useRef, useState} from 'react';
import {api, type ConversationPayload, type Message} from './api';
import {createVoiceSession, emptyVoice, nativeVoicePost, nativeVoiceAvailable, voiceRequestId, spokenAnswer, voiceAnswerKey, type VoiceSession, type VoiceState} from './nativeVoice';
import {icon} from './ui';
import './ConversationVoice.css';

export function useConversationVoice(id:string,data:ConversationPayload|null,disabled:boolean) {
  const [state,setState]=useState<VoiceState>({...emptyVoice});
  const session=useRef<VoiceSession|null>(null);
  const latest=useRef({data,disabled});latest.current={data,disabled};
  const reading=useRef<{id:string;key:string}|null>(null);
  useEffect(()=>{
    if(!nativeVoiceAvailable(window)){setState({...emptyVoice});return;}
    const voice=createVoiceSession({post:body=>nativeVoicePost(body,window),newId:()=>voiceRequestId(window),
      active:()=>document.visibilityState==='visible' && document.hasFocus() && !latest.current.disabled && latest.current.data?.conversation.id===id,
      changed:setState});
    session.current=voice;setState({...emptyVoice});reading.current=null;
    const event=(event:Event)=>voice.event((event as CustomEvent).detail);
    const suspend=()=>{reading.current=null;voice.cancel();};
    const probe=()=>{if(document.visibilityState==='visible' && document.hasFocus())voice.probe();else suspend();};
    window.addEventListener('kingfisher:voice',event);window.addEventListener('blur',suspend);
    window.addEventListener('focus',probe);document.addEventListener('visibilitychange',probe);
    voice.probe();
    return ()=>{window.removeEventListener('kingfisher:voice',event);window.removeEventListener('blur',suspend);
      window.removeEventListener('focus',probe);document.removeEventListener('visibilitychange',probe);
      voice.dispose();session.current=null;reading.current=null;};
  },[id]);
  useEffect(()=>{if(disabled){reading.current=null;session.current?.cancel();}else session.current?.probe();},[disabled,data?.conversation.id]);
  useEffect(()=>{
    const item=reading.current;
    if(item && voiceAnswerKey(data?.messages.find(m=>m.id===item.id))!==item.key){reading.current=null;session.current?.cancel();}
  },[data]);
  function cancel(){reading.current=null;session.current?.cancel();}
  function read(message:Message){
    reading.current={id:message.id,key:voiceAnswerKey(message)};
    void session.current?.read(message,async signal=>{
      const current=await api.getConversation(id,signal);
      return current.conversation.id===id ? current.messages.find(m=>m.id===message.id) : undefined;
    },()=>latest.current.data?.messages.find(m=>m.id===message.id));
  }
  return {state,cancel,read,startDraft:(base:string,commit:(text:string)=>void)=>{
    reading.current=null;session.current?.startDraft(base,commit);
  },finish:()=>session.current?.finish()};
}
export type ConversationVoice=ReturnType<typeof useConversationVoice>;
export const recordingVoice=(state:VoiceState)=>['authorizing','listening','finishing'].includes(state.phase);
export function VoiceDraftControls({voice,disabled,base,onDraft}:{voice:ConversationVoice;disabled:boolean;base:string;onDraft:(text:string)=>void}) {
  if(!voice.state.dictationAvailable)return null;
  const recording=recordingVoice(voice.state);
  return <button className="voice-button" type="button" disabled={disabled || recording}
    aria-label="Lokal diktieren" title="Lokal diktieren · Text vor dem Senden prüfen"
    onClick={()=>voice.startDraft(base,onDraft)}><img src={icon('microphone','Outline')} alt="" /></button>;
}
export function VoiceDraftStatus({voice}:{voice:ConversationVoice}) {
  const {state}=voice,recording=recordingVoice(state);
  if(!recording && !state.notice)return null;
  return <section className="conversation-voice-draft" aria-label="Diktierter Entwurf">
    <p role="status">{state.phase==='authorizing' ? 'Lokales Diktieren wird freigegeben …' : state.phase==='listening' ? 'Diktiere bis zu einer Minute. Noch nichts gesendet.' : state.phase==='finishing' ? 'Aufnahme beendet. Text wird fertiggestellt …' : state.notice}</p>
    {recording && <><p className="voice-partial">{state.partial || 'Dein bisheriger Entwurf bleibt erhalten.'}</p>
      <div><button type="button" disabled={state.phase!=='listening'} onClick={voice.finish}>Als Entwurf übernehmen</button>
        <button type="button" onClick={voice.cancel}>Abbrechen</button></div></>}
  </section>;
}
export function VoiceReply({voice,message,disabled}:{voice:ConversationVoice;message:Message;disabled:boolean}) {
  if(!voice.state.speechAvailable || !spokenAnswer(message))return null;
  const active=voice.state.messageId===message.id && ['checking','speaking'].includes(voice.state.phase);
  return <button className="voice-reply" type="button" disabled={disabled || recordingVoice(voice.state)}
    onClick={()=>active ? voice.cancel() : voice.read(message)}>
    {active ? voice.state.phase==='checking' ? 'Prüfung abbrechen' : 'Vorlesen stoppen' : 'Antwort lokal vorlesen'}
  </button>;
}
