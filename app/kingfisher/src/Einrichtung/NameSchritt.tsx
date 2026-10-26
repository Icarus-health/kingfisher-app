import {useState} from "react";
import {fuerSystem} from "../system";
import {useSystem} from "../useSystem";
import {VORSCHLAG_HERKUNFT, namensEntwurf, namensStart, namensVorschlag} from "./schritte";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";

/**
 * (a) Der Name für den Gruß des Briefings. Kennt Kingfisher ihn schon (eigene Mails, Benutzerkonto, Einrichtung), steht
 * er im Feld, und die Überschrift sagt „Hallo Lea.“: ein Klick auf „Weiter“ bestätigt, ändern geht im Feld. Erst dieser
 * Klick speichert ihn. Ohne Quelle die Frage „Wie heißt du?“ mit leerem Feld, freiwillig wie bisher.
 */
export function NameSchritt({stand, weiter, ueberspringen, zurueck, entwurf}: SchrittProps) {
  const system = useSystem();
  const vorschlag = namensVorschlag(stand);
  const [name, setName] = useState(() => namensStart(stand));
  const [arbeitet, setArbeitet] = useState(false);
  async function speichern() {
    if (arbeitet) return;
    setArbeitet(true);
    try { await weiter({name: name.trim()}); } finally { setArbeitet(false); }
  }
  return <form className="erststart-inhalt" onSubmit={event => { event.preventDefault(); void speichern(); }}>
    <p>{vorschlag ? "Stimmt der Name?" : "Kingfisher grüßt dich morgens mit deinem Namen."}</p>
    <label htmlFor="erststart-name" className="visually-hidden">Wie soll Kingfisher dich nennen?</label>
    {/* Mit Vorschlag liegt der Fokus auf „Weiter“ (ein Klick, keine Tastatur auf dem Handy); ohne im Feld. */}
    <input id="erststart-name" value={name} maxLength={80} autoComplete="given-name" autoFocus={!vorschlag} placeholder="Dein Vorname"
      onChange={event => { setName(event.target.value); entwurf(namensEntwurf(event.target.value, stand.name)); }} />
    <p className="source-hint">{vorschlag
      ? `${fuerSystem(VORSCHLAG_HERKUNFT[vorschlag.quelle], system)} Der Name bleibt auf diesem Rechner.`
      : "Der Name bleibt auf diesem Rechner. Du kannst das Feld leer lassen."}</p>
    <SchrittFuss erledigt={name.trim() !== ""} zurueck={zurueck} absenden arbeitet={arbeitet} fokus={Boolean(vorschlag)}
      weiter={() => void speichern()} ueberspringen={() => void ueberspringen()} />
  </form>;
}
