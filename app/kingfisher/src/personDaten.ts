// Alles zu einer Person und die Sicherung zurück (Persona-Prüfung, Paket P, D7, 27.10.2026): die Sätze und Regeln ohne
// React, damit sie sich mit `node --test` prüfen lassen. Die Anzeige steht in `PersonMehr.tsx` und
// `SicherungZurueck.tsx`.
import type { PersonLoeschVorschau, SicherungEintrag, SicherungStand } from "./api";

/** „1 Quelle“, „2 Quellen“. */
export function anzahl(n: number, eins: string, mehr: string): string {
  return `${n} ${n === 1 ? eins : mehr}`;
}

/** „a, b und c“. */
export function aufzaehlen(teile: string[]): string {
  return teile.length < 2 ? teile.join("") : `${teile.slice(0, -1).join(", ")} und ${teile[teile.length - 1]}`;
}

/** Die Rückfrage vor dem Löschen: eine Frage, ein Satz, was gelöscht wird und was bleibt (nur, was es gibt). */
export function loeschRueckfrage(v: PersonLoeschVorschau): { frage: string; satz: string; geloescht: string[]; bleibt: string[] } {
  const z = v.zahlen;
  const geloescht: string[] = [];
  if (z.quellen_nur_ihre) geloescht.push(`${anzahl(z.quellen_nur_ihre, "Quelle", "Quellen")} nur mit dieser Person (aus Kingfisher, nicht aus Postfach oder Kalender)`);
  if (z.quellen_geteilt) geloescht.push(`ihr Bezug zu ${anzahl(z.quellen_geteilt, "Quelle", "Quellen")}, an ${z.quellen_geteilt === 1 ? "der" : "denen"} auch andere beteiligt sind`);
  if (z.aussagen) geloescht.push(`${anzahl(z.aussagen, "bestätigte Angabe", "bestätigte Angaben")} über sie`);
  if (z.vorschlaege) geloescht.push(anzahl(z.vorschlaege, "Vorschlag", "Vorschläge"));
  if (z.aufgaben) geloescht.push(`${anzahl(z.aufgaben, "Aufgabe", "Aufgaben")} von ihr oder für sie`);
  const identitaet = [z.adressen ? (z.adressen === 1 ? "ihre Adresse" : "ihre Adressen") : "",
    z.schreibweisen ? "Schreibweisen" : "", z.zusammenfuehrungen ? "Zusammenführungen" : ""].filter(Boolean);
  if (identitaet.length) geloescht.push(aufzaehlen(identitaet));
  if (z.vermerke) geloescht.push(anzahl(z.vermerke, "Vermerk", "Vermerke"));
  if (z.zusammenfassungen) geloescht.push(anzahl(z.zusammenfassungen, "Zusammenfassung, die sie nennt", "Zusammenfassungen, die sie nennen"));
  const bleibt: string[] = ["Mails und Termine in deinem Postfach und Kalender: Dort löscht Kingfisher nichts."];
  if (z.quellen_geteilt) bleibt.push(`${anzahl(z.quellen_geteilt, "Quelle", "Quellen")} mit anderen Beteiligten, ohne Bezug zu ihr; der Text bleibt, wie er ist.`);
  if (z.gespraeche) bleibt.push(`${anzahl(z.gespraeche, "Gespräch", "Gespräche")} mit Kingfisher, in ${z.gespraeche === 1 ? "dem" : "denen"} sie vorkommt: Das sind deine Fragen; du löschst sie unter Gespräche.`);
  if (v.projekte.length) bleibt.push(`${v.projekte.length === 1 ? "Das Projekt" : "Die Projekte"} ${aufzaehlen(v.projekte.map(p => `„${p}“`))}: ${v.projekte.length === 1 ? "Es gehört" : "Sie gehören"} dir.`);
  bleibt.push("Ältere Sicherungen enthalten sie noch.");
  return {
    frage: `Alles zu ${v.name} löschen?`,
    satz: "Das lässt sich nicht rückgängig machen. Kingfisher legt die Person danach nicht wieder an, bis du das unter Einstellungen → Kingfisher und du aufhebst.",
    geloescht, bleibt,
  };
}

/** Der Hinweis nach dem Löschen. */
export function geloeschtSatz(name: string): string {
  return `Alles zu ${name} gelöscht. Kingfisher legt die Person nicht wieder an.`;
}

/** Der Satz nach dem Export: wo die Datei liegt. */
export function exportSatz(datei: string): string {
  return `Gespeichert: „${datei}“, meist im Ordner „Downloads“. Darin eine Seite zum Lesen und dieselben Angaben als JSON. Nichts davon hat den Rechner verlassen.`;
}

// -- Sicherung ----------------------------------------------------------------------------------------------------

const ZEIT = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
const KURZ = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

/** „Di., 27. Oktober 2026 um 14:05“; ohne lesbare Zeit der Name. */
export function sicherungZeit(iso: string, kurz = false): string {
  const datum = new Date(iso);
  if (!iso || Number.isNaN(datum.getTime())) return iso || "unbekannter Zeitpunkt";
  return (kurz ? KURZ : ZEIT).format(datum).replace(/ um /, ", ");
}

/** Wozu die Sicherung entstand, in Alltagssprache. */
export function sicherungArt(art: SicherungEintrag["art"]): string {
  return art === "vor_update" ? "vor einem Update" : art === "vor_wiederherstellung" ? "vor dem Wiederherstellen" : "regelmäßig";
}

/** Die Rückfrage vor dem Wiederherstellen, in einem Satz. */
export function wiederherstellenFrage(e: Pick<SicherungEintrag, "erstellt">): { frage: string; satz: string } {
  return {
    frage: `Stand vom ${sicherungZeit(e.erstellt, true)} wiederherstellen?`,
    satz: "Was seitdem dazukam, geht verloren. Kingfisher sichert vorher den jetzigen Stand, du kannst es also rückgängig machen.",
  };
}

/** Welcher Stand gilt, nach dem Neuladen gesagt. */
export function standSatz(stand: Pick<SicherungStand, "stand" | "art">): string {
  return stand.art === "vor_wiederherstellung"
    ? `Der Stand von vorher (${sicherungZeit(stand.stand, true)}) gilt wieder.`
    : `Wiederhergestellt: Jetzt gilt der Stand vom ${sicherungZeit(stand.stand, true)}.`;
}

/** Der Kopf unter „Stand wiederherstellen“: welcher Stand seit dem letzten Mal gilt. */
export function kopfSatz(zuletzt: Pick<SicherungStand, "stand" | "art" | "am">): string {
  const stand = sicherungZeit(zuletzt.stand, true), am = sicherungZeit(zuletzt.am, true);
  return zuletzt.art === "vor_wiederherstellung"
    ? `Jetzt gilt wieder der Stand von vor dem Wiederherstellen (${stand}), zurückgeholt am ${am}.`
    : `Jetzt gilt der Stand vom ${stand}, wiederhergestellt am ${am}.`;
}

/** Die Sicherungen, die vorne stehen: die jüngsten; „vor dem Wiederherstellen“ nur die letzte (sie ist der Weg zurück). */
export function sichtbareSicherungen(liste: SicherungEintrag[], alle: boolean, hoechstens = 5): SicherungEintrag[] {
  let vorWieder = 0;
  const gefiltert = liste.filter(e => e.art !== "vor_wiederherstellung" || (vorWieder += 1) === 1);
  return alle ? liste : gefiltert.slice(0, hoechstens);
}

// Nach dem Neuladen soll der Hinweis sagen, welcher Stand gilt, und „Rückgängig“ anbieten. Die Seite lädt dafür neu
// (alle Ansichten lesen den neuen Stand); der Stand wartet so lange in der Sitzung des Tabs.
const MERK = "kingfisher.sicherung.wiederhergestellt";

export function merkeStand(stand: SicherungStand, speicher: Pick<Storage, "setItem"> | null = sitzung()): void {
  try { speicher?.setItem(MERK, JSON.stringify(stand)); } catch { /* ohne Speicher sagt es die Sicherungsseite */ }
}

export function holeStand(speicher: Pick<Storage, "getItem" | "removeItem"> | null = sitzung()): SicherungStand | null {
  try {
    const roh = speicher?.getItem(MERK);
    if (!roh) return null;
    speicher?.removeItem(MERK);
    const stand = JSON.parse(roh) as SicherungStand;
    return stand && typeof stand.name === "string" && typeof stand.rueckgaengig === "string" ? stand : null;
  } catch { return null; }
}

function sitzung(): Storage | null {
  try { return typeof sessionStorage === "undefined" ? null : sessionStorage; } catch { return null; }
}
