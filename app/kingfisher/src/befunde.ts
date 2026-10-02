// Kleine reine Hilfen der Liste „Was Kingfisher aufgefallen ist“ (sidecar: lint.py); ohne React, im Test ohne Browser.

type Wahlbefund = { art: string; werte: Record<string, string>; vorschlaege: Array<{ wahl: "alt" | "neu"; zustand: string }> };
type Einordnung = { schwere: string; art: string; unterart: string };

/** „Nichts aufgefallen.“, „1 Punkt, davon 1 zum Entscheiden.“ … ohne Prozent, ohne Fachwort. */
export function zaehlSatz(z: { offen: number; wichtig: number }): string {
  if (z.offen === 0) return "Nichts aufgefallen. Die Akten widersprechen sich nicht.";
  const punkte = z.offen === 1 ? "1 Punkt" : `${z.offen} Punkte`;
  if (z.wichtig === 0) return `${punkte}, nur zur Kenntnis.`;
  return `${punkte}, davon ${z.wichtig} zum Entscheiden.`;
}

/** Ein Befund, zu dem es zwei Klicks gibt (alt oder neu): Widerspruch oder angenommene Aussage mit offenem Vorschlag. */
export function waehlbar(befund: Wahlbefund): boolean {
  return (befund.art === "widerspruch" || befund.art === "aussage_gegen_quelle")
    && befund.vorschlaege.some(v => v.zustand === "pending");
}

/** Beschriftung der beiden Knöpfe: der Wert selbst, damit niemand „alt“ und „neu“ übersetzen muss. */
export function wahlTexte(befund: Wahlbefund): { neu: string; alt: string } {
  const neu = befund.werte.neu ?? "neu";
  const alt = befund.werte.alt ?? "alt";
  if (befund.art === "aussage_gegen_quelle") return { neu: `„${neu}“ übernehmen`, alt: `„${alt}“ bleibt` };
  return { neu: `${neu} gilt`, alt: `${alt} gilt` };
}

/** Ruhende Akten stehen gesammelt unten (nur zur Kenntnis), alles andere oben, Entscheidungen zuerst. */
export function gruppieren<T extends Einordnung>(befunde: T[]): { oben: T[]; ruhend: T[] } {
  const ruhend = befunde.filter(b => b.art === "waise" && b.unterart === "ruhend");
  const oben = befunde.filter(b => !(b.art === "waise" && b.unterart === "ruhend"));
  oben.sort((a, b) => (a.schwere === "wichtig" ? 0 : 1) - (b.schwere === "wichtig" ? 0 : 1));
  return { oben, ruhend };
}

/** Was nach einem Klick passiert ist, in einem Satz. */
export function ergebnisSatz(aktion: "neu" | "alt" | "erledigt" | "abgewiesen", befund: Wahlbefund): string {
  if (aktion === "erledigt") return "Als erledigt vermerkt.";
  if (aktion === "abgewiesen") return "Ignoriert. Dieser Punkt kommt nicht wieder, solange sich an den Quellen nichts ändert.";
  const { neu, alt } = { neu: befund.werte.neu ?? "", alt: befund.werte.alt ?? "" };
  if (befund.art === "aussage_gegen_quelle" && aktion === "alt") return `„${alt}“ bleibt, wie du es angenommen hattest.`;
  return `Gespeichert: ${aktion === "neu" ? neu : alt} gilt jetzt. Kingfisher nutzt diesen Stand ab sofort.`;
}
