// Ordner ohne Mac-Helfer (Fremdprobe, Befund 6): Mit Helfer gilt sein Dialog, sonst der Weg im Browser.
import assert from "node:assert/strict";
import {test} from "node:test";
import {OHNE_ORTE, ordnerWeg, ortText, ortZusatz, wartetSatz} from "../src/ordnerWahl.ts";

test("Cloud-Ordner tragen ihren Namen und sagen, dass sie abgeglichen sind", () => {
  const onedrive = {pfad: "/h/Library/CloudStorage/OneDrive-Hochschule", name: "OneDrive (Hochschule)", da: true, vorgabe: false, dateien: 12, cloud: "onedrive"};
  assert.equal(ortText(onedrive), "OneDrive (Hochschule) verwenden");
  assert.equal(ortZusatz(onedrive), "aus der Cloud, auf diesem Rechner abgeglichen · 12 passende Dateien");
  assert.equal(ortZusatz({...onedrive, cloud: ""}), "12 passende Dateien");
});

test("Ohne Helfer am Mac wird im Browser gewählt", () => {
  assert.equal(ordnerWeg({helfer: false, lokal: false}), "browser");
  assert.equal(ordnerWeg({helfer: true, lokal: false}), "helfer");
  // Ein im Browser gewählter Ordner bleibt im Browser, auch wenn ein Helfer auftaucht.
  assert.equal(ordnerWeg({helfer: true, lokal: true}), "browser");
  assert.equal(ordnerWeg({}), "browser");
});

test("Der Vorgabeordner verspricht kein Fenster", () => {
  assert.doesNotMatch(wartetSatz("vorgabe", "Dokumente/Kingfisher/Transkripte"), /Fenster/);
  assert.match(wartetSatz("vorgabe", "Dokumente/Kingfisher/Transkripte"), /legt den Ordner „Dokumente\/Kingfisher\/Transkripte“/);
  assert.match(wartetSatz("waehlen", "x"), /Fenster/);
});

test("Orte sagen, was ein Klick tut und was darin liegt", () => {
  const vorgabe = {pfad: "/h/Documents/Kingfisher/Transkripte", name: "~/Documents/Kingfisher/Transkripte", da: false, vorgabe: true, dateien: 0};
  assert.equal(ortText(vorgabe), "Ordner „~/Documents/Kingfisher/Transkripte“ anlegen und verwenden");
  assert.equal(ortZusatz(vorgabe), "");
  assert.equal(ortText({...vorgabe, da: true}), "Ordner „~/Documents/Kingfisher/Transkripte“ verwenden");
  const eingebunden = {pfad: "/ordner/Mitschriften", name: "/ordner/Mitschriften", da: true, vorgabe: false, dateien: 3};
  assert.equal(ortText(eingebunden), "/ordner/Mitschriften verwenden");
  assert.equal(ortZusatz(eingebunden), "3 passende Dateien");
  assert.equal(ortZusatz({...eingebunden, dateien: 1}), "1 passende Datei");
  assert.equal(ortZusatz({...eingebunden, dateien: 0}), "noch leer");
  assert.match(OHNE_ORTE, /^Kingfisher läuft hier in einem Container/);
});
