// Briefing (Fremdprobe, Befunde 20 und 24; Paket U, H1): Heute ist das Briefing. Keine zweite Seite, keine Schublade,
// kein Spieler ohne lokales Audio; „Zum Briefing“ am Ende der Einrichtung zeigt einfach Heute.
// Im Browser prüft scripts/probe_seiten_ui.py dasselbe.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const morning = () => quelle("App.tsx").match(/function Morning\([\s\S]*?\n\}\n/)[0];

test("keine englischen Beschriftungen und keine zweite Briefing-Seite neben Heute", () => {
  const app = quelle("App.tsx");
  assert.doesNotMatch(app, /MORNING|Morning Briefing|>Dashboard</);
  assert.doesNotMatch(app, /BriefingDrawer|briefing-drawer|Briefing öffnen|Zurück zu Heute/);
  assert.doesNotMatch(morning(), /briefingOpen|inert=/, "Heute sperrt weder Seite noch Leiste");
});

test("/today?briefing=1 zeigt Heute und macht die Adresse wieder schlicht", () => {
  assert.match(morning(), /new URLSearchParams\(window\.location\.search\)\.has\("briefing"\)\) window\.history\.replaceState\(\{\}, "", "\/today"\)/);
});

test("Vorlesen bleibt als leiser Knopf im Kopf von Heute", () => {
  const kopf = morning().match(/<section className="hero">[\s\S]*?<\/section>/)[0];
  assert.match(kopf, /<AudioBriefing briefing=\{briefing\} \/>/);
  const audio = quelle("AudioBriefing.tsx");
  assert.match(audio, /<button className="today-text-link" type="button" onClick=\{\(\) => void generate\(\)\}>Vorlesen<\/button>/);
  assert.doesNotMatch(audio, /primary-action|play-toggle/, "kein gefüllter Knopf für das Vorlesen");
});

test("ohne lokales Audio kein Spieler", () => {
  const audio = quelle("AudioBriefing.tsx");
  assert.match(audio, /if \(available !== true && \(status === "idle" \|\| status === "unavailable"\)\) return null;/);
});

test("die Seitenleiste kennt keine Schublade mehr", () => {
  const leiste = quelle("chrome.tsx");
  assert.doesNotMatch(leiste, /briefingOpen|onToday|aria-expanded/);
  assert.match(leiste, /if \(label === "Heute"\) navigate\("\/today"\);/);
});
