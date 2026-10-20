import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { api, ApiError, type IntegrationOverview, type MailAccount } from "../api";

/**
 * Zugänge: Neu anmelden, wenn ein Postfach Kingfisher nicht mehr hineinlässt (das Passwort hat sich geändert). Dorthin
 * führt der Satz auf Heute („Melde dich unter Einstellungen → Zugänge neu an.“). Nur das neue Passwort: Adresse und
 * Postfach kennt Kingfisher schon, es entsteht kein zweites Postfach und kein zweites Einlesen. Kingfisher meldet sich
 * vorher an; klappt das nicht, steht der Grund in einem Satz am Knopf, der Fokus bleibt im Feld, und nichts wird
 * gespeichert. Escape bricht ab und bringt den Fokus zurück auf „Neu anmelden“.
 */
export function NeuAnmelden({ konto, beiErfolg }: { konto: MailAccount; beiErfolg: (neu: IntegrationOverview & { satz?: string }) => void }) {
  const [offen, setOffen] = useState(false);
  const [passwort, setPasswort] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const feld = useRef<HTMLInputElement>(null);
  const knopf = useRef<HTMLButtonElement>(null);
  const zurueck = useRef(false);

  useEffect(() => {
    if (offen) feld.current?.focus();
    else if (zurueck.current) { zurueck.current = false; knopf.current?.focus(); }
  }, [offen]);

  function abbrechen() {
    zurueck.current = true;
    setOffen(false); setFehler(""); setPasswort("");
  }

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
      // Nach der Ablehnung gleich neu tippen können: Fokus ins Feld, der Text ist markiert.
      requestAnimationFrame(() => { feld.current?.focus(); feld.current?.select(); });
    } finally {
      setArbeitet(false);
    }
  }

  function taste(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key === "Escape" && !arbeitet) { event.preventDefault(); abbrechen(); }
  }

  if (!offen) return <button ref={knopf} type="button" className="secondary-action" onClick={() => setOffen(true)}>Neu anmelden</button>;
  return <form className="neu-anmelden" aria-label={`${konto.label} neu anmelden`} onSubmit={event => void anmelden(event)} onKeyDown={taste}>
    <label>Neues Passwort für {konto.user}
      <input ref={feld} type="password" autoComplete="current-password" value={passwort} aria-invalid={fehler ? true : undefined}
        aria-describedby={fehler ? `neu-anmelden-fehler-${konto.id}` : undefined} onChange={event => setPasswort(event.target.value)} />
    </label>
    <div className="source-form-actions">
      <button type="button" className="secondary-action" disabled={arbeitet} onClick={abbrechen}>Abbrechen</button>
      <button type="submit" className="primary-action" disabled={arbeitet || !passwort}>{arbeitet ? "Wird angemeldet …" : "Anmelden"}</button>
    </div>
    {fehler ? <p id={`neu-anmelden-fehler-${konto.id}`} role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </form>;
}
