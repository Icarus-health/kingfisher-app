import type { KeyboardEvent, ReactNode } from "react";
import { segmentImFokus, segmentNachTaste } from "./segmentTasten.ts";

export type Segment<T extends string> = {
  wert: T;
  titel: ReactNode;
  /** Zahl neben dem Titel, nur wenn größer als null. */
  zahl?: number;
  deaktiviert?: boolean;
};

/** Merkt am rollenden Behälter, ob links oder rechts noch etwas verborgen ist; die Stile blenden dort den Rand aus. */
export function raenderMarkieren(el: HTMLElement) {
  const rest = el.scrollWidth - el.clientWidth - el.scrollLeft;
  el.dataset.randLinks = String(el.scrollLeft > 1);
  el.dataset.randRechts = String(rest > 1);
}

/** Die Ränder neu markieren, wenn sich die Breite ändert (React 19: der Rückgabewert räumt auf). */
function beobachten(el: HTMLDivElement | null) {
  if (!el) return;
  raenderMarkieren(el);
  if (typeof ResizeObserver === "undefined") return;
  const beobachter = new ResizeObserver(() => raenderMarkieren(el));
  beobachter.observe(el);
  return () => beobachter.disconnect();
}

/** Segmente: Segmentsteuerung als Pille. Rollt waagrecht, statt umzubrechen; Pfeiltasten, Pos1 und Ende wählen
 * (die Taste wählt sofort, wie am Mac). Ohne Zustand: Die Seite hält den gewählten Wert. */
export function Segmente<T extends string>({ optionen, wert, onWahl, label, kompakt = false, className }: {
  optionen: readonly Segment<T>[];
  wert: T;
  onWahl: (wert: T) => void;
  /** Name für Vorleser, etwa „Ansicht“. */
  label: string;
  kompakt?: boolean;
  className?: string;
}) {
  const abgeschaltet = optionen.map(o => Boolean(o.deaktiviert));
  const gewaehlt = optionen.findIndex(o => o.wert === wert);
  const imFokus = segmentImFokus(gewaehlt, abgeschaltet);

  function taste(e: KeyboardEvent<HTMLDivElement>) {
    const knoepfe = [...e.currentTarget.querySelectorAll<HTMLButtonElement>("[role='tab']")];
    const jetzt = knoepfe.findIndex(k => k === e.target);
    const ziel = segmentNachTaste(e.key, jetzt >= 0 ? jetzt : imFokus, abgeschaltet);
    if (ziel === null) return;
    e.preventDefault();
    onWahl(optionen[ziel].wert);
    knoepfe[ziel]?.focus();
    knoepfe[ziel]?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }

  // data-rollt="waagrecht": die eine gewollte Ausnahme von „nichts rollt seitlich“ (docs/16-gestaltung.md).
  return <div role="tablist" aria-label={label} aria-orientation="horizontal" onKeyDown={taste}
    data-rollt="waagrecht" ref={beobachten} onScroll={e => raenderMarkieren(e.currentTarget)}
    className={["g-segmente", kompakt ? "g-kompakt" : "", className].filter(Boolean).join(" ")}>
    {optionen.map((o, i) => <button key={o.wert} type="button" role="tab" className="g-segment"
      aria-selected={i === gewaehlt} tabIndex={i === imFokus ? 0 : -1} disabled={o.deaktiviert}
      onClick={e => { onWahl(o.wert); e.currentTarget.scrollIntoView?.({ block: "nearest", inline: "nearest" }); }}>
      <span>{o.titel}</span>
      {o.zahl && o.zahl > 0 ? <span className="g-segment-zahl">{o.zahl}</span> : null}
    </button>)}
  </div>;
}
