import {useState} from "react";
import {namensEntwurf} from "./schritte";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";

/** (a) „Wie heißt du?“ Ein Feld, freiwillig; der Name steht nur im Gruß des Briefings. */
export function NameSchritt({stand, weiter, ueberspringen, zurueck, entwurf}: SchrittProps) {
  const [name, setName] = useState(stand.name);
  const [arbeitet, setArbeitet] = useState(false);
  async function speichern() {
    if (arbeitet) return;
    setArbeitet(true);
    try { await weiter({name: name.trim()}); } finally { setArbeitet(false); }
  }
  return <form className="erststart-inhalt" onSubmit={event => { event.preventDefault(); void speichern(); }}>
    <p>Kingfisher grüßt dich morgens mit deinem Namen.</p>
    <label htmlFor="erststart-name">Wie soll Kingfisher dich nennen?</label>
    <input id="erststart-name" value={name} maxLength={80} autoComplete="given-name" autoFocus placeholder="Dein Vorname"
      onChange={event => { setName(event.target.value); entwurf(namensEntwurf(event.target.value, stand.name)); }} />
    <p className="source-hint">Der Name bleibt auf diesem Rechner und steht nur im Gruß, zum Beispiel „Guten Morgen, Lea.“ Du kannst das Feld leer lassen.</p>
    <SchrittFuss erledigt={name.trim() !== ""} zurueck={zurueck} absenden arbeitet={arbeitet}
      weiter={() => void speichern()} ueberspringen={() => void ueberspringen()} />
  </form>;
}
