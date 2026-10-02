import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {gueltigeQuellen, nachrichtAusAdresse, quellenWeg, technikZeile} from "../src/quellenWeg.ts";

const gespraech = {nummer: 1, text: "Gespräch vom 1. Oktober 2026, 12:25 Uhr", art: "chat", assertion_id: "claim:k-1",
  episode_id: "e-1", source_ref: "conversation:c-1:message:m-1", conversation_id: "c-1", message_id: "m-1"};
const mail = {nummer: 2, text: "E-Mail „Angebot“ von Lena Probe vom 29. September 2026, 09:00 Uhr", art: "email",
  assertion_id: "claim:k-2", episode_id: "e-2", source_ref: "imap:lena.probe@example.org:INBOX:42"};

test("Eine Nachricht aus diesem Gespräch wird angesprungen", () => {
  assert.deepEqual(quellenWeg(gespraech, "c-1"), {art: "nachricht", nachricht: "m-1"});
});

test("Eine Nachricht aus einem anderen Gespräch öffnet dieses Gespräch an der Nachricht", () => {
  assert.deepEqual(quellenWeg(gespraech, "c-2"), {art: "gespraech", pfad: "/conversations/c-1#message-m-1", nachricht: "m-1"});
  assert.equal(nachrichtAusAdresse("#message-m-1"), "m-1");
  assert.equal(nachrichtAusAdresse("#zugaenge"), null);
  assert.equal(nachrichtAusAdresse(""), null);
});

test("Mail, Termin und Dokument öffnen die Quellenansicht", () => {
  assert.deepEqual(quellenWeg(mail, "c-1"), {art: "quelle", episode: "e-2"});
  // Ohne Gespräch und Nachricht bleibt auch eine Gesprächsquelle in der Quellenansicht erreichbar.
  assert.deepEqual(quellenWeg({...gespraech, message_id: undefined}, "c-1"), {art: "quelle", episode: "e-1"});
});

test("Kennungen nur in der Zeile für Techniker", () => {
  assert.equal(technikZeile(gespraech), "[1] claim:k-1 · conversation:c-1:message:m-1");
  assert.equal(technikZeile({...mail, source_ref: null}), "[2] claim:k-2 · e-2");
});

test("Ein beschädigtes Datenfeld zeigt keinen Knopf", () => {
  assert.deepEqual(gueltigeQuellen(undefined), []);
  assert.deepEqual(gueltigeQuellen([{nummer: 1}, null, "x", {...mail, text: ""}]), []);
  assert.deepEqual(gueltigeQuellen([gespraech, mail]), [gespraech, mail]);
});

test("Die Gesprächsseite zeigt die Quellen unter jeder belegten Antwort", () => {
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /<BelegQuellen quellen=\{message\.metadata\.context\.quellen\}/);
  assert.match(app, /nachrichtAusAdresse\(window\.location\.hash\)/);
});
