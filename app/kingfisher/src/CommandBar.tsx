import {useEffect, useRef, useState, type FormEvent} from "react";
import {VoiceDraftControls, recordingVoice, type ConversationVoice} from "./ConversationVoice";
import {InterfaceIcon} from "./InterfaceIcon";
import {tastenHinweis} from "./system";
import {useEingabegeraet} from "./useSystem";
import "./CommandBar.css";

export function CommandBar({ onSubmit, busy = false, conversation = false, disabled = false, placeholder, voice }: {
  onSubmit: (message: string) => Promise<void>;
  busy?: boolean;
  conversation?: boolean;
  disabled?: boolean;
  placeholder?: string;
  voice?: ConversationVoice;
}) {
  const [message, setMessage] = useState("");
  const recording = voice ? recordingVoice(voice.state) : false;
  const input = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
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
    if (!clean || busy || disabled || recording) return;
    voice?.cancel();
    try {
      await onSubmit(clean);
      setMessage("");
    } catch {
      // Der aufrufende Screen zeigt den Fehler in der bestehenden Fläche.
    }
  }

  return (
    <><form className={`command-bar ${conversation ? "conversation-command" : ""}`} onSubmit={submit}>
      {!conversation ? <InterfaceIcon name="search" /> : null}
      {conversation ? <textarea
        aria-label="Kingfisher fragen"
        aria-describedby="conversation-composer-hint"
        rows={2}
        disabled={busy || disabled || recording}
        onChange={event=>setMessage(event.target.value)}
        onKeyDown={event=>{if(event.key==='Enter' && (event.ctrlKey || event.metaKey)) {event.preventDefault();event.currentTarget.form?.requestSubmit();}}}
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
      <button aria-label="Nachricht senden" className="send-button" disabled={!message.trim() || busy || disabled || recording} type="submit">
        <InterfaceIcon name="arrow-up" />
      </button>
    </form>{conversation && <p className="composer-hint" id="conversation-composer-hint">Enter fügt eine Zeile hinzu.{!device.nurTouch && ` ${device.mac ? '⌘' : 'Strg'} + Enter sendet.`} Diktat bleibt ein Entwurf bis zum Senden.</p>}</>
  );
}
