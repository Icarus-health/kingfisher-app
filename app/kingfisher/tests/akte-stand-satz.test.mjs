// Paket V2 (Akte): ein Satz Stand unter dem Namen, ohne Modell und ohne erfundenen Inhalt; keine Doppelungen darunter.
// Synthetische Daten (Welt Lea Hartmann, Stichtag 29.09.2026).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { naechstesSatz, standSatz, termineObenGenannt } from "../src/akteAnzeige.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const JETZT = new Date("2026-09-29T07:31:00+02:00");
const ABSAGE = { art: "Änderung", titel: "Absage Workshop am 28. Oktober", episode_id: "e-absage", participants: ["Silke Vogt <s.vogt@akademie-taunus.example>"],
  occurred_at: "2026-09-17T09:12:00+02:00", recorded_at: "2026-09-29T07:30:00+02:00", text: "leider müssen wir den Workshop am 28. Oktober absagen.", gekuerzt: false };
const TERMIN = { episode_id: "e-termin", titel: "Workshop Mangelernährung, Akademie Taunus", start: "2026-10-28T10:00:00+01:00", ort: "Bad Homburg",
  vermutlich_abgesagt: ABSAGE, ziel: "t:e-termin", entscheidung: null };
const satz = (x = {}) => standSatz({ name: "Silke Vogt", jetzt: JETZT, stand: ABSAGE, verlauf: [], braucht: 2, termin: TERMIN, frist: null, ...x });

test("V2: der Stand-Satz nennt Art, Tag und Titel der jüngsten Zeile unter „Stand“ und das Nächste", () => {
  const s = satz();
  assert.equal(s.text, "Änderung am 17.9.: Absage Workshop am 28. Oktober. 2 Punkte brauchen dich.");
  assert.deepEqual([s.vor, s.titel, s.nach, s.episode_id, s.aus], ["Änderung am 17.9.: ", "Absage Workshop am 28. Oktober", ".", "e-absage", "stand"]);
  // In der Akte der Organisation steht, wer es schrieb; in der eigenen Akte der Person wäre der Name doppelt.
  assert.equal(satz({ name: "Akademie Taunus" }).text, "Änderung am 17.9.: Absage Workshop am 28. Oktober (Silke Vogt). 2 Punkte brauchen dich.");
  assert.equal(satz({ braucht: 1 }).naechstes, "1 Punkt braucht dich.");
});

test("V2: der Satz erfindet nichts – nur Felder der Akte, sonst kein Satz", () => {
  assert.equal(standSatz({ name: "X", jetzt: JETZT, stand: null, verlauf: [], braucht: 0, termin: null, frist: null }), null);
  const s = satz({ braucht: 0, termin: null });
  assert.equal(s.naechstes, null, "eine Null sagt nichts");
  assert.equal(s.text, "Änderung am 17.9.: Absage Workshop am 28. Oktober.");
  // Jedes Wort stammt aus Art, Tag, Titel oder Absender (und den festen Bindewörtern).
  const erlaubt = new Set(["Änderung", "am", "17.9.:", "(Silke", "Vogt).", ...ABSAGE.titel.split(" "), "Oktober."]);
  for (const wort of satz({ name: "Akademie Taunus", braucht: 0, termin: null }).text.split(" ")) assert.ok(erlaubt.has(wort), wort);
  // Ohne Quelldatum zählt die Erfassung, und so heißt sie auch; ein anderes Jahr steht dabei.
  assert.equal(satz({ stand: { ...ABSAGE, occurred_at: null }, braucht: 0, termin: null }).vor, "Änderung, erfasst am 29.9.: ");
  assert.equal(satz({ stand: { ...ABSAGE, occurred_at: "2025-09-17T09:00:00+02:00" }, braucht: 0, termin: null }).vor, "Änderung am 17.9.2025: ");
  assert.equal(satz({ stand: { ...ABSAGE, titel: "Rechnung bezahlt?" }, braucht: 0, termin: null }).text, "Änderung am 17.9.: Rechnung bezahlt?");
});

test("V2: ohne „Stand“ die jüngste Quelle bis heute, nicht ein Termin, der noch kommt", () => {
  const verlauf = [{ episode_id: "e-k", titel: "Gespräch Rheinauenblick", datum: "2026-09-30T14:00:00+02:00", quelle_art: "event" },
    { episode_id: "e-p", titel: "Projekttreffen Handbuch", datum: "2026-09-16T10:00:00+02:00", quelle_art: "event" },
    { episode_id: "e-m", titel: "Re: Handbuch", datum: "2026-09-10T10:00:00+02:00", quelle_art: "message" }];
  const s = standSatz({ name: "Lea Hartmann", jetzt: JETZT, stand: null, verlauf, braucht: 0, termin: { start: "2026-09-30T14:00:00+02:00", vermutlich_abgesagt: null }, frist: null });
  assert.equal(s.text, "Zuletzt am 16.9.: Termin Projekttreffen Handbuch. Nächster Termin am 30.9.");
  assert.equal(s.aus, "verlauf");
  assert.equal(s.episode_id, "e-p");
});

test("V2: das Nächste – abgesagter Termin vor Frist und Termin, ein Tag trägt den Schlusspunkt", () => {
  const frist = { datum: "2026-10-12" };
  assert.equal(naechstesSatz({ braucht: 0, termin: TERMIN, frist, jetzt: JETZT }), "Nächster Termin am 28.10. vermutlich abgesagt.");
  assert.equal(naechstesSatz({ braucht: 0, termin: { ...TERMIN, entscheidung: "erledigt" }, frist, jetzt: JETZT }), "Nächster Termin am 28.10. abgesagt.");
  assert.equal(naechstesSatz({ braucht: 0, termin: { ...TERMIN, vermutlich_abgesagt: null }, frist, jetzt: JETZT }), "Nächste Frist am 12.10.");
  assert.equal(naechstesSatz({ braucht: 0, termin: { ...TERMIN, vermutlich_abgesagt: null }, frist: { datum: "2026-11-12" }, jetzt: JETZT }), "Nächster Termin am 28.10.");
  assert.equal(naechstesSatz({ braucht: 0, termin: null, frist: { datum: "2027-01-12" }, jetzt: JETZT }), "Nächste Frist am 12.1.2027.");
  assert.deepEqual([...termineObenGenannt([{ art: "abgesagter_termin", episode_id: "e-termin" }, { art: "gilt_noch", episode_id: "e-x" }])], ["e-termin"]);
  assert.equal(termineObenGenannt(null).size, 0);
});

// Die Akte selbst, flach gerendert (Teilbausteine bleiben Elemente mit ihren Props), mit einer erfundenen Antwort.
const server = await createServer({cacheDir: `/private/tmp/kf-v2-${process.pid}`, root: fileURLToPath(new URL("..", import.meta.url)), configFile: false,
  plugins: [{name: "v2-hooks", enforce: "pre", resolveId(id) { if (id === "virtual:v2-hooks") return "\0" + id; },
    load(id) { if (id === "\0virtual:v2-hooks") return "export const useState=(...a)=>globalThis.__v2.state(...a);export const useRef=(...a)=>globalThis.__v2.ref(...a);export const useEffect=(...a)=>globalThis.__v2.effect(...a);export const useCallback=(...a)=>globalThis.__v2.callback(...a);export const useMemo=f=>f();"; },
    transform(code, id) { if (/\/AkteAbschnitte\.tsx$/.test(id)) return code.replace(/from (["'])react\1/g, 'from "virtual:v2-hooks"'); }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: "custom"});
after(() => server.close());
function nodes(n, p, out = []) { if (!n || typeof n !== "object") return out; if (p(n)) out.push(n); for (const c of [n.props?.children].flat(10)) nodes(c, p, out); return out; }
const text = (n) => n == null || n === false ? "" : typeof n === "object" ? [n.props?.children].flat(10).map(text).join("") : String(n);
const gleich = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
function driver(Component, props) {
  const values = [], refs = [], deps = [], rueck = [], pending = []; let si = 0, ri = 0, ei = 0, ci = 0;
  const d = {state(v) { const i = si++; if (!(i in values)) values[i] = typeof v === "function" ? v() : v; return [values[i], n => values[i] = typeof n === "function" ? n(values[i]) : n]; },
    ref(v) { return refs[ri++] ??= {current: v}; },
    callback(fn, next) { const i = ci++; if (!rueck[i] || !gleich(rueck[i][1], next)) rueck[i] = [fn, next]; return rueck[i][0]; },
    effect(fn, next) { const i = ei++; if (!deps[i] || !next || !gleich(deps[i], next)) { deps[i] = next; pending.push(fn); } },
    render() { si = ri = ei = ci = 0; globalThis.__v2 = d; return Component(props); },
    async flush() { for (let k = 0; k < 5; k++) { d.render(); while (pending.length) pending.shift()(); await new Promise(r => setImmediate(r)); } }};
  return d;
}
const leer = { eintraege: [], gesamt: 0 };
const VORHER = { ...ABSAGE, art: "Angabe", titel: "Workshop am 28. Oktober", episode_id: "e-alt", occurred_at: "2026-07-01T09:00:00+02:00" };
const AKTE = { sache: "person:a:s.vogt@akademie-taunus.example", art: "person", art_text: "Person", name: "Silke Vogt <s.vogt@akademie-taunus.example>",
  stand: JETZT.toISOString(), aus_zwischenspeicher: false, quellen: { gesamt: 2, beruecksichtigt: 2, archiviert: 0, begrenzt: false, abschnitte_abgeschnitten: false },
  verlauf: { eintraege: [{ episode_id: "e-absage", titel: ABSAGE.titel, datum: ABSAGE.occurred_at, grundlagen: ["anker"], archiviert: false, art: "Änderung", text: ABSAGE.text, gekuerzt: false, quelle_art: "message" }], gesamt: 1 },
  offen: { eintraege: [], gesamt: 0, vermutlich: true, erledigt: leer },
  fristen: { kommend: [], verstrichen: [], ersetzt: [], gesamt: { kommend: 0, verstrichen: 0, ersetzt: 0 }, ohne_datum: leer, quellenangaben: leer },
  stand_der_dinge: { aktuell: ABSAGE, vorher: [VORHER], vorher_gesamt: 1, weitere: [], weitere_gesamt: 0 },
  beteiligte: leer, termine: { kommend: [TERMIN], vergangen: [], gesamt: { kommend: 1, vergangen: 0 } }, aufgaben: leer,
  einordnung: { eingeordnet: 2, offen: 0, ausgeschlossen: 0 }, berechnung: { offen: 0, berechnet: 2 },
  braucht_dich: { eintraege: [{ art: "abgesagter_termin", ziel: "t:e-termin", satz: "„Workshop“ am 28. Oktober ist laut „Absage“ vom 17. September abgesagt, steht aber noch in deinem Kalender.",
    zeile: null, laut: ABSAGE, episode_id: "e-termin", wahl: [{ entscheidung: "erledigt", text: "Erledigt" }] }], gesamt: 1 }, zeitstrahl: null };

async function akteRendern(daten) {
  const {AkteAnsicht} = await server.ssrLoadModule("/src/AkteAbschnitte.tsx");
  const {api} = await server.ssrLoadModule("/src/api.ts");
  const alt = [api.akte, api.personProfile];
  api.akte = async () => structuredClone(daten); api.personProfile = async () => { throw new Error("kein Profil"); };
  try { const d = driver(AkteAnsicht, {sache: daten.sache, mitKopf: true}); await d.flush(); return d.render(); }
  finally { [api.akte, api.personProfile] = alt; }
}

test("V2: Kopf mit Stand-Satz; „Stand“ wiederholt ihn nicht, nur Früheres ist aufklappbar", async () => {
  const baum = await akteRendern(AKTE);
  const [kopf] = nodes(baum, n => n.type?.name === "StandKopf");
  assert.ok(kopf, "Stand-Satz im Kopf");
  assert.equal(kopf.props.satz.text, "Änderung am 17.9.: Absage Workshop am 28. Oktober. 1 Punkt braucht dich.");
  assert.equal(nodes(baum, n => n.type?.name === "Blick" || n.props?.className === "akte-blick").length, 0, "keine zweite Zeile unter dem Namen");
  // Ohne Datiertes bleibt die leise Zeile „Auf einen Blick“ (Gegenprobe, damit die Suche nach ihr etwas findet).
  const leerKopf = await akteRendern({ ...AKTE, stand_der_dinge: { aktuell: null, vorher: [], vorher_gesamt: 0, weitere: [], weitere_gesamt: 0 }, verlauf: { eintraege: [], gesamt: 0 } });
  assert.equal(nodes(leerKopf, n => n.type?.name === "StandKopf").length, 0);
  assert.equal(nodes(leerKopf, n => n.type?.name === "Blick").length, 1);
  const zeilen = nodes(baum, n => n.type?.name === "Zeile").map(n => n.props.zeile.episode_id);
  assert.ok(!zeilen.includes("e-absage"), "die jüngste Stand-Zeile steht schon im Kopf");
  assert.ok(zeilen.includes("e-alt"), "Früheres bleibt aufklappbar");
  const stand = nodes(baum, n => n.type?.name === "Teil" && n.props.titel === "Stand")[0];
  assert.match(text(stand), /Vor dem 17\.9\.2026 \(1\)/);
  // Ohne früheren Stand fällt der Abschnitt ganz weg.
  const ohne = await akteRendern({ ...AKTE, stand_der_dinge: { ...AKTE.stand_der_dinge, vorher: [], vorher_gesamt: 0 } });
  assert.equal(nodes(ohne, n => n.type?.name === "Teil" && n.props.titel === "Stand").length, 0);
});

test("V2: ein abgesagter Termin aus „Braucht dich“ steht unter „Termine“ nur als leise Zeile ohne Zitat", async () => {
  const baum = await akteRendern(AKTE);
  const termine = nodes(baum, n => n.type?.name === "Teil" && n.props.titel === "Termine")[0];
  const [zeile] = nodes(termine, n => n.type === "article");
  assert.match(zeile.props.className, /akte-termin-oben/);
  assert.equal(nodes(zeile, n => n.type === "blockquote" || n.props?.className === "mappe-mehr").length, 0, "kein Zitat");
  assert.doesNotMatch(text(zeile), /leider müssen wir/);
  assert.match(text(zeile), /vermutlich abgesagt, steht oben unter „Braucht dich“/);
  // Steht er nicht oben (etwa nach „Erledigt“), bleibt die Begründung mit Zitat.
  const unten = await akteRendern({ ...AKTE, braucht_dich: leer });
  const [voll] = nodes(nodes(unten, n => n.type?.name === "Teil" && n.props.titel === "Termine")[0], n => n.type === "article");
  assert.match(text(voll), /Vermutlich abgesagt laut „leider müssen wir/);
});

test("V2: schmal steht das Bild klein über dem Namen, der Name in voller Breite", () => {
  const css = quelle("AkteAbschnitte.css");
  const schmal = css.slice(css.indexOf("@media (max-width: 699px)"));
  assert.match(schmal, /\.akte\.akte-seite \.akte-kopf \{ flex-direction: column;/);
  const groesse = schmal.match(/\.akte\.akte-seite \.akte-kopf \.memory-avatar-editor \.memory-avatar-large \{ width: (\d+)px; height: (\d+)px;/);
  assert.ok(groesse && Number(groesse[1]) <= 56 && Number(groesse[2]) <= 56, "Bild höchstens 56 px");
  assert.match(schmal, /\.akte-achse span:nth-child\(even\) \{ display: none; \}/, "Monatsmarken liegen schmal nicht aufeinander");
});
