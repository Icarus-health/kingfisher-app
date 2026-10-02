import {test} from "node:test";
import assert from "node:assert/strict";
import {herkunftKennung, herkunftLesbar} from "../src/herkunft.ts";

test("Technische Kennungen stehen nie vorne, nur für Techniker (Fremdprobe 3, Befund 9)", () => {
  const termin = {source_type: "calendar", source_ref: "calendar:calendar-38d1718069744e76808c8e351eb567a6:probe-1@attrappe"};
  assert.equal(herkunftLesbar(termin), null);
  assert.equal(herkunftKennung(termin), termin.source_ref);
  assert.equal(herkunftLesbar({source_type: "mail", source_ref: "mail:a:7.3"}), null);
});

test("Was ein Mensch lesen kann, steht vorne, und dann nichts doppelt unter „Für Techniker“", () => {
  assert.equal(herkunftLesbar({source_type: "manual_correction"}), "Deine Berichtigung");
  assert.equal(herkunftLesbar({source_type: "chat", source_ref: "chat:abc"}), "Dein Gespräch mit Kingfisher");
  assert.equal(herkunftKennung({source_type: "chat", source_ref: "chat:abc"}), null);
  assert.equal(herkunftKennung(null), null);
  assert.equal(herkunftKennung({source_type: "calendar"}), null);
});
