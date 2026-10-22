// Stilprofil (Paket B5): der eigene Ton je Person und je Kreis aus gesendeten Mails. Reine Hilfen ohne React, damit
// `node --test` sie prüfen kann. Ein Vorschlag ist nie eine Regel: Erst „Übernehmen“ macht ihn dazu (sidecar: mail_style.py).

export type StilRegeln = {
  address: "default" | "du" | "sie";
  length: "default" | "short" | "detailed";
  emoji: "default" | "yes" | "no";
  /** Die Grußformel wörtlich; leer heißt keine Regel. */
  gruss: string;
  anrede_form: "default" | "vorname" | "nachname" | "hallo" | "liebe" | "ohne";
  sprache: "default" | "de" | "en";
};

export type StilVorschlag = {
  rules: StilRegeln;
  evidence_ids: string[];
  /** Wie viele gesendete Mails und wie viele bestätigte Lernbelege den Vorschlag tragen. */
  gesendet: number;
  belege: number;
  /** Nur beim Kreis: an wie viele Personen die Mails gingen. */
  personen?: number;
};

export type StilBeleg = { id: string; title: string; occurred_at: string; text: string };

export type StilProfil = { id: string; rules: StilRegeln; evidence_ids?: string[] };

export type KreisTonStand = {
  kreis: "innerer_kreis" | "kollegen" | "kontakte";
  kreis_text: string;
  personen: number;
  profile: StilProfil | null;
  proposal: StilVorschlag | null;
  abgelehnt: boolean;
  gesendete: StilBeleg[];
};

export const LEERE_REGELN: StilRegeln = { address: "default", length: "default", emoji: "default", gruss: "", anrede_form: "default", sprache: "default" };

export const REGEL_WERTE = {
  address: { default: "Standard", du: "Du", sie: "Sie" },
  length: { default: "Standard", short: "Kurz", detailed: "Ausführlich" },
  emoji: { default: "Standard", yes: "Ja", no: "Nein" },
  anrede_form: { default: "Standard", vorname: "Hallo und Vorname", nachname: "Frau/Herr und Nachname", hallo: "Nur Hallo", liebe: "Liebe/Lieber und Name", ohne: "Ohne Anrede" },
  sprache: { default: "Standard", de: "Deutsch", en: "Englisch" },
} as const;

/** Die Regeln als kurze Teile für einen Satz: „Du, kurz, ohne Emoji, Gruß „Viele Grüße““. Nur, was gesetzt ist. */
export function regelTeile(rules: Partial<StilRegeln>): string[] {
  const teile: string[] = [];
  if (rules.address === "du") teile.push("Du");
  if (rules.address === "sie") teile.push("Sie");
  if (rules.anrede_form === "vorname") teile.push("Anrede mit Vornamen");
  if (rules.anrede_form === "nachname") teile.push("Anrede mit Nachnamen");
  if (rules.anrede_form === "hallo") teile.push("nur „Hallo“");
  if (rules.anrede_form === "liebe") teile.push("Anrede „Liebe/Lieber“");
  if (rules.anrede_form === "ohne") teile.push("ohne Anrede");
  if (rules.length === "short") teile.push("kurz");
  if (rules.length === "detailed") teile.push("ausführlich");
  if (rules.emoji === "no") teile.push("ohne Emoji");
  if (rules.emoji === "yes") teile.push("mit Emoji");
  if (rules.gruss) teile.push(`Gruß „${rules.gruss}“`);
  if (rules.sprache === "en") teile.push("auf Englisch");
  if (rules.sprache === "de") teile.push("auf Deutsch");
  return teile;
}

function mails(n: number): string {
  return n === 1 ? "einer gesendeten Mail" : `${n} gesendeten Mails`;
}

function belege(n: number): string {
  return n === 1 ? "einem Lernbeleg" : `${n} Lernbelegen`;
}

/** Woraus der Vorschlag stammt, in Klammern: „(aus 7 gesendeten Mails)“, „(aus 5 gesendeten Mails und 2 Lernbelegen)“. */
export function herkunft(vorschlag: StilVorschlag): string {
  const teile: string[] = [];
  if (vorschlag.gesendet > 0) {
    teile.push(mails(vorschlag.gesendet) + (vorschlag.personen && vorschlag.personen > 1 ? ` an ${vorschlag.personen} Personen` : ""));
  }
  if (vorschlag.belege > 0) teile.push(belege(vorschlag.belege));
  return teile.length ? `(aus ${teile.join(" und ")})` : "";
}

/** Die Zeile über den Knöpfen: „Dein Ton an anna@…: Du, kurz, ohne Emoji, Gruß „Viele Grüße“ (aus 7 gesendeten Mails).“ */
export function tonSatz(wen: string, vorschlag: StilVorschlag): string {
  const teile = regelTeile(vorschlag.rules);
  return `Dein Ton an ${wen}: ${teile.join(", ")} ${herkunft(vorschlag)}.`.replace(" .", ".");
}

/** Die Zeile zum bestätigten Stil: „Bestätigt: Du, kurz.“ */
export function bestaetigtSatz(rules: Partial<StilRegeln>): string {
  const teile = regelTeile(rules);
  return teile.length ? `Bestätigt: ${teile.join(", ")}.` : "Bestätigt, ohne eigene Regel.";
}

/** Was die Karte „Ton je Kreis“ zu einem Kreis sagt: bestätigt, vorgeschlagen, oder warum nichts. */
export function kreisTonSatz(stand: KreisTonStand): string {
  if (stand.profile) return `${stand.kreis_text}: ${bestaetigtSatz(stand.profile.rules)}`;
  if (stand.proposal) return tonSatz(stand.kreis_text.toLowerCase() === "kollegen" ? "Kollegen" : `den ${stand.kreis_text}`, stand.proposal);
  if (stand.personen === 0) return `${stand.kreis_text}: Noch niemand bestätigt zugeordnet; Kreise legst du in der Akte einer Person fest.`;
  if (stand.abgelehnt) return `${stand.kreis_text}: Vorschlag nicht übernommen. Kommt eine neue gesendete Mail dazu, fragt Kingfisher wieder.`;
  return `${stand.kreis_text}: Noch kein einheitlicher Ton in den gesendeten Mails an die ${stand.personen === 1 ? "Person" : `${stand.personen} Personen`} dieses Kreises.`;
}

/** Der Hinweis dort, wo der Entwurf entsteht; nichts, wenn der Kontaktstil bestätigt ist oder nichts vorliegt. */
export function stilHinweis(stil: { bestaetigt: boolean; gesendet: number } | undefined): string | null {
  if (!stil || stil.bestaetigt || stil.gesendet <= 0) return null;
  return `Ton aus ${mails(stil.gesendet)} vorgeschlagen, noch nicht übernommen.`;
}

/** Die Überschrift der Belege: „7 gesendete Mails ansehen“. */
export function belegeTitel(anzahl: number): string {
  return anzahl === 1 ? "Die gesendete Mail ansehen" : `${anzahl} gesendete Mails ansehen`;
}
