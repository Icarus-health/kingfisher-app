// Der Hinweis mit „Rückgängig“ (docs/16-gestaltung.md, „Hinweis“): eine Zeile unten in der Mitte, etwa „„Angebot
// prüfen“ erledigt · Rückgängig“. Ein Hinweis zur Zeit; der neue ersetzt den alten. Er steht lange genug, um ihn zu
// lesen (mindestens zehn Sekunden, länger bei langem Satz), und geht nicht, solange Maus, Finger oder Tastaturfokus
// darauf liegen (Paket Z2, WCAG 2.2.1). Er ist nie der einzige Weg zurück: Was er anbietet, gibt es auch an der Sache
// selbst (unter „Erledigt“, in der Aufgabe, in der Prüfliste). Hier steht nur das Modell (ohne DOM, damit es sich ohne
// Browser prüfen lässt); die Anzeige ist `Hinweis.tsx`.
//
// Rückgängig ist nie erfunden: Wer einen Hinweis mit `rueckgaengig` zeigt, gibt den Weg mit, den es dafür schon gibt
// (eine Route im Sidecar). Wo es keinen gibt, zeigt der Hinweis nur, was passiert ist, und eine Rückfrage davor bleibt.

export type HinweisDaten = {
  /** Was passiert ist, ein kurzer Satz: „„Angebot prüfen“ erledigt.“ */
  text: string;
  /** Der vorhandene Weg zurück. Ohne ihn hat der Hinweis keinen Knopf. Gibt er einen Satz zurück (etwa die Antwort des
   * Sidecars), steht dieser danach da; sonst `danach`. Wirft er, sagt der Hinweis, dass nichts zurückgenommen ist. */
  rueckgaengig?: () => unknown | Promise<unknown>;
  /** Was nach dem Zurücknehmen dasteht; Vorgabe „Rückgängig gemacht.“ */
  danach?: string;
  /** Höchstens ein Verweis, etwa zur neuen Akte. */
  verweis?: { text: string; href: string };
  /** Ein Fehler, keine Bestätigung: bleibt länger stehen und wird als Fehler angesagt. */
  fehler?: boolean;
};

export type HinweisPhase = "offen" | "laeuft" | "zurueck" | "fehlgeschlagen";
export type HinweisZustand = { nummer: number; daten: HinweisDaten; phase: HinweisPhase; nachher?: string } | null;

/** Wie lange ein Hinweis mindestens steht, wenn niemand ihn berührt (bis 1.0.29: sechs Sekunden, zu kurz; Paket Z2). */
export const HINWEIS_DAUER = 10000;
/** Ein Fehler (auch ein misslungenes Zurücknehmen) steht länger. */
export const HINWEIS_DAUER_FEHLER = 15000;

/** Lesezeit: zehn Sekunden, bei langem Satz mehr (gut 12 Zeichen je Sekunde, gemächlich gelesen, dazu der Griff zum
 * Knopf); ein Fehler mindestens fünfzehn. */
export function hinweisDauer(text: string, fehler = false): number {
  const lesen = 4000 + Array.from(text).length * 80;
  return Math.max(fehler ? HINWEIS_DAUER_FEHLER : HINWEIS_DAUER, lesen);
}

/** Was Vorleser zum Hinweis mit „Rückgängig“ zusätzlich hören: wie man zurücknimmt, ohne dorthin zu springen. */
export function kuerzelSatz(mac: boolean): string {
  return mac ? "Zurücknehmen mit Befehl Z." : "Zurücknehmen mit Steuerung Z.";
}
export const ZURUECK_TEXT = "Rückgängig gemacht.";
export const ZURUECK_FEHLER = "Nicht zurückgenommen. Die Änderung gilt weiter.";

type Uhr = { setTimeout: (f: () => void, ms: number) => unknown; clearTimeout: (id: unknown) => void };
const systemUhr: Uhr = {
  setTimeout: (f, ms) => globalThis.setTimeout(f, ms),
  clearTimeout: id => globalThis.clearTimeout(id as ReturnType<typeof setTimeout>),
};

/** Ein Ort für den einen Hinweis. Die App hat genau einen (`hinweise`); Tests bauen sich einen eigenen mit eigener Uhr. */
export class HinweisOrt {
  private zustand: HinweisZustand = null;
  private zaehler = 0;
  private zeitgeber: unknown = null;
  private gehalten = new Set<string>();
  private hoerer = new Set<() => void>();
  private uhr: Uhr;
  constructor(uhr: Uhr = systemUhr) { this.uhr = uhr; }

  /** Für `useSyncExternalStore`. */
  abonnieren = (hoerer: () => void) => { this.hoerer.add(hoerer); return () => { this.hoerer.delete(hoerer); }; };
  stand = (): HinweisZustand => this.zustand;

  /** Zeigt einen Hinweis; ein stehender wird ersetzt. Gibt die Nummer zurück (für `schliessen`). */
  zeigen(daten: HinweisDaten): number {
    this.zaehler += 1;
    this.zustand = { nummer: this.zaehler, daten, phase: "offen" };
    this.gehalten.clear();
    this.melden();
    this.stellen();
    return this.zaehler;
  }

  /** Schließt den Hinweis (Escape, Zeitablauf). Mit Nummer nur, wenn noch derselbe steht. */
  schliessen(nummer?: number) {
    if (!this.zustand || (nummer !== undefined && nummer !== this.zustand.nummer)) return;
    this.anhalten();
    this.zustand = null;
    this.gehalten.clear();
    this.melden();
  }

  /** Maus, Finger oder Fokus auf dem Hinweis halten ihn (`grund`: „maus“, „beruehren“, „fokus“); erst wenn nichts mehr hält, läuft die Zeit
   * wieder, und zwar von vorn, damit niemand beim Wegziehen der Maus den Knopf verliert. */
  halten(grund: string, an: boolean) {
    if (!this.zustand) return;
    const vorher = this.gehalten.size > 0;
    if (an) this.gehalten.add(grund); else this.gehalten.delete(grund);
    const jetzt = this.gehalten.size > 0;
    if (vorher === jetzt) return;
    if (jetzt) this.anhalten(); else this.stellen();
  }

  /** „Rückgängig“: ruft den mitgegebenen Weg auf und sagt, wie es ausging. Ein zweiter Klick währenddessen zählt nicht. */
  async zuruecknehmen() {
    const z = this.zustand;
    if (!z || !z.daten.rueckgaengig || z.phase === "laeuft" || z.phase === "zurueck") return;
    this.anhalten();
    this.setzen({ ...z, phase: "laeuft" });
    try {
      const antwort = await z.daten.rueckgaengig();
      const nachher = typeof antwort === "string" && antwort.trim() ? antwort : undefined;
      // Der Knopf ist danach weg; ein Fokus auf ihm hält nichts mehr (ein entfernter Knopf meldet kein Verlassen).
      if (this.zustand?.nummer === z.nummer) { this.gehalten.delete("fokus"); this.setzen({ ...z, phase: "zurueck", nachher }); this.stellen(); }
    } catch {
      if (this.zustand?.nummer === z.nummer) { this.setzen({ ...z, phase: "fehlgeschlagen" }); this.stellen(); }
    }
  }

  private setzen(z: HinweisZustand) { this.zustand = z; this.melden(); }
  private melden() { for (const h of [...this.hoerer]) h(); }
  private anhalten() { if (this.zeitgeber !== null) { this.uhr.clearTimeout(this.zeitgeber); this.zeitgeber = null; } }
  private stellen() {
    this.anhalten();
    const z = this.zustand;
    if (!z || this.gehalten.size > 0 || z.phase === "laeuft") return;
    const fehler = Boolean(z.daten.fehler) || z.phase === "fehlgeschlagen";
    this.zeitgeber = this.uhr.setTimeout(() => this.schliessen(z.nummer), hinweisDauer(hinweisInhalt(z).text, fehler));
  }
}

/** Was im Hinweis steht, je nach Phase: Satz, Knopf (oder keiner), ob es ein Fehler ist. */
export function hinweisInhalt(z: NonNullable<HinweisZustand>): { text: string; knopf: "Rückgängig" | "Erneut versuchen" | null; fehler: boolean } {
  if (z.phase === "zurueck") return { text: z.nachher ?? z.daten.danach ?? ZURUECK_TEXT, knopf: null, fehler: false };
  if (z.phase === "fehlgeschlagen") return { text: ZURUECK_FEHLER, knopf: "Erneut versuchen", fehler: true };
  return { text: z.daten.text, knopf: z.daten.rueckgaengig ? "Rückgängig" : null, fehler: Boolean(z.daten.fehler) };
}

/** ⌘Z (am Mac) bzw. Strg+Z nimmt zurück, solange ein Hinweis mit „Rückgängig“ steht, aber nie in einem Eingabefeld:
 * dort gehört die Taste dem Text. */
export function istRueckgaengigTaste(e: { key: string; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean },
  ziel: { tagName?: string; isContentEditable?: boolean } | null): boolean {
  if (e.key.toLowerCase() !== "z" || e.shiftKey || e.altKey || !(e.metaKey || e.ctrlKey)) return false;
  const tag = (ziel?.tagName ?? "").toUpperCase();
  return !(tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || ziel?.isContentEditable);
}

/** Ein Titel im Hinweis, in „…“ und gekürzt, damit der Hinweis eine Zeile bleibt (der volle Titel steht in der Liste). */
export function zitat(titel: string, hoechstens = 48): string {
  const rein = titel.replace(/\s+/g, " ").trim();
  return `„${rein.length > hoechstens ? `${rein.slice(0, hoechstens - 1).trimEnd()}…` : rein}“`;
}

/** Der eine Hinweis der App. */
export const hinweise = new HinweisOrt();
/** Kurzform für die Seiten: `zeigeHinweis({ text, rueckgaengig })`. */
export const zeigeHinweis = (daten: HinweisDaten) => hinweise.zeigen(daten);
