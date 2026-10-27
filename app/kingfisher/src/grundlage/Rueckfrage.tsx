import { useEffect, useId, useLayoutEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { fokusZiel, merkeFokus, type FokusMerk } from "./fokusZiel.ts";
import { fallenZiel, RUECKFRAGE_BEDIENBAR, RUECKFRAGE_ROLLE, startSelektor, type RueckfrageStart } from "./rueckfrageModell.ts";

/**
 * Rückfrage (Paket B, B3): eine Frage vor etwas, das sich nicht zurücknehmen lässt, als echter Dialog. Die Seite zeigt
 * sie, solange gefragt wird (`{frage && <Rueckfrage … />}`): Mit dem Erscheinen öffnet sie modal, mit dem Verschwinden
 * geht der Fokus zurück. Ein Satz als Frage, höchstens ein Satz darunter, zwei Knöpfe: „Abbrechen“ (vorausgewählt) und
 * die Aktion, rot, wenn sie etwas unwiderruflich entfernt.
 *
 * - `role=alertdialog`, `aria-modal`, beschriftet mit der Frage, beschrieben mit dem Satz.
 * - Fokus beim Öffnen auf „Abbrechen“ (oder im Feld, wenn erst etwas einzutragen ist), Tab bleibt im Dialog.
 * - Escape bricht ab (nicht, solange die Aktion läuft).
 * - Danach der Fokus am Auslöser; ist er mit seiner Zeile verschwunden, auf der Liste oder dem Abschnitt (`fokusZiel`).
 * - Solange die Aktion läuft, bleiben die Knöpfe stehen und fokussiert, nehmen aber nichts an (`aria-disabled`): Ein
 *   gesperrter Knopf verlöre den Fokus.
 */
export function Rueckfrage({ frage, satz, bestaetigen, abbrechen = "Abbrechen", onBestaetigen, onAbbrechen, arbeitet = false,
  gesperrt = false, rot = false, start = "abbrechen", fehler, children, className }: {
  /** Die Frage in einem Satz: „Quelle wirklich entfernen?“ */
  frage: ReactNode;
  /** Höchstens ein Satz dazu: was danach gilt. */
  satz?: ReactNode;
  /** Beschriftung der Aktion: „Entfernen“. */
  bestaetigen: ReactNode;
  /** Beschriftung der sicheren Wahl; Vorgabe „Abbrechen“. */
  abbrechen?: ReactNode;
  onBestaetigen: () => void;
  onAbbrechen: () => void;
  /** Die Aktion läuft: Knöpfe nehmen nichts an, Escape bricht nicht ab. */
  arbeitet?: boolean;
  /** Die Aktion ist noch nicht möglich (etwa: der Grund fehlt). */
  gesperrt?: boolean;
  /** Entfernt etwas unwiderruflich: der Knopf rot (docs/16-gestaltung.md, Knöpfe). */
  rot?: boolean;
  /** Womit der Fokus beginnt; „feld“ nur, wenn erst etwas einzutragen ist (das Feld trägt `data-rueckfrage-feld`). */
  start?: RueckfrageStart;
  /** Ein Fehler der Aktion, angesagt im Dialog. */
  fehler?: ReactNode;
  /** Zusätzlicher Inhalt zwischen Satz und Knöpfen (etwa ein Feld für den Grund). */
  children?: ReactNode;
  className?: string;
}) {
  const dialog = useRef<HTMLDialogElement | null>(null);
  const merk = useRef<FokusMerk<HTMLElement> | null>(null);
  const offen = useRef(false);
  const abbrechenRef = useRef(onAbbrechen);
  abbrechenRef.current = onAbbrechen;
  const arbeitetRef = useRef(arbeitet);
  arbeitetRef.current = arbeitet;
  const titelId = useId();
  const satzId = useId();

  // Öffnen mit dem Erscheinen, Fokus auf die sichere Wahl; beim Verschwinden zurück zum Auslöser.
  useLayoutEffect(() => {
    const el = dialog.current;
    if (!el) return;
    merk.current = merkeFokus(ausloeser());
    offen.current = true;
    try { if (!el.open) el.showModal(); } catch { el.setAttribute("open", ""); }
    (el.querySelector<HTMLElement>(startSelektor(start)) ?? el.querySelector<HTMLElement>(startSelektor("abbrechen")))?.focus();
    return () => {
      offen.current = false;
      try { if (el.open) el.close(); } catch { /* schon zu */ }
      fokusZurueck(merk.current);
    };
  }, []);

  function taste(e: KeyboardEvent<HTMLDialogElement>) {
    if (e.key !== "Tab" || !dialog.current) return;
    const bedienbar = [...dialog.current.querySelectorAll<HTMLElement>(RUECKFRAGE_BEDIENBAR)]
      .filter(k => !(k as HTMLButtonElement).disabled && k.getClientRects().length > 0);
    const ziel = fallenZiel(bedienbar.indexOf(document.activeElement as HTMLElement), bedienbar.length, e.shiftKey);
    if (ziel === null) return;
    e.preventDefault();
    bedienbar[ziel].focus();
  }

  const inhalt = <dialog ref={dialog} className={["g-rueckfrage", className].filter(Boolean).join(" ")} role={RUECKFRAGE_ROLLE}
    aria-modal="true" aria-labelledby={titelId} aria-describedby={satz ? satzId : undefined} aria-busy={arbeitet || undefined}
    onKeyDown={taste}
    // Escape: Der Browser meldet „cancel“; die Seite entscheidet über das Schließen (sie nimmt die Rückfrage weg).
    onCancel={e => { e.preventDefault(); if (!arbeitetRef.current) abbrechenRef.current(); }}
    // Schließt der Browser trotzdem (zweites Escape ohne Nutzeraktion), gilt das als Abbrechen.
    onClose={() => { if (offen.current && !arbeitetRef.current) abbrechenRef.current(); }}>
    <h2 className="g-rueckfrage-frage" id={titelId}>{frage}</h2>
    {satz ? <p className="g-rueckfrage-satz" id={satzId}>{satz}</p> : null}
    {children}
    {fehler ? <p className="g-rueckfrage-fehler" role="alert">{fehler}</p> : null}
    <div className="g-rueckfrage-knoepfe">
      <button type="button" className="g-knopf-getoent" data-rueckfrage-abbrechen="" aria-disabled={arbeitet || undefined}
        onClick={() => { if (!arbeitet) onAbbrechen(); }}>{abbrechen}</button>
      <button type="button" className={rot ? "g-knopf-rot" : "g-knopf"} data-rueckfrage-aktion="" aria-disabled={arbeitet || gesperrt || undefined}
        onClick={() => { if (!arbeitet && !gesperrt) onBestaetigen(); }}>{bestaetigen}</button>
    </div>
  </dialog>;
  // Über allem, außerhalb der Zeile: So erbt der Dialog keine Farbe und keine Schrift der Stelle, an der gefragt wird.
  return typeof document === "undefined" ? inhalt : createPortal(inhalt, document.body);
}

// -- Wer gefragt hat -----------------------------------------------------------------------------------------------

/** Der zuletzt mit Maus oder Finger bediente Knopf: Safari fokussiert Knöpfe beim Klick nicht. */
let zuletztBedient: HTMLElement | null = null;
if (typeof document !== "undefined") {
  document.addEventListener("pointerdown", e => {
    const ziel = e.target instanceof Element ? e.target.closest<HTMLElement>("button, a[href], [role=button], summary") : null;
    if (ziel && !ziel.closest(".g-rueckfrage")) zuletztBedient = ziel;
  }, true);
}

function ausloeser(): HTMLElement | null {
  if (typeof document === "undefined") return null;
  const aktiv = document.activeElement;
  if (aktiv instanceof HTMLElement && aktiv !== document.body && !aktiv.closest(".g-rueckfrage")) return aktiv;
  return zuletztBedient?.isConnected ? zuletztBedient : null;
}

/** Nach dem Schließen: zurück zum Auslöser; ist er gesperrt (die Aktion läuft noch), kurz warten; ist er weg, auf seine
 * Liste. Hat inzwischen jemand anderes den Fokus sinnvoll gesetzt, bleibt er dort. */
function fokusZurueck(merk: FokusMerk<HTMLElement> | null) {
  if (typeof window === "undefined") return;
  let versuche = 0;
  const schritt = () => {
    const aktiv = document.activeElement;
    const verloren = !aktiv || aktiv === document.body || !aktiv.isConnected || Boolean(aktiv.closest("dialog:not([open])"));
    if (!verloren) return;
    const seite = document.querySelector<HTMLElement>("main");
    const ziel = fokusZiel(merk, seite) ?? (versuche >= 40 ? seite : null);
    if (ziel) {
      if (ziel === seite && !ziel.hasAttribute("tabindex")) ziel.setAttribute("tabindex", "-1");
      ziel.focus();
    } else { versuche += 1; window.setTimeout(schritt, 50); }
  };
  window.setTimeout(schritt, 0);
}
