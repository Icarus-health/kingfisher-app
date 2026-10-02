import {navigate} from "../ui";
import {KingfisherLernt} from "./KingfisherLernt";
import {offeneSchritte} from "./schritte";
import {useEinrichtung} from "./useEinrichtung";
import "./Einrichtung.css";

/** Oben in Einstellungen: der Assistent jederzeit wieder, was noch offen ist, und was im Hintergrund läuft. Den Autostart gibt es unter „Was Kingfisher darf“. */
export function EinrichtungKopf() {
  const {stand} = useEinrichtung();
  const offen = stand ? offeneSchritte(stand).map(schritt => schritt.kurz) : [];
  return <div className="einrichtung-kopf">
    <section className="einrichtung-assistent" aria-label="Einrichtungsassistent">
      <div>
        <h2>Einrichtung in einem Durchgang</h2>
        <p>{!stand ? "Der Stand wird geladen …" : offen.length
          ? `Noch offen: ${offen.join(", ")}. Der Assistent führt dich Schritt für Schritt und lässt sich jederzeit unterbrechen.`
          : "Alles Wesentliche ist durchgegangen. Du kannst den Assistenten jederzeit noch einmal öffnen."}</p>
      </div>
      <button className={offen.length ? "primary-action" : "secondary-action"} type="button" disabled={!stand}
        onClick={() => navigate(offen.length ? "/willkommen" : "/willkommen?schritt=name")}>{offen.length ? "Einrichtung fortsetzen" : "Assistenten öffnen"}</button>
    </section>
    <KingfisherLernt />
  </div>;
}
