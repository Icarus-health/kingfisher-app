import { useId, type ReactNode } from "react";

/** Gruppe: eine gruppierte Fläche, optional klein die Überschrift darüber und eine Fußnote darunter. Zeilen
 * (`Zeile`) stehen direkt darin; freier Inhalt bekommt mit `frei` Innenabstand. Im Kopf rechts leise eine Zahl
 * (`zahl`, etwa „2 Postfächer“) oder eine Aktion (`aktion`); im Fuß rechts eine Aktion (`fussAktion`, etwa
 * „Postfach hinzufügen“), links daneben die Fußnote – wie die Accounts in den Systemeinstellungen am Mac. */
export function Gruppe({ titel, zahl, aktion, fussnote, fussAktion, frei = false, label, flaecheKlasse, stufe = 2, children, className }: {
  titel?: ReactNode;
  /** Leise rechts im Kopf; nur, wenn es etwas zu zählen gibt (die Seite entscheidet, null blendet aus). */
  zahl?: ReactNode;
  /** Ein schlichter Knopf rechts im Kopf. */
  aktion?: ReactNode;
  /** Ein Satz unter der Fläche, nur wo ohne ihn ein Fehler passiert. */
  fussnote?: ReactNode;
  /** Ein Knopf rechts unter der Fläche (schmal: darunter). Auch `null` hält den Fuß stehen (etwa, solange ein Formular offen ist). */
  fussAktion?: ReactNode;
  /** Freier Inhalt statt Zeilen: dann mit Innenabstand. */
  frei?: boolean;
  /** Name der Gruppe für Vorleser, wenn der sichtbare Titel nicht reicht oder fehlt. */
  label?: string;
  /** Eine zusätzliche Klasse an der Fläche (für den Inhalt der Seite, nicht für ihr Aussehen). */
  flaecheKlasse?: string;
  /** Stufe der Überschrift (Paket B, B5): 2 direkt unter dem Seitentitel, 3 in einem Abschnitt mit eigener h2. */
  stufe?: 2 | 3 | 4;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const Ueberschrift = stufe === 4 ? "h4" : stufe === 3 ? "h3" : "h2";
  const zahlDa = zahl !== undefined && zahl !== null && zahl !== false && zahl !== "";
  const kopf = titel || zahlDa || aktion;
  return <section className={["g-gruppe", className].filter(Boolean).join(" ")} aria-label={label}
    aria-labelledby={!label && titel ? id : undefined}>
    {kopf ? <div className="g-gruppe-kopf">{titel ? <Ueberschrift className="g-gruppe-titel" id={id}>{titel}</Ueberschrift> : null}
      {zahlDa ? <span className="g-gruppe-zahl">{zahl}</span> : null}{aktion ? <span className="g-gruppe-aktion">{aktion}</span> : null}</div> : null}
    <div className={["g-flaeche", frei ? "g-flaeche-frei" : null, flaecheKlasse].filter(Boolean).join(" ")}>{children}</div>
    {fussAktion !== undefined ? <div className="g-gruppe-fuss"><p className="g-gruppe-fussnote">{fussnote ?? ""}</p>{fussAktion}</div>
      : fussnote ? <p className="g-gruppe-fussnote">{fussnote}</p> : null}
  </section>;
}
