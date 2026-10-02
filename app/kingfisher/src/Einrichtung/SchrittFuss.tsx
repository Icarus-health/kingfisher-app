import type {EinrichtungAenderung, EinrichtungSchritt, EinrichtungStand} from "../api";

/** Was jeder Schritt vom Assistenten bekommt. `weiter` merkt den Schritt als erledigt (mit Zusatz, etwa dem Namen). */
export type SchrittProps = {
  stand: EinrichtungStand;
  neuLesen: () => Promise<unknown>;
  weiter: (zusatz?: EinrichtungAenderung) => Promise<void>;
  ueberspringen: () => Promise<void>;
  zurueck: (() => void) | null;
  /** Springt zu einem anderen Schritt (etwa von „Fertig“ zurück zur Mail, wenn das Postfach nicht antwortet). */
  gehe: (id: EinrichtungSchritt) => void;
  /** Merkt, was getippt, aber noch nicht gespeichert ist; „Später weitermachen“ nimmt es mit (Befund 21). */
  entwurf: (aenderung: EinrichtungAenderung | null) => void;
};

/** Der Fuß eines Schritts: „Weiter“, wenn etwas getan ist; sonst „Überspringen“. Nie ein Pflichtfeld. */
export function SchrittFuss({erledigt, zurueck, weiter, ueberspringen, weiterText = "Weiter", absenden = false, arbeitet = false}: {
  erledigt: boolean;
  zurueck: (() => void) | null;
  weiter: () => void;
  ueberspringen: () => void;
  weiterText?: string;
  /** Der Hauptknopf schickt das umgebende Formular ab (Enter genügt). */
  absenden?: boolean;
  arbeitet?: boolean;
}) {
  return <div className="erststart-fuss">
    {zurueck ? <button className="text-action" type="button" onClick={zurueck} disabled={arbeitet}>Zurück</button> : <span />}
    {erledigt
      ? <button className="primary-action" type={absenden ? "submit" : "button"} onClick={absenden ? undefined : weiter} disabled={arbeitet}>{weiterText}</button>
      : <button className="secondary-action" type="button" onClick={ueberspringen} disabled={arbeitet}>Überspringen</button>}
  </div>;
}
