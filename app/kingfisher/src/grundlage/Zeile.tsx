import type { ReactNode } from "react";

type Gemeinsam = {
  titel: ReactNode;
  /** Leise Nebenzeile unter dem Titel. */
  neben?: ReactNode;
  /** Rechts: Wert, Datum, Zahl. */
  wert?: ReactNode;
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
  zusatz?: never;
} & ({ onClick: () => void; href?: never } | { href: string; onClick?: never });
type Statisch = Gemeinsam & {
  onClick?: never; href?: never; pfeil?: never; aktiv?: never; deaktiviert?: never;
  /** Ein eigenes Bedienelement rechts (Schalter, kleiner Knopf). Nur in statischen Zeilen: keine Knöpfe im Knopf. */
  zusatz?: ReactNode;
};

/** Zeile: Listenzeile von mindestens 52 px. Mit `onClick` oder `href` ist die ganze Zeile das Ziel. */
export function Zeile(props: Klickbar | Statisch) {
  const { titel, neben, wert, symbol, className } = props;
  const klasse = ["g-zeile", className].filter(Boolean).join(" ");
  const inhalt = <>
    {symbol ? <span className="g-zeile-symbol" aria-hidden="true">{symbol}</span> : null}
    <span className="g-zeile-text">
      <span className="g-zeile-titel">{titel}</span>
      {neben ? <span className="g-zeile-neben">{neben}</span> : null}
    </span>
    {wert != null && wert !== "" ? <span className="g-zeile-wert">{wert}</span> : null}
  </>;
  if (props.href !== undefined || props.onClick !== undefined) {
    const pfeil = props.pfeil ?? props.href !== undefined;
    const pfeilTeil = pfeil ? <span className="g-zeile-pfeil" aria-hidden="true" /> : null;
    if (props.href !== undefined) {
      return <a className={klasse} href={props.deaktiviert ? undefined : props.href} aria-current={props.aktiv ? "page" : undefined}
        aria-disabled={props.deaktiviert || undefined}>{inhalt}{pfeilTeil}</a>;
    }
    return <button type="button" className={klasse} onClick={props.onClick} disabled={props.deaktiviert}
      aria-current={props.aktiv ? "true" : undefined}>{inhalt}{pfeilTeil}</button>;
  }
  return <div className={klasse}>{inhalt}{props.zusatz ? <span className="g-zeile-zusatz">{props.zusatz}</span> : null}</div>;
}
