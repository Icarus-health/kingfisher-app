import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("/world öffnet die eigene Quellenansicht und Today verlinkt sie außerhalb des leeren Tagesbereichs", () => {
  const app = quelle("App.tsx");
  const worldRoute = app.indexOf('if (path === "/world")');
  assert.ok(worldRoute >= 0, "App muss /world auf eine eigene Seite routen");
  assert.ok(worldRoute < app.indexOf('if (path !== "/today")'), "die Route muss vor dem Heute-Fallback liegen");
  assert.match(app.slice(worldRoute, worldRoute + 100), /<WorldPage/);

  const today = quelle("TodayOverview.tsx");
  const personal = today.match(/export function TodayPersonal\(\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
  assert.match(personal, /href="\/world"/);
  assert.match(personal, /Öffentliches Wissen & Quellen/);
  assert.match(app, /<HeuteLeer[\s\S]*?<\/HeuteLeer>[\s\S]*?<TodayPersonal \/>/);
});

test("die Quellenansicht zeigt alle registrierten Quellen auch ohne Zielüberschneidung", () => {
  const page = quelle("WorldPage.tsx");
  const controls = quelle("WorldControls.tsx");
  assert.match(page, /<WorldControls[^>]*initiallyOpen/);
  assert.match(controls, /payload\?\.items\.map\(source/);
  assert.doesNotMatch(controls.match(/export function WorldControls\(\)[\s\S]*?export function WorldRadar/)?.[0] ?? "", /filter\(.*matched_goals/);
  assert.match(controls, /Themenüberschneidung mit einem Ziel \(nur ein Hinweis\)/);
});

test("Quellenkarten zeigen Weiterleitungsziel und gespeicherten Text-Hash mit klarer Abrufzeit", () => {
  const controls = quelle("WorldControls.tsx");
  assert.match(controls, /fetched_url\?: string \| null/);
  assert.match(controls, /source_sha256\?: string \| null/);
  assert.match(controls, /source\.fetched_url/);
  assert.match(controls, /source\.source_sha256/);
  assert.match(controls, /Veröffentlichungsdatum wird nicht übernommen/);
});
