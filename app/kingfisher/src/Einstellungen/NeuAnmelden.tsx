import { useState, type FormEvent } from "react";
import { api, ApiError, type IntegrationOverview, type MailAccount } from "../api";

/**
 * Zugänge: Neu anmelden, wenn ein Postfach Kingfisher nicht mehr hineinlässt (das Passwort hat sich geändert). Dorthin
 * führt der Satz auf Heute („Melde dich unter Einstellungen → Zugänge neu an.“). Nur das neue Passwort: Adresse und
 * Postfach kennt Kingfisher schon, es entsteht kein zweites Postfach und kein zweites Einlesen. Kingfisher meldet sich
 * vorher an; klappt das nicht, steht der Grund in einem Satz am Knopf, und nichts wird gespeichert.
 */
export function NeuAnmelden({ konto, beiErfolg }: { konto: MailAccount; beiErfolg: (neu: IntegrationOverview) => void }) {
  const [offen, setOffen] = useState(false);
  const [passwort, setPasswort] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");

  async function anmelden(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (arbeitet || !passwort) return;
    setArbeitet(true);
    setFehler("");
    try {
      const neu = await api.mailNeuAnmelden(konto.id, passwort);
      setPasswort("");
      setOffen(false);
      beiErfolg(neu);
    } catch (problem) {
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Das hat gerade nicht geklappt. Bitte versuche es noch einmal.");
    } finally {
      setArbeitet(false);
    }
  }

  if (!offen) return <button type="button" className="secondary-action" onClick={() => setOffen(true)}>Neu anmelden</button>;
  return <form className="neu-anmelden" aria-label={`${konto.label} neu anmelden`} onSubmit={event => void anmelden(event)}>
    <label>Neues Passwort für {konto.user}
      <input type="password" autoComplete="current-password" autoFocus value={passwort} onChange={event => setPasswort(event.target.value)} />
    </label>
    <div className="source-form-actions">
      <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => { setOffen(false); setFehler(""); setPasswort(""); }}>Abbrechen</button>
      <button type="submit" className="primary-action" disabled={arbeitet || !passwort}>{arbeitet ? "Wird angemeldet …" : "Anmelden"}</button>
    </div>
    {fehler ? <p role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </form>;
}
