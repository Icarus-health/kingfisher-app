// V4 (25.10.2026): ein „Rückgängig“ für alles. Der Baustein `Hinweis` (grundlage/hinweisOrt.ts, Hinweis.tsx) und die
// Stellen, die ihn zeigen: jede mit dem Weg zurück, den es im Sidecar schon gibt; wo es keinen gibt, bleibt die Rückfrage.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement as h } from "react";
import { createServer } from "vite";
import { HINWEIS_DAUER, HINWEIS_DAUER_FEHLER, HinweisOrt, hinweisInhalt, istRueckgaengigTaste, zitat } from "../src/grundlage/hinweisOrt.ts";
import { erledigtHinweis, verworfenHinweis, wartetHinweis, wiederOffenHinweis, zurueckZuMirHinweis } from "../src/aufgabenHinweis.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** Eine Uhr zum Vorstellen: hält die Zeitgeber, statt zu warten. */
function testUhr() {
  let jetzt = 0, naechste = 1;
  const offen = new Map();
  return {
    setTimeout(f, ms) { const id = naechste++; offen.set(id, { f, um: jetzt + ms }); return id; },
    clearTimeout(id) { offen.delete(id); },
    vor(ms) { jetzt += ms; for (const [id, t] of [...offen]) if (t.um <= jetzt) { offen.delete(id); t.f(); } },
    get anzahl() { return offen.size; },
  };
}

test("ein Hinweis zur Zeit: der neue ersetzt den alten, nach sechs Sekunden geht er von selbst", () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  let meldungen = 0; ort.abonnieren(() => { meldungen += 1; });
  const eins = ort.zeigen({ text: "Eins." });
  const zwei = ort.zeigen({ text: "Zwei." });
  assert.notEqual(eins, zwei);
  assert.equal(ort.stand().daten.text, "Zwei.");
  assert.equal(uhr.anzahl, 1, "nur der Zeitgeber des neuen Hinweises läuft");
  ort.schliessen(eins);
  assert.equal(ort.stand().daten.text, "Zwei.", "ein alter Zeitgeber schließt den neuen nicht");
  uhr.vor(HINWEIS_DAUER - 1);
  assert.ok(ort.stand());
  uhr.vor(1);
  assert.equal(ort.stand(), null);
  assert.ok(meldungen >= 3);
  assert.equal(HINWEIS_DAUER, 6000);
});

test("Maus und Fokus halten den Hinweis; erst wenn nichts mehr hält, laufen die sechs Sekunden von vorn", () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  ort.zeigen({ text: "Erledigt.", rueckgaengig() {} });
  uhr.vor(5000);
  ort.halten("maus", true);
  uhr.vor(60000);
  assert.ok(ort.stand(), "unter der Maus bleibt er");
  ort.halten("fokus", true);
  ort.halten("maus", false);
  uhr.vor(60000);
  assert.ok(ort.stand(), "mit dem Fokus bleibt er");
  ort.halten("fokus", false);
  uhr.vor(HINWEIS_DAUER - 1);
  assert.ok(ort.stand(), "die Zeit beginnt von vorn");
  uhr.vor(1);
  assert.equal(ort.stand(), null);
});

test("Rückgängig ruft den mitgegebenen Weg genau einmal und sagt, wie es ausging", async () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  let aufrufe = 0; let freigeben;
  ort.zeigen({ text: "„Angebot“ erledigt.", danach: "„Angebot“ ist wieder offen.", rueckgaengig: () => { aufrufe += 1; return new Promise(r => { freigeben = r; }); } });
  assert.deepEqual(hinweisInhalt(ort.stand()), { text: "„Angebot“ erledigt.", knopf: "Rückgängig", fehler: false });
  const laeuft = ort.zuruecknehmen();
  assert.equal(ort.stand().phase, "laeuft");
  await ort.zuruecknehmen();
  assert.equal(aufrufe, 1, "ein zweiter Klick währenddessen zählt nicht");
  uhr.vor(60000);
  assert.ok(ort.stand(), "solange es läuft, verschwindet nichts");
  freigeben(); await laeuft;
  assert.deepEqual(hinweisInhalt(ort.stand()), { text: "„Angebot“ ist wieder offen.", knopf: null, fehler: false });
  await ort.zuruecknehmen();
  assert.equal(aufrufe, 1, "nach dem Zurücknehmen gibt es kein zweites");
  uhr.vor(HINWEIS_DAUER);
  assert.equal(ort.stand(), null);

  // Ein Satz des Sidecars geht der Vorgabe vor.
  ort.zeigen({ text: "Akte angelegt.", danach: "Vorgabe.", rueckgaengig: async () => "Zurückgenommen: Akte entfernt." });
  await ort.zuruecknehmen();
  assert.equal(hinweisInhalt(ort.stand()).text, "Zurückgenommen: Akte entfernt.");
});

test("nach dem Zurücknehmen hält ein Fokus auf dem verschwundenen Knopf den Hinweis nicht fest", async () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  ort.zeigen({ text: "Erledigt.", rueckgaengig: async () => {} });
  ort.halten("fokus", true);
  await ort.zuruecknehmen();
  uhr.vor(HINWEIS_DAUER);
  assert.equal(ort.stand(), null, "der Knopf ist weg; ein entfernter Knopf meldet kein Verlassen");
});

test("misslingt das Zurücknehmen, sagt der Hinweis es als Fehler, bleibt länger und bietet „Erneut versuchen“", async () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  let versuche = 0;
  ort.zeigen({ text: "Erledigt.", rueckgaengig: async () => { versuche += 1; if (versuche === 1) throw new Error("offline"); } });
  await ort.zuruecknehmen();
  assert.deepEqual(hinweisInhalt(ort.stand()), { text: "Nicht zurückgenommen. Die Änderung gilt weiter.", knopf: "Erneut versuchen", fehler: true });
  uhr.vor(HINWEIS_DAUER);
  assert.ok(ort.stand(), "ein Fehler steht länger als sechs Sekunden");
  await ort.zuruecknehmen();
  assert.equal(versuche, 2);
  assert.equal(hinweisInhalt(ort.stand()).text, "Rückgängig gemacht.");
  // Ein Fehlerhinweis ohne Rückweg.
  ort.zeigen({ text: "Das ließ sich gerade nicht merken.", fehler: true });
  assert.deepEqual(hinweisInhalt(ort.stand()), { text: "Das ließ sich gerade nicht merken.", knopf: null, fehler: true });
  uhr.vor(HINWEIS_DAUER_FEHLER - 1); assert.ok(ort.stand()); uhr.vor(1); assert.equal(ort.stand(), null);
});

test("⌘Z und Strg+Z nehmen zurück, aber nie in einem Eingabefeld; Shift oder Alt nicht", () => {
  const knopf = { tagName: "BUTTON" };
  assert.equal(istRueckgaengigTaste({ key: "z", metaKey: true }, knopf), true);
  assert.equal(istRueckgaengigTaste({ key: "Z", ctrlKey: true }, null), true);
  assert.equal(istRueckgaengigTaste({ key: "z" }, knopf), false);
  assert.equal(istRueckgaengigTaste({ key: "z", metaKey: true, shiftKey: true }, knopf), false, "⇧⌘Z ist Wiederholen");
  assert.equal(istRueckgaengigTaste({ key: "z", metaKey: true, altKey: true }, knopf), false);
  for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) assert.equal(istRueckgaengigTaste({ key: "z", metaKey: true }, { tagName }), false, tagName);
  assert.equal(istRueckgaengigTaste({ key: "z", metaKey: true }, { tagName: "DIV", isContentEditable: true }), false);
});

test("Titel im Hinweis: in „…“, gekürzt, damit er eine Zeile bleibt", () => {
  assert.equal(zitat("Angebot prüfen"), "„Angebot prüfen“");
  const lang = zitat("Bindefrist Angebot Rheingau-Süd an Frau Feldmann bestätigen und Unterlagen schicken");
  assert.ok(lang.length <= 50, lang);
  assert.match(lang, /^„.*…“$/);
  assert.equal(zitat("  zwei   Leerzeichen "), "„zwei Leerzeichen“");
});

test("Aufgaben: jeder Hinweis nennt die Aufgabe und gibt den Gegenweg mit", async () => {
  const a = { id: "t1", title: "Flyer prüfen" };
  const wege = [];
  const weg = (name) => async () => { wege.push(name); };
  const faelle = [
    [erledigtHinweis(a, weg("reopen")), "„Flyer prüfen“ erledigt.", "„Flyer prüfen“ ist wieder offen.", "reopen"],
    [wiederOffenHinweis(a, weg("done")), "„Flyer prüfen“ ist wieder offen.", "„Flyer prüfen“ wieder erledigt.", "done"],
    [verworfenHinweis(a, weg("reopen")), "„Flyer prüfen“ verworfen.", "„Flyer prüfen“ ist wieder offen.", "reopen"],
    [wartetHinweis(a, "Frau Brandl", weg("zurueckholen")), "Wartet auf Frau Brandl.", "„Flyer prüfen“ liegt wieder bei dir.", "zurueckholen"],
  ];
  for (const [daten, text, danach, route] of faelle) {
    assert.equal(daten.text, text); assert.equal(daten.danach, danach);
    await daten.rueckgaengig(); assert.equal(wege.at(-1), route);
  }
  let wieder = null;
  const zurueck = zurueckZuMirHinweis(a, "Frau Brandl", async name => { wieder = name; });
  await zurueck.rueckgaengig();
  assert.equal(wieder, "Frau Brandl", "„Zurück zu mir“ wartet beim Zurücknehmen wieder auf dieselbe Person");
  assert.equal(zurueckZuMirHinweis(a, null, async () => {}).rueckgaengig, undefined, "ohne bekannten Namen kein erfundenes Zurück");
});

const server = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)), configFile: false, cacheDir: `/tmp/kingfisher-hinweis-tests-${process.pid}`,
  server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom", logLevel: "error",
});
after(() => server.close());
const g = await server.ssrLoadModule("/src/grundlage/index.ts");

test("Anzeige: der Ort ist immer da (status, polite), der Hinweis eine Zeile mit Punkt und Knopf; Fehler als alert", () => {
  const ort = new g.HinweisOrt(testUhr());
  const leer = renderToStaticMarkup(h(g.HinweisAnzeige, { ort }));
  assert.equal(leer, '<div class="g-hinweis-ort" role="status" aria-live="polite" aria-atomic="true"></div>');
  ort.zeigen({ text: "„Flyer“ erledigt.", rueckgaengig() {} });
  const voll = renderToStaticMarkup(h(g.HinweisAnzeige, { ort }));
  assert.match(voll, /^<div class="g-hinweis-ort" role="status" aria-live="polite" aria-atomic="true"><div class="g-hinweis" tabindex="-1" data-phase="offen">/);
  assert.match(voll, /<span class="g-hinweis-text">„Flyer“ erledigt\.<\/span><span class="g-hinweis-aktionen"><span class="g-hinweis-punkt" aria-hidden="true">·<\/span><button type="button" class="g-hinweis-knopf" aria-keyshortcuts="Meta\+Z Control\+Z">Rückgängig<\/button>/);
  ort.zeigen({ text: "Nur gesagt." });
  assert.doesNotMatch(renderToStaticMarkup(h(g.HinweisAnzeige, { ort })), /<button/, "ohne Rückweg kein Knopf");
  ort.zeigen({ text: "Nicht gemerkt.", fehler: true });
  assert.match(renderToStaticMarkup(h(g.HinweisAnzeige, { ort })), /data-fehler="true"[^>]*><span class="g-hinweis-text" role="alert">Nicht gemerkt\.<\/span>/);
  ort.zeigen({ text: "Akte angelegt.", verweis: { text: "Akte öffnen", href: "/memory/akte/x" }, rueckgaengig() {} });
  assert.match(renderToStaticMarkup(h(g.HinweisAnzeige, { ort })), />Rückgängig<\/button><span class="g-hinweis-punkt" aria-hidden="true">·<\/span><a class="g-hinweis-knopf" href="\/memory\/akte\/x">Akte öffnen<\/a>/);
});

test("Anzeige: Escape schließt, Maus und Fokus halten, ⌘Z wirkt, der Fokus kommt nur bei Tastaturbedienung", () => {
  const anzeige = quelle("grundlage/Hinweis.tsx");
  assert.match(anzeige, /if \(e\.key !== "Escape" \|\| !zustand\) return;\n\s*e\.preventDefault\(\);\n\s*ort\.schliessen\(zustand\.nummer\);/);
  assert.match(anzeige, /onMouseEnter=\{\(\) => ort\.halten\("maus", true\)\} onMouseLeave=\{\(\) => ort\.halten\("maus", false\)\}/);
  assert.match(anzeige, /onFocus=\{e => ort\.halten\("fokus", sichtbarerFokus\(e\.target\)\)\}/);
  assert.match(anzeige, /document\.addEventListener\("pointerdown", zeiger, true\)/);
  assert.match(anzeige, /document\.addEventListener\("keydown", taste\)/);
  assert.match(anzeige, /if \(!nummer \|\| typeof document === "undefined" \|\| !tastatur\.current\) return;/);
  // Genau einmal eingehängt, für alle Seiten.
  const main = quelle("main.tsx");
  assert.equal(main.match(/<HinweisAnzeige \/>/g).length, 1);
});

test("Stile: unten mittig, über allem, 44-px-Knopf, leise Bewegung, die bei reduzierter Bewegung entfällt", () => {
  const css = ohneKommentare(quelle("Grundlage.css"));
  assert.match(css, /\.g-hinweis-ort \{ position: fixed; z-index: 60; left: 0; right: 0; bottom: max\(var\(--g-a5\), env\(safe-area-inset-bottom\)\); display: flex; justify-content: center;/);
  assert.match(css, /\.g-hinweis \{[^}]*max-width: min\(560px, 100%\);[^}]*background: var\(--g-tinte\); color: var\(--g-auf-akzent\);[^}]*animation: g-hinweis-kommt var\(--g-bewegung\) both;/);
  assert.match(css, /\.g-hinweis-knopf \{[^}]*min-height: var\(--g-ziel\);/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\) \{[^@]*\n  \.g-hinweis \{ animation: none; \}\n\}/);
  // Die alte Meldung der Akte ist im Baustein aufgegangen.
  assert.doesNotMatch(quelle("AkteAbschnitte.css"), /akte-meldung/);
});

// Inventar (docs/16-gestaltung.md, „Hinweis“): jede umkehrbare Aktion zeigt den Hinweis mit ihrem vorhandenen Gegenweg.
const STELLEN = [
  ["App.tsx", /erledigtHinweis\(aufgabe, async \(\) => \{ await api\.reopenTask\(taskId\); load\(\); \}\)/, "Aufgaben: erledigen → /reopen"],
  ["App.tsx", /wiederOffenHinweis\(aufgabe, async \(\) => \{ await api\.completeTask\(taskId\); load\(\); \}\)/, "Aufgaben: wieder öffnen → /done"],
  ["App.tsx", /wartetHinweis\(aufgabe, name, async \(\) => \{ await api\.unwaitTask\(taskId\); load\(\); \}\)/, "Aufgaben: Warte auf → /zurueckholen"],
  ["App.tsx", /zurueckZuMirHinweis\(aufgabe, [^,]+, async vorher => \{ await api\.waitTask\(taskId, vorher\); load\(\); \}\)/, "Aufgaben: Zurück zu mir → /warten"],
  ["TaskDetail.tsx", /erledigtHinweis\(task, \(\) => change\(\(\) => api\.reopenTask\(task\.id\)\)\)/, "Aufgabe: erledigen"],
  ["TaskDetail.tsx", /verworfenHinweis\(task, \(\) => change\(\(\) => api\.reopenTask\(task\.id\)\)\)/, "Aufgabe: verwerfen → /reopen"],
  ["TaskDetail.tsx", /rueckgaengig: \(\) => change\(\(\) => api\.dropTask\(task\.id\)\)/, "Aufgabe: wieder aufnehmen → /drop"],
  ["TodayTaskRow.tsx", /zeigeHinweis\(erledigtHinweis\(task, async \(\) => \{\n\s*await api\.reopenTask\(task\.id\);/, "Heute: erledigen"],
  ["AufgabenPostVorschlaege.tsx", /rueckgaengig: async \(\) => \{ await api\.taskRueckgaengig\(task\.id\);/, "Aus deiner Post: annehmen → /rueckgaengig"],
  ["AkteVorschlagKnoepfe.tsx", /await api\.akteVorschlagZuruecknehmen\(kennung\)/, "Heute: Neue Akte? → /zuruecknehmen"],
  ["AkteAbschnitte.tsx", /rueckgaengig: zurueckWeg\(ziel, antwort\.vorher\)/, "Akte: Erledigt / Gilt nicht mehr / Gilt weiter"],
  ["KreisKarten.tsx", /const zurueck = vorher \? await api\.kreisBestaetigen\(sache, vorher\) : await api\.kreisZuruecknehmen\(sache\);/, "Kreis wählen"],
  ["KreisKarten.tsx", /const zurueck = vorher \? await api\.aktenArtBestaetigen\(sache, vorher\) : await api\.aktenArtZuruecknehmen\(sache\);/, "Art der Akte"],
  ["KreisKarten.tsx", /const zurueck = await api\.kreisSammlungZurueck\(sammlung\);/, "Kollegen gesammelt festlegen"],
  ["SourceBezuege.tsx", /api\.bezugSetzen\(id, abgelehnt\.sache, "nicht"\)/, "Quelle: Doch zuordnen ↔ Gehört nicht dazu"],
  ["SourceProject.tsx", /await api\.linkSourceProject\(id, previous \|\| null\);/, "Quelle: Projekt zuordnen"],
  ["SourceProject.tsx", /rueckgaengig: \(\) => undoSender\(moved\)/, "Quelle: weitere Mails desselben Absenders"],
  ["OrganisationGroups.tsx", /organisationSuggestionsApi\.undoDismissal\(value\.id,abgelehnt\.revision\)/, "Gruppenvorschlag ablehnen → undo-dismissal"],
];
test("jede umkehrbare Aktion zeigt den Hinweis mit ihrem vorhandenen Gegenweg", () => {
  for (const [datei, muster, was] of STELLEN) {
    const text = quelle(datei);
    assert.match(text, muster, `${datei}: ${was}`);
    assert.match(text, /zeigeHinweis/, datei);
  }
  const api = quelle("api.ts");
  for (const route of ["/reopen`", "/done`", "/zurueckholen`", "/warten`", "/rueckgaengig`", "/drop`", "/zuruecknehmen`", "/api/v1/kreis/sammel?sammlung=", "/undo-dismissal"])
    assert.ok(api.includes(route) || quelle("organisationSuggestionsApi.ts").includes(route), route);
  assert.match(api, /aktenArtZuruecknehmen: \(sache: string\) => request<ArtStand>\(`\/api\/v1\/akten\/art\?sache=\$\{encodeURIComponent\(sache\)\}`, \{ method: "DELETE" \}\)/);
});

test("vor einer umkehrbaren Aktion keine Rückfrage mehr; vor einer nicht umkehrbaren bleibt sie", () => {
  const kreis = quelle("KreisKarten.tsx");
  assert.doesNotMatch(kreis, /Ja, festlegen|setFrage|kreis-frage/, "Kollegen gesammelt festlegen ist umkehrbar: ein Klick");
  assert.match(kreis, /onClick=\{\(\) => void sammeln\(kollegen\)\}>\{sammelKnopf\(kollegen\)\}<\/button>/);
  // Bleiben: was sich nicht (vollständig) zurücknehmen lässt.
  assert.match(quelle("DecisionControls.tsx"), /Wirklich zurücknehmen\?/);
  assert.match(quelle("ProfileSource.tsx"), /Ja, nicht mehr verwenden/);
  assert.match(quelle("ProfileSource.tsx"), /Sortierergebnis jetzt verwerfen/);
  assert.match(quelle("Einstellungen/Quellenformulare.tsx"), /Quelle wirklich entfernen\?/);
});
