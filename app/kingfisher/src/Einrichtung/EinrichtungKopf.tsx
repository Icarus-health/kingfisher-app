import type {EinrichtungStand} from "../api";
import {Zeile} from "../grundlage";
import {InterfaceIcon} from "../InterfaceIcon";
import {navigate} from "../ui";
import {KingfisherLernt} from "./KingfisherLernt";
import {offeneSchritte} from "./schritte";
import "./Einrichtung.css";

/** Oben in Einstellungen: der Assistent jederzeit wieder, was noch offen ist, und was im Hintergrund läuft. Den Autostart gibt es unter „Was Kingfisher darf“.
 * Ist etwas offen, ist „Einrichtung fortsetzen“ der eine gefüllte Knopf der Ansicht; sonst eine ruhige Zeile zum Assistenten. */
export function EinrichtungKopf({stand}: {stand: EinrichtungStand | null}) {
  const offen = stand ? offeneSchritte(stand).map(schritt => schritt.kurz) : [];
  return <div className="einrichtung-kopf">
    {offen.length || !stand ? <section className="einrichtung-assistent" aria-label="Einrichtungsassistent">
      <span className="g-zeile-symbol" aria-hidden="true"><InterfaceIcon name="check" /></span>
      <div>
        <h2>Einrichtung</h2>
        <p>{!stand ? "Der Stand wird geladen …" : `Noch offen: ${offen.join(", ")}.`}</p>
      </div>
      <button className="g-knopf" type="button" disabled={!stand} onClick={() => navigate("/willkommen")}>Einrichtung fortsetzen</button>
    </section>
      : <section className="g-flaeche einrichtung-assistent-zeile" aria-label="Einrichtungsassistent">
        <Zeile symbol={<InterfaceIcon name="check" />} titel="Einrichtungsassistent" wert="Durchgesehen" pfeil onClick={() => navigate("/willkommen?schritt=name")} />
      </section>}
    <KingfisherLernt />
  </div>;
}
