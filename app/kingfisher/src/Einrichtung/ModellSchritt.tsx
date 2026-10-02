import {useState} from "react";
import {RechnerKarte} from "./RechnerKarte";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";
import {nachbar} from "./schritte";

/**
 * (d) „Kingfisher auf diesem Rechner einrichten“: was Kingfisher hier kann, Größe und Dauer des Ladens, ein Knopf
 * (Befund 10). Das Laden hält die Einrichtung nicht auf (Fremdprobe 2, Befund 6): Läuft es, heißt der Knopf „Weiter“
 * und führt zum nächsten Schritt, ohne den Schritt als erledigt zu vermerken; erledigt ist er erst, wenn das Modell
 * wirklich bereit ist. Den Fortschritt zeigt Heute.
 */
export function ModellSchritt({stand, neuLesen, weiter, ueberspringen, zurueck, gehe}: SchrittProps) {
  const [laedt, setLaedt] = useState(false);
  const bereit = stand.vorhanden.modell;
  return <div className="erststart-inhalt">
    <p>Kingfisher denkt auf deinem Rechner nach. Deine Mails und Termine verlassen ihn dafür nicht. Einmal lädt es dazu einige Programme herunter; das läuft im Hintergrund, und du machst derweil mit der Einrichtung weiter.</p>
    {bereit ? <p className="erststart-ok" role="status">Kingfisher kann auf diesem Rechner schon Fragen beantworten.</p> : null}
    <RechnerKarte beiFertig={() => void neuLesen()} beiLaden={setLaedt} />
    <SchrittFuss erledigt={bereit || laedt} zurueck={zurueck}
      weiter={() => bereit ? void weiter() : gehe(nachbar("modell", 1, stand))} ueberspringen={() => void ueberspringen()} />
  </div>;
}
