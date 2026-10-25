import type { ReactNode } from "react";

/** Unterkopf: der Kopf einer Unteransicht unter dem großen Seitentitel (etwa „Verarbeitung & Verlauf“ im Gedächtnis).
 * Titel, höchstens eine leise Zeile darunter, rechts eine schlichte Aktion (schmal: darunter). */
export function Unterkopf({ titel, zeile, aktion, className }: {
  titel: ReactNode;
  zeile?: ReactNode;
  aktion?: ReactNode;
  className?: string;
}) {
  return <header className={["g-unterkopf", className].filter(Boolean).join(" ")}>
    <div><h2 className="g-titel">{titel}</h2>{zeile ? <p className="g-unterkopf-zeile">{zeile}</p> : null}</div>
    {aktion}
  </header>;
}
