// Mit Microsoft anmelden (docs/50-microsoft-365.md): Sätze, Restzeit, wann der Mail-Schritt Microsoft anbietet, und
// das Nachfragen, das nach dem Ende nichts mehr meldet.
import assert from "node:assert/strict";
import { test } from "node:test";
import { SAETZE, istFertig, kontoSatz, microsoftZuerst, nachfragen, restText, standSatz } from "../src/microsoftAnmeldung.ts";
import { fachwoerter } from "../src/Einstellungen/gliederung.ts";

test("die Restzeit des Codes in Alltagswörtern", () => {
  assert.equal(restText(900), "noch 15 Minuten");
  assert.equal(restText(119), "noch eine Minute");
  assert.equal(restText(40), "noch 40 Sekunden");
  assert.equal(restText(1), "noch eine Sekunde");
  assert.equal(restText(undefined), "noch 0 Sekunden");
});

test("jeder Stand hat einen Satz, und der Satz des Sidecars gewinnt bei Fehlern", () => {
  assert.match(standSatz({ status: "waiting", restsekunden: 600 }), /wartet .*noch 10 Minuten/);
  assert.match(standSatz({ status: "connected", email: "lena@uni.example" }), /Post und Kalender von lena@uni\.example/);
  assert.match(standSatz({ status: "connected", email: "x@y.z", mitschriften_an: true }), /Teams-Mitschriften/);
  assert.match(standSatz({ status: "connected", email: "x@y.z", ohne_mitschriften: true }), /IT zustimmen/);
  assert.equal(standSatz({ status: "failed", satz: "Deine Hochschule muss Kingfisher erst freigeben." }), "Deine Hochschule muss Kingfisher erst freigeben.");
  assert.match(standSatz({ status: "expired" }), /neu/);
  assert.equal(istFertig({ status: "waiting" }), false);
  assert.equal(istFertig({ status: "ready" }), false);
  for (const status of ["connected", "failed", "expired", "cancelled"]) assert.equal(istFertig({ status }), true, status);
});

test("Microsoft zuerst nur bei Hochschule oder Firma, nicht bei privaten Konten", () => {
  assert.equal(microsoftZuerst({ provider: null, erkannt_an: "mx", dienst: "microsoft", art: "organisation" }), true);
  assert.equal(microsoftZuerst({ provider: null, erkannt_an: "domain", dienst: "microsoft", art: "privat" }), false);
  // Google Workspace ist auch eine Organisation, aber nicht Microsoft: dort gilt das App-Passwort.
  assert.equal(microsoftZuerst({ provider: null, erkannt_an: "mx", dienst: "google", art: "organisation" }), false);
  assert.equal(microsoftZuerst({ provider: null, erkannt_an: "", dienst: "", art: "" }), false);
  assert.equal(microsoftZuerst(null), false);
});

test("die Sätze vorne tragen kein Fachwort und versprechen nur Lesen", () => {
  for (const satz of Object.values(SAETZE)) assert.deepEqual(fachwoerter(satz), [], satz);
  assert.match(SAETZE.einleitung, /schreibt, verschickt und löscht dort nichts/);
  assert.match(SAETZE.admin, /IT/);
});

test("Nachfragen hört nach dem Ende auf und meldet danach nichts mehr", async () => {
  const staende = [{ status: "waiting" }, { status: "waiting" }, { status: "connected", email: "a@b.c" }];
  const gesehen = [];
  let gelesen = 0;
  await new Promise(fertig => {
    nachfragen({
      lesen: async () => staende[Math.min(gelesen++, staende.length - 1)],
      beiStand: stand => { gesehen.push(stand.status); if (stand.status === "connected") setTimeout(fertig, 30); },
      beiFehler: () => assert.fail("kein Fehler erwartet"),
      abstand: 1,
    });
  });
  assert.deepEqual(gesehen, ["waiting", "waiting", "connected"]);
  assert.equal(gelesen, 3);
});

test("Nach stop() kommt keine späte Antwort mehr an", async () => {
  let melden;
  const gesehen = [];
  const beobachter = nachfragen({ lesen: () => new Promise(r => { melden = r; }), beiStand: s => gesehen.push(s), beiFehler: () => {}, abstand: 1 });
  await new Promise(r => setTimeout(r, 10));
  beobachter.stop();
  melden({ status: "connected" });
  await new Promise(r => setTimeout(r, 10));
  assert.deepEqual(gesehen, []);
});

test("Die Bestätigung kommt auch aus dem gespeicherten Konto, falls die Anmeldekarte beim Neulesen verschwand", () => {
  const konto = {adresse: "lena.probe@hochschule.example", verbunden: true, post: true, kalender: true, mitschriften: false};
  assert.equal(kontoSatz(konto),
    "Verbunden: Post und Kalender von lena.probe@hochschule.example. Deine Post liest Kingfisher erst, wenn du „Mails einlesen“ wählst.");
  assert.equal(kontoSatz({...konto, mitschriften: true}),
    "Verbunden: Post, Kalender und Teams-Mitschriften von lena.probe@hochschule.example. Deine Post liest Kingfisher erst, wenn du „Mails einlesen“ wählst.");
  assert.equal(kontoSatz({...konto, verbunden: false}), null);
  assert.deepEqual(fachwoerter(kontoSatz(konto)), []);
});
