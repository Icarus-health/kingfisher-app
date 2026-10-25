// Was eine Aufgabe nach einem Klick sagt (Hinweis mit „Rückgängig“, grundlage/hinweisOrt.ts). Jeder Weg zurück ist eine
// vorhandene Route: erledigt ↔ wieder offen (`/done`, `/reopen`), verworfen → wieder offen (`/reopen`), „Warte auf“ ↔
// „Zurück zu mir“ (`/warten`, `/zurueckholen`), was die Post vorgeschlagen hat → wie vorher (`/rueckgaengig`).
import { zitat, type HinweisDaten } from "./grundlage/hinweisOrt.ts";

type Aufgabe = { id: string; title: string };
type Weg = () => Promise<unknown>;

export function erledigtHinweis(a: Aufgabe, wiederOeffnen: Weg): HinweisDaten {
  return { text: `${zitat(a.title)} erledigt.`, rueckgaengig: wiederOeffnen, danach: `${zitat(a.title)} ist wieder offen.` };
}
export function wiederOffenHinweis(a: Aufgabe, erledigen: Weg): HinweisDaten {
  return { text: `${zitat(a.title)} ist wieder offen.`, rueckgaengig: erledigen, danach: `${zitat(a.title)} wieder erledigt.` };
}
export function verworfenHinweis(a: Aufgabe, wiederAufnehmen: Weg): HinweisDaten {
  return { text: `${zitat(a.title)} verworfen.`, rueckgaengig: wiederAufnehmen, danach: `${zitat(a.title)} ist wieder offen.` };
}
export function wartetHinweis(a: Aufgabe, name: string, zurueckZuMir: Weg): HinweisDaten {
  return { text: `Wartet auf ${name}.`, rueckgaengig: zurueckZuMir, danach: `${zitat(a.title)} liegt wieder bei dir.` };
}
/** „Zurück zu mir“: Rückgängig geht nur, wenn bekannt ist, auf wen die Aufgabe gewartet hat. */
export function zurueckZuMirHinweis(a: Aufgabe, vorher: string | null | undefined, wiederWarten: (name: string) => Promise<unknown>): HinweisDaten {
  return vorher ? { text: `${zitat(a.title)} liegt wieder bei dir.`, rueckgaengig: () => wiederWarten(vorher), danach: `Wartet wieder auf ${vorher}.` }
    : { text: `${zitat(a.title)} liegt wieder bei dir.` };
}
/** Das Zurücknehmen einer Änderung durch die Post: Ein Zurück davon gibt es nicht; der Hinweis sagt nur, was gilt. */
export const POST_ZURUECK = "Zurückgenommen. Die Aufgabe steht wieder so, wie sie vorher war.";
