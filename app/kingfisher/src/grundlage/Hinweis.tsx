import { useEffect, useRef, useSyncExternalStore, type KeyboardEvent } from "react";
import { hinweise, hinweisInhalt, istRueckgaengigTaste, type HinweisOrt } from "./hinweisOrt.ts";

/**
 * Hinweis: die eine Zeile unten in der Mitte, etwa „„Angebot prüfen“ erledigt · Rückgängig“ (Modell `hinweisOrt.ts`).
 * Steht einmal in der App (main.tsx). Der Ort ist immer da (`role=status`, `aria-live=polite`), damit Vorleser jeden
 * neuen Satz ansagen; ein Fehler wird als Fehler angesagt. Maus und Fokus halten ihn, Escape schließt ihn, ⌘Z bzw.
 * Strg+Z nimmt zurück (außer in Eingabefeldern). Verschwindet bei Tastaturbedienung der Knopf, der die Aktion ausgelöst
 * hat, mit seiner Zeile, geht der Fokus zum Hinweis, statt im Nichts zu landen.
 */
/** Hält nur ein Fokus, den man sieht (Tastatur); ein Mausklick auf „Rückgängig“ hält den Hinweis nicht fest. */
function sichtbarerFokus(el: Element) {
  try { return el.matches(":focus-visible"); } catch { return true; }
}

export function HinweisAnzeige({ ort = hinweise }: { ort?: HinweisOrt }) {
  const zustand = useSyncExternalStore(ort.abonnieren, ort.stand, ort.stand);
  const flaeche = useRef<HTMLDivElement | null>(null);
  const knopf = useRef<HTMLButtonElement | null>(null);
  const ausloeser = useRef<Element | null>(null);
  const nummer = zustand?.nummer ?? 0;

  // Wer mit der Tastatur arbeitet: Der Knopf, der eben gedrückt wurde, ist oft gesperrt oder mit seiner Zeile
  // verschwunden, bis der Hinweis kommt. Dann geht der Fokus zum Hinweis statt ins Nichts. Mit der Maus nie: Dort bliebe
  // der Hinweis sonst stehen, bis man weiterklickt.
  const tastatur = useRef(false);
  useEffect(() => {
    if (typeof document === "undefined") return;
    const taste = (e: globalThis.KeyboardEvent) => { if (!e.metaKey && !e.ctrlKey) tastatur.current = true; };
    const zeiger = () => { tastatur.current = false; };
    document.addEventListener("keydown", taste, true);
    document.addEventListener("pointerdown", zeiger, true);
    return () => { document.removeEventListener("keydown", taste, true); document.removeEventListener("pointerdown", zeiger, true); };
  }, []);
  useEffect(() => {
    if (!nummer || typeof document === "undefined" || !tastatur.current) return;
    ausloeser.current = document.activeElement;
    const pruefen = () => {
      const aktiv = document.activeElement;
      const verloren = !aktiv || aktiv === document.body || (ausloeser.current !== null && !ausloeser.current.isConnected)
        || (aktiv instanceof HTMLButtonElement && aktiv.disabled);
      if (verloren && flaeche.current && !flaeche.current.contains(aktiv)) (knopf.current ?? flaeche.current).focus({ preventScroll: true });
    };
    const zeiten = [60, 500, 1500].map(ms => window.setTimeout(pruefen, ms));
    return () => zeiten.forEach(id => window.clearTimeout(id));
  }, [nummer]);

  // ⌘Z / Strg+Z überall, solange „Rückgängig“ dasteht.
  useEffect(() => {
    if (!zustand || !zustand.daten.rueckgaengig || zustand.phase !== "offen") return;
    const taste = (e: globalThis.KeyboardEvent) => {
      if (e.defaultPrevented || !istRueckgaengigTaste(e, e.target as HTMLElement | null)) return;
      e.preventDefault();
      void ort.zuruecknehmen();
    };
    document.addEventListener("keydown", taste);
    return () => document.removeEventListener("keydown", taste);
  }, [zustand, ort]);

  const inhalt = zustand ? hinweisInhalt(zustand) : null;
  function tasten(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "Escape" || !zustand) return;
    e.preventDefault();
    ort.schliessen(zustand.nummer);
  }
  // Der Ort bleibt stehen; nur sein Inhalt wechselt (so sagen Vorleser jeden Hinweis an).
  return <div className="g-hinweis-ort" role="status" aria-live="polite" aria-atomic="true">
    {zustand && inhalt ? <div key={zustand.nummer} ref={flaeche} className="g-hinweis" tabIndex={-1} data-phase={zustand.phase}
      data-fehler={inhalt.fehler || undefined} aria-busy={zustand.phase === "laeuft" || undefined} onKeyDown={tasten}
      onMouseEnter={() => ort.halten("maus", true)} onMouseLeave={() => ort.halten("maus", false)}
      onFocus={e => ort.halten("fokus", sichtbarerFokus(e.target))}
      onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) ort.halten("fokus", false); }}>
      {inhalt.fehler ? <span className="g-hinweis-text" role="alert">{inhalt.text}</span> : <span className="g-hinweis-text">{inhalt.text}</span>}
      {inhalt.knopf || (zustand.daten.verweis && zustand.phase === "offen") ? <span className="g-hinweis-aktionen">
        {inhalt.knopf ? <><span className="g-hinweis-punkt" aria-hidden="true">·</span>
          <button ref={knopf} type="button" className="g-hinweis-knopf" disabled={zustand.phase === "laeuft"}
            aria-keyshortcuts={inhalt.knopf === "Rückgängig" ? "Meta+Z Control+Z" : undefined}
            onClick={() => void ort.zuruecknehmen()}>{inhalt.knopf}</button></> : null}
        {zustand.daten.verweis && zustand.phase === "offen" ? <><span className="g-hinweis-punkt" aria-hidden="true">·</span>
          <a className="g-hinweis-knopf" href={zustand.daten.verweis.href} onClick={() => ort.schliessen(zustand.nummer)}>{zustand.daten.verweis.text}</a></> : null}
      </span> : null}
    </div> : null}
  </div>;
}
