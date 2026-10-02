// Kleine reine Hilfen für den Kreis je Person und die Art einer Akte (M4, docs/49-kreis-und-privat.md); ohne React,
// damit `node --test` sie prüfen kann. Ein Vorschlag ist nie ein Fakt: Erst der Klick eines Menschen legt ihn fest.

export type KreisArt = "innerer_kreis" | "kollegen" | "kontakte";
export type KreisWahl = { kreis: KreisArt; text: string; wirkung: string };
export type KreisStand = {
  sache: string; kreis: KreisArt | "unbestimmt"; kreis_text: string; bestaetigt: boolean; bestaetigt_am: number | null;
  vorschlag: { kreis: KreisArt; kreis_text: string; begruendung: string };
  neuer_vorschlag: boolean; wahlen: KreisWahl[];
  /** Es gibt nichts, worauf ein Vorschlag beruhen könnte (keine Mails, keine gemeinsamen Termine). */
  ohne_vorschlag?: boolean;
};
export type KreisUebersicht = {
  bestaetigt: number; offen: number; geaendert: number; je_kreis: Record<KreisArt, number>;
  offen_je_kreis?: { innerer_kreis: number; kollegen: number };
  zaehlt_noch?: boolean;
  letzte_sammlung?: { sammlung: number; anzahl: number } | null;
  vorschlaege: Array<{ sache: string; name: string; kreis: KreisArt; kreis_text: string; begruendung: string }>;
};
export type AktenArt = "haushalt" | "familie" | "gesundheit" | "vertraege" | "keine";
export type ArtStand = {
  sache: string; art: AktenArt | null; art_text: string; bestaetigt: boolean; neuer_vorschlag: boolean;
  vorschlag: { art: AktenArt | null; art_text: string; begruendung: string };
  wahlen: Array<{ art: AktenArt; text: string }>;
};

/** Der Satz über den drei Knöpfen: was gilt und was Kingfisher vorschlägt. */
export function kreisSatz(stand: KreisStand): string {
  if (!stand.bestaetigt && stand.ohne_vorschlag) return "Noch kein Vorschlag; du kannst den Kreis selbst festlegen.";
  if (!stand.bestaetigt) return `Vorschlag: ${stand.vorschlag.kreis_text}. Ein Klick bestätigt ihn, oder du wählst einen anderen Kreis.`;
  if (stand.neuer_vorschlag) return `Bestätigt: ${stand.kreis_text}. Nach dem, was seitdem dazukam, würde Kingfisher „${stand.vorschlag.kreis_text}“ vorschlagen. Es bleibt bei deiner Wahl, bis du sie änderst.`;
  return `Bestätigt: ${stand.kreis_text}.`;
}

/** Was nach dem Klick zu sagen ist: der gewählte Kreis und was er bewirkt. */
export function kreisGespeichert(stand: KreisStand): string {
  const wahl = stand.wahlen.find(w => w.kreis === stand.kreis);
  return wahl ? `Gespeichert: ${wahl.text}. ${wahl.wirkung}` : "Zurückgenommen. Der Kreis ist wieder offen, nichts richtet sich mehr nach ihm.";
}

/** Der Satz unter „Kingfisher und du“: wie viele bestätigt, wie viele Vorschläge offen. */
export function uebersichtSatz(u: KreisUebersicht): string {
  const bestaetigt = u.bestaetigt === 0 ? "Noch für niemanden bestätigt." : u.bestaetigt === 1 ? "Für eine Person bestätigt." : `Für ${u.bestaetigt} Personen bestätigt.`;
  const innen = u.offen_je_kreis?.innerer_kreis ?? 0;
  const kollegen = u.offen_je_kreis?.kollegen ?? u.offen - innen;
  const teile = [innen ? (innen === 1 ? "einer für den inneren Kreis" : `${innen} für den inneren Kreis`) : "",
    kollegen ? `${kollegen} für Kollegen` : ""].filter(Boolean);
  const offen = u.offen === 0 ? " Kein Vorschlag offen." : ` Offen ${u.offen === 1 ? "ist ein Vorschlag" : `sind ${u.offen} Vorschläge`}: ${teile.join(", ")}.`;
  const geaendert = u.geaendert === 1 ? " Bei einer Person würde Kingfisher heute anders vorschlagen." : u.geaendert > 1 ? ` Bei ${u.geaendert} Personen würde Kingfisher heute anders vorschlagen.` : "";
  // Solange die Akten im Hintergrund abgeglichen werden, ist die Zahl vorläufig; das steht dann dabei.
  const vorlaeufig = u.zaehlt_noch ? " Kingfisher sortiert noch; die Zahlen werden gleich genauer." : "";
  return `${bestaetigt}${offen}${geaendert}${vorlaeufig}`;
}

/** Der Satz der Karte „Art der Akte“, oder null, wenn es nichts zu sagen gibt (berufliche Akte ohne Vorschlag). */
export function artSatz(stand: ArtStand): string | null {
  if (stand.bestaetigt) {
    if (stand.neuer_vorschlag && stand.vorschlag.art) return `Bestätigt: ${stand.art_text}. Kingfisher würde heute „${stand.vorschlag.art_text}“ vorschlagen; es bleibt bei deiner Wahl.`;
    return `Bestätigt: ${stand.art_text}.`;
  }
  if (!stand.vorschlag.art) return null;
  return `Vorschlag: ${stand.vorschlag.art_text}. Ein Klick bestätigt ihn.`;
}

/** Der Pfad zur Akte einer Sache (dieselbe Seite wie „Beteiligte“ in der Akte). */
export function aktePfad(sache: string): string {
  return `/memory/akte/${encodeURIComponent(sache)}`;
}

/** Die Rückfrage vor der Sammelbestätigung, in einem Satz. Nur für Kollegen, nie für den inneren Kreis. */
export function sammelFrage(anzahl: number): string {
  return anzahl === 1 ? "Eine Person als Kollegen festlegen?" : `${anzahl} Personen als Kollegen festlegen?`;
}

/** Die Beschriftung des Knopfs, der die Rückfrage öffnet. */
export function sammelKnopf(anzahl: number): string {
  return anzahl === 1 ? "Als Kollegen festlegen" : `Alle ${anzahl} als Kollegen festlegen`;
}

/** Der Satz zur letzten Sammlung, die noch steht (mit „Liste zurücknehmen“ daneben). */
export function sammlungSatz(s: { anzahl: number }): string {
  return s.anzahl === 1 ? "Zuletzt eine Person gesammelt als Kollegen festgelegt." : `Zuletzt ${s.anzahl} Personen gesammelt als Kollegen festgelegt.`;
}

/** Wie viele offene Vorschläge „Kollegen“ es gibt (alle, nicht nur die angezeigten). */
export function offeneKollegen(u: KreisUebersicht): number {
  return u.offen_je_kreis?.kollegen ?? u.vorschlaege.filter(v => v.kreis === "kollegen").length;
}

/** Welche Sache die Karte „Kreis“ in einem Personenprofil meint: die Adresse, sonst der Name (`person:n:…`). Nur, wenn die
 * Person eindeutig ist; eine offene Nennung (mehrere mögliche Adressen) bekommt keinen Kreis (Fremdprobe 2, Befund 19). */
export function kreisSache(person: { id?: string; adressen?: string[]; offen_mit?: string[] }): string | null {
  if ((person.offen_mit?.length ?? 0) > 0) return null;
  const adresse = person.adressen?.[0];
  if (adresse) return `person:a:${adresse.toLowerCase()}`;
  return person.id && /^[an]:./.test(person.id) ? `person:${person.id}` : null;
}

/** Die Zeile unter dem Namen in der Akte: wie viele Kontakte belegt sind. Nur Quellen, an denen die Person selbst
 * beteiligt war, zählen; wer nur im Gespräch mit Kingfisher vorkam, hat noch keinen (Fremdprobe 2, Befund 21). */
export function kontakteText(person: { kontakte?: number; episoden_anzahl: number }): string {
  const anzahl = person.kontakte ?? person.episoden_anzahl;
  if (anzahl === 0) return "Noch kein Kontakt belegt; bisher nur in deinen Gesprächen mit Kingfisher erwähnt";
  return anzahl === 1 ? "1 belegter Kontakt" : `${anzahl} belegte Kontakte`;
}
