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
