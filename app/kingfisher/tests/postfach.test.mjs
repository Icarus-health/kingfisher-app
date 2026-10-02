// Fremdprobe 3, Befund 5: Die Frage vor dem Einlesen nennt das eigene Postfach, nicht „die Mails von example.org“, und
// verweist fürs Pausieren auf Heute statt unter „Für Techniker“.
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {deinPostfach, einlesenFrage} from "../src/Einrichtung/postfach.ts";
import {PAUSIEREN_AUF_HEUTE} from "../src/Einrichtung/fertig.ts";

test("Das Postfach heißt nach seiner Adresse", () => {
  assert.equal(deinPostfach("example.org", "lena.probe@example.org"), "dein Postfach lena.probe@example.org");
  assert.equal(deinPostfach("Probe-Post", ""), "dein Postfach „Probe-Post“");
  assert.equal(deinPostfach("Probe-Post", "lena"), "dein Postfach „Probe-Post“");
});

test("Die Frage nennt das Postfach und Pausieren auf Heute", () => {
  const frage = einlesenFrage("example.org", "lena.probe@example.org");
  assert.match(frage, /^Soll Kingfisher dein Postfach lena\.probe@example\.org jetzt einlesen\? /);
  assert.doesNotMatch(frage, /Mails von|Für Techniker/);
  assert.match(frage, /auf Heute mit „Pausieren“/);
  assert.match(PAUSIEREN_AUF_HEUTE, /auf Heute mit „Pausieren“/);
});

test("Kein Verweis unter „Für Techniker“ fürs Pausieren im Assistenten", () => {
  for (const datei of ["MailEinlesen.tsx", "FertigSchritt.tsx"]) {
    const code = readFileSync(new URL(`../src/Einrichtung/${datei}`, import.meta.url), "utf8");
    assert.doesNotMatch(code, /Pausieren[^<]*<Verweis ziel="technik-hintergrund"/, datei);
  }
  assert.match(readFileSync(new URL("../src/Einrichtung/MailEinlesen.tsx", import.meta.url), "utf8"),
    /einlesenFrage\(konto\.label, adressen\[konto\.account_id\]\)/);
});
