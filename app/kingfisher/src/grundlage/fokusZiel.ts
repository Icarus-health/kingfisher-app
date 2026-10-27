// Wohin der Fokus geht, wenn eine Aktion ihren Knopf mitnimmt (Persona-Prüfung, Paket Z3, 27.10.2026).
//
// Bis 1.0.29 sprang er auf „Rückgängig“ im Hinweis: Für Vorleser war das gut (er landete nicht im Nichts), aber ein
// zweites Enter nahm sofort alles zurück, und am Handy hielt der Fokus den Hinweis zwanzig Sekunden über dem Schalter
// darunter. Jetzt bleibt der Fokus bei der Arbeit: Steht der Knopf noch da, auf ihm; ist er gesperrt, weil die Aktion
// noch läuft, wird gewartet; ist er mit seiner Zeile verschwunden, auf der Liste oder dem Abschnitt, in dem er stand.
// Das ist ein Ort ohne eigene Wirkung: Ein zweites Enter löst dort nichts aus, Tab führt zur nächsten Zeile. Der Hinweis
// wird als Status angesagt (mit „Zurücknehmen mit Steuerung Z“), ist mit ⌘Z/Strg+Z oder Tab erreichbar, aber nie
// vorausgewählt. Ohne DOM-Typen geschrieben, damit es sich ohne Browser prüfen lässt.

type Knoten = {
  isConnected: boolean;
  parentElement: Knoten | null;
  matches(selektor: string): boolean;
  closest(selektor: string): Knoten | null;
  hasAttribute(name: string): boolean;
  setAttribute(name: string, wert: string): void;
  focus(optionen?: { preventScroll?: boolean }): void;
  disabled?: boolean;
};

/** Ein Abschnitt, der als Ziel taugt: er hat einen Namen (Überschrift oder Beschriftung) oder ist die Seite. */
const BEHAELTER = "section, article, form, ul, ol, aside, dialog, main, [role=region], [role=list], [role=dialog], .g-flaeche, .g-gruppe";
/** Der Hinweis selbst ist nie Ziel. */
const HINWEIS = ".g-hinweis-ort";

export type FokusMerk<K extends Knoten = Knoten> = { ausloeser: K; vorfahren: K[] };

/** Merkt sich bei jedem Tastendruck, wo der Fokus war, mit seinen Vorfahren (damit sie auch nach dem Entfernen
 * bekannt sind). */
export function merkeFokus<K extends Knoten>(element: K | null): FokusMerk<K> | null {
  if (!element) return null;
  const vorfahren: K[] = [];
  for (let n = element.parentElement as K | null; n; n = n.parentElement as K | null) vorfahren.push(n);
  return { ausloeser: element, vorfahren };
}

/** Das Ziel nach einer Aktion, die den Fokus verloren hat, oder null (noch warten). */
export function fokusZiel<K extends Knoten>(merk: FokusMerk<K> | null, seite: K | null): K | null {
  const imHinweis = (n: K) => Boolean(n.closest(HINWEIS));
  if (merk && merk.ausloeser.isConnected && !imHinweis(merk.ausloeser)) {
    if (merk.ausloeser.disabled) return null;
    return merk.ausloeser;
  }
  const behaelter = merk?.vorfahren.find(n => n.isConnected && !imHinweis(n) && n.matches(BEHAELTER)) ?? null;
  const ziel = behaelter ?? seite;
  if (ziel && !ziel.hasAttribute("tabindex")) ziel.setAttribute("tabindex", "-1");
  return ziel;
}
