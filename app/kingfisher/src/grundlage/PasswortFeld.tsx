import { useState, type Ref } from "react";

/**
 * Ein Passwortfeld mit „Anzeigen“ (Persona-Prüfung, Paket S, Befund 8): Wer ein App-Passwort abtippt, will sehen, was
 * er getippt hat. Vorgabe verborgen; der Knopf schaltet um und sagt, was er tut. Das Passwort selbst bleibt, wo es war.
 */
export function PasswortFeld({ id, wert, onWert, autoComplete = "new-password", feldRef, invalid, describedBy }: {
  id?: string;
  wert: string;
  onWert: (wert: string) => void;
  autoComplete?: string;
  feldRef?: Ref<HTMLInputElement>;
  invalid?: boolean;
  describedBy?: string;
}) {
  const [zeigen, setZeigen] = useState(false);
  return <span className="g-passwort">
    <input id={id} ref={feldRef} type={zeigen ? "text" : "password"} value={wert} autoComplete={autoComplete}
      autoCapitalize="off" autoCorrect="off" spellCheck={false} aria-invalid={invalid ? true : undefined}
      aria-describedby={describedBy} onChange={event => onWert(event.target.value)} />
    <button type="button" className="g-passwort-zeigen" aria-pressed={zeigen} aria-label={zeigen ? "Passwort verbergen" : "Passwort anzeigen"}
      onClick={() => setZeigen(z => !z)}>{zeigen ? "Verbergen" : "Anzeigen"}</button>
  </span>;
}
