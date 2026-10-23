import { useEffect, useRef, useState, type ReactNode } from "react";

/** Seitenkopf: großer Titel, höchstens eine Zeile darunter, Aktionen rechts (schmal: darunter). Rollt der Titel aus dem
 * Bild, erscheint oben eine schmale, klebende Leiste mit dem Titel (Grundlage.css, docs/16-gestaltung.md). */
export function Seitenkopf({ titel, zeile, aktionen, className }: {
  titel: ReactNode;
  /** Eine Zeile unter dem Titel, nicht mehr. */
  zeile?: ReactNode;
  /** Höchstens ein gefüllter Knopf (`g-knopf`); alles andere getönt oder schlicht. */
  aktionen?: ReactNode;
  className?: string;
}) {
  const titelRef = useRef<HTMLHeadingElement>(null);
  const [eingerollt, setEingerollt] = useState(false);

  useEffect(() => {
    const el = titelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    // Nur „oben hinausgerollt“ zählt; unter dem Fenster ist der Titel noch nicht erreicht.
    const beobachter = new IntersectionObserver(([eintrag]) => {
      setEingerollt(!eintrag.isIntersecting && eintrag.boundingClientRect.top < 0);
    });
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, []);

  return <>
    <div className="g-kopfleiste" data-sichtbar={eingerollt ? "true" : "false"} aria-hidden="true">
      <div className="g-kopfleiste-inhalt"><span>{titel}</span></div>
    </div>
    <header className={["g-seitenkopf", className].filter(Boolean).join(" ")}>
      <div className="g-seitenkopf-text">
        <h1 className="g-seitenkopf-titel" ref={titelRef}>{titel}</h1>
        {zeile ? <p className="g-seitenkopf-zeile">{zeile}</p> : null}
      </div>
      {aktionen ? <div className="g-seitenkopf-aktionen">{aktionen}</div> : null}
    </header>
  </>;
}
