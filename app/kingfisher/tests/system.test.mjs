// Texte passend zum System, auf dem Kingfisher läuft (Fremdprobe, Befund 18): eine Hilfsfunktion (src/system.ts), und
// kein fester Mac-Satz mehr in den Dateien der Oberfläche, außer wo es ihn nur auf dem Mac gibt.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { UNBEKANNT, ausstattungUnbekannt, eingabegeraetAus, fuerSystem, nurAufDemMac, tastenHinweis, wo } from "../src/system.ts";

const SRC = new URL("../src/", import.meta.url);

test("{Rechner} wird auf dem Mac „Mac“, sonst „Rechner“; bis die Angabe da ist, gilt „Rechner“", () => {
  assert.equal(fuerSystem("Auf diesem {Rechner} gespeichert", { art: "mac" }), "Auf diesem Mac gespeichert");
  for (const art of ["docker", "linux", "windows", "rechner"]) {
    assert.equal(fuerSystem("Auf diesem {Rechner} gespeichert, am {Rechner} angemeldet", { art }), "Auf diesem Rechner gespeichert, am Rechner angemeldet");
  }
  assert.equal(UNBEKANNT.art, "rechner");
  assert.equal(fuerSystem("am {Rechner}", UNBEKANNT), "am Rechner");
});

test("was nur ein Mac-Helfer kann, sagt auf dem Mac, was zu tun ist, und sonst ehrlich, dass es das hier nicht gibt", () => {
  assert.match(nurAufDemMac({ art: "mac" }, "Die Sicherung"), /^Die Sicherung erledigt ein Helfer der Kingfisher-App\. .*öffne die Kingfisher-App neu\.$/);
  assert.equal(nurAufDemMac({ art: "docker" }, "Die Sicherung"), "Die Sicherung gibt es nur in der Kingfisher-App auf dem Mac, nicht im Browser mit Docker.");
  assert.equal(nurAufDemMac({ art: "linux" }, "Die Ordnerwahl im Fenster"), "Die Ordnerwahl im Fenster gibt es nur in der Kingfisher-App auf dem Mac, nicht unter Linux.");
  for (const art of ["docker", "linux", "windows", "rechner"]) {
    assert.doesNotMatch(nurAufDemMac({ art }, "X"), /öffne|neu/, art);
    assert.doesNotMatch(ausstattungUnbekannt({ art }), /Mac/, art);
  }
  assert.match(ausstattungUnbekannt({ art: "docker" }), /Container/);
  assert.equal(wo("windows"), "unter Windows");
});

/** Alle .ts/.tsx-Dateien unter src, relativ. */
function dateien(ordner = SRC, praefix = "") {
  return readdirSync(ordner, { withFileTypes: true }).flatMap(e => e.isDirectory()
    ? dateien(new URL(`${e.name}/`, ordner), `${praefix}${e.name}/`)
    : /\.tsx?$/.test(e.name) ? [`${praefix}${e.name}`] : []);
}

// Wo ein Mac-Satz stehen darf, mit Grund. Geprüft werden alle Dateien unter src/, auch Einrichtung/ und die Akten als
// Ordner (seit dem Zusammenführen mit der Einrichtung ohne Fachwissen).
const AUSNAHMEN = {
  "system.ts": "die Hilfsfunktion selbst",
  "MacCalendarSettings.tsx": "erscheint nur auf dem Mac (Zugaenge.tsx)",
  "WegezeitSettings.tsx": "„Apple Karten ist auf diesem Mac bereit“ steht nur, wenn Apple Karten bereit ist, also auf dem Mac",
  "Einrichtung/KalenderSchritt.tsx": "der Knopf „Kalender auf diesem Mac“ erscheint nur mit system.mac_helfer",
  "Einstellungen/gliederung.ts": "„Apple Karten auf dem Mac“ nennt den Dienst, der nur auf dem Mac rechnet",
};
const MAC_SATZ = /\b(?:diesem|deinem|dem|am) Mac\b|Mac-App|Mac-Helfer|Kingfisher-starten\.command/;

test("kein fester Mac-Satz in der Oberfläche: Texte gehen durch fuerSystem oder nurAufDemMac", () => {
  const funde = [];
  for (const datei of dateien()) {
    if (AUSNAHMEN[datei]) continue;
    const code = readFileSync(new URL(datei, SRC), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\s\/\/\s.*$/gm, "");
    for (const zeile of code.split("\n")) if (MAC_SATZ.test(zeile)) funde.push(`${datei}: ${zeile.trim().slice(0, 120)}`);
  }
  assert.deepEqual(funde, []);
  // Die Stellen aus der Fremdprobe gehen durch die Hilfsfunktion.
  const quelle = (datei) => readFileSync(new URL(datei, SRC), "utf8");
  assert.match(quelle("Einstellungen/Seite.tsx"), /fuerSystem\("Auf diesem \{Rechner\} gespeichert", system\)/);
  assert.match(quelle("RecoverySettings.tsx"), /nurAufDemMac\(system, "Die Sicherung"\)/);
  assert.match(quelle("DeviceModelHelp.tsx"), /ausstattungUnbekannt\(system\)/);
  assert.match(quelle("Einstellungen/Zugaenge.tsx"), /system\.mac_helfer \? <MacCalendarSettings \/> : null/);
  assert.match(quelle("Einrichtung/KalenderSchritt.tsx"), /system\.mac_helfer \? knopf\("mac", "Kalender auf diesem Mac"\) : null/);
  assert.match(quelle("TranscriptSettings.tsx"), /fuerSystem\(wartetSatz\(/);
  assert.match(quelle("AktenOrdnerSettings.tsx"), /nurAufDemMac\(system, "Akten als Ordner"\)/);
});

test("Tastenhinweis am Suchfeld: ⌘ K auf dem Mac, Strg K sonst, keiner auf Touchgeräten (Fremdprobe 2, Befund 11)", () => {
  const mac = eingabegeraetAus({ plattform: "macOS", userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)" });
  const linux = eingabegeraetAus({ plattform: "Linux x86_64", userAgent: "Mozilla/5.0 (X11; Linux x86_64)" });
  const windows = eingabegeraetAus({ plattform: "Win32", userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" });
  const iphone = eingabegeraetAus({ plattform: "iPhone", userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", nurTouch: true });
  const telefon = eingabegeraetAus({ plattform: "Linux armv8l", userAgent: "Mozilla/5.0 (Linux; Android 14)", nurTouch: true });
  assert.equal(tastenHinweis(mac), "⌘ K");
  assert.equal(tastenHinweis(linux), "Strg K");
  assert.equal(tastenHinweis(windows), "Strg K");
  assert.equal(iphone.mac, false, "ein iPhone ist kein Mac, auch wenn „Mac OS X“ im Text steht");
  assert.equal(tastenHinweis(iphone), null);
  assert.equal(tastenHinweis(telefon), null);
  // Kein fester Hinweis mehr in der Oberfläche: Er kommt nur aus tastenHinweis.
  for (const datei of ["App.tsx", "TodayOverview.tsx"]) {
    assert.doesNotMatch(readFileSync(new URL(datei, SRC), "utf8"), /<kbd>⌘/, datei);
  }
});
