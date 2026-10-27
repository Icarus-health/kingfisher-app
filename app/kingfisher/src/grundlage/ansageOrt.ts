// Eine höfliche Ansage für Vorleser (Persona-Prüfung, Paket B, B1, 27.10.2026): ohne React, testbar mit node --test.
//
// Der Ort steht einmal in der App (`Ansage.tsx` in main.tsx) und bleibt über Seitenwechsel stehen, damit eine Ansage
// nicht mit der Seite verschwindet. Er ist leer, bis etwas anzusagen ist; ein neuer Satz ersetzt den alten. Damit auch ein
// gleicher Satz noch einmal angesagt wird, leert der Ort sich zuerst und setzt den Satz einen Augenblick später.

type Uhr = { setTimeout(f: () => void, ms: number): unknown; clearTimeout(id: unknown): void };

/** So lange steht der Ort leer, bevor der Satz kommt: Vorleser sagen nur Änderungen an. */
export const ANSAGE_PAUSE_MS = 150;
/** Danach räumt der Ort sich, damit beim Zurückblättern mit dem Vorleser kein alter Satz steht. */
export const ANSAGE_STEHT_MS = 10000;

export class AnsageOrt {
  private text = "";
  private hoerer = new Set<() => void>();
  private zeit: unknown = null;
  private uhr: Uhr;
  constructor(uhr: Uhr = globalThis as unknown as Uhr) { this.uhr = uhr; }
  stand = () => this.text;
  abonnieren = (f: () => void) => { this.hoerer.add(f); return () => { this.hoerer.delete(f); }; };
  private setzen(text: string) { this.text = text; this.hoerer.forEach(f => f()); }
  sageAn = (text: string) => {
    const satz = text.replace(/\s+/g, " ").trim();
    if (!satz) return;
    if (this.zeit !== null) this.uhr.clearTimeout(this.zeit);
    this.setzen("");
    this.zeit = this.uhr.setTimeout(() => {
      this.setzen(satz);
      this.zeit = this.uhr.setTimeout(() => { this.zeit = null; this.setzen(""); }, ANSAGE_STEHT_MS);
    }, ANSAGE_PAUSE_MS);
  };
}

export const ansagen = new AnsageOrt();
export const sageAn = (text: string) => ansagen.sageAn(text);
