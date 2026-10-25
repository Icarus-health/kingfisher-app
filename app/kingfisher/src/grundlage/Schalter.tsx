import type { ReactNode } from "react";

/** Schalter: ein Umlegeschalter wie am Mac, rechts in seiner Zeile; links der Titel und darunter leise der eine Satz (etwa,
 * was den Rechner verlässt). Die ganze Zeile ist das Ziel (`label`). Die Stile gelten für jedes `input[role=switch]`
 * (Grundlage.css, „Schalter“). Ohne Zustand: Die Seite hält `an` und speichert in `onWechsel`. */
export function Schalter({ titel, satz, an, onWechsel, deaktiviert, className }: {
  titel: ReactNode;
  /** Ein Satz unter dem Titel; ohne ihn steht nur der Titel da. */
  satz?: ReactNode;
  an: boolean;
  onWechsel: (an: boolean) => void;
  deaktiviert?: boolean;
  className?: string;
}) {
  return <label className={className}>
    <input type="checkbox" role="switch" checked={an} disabled={deaktiviert} onChange={event => onWechsel(event.target.checked)} />
    {satz ? <span><strong>{titel}</strong><small>{satz}</small></span> : <span>{titel}</span>}
  </label>;
}
