import { useId, type ReactNode } from "react";

/** Gruppe: eine gruppierte Fläche, optional klein die Überschrift darüber und eine Fußnote darunter. Zeilen
 * (`Zeile`) stehen direkt darin; freier Inhalt bekommt mit `frei` Innenabstand. */
export function Gruppe({ titel, fussnote, frei = false, children, className }: {
  titel?: ReactNode;
  /** Ein Satz unter der Fläche, nur wo ohne ihn ein Fehler passiert. */
  fussnote?: ReactNode;
  /** Freier Inhalt statt Zeilen: dann mit Innenabstand. */
  frei?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return <section className={["g-gruppe", className].filter(Boolean).join(" ")} aria-labelledby={titel ? id : undefined}>
    {titel ? <div className="g-gruppe-kopf"><h2 className="g-gruppe-titel" id={id}>{titel}</h2></div> : null}
    <div className={frei ? "g-flaeche g-flaeche-frei" : "g-flaeche"}>{children}</div>
    {fussnote ? <p className="g-gruppe-fussnote">{fussnote}</p> : null}
  </section>;
}
