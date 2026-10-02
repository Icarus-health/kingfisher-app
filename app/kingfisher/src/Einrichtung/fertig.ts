// Reine Logik der Fertig-Seite (ohne React, testbar mit node --test): was sie über die Quellen sagen darf und
// welche Automatik sie am Ende einmal anbietet (Fremdprobe, Befunde 5 und 17).
import type {MailIntakeStatus, MemoryAutomation, PostfachErreichbar} from "../api";
import {deriveIntakeProgress} from "../mailIntakeProgress.ts";

export type FertigLage = {
  mail: boolean;
  kalender: boolean;
  /** Postfächer, die gerade nicht antworten; `null`, solange noch geprüft wird. */
  stumm: PostfachErreichbar[] | null;
  /** Verbundene Konten, deren Mails noch nicht eingelesen werden. */
  nichtEingelesen: number;
};

/** Was unter „Kingfisher lernt gerade“ steht, wenn nichts läuft. „Bereit“ nur, wenn es stimmt. */
export function fertigLeerText({mail, kalender, stumm, nichtEingelesen}: FertigLage): string | undefined {
  if (!mail && !kalender) return undefined;
  if (mail && stumm === null) return "Kingfisher sieht nach, ob dein Postfach antwortet …";
  if (mail && stumm && stumm.length) return "Dein Briefing kommt ohne Mails aus, bis dein Postfach wieder antwortet.";
  if (mail && nichtEingelesen) return "Deine Mails sind noch nicht eingelesen; das Briefing wartet darauf.";
  return "Gerade läuft nichts mehr im Hintergrund. Dein Briefing ist bereit.";
}

/** Die Überschrift über den Postfächern, die nicht antworten. */
export const stummTitel = (stumm: readonly PostfachErreichbar[]) =>
  stumm.length === 1 ? "Dein Postfach antwortet nicht" : "Deine Postfächer antworten nicht";

export type Angebote = {einlesen: string[]; sortieren: boolean; sortierenSpaeter: boolean};

/** Zustände, in denen das Sortieren vorgemerkt werden kann: Das lokale Modell fehlt noch (es lädt) oder antwortet noch nicht. */
const VORMERKBAR = new Set(["model_missing", "local_model_unavailable"]);

/**
 * Was die Fertig-Seite einmal anbietet, vorausgewählt: Mails verbundener Konten einlesen (nur Postfächer, die
 * antworten) und die Quellen lokal sortieren lassen. Lädt das lokale Modell noch, wird das Sortieren vorgemerkt
 * (`sortierenSpaeter`) und beginnt, sobald es bereit ist: Die Seite verspricht die Einordnung, also ist sie die Vorgabe
 * (Fremdprobe 3, Befund 3). Ein Modell im Internet wird nie vorgemerkt. Sortieren erzeugt nur Vorschläge; zur Tatsache
 * wird etwas erst mit einem Ja (docs/10-verdichtung.md).
 */
export function automatikAngebote(intake: MailIntakeStatus | null, automatik: MemoryAutomation | null,
  stumm: readonly PostfachErreichbar[] | null): Angebote {
  const schweigt = new Set((stumm ?? []).map(konto => konto.account_id));
  const einlesen = stumm === null ? [] : (intake?.accounts ?? [])
    .filter(konto => konto.connected && !konto.started && !schweigt.has(konto.account_id))
    .map(konto => konto.account_id);
  const offen = automatik !== null && !automatik.requested;
  const spaeter = offen && VORMERKBAR.has(automatik.state);
  return {einlesen, sortieren: offen && (automatik.state === "paused" || spaeter), sortierenSpaeter: spaeter};
}

/** Ob die Fertig-Seite versprechen darf, dass Kingfisher einordnet: Es läuft schon, oder es wird gleich eingeschaltet. */
export const ordnetEin = (automatik: MemoryAutomation | null, angebote: Angebote, sortierenAn: boolean) =>
  Boolean(automatik?.requested || (angebote.sortieren && sortierenAn));

/**
 * Was die Fertig-Seite unter „Was im Hintergrund passiert“ zuerst sagt: nur, was wirklich verbunden ist (Fremdprobe 2,
 * Befund 8). Ohne Kalender keine „Termine“, ohne Mail keine „Mails“, ohne beides kein Satz.
 */
export function liestSatz({mail, kalender}: {mail: boolean; kalender: boolean}): string | null {
  const was = mail && kalender ? "deine Mails und Termine" : mail ? "deine Mails" : kalender ? "deine Termine" : "";
  return was ? `Kingfisher liest ${was}. Das bleibt auf diesem Rechner.` : null;
}

/** Pausieren ist Alltag: Es steht auf Heute in „Kingfisher lernt gerade“, nicht unter „Für Techniker“ (Fremdprobe 3, Befund 5). */
export const PAUSIEREN_AUF_HEUTE = "Anhalten kannst du beides jederzeit auf Heute mit „Pausieren“.";

export type Zahl = {titel: string; wert: number | null};

/**
 * Die Zahlen unter „Schon da“, nur wenn sie stimmen (Fremdprobe 3, Befund 6). Früher stand „Mails 0 · Termine 0“, obwohl
 * der Termin schon aufgenommen war: Die Termine wurden gezählt, bevor der Abgleich fertig war, und „Mails“ zählte, was
 * gelesen ist, ohne es zu sagen. Jetzt: Termine erst nach dem Abgleich (bis dahin `null`, also „…“), Mails nur, wenn das
 * Einlesen läuft, und die Beschriftung sagt, was gezählt ist.
 */
export function schonDaZahlen({mail, kalender, intake, termine}: {
  mail: boolean; kalender: boolean; intake: MailIntakeStatus | null;
  /** Termine im Gedächtnis nach dem ersten Abgleich auf dieser Seite; `null`, solange er läuft. */
  termine: number | null;
}): Zahl[] {
  const zahlen: Zahl[] = [];
  const gestartet = (intake?.accounts ?? []).filter(konto => konto.connected && konto.started);
  if (mail && gestartet.length) {
    zahlen.push({titel: "Mails gelesen", wert: gestartet.reduce((summe, konto) => summe + deriveIntakeProgress(konto).sources, 0)});
  }
  if (kalender) zahlen.push({titel: "Termine aufgenommen", wert: termine});
  return zahlen;
}
