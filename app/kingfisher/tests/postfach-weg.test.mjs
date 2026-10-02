// Eigene Domain ohne Servereingabe (Fremdprobe 2, Befunde 2 und 3): was die Karte im Assistenten und unter Zugänge tut.
import assert from "node:assert/strict";
import {test} from "node:test";
import {EIGENER_SERVER, SERVER_SATZ, STANDARD_PORT, anmeldeName, eigenerServer, erkanntText, nachsehenSatz, postfachName,
  servername} from "../src/postfachWeg.ts";

test("Ein selbst gefundener Server heißt nach seinem Namen, ein Katalogeintrag nach dem Anbieter", () => {
  assert.equal(erkanntText({id: "gefunden", label: "mail.example.org"}),
    "Erkannt: mail.example.org. Kingfisher hat deinen Mailserver in den Angaben deiner Domain gefunden.");
  assert.equal(erkanntText({id: "webde", label: "WEB.DE"}), "Erkannt: WEB.DE");
  assert.equal(postfachName("lena.probe@example.org", {id: "gefunden", label: "mail.example.org"}), "example.org");
  assert.equal(postfachName("lena.probe@web.de", {id: "webde", label: "WEB.DE"}), "WEB.DE");
});

test("Was hinausgeht: nur die Domain, ein Satz", () => {
  const satz = nachsehenSatz("lena.probe@example.org");
  assert.match(satz, /nur nach example\.org/);
  assert.ok(!satz.includes("lena.probe"));
});

test("Letzte Möglichkeit: Servername und Port, Vorgabe 993", () => {
  assert.equal(STANDARD_PORT, 993);
  assert.equal(eigenerServer("", 993), null);
  assert.equal(eigenerServer("kein server", 993), null);
  assert.equal(eigenerServer("mail.example.org", 0), null);
  const eigen = eigenerServer(" IMAPS://Mail.Example.org/ ", 993);
  assert.deepEqual([eigen.id, eigen.imap_host, eigen.imap_port, eigen.smtp_host], [EIGENER_SERVER, "mail.example.org", 993, ""]);
  assert.equal(servername("127.0.0.1"), "127.0.0.1");
  assert.match(SERVER_SATZ, /Anleitung/);
});

test("Angemeldet wird mit der Adresse, wo die Domain es sagt mit dem Namensteil", () => {
  assert.equal(anmeldeName(" lena.probe@example.org ", {benutzer: "adresse"}), "lena.probe@example.org");
  assert.equal(anmeldeName("lena.probe@example.org", {}), "lena.probe@example.org");
  assert.equal(anmeldeName("lena.probe@example.org", {benutzer: "lokalteil"}), "lena.probe");
});
