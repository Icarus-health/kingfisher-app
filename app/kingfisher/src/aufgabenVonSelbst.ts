import type {AlleUebernehmenErgebnis, AufgabeAngelegt, AufgabePerson, AufgabenVonSelbstHeute} from "./api";
import {zitat, type HinweisDaten} from "./grundlage/hinweisOrt.ts";
import {taskHref} from "./taskWorkflow.ts";

// Aufgaben von selbst (26.10.2026, docs/66-automatik.md): Eindeutige Bitten an dich und eigene Zusagen legt Kingfisher
// selbst an, mit „Von Kingfisher angelegt · Rückgängig“; Unsichere bleiben Vorschläge, mit „Alle übernehmen“. Was und
// warum entscheidet der Sidecar (`aufgaben_von_selbst.py`); hier stehen nur die Sätze und wann sie dastehen.

const TAG = new Intl.DateTimeFormat("de-DE", {day: "numeric", month: "long"});

type MitHerkunft = {angelegt?: AufgabeAngelegt | null; person?: AufgabePerson | null};

/** „Von Kingfisher angelegt · aus der Mail von Anna Berg vom 28. September“; nur bei selbst angelegten Aufgaben. */
export function anlageZeile(task: MitHerkunft): string | null {
  const a = task.angelegt;
  if (!a || a.art !== "automatisch") return null;
  const wer = a.wer || task.person?.name || "";
  let tag = "";
  if (a.datum) {
    const datum = new Date(a.datum);
    if (!Number.isNaN(datum.getTime())) tag = ` vom ${TAG.format(datum)}`;
  }
  const mail = a.richtung === "zusage" ? `aus deiner Mail an ${wer || "die Gegenseite"}` : `aus der Mail von ${wer || "einem Absender"}`;
  return `Von Kingfisher angelegt · ${mail}${tag}`;
}

/** Der Name der Person in der leisen Zeile unter dem Titel; leer, wenn keine zugeordnet ist. */
export function personName(task: MitHerkunft): string {
  return task.person?.name || task.person?.adresse || "";
}

/** Wohin der Name führt: die Akte des Menschen (die Adresse ist sein Anker). */
export function personHref(person: AufgabePerson): string {
  return `/memory/people/${encodeURIComponent(person.adresse || person.name)}`;
}

/** Was nach dem Zurücknehmen dasteht: Es kommt nicht wieder, und „Rückgängig“ holt sie zurück. */
export const ANLAGE_ZURUECK = "Zurückgenommen. Kingfisher legt diese Aufgabe nicht wieder an.";
export const ANLAGE_WIEDER = "Die Aufgabe ist wieder da.";

/** Die Zeile auf Heute: nichts, wenn heute nichts angelegt wurde; sonst der Satz des Sidecars. */
export function heuteSatz(heute: AufgabenVonSelbstHeute | null): string | null {
  if (!heute || heute.anzahl <= 0) return null;
  return heute.satz || (heute.anzahl === 1 ? "1 Aufgabe aus der Post angelegt." : `${heute.anzahl} Aufgaben aus der Post angelegt.`);
}

/** Welche Aufgaben „Rückgängig“ auf Heute zurücknimmt: nur die noch offenen; Erledigtes gehört schon dem Nutzer. */
export function heuteZurueck(heute: AufgabenVonSelbstHeute | null): string[] {
  return (heute?.aufgaben ?? []).filter(a => a.status === "open").map(a => a.id);
}

/** Der Knopf über den Vorschlägen: ein Klick für alle, die zu sehen sind. */
export function alleKnopf(anzahl: number): string {
  return anzahl === 1 ? "Übernehmen" : `Alle ${anzahl} übernehmen`;
}

/** Die Antwort nach „Alle übernehmen“, mit „Rückgängig“ im Hinweis gleich daneben. */
export function alleHinweis(ergebnis: Pick<AlleUebernehmenErgebnis, "aufgaben" | "fehler">): string {
  const n = ergebnis.aufgaben.length;
  const teil = n === 0 ? "Nichts übernommen." : n === 1 ? "1 Aufgabe übernommen." : `${n} Aufgaben übernommen.`;
  const f = ergebnis.fehler.length;
  if (!f) return teil;
  return `${teil} ${f === 1 ? "1 Vorschlag bleibt" : `${f} Vorschläge bleiben`} zur Prüfung, die Quelle hat sich geändert.`;
}

/** Was „Rückgängig“ nach „Alle übernehmen“ sagt. */
export function gruppeZurueckText(ergebnis: {zurueckgenommen: number; geblieben: number}): string {
  const n = ergebnis.zurueckgenommen;
  const satz = n === 1 ? "1 Vorschlag steht wieder zur Prüfung." : `${n} Vorschläge stehen wieder zur Prüfung.`;
  return ergebnis.geblieben ? `${satz} ${ergebnis.geblieben} schon bearbeitete Aufgaben bleiben.` : satz;
}

/** Die leise Zeile unter einem Vorschlag: Projekt, Person, Frist, schon vorbefüllt. */
export function vorschlagMeta(projekt: string, person: AufgabePerson | null | undefined, frist: string): string {
  return [projekt, person ? (person.name || person.adresse) : "", frist].filter(Boolean).join(" · ");
}

// -- Ein Rückweg, der bleibt (Paket Z2, Z4) ----------------------------------------------------------------------------

const TAG_LANG = new Intl.DateTimeFormat("de-DE", {day: "numeric", month: "long"});
const tagVon = (wert: string | null | undefined) => {
  if (!wert) return "";
  const datum = new Date(wert);
  return Number.isNaN(datum.getTime()) ? "" : TAG_LANG.format(datum);
};

/** Die leise Zeile unter einer zurückgenommenen Aufgabe in „Erledigt → Zurückgenommen“. */
export function zurueckgenommenNeben(eintrag: {zurueck_am: string}): string {
  const tag = tagVon(eintrag.zurueck_am);
  return tag ? `Von Kingfisher angelegt, am ${tag} zurückgenommen` : "Von Kingfisher angelegt, zurückgenommen";
}

/** In der Aufgabe selbst: woher sie kam, wenn aus einem übernommenen Vorschlag (dort steht „Zurück zur Prüfung“). */
export function uebernahmeZeile(task: {angelegt?: AufgabeAngelegt | null}): string | null {
  const a = task.angelegt;
  if (!a || (a.art !== "uebernommen" && a.art !== "alle_uebernehmen")) return null;
  const tag = tagVon(a.am);
  const wie = a.art === "alle_uebernehmen" ? "Mit „Alle übernehmen“ übernommen" : "Aus einem Vorschlag übernommen";
  return tag ? `${wie} am ${tag}` : wie;
}

type Aufgabe = {id: string; title: string; project_id?: string | null};

/** Nach „Übernehmen“: die Liste bleibt, der Hinweis sagt es; Rückgängig schickt den Vorschlag zurück zur Prüfung. */
export function uebernommenHinweis(task: Aufgabe, zurPruefung: () => Promise<unknown>): HinweisDaten {
  return {text: `${zitat(task.title)} übernommen.`, rueckgaengig: zurPruefung, danach: "Der Vorschlag steht wieder zur Prüfung.",
    verweis: {text: "Ansehen", href: taskHref({id: task.id, project_id: null})}};
}

/** Nach „+ Aufgabe“: die Aufgabe steht in der Liste (nicht im Vollbild); öffnen auf Wunsch, Rückgängig verwirft sie. */
export function angelegtHinweis(task: Aufgabe, verwerfen: () => Promise<unknown>): HinweisDaten {
  return {text: `${zitat(task.title)} angelegt.`, rueckgaengig: verwerfen, danach: `${zitat(task.title)} verworfen.`,
    verweis: {text: "Öffnen", href: taskHref({id: task.id, project_id: null})}};
}
