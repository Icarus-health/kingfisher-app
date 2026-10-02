// Die Gliederung der Einstellungen in zwei Ebenen (docs/47-einstellungen.md). Reine Daten und Logik, ohne React, damit
// `node --test` sie prüfen kann. Vorne steht, was ein Mensch tun will; hinten, was nur ein Techniker einstellen würde.
// Alle Texte der vorderen Ebene stehen hier oder in den Dateien aus VORDERE_DATEIEN; der Wortlistentest
// (tests/einstellungen-gliederung.test.mjs) sucht darin nach Fachwörtern. `{Rechner}` wird „Mac“ oder „Rechner“, je nachdem,
// wo Kingfisher läuft (`fuerSystem` in system.ts, Fremdprobe Befund 18).

export type Bereich = "zugaenge" | "darf" | "ich" | "sicherung" | "technik";

export const BEREICHE: ReadonlyArray<{ id: Bereich; label: string; satz: string; hinten?: boolean }> = [
  { id: "zugaenge", label: "Zugänge",
    satz: "Woher Kingfisher seine Informationen holt: deine Post, deine Kalender und deine Ordner. Du verbindest, was du willst, und trennst es jederzeit wieder." },
  { id: "darf", label: "Was Kingfisher darf",
    satz: "Fünf Schalter, alle aus, bis du sie einschaltest. Bei jedem steht, was dabei deinen Rechner verlässt." },
  { id: "ich", label: "Kingfisher und du",
    satz: "Wie Kingfisher dich nennt, von wo du meistens losfährst, wie es dir antworten soll und welche Fassung läuft." },
  { id: "sicherung", label: "Sicherung",
    satz: "Sichere alles, was Kingfisher über dich weiß, verschlüsselt auf diesem {Rechner}, und stelle es bei Bedarf wieder her." },
  { id: "technik", label: "Für Techniker", hinten: true,
    satz: "Hier muss nichts geändert werden. Kingfisher arbeitet auch so, mit den Vorgaben. Die Abschnitte sind für alle, die wissen wollen, wie es innen läuft." },
];

/** Die fünf Schalter unter „Was Kingfisher darf“: je ein Satz, was dabei den Rechner verlässt. */
export const SCHALTER = {
  wetter: { titel: "Morgens das Wetter holen",
    verlaesst: "Es verlässt nur der Name deines Ortes den Rechner, an den Wetterdienst Open-Meteo. Termine, Namen und Adressen bleiben bei dir." },
  welt: { titel: "Eine Meldung aus der Welt zeigen",
    verlaesst: "Es verlässt nichts den Rechner, außer dass Kingfisher die Nachrichtenseiten abruft, die du auswählst. Was in deinen Akten steht, wird nicht gesendet." },
  wegezeit: { titel: "Wegezeit berechnen",
    verlaesst: "Es verlassen die Adresse des Termins und dein Startort den Rechner, an Apple Karten auf dem Mac oder an einen Routenplaner, den du selbst einrichtest." },
  autostart: { titel: "Beim Anmelden starten",
    verlaesst: "Es verlässt nichts den Rechner. Kingfisher öffnet sich im Hintergrund, sobald du dich am {Rechner} anmeldest." },
  cloud: { titel: "Cloud für Fragen und Antworten nutzen",
    verlaesst: "Es verlassen deine Fragen und die dazu gefundenen Textstellen den Rechner, an den Cloudanbieter, den du wählst. Aus: alles bleibt auf diesem Rechner.",
    zustimmung: "Deine Fragen und die dazu gefundenen Textstellen gehen an den Cloudanbieter, den du gewählt hast. Ich willige ein." },
} as const;

export const ICH = {
  name: { frage: "Wie soll Kingfisher dich nennen?", hilfe: "Der Name steht nur im Gruß des Briefings und bleibt auf diesem Rechner." },
  startort: { frage: "Von wo startest du meistens?",
    hilfe: "Straße und Ort. Kingfisher braucht das für die Wegezeit und schlägt daraus den Ort für das Wetter vor. Gesendet wird es nur, wenn du „Wegezeit berechnen“ einschaltest." },
  zeitzone: { hilfe: "Nach dieser Zeitzone liest Kingfisher alle Uhrzeiten." },
  kreis: { titel: "Kreis",
    text: "In jeder Akte einer Person steht die Karte „Kreis“: innerer Kreis, Kollegen oder Kontakte. Wo Kingfisher genug Mails oder gemeinsame Termine kennt, schlägt es einen Kreis vor, und du bestätigst ihn mit einem Klick; sonst legst du ihn dort selbst fest. Danach richtet sich, wie viel Kingfisher dir ungefragt über die Person sagt. Es verlässt nichts deinen Rechner." },
  antwort: { titel: "Wie Kingfisher dir antwortet", hilfe: "Kurz oder ausführlich, Du oder Sie, mit oder ohne Emojis." },
} as const;

export const ZUGAENGE = {
  postfaecher: { titel: "Postfächer", leer: "Noch kein Postfach verbunden." },
  kalender: { titel: "Kalender", leer: "Noch kein Kalender verbunden." },
  ordner: { titel: "Ordner und Dateien", satz: "Meeting-Mitschriften und Dokumente, die Kingfisher lesen soll. Es liest nur Ordner, die du hier ausgewählt hast." },
} as const;

/** Die Abschnitte hinter „Für Techniker“, in der Reihenfolge, in der sie eingeklappt erscheinen. */
export const TECHNIK: ReadonlyArray<{ id: string; titel: string; satz: string }> = [
  { id: "modelle", titel: "Modelle je Aufgabe und Speicherbedarf", satz: "Welches Sprachmodell welche Aufgabe übernimmt, was alle zusammen an Speicher brauchen, lokale Modelle einrichten." },
  { id: "routing", titel: "Modellauswahl (Routing)", satz: "Automatische Wahl unter den eingerichteten Modellen nach einer Bereitschaftsprüfung." },
  { id: "antwortzeiten", titel: "Antwortzeiten, Sätze und Prüfmodell", satz: "Wie lange Antworten dauern und welche zusätzlichen Modellaufrufe dabei mitlaufen." },
  { id: "suchindex", titel: "Suchindex", satz: "Wie genau und wie platzsparend alte Quellen durchsucht werden." },
  { id: "akten", titel: "Akten als Ordner", satz: "Die Akten als lesbare Dateien in einem Ordner, etwa für Obsidian. Nur zum Lesen." },
  { id: "rueckmeldungen", titel: "Rückmeldungen", satz: "Was als falsch gemeldet wurde, und der Export als Prüffälle." },
  { id: "befunde", titel: "Befunde der Prüfung über alle Akten", satz: "Widersprüche und Lücken, die die regelmäßige Prüfung gefunden hat." },
  { id: "hintergrund", titel: "Zeitplan und Hintergrund", satz: "Ob und wie oft Kingfisher deine Mails abruft, ältere Mails einliest und Quellen sortiert." },
  { id: "filter", titel: "Filterregeln für Post", satz: "Erlaubte und gesperrte Absender für die automatische Aufnahme." },
  { id: "quellen", titel: "Weitere öffentliche Quellen", satz: "Öffentliche Seiten, die Kingfisher von Hand oder nach Zeitplan abruft." },
  { id: "kartendienst", titel: "Eigener Kartendienst für die Wegezeit", satz: "Nötig nur ohne Apple Karten: Dienst und Schlüssel für die Wegezeit." },
  { id: "google", titel: "Google-Anmeldung vorbereiten", satz: "Einmalige Vorbereitung, damit „Mit Google anmelden“ für Post und Kalender funktioniert." },
  { id: "microsoft", titel: "Microsoft-Anmeldung vorbereiten", satz: "Die Kennung der App, damit „Mit Microsoft anmelden“ für Post, Kalender und Teams-Mitschriften funktioniert." },
  { id: "stand", titel: "Stand aller Bereiche", satz: "Was eingerichtet ist und was noch fehlt, auf einen Blick." },
  { id: "speicherorte", titel: "Speicherorte", satz: "Wo Kingfisher welche Daten auf diesem Rechner ablegt." },
  { id: "fassung", titel: "Updates ohne App", satz: "Wie eine Arbeitskopie mit einem Befehl auf die neue Fassung wechselt, und was die tägliche Prüfung abfragt." },
];

/** Die alten Reiter und ihre neue Heimat, damit jeder frühere Verweis (`#mail`, `#model`, …) weiter ankommt. */
const ALT: Record<string, string> = {
  setup: "zugaenge", mail: "zugaenge", calendar: "zugaenge", documents: "zugaenge",
  world: "darf", profile: "ich", recovery: "sicherung",
  model: "technik-modelle", memory: "technik-suchindex", automation: "technik-hintergrund",
  rueckmeldungen: "technik-rueckmeldungen", advanced: "technik",
};

export type Ziel = { bereich: Bereich; technik: string | null };

/** `#darf`, `#technik-akten` oder eine alte Kennung (`#world`) ergibt das Ziel; Unbekanntes führt nach vorn. */
export function zielAus(kennung: string): Ziel {
  const roh = kennung.replace(/^#/, "").trim();
  const neu = ALT[roh] ?? roh;
  if (neu.startsWith("technik")) {
    const rest = neu.slice("technik".length).replace(/^-/, "");
    return { bereich: "technik", technik: TECHNIK.some(t => t.id === rest) ? rest : null };
  }
  const bereich = BEREICHE.find(b => b.id === neu);
  return { bereich: bereich ? bereich.id : "zugaenge", technik: null };
}

export const kennungVon = (ziel: Ziel) => ziel.technik ? `technik-${ziel.technik}` : ziel.bereich;

/**
 * Fachwörter, die vorne nichts zu suchen haben: Der Nutzer kann sie nicht kennen (Prüffrage 1 in CLAUDE.md). Ganze
 * Wörter, Groß- und Kleinschreibung egal. Hinter „Für Techniker“ dürfen sie stehen.
 */
export const FACHWOERTER: readonly string[] = [
  "IMAP", "SMTP", "POP3", "CalDAV", "iCalendar", "OAuth", "API", "Token", "Port", "Host", "Server", "Embedding", "Embeddings",
  "Rolle", "Rollen", "Orchester", "Feed", "Feeds", "RSS", "Atom", "Ollama", "Routing", "Lint", "Suchindex", "FTS", "BM25",
  "Sidecar", "Docker", "Adapter", "Markdown", "JSON", "Prompt", "Kontext", "Inferenz", "Quantisierung", "Parameter", "GiB", "RAM",
  "Median", "Prüfmodell", "Schlüsselspeicher", "Keychain", "Webhook", "Cron", "Zeitplan", "Launch", "Agent", "HTTPS", "URL",
];

const WOERTER = FACHWOERTER.map(wort => ({ wort, muster: new RegExp(`(?<![\\p{L}\\p{N}])${wort}(?![\\p{L}\\p{N}])`, "iu") }));

/** Die Fachwörter, die in `text` als ganze Wörter vorkommen. */
export function fachwoerter(text: string): string[] {
  return WOERTER.filter(eintrag => eintrag.muster.test(text)).map(eintrag => eintrag.wort);
}

/** Alle Texte der vorderen Ebene aus diesem Modul, flach: Bereiche, Schalter, Ich, Zugänge und der Technik-Satz. */
export function vordereTexte(): string[] {
  const werte = (objekt: object): string[] => Object.values(objekt).flatMap(wert => typeof wert === "string" ? [wert] : werte(wert as object));
  return [
    ...BEREICHE.flatMap(b => [b.label, b.satz]),
    ...werte(SCHALTER), ...werte(ICH), ...werte(ZUGAENGE),
  ];
}

/** Die Dateien, deren sichtbare Texte vorne stehen (für den Wortlistentest). Ausnahmen stehen in AUSNAHMEN. */
export const VORDERE_DATEIEN: readonly string[] = [
  "Einstellungen/Zugaenge.tsx", "Einstellungen/Darf.tsx", "Einstellungen/Ich.tsx", "Einstellungen/CloudSchalter.tsx",
  "Einstellungen/Seite.tsx", "GoogleSignIn.tsx", "MicrosoftAnmeldung.tsx", "MicrosoftZugang.tsx", "microsoftAnmeldung.ts", "WeltSettings.tsx", "WegezeitSettings.tsx", "Einrichtung/AutostartWahl.tsx",
  "Einrichtung/EinrichtungKopf.tsx", "SettingsSections.tsx", "RecoverySettings.tsx", "Kreis.tsx",
  // Google ohne Cloud-Projekt (Fremdprobe, Befund 2): Post und Kalender vorne, in Alltagsworten.
  "GoogleKalenderAdresse.tsx", "googleWeg.ts", "KalenderMitAdresse.tsx", "Einrichtung/MailSchritt.tsx", "Einrichtung/KalenderSchritt.tsx",
  // Eigene Domain ohne Servereingabe (Fremdprobe 2, Befund 2): im Assistenten und unter Zugänge.
  "PostfachMitAdresse.tsx", "postfachWeg.ts",
  // Fassung und Update-Angebot (docs/53): die Zeile unter „Kingfisher und du“ und der Hinweis auf Heute.
  "Fassung.tsx",
];

/**
 * Was ein Techniker braucht und trotzdem in einer vorderen Datei steht, mit Grund. Jede Ausnahme ist ein Wort in einer
 * Datei, nicht die ganze Datei.
 */
export const AUSNAHMEN: ReadonlyArray<{ datei: string; wort: string; grund: string }> = [
  { datei: "Einrichtung/AutostartWahl.tsx", wort: "Agent", grund: "steht nur in einem Kommentar über dem Schalter" },
  { datei: "PostfachMitAdresse.tsx", wort: "Port", grund: "nur als letzte Möglichkeit, wenn Kingfisher den Mailserver der Domain nicht selbst findet, mit Vorgabe 993" },
  { datei: "postfachWeg.ts", wort: "IMAP", grund: "das Wort, unter dem der Anbieter den Servernamen in seiner Anleitung nennt; danach sucht der Mensch" },
];
