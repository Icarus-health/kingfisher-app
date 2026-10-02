// Fassung und Update-Angebot (docs/53-download-und-updates.md): wann der Hinweis erscheint, welcher Weg gilt (Knopf in
// der App, neue App laden, App öffnen), was über die Brücke geht und die einmalige Rückmeldung nach dem Neuladen.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  MERKER, SATZ_FEHLGESCHLAGEN, SATZ_OHNE_APP, SATZ_PRUEFEN, SATZ_VORHER, angebot, auftrag, brueckeFinden, fassungText,
  merken, nachgesehenText, rueckmeldung, zuletztText,
} from "../src/fassungsAngebot.ts";

const manifest = (mehr = {}) => ({ fassung: "1.2.0", datum: "2026-10-02", image: "ghcr.io/icarus-health/kingfisher-app:1.2.0",
  dmg: "https://github.com/Icarus-health/kingfisher-app/releases/download/v1.2.0/Kingfisher.dmg",
  hinweise: ["Das Briefing nennt Geburtstage.", "Akten als Ordner."], app_mindestens: "1.0.0", ...mehr });
const stand = (mehr = {}) => ({ fassung: "1.0.0", neueste: manifest(), update_verfuegbar: true, app_update_noetig: false,
  geprueft_um: "2026-10-02T06:00:00+00:00", pruefen: true, download_seite: "https://icarus-health.github.io/kingfisher-app/", ...mehr });

class Ablage {
  constructor() { this.daten = new Map(); }
  getItem(k) { return this.daten.has(k) ? this.daten.get(k) : null; }
  setItem(k, v) { this.daten.set(k, String(v)); }
  removeItem(k) { this.daten.delete(k); }
}

test("ohne neue Fassung kein Hinweis", () => {
  assert.equal(angebot(null, true), null);
  assert.equal(angebot(stand({ update_verfuegbar: false }), true), null);
  assert.equal(angebot(stand({ neueste: null }), true), null);
});

test("in der App: erste Neuerung, ein Satz vorher, der Knopf", () => {
  const a = angebot(stand(), true);
  assert.deepEqual(a, { titel: "Neue Fassung 1.2.0 ist da: Das Briefing nennt Geburtstage.", weg: "knopf", satz: SATZ_VORHER });
  assert.equal(SATZ_VORHER, "Kingfisher sichert vorher deine Daten und ist etwa eine Minute weg.");
  assert.equal(angebot(stand({ neueste: manifest({ hinweise: [] }) }), true).titel, "Neue Fassung 1.2.0 ist da.");
});

test("im Browser statt des Knopfs der Satz zur App", () => {
  const a = angebot(stand(), false);
  assert.equal(a.weg, "app_oeffnen");
  assert.equal(a.satz, "Öffne Kingfisher über die App, um zu aktualisieren.");
  assert.equal(SATZ_OHNE_APP, a.satz);
});

test("braucht die Fassung eine neue App, gibt es keinen Knopf, sondern den Weg zur Download-Seite", () => {
  for (const bruecke of [true, false]) {
    const a = angebot(stand({ app_update_noetig: true }), bruecke);
    assert.equal(a.weg, "app_laden");
    assert.match(a.satz, /neue App/);
  }
});

test("über die Brücke gehen genau Aktion, Fassung und Bild", () => {
  assert.deepEqual(auftrag(manifest()), { aktion: "aktualisieren", fassung: "1.2.0", image: "ghcr.io/icarus-health/kingfisher-app:1.2.0" });
});

test("die Brücke wird nur im Fenster der App gefunden", () => {
  const nachrichten = [];
  const fenster = { webkit: { messageHandlers: { kingfisher: { postMessage: n => nachrichten.push(n) } } } };
  const b = brueckeFinden(fenster);
  b.postMessage({ x: 1 });
  assert.deepEqual(nachrichten, [{ x: 1 }]);
  assert.equal(brueckeFinden({}), null);
  assert.equal(brueckeFinden({ webkit: { messageHandlers: {} } }), null);
  assert.equal(brueckeFinden({ webkit: { messageHandlers: { kingfisher: {} } } }), null);
  assert.equal(brueckeFinden(undefined), null);
  const boese = {}; Object.defineProperty(boese, "webkit", { get() { throw new Error("nein"); } });
  assert.equal(brueckeFinden(boese), null);
  assert.equal(brueckeFinden(), null);   // node hat kein webkit
});

test("Rückmeldung nach dem Neuladen: einmal, und je nachdem, welche Fassung läuft", () => {
  const ablage = new Ablage();
  merken("1.2.0", "1.0.0", ablage);
  assert.equal(rueckmeldung("1.2.0", ablage), "Kingfisher ist jetzt auf Fassung 1.2.0.");
  assert.equal(rueckmeldung("1.2.0", ablage), "", "nur einmal");
  merken("1.2.0", "1.0.0", ablage);
  assert.equal(rueckmeldung("1.0.0", ablage), SATZ_FEHLGESCHLAGEN);
  assert.equal(SATZ_FEHLGESCHLAGEN, "Das Update hat nicht geklappt; deine Daten sind gesichert.");
  assert.equal(ablage.getItem(MERKER), null);
  merken("1.2.0", "1.0.0", ablage);
  assert.equal(rueckmeldung("1.1.0", ablage), "");
  ablage.setItem(MERKER, "{kaputt");
  assert.equal(rueckmeldung("1.2.0", ablage), "");
  assert.equal(rueckmeldung("1.2.0", new Ablage()), "");
});

test("ohne Ablage (privates Fenster) wirft nichts", () => {
  const kaputt = { getItem() { throw new Error("gesperrt"); }, setItem() { throw new Error("gesperrt"); }, removeItem() { throw new Error("gesperrt"); } };
  assert.doesNotThrow(() => merken("1.2.0", "1.0.0", kaputt));
  assert.equal(rueckmeldung("1.2.0", kaputt), "");
  assert.doesNotThrow(() => merken("1.2.0", "1.0.0", null));
  assert.equal(rueckmeldung("1.2.0", null), "");
  assert.doesNotThrow(() => merken("1.2.0", "1.0.0"));
});

test("„Jetzt nachsehen“ antwortet immer mit einem Satz", () => {
  assert.equal(nachgesehenText(stand({ erreicht: true })), "Neue Fassung 1.2.0 ist da.");
  assert.equal(nachgesehenText(stand({ erreicht: true, update_verfuegbar: false })), "Kingfisher ist auf dem neuesten Stand.");
  assert.match(nachgesehenText(stand({ erreicht: false })), /nicht erreichbar/);
});

test("Fassung und Zeitpunkt für Menschen", () => {
  assert.equal(fassungText("1.0.0"), "Fassung 1.0.0");
  assert.equal(fassungText("entwicklung"), "Aus dem Quelltext gebaut, ohne Fassungsnummer");
  assert.equal(zuletztText(null), "Noch nie nachgesehen.");
  assert.equal(zuletztText("2026-10-02T06:05:00+00:00", "Europe/Berlin"), "Zuletzt nachgesehen am 2. Oktober um 8:05.");
  assert.equal(zuletztText("unsinn"), "");
});

test("der Satz zur täglichen Prüfung sagt, wen Kingfisher fragt und dass über dich nichts hinausgeht", () => {
  assert.equal(SATZ_PRUEFEN, "Einmal am Tag fragt Kingfisher bei GitHub, ob es eine neue Fassung gibt. Über dich geht dabei nichts hinaus.");
});

test("Heute zeigt den Hinweis, Kingfisher und du die Einstellung, Für Techniker den Befehl", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /<FassungHeute \/>/);
  const ich = readFileSync(new URL("../src/Einstellungen/Ich.tsx", import.meta.url), "utf8");
  assert.match(ich, /<FassungEinstellung \/>/);
  const technik = readFileSync(new URL("../src/Einstellungen/Technik.tsx", import.meta.url), "utf8");
  assert.match(technik, /make aktualisieren/);
  const fassung = readFileSync(new URL("../src/Fassung.tsx", import.meta.url), "utf8");
  // Kein gefüllter Knopf auf Heute: Der Tag ist der wichtigste Gegenstand der Ansicht.
  assert.doesNotMatch(fassung, /primary-action/);
  assert.match(fassung, /Jetzt aktualisieren/);
  assert.match(fassung, /Jetzt nachsehen/);
  assert.match(fassung, /Nach neuen Fassungen sehen/);
});
