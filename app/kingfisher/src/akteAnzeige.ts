// Reine Anzeige-Hilfen für die Akte (Paket U, Befund AK1); ohne React, damit `node --test` sie prüfen kann.
// Sie ändern nichts an dem, was die Akte liefert: weder Zählung noch Entscheidungen.

type Stelle = { episode_id: string; text: string; ziel?: string | null };
type Oben = { ziel: string; zeile: { episode_id: string; text: string } | null };

/** „Vermutlich offen“ ohne die Punkte, die oben unter „Braucht dich“ schon stehen (gleiche Quelle und Stelle, oder
 * dasselbe Ziel). Dazu, wie viele deshalb fehlen, für den einen Satz „… steht oben unter Braucht dich“. */
export function offenOhneBrauchtDich<T extends Stelle>(offen: T[], braucht: Oben[] | null | undefined): { sichtbar: T[]; oben: number } {
  const stellen = new Set((braucht ?? []).flatMap(p => p.zeile ? [`${p.zeile.episode_id}\n${p.zeile.text}`] : []));
  const ziele = new Set((braucht ?? []).map(p => p.ziel));
  const sichtbar = offen.filter(e => !stellen.has(`${e.episode_id}\n${e.text}`) && !(e.ziel && ziele.has(e.ziel)));
  return { sichtbar, oben: offen.length - sichtbar.length };
}

/** Der Satz unter „Vermutlich offen“, wenn Punkte oben stehen; sonst nichts. */
export function obenGenanntSatz(anzahl: number): string | null {
  if (anzahl <= 0) return null;
  return `${anzahl === 1 ? "1 weiterer Punkt steht" : `${anzahl} weitere Punkte stehen`} oben unter „Braucht dich“.`;
}

/** Auf einen Blick als eine leise Zeile: Teile mit Mittelpunkt, eine Null zählt nicht mit. */
export function blickZeile(teile: { offen: number; frist?: string | null; termin?: string | null; abgesagt?: boolean; zuletzt?: string | null }): string | null {
  const zeile: string[] = [];
  if (teile.offen > 0) zeile.push(`${teile.offen} ${teile.offen === 1 ? "Punkt" : "Punkte"} vermutlich offen`);
  if (teile.frist) zeile.push(`nächste Frist ${teile.frist}`);
  if (teile.termin) zeile.push(`nächster Termin ${teile.termin}${teile.abgesagt ? " (abgesagt?)" : ""}`);
  if (teile.zuletzt) zeile.push(`zuletzt ${teile.zuletzt}`);
  return zeile.length ? zeile.join(" · ") : null;
}

// ── Der Stand-Satz unter dem Namen (Paket V2) ──────────────────────────────────────────────────────────────
// Ohne Modell und ohne erfundenen Inhalt: Art, Datum, Titel und Absender kommen aus der jüngsten Zeile unter
// „Stand“ (sonst aus der jüngsten Quelle im Verlauf), das Nächste aus Zahlen und Tagen, die die Akte schon liefert.

type SatzZeile = { art: string; titel: string; episode_id: string; participants: string[]; occurred_at: string | null; recorded_at: string };
type SatzVerlauf = { episode_id: string; titel: string; datum: string; quelle_art: string };
type SatzTermin = { start: string; vermutlich_abgesagt: unknown; entscheidung?: string | null };

export type StandSatz = {
  /** Vor dem Titel, etwa „Änderung am 17.9.: “. */
  vor: string;
  /** Der Titel der Quelle; die Anzeige macht ihn zum Verweis auf die Quelle. */
  titel: string;
  /** Nach dem Titel, etwa „ (Silke Vogt).“ */
  nach: string;
  episode_id: string;
  /** Woher der Satz stammt: aus „Stand“ (dann wiederholt der Abschnitt ihn nicht) oder aus dem Verlauf. */
  aus: "stand" | "verlauf";
  /** Das Nächste in einem kurzen Satz, oder nichts. */
  naechstes: string | null;
  /** Der ganze Satz als Text (Bildschirmleser, Prüfung). */
  text: string;
};

const SATZ_QUELLE: Record<string, string> = { message: "Mail", document: "Notiz", event: "Termin" };

function satzZeit(wert: string | null | undefined): Date | null {
  if (!wert) return null;
  const zeit = /^\d{4}-\d{2}-\d{2}$/.test(wert) ? new Date(`${wert}T12:00:00`) : new Date(wert);
  return Number.isNaN(zeit.getTime()) ? null : zeit;
}

/** „17.9.“, in einem anderen Jahr als heute „17.9.2025“. */
function satzTag(zeit: Date, jetzt: Date): string {
  const tag = `${zeit.getDate()}.${zeit.getMonth() + 1}.`;
  return zeit.getFullYear() === jetzt.getFullYear() ? tag : `${tag}${zeit.getFullYear()}`;
}

function nameAus(teilnehmer: string): string {
  const treffer = teilnehmer.match(/^(.*?)\s*<([^<>]+)>$/);
  return (treffer?.[1]?.trim() || treffer?.[2] || teilnehmer).trim().replace(/^(["'])(.*)\1$/, "$2");
}

/** Der Punkt nach einem Titel, außer er endet schon mit einem Satzzeichen („Rechnung bezahlt?“). */
function schluss(titel: string): string {
  return /[.!?…]$/.test(titel.trim()) ? "" : ".";
}

/** Das Nächste: „2 Punkte brauchen dich.“, sonst ein abgesagter nächster Termin, sonst der frühere von nächster Frist
 * und nächstem Termin. Nur, was die Akte ausweist; eine Null sagt nichts. */
/** Ein Satzende: Endet der Satz mit einem Tag („am 30.9.“), trägt dessen Punkt das Ende. */
function ende(satz: string): string {
  return satz.endsWith(".") ? satz : `${satz}.`;
}

export function naechstesSatz(teile: { braucht: number; termin: SatzTermin | null; frist: { datum: string } | null; jetzt: Date }): string | null {
  if (teile.braucht > 0) return `${teile.braucht} ${teile.braucht === 1 ? "Punkt braucht" : "Punkte brauchen"} dich.`;
  const termin = teile.termin ? satzZeit(teile.termin.start) : null;
  const frist = teile.frist ? satzZeit(teile.frist.datum) : null;
  if (termin && teile.termin?.vermutlich_abgesagt)
    return `Nächster Termin am ${satzTag(termin, teile.jetzt)} ${teile.termin.entscheidung === "erledigt" ? "abgesagt" : "vermutlich abgesagt"}.`;
  if (frist && (!termin || frist.getTime() <= termin.getTime())) return ende(`Nächste Frist am ${satzTag(frist, teile.jetzt)}`);
  if (termin) return ende(`Nächster Termin am ${satzTag(termin, teile.jetzt)}`);
  return null;
}

/** Ein Satz Stand für den Kopf der Akte, oder nichts, wenn die Akte nichts Datiertes hat. */
export function standSatz(eingabe: { name: string; jetzt: Date; stand: SatzZeile | null; verlauf: SatzVerlauf[]; braucht: number;
  termin: SatzTermin | null; frist: { datum: string } | null; wer?: (teilnehmer: string) => string }): StandSatz | null {
  const naechstes = naechstesSatz(eingabe);
  const wer = eingabe.wer ?? nameAus;
  const fertig = (satz: Omit<StandSatz, "text" | "naechstes">): StandSatz =>
    ({ ...satz, naechstes, text: `${satz.vor}${satz.titel}${satz.nach}${naechstes ? ` ${naechstes}` : ""}` });
  const s = eingabe.stand;
  if (s) {
    const quelle = satzZeit(s.occurred_at);
    const erfasst = satzZeit(s.recorded_at);
    const wann = quelle ? `am ${satzTag(quelle, eingabe.jetzt)}` : erfasst ? `, erfasst am ${satzTag(erfasst, eingabe.jetzt)}` : "";
    // Wer die Meldung schrieb; in der eigenen Akte dieser Person wäre der Name doppelt.
    const von = s.participants.length ? wer(s.participants[0]) : "";
    const zeigeVon = von && von.toLocaleLowerCase("de-DE") !== eingabe.name.trim().toLocaleLowerCase("de-DE");
    return fertig({ vor: `${s.art}${wann ? `${wann.startsWith(",") ? "" : " "}${wann}` : ""}: `, titel: s.titel || "ohne Titel",
      nach: zeigeVon ? ` (${von}).` : schluss(s.titel), episode_id: s.episode_id, aus: "stand" });
  }
  // Ohne Stand: die jüngste Quelle bis heute, nicht ein Termin, der noch kommt.
  const zuletzt = eingabe.verlauf.find(e => { const zeit = satzZeit(e.datum); return zeit !== null && zeit.getTime() <= eingabe.jetzt.getTime(); });
  const zeit = zuletzt ? satzZeit(zuletzt.datum) : null;
  if (!zuletzt || !zeit) return null;
  return fertig({ vor: `Zuletzt am ${satzTag(zeit, eingabe.jetzt)}: ${SATZ_QUELLE[zuletzt.quelle_art] ?? "Quelle"} `, titel: zuletzt.titel || "ohne Titel",
    nach: schluss(zuletzt.titel), episode_id: zuletzt.episode_id, aus: "verlauf" });
}

/** Termine, die oben unter „Braucht dich“ als abgesagt stehen: unter „Termine“ nur noch eine leise Zeile ohne Zitat. */
export function termineObenGenannt(braucht: Array<{ art: string; episode_id: string }> | null | undefined): Set<string> {
  return new Set((braucht ?? []).filter(p => p.art === "abgesagter_termin" && p.episode_id).map(p => p.episode_id));
}
