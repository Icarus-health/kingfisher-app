import assert from "node:assert/strict";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

// Use the application's existing TSX pipeline and render the real component.
const server = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null, ws: false, hmr: false },
  appType: "custom",
});
after(() => server.close());
const { SemanticMemoryProgress } = await server.ssrLoadModule("/src/MemoryStatus.tsx");
const base = {
  status: "partial", model_key: `nomic-embed-text:latest:${"a".repeat(64)}`,
  identity_checked_at: 1780000000, total: 10, indexed: 4, pending: 6,
  failed: 0, updated_at: 1780000000, source_pending: 0,
};
const render = (progress = {}, stale = false) => renderToStaticMarkup(createElement(SemanticMemoryProgress, {
  progress: { ...base, ...progress }, stale,
}));

test("renders prepared sections independently from sources and hides model digests", () => {
  const html = render({ source_pending: 12 });
  assert.match(html, /4 von 10 Abschnitten/);
  assert.match(html, /6 Abschnitte stehen noch aus/);
  assert.match(html, /12 Quellen werden noch sortiert/);
  assert.match(html, /Suchmodell: nomic-embed-text:latest/);
  assert.doesNotMatch(html, /a{64}/);
  assert.match(html, /<progress[^>]*max="10"[^>]*value="4"/);
});

test("initial unavailable state preserves unknown counts and explains pending identity check", () => {
  const html = render({ status: "unavailable", identity_checked_at: null,
    total: null, indexed: null, pending: null, failed: null, updated_at: null, source_pending: null });
  assert.match(html, /Abschnittszahl noch nicht verfügbar/);
  assert.match(html, /Suchmodell und der Suchindex wurden noch nicht geprüft/);
  assert.doesNotMatch(html, /<progress|0 von|sind vorbereitet|keine Quellen/);
});

test("disabled state is neutral even with historical failures", () => {
  const html = render({ status: "disabled", failed: 2 });
  assert.match(html, /Bedeutungssuche ist ausgeschaltet/);
  assert.doesNotMatch(html, /fehlgeschlagen|erneut versucht|<progress/);
});

test("finished current sections keep remaining source sorting visible", () => {
  const html = render({ indexed: 10, pending: 0, source_pending: 7 });
  assert.match(html, /10 von 10 Abschnitten/);
  assert.match(html, /7 Quellen werden noch sortiert/);
  assert.doesNotMatch(html, /Alle Quellen|abgeschlossen/);
});

test("stale and unavailable coverage never announces current completion", () => {
  for (const html of [
    render({ status: "indexed", indexed: 10, pending: 0 }, true),
    render({ status: "unavailable", indexed: 10, pending: 0 }),
  ]) {
    assert.match(html, /10 von 10 Abschnitten/);
    assert.doesNotMatch(html, /Die bisher sortierten Abschnitte sind/);
  }
  assert.match(render({ status: "indexed", indexed: 10, pending: 0 }, true), /letzter bekannter Stand/);
});

test("pause explanation, retry count, and Unix-second timestamp render without ETA", () => {
  const html = render({ failed: 2, pause_reason: "Die Vorbereitung pausiert, solange dein Rechner auf Akku läuft." });
  assert.match(html, /Die Vorbereitung pausiert, solange dein Rechner auf Akku läuft/);
  assert.match(html, /Bei 2 Abschnitten ist ein Versuch fehlgeschlagen; sie werden erneut versucht/);
  assert.match(html, /2026/);
  assert.doesNotMatch(html, /1970|Noch etwa/);
});

test("completion is scoped to known prepared sections, including empty index", () => {
  assert.match(render({ status: "indexed", indexed: 10, pending: 0 }), /Die bisher sortierten Abschnitte sind für die Bedeutungssuche vorbereitet/);
  const empty = render({ status: "indexed", total: 0, indexed: 0, pending: 0 });
  assert.match(empty, /Sobald sortierte Abschnitte vorliegen/);
  assert.doesNotMatch(empty, /<progress|Die bisher sortierten Abschnitte sind/);
});
