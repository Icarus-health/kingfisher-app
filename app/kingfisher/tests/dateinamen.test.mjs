import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const src = fileURLToPath(new URL("../src/", import.meta.url));

test("TypeScript-Dateinamen sind auf Macs eindeutig auflösbar", () => {
  const konflikte = [];
  const pruefen = ordner => {
    const gesehen = new Map();
    for (const datei of readdirSync(ordner, { withFileTypes: true })) {
      const pfad = join(ordner, datei.name);
      if (datei.isDirectory()) {
        pruefen(pfad);
        continue;
      }
      if (!datei.isFile() || !/\.tsx?$/.test(datei.name)) continue;
      // TypeScript löst importierte Module ohne Endung auf; .ts und .tsx teilen denselben Namen.
      const schluessel = datei.name.replace(/\.tsx?$/, "").toLowerCase();
      const zuerst = gesehen.get(schluessel);
      if (zuerst) konflikte.push(`${join(ordner, zuerst)} ↔ ${pfad}`);
      else gesehen.set(schluessel, datei.name);
    }
  };
  pruefen(src);
  assert.deepEqual(konflikte, [], `Mehrdeutige Module auf einem Dateisystem ohne Groß-/Kleinschreibung:\n${konflikte.join("\n")}`);
});
