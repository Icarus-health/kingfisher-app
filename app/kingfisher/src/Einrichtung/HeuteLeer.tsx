import {useState, type ReactNode} from "react";
import {ASSET, navigate} from "../ui";
import {KingfisherLernt} from "./KingfisherLernt";
import {naechsterHinweis} from "./schritte";
import {useEinrichtung} from "./useEinrichtung";
import "./Einrichtung.css";

/**
 * Die Startseite, solange noch nichts da ist: statt leerer Karten ein einziger klarer nächster Schritt, und während
 * Kingfisher die ersten Mails liest, der Fortschritt. Ist etwas da, stehen die Karten wie immer da, und wenn im
 * Hintergrund etwas läuft, darüber eine ruhige Zeile.
 */
export function HeuteLeer({leer, children}: {leer: boolean; children: ReactNode}) {
  const {stand} = useEinrichtung();
  const [laeuft, setLaeuft] = useState<boolean | null>(null);
  // Dieselbe Karte in beiden Fällen (Schlüssel „lernt“): Kommen die Karten nach, darf sie nicht neu entstehen, sonst
  // klappten aufgeklappte „Details“ von selbst wieder zu.
  if (!leer) return <>
    <KingfisherLernt key="lernt" kompakt />
    {children}
  </>;

  const hinweis = stand ? naechsterHinweis(stand.vorhanden, laeuft === true) : null;
  // Solange unbekannt ist, ob etwas läuft, bleibt die Fläche ruhig leer, statt kurz leere Karten zu zeigen.
  const karten = stand !== null && laeuft === false && !hinweis;
  return <>
    {hinweis ? <section className="heute-naechster-schritt" aria-labelledby="heute-naechster-titel">
      <img src={`${ASSET.media}kingfisher-flight-clean-v1.png`} alt="" />
      <div>
        <h2 id="heute-naechster-titel">Als Nächstes</h2>
        <p>{hinweis.text}</p>
        <button className="primary-action" type="button" onClick={() => navigate(`/willkommen?schritt=${hinweis.schritt}`)}>{hinweis.knopf}</button>
      </div>
    </section> : null}
    <KingfisherLernt key="lernt" beiAenderung={setLaeuft} />
    {karten ? children : null}
  </>;
}
