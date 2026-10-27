// Ein Rückweg, der bleibt, und ein Hinweis, der nichts verdeckt (Persona-Prüfung, Paket Z, Z2 bis Z4, 27.10.2026).
// Z2: Rückgängig stand nur sechs Sekunden; Berühren am Handy hielt den Hinweis nicht; danach gab es keinen Weg zurück.
// Z3: Nach Enter lag der Fokus auf „Rückgängig“, ein zweites Enter nahm alles zurück; am Handy verdeckte der Hinweis.
// Z4: Ein übernommener Vorschlag und eine neue Aufgabe öffneten ungefragt im Vollbild, ohne Hinweis und Rückweg.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { HINWEIS_DAUER, HINWEIS_DAUER_FEHLER, HinweisOrt, hinweisDauer } from "../src/grundlage/hinweisOrt.ts";
import { fokusZiel, merkeFokus } from "../src/grundlage/fokusZiel.ts";
import { uebernahmeZeile, zurueckgenommenNeben, angelegtHinweis, uebernommenHinweis } from "../src/aufgabenVonSelbst.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");

function testUhr() {
  let jetzt = 0, naechste = 1;
  const offen = new Map();
  return {
    setTimeout(f, ms) { const id = naechste++; offen.set(id, { f, um: jetzt + ms }); return id; },
    clearTimeout(id) { offen.delete(id); },
    vor(ms) { jetzt += ms; for (const [id, t] of [...offen]) if (t.um <= jetzt) { offen.delete(id); t.f(); } },
  };
}

// -- Z2: lange genug, und Berühren hält -------------------------------------------------------------------------------

test("der Hinweis steht lange genug, um ihn zu lesen: mindestens zehn Sekunden, länger bei langem Satz", () => {
  assert.equal(HINWEIS_DAUER, 10000);
  assert.ok(HINWEIS_DAUER_FEHLER >= 15000);
  assert.equal(hinweisDauer("„Flyer“ erledigt."), HINWEIS_DAUER);
  const lang = "Zurückgenommen. Kingfisher legt diese Aufgabe nicht wieder an. Unter „Erledigt“ kannst du sie jederzeit wiederherstellen.";
  assert.ok(hinweisDauer(lang) > HINWEIS_DAUER, "ein langer Satz steht länger");
  assert.ok(hinweisDauer("Nicht gemerkt.", true) >= HINWEIS_DAUER_FEHLER);
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  ort.zeigen({ text: lang, rueckgaengig() {} });
  uhr.vor(hinweisDauer(lang) - 1);
  assert.ok(ort.stand());
  uhr.vor(1);
  assert.equal(ort.stand(), null);
});

test("ein Finger auf dem Hinweis hält ihn wie die Maus; danach läuft die Zeit von vorn", () => {
  const uhr = testUhr(); const ort = new HinweisOrt(uhr);
  ort.zeigen({ text: "Erledigt.", rueckgaengig() {} });
  uhr.vor(9000);
  ort.halten("beruehren", true);
  uhr.vor(60000);
  assert.ok(ort.stand(), "unter dem Finger bleibt er");
  ort.halten("beruehren", false);
  uhr.vor(HINWEIS_DAUER - 1);
  assert.ok(ort.stand());
  uhr.vor(1);
  assert.equal(ort.stand(), null);
  const anzeige = quelle("grundlage/Hinweis.tsx");
  assert.match(anzeige, /onPointerDown=\{\(\) => ort\.halten\("beruehren", true\)\}/);
  assert.match(anzeige, /document\.addEventListener\("pointerup", loslassen, true\)/);
  assert.match(anzeige, /document\.addEventListener\("pointercancel", loslassen, true\)/);
});

// -- Z3: der Fokus bleibt bei der Arbeit, nicht auf „Rückgängig“ -----------------------------------------------------

/** Ein kleines Element-Modell: genug für fokusZiel, ohne Browser. */
function el(name, { verbunden = true, deaktiviert = false, rolle = "", tabindex = null, eltern = null, im_hinweis = false } = {}) {
  const e = {
    name, isConnected: verbunden, disabled: deaktiviert, parentElement: eltern, fokussiert: false, attrs: tabindex === null ? {} : { tabindex: String(tabindex) },
    tagName: name.toUpperCase().split(".")[0].split("#")[0],
    matches(sel) { return sel.split(",").map(s => s.trim()).some(s => s === this.tagName.toLowerCase() || (rolle && s === `[role=${rolle}]`) || (s.startsWith(".") && name.includes(s)) || (s === ".g-hinweis-ort" && im_hinweis)); },
    closest(sel) { let n = this; while (n) { if (n.matches(sel)) return n; n = n.parentElement; } return null; },
    hasAttribute(a) { return a in this.attrs; }, setAttribute(a, v) { this.attrs[a] = String(v); },
    focus() { this.fokussiert = true; },
  };
  return e;
}

test("nach Enter: die verschwundene Zeile übergibt den Fokus an ihre Liste, nie an „Rückgängig“", () => {
  const main = el("main");
  const liste = el("section.task-vorschlaege", { eltern: main });
  const zeile = el("article", { eltern: liste, verbunden: false });
  const knopf = el("button", { eltern: zeile, verbunden: false });
  const merk = merkeFokus(knopf);
  assert.deepEqual(merk.vorfahren.map(v => v.name), ["article", "section.task-vorschlaege", "main"]);
  const ziel = fokusZiel(merk, main);
  assert.equal(ziel, liste, "die Liste, nicht die nächste Schaltfläche: ein zweites Enter löst dort nichts aus");
  assert.equal(liste.attrs.tabindex, "-1", "nur programmatisch fokussierbar, kein neuer Tab-Halt");
});

test("ist der Auslöser noch da, bleibt er; ist er gesperrt (die Aktion läuft), wird gewartet; sonst die Seite", () => {
  const main = el("main");
  const knopf = el("button", { eltern: main });
  assert.equal(fokusZiel(merkeFokus(knopf), main), knopf);
  const gesperrt = el("button", { eltern: main, deaktiviert: true });
  assert.equal(fokusZiel(merkeFokus(gesperrt), main), null);
  const weg = el("button", { verbunden: false });
  assert.equal(fokusZiel(merkeFokus(weg), main), main);
  assert.equal(fokusZiel(null, main), main);
  // Was im Hinweis selbst liegt, ist nie das Ziel.
  const ort = el("div.g-hinweis-ort", { im_hinweis: true, eltern: main });
  const imHinweis = el("button", { eltern: ort, verbunden: false, im_hinweis: true });
  assert.equal(fokusZiel(merkeFokus(imHinweis), main), main);
});

test("Anzeige: kein Sprung auf „Rückgängig“; angesagt als Status mit Tastenkürzel; erreichbar mit Tab oder ⌘Z/Strg+Z", () => {
  const anzeige = quelle("grundlage/Hinweis.tsx");
  assert.doesNotMatch(anzeige, /\(knopf\.current \?\? flaeche\.current\)\.focus/);
  assert.doesNotMatch(anzeige, /knopf\.current\??\.focus\(/);
  assert.match(anzeige, /fokusZiel\(merk\.current, document\.querySelector\("main"\)\)/);
  assert.match(anzeige, /<span className="visually-hidden">\{` \$\{kuerzelSatz\(mac\)\}`\}<\/span>/);
  assert.match(quelle("grundlage/hinweisOrt.ts"), /export function kuerzelSatz\(mac: boolean\): string/);
});

// -- Z3 am Handy: der Hinweis verdeckt nichts Bedienbares -------------------------------------------------------------

test("am Handy bekommt die Seite unten Platz in Höhe des Hinweises, und was du bedienst, rückt darüber", () => {
  const css = ohneKommentare(quelle("Grundlage.css"));
  assert.match(css, /@media \(max-width: 700px\) \{\s*html\.g-hinweis-offen body \{ padding-bottom: calc\(var\(--g-hinweis-platz, 0px\) \+ var\(--g-a5\)\); \}/);
  const anzeige = quelle("grundlage/Hinweis.tsx");
  assert.match(anzeige, /const wurzel = document\.documentElement;/);
  assert.match(anzeige, /wurzel\.classList\.add\("g-hinweis-offen"\)/);
  assert.match(anzeige, /wurzel\.style\.setProperty\("--g-hinweis-platz", `\$\{hoehe\}px`\)/);
  assert.match(anzeige, /freiRuecken\(/);
  // Würde er unten Bedienbares verdecken und oben nicht, steht er oben.
  assert.match(css, /\.g-hinweis-ort\.g-hinweis-oben \{ top: max\(var\(--g-a5\), env\(safe-area-inset-top\)\); bottom: auto; \}/);
  assert.match(anzeige, /if \(verdeckt\(r\.top, r\.bottom, r\.left, r\.right\) > 0 && verdeckt\(abstand, abstand \+ r\.height, r\.left, r\.right\) === 0\)/);
});

// -- Z2: ein Weg zurück, der bleibt -----------------------------------------------------------------------------------

test("Zurückgenommenes steht unter „Erledigt“ mit „Wiederherstellen“, ohne neue Seite", () => {
  assert.equal(zurueckgenommenNeben({ zurueck_am: "2026-09-29T08:00:00+00:00" }), "Von Kingfisher angelegt, am 29. September zurückgenommen");
  const gruppe = quelle("ZurueckgenommenGruppe.tsx");
  assert.match(gruppe, /api\.aufgabenZurueckgenommen\(\)/);
  assert.match(gruppe, /titel="Zurückgenommen"/);
  assert.match(gruppe, />Wiederherstellen<\/button>/);
  assert.match(gruppe, /api\.aufgabeVonSelbstWiederherstellen\(eintrag\.id\)/);
  assert.match(gruppe, /rueckgaengig: async \(\) => \{ await api\.aufgabeVonSelbstZuruecknehmen\(eintrag\.id\);/);
  assert.match(quelle("App.tsx"), /view === "done" && !search \? <ZurueckgenommenGruppe /);
  assert.match(quelle("api.ts"), /aufgabenZurueckgenommen: \(\) => request<\{aufgaben: ZurueckgenommeneAufgabe\[\]\}>\("\/api\/v1\/aufgaben-von-selbst\/zurueckgenommen"\)/);
});

test("übernommene Vorschläge tragen in der Aufgabe selbst „Zurück zur Prüfung“, auch Tage später", () => {
  assert.equal(uebernahmeZeile({ angelegt: { art: "uebernommen", am: "2026-09-29T06:00:00+00:00" } }), "Aus einem Vorschlag übernommen am 29. September");
  assert.equal(uebernahmeZeile({ angelegt: { art: "alle_uebernehmen", gruppe: "g-1", am: "2026-09-29T06:00:00+00:00" } }), "Mit „Alle übernehmen“ übernommen am 29. September");
  assert.equal(uebernahmeZeile({ angelegt: { art: "automatisch" } }), null);
  assert.equal(uebernahmeZeile({ angelegt: null }), null);
  const detail = quelle("TaskDetail.tsx");
  assert.match(detail, /uebernahmeZeile\(task\)/);
  assert.match(detail, /api\.zurPruefung\(aufgabe\.id\)/);
  assert.match(detail, />Zurück zur Prüfung<\/button>/);
  assert.match(detail, /api\.gruppeZuruecknehmen\(gruppe\)/);
  assert.match(detail, />Alle dieser Übernahme zurück<\/button>/);
  // Paket S: dazu `projekt`, das beim Übernehmen neu angelegte Projekt.
  assert.match(quelle("api.ts"), /zurPruefung: \(taskId: string\) => request<\{satz: string; proposal_id: string; projekt\?: \{name: string; entfernt: boolean\} \| null\}>\(`\/api\/v1\/task-candidates\/aufgabe\/\$\{encodeURIComponent\(taskId\)\}\/zurueck`, \{method: "POST"\}\)/);
});

// -- Z4: Übernehmen und „+ Aufgabe“ bleiben in der Liste, mit Hinweis und Rückgängig --------------------------------

test("einen Vorschlag übernehmen: die Liste bleibt, der Hinweis sagt es, Rückgängig schickt ihn zurück zur Prüfung", () => {
  const h = uebernommenHinweis({ id: "t-suggestion-p1", title: "Folien schicken" }, async () => "Der Vorschlag steht wieder zur Prüfung.");
  assert.equal(h.text, "„Folien schicken“ übernommen.");
  assert.equal(typeof h.rueckgaengig, "function");
  assert.deepEqual(h.verweis, { text: "Ansehen", href: "/vorhaben?view=mine&task=t-suggestion-p1" });
  const vorschlaege = quelle("TaskSuggestions.tsx");
  assert.match(vorschlaege, /zeigeHinweis\(uebernommenHinweis\(task, async \(\) => \{ const antwort = await api\.zurPruefung\(task\.id\);/);
  assert.doesNotMatch(vorschlaege, /setNotice\(task \? "Aufgabe gespeichert\." : "Vorschlag verworfen\."\)/);
  const app = quelle("App.tsx");
  assert.match(app, /<TaskSuggestions projects=\{projects\} onTotal=\{setReviewTotal\} onPreview=\{\(\)=>openTask\(null\)\} onAccepted=\{\(\) => \{ loadProjects\(\); load\(\); \}\} \/>/);
});

test("„+ Aufgabe“: die neue Aufgabe steht in der Liste, nicht im Vollbild; der Hinweis bietet Öffnen und Rückgängig", () => {
  const h = angelegtHinweis({ id: "t1", title: "Hausarbeit hochladen" }, async () => undefined);
  assert.equal(h.text, "„Hausarbeit hochladen“ angelegt.");
  assert.equal(h.danach, "„Hausarbeit hochladen“ verworfen.");
  assert.deepEqual(h.verweis, { text: "Öffnen", href: "/vorhaben?view=mine&task=t1" });
  const app = quelle("App.tsx");
  const anlegen = app.slice(app.indexOf("async function create("), app.indexOf("// Jeder Klick am Kreis"));
  assert.doesNotMatch(anlegen, /openTask\(task\.id\)/);
  assert.match(anlegen, /zeigeHinweis\(angelegtHinweis\(task, async \(\) => \{ await api\.dropTask\(task\.id\); load\(\); \}\)\)/);
});
