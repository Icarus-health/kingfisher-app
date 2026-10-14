import {useEffect, useRef, useState, type FormEvent} from "react";
import {VoiceDraftControls, recordingVoice, type ConversationVoice} from "./ConversationVoice";
import {InterfaceIcon} from "./InterfaceIcon";
import {tastenHinweis} from "./system";
import {useEingabegeraet} from "./useSystem";
import "./CommandBar.css";
import {conversationDraft, writeConversationDraft, clearSubmittedDraft, subscribeConversationDraft, conversationSending, beginConversationSend, endConversationSend} from "./conversationDrafts";

export function CommandBar({ onSubmit, busy = false, conversation = false, disabled = false, placeholder, voice, conversationId }: {
  onSubmit: (message: string) => Promise<void>;
  busy?: boolean;
  conversation?: boolean;
  disabled?: boolean;
  placeholder?: string;
  voice?: ConversationVoice;
  conversationId?: string;
}) {
  const [message, updateMessage] = useState(() => conversationId ? conversationDraft(conversationId).text : "");
  const revision = useRef(0);
  const inFlight = useRef(false);
  const [,draftVersion] = useState(0);
  const sharedSending = conversationId ? conversationSending(conversationId) : false;
  function setMessage(text: string) {
    revision.current++;
    if (conversationId) writeConversationDraft(conversationId, text);
    updateMessage(text);
  }
  const recording = voice ? recordingVoice(voice.state) : false;
  const input = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  useEffect(()=>{
    if(!conversationId) return;
    const refresh=()=>{updateMessage(conversationDraft(conversationId).text);draftVersion(n=>n+1);};
    refresh();
    return subscribeConversationDraft(conversationId,refresh);
  },[conversationId]);
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
    if (!clean || busy || disabled || recording || inFlight.current) return;
    if(conversationId && !beginConversationSend(conversationId)) return;
    inFlight.current = true;
    voice?.cancel();
    const submittedRevision = conversationId ? conversationDraft(conversationId).revision : revision.current;
    try {
      await onSubmit(clean);
      const clear = conversationId ? clearSubmittedDraft(conversationId, submittedRevision) : revision.current === submittedRevision;
      if (clear) {
        updateMessage("");
      }
    } catch {
      // Der aufrufende Screen zeigt den Fehler in der bestehenden Fläche.
    } finally { inFlight.current = false; if(conversationId) endConversationSend(conversationId); }
  }

  return (
    <><form className={`command-bar ${conversation ? "conversation-command" : ""}`} onSubmit={submit}>
      {!conversation ? <InterfaceIcon name="search" /> : null}
      {conversation ? <textarea
        aria-label="Kingfisher fragen"
        aria-describedby="conversation-composer-hint"
        rows={2}
        disabled={disabled || recording}
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
        placeholder={placeholder ?? (conversation ? "Nachricht oder Befehl …" : "Frag Kingfisher etwas …    z. B. „Bereite mich auf meinen Termin um 11:30 vor“")}
        ref={element=>{input.current=element;}}
        value={message}
      />}
      {!conversation && taste ? <kbd>{taste}</kbd> : null}
      {voice ? <VoiceDraftControls voice={voice} disabled={busy || disabled} base={message} onDraft={setMessage} /> : null}
      <button aria-label="Nachricht senden" className="send-button" disabled={!message.trim() || busy || sharedSending || disabled || recording} type="submit">
        <InterfaceIcon name="arrow-up" />
      </button>
    </form>{conversation && <p className="composer-hint" id="conversation-composer-hint">Enter sendet. Shift + Enter fügt eine Zeile hinzu. Diktat bleibt ein Entwurf bis zum Senden.</p>}</>
  );
}
