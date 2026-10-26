import type { ReactNode } from "react";

/** Bestätigung: die Karte für alles, was erst mit dem Klick eines Menschen gilt (Freigabe einer Aktion,
 * Gedächtnisvorschlag, Vorschlag für die Akte). Eine ruhige graue Fläche, klein der Titel, groß der Satz (als
 * `<strong>` im Inhalt), darunter die Knöpfe. Nichts darin geschieht ohne den Klick. */
export function Bestaetigung({ titel, label, knoepfe, knoepfeKlasse, className, children }: {
  /** Klein über dem Satz: „Gedächtnisvorschlag“, „Zur Freigabe“. */
  titel: ReactNode;
  /** Name für Vorleser. */
  label: string;
  /** Die Knöpfe (Bestätigen, Ablehnen); `null` hält die Leiste stehen, auch wenn gerade keiner gilt. */
  knoepfe?: ReactNode;
  /** Eine zusätzliche Klasse an der Knopfleiste (für die Seite, nicht für das Aussehen). */
  knoepfeKlasse?: string;
  className?: string;
  children?: ReactNode;
}) {
  return <section className={["g-bestaetigung", className].filter(Boolean).join(" ")} aria-label={label}>
    <span className="g-bestaetigung-titel">{titel}</span>
    {children}
    {knoepfe !== undefined ? <div className={["g-bestaetigung-knoepfe", knoepfeKlasse].filter(Boolean).join(" ")}>{knoepfe}</div> : null}
  </section>;
}
