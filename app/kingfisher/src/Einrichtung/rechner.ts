// Reine Logik des Schritts „Dieser Rechner“ (ohne React, testbar mit node --test). Fremdprobe, Befunde 10 und 11:
// vorne steht, was Kingfisher auf diesem Rechner kann, wie groß das Laden ist und wie lange es dauert, und ein Knopf.
// Modellnamen, „Messlatte“ und Speicher je Tageszeit stehen nur im Aufklapper „Für Techniker“.
import type {ModelEntry, ModelOrchestra, ModelPullState, ModelRecommendation, ModelRecommendationRow, ModellLaden} from "../api";
import {pullPercent} from "../modelSetup.ts";

export type Faehigkeit = {id: "antworten" | "einordnen" | "pruefen"; titel: string; satz: string; rollen: string[]};

export const FAEHIGKEITEN: readonly Faehigkeit[] = [
  {id: "antworten", titel: "Deine Fragen beantworten", rollen: ["frage", "antwort", "einbettung"],
    satz: "Kurz und mit Beleg aus deinen Mails, Terminen und Unterlagen."},
  {id: "einordnen", titel: "Im Hintergrund einordnen", rollen: ["hintergrund"],
    satz: "Wer wer ist, was zu welchem Vorhaben gehört und welche Fristen anstehen."},
  {id: "pruefen", titel: "Antworten prüfen", rollen: ["pruefung"],
    satz: "Jeden Satz einer Antwort noch einmal gegen seine Quelle halten."},
];

/** Was im Assistenten gerade mit einer Aufgabe passiert (nur in dieser Sitzung). */
export type Lauf = {phase: ModelPullState["phase"]; prozent: number | null; nichtBestanden: boolean; satz: string; modell: string};

export function laufAus(stand: ModelPullState): Lauf {
  const nichtBestanden = stand.phase === "fehler" && stand.fehler?.art === "pruefung";
  const satz = stand.phase === "fehler" ? (nichtBestanden
    ? "Das geladene Modell hat die Prüfung nicht bestanden und wird nicht benutzt."
    : `${stand.fehler?.grund ?? "Das Laden hat nicht geklappt."} ${stand.fehler?.naechster_schritt ?? ""}`.trim()) : "";
  return {phase: stand.phase, prozent: pullPercent(stand), nichtBestanden, satz, modell: stand.modell};
}

export type FaehigkeitStand = {art: "bereit" | "laedt" | "offen" | "nicht_bestanden" | "fehler"; text: string};

/** Ein Wort zum Stand einer Fähigkeit, passend zu dem, was darunter steht (kein „Fehlt“ neben „geladen“). */
export function faehigkeitStand(faehigkeit: Faehigkeit, zeilen: readonly ModelRecommendationRow[], laeufe: Readonly<Record<string, Lauf>>): FaehigkeitStand {
  const eigene = faehigkeit.rollen.map(rolle => ({zeile: zeilen.find(z => z.rolle === rolle), lauf: laeufe[rolle]}));
  const laufend = eigene.find(e => e.lauf && ["wartet", "laedt", "prueft"].includes(e.lauf.phase));
  if (laufend?.lauf) return {art: "laedt", text: laufend.lauf.phase === "prueft" ? "Wird geprüft …"
    : laufend.lauf.prozent === null ? "Wird geladen …" : `Wird geladen … ${laufend.lauf.prozent} %`};
  if (eigene.some(e => e.lauf?.nichtBestanden)) return {art: "nicht_bestanden", text: "Prüfung nicht bestanden"};
  if (eigene.some(e => e.lauf?.phase === "fehler")) return {art: "fehler", text: "Nicht geladen"};
  const bereit = eigene.every(e => e.lauf?.phase === "fertig" || e.zeile?.status === "eingerichtet");
  return bereit ? {art: "bereit", text: "Bereit"} : {art: "offen", text: "Noch nicht eingerichtet"};
}

const gb = (zahl: number) => (Math.round(zahl * 10) / 10).toLocaleString("de-DE");

/** Ein Satz über den Rechner, ohne Chip, ohne Fachwort; ermittelt hat ihn das Programm, nicht der Mensch. */
export function ausstattungSatz(geraet: ModelRecommendation["geraet"]): string {
  const speicher = geraet.arbeitsspeicher_gb;
  if (!geraet.bekannt || speicher === null) return "Kingfisher wählt eine kleine Ausstattung, die auf jedem Rechner läuft.";
  if (geraet.quelle === "untergrenze") return `Kingfisher sieht hier mindestens ${gb(speicher)} GB Arbeitsspeicher und wählt danach.`;
  return `Dieser Rechner hat ${gb(speicher)} GB Arbeitsspeicher; danach wählt Kingfisher aus.`;
}

/**
 * Größe und Dauer des Ladens in einem Satz; leer, wenn nichts zu laden ist (Fremdprobe 2, Befund 6). Die Zahl kommt aus
 * einer Quelle, `orchester.festplatte_noch_gb` (`model_recommendation.orchester_bedarf`), wie die Größe des Laufs selbst.
 * Liegt ein Teil schon auf dem Rechner (etwa nach einem Fehlschlag), sagt der Satz das, statt still eine kleinere Zahl
 * zu nennen.
 */
export function ladeSatz(orchester: Pick<ModelOrchestra, "festplatte_gb" | "festplatte_noch_gb" | "festplatte_frei_gb">): string {
  const noch = orchester.festplatte_noch_gb;
  if (!(noch > 0)) return "";
  const von = Math.max(1, Math.ceil(noch * 1024 / 62.5 / 60));
  const bis = Math.max(2, Math.ceil(noch * 1024 / 12.5 / 60));
  const teil = orchester.festplatte_gb - noch >= 0.1
    ? `Noch zu laden: etwa ${gb(noch)} von ${gb(orchester.festplatte_gb)} GB; der Rest liegt schon auf diesem Rechner. Je nach Internetleitung dauert das ${von} bis ${bis} Minuten.`
    : `Einmal laden: etwa ${gb(noch)} GB, je nach Internetleitung ${von} bis ${bis} Minuten.`;
  const platz = typeof orchester.festplatte_frei_gb === "number" ? ` Frei sind etwa ${gb(orchester.festplatte_frei_gb)} GB.` : "";
  return `${teil} Das Laden läuft im Hintergrund weiter; du machst gleich mit der Einrichtung weiter.${platz}`;
}

/** Der Stand je Aufgabe aus dem Lauf im Hintergrund (für die Fähigkeiten und „Anderes Modell nehmen“). */
export function laeufeAus(laden: ModellLaden | null): Record<string, Lauf> {
  return Object.fromEntries((laden?.auftraege ?? []).map(auftrag => [auftrag.rolle, laufAus(auftrag)]));
}

/** Während des Ladens: ein Satz mit Prozent und dass man weitergehen kann. */
export const ladenLaeuftSatz = (laden: Pick<ModellLaden, "prozent">) =>
  `Kingfisher lädt sein Sprachmodell: ${laden.prozent} %. Du kannst schon weitermachen; das Laden läuft im Hintergrund weiter, den Stand siehst du auf Heute.`;

/**
 * Was nach dem Lauf oben steht, genau einmal (Befund 7): alles, teilweise oder nichts eingerichtet. Nie „Fast alles“,
 * wenn alles fehlschlug. `nochmal`: der Knopf „Noch einmal versuchen“.
 */
export function abschluss(laden: ModellLaden | null): {ok: boolean; text: string; nochmal: boolean} | null {
  if (!laden || laden.laeuft || !laden.auftraege.length) return null;
  const gesamt = laden.auftraege.length;
  const gut = laden.eingerichtet.length;
  if (!laden.fehlgeschlagen.length) return {ok: true, text: "Alles eingerichtet und geprüft.", nochmal: false};
  if (gut === 0) return {ok: false, text: "Nichts ist eingerichtet: Keine Aufgabe hat Laden und Prüfung bestanden. Was du tun kannst, steht darunter.", nochmal: true};
  return {ok: false, text: `Teilweise eingerichtet: ${gut} von ${gesamt} Aufgaben. Was fehlt und was du tun kannst, steht darunter.`, nochmal: false};
}

/** Die Probleme je Fähigkeit, jedes nur einmal (früher stand derselbe Satz für Frage, Antwort und Einbettung dreimal). */
export function probleme(zeilen: readonly ModelRecommendationRow[], laeufe: Readonly<Record<string, Lauf>>) {
  const gesehen = new Set<string>();
  const liste: {titel: string; zeile: ModelRecommendationRow; lauf: Lauf}[] = [];
  for (const zeile of zeilen) {
    const lauf = laeufe[zeile.rolle];
    if (!lauf || lauf.phase !== "fehler") continue;
    const titel = FAEHIGKEITEN.find(f => f.rollen.includes(zeile.rolle))?.titel ?? zeile.titel;
    const schluessel = `${titel}\u0000${lauf.satz}`;
    if (gesehen.has(schluessel)) continue;
    gesehen.add(schluessel);
    liste.push({titel, zeile, lauf});
  }
  return liste;
}

/** Das nächste Modell, das „Anderes Modell nehmen“ versucht; `null`, wenn es keines mehr gibt. */
export function naechsteWahl(zeile: ModelRecommendationRow | undefined, versucht: readonly string[]): ModelEntry | null {
  return zeile?.ausweich?.find(eintrag => !versucht.includes(eintrag.name)) ?? null;
}

/** Was „Laden und einrichten“ nacheinander lädt: alle Aufgaben, die noch nicht eingerichtet sind. */
export const offeneRollen = (zeilen: readonly ModelRecommendationRow[]) => zeilen.filter(z => z.status !== "eingerichtet").map(z => z.rolle);

/** Wo man Ollama bekommt (dieselbe Seite nennt der Starter). */
export const OLLAMA_DOWNLOAD = "https://ollama.com/download";

/**
 * Was „Dieser Rechner“ sagt, wenn Ollama nicht antwortet (README, Fremdprobe 3, S3): was fehlt, was zu tun ist, und was
 * ohne Ollama trotzdem geht. Vorher stand nur „antwortet gerade nicht“, und wer es nie installiert hatte, wusste nicht weiter.
 */
export const OHNE_OLLAMA = {
  satz: "Kingfisher denkt mit dem kostenlosen Programm Ollama, und das antwortet auf diesem Rechner gerade nicht. Ist es installiert, starte es; sonst lade es hier:",
  link: "Ollama laden",
  ohne: "Ohne Ollama liest Kingfisher trotzdem deine Mails und Termine und zeigt dein Briefing; Fragen beantworten und im Hintergrund einordnen kann es erst damit.",
} as const;
