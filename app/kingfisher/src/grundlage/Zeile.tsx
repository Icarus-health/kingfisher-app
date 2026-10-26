import type { ReactNode } from "react";

type Gemeinsam = {
  titel: ReactNode;
  /** Leise Nebenzeile unter dem Titel. */
  neben?: ReactNode;
  /** Rechts: Wert, Datum, Zahl. */
  wert?: ReactNode;
  /** Ist der Wert ein Zeitpunkt, steht er als `<time dateTime>` da (für Vorleser und Suche). */
  wertZeit?: string;
  /** Eine Klasse am Wert, etwa „overdue“ für eine überfällige Frist. */
  wertKlasse?: string;
  /** Links: ein Zeichen, etwa `<InterfaceIcon name="mail" />`. */
  symbol?: ReactNode;
  className?: string;
};
type Klickbar = Gemeinsam & {
  /** Pfeil rechts; Vorgabe: bei Verweisen ja, bei Knöpfen nein. */
  pfeil?: boolean;
  /** Ausgewählt (etwa die offene Nachricht). */
  aktiv?: boolean;
  deaktiviert?: boolean;
  /** Name für Vorleser, wenn der sichtbare Titel nicht reicht („Akte öffnen: Silke Vogt“). */
  label?: string;
  /** Ein eigenes Bedienelement links (Kreis zum Erledigen, Häkchen). Es liegt über der Zeile; der Rest bleibt das Ziel. */
  links?: ReactNode;
  zusatz?: never;
} & ({ onClick: () => void; href?: never } | { href: string; onClick?: never });
type Statisch = Gemeinsam & {
  onClick?: never; href?: never; pfeil?: never; aktiv?: never; deaktiviert?: never; label?: never; links?: never;
  /** Ein eigenes Bedienelement rechts (Schalter, kleiner Knopf). Nur in statischen Zeilen: keine Knöpfe im Knopf. */
  zusatz?: ReactNode;
};

/** Zeile: Listenzeile von mindestens 52 px. Mit `onClick` oder `href` ist die ganze Zeile das Ziel; mit `links` steht
 * davor ein eigenes Bedienelement (dann deckt der Knopf in der Mitte die Zeile, das Element liegt darüber). */
export function Zeile(props: Klickbar | Statisch) {
  const { titel, neben, wert, wertZeit, wertKlasse, symbol, className } = props;
  const wertKlassen = ["g-zeile-wert", wertKlasse].filter(Boolean).join(" ");
  const inhalt = <>
    {symbol ? <span className="g-zeile-symbol" aria-hidden="true">{symbol}</span> : null}
    <span className="g-zeile-text">
      <span className="g-zeile-titel">{titel}</span>
      {neben ? <span className="g-zeile-neben">{neben}</span> : null}
    </span>
    {wert != null && wert !== "" ? wertZeit ? <time className={wertKlassen} dateTime={wertZeit}>{wert}</time> : <span className={wertKlassen}>{wert}</span> : null}
  </>;
  if (props.href !== undefined || props.onClick !== undefined) {
    const pfeil = props.pfeil ?? props.href !== undefined;
    const pfeilTeil = pfeil ? <span className="g-zeile-pfeil" aria-hidden="true" /> : null;
    const links = props.links;
    const klasse = ["g-zeile", links ? "g-zeile-bedient" : null, className].filter(Boolean).join(" ");
    const ziel = links ? "g-zeile-ziel" : klasse;
    const knopf = props.href !== undefined
      ? <a className={ziel} href={props.deaktiviert ? undefined : props.href} aria-current={props.aktiv ? "page" : undefined}
        aria-disabled={props.deaktiviert || undefined} aria-label={props.label}>{inhalt}{pfeilTeil}</a>
      : <button type="button" className={ziel} onClick={props.onClick} disabled={props.deaktiviert}
        aria-current={props.aktiv ? "true" : undefined} aria-label={props.label}>{inhalt}{pfeilTeil}</button>;
    return links ? <div className={klasse}><span className="g-zeile-links">{links}</span>{knopf}</div> : knopf;
  }
  const klasse = ["g-zeile", className].filter(Boolean).join(" ");
  return <div className={klasse}>{inhalt}{props.zusatz ? <span className="g-zeile-zusatz">{props.zusatz}</span> : null}</div>;
}
