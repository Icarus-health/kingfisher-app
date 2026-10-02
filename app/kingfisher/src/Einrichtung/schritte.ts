// Reine Logik des Erststart-Assistenten (ohne React, testbar mit node --test): welche Schritte es gibt, welcher
// als Nächstes dran ist, wo man nach einer Pause weitermacht und was die leere Startseite als Einziges vorschlägt.
import type {EinrichtungAenderung, EinrichtungSchritt, EinrichtungStand} from "../api";

export type SchrittInfo = {id: EinrichtungSchritt; kurz: string; titel: string};

// Die Reihenfolge ist die des Assistenten. „fertig“ ist kein Arbeitsschritt, sondern das Ziel.
export const SCHRITTE: readonly SchrittInfo[] = [
  {id: "name", kurz: "Name", titel: "Wie heißt du?"},
  {id: "mail", kurz: "Mail", titel: "Deine Mail verbinden"},
  {id: "kalender", kurz: "Kalender", titel: "Deinen Kalender verbinden"},
  {id: "modell", kurz: "Dieser Rechner", titel: "Kingfisher auf diesem Rechner einrichten"},
  {id: "freigaben", kurz: "Freigaben", titel: "Was darf Kingfisher noch?"},
  {id: "autostart", kurz: "Beim Anmelden", titel: "Kingfisher beim Anmelden starten?"},
  {id: "fertig", kurz: "Fertig", titel: "Fertig – dein erstes Briefing entsteht jetzt"},
];

export type Stand = "erledigt" | "uebersprungen" | "offen";

// Die Schritte, die dieser Rechner zeigt. „Beim Anmelden“ gibt es nur, wo ein Helfer den Autostart einrichten kann
// (Mac); im Browser oder unter Docker wäre der Schritt nur der Satz „noch nicht verfügbar“ (Fremdprobe, Befund 26).
// Ohne Angabe bleibt er stehen: Auf dem Mac ist der Autostart eine Frage, keine stille Vorgabe (docs/41).
export function sichtbareSchritte(stand?: Pick<EinrichtungStand, "autostart_verfuegbar"> | null): readonly SchrittInfo[] {
  return stand?.autostart_verfuegbar === false ? SCHRITTE.filter(schritt => schritt.id !== "autostart") : SCHRITTE;
}

export const istSchritt = (wert: string | null | undefined): wert is EinrichtungSchritt =>
  SCHRITTE.some(schritt => schritt.id === wert);

// Was schon da ist, zählt als erledigt, auch wenn es nicht im Assistenten geschah: Niemand richtet zweimal ein.
export function schrittStand(id: EinrichtungSchritt, stand: EinrichtungStand): Stand {
  const gemerkt = stand.schritte[id];
  if (gemerkt === "erledigt") return "erledigt";
  if (id === "name" && stand.name.trim()) return "erledigt";
  if ((id === "mail" || id === "kalender" || id === "modell") && stand.vorhanden[id]) return "erledigt";
  return gemerkt === "uebersprungen" ? "uebersprungen" : "offen";
}

// Der erste Schritt, der weder getan noch übersprungen ist. Sind alle durch, ist es „fertig“.
export function ersterOffener(stand: EinrichtungStand): EinrichtungSchritt {
  const offen = sichtbareSchritte(stand).find(schritt => schritt.id !== "fertig" && schrittStand(schritt.id, stand) === "offen");
  return offen ? offen.id : "fertig";
}

// Wo der Assistent aufgeht: bei einem ausdrücklich gewünschten Schritt (Link „Mail verbinden“), sonst dort, wo man aufhörte.
export function startSchritt(stand: EinrichtungStand, gewuenscht?: string | null): EinrichtungSchritt {
  return istSchritt(gewuenscht) && sichtbareSchritte(stand).some(schritt => schritt.id === gewuenscht) ? gewuenscht : ersterOffener(stand);
}

export function nachbar(id: EinrichtungSchritt, richtung: 1 | -1, stand?: EinrichtungStand | null): EinrichtungSchritt {
  const liste = sichtbareSchritte(stand);
  const index = liste.findIndex(schritt => schritt.id === id);
  if (index < 0) return richtung > 0 ? "fertig" : liste[0].id;
  return liste[Math.min(liste.length - 1, Math.max(0, index + richtung))].id;
}

// „Schritt 2 von 7“: gezählt wird, was die Schrittleiste zeigt, „Fertig“ eingeschlossen. Früher stand dort
// „Schritt 1 von 6“ über sieben Punkten (Fremdprobe, Befund 27).
// Ist „Beim Anmelden“ ausgeblendet, zählt er auch nicht mit („Schritt 6 von 6“ für „Fertig“).
export function schrittZaehler(id: EinrichtungSchritt, stand?: EinrichtungStand | null) {
  const liste = sichtbareSchritte(stand);
  const index = liste.findIndex(schritt => schritt.id === id);
  return index < 0 ? null : {nummer: index + 1, gesamt: liste.length};
}

// Der getippte, noch nicht gespeicherte Name als Änderung für „Später weitermachen“; nichts, wenn er schon so gilt.
export function namensEntwurf(getippt: string, gespeichert: string): EinrichtungAenderung | null {
  const name = getippt.trim();
  return name && name !== gespeichert.trim() ? {name} : null;
}

// Ob es noch etwas gibt, das die Einrichtung weiterbringen würde (für den Hinweis oben unter „Einstellungen“).
export const offeneSchritte = (stand: EinrichtungStand) =>
  sichtbareSchritte(stand).filter(schritt => schritt.id !== "fertig" && schrittStand(schritt.id, stand) === "offen");

export type Hinweis = {schritt: EinrichtungSchritt; text: string; knopf: string};

// Die leere Startseite sagt genau einen nächsten Schritt, und zwar den wichtigsten: ohne Mail hat das Briefing nichts zu erzählen.
export function naechsterHinweis(vorhanden: EinrichtungStand["vorhanden"], laeuftEtwas: boolean): Hinweis | null {
  if (!vorhanden.mail) return {schritt: "mail", knopf: "Mail verbinden", text: "Mail verbinden, dann kann ich dir morgen früh sagen, was wichtig ist."};
  if (laeuftEtwas) return null;
  if (!vorhanden.kalender) return {schritt: "kalender", knopf: "Kalender verbinden", text: "Kalender verbinden, dann bereite ich deine Termine für dich vor."};
  if (!vorhanden.modell) return {schritt: "modell", knopf: "Auf diesem Rechner einrichten", text: "Kingfisher auf diesem Rechner einrichten, dann kann ich deine Fragen beantworten."};
  return null;
}

// Wahr, wenn der Assistent von selbst aufgehen soll: nicht abgeschlossen und noch Wesentliches offen.
export const sollZeigen = (stand: EinrichtungStand | null) => stand !== null && stand.zeigen;

// Aus der Adresse den Anbieter erkennen, damit niemand einen Server kennen muss.
export function anbieterZurAdresse<T extends {id: string; domains?: string[]}>(adresse: string, anbieter: readonly T[]): T | null {
  const at = adresse.lastIndexOf("@");
  if (at < 0) return null;
  const domain = adresse.slice(at + 1).trim().toLowerCase();
  return domain ? anbieter.find(eintrag => (eintrag.domains ?? []).includes(domain)) ?? null : null;
}
