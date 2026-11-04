import {useEffect, useRef, useState, type FormEvent} from "react";
import {VoiceDraftControls, recordingVoice, type ConversationVoice} from "./ConversationVoice";
import {InterfaceIcon} from "./InterfaceIcon";
import {tastenHinweis} from "./system";
import {useEingabegeraet} from "./useSystem";
import "./CommandBar.css";
import {conversationDraft, writeConversationDraft, clearSubmittedDraft, subscribeConversationDraft, conversationSending, beginConversationSend, endConversationSend, loadConversationDraft, flushConversationDraft, retryConversationDraft, resolveConversationDraft, adoptConversationDraft, dismissConversationDraft, conversationDraftEditingLocked} from "./conversationDrafts";

export function CommandBar({ onSubmit, busy = false, conversation = false, disabled = false, placeholder, voice, conversationId, draftId, lockWhileBusy = false }: {
  onSubmit: (message: string, draft?:{instanceId:string}) => Promise<void>;
  busy?: boolean;
  conversation?: boolean;
  disabled?: boolean;
  placeholder?: string;
  voice?: ConversationVoice;
  conversationId?: string;
  draftId?: string;
  lockWhileBusy?: boolean;
}) {
  const draftKey = draftId ?? conversationId;
  const [message, updateMessage] = useState(() => draftKey ? conversationDraft(draftKey).text : "");
  const revision = useRef(0);
  const inFlight = useRef(false);
  const [,draftVersion] = useState(0);
  const sharedSending = draftKey ? conversationSending(draftKey) : false;
  function setMessage(text: string) {
    if (conversationDraftEditingLocked() || lockWhileBusy && (inFlight.current || busy)) return;
    revision.current++;
    if (draftKey) writeConversationDraft(draftKey, text);
    updateMessage(text);
  }
  const leaveLocked = conversationDraftEditingLocked();
  const recording = voice ? recordingVoice(voice.state) : false;
  const input = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  useEffect(()=>{
    if(!draftKey) return;
    const refresh=()=>{updateMessage(conversationDraft(draftKey).text);draftVersion(n=>n+1);};
    const stop=subscribeConversationDraft(draftKey,refresh);
    void loadConversationDraft(draftKey);refresh();
    return stop;
  },[draftKey]);
  const draft = draftKey ? conversationDraft(draftKey) : null;
  const draftBlocked = draft ? ['loading','error','clear_error','conflict','instance_changed'].includes(draft.status) : false;
  useEffect(() => { if ((busy || disabled) && recording) voice?.cancel(); }, [busy, disabled, recording, voice]);
  // Der Hinweis passt zum Gerät: „⌘ K“ auf dem Mac, „Strg K“ sonst, keiner auf dem Telefon (Fremdprobe 2, Befund 11).
  const device = useEingabegeraet();
  const taste = tastenHinweis(device);

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const clean = message.trim();
    if (!clean || busy || disabled || recording || inFlight.current || draftBlocked || leaveLocked) return;
    if(draftKey && !beginConversationSend(draftKey)) return;
    inFlight.current = true;
    voice?.cancel();
    const submittedRevision = draftKey ? conversationDraft(draftKey).revision : revision.current;
    try {
      if (draftKey) await flushConversationDraft(draftKey, submittedRevision);
      await onSubmit(clean, draftKey && conversationDraft(draftKey).instanceId ? {instanceId:conversationDraft(draftKey).instanceId!} : undefined);
      const clear = draftKey ? await clearSubmittedDraft(draftKey, submittedRevision) : revision.current === submittedRevision;
      if (clear) {
        updateMessage("");
      }
    } catch {
      // Der aufrufende Screen zeigt den Fehler in der bestehenden Fläche.
    } finally { inFlight.current = false; if(draftKey) endConversationSend(draftKey); }
  }

  return (
    <><form className={`command-bar ${conversation ? "conversation-command" : ""}`} onSubmit={submit}>
      {!conversation ? <InterfaceIcon name="search" /> : null}
      {conversation ? <textarea
        aria-label="Kingfisher fragen"
        aria-describedby="conversation-composer-hint"
        rows={2}
        maxLength={20000}
        disabled={disabled || recording || leaveLocked || lockWhileBusy && (busy || sharedSending)}
        onChange={event=>setMessage(event.target.value)}
        onKeyDown={event=>{
          if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent?.isComposing || event.nativeEvent?.keyCode === 229) return;
          event.preventDefault();
          if (!busy && !disabled && !recording) event.currentTarget.form?.requestSubmit();
        }}
        placeholder={placeholder ?? 'Nachricht, Notizen oder Befehl …'}
        ref={element=>{input.current=element;}}
        value={message}
      /> : <input
        aria-label="Kingfisher fragen"
        disabled={busy || disabled || recording}
        onChange={(event) => setMessage(event.target.value)}
        placeholder={placeholder ?? (conversation ? "Nachricht oder Befehl …" : "Frag Kingfisher …")}
        ref={element=>{input.current=element;}}
        value={message}
      />}
      {!conversation && taste ? <kbd>{taste}</kbd> : null}
      {voice ? <VoiceDraftControls voice={voice} disabled={busy || disabled || leaveLocked} base={message} onDraft={setMessage} /> : null}
      <button aria-label="Nachricht senden" className="send-button" disabled={!message.trim() || busy || sharedSending || disabled || recording || draftBlocked || leaveLocked} type="submit">
        <InterfaceIcon name="arrow-up" />
      </button>
    </form>{draft && draftKey && <div className="composer-draft-status" role={['error','clear_error','conflict','instance_changed'].includes(draft.status) ? 'alert' : 'status'}>
      <span>{draft.status==='loading' ? 'Entwurf wird geladen …' : draft.status==='saving'||draft.status==='dirty' ? 'Entwurf wird gesichert …' :
        draft.status==='error' ? 'Entwurf noch nicht gesichert. Bitte das Fenster offen lassen.' :
        draft.status==='clear_error' ? 'Nachricht gesendet. Der alte Entwurf konnte noch nicht entfernt werden.' :
        draft.status==='conflict' ? draft.cleanupPending ? 'Nachricht gesendet. Ein anderer Entwurf muss noch geprüft werden.' : 'Dieses Gespräch wurde auch in einem anderen Fenster bearbeitet.' :
        draft.status==='instance_changed' ? 'Die Verbindung hat gewechselt. Frühere Eingaben wurden nicht übernommen.' :
        draft.text||draft.revision>0 ? 'Entwurf gesichert' : ''}</span>
      {['error','clear_error'].includes(draft.status) && <button type="button" className="g-knopf-schlicht g-kompakt" onClick={()=>void retryConversationDraft(draftKey)}>Erneut sichern</button>}
      {draft.status==='conflict' && <details><summary>Fassungen vergleichen</summary><p>Deine Eingabe</p><pre>{draft.text}</pre><p>Gespeicherte Fassung</p><pre>{draft.remoteText}</pre>
        <button type="button" onClick={()=>resolveConversationDraft(draftKey,true)}>Meine Fassung behalten</button>
        <button type="button" onClick={()=>resolveConversationDraft(draftKey,false)}>Gespeicherte Fassung übernehmen</button></details>}
      {(draft.legacyText!==null||draft.recoveryText!==null) && <details><summary>Früheren Entwurf prüfen</summary>
        <p>Dieser Text ist noch keinem aktuellen Datenbestand zugeordnet.</p><pre>{draft.recoveryText??draft.legacyText}</pre>
        <button type="button" disabled={!draft.instanceId} onClick={()=>adoptConversationDraft(draftKey)}>In dieses Gespräch übernehmen</button>
        <button type="button" onClick={()=>dismissConversationDraft(draftKey)}>Nicht übernehmen</button></details>}
      {draftKey==='new' && draft.binding && <a href={`/conversations/${encodeURIComponent(draft.binding.conversation_id)}`}>{draft.binding.handoff.state==='started' ? 'Sendestatus prüfen' : 'Vorbereitete Nachricht öffnen'}</a>}
    </div>}{conversation && <p className="composer-hint" id="conversation-composer-hint">Enter sendet, Shift + Enter beginnt eine neue Zeile.{voice?.state.dictationAvailable ? " Diktat bleibt ein Entwurf bis zum Senden." : ""}</p>}</>
  );
}
