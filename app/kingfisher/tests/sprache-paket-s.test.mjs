// Sprache und Kleinigkeiten (Persona-Prüfung, Paket S, 27.10.2026). Je Test der Befund aus Abschnitt 6 des Berichts
// (docs/runs/2026-10-26-persona-pruefung/README.md) oder der offene Rest eines vorigen Pakets.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { schonVerbunden, schonVerbundenSatz } from "../src/postfachWeg.ts";
import { vorbelegteAdresse } from "../src/kalenderWeg.ts";
import { ANDERES_MODELL, listenWert, vorbelegtesModell } from "../src/cloudAccessForm.ts";
import { testCache } from "./testcache.mjs";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const server = await createServer({ cacheDir: testCache("sprache-paket-s"), root: fileURLToPath(new URL("..", import.meta.url)),
  configFile: false, logLevel: "silent", server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom" });
after(() => server.close());

// -- Befund 4: doppeltes Postfach gleich nach der Adresse, ruhig ---------------------------------------------------

test("ein schon verbundenes Postfach wird an der Adresse erkannt, gleich welche Schreibweise", () => {
  const liste = [{ id: "mail-a", name: "Kanzlei", adresse: "Lea@Hartmann-Beratung.example" }];
  assert.deepEqual(schonVerbunden("  lea@hartmann-beratung.example ", liste), liste[0]);
  assert.equal(schonVerbunden("lea@hartmann-beratung.exampl", liste), null, "halb getippt: noch nichts");
  assert.equal(schonVerbunden("lea@hartmann", liste), null);
  assert.equal(schonVerbunden("anna@hartmann-beratung.example", liste), null);
  assert.equal(schonVerbundenSatz("Kanzlei"), "Dieses Postfach ist schon verbunden: Kanzlei. Kingfisher liest es bereits.");
});

test("die Karte sagt es vor dem Passwort, ohne roten Rahmen, mit dem Weg dorthin; auch die Antwort 409 steht ruhig da", () => {
  const karte = quelle("PostfachMitAdresse.tsx");
  const hinweis = karte.slice(karte.indexOf("{schon || doppeltSatz"), karte.indexOf("{schon ? null : <>"));
  assert.ok(hinweis.length > 0, "der Hinweis steht direkt unter der Adresse");
  assert.ok(karte.indexOf("{schon || doppeltSatz") < karte.indexOf("<PasswortFeld"), "vor dem Passwortfeld");
  assert.match(hinweis, /role="status"/);
  assert.doesNotMatch(hinweis, /settings-error|role="alert"/, "kein roter Fehler");
  assert.match(hinweis, /Zum Postfach/);
  assert.match(karte, /problem\.status === 409[^\n]*setDoppeltSatz/);
  // Ist es schon verbunden, wird die Domain nicht gefragt.
  assert.match(karte, /useAnbieter\(schon \? "" : adresse/);
  assert.match(quelle("Einstellungen/Zugaenge.tsx"), /zumPostfach=\{kontoId =>/);
});

// -- Befund 8: Passwort anzeigen, Kalender vom selben Anbieter vorbelegt ---------------------------------------------

test("jedes Passwortfeld vorne hat „Anzeigen“, verborgen als Vorgabe", async () => {
  const { PasswortFeld } = await server.ssrLoadModule("/src/grundlage/PasswortFeld.tsx");
  const html = renderToStaticMarkup(createElement(PasswortFeld, { id: "p", wert: "geheim", onWert() {} }));
  assert.match(html, /type="password"/);
  assert.match(html, /aria-pressed="false"/);
  assert.match(html, />Anzeigen</);
  assert.match(html, /aria-label="Passwort anzeigen"/);
  for (const datei of ["PostfachMitAdresse.tsx", "KalenderMitAdresse.tsx", "Einstellungen/NeuAnmelden.tsx"])
    assert.doesNotMatch(quelle(datei), /type="password"/, `${datei}: das Feld mit „Anzeigen“`);
});

test("der Kalender nimmt zuerst das Postfach, dessen Anbieter den Kalender mit demselben Passwort hat", () => {
  const anbieter = [{ id: "gmail", label: "Gmail", imap_host: "imap.gmail.com", domains: ["gmail.com"], kalender_ical: true },
    { id: "gmx", label: "GMX", imap_host: "imap.gmx.net", domains: ["gmx.de"], caldav_url: "https://caldav.gmx.net" }];
  const praxis = { user: "praxis@praxis-fehr.example", secret_present: true };
  const gmail = { user: "miriam.fehr@gmail.com", secret_present: true };
  assert.equal(vorbelegteAdresse([gmail, praxis], anbieter), "praxis@praxis-fehr.example", "eigene Domain: beim Mailserver suchen");
  assert.equal(vorbelegteAdresse([gmail, { user: "m@gmx.de", secret_present: true }], anbieter), "m@gmx.de");
  assert.equal(vorbelegteAdresse([gmail], anbieter), "miriam.fehr@gmail.com", "nur Gmail: dann Gmail");
  assert.equal(vorbelegteAdresse([{ ...praxis, secret_present: false }, gmail], anbieter), "miriam.fehr@gmail.com",
    "ohne gespeichertes Passwort zählt das Postfach nicht als gleicher Weg");
  assert.equal(vorbelegteAdresse([], anbieter), "");
});

// -- Befund 5: Cloud einschalten ohne Modellnamen -------------------------------------------------------------------

test("das Modell ist vorbelegt: gespeichert, sonst das empfohlene; die Wahl ist eine Liste", () => {
  const modelle = [{ id: "claude-sonnet-5-5", titel: "Empfohlen: gründlich und schnell" }, { id: "claude-sonnet-5", titel: "Die Fassung davor" }];
  assert.equal(vorbelegtesModell({ model: "", modelle }), "claude-sonnet-5-5");
  assert.equal(vorbelegtesModell({ model: "claude-sonnet-5", modelle }), "claude-sonnet-5");
  assert.equal(vorbelegtesModell({ model: "", modelle: [] }), "");
  assert.equal(listenWert("claude-sonnet-5", modelle), "claude-sonnet-5");
  assert.equal(listenWert("eigenes-modell", modelle), ANDERES_MODELL, "ein eigener Name: das Feld für Techniker");
  const karte = quelle("CloudAccess.tsx");
  assert.match(karte, /<select value=\{wert\}/);
  assert.doesNotMatch(karte, /Endpunkt/);
  assert.doesNotMatch(karte, />API-Schlüssel/, "vorne „Zugangsschlüssel“, das Wort des Anbieters in Klammern");
  assert.match(karte, /<summary>Für Techniker<\/summary>[\s\S]*provider\.endpoint/);
  assert.match(quelle("ChatGPTAccess.tsx"), />Mit ChatGPT anmelden</);
  assert.doesNotMatch(quelle("ChatGPTAccess.tsx"), /Continue with/);
  assert.doesNotMatch(quelle("Einstellungen/CloudSchalter.tsx"), /gespeicherten Zugang und ein Modell/);
});

// -- Befund 2: Technikzeile unter Antworten hinter „Details“, zu ------------------------------------------------------

test("die Zeiten unter einer Antwort stehen hinter einem zugeklappten „Details“", async () => {
  const { AntwortZeile } = await server.ssrLoadModule("/src/AntwortZeiten.tsx");
  const html = renderToStaticMarkup(createElement(AntwortZeile, { zeiten: { gesamt: 10, antwort_modell: 4, saetze_modell: 6 } }));
  assert.match(html, /^<details class="antwortzeit-details"><summary>Details<\/summary><p class="antwortzeit"/);
  assert.doesNotMatch(html, /<details[^>]*open/, "Vorgabe: zu");
  assert.match(html, /10 s · /);
  assert.equal(renderToStaticMarkup(createElement(AntwortZeile, { zeiten: null })), "", "ohne Zeiten nichts, auch kein „Details“");
});

// -- Befund 6: Texte ----------------------------------------------------------------------------------------------

test("der Satz unter den Häkchen passt zu ihrer Zahl: kein „beides“ unter einem", async () => {
  const { pausierenSatz, PAUSIEREN_AUF_HEUTE, schonDaZahlen } = await import("../src/Einrichtung/fertig.ts");
  assert.equal(pausierenSatz({ einlesen: true, sortieren: true }), PAUSIEREN_AUF_HEUTE);
  for (const eines of [{ einlesen: true, sortieren: false }, { einlesen: false, sortieren: true }]) {
    assert.doesNotMatch(pausierenSatz(eines), /beides/);
    assert.match(pausierenSatz(eines), /auf Heute mit „Pausieren“/);
  }
  assert.equal(pausierenSatz({ einlesen: false, sortieren: false }), null);
  assert.match(quelle("Einrichtung/FertigSchritt.tsx"), /pausierenSatz\(\{einlesen: angebote\.einlesen\.length > 0, sortieren: angebote\.sortieren\}\)/);
  // Die gelesenen Mails stehen einmal: zeigt „Kingfisher lernt gerade“ sie, fehlt die Kachel.
  const ordner = { folder: "INBOX", inventory_complete: true, total: 5, captured: 5, duplicates: 0, failed: 0, pending: 0,
    live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0 };
  const intake = { accounts: [{ account_id: "a", label: "A", connected: true, started: true, paused: false, folders: [ordner] }] };
  assert.deepEqual(schonDaZahlen({ mail: true, kalender: false, intake, termine: null }).map(z => z.titel), ["Mails gelesen"]);
  assert.deepEqual(schonDaZahlen({ mail: true, kalender: false, intake, termine: null, mailImLernen: true }), []);
  assert.match(quelle("Einrichtung/FertigSchritt.tsx"), /beiAenderung=\{\(_, zeilen\) => setMailImLernen\(zeilen\.some\(zeile => zeile\.id === "mail"\)\)\}/);
  assert.match(quelle("Einrichtung/KingfisherLernt.tsx"), /const kennung = `\$\{neu\.length > 0\}:\$\{neu\.map\(zeile => zeile\.id\)\.join\(","\)\}`/);
});

// -- Befund 7: „Neu eingegangen → Mehr“ ---------------------------------------------------------------------------

test("„Mehr“ unter „Neu eingegangen“ führt zu den neuen Mails, nicht in die allgemeine Suche", async () => {
  const { mehrZiel } = await server.ssrLoadModule("/src/TodayOverview.tsx");
  assert.equal(mehrZiel({ neu_mehr: "nachrichten", working_memory_more: true }), "/nachrichten");
  assert.equal(mehrZiel({ neu_mehr: "gedaechtnis" }), "/memory");
  assert.equal(mehrZiel({ neu_mehr: null, working_memory_more: true }), null);
  assert.equal(mehrZiel({ working_memory_more: true }), "/memory", "ein älterer Sidecar: wie bisher");
  assert.match(quelle("TodayOverview.tsx"), /\{mehrZiel\(briefing\) \? <a className="today-text-link" href=\{mehrZiel\(briefing\)!\}>Mehr<\/a>/);
});

test("Umbenennen steht sichtbar neben dem Namen; der Name selbst ist kein Knopf", async () => {
  const { KontoZeile } = await server.ssrLoadModule("/src/Einstellungen/KontoZeile.tsx");
  const konto = { id: "mail-a", name: "Kanzlei", adresse: "lea@kanzlei.example", bereich: "arbeit", vorschlag: null, stand: null };
  const html = renderToStaticMarkup(createElement(KontoZeile, { konto, konten: null, iconName: "mail", neben: "lea@kanzlei.example",
    busy: false, onUmbenennen: async () => null, onBereich() {}, onNeuerBereich: async () => null }));
  assert.match(html, /<strong class="g-zeile-titel">Kanzlei<\/strong><button type="button" class="text-action konto-umbenennen" aria-label="Kanzlei umbenennen">Umbenennen<\/button>/);
  assert.doesNotMatch(html, /<button[^>]*>Kanzlei<\/button>/);
  assert.match(html, /data-konto="mail-a"/);
  const mac = renderToStaticMarkup(createElement(KontoZeile, { konto: { ...konto, umbenennbar: false }, konten: null, iconName: "mail",
    neben: "", busy: false, onUmbenennen: async () => null, onBereich() {}, onNeuerBereich: async () => null }));
  assert.doesNotMatch(mac, /Umbenennen/, "ein Mac-Kalender heißt, wie er auf dem Mac heißt");
});

// -- Offener Rest aus D: eingetragene öffentliche Seiten unter „Was Kingfisher darf“ ---------------------------------

test("die eingetragenen öffentlichen Seiten stehen mit Schalter und ehrlichem Satz unter „Was Kingfisher darf“", async () => {
  const darf = quelle("Einstellungen/Darf.tsx");
  assert.ok(darf.indexOf("<WebSchalter />") < darf.indexOf("<QuellenSchalter />") && darf.indexOf("<QuellenSchalter />") < darf.indexOf("<FassungSchalter />"));
  const { quellenAnzahlSatz } = await server.ssrLoadModule("/src/Einstellungen/Darf.tsx");
  assert.equal(quellenAnzahlSatz(0), "Noch keine Seite eingetragen; dann geht hier nichts hinaus.");
  assert.equal(quellenAnzahlSatz(2), "Eingetragen sind 2 Seiten.");
  const { TECHNIK } = await import("../src/Einstellungen/gliederung.ts");
  assert.match(TECHNIK.find(t => t.id === "quellen").satz, /steht unter „Was Kingfisher darf“/);
});

// -- Offener Rest aus Z: „Zurück zur Prüfung“ und das dafür angelegte Projekt -----------------------------------

test("Rückgängig nach „Zurück zur Prüfung“ legt ein mitgenommenes Projekt wieder an", () => {
  const detail = quelle("TaskDetail.tsx");
  assert.match(detail, /const neuesProjekt = antwort\.projekt\?\.entfernt \? antwort\.projekt\.name : null;/);
  assert.match(detail, /project_id: neuesProjekt \? null : aufgabe\.project_id \?\? null,\s*new_project_name: neuesProjekt/);
});

// -- Offener Rest aus B: Abbestellen und Mitschrift zuordnen/lösen -------------------------------------------------

test("Abbestellen und Mitschrift zuordnen fragen nicht vorher, der Hinweis trägt Rückgängig; die Gestaltung sagt dasselbe", () => {
  const lage = quelle("TagesLage.tsx");
  assert.match(lage, /zeigeHinweis\(\{ text: abbestelltSatz\(a\.art === "welt_quelle"\), danach: "Wieder bestellt\.",\s*rueckgaengig: async \(\) => \{ await api\.weltAbbestellenRueckgaengig\(ziel\)/);
  assert.doesNotMatch(lage, /Rueckfrage/);
  const nach = quelle("CalendarFollowup.tsx");
  assert.match(nach, /rueckgaengig: async \(\) => \{\s*await api\.transkriptRueckgaengig\(episodeId\)/);
  assert.doesNotMatch(nach, /<Rueckfrage/);
  const doku = readFileSync(new URL("../../../docs/16-gestaltung.md", import.meta.url), "utf8");
  const ohne = doku.slice(doku.indexOf("Ohne „Rückgängig“ (kein vollständiger Weg zurück)"), doku.indexOf("**Abbestellen und Mitschrift zuordnen"));
  assert.doesNotMatch(ohne, /Mitschrift zuordnen|Welt-Meldung/, "nicht mehr unter „Rückfrage bleibt“");
  assert.match(doku, /\| Welt-Meldung abbestellen[^\n]*\/welt\/abbestellen\/rueckgaengig/);
  assert.match(doku, /\| Mitschrift „Zu diesem Termin“[^\n]*\/transkripte\/\{id\}\/zuordnung\/rueckgaengig/);
});

// -- Offener Rest aus H: 16 px Seitenrand unter 900 px ---------------------------------------------------------------

test("die Regel für 16 px Seitenrand unter 900 px trifft main selbst", () => {
  const css = quelle("Seitenbreite.css").replace(/\/\*[\s\S]*?\*\//g, "");
  const block = css.slice(css.indexOf("@media (max-width: 900px)"), css.indexOf("@media (max-width: 700px)"));
  assert.match(block, /\.shell main:is\(\.tasks-page, \.settings-page, \.profile-page, \.inbox-page, \.conversation-history\) \{ padding-inline: 16px; \}/);
  assert.doesNotMatch(css, /main :is\(\.tasks-page/, "kein Leerzeichen zwischen main und :is: sonst trifft die Regel nie");
});

test("Heute fragt mit der Zeitzone des Geräts, wie die Uhr in der Seitenleiste", () => {
  const api = quelle("api.ts");
  assert.match(api, /morning: \(post = true\) => request<MorningBriefing>\(`\/api\/v1\/morning-briefing\?\$\{new URLSearchParams\(\{\s*\.\.\.\(geraeteZone\(\) \? \{timezone: geraeteZone\(\)\} : \{\}\)/);
  assert.match(quelle("LiveClock.tsx"), /Intl\.DateTimeFormat\(\)\.resolvedOptions\(\)\.timeZone/);
});
