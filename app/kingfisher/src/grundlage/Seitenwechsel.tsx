import { useEffect, type MouseEvent } from "react";
import { fokusVerloren, seiteGewechselt, seitenTitel } from "./seitenwechselModell.ts";

/** Die Hauptüberschrift der Seite: die erste sichtbare im Inhalt (nicht die klebende Kopfleiste, die `aria-hidden` ist). */
function hauptueberschrift(): HTMLElement | null {
  for (const h of document.querySelectorAll<HTMLElement>("main h1")) {
    if (!h.closest("[aria-hidden=true], dialog") && h.getClientRects().length > 0) return h;
  }
  return null;
}

/** Fokus auf ein Ziel, das selbst kein Bedienelement ist: nur programmatisch fokussierbar, kein neuer Tab-Halt. */
function fokussieren(ziel: HTMLElement) {
  if (!ziel.hasAttribute("tabindex")) ziel.setAttribute("tabindex", "-1");
  ziel.focus({ preventScroll: false });
}

/**
 * Seitenwechsel (Paket B, B2): steht einmal in der App (main.tsx). Setzt den Fenstertitel jeder Seite und stellt nach
 * einem Wechsel, bei dem der Fokus verloren ging, den Fokus auf die Hauptüberschrift (das sagt der Vorleser an). Was die
 * neue Seite selbst fokussiert (das Eingabefeld im Gespräch nach dem Senden), bleibt. Davor der Sprunglink „Zum Inhalt
 * springen“, der beim ersten Tab erscheint.
 */
export function Seitenwechsel() {
  useEffect(() => {
    if (typeof document === "undefined") return;
    let pfad: string | null = null;
    let warten: number | undefined;
    let titelRahmen: number | undefined;

    const titel = () => {
      titelRahmen = undefined;
      const neu = seitenTitel(window.location.pathname, hauptueberschrift()?.textContent);
      if (document.title !== neu) document.title = neu;
    };
    const titelBald = () => { if (titelRahmen === undefined) titelRahmen = window.requestAnimationFrame(titel); };

    const wechsel = () => {
      const jetzt = window.location.pathname;
      const gewechselt = seiteGewechselt(pfad, jetzt);
      pfad = jetzt;
      titelBald();
      if (!gewechselt) return;
      window.clearTimeout(warten);
      // Die neue Seite rendert nach dem Ereignis; ihre Überschrift kann erst mit den Daten kommen. Bis zu 3 s warten.
      let versuche = 0;
      const schritt = () => {
        if (!fokusVerloren(document.activeElement, document.body, document.querySelector("main"))) return;
        const h = hauptueberschrift();
        if (h) { fokussieren(h); return; }
        if (++versuche < 60) warten = window.setTimeout(schritt, 50);
      };
      warten = window.setTimeout(schritt, 0);
    };

    wechsel();
    window.addEventListener("popstate", wechsel);
    // Der Titel folgt der Überschrift, auch wenn sie erst mit den Daten kommt (der Name des Gesprächs).
    const beobachter = typeof MutationObserver === "undefined" ? null : new MutationObserver(titelBald);
    const wurzel = document.getElementById("root");
    if (beobachter && wurzel) beobachter.observe(wurzel, { childList: true, subtree: true, characterData: true });
    return () => {
      window.removeEventListener("popstate", wechsel);
      beobachter?.disconnect();
      window.clearTimeout(warten);
      if (titelRahmen !== undefined) window.cancelAnimationFrame(titelRahmen);
    };
  }, []);
  return null;
}

/** „Zum Inhalt springen“: der erste Tab-Halt jeder Seite, sichtbar nur mit Fokus; führt an der Navigation vorbei zur
 * Hauptüberschrift (oder, wo es keine gibt, zum Inhalt). */
export function Sprunglink() {
  function springen(e: MouseEvent<HTMLAnchorElement>) {
    e.preventDefault();
    const ziel = hauptueberschrift() ?? document.querySelector<HTMLElement>("main");
    if (ziel) fokussieren(ziel);
  }
  return <a className="g-sprunglink" href="#inhalt" onClick={springen}>Zum Inhalt springen</a>;
}
