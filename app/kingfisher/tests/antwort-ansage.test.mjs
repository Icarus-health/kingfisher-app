// Die fertige Antwort wird angesagt, und der Fokus bleibt im Eingabefeld (Persona-Prüfung, Paket B, B1, 27.10.2026).
// Vorher: Ein Vorleser sagte „Kingfisher antwortet …“ und danach nichts; der Fokus lag nach der Antwort auf body.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ANSAGE_ZEICHEN, anfang, antwortAnsage, klartext } from "../src/antwortAnsage.ts";
import { ANSAGE_PAUSE_MS, ANSAGE_STEHT_MS, AnsageOrt } from "../src/grundlage/ansageOrt.ts";
import { istBeantwortet, merkeBeantwortet, vergissBeantwortet } from "../src/wartenImGespraech.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const antwort = (content, extra = {}) => ({ role: "assistant", content, status: "complete", ...extra });

function testUhr() {
  let jetzt = 0, naechste = 1;
  const offen = new Map();
  return {
    setTimeout(f, ms) { const id = naechste++; offen.set(id, { f, um: jetzt + ms }); return id; },
    clearTimeout(id) { offen.delete(id); },
    vor(ms) { jetzt += ms; for (const [id, t] of [...offen]) if (t.um <= jetzt) { offen.delete(id); t.f(); } },
  };
}

test("angesagt wird der Anfang der Antwort, ohne Sternchen, Belegnummern und Verweisziele", () => {
  assert.equal(klartext("**Ja.** Die Frist ist jetzt der *15. November* [1][2]."), "Ja. Die Frist ist jetzt der 15. November.");
  assert.equal(klartext("## Stand\n- [Antrag](https://example.invalid) liegt vor"), "Stand Antrag liegt vor");
  assert.equal(antwortAnsage([{ role: "user", content: "Frage?", status: "complete" }, antwort("Ja, am 15. November.")]),
    "Kingfisher antwortet: Ja, am 15. November.");
});

test("lang: ganze Sätze bis etwa zwei kurze Sätze; ein einziger langer Satz am Wort gekürzt", () => {
  const lang = "Die Frist wurde geändert. Sie liegt jetzt am 15. November 2026. " + "Danach folgen Einzelheiten zum Antrag. ".repeat(10);
  const satz = anfang(lang);
  assert.ok(satz.length <= ANSAGE_ZEICHEN, satz);
  assert.ok(satz.startsWith("Die Frist wurde geändert. Sie liegt jetzt am 15. November 2026."), satz);
  assert.match(satz, /[.!?]$/, "endet an einem Satzende");
  const einSatz = anfang("wort ".repeat(100).trim());
  assert.ok(einSatz.length <= ANSAGE_ZEICHEN + 2 && einSatz.endsWith(" …"), einSatz);
});

test("Satzantwort, Rückfrage, Fehler; nach einer eigenen Frage nichts", () => {
  const satz = antwort("ignoriert", { metadata: { context: { satzantwort: { saetze: [{ text: "Die Frist ist der 15. November." }, { text: "Das steht in der Mail von Anna." }] } } } });
  assert.equal(antwortAnsage([satz]), "Kingfisher antwortet: Die Frist ist der 15. November. Das steht in der Mail von Anna.");
  assert.match(antwortAnsage([antwort("Welche Stiftung meinst du?", { metadata: { context: { clarification_choices: [{ label: "A" }] } } })]), /^Kingfisher fragt zurück: Welche Stiftung/);
  assert.equal(antwortAnsage([antwort("", { status: "error" })]), "Die Antwort ist fehlgeschlagen. Unter der Nachricht steht „Wiederholen“.");
  assert.equal(antwortAnsage([{ role: "user", content: "Noch da?", status: "complete" }]), null);
  assert.equal(antwortAnsage([]), null);
});

test("der Ort für Ansagen: höflich, einmal, ein gleicher Satz wird wieder angesagt, danach räumt er sich", () => {
  const uhr = testUhr(); const ort = new AnsageOrt(uhr);
  let meldungen = 0; ort.abonnieren(() => meldungen++);
  ort.sageAn("Kingfisher antwortet: Ja.");
  assert.equal(ort.stand(), "", "erst leer: Vorleser sagen nur Änderungen an");
  uhr.vor(ANSAGE_PAUSE_MS);
  assert.equal(ort.stand(), "Kingfisher antwortet: Ja.");
  ort.sageAn("Kingfisher antwortet: Ja.");
  assert.equal(ort.stand(), "");
  uhr.vor(ANSAGE_PAUSE_MS);
  assert.equal(ort.stand(), "Kingfisher antwortet: Ja.");
  uhr.vor(ANSAGE_STEHT_MS);
  assert.equal(ort.stand(), "");
  assert.ok(meldungen >= 4);
  const anzeige = quelle("grundlage/Ansage.tsx");
  assert.match(anzeige, /role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(quelle("main.tsx"), /<AnsageAnzeige \/>/, "der Ort steht über allen Seiten und überlebt den Wechsel ins Gespräch");
});

test("das Gespräch sagt jede fertige Antwort an: senden, neu beantworten, wiederholen und nach dem Start aus der Liste", () => {
  const app = quelle("App.tsx");
  assert.match(app, /const antwort = await api\.sendMessage\(id, message, clarification\);\s*setData\(antwort\);\s*[^\n]*\n\s*if \(live\.current\) antwortAnsagen\(antwort\.messages\);/);
  assert.match(app, /const neu = await api\.sendMessage\(id, original, \{ newQuestion: true \}\);\s*setData\(neu\);\s*if \(live\.current\) antwortAnsagen\(neu\.messages\);/);
  assert.match(app, /const neu = await api\.retryMessage\(id, messageId\);\s*setData\(neu\);\s*if \(live\.current\) antwortAnsagen\(neu\.messages\);/);
  assert.match(app, /merkeBeantwortet\(id\);\s*if \(live\.current\) navigate\(`\/conversations\/\$\{id\}`\);/);
  assert.match(app, /if \(art === "antwort"\) antwortAnsagen\(data\.messages\)/);
  // Der Zwischenstand wird nicht Wort für Wort vorgelesen: Die Nachrichtenliste selbst ist keine Live-Region.
  assert.doesNotMatch(app, /<div className="messages"[^>]*aria-live/);
  assert.match(quelle("GespraechWarten.tsx"), /role="status" aria-live="polite">\s*<span className="warte-punkt" aria-hidden="true" \/>\{warteSatz\(stand\)\}/);
});

test("Fokus: nach dem Senden im Eingabefeld, auch mit dem Sendeknopf und wenn die Frage von einer anderen Seite kam", () => {
  const bar = quelle("CommandBar.tsx");
  assert.match(bar, /if \(conversation && input\.current && document\.activeElement !== input\.current\) input\.current\.focus\(\{ preventScroll: true \}\);/);
  const app = quelle("App.tsx");
  assert.match(app, /const ankunft = useRef<"frage" \| "antwort" \| null>\(istBeantwortet\(id\) \? "antwort" : null\);/);
  assert.match(app, /if \(frage\) \{ ankunft\.current = "frage";/);
  assert.match(app, /document\.querySelector<HTMLTextAreaElement>\("\.workspace-chat \.thread-command textarea"\)/);
  assert.match(app, /if \(feld && !feld\.disabled\) \{ feld\.focus\(\{ preventScroll: true \}\);/);
  merkeBeantwortet("g-1");
  assert.equal(istBeantwortet("g-1"), true);
  assert.equal(istBeantwortet("g-1"), true, "Nachsehen verbraucht nichts (StrictMode rendert doppelt)");
  vergissBeantwortet("g-1");
  assert.equal(istBeantwortet("g-1"), false);
});
