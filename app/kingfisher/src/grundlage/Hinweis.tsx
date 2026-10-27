import { useEffect, useRef, useSyncExternalStore, type KeyboardEvent } from "react";
import { hinweise, hinweisInhalt, istRueckgaengigTaste, kuerzelSatz, type HinweisOrt } from "./hinweisOrt.ts";
import { fokusZiel, merkeFokus, type FokusMerk } from "./fokusZiel.ts";

/**
 * Hinweis: die eine Zeile unten in der Mitte, etwa „„Angebot prüfen“ erledigt · Rückgängig“ (Modell `hinweisOrt.ts`).
 * Steht einmal in der App (main.tsx). Der Ort ist immer da (`role=status`, `aria-live=polite`), damit Vorleser jeden
 * neuen Satz ansagen, mit dem Tastenkürzel zum Zurücknehmen; ein Fehler wird als Fehler angesagt. Maus, Finger und
 * Fokus halten ihn, Escape schließt ihn, ⌘Z bzw. Strg+Z nimmt zurück (außer in Eingabefeldern).
 *
 * Fokus (Paket Z3): Er springt nie auf „Rückgängig“, sonst nähme ein zweites Enter alles zurück. Verschwindet bei
 * Tastaturbedienung der Knopf, der die Aktion ausgelöst hat, mit seiner Zeile, geht der Fokus auf die Liste oder den
 * Abschnitt, in dem er stand (`fokusZiel.ts`), nicht ins Nichts und nicht in den Hinweis. Mit Tab oder dem Kürzel
 * erreicht man den Hinweis trotzdem.
 *
 * Am Handy (Paket Z3): Die Seite bekommt unten Platz in Höhe des Hinweises, und was man gerade bedient hat, rückt über
 * ihn; so verdeckt er nichts, was man noch erreichen will.
 */
/** Hält nur ein Fokus, den man sieht (Tastatur); ein Mausklick auf „Rückgängig“ hält den Hinweis nicht fest. */
function sichtbarerFokus(el: Element) {
  try { return el.matches(":focus-visible"); } catch { return true; }
}

export function HinweisAnzeige({ ort = hinweise }: { ort?: HinweisOrt }) {
  const zustand = useSyncExternalStore(ort.abonnieren, ort.stand, ort.stand);
  const flaeche = useRef<HTMLDivElement | null>(null);
  const merk = useRef<FokusMerk<HTMLElement> | null>(null);
  const zuletztBeruehrt = useRef<Element | null>(null);
  const fokusDrin = useRef(false);
  const nummer = zustand?.nummer ?? 0;

  // Wer mit der Tastatur arbeitet: Der Knopf, der eben gedrückt wurde, ist oft gesperrt oder mit seiner Zeile
  // verschwunden, bis der Hinweis kommt. Dann geht der Fokus zum Hinweis statt ins Nichts. Mit der Maus nie: Dort bliebe
  // der Hinweis sonst stehen, bis man weiterklickt.
  const tastatur = useRef(false);
  useEffect(() => {
    if (typeof document === "undefined") return;
    // Bei jedem Tastendruck merken, wo der Fokus war (mit seinen Vorfahren, die nach dem Entfernen nicht mehr zu finden sind).
    const taste = (e: globalThis.KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) return;
      tastatur.current = true;
      const aktiv = document.activeElement;
      if (aktiv instanceof HTMLElement && aktiv !== document.body && !aktiv.closest(".g-hinweis-ort")) merk.current = merkeFokus(aktiv);
    };
    const zeiger = (e: PointerEvent) => { tastatur.current = false; zuletztBeruehrt.current = e.target instanceof Element ? e.target : null; };
    // Ein Finger oder eine gedrückte Maustaste auf dem Hinweis hält ihn; Loslassen gibt ihn frei, die Zeit beginnt von vorn.
    const loslassen = () => ort.halten("beruehren", false);
    document.addEventListener("keydown", taste, true);
    document.addEventListener("pointerdown", zeiger, true);
    document.addEventListener("pointerup", loslassen, true);
    document.addEventListener("pointercancel", loslassen, true);
    return () => {
      document.removeEventListener("keydown", taste, true); document.removeEventListener("pointerdown", zeiger, true);
      document.removeEventListener("pointerup", loslassen, true); document.removeEventListener("pointercancel", loslassen, true);
    };
  }, [ort]);
  // Den Fokus dorthin, wo weitergearbeitet wird, wenn die Aktion ihn verloren hat (nie auf „Rückgängig“).
  const fokusZurueck = () => {
    const ziel = fokusZiel(merk.current, document.querySelector("main"));
    ziel?.focus({ preventScroll: true });
    return ziel;
  };
  useEffect(() => {
    if (!nummer || typeof document === "undefined" || !tastatur.current) return;
    const pruefen = () => {
      const aktiv = document.activeElement;
      if (flaeche.current?.contains(aktiv)) return;
      const verloren = !aktiv || aktiv === document.body || !aktiv.isConnected || (aktiv instanceof HTMLButtonElement && aktiv.disabled);
      if (verloren) fokusZurueck();
    };
    const zeiten = [60, 500, 1500, 3000].map(ms => window.setTimeout(pruefen, ms));
    return () => zeiten.forEach(id => window.clearTimeout(id));
  }, [nummer]);
  // Geht der Hinweis, während der Fokus in ihm lag (Escape, Zeitablauf, nach dem Zurücknehmen), kehrt er zur Arbeit zurück.
  const offen = Boolean(zustand);
  useEffect(() => {
    if (offen || !fokusDrin.current || typeof document === "undefined") return;
    fokusDrin.current = false;
    const aktiv = document.activeElement;
    if (!aktiv || aktiv === document.body || !aktiv.isConnected) fokusZurueck();
  }, [offen]);

  // Am Handy: unten Platz in Höhe des Hinweises, und das zuletzt Bediente rückt darüber, damit er nichts verdeckt.
  useEffect(() => {
    if (!nummer || typeof document === "undefined" || !flaeche.current) return;
    const wurzel = document.documentElement;
    const hoehe = Math.ceil(flaeche.current.getBoundingClientRect().height);
    wurzel.style.setProperty("--g-hinweis-platz", `${hoehe}px`);
    wurzel.classList.add("g-hinweis-offen");
    freiRuecken(flaeche.current, document.activeElement !== document.body ? document.activeElement : zuletztBeruehrt.current);
    return () => { wurzel.classList.remove("g-hinweis-offen"); };
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
  const mac = typeof navigator !== "undefined" && /mac/i.test(`${navigator.platform ?? ""}`) && !/iphone|ipad/i.test(navigator.userAgent ?? "");
  // Der Ort bleibt stehen; nur sein Inhalt wechselt (so sagen Vorleser jeden Hinweis an).
  return <div className="g-hinweis-ort" role="status" aria-live="polite" aria-atomic="true">
    {zustand && inhalt ? <div key={zustand.nummer} ref={flaeche} className="g-hinweis" tabIndex={-1} data-phase={zustand.phase}
      data-fehler={inhalt.fehler || undefined} aria-busy={zustand.phase === "laeuft" || undefined} onKeyDown={tasten}
      onMouseEnter={() => ort.halten("maus", true)} onMouseLeave={() => ort.halten("maus", false)}
      onPointerDown={() => ort.halten("beruehren", true)}
      onFocus={e => { fokusDrin.current = true; ort.halten("fokus", sichtbarerFokus(e.target)); }}
      onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) { fokusDrin.current = false; ort.halten("fokus", false); } }}>
      {inhalt.fehler ? <span className="g-hinweis-text" role="alert">{inhalt.text}</span> : <span className="g-hinweis-text">{inhalt.text}
        {inhalt.knopf === "Rückgängig" ? <span className="visually-hidden">{` ${kuerzelSatz(mac)}`}</span> : null}</span>}
      {inhalt.knopf || (zustand.daten.verweis && zustand.phase === "offen") ? <span className="g-hinweis-aktionen">
        {inhalt.knopf ? <><span className="g-hinweis-punkt" aria-hidden="true">·</span>
          <button type="button" className="g-hinweis-knopf" disabled={zustand.phase === "laeuft"}
            aria-keyshortcuts={inhalt.knopf === "Rückgängig" ? "Meta+Z Control+Z" : undefined}
            onClick={() => void ort.zuruecknehmen()}>{inhalt.knopf}</button></> : null}
        {zustand.daten.verweis && zustand.phase === "offen" ? <><span className="g-hinweis-punkt" aria-hidden="true">·</span>
          <a className="g-hinweis-knopf" href={zustand.daten.verweis.href} onClick={() => ort.schliessen(zustand.nummer)}>{zustand.daten.verweis.text}</a></> : null}
      </span> : null}
    </div> : null}
  </div>;
}

const BEDIENBAR = "button, a[href], input, select, textarea, summary, [tabindex='0'], [role=button], [role=switch]";

/** Wie viele bedienbare Dinge eine Fläche des Bildschirms verdeckt (der Hinweis selbst zählt nicht). */
function verdeckt(oben: number, unten: number, links: number, rechts: number): number {
  let n = 0;
  for (const e of document.querySelectorAll(BEDIENBAR)) {
    if (e.closest(".g-hinweis-ort")) continue;
    const b = e.getBoundingClientRect();
    if (b.width && b.height && b.bottom > oben && b.top < unten && b.right > links && b.left < rechts) n += 1;
  }
  return n;
}

/** Am Handy (bis 700 px): Der Hinweis steht dort, wo er nichts Bedienbares verdeckt, unten oder oben; liegt das zuletzt
 * Bediente trotzdem darunter, rückt die Seite es darüber (unten ist dafür Platz, `g-hinweis-offen`). */
function freiRuecken(hinweis: HTMLElement, bedient: Element | null) {
  const ort = hinweis.parentElement;
  const schmal = typeof window.matchMedia === "function" && window.matchMedia("(max-width: 700px)").matches;
  if (ort && schmal) {
    ort.classList.remove("g-hinweis-oben");
    const r = hinweis.getBoundingClientRect();
    const abstand = window.innerHeight - r.bottom;
    if (verdeckt(r.top, r.bottom, r.left, r.right) > 0 && verdeckt(abstand, abstand + r.height, r.left, r.right) === 0)
      ort.classList.add("g-hinweis-oben");
  }
  if (!bedient || !bedient.isConnected || bedient.closest(".g-hinweis-ort")) return;
  const h = hinweis.getBoundingClientRect();
  const b = bedient.getBoundingClientRect();
  if (b.bottom > h.top - 8 && b.top < h.bottom + 8 && b.bottom < window.innerHeight + 1)
    window.scrollBy({ top: ort?.classList.contains("g-hinweis-oben") ? -(h.bottom - b.top + 16) : b.bottom - h.top + 16, behavior: "auto" });
}
