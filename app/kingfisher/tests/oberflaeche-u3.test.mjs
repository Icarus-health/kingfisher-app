// Paket U, Teil U3 (Nachrichten, Kalender, Gedächtnis, Akte, Gespräche, Einstellungen, Prüfen): nur aufräumen.
// Zusicherungen: ein gefüllter Knopf, keine leeren Abschnitte, keine Doppelungen, kein Handbetrieb, Suche beim Tippen.
// Synthetische Daten.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { blickZeile, obenGenanntSatz, offenOhneBrauchtDich } from "../src/akteAnzeige.ts";
import { gefuellterZugang } from "../src/Einstellungen/gliederung.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const DATEIEN = /\/(ReviewPage|KnowledgeQuestions|BefundeAnsicht|MemorySearch|KreisKarten)\.tsx$/;
const server = await createServer({cacheDir: `/private/tmp/kf-u3-${process.pid}`, root: fileURLToPath(new URL("..", import.meta.url)), configFile: false,
  plugins: [{name: "u3-hooks", enforce: "pre", resolveId(id) { if (id === "virtual:u3-hooks") return "\0" + id; },
    load(id) { if (id === "\0virtual:u3-hooks") return "export const useState=(...a)=>globalThis.__u3.state(...a);export const useRef=(...a)=>globalThis.__u3.ref(...a);export const useEffect=(...a)=>globalThis.__u3.effect(...a);export const useCallback=f=>f;export const useMemo=f=>f();"; },
    transform(code, id) { if (DATEIEN.test(id)) return code.replace(/from (["'])react\1/g, 'from "virtual:u3-hooks"'); }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: "custom"});
after(() => server.close());
function nodes(n, p, out = []) { if (!n || typeof n !== "object") return out; if (p(n)) out.push(n); for (const c of [n.props?.children].flat(10)) nodes(c, p, out); return out; }
const text = (n) => n == null || n === false ? "" : typeof n === "object" ? [n.props?.children].flat(10).map(text).join("") : String(n);
function driver(Component, props) {
  const values = [], refs = [], deps = [], pending = []; let si = 0, ri = 0, ei = 0;
  const d = {state(v) { const i = si++; if (!(i in values)) values[i] = typeof v === "function" ? v() : v; return [values[i], n => values[i] = typeof n === "function" ? n(values[i]) : n]; },
    ref(v) { return refs[ri++] ??= {current: v}; },
    effect(fn, next) { const i = ei++; if (!deps[i] || !next || next.some((v, j) => v !== deps[i][j])) { deps[i] = next; pending.push(fn); } },
    render() { si = ri = ei = 0; globalThis.__u3 = d; return Component(props); },
    async flush() { for (let k = 0; k < 5; k++) { while (pending.length) pending.shift()(); await new Promise(r => setImmediate(r)); } }};
  return d;
}
async function mitFenster(lauf) {
  const alt = globalThis.window, altDoc = globalThis.document;
  globalThis.window = {location: {search: "", pathname: "/review", hash: ""}, addEventListener() {}, removeEventListener() {}, setTimeout, clearTimeout, scrollTo() {}};
  try { await lauf(); } finally { globalThis.window = alt; globalThis.document = altDoc; }
}

test("AK1: „Vermutlich offen“ zeigt nicht noch einmal, was oben unter „Braucht dich“ steht, und sagt es in einem Satz", () => {
  const offen = [{episode_id: "e1", text: "vielen Dank für Ihre Zusage", ziel: "z1"}, {episode_id: "e2", text: "schicken Sie mir den Termin", ziel: "z2"},
    {episode_id: "e3", text: "gleiches Ziel", ziel: "z9"}];
  const braucht = [{ziel: "gilt:e1", zeile: {episode_id: "e1", text: "vielen Dank für Ihre Zusage"}}, {ziel: "z9", zeile: null}];
  const {sichtbar, oben} = offenOhneBrauchtDich(offen, braucht);
  assert.deepEqual(sichtbar.map(e => e.episode_id), ["e2"]);
  assert.equal(oben, 2);
  // Gleiche Quelle, andere Stelle: bleibt stehen.
  assert.equal(offenOhneBrauchtDich([{episode_id: "e1", text: "anderer Satz"}], braucht).sichtbar.length, 1);
  assert.equal(offenOhneBrauchtDich(offen, null).oben, 0);
  assert.equal(obenGenanntSatz(1), "1 weiterer Punkt steht oben unter „Braucht dich“.");
  assert.equal(obenGenanntSatz(2), "2 weitere Punkte stehen oben unter „Braucht dich“.");
  assert.equal(obenGenanntSatz(0), null);
});

test("AK1: Auf einen Blick ist eine leise Zeile ohne Nullzähler, keine Kacheln", () => {
  assert.equal(blickZeile({offen: 2, termin: "28.10.", abgesagt: true, zuletzt: "18.9.2026"}),
    "2 Punkte vermutlich offen · nächster Termin 28.10. (abgesagt?) · zuletzt 18.9.2026");
  assert.equal(blickZeile({offen: 0, zuletzt: "16.9.2026"}), "zuletzt 16.9.2026");
  assert.equal(blickZeile({offen: 0}), null);
  const akte = quelle("AkteAbschnitte.tsx");
  assert.doesNotMatch(akte, /<ul className="akte-blick"/);
  assert.match(akte, /offenOhneBrauchtDich\(data\.offen\.eintraege, braucht\?\.eintraege\)/);
});

test("AK1: Für die eigene Person zeigt die Akte keinen Kreis", async () => {
  const {KreisKarte} = await server.ssrLoadModule("/src/KreisKarten.tsx");
  const {api} = await server.ssrLoadModule("/src/api.ts");
  const alt = api.kreis;
  const stand = (eigene) => ({sache: "person:a:lea@example.invalid", kreis: "unbestimmt", kreis_text: "offen", bestaetigt: false, bestaetigt_am: null, eigene,
    ohne_vorschlag: eigene, neuer_vorschlag: false, vorschlag: {kreis: "kontakte", kreis_text: "Kontakte", begruendung: "17 gemeinsame Termine."},
    wahlen: [{kreis: "kontakte", text: "Kontakte", wirkung: ""}]});
  try {
    for (const eigene of [true, false]) {
      api.kreis = async () => stand(eigene);
      const d = driver(KreisKarte, {sache: "person:a:lea@example.invalid"}); d.render(); await d.flush();
      const baum = d.render();
      if (eigene) assert.equal(baum, null, "eigene Person: keine Karte");
      else assert.match(text(baum), /Vorschlag: Kontakte/);
    }
  } finally { api.kreis = alt; }
});

test("E1: genau ein gefüllter Knopf unter Zugänge", () => {
  assert.equal(gefuellterZugang(true, 0, 0), null, "Einrichtung offen: nur „Einrichtung fortsetzen“");
  assert.equal(gefuellterZugang(false, null, null), null, "Stand fehlt: keiner");
  assert.equal(gefuellterZugang(false, 0, 0), "mail");
  assert.equal(gefuellterZugang(false, 1, 0), "calendar");
  assert.equal(gefuellterZugang(false, 1, 2), null);
  const zugaenge = quelle("Einstellungen/Zugaenge.tsx");
  assert.equal((zugaenge.match(/className="source-add source-add-text"/g) ?? []).length, 0, "kein fest gefüllter „hinzufügen“-Knopf");
  assert.match(zugaenge, /className=\{knopf\("mail"\)\}/);
  assert.match(zugaenge, /className=\{knopf\("calendar"\)\}/);
  const ordner = quelle("FolderSyncSettings.tsx");
  assert.match(ordner, /<section className="source-section document-import ordner-aufnahme"/, "gleich gebaut wie die Nachbarkarten");
  assert.match(ordner, /<h2>Dokumentenordner<\/h2>/);
});

test("P1: leere Abschnitte stehen nicht da; ist alles leer, steht ein Satz", () => mitFenster(async () => {
  const {ReviewPage} = await server.ssrLoadModule("/src/ReviewPage.tsx");
  const d = driver(ReviewPage, {recentConversation: null});
  let baum = d.render();
  assert.doesNotMatch(text(baum), /Nichts zu prüfen/, "erst wenn beide Abschnitte leer gemeldet haben");
  assert.doesNotMatch(text(baum), /Hier stehen offene Fragen/, "keine Einleitungsprosa");
  const klaerungen = nodes(baum, n => n.type?.name === "KnowledgeQuestions")[0], befunde = nodes(baum, n => n.type?.name === "WasAufgefallenIst")[0];
  assert.equal(klaerungen.props.leerAusblenden, true); assert.equal(befunde.props.leerAusblenden, true);
  klaerungen.props.onLeer(true); baum = d.render();
  assert.doesNotMatch(text(baum), /Nichts zu prüfen/);
  befunde.props.onLeer(true); baum = d.render();
  assert.match(text(baum), /Nichts zu prüfen\./);
  befunde.props.onLeer(false); baum = d.render();
  assert.doesNotMatch(text(baum), /Nichts zu prüfen/);
  assert.equal(nodes(baum, n => n.type === "section" && /drawer-card/.test(n.props.className ?? "")).length, 0, "keine Karte mit Leerfläche");
}));

test("P1: Wissensklärungen und Befunde blenden sich aus, wenn nichts offen ist", () => mitFenster(async () => {
  const {KnowledgeQuestions} = await server.ssrLoadModule("/src/KnowledgeQuestions.tsx");
  const {WasAufgefallenIst} = await server.ssrLoadModule("/src/BefundeAnsicht.tsx");
  const {api} = await server.ssrLoadModule("/src/api.ts");
  const alt = {memoryQuestions: api.memoryQuestions, lintBefunde: api.lintBefunde};
  try {
    api.memoryQuestions = async () => ({items: [], truncated: false});
    api.lintBefunde = async () => ({befunde: [], zusammenfassung: {offen: 0, wichtig: 0, letzter_lauf: null}});
    for (const [Komponente, name] of [[KnowledgeQuestions, "Klärungen"], [WasAufgefallenIst, "Befunde"]]) {
      const gemeldet = [];
      const leise = driver(Komponente, {active: true, leerAusblenden: true, onLeer: v => gemeldet.push(v)}); leise.render(); await leise.flush();
      assert.equal(leise.render(), null, `${name}: leer und ausgeblendet`); await leise.flush();
      assert.equal(gemeldet.at(-1), true, `${name}: meldet leer`);
      const voll = driver(Komponente, {active: true}); voll.render(); await voll.flush();
      assert.notEqual(voll.render(), null, `${name}: ohne leerAusblenden bleibt der Abschnitt (Einstellungen, Heute)`);
    }
  } finally { Object.assign(api, alt); }
}));

test("M1: ein Titel, kein Hilfe-Aufklapper, kein Suchen-Knopf; die Suche läuft beim Tippen", () => mitFenster(async () => {
  const {MemorySearch} = await server.ssrLoadModule("/src/MemorySearch.tsx");
  const {api} = await server.ssrLoadModule("/src/api.ts");
  const alt = api.memorySearch; const gesucht = [];
  api.memorySearch = async (q) => { gesucht.push(q); return {query: q, items: [], note_items: [], scope: "", truncated: false}; };
  try {
    const props = {graph: {nodes: [], edges: []}, query: "", page: 1, onQueryChange() {}, onPageChange() {}, onOpen() {}};
    const d = driver(MemorySearch, props); let baum = d.render(); await d.flush(); baum = d.render();
    assert.equal(nodes(baum, n => n.type === "h1").length, 0, "der Seitentitel „Gedächtnis“ reicht");
    assert.equal(nodes(baum, n => n.type === "details").length, 0, "kein „So funktioniert die Suche“");
    assert.equal(nodes(baum, n => n.type === "button" && /Suchen/.test(text(n))).length, 0, "kein eigener Suchen-Knopf");
    assert.equal(nodes(baum, n => n.type?.name === "GedaechtnisLeer").length, 1, "leeres Gedächtnis: ein Satz mit Weg");
    props.query = "Brandl"; d.render(); await d.flush(); d.render(); await d.flush();
    assert.deepEqual(gesucht, [], "entprellt: nicht bei jedem Zeichen sofort");
    await new Promise(r => setTimeout(r, 400)); d.render(); await d.flush(); d.render(); await d.flush();
    assert.deepEqual(gesucht, ["Brandl"], "nach dem Tippen sucht sie von selbst in den Originalen");
  } finally { api.memorySearch = alt; }
}));

test("K1, N1: kein Handbetrieb und keine zweite Kalenderansicht im Quelltext", () => {
  const kalender = quelle("CalendarPage.tsx"), nachrichten = quelle("Messages.tsx"), leser = quelle("MailReader.tsx");
  assert.doesNotMatch(kalender, /Ansicht aktualisieren|Weitere Aktionen|type="date"|Datum wählen/);
  assert.doesNotMatch(nachrichten, /Lokale Nachrichtenliste aktualisieren|Stand und Konten/);
  assert.doesNotMatch(leser, /aktueller Postfachstand unbekannt|Quelle vom letzten Speichern/);
  assert.equal((kalender.match(/className="primary-action"/g) ?? []).length, 1, "ein gefüllter Knopf: + Termin");
});
