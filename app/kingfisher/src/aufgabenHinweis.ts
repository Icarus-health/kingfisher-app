// Was eine Aufgabe nach einem Klick sagt (Hinweis mit „Rückgängig“, grundlage/hinweisOrt.ts). Jeder Weg zurück ist eine
// vorhandene Route: erledigt ↔ wieder offen (`/done`, `/reopen`), verworfen → wieder offen (`/reopen`), „Warte auf“ ↔
// „Warten beenden“ (`/warten`, `/zurueckholen`), was die Post vorgeschlagen hat → wie vorher (`/rueckgaengig`).
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
export function wartetHinweis(a: Aufgabe, name: string, wartenBeenden: Weg): HinweisDaten {
  return { text: `Wartet auf ${name}.`, rueckgaengig: wartenBeenden, danach: `Warten für ${zitat(a.title)} beendet.` };
}
/** „Warten beenden“: Rückgängig geht nur, wenn bekannt ist, auf wen die Aufgabe gewartet hat. */
export function wartenBeendetHinweis(a: Aufgabe, vorher: string | null | undefined, wiederWarten: (name: string) => Promise<unknown>): HinweisDaten {
  return vorher ? { text: `Warten für ${zitat(a.title)} beendet.`, rueckgaengig: () => wiederWarten(vorher), danach: `Wartet wieder auf ${vorher}.` }
    : { text: `Warten für ${zitat(a.title)} beendet.` };
}
/** Das Zurücknehmen einer Änderung durch die Post: Ein Zurück davon gibt es nicht; der Hinweis sagt nur, was gilt. */
export const POST_ZURUECK = "Zurückgenommen. Die Aufgabe steht wieder so, wie sie vorher war.";
