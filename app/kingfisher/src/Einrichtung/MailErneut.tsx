import {useState} from "react";
import {api, type MailIntakeStatus} from "../api";

/**
 * „Erneut versuchen“ unter dem Satz, warum Mails nicht ins Gedächtnis kamen (Fremdprobe 3, Befund 2). Die technische
 * Angabe steht nur aufgeklappt unter „Für Techniker“. Gelingt der Klick, meldet `beiErgebnis` den neuen Stand; der Satz
 * darüber wechselt dann von selbst auf „wird gelesen“.
 */
export function MailErneut({konto, technik, beiErgebnis}: {
  konto: string;
  technik?: string | null;
  beiErgebnis: (stand: MailIntakeStatus) => void;
}) {
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");

  async function versuchen() {
    setArbeitet(true); setFehler("");
    try {
      beiErgebnis(await api.retryMailIntake(konto));
    } catch {
      setFehler("Das hat gerade nicht geklappt. Bitte versuche es in einem Moment noch einmal.");
    } finally {
      setArbeitet(false);
    }
  }

  return <div className="mail-erneut">
    <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => void versuchen()}>
      {arbeitet ? "Wird versucht …" : "Erneut versuchen"}</button>
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
    {technik ? <details className="mail-erneut-technik"><summary>Für Techniker</summary><p>{technik}</p></details> : null}
  </div>;
}
