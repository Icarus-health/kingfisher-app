import assert from "node:assert/strict";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null, ws: false, hmr: false },
  appType: "custom",
});
after(() => server.close());
const { SatzAntwort } = await server.ssrLoadModule("/src/SatzAntwort.tsx");
const base = {
  version: 1, saetze: [{ text: "Die Einreichfrist ist der 12. November 2026.", belege: [1], vom_programm: false }],
  belege: [], akte: [], verworfen: 0, modell: "synthetisch", stichtag: "2026-09-29T08:00:00Z",
};
const render = (extra = {}) => renderToStaticMarkup(createElement(SatzAntwort, { daten: { ...base, ...extra } }));

test("search coverage notices are visible while evidence details remain closed", () => {
  const notices = ["Die Bedeutungssuche war nicht verfügbar; passende Quellen können fehlen.",
    "Zu 1 passenden Originalquelle fehlt ein nutzbarer Belegabschnitt; die Antwort kann unvollständig sein."];
  const html = render({ hinweise: notices });
  const visible = html.split("<details")[0];
  for (const notice of notices) assert.ok(visible.includes(notice));
  assert.match(html, /<details class="satz-weg">/);
});

test("legacy sentence answers remain readable without notices", () => {
  const html = render();
  assert.match(html, /Die Einreichfrist ist der 12. November 2026/);
  assert.doesNotMatch(html, /Antwort kann unvollständig|Bedeutungssuche/);
});

test("notice text is escaped rather than interpreted as markup", () => {
  const html = render({ hinweise: ["<script>alert('source')</script>"] });
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});
