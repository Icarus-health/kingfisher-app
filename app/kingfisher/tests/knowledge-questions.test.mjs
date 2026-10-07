import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

const path = new URL("../src/KnowledgeQuestions.tsx", import.meta.url);
const source = () => readFileSync(path, "utf8");

test("persistente Wissensfragen laden nur aktiv, bleiben begrenzt und lassen weitere sichtbar werden", () => {
  const code = source();
  assert.match(code, /api\.memoryQuestions\(\)/);
  assert.match(code, /if \(!active\) return null/);
  assert.match(code, /FIRST_PAGE = 5/);
  assert.match(code, /MAX_QUESTIONS = 50/);
  assert.match(code, /Weitere \{Math\.min\(FIRST_PAGE, total - visibleLimit\)\} anzeigen/);
  assert.match(code, /addEventListener\("focus"/);
});

test("Fragen zeigen opaque Zuordnungsreferenz, Originalzitat und getrennte Quell- und Erfassungszeit", () => {
  const code = source();
  assert.match(code, /Zuordnungsreferenz:[\s\S]*question\.subject_ref/);
  assert.match(code, /<blockquote>\{source\.quote\}<\/blockquote>/);
  assert.match(code, /Quelldatum: \{timeLabel\(source\.occurred_at\)\}/);
  assert.match(code, /shouldShowRecordedAt\(source\) && <p>Erfasst: \{timeLabel\(source\.recorded_at\)\}<\/p>/);
  assert.match(code, /if \(!source\.recorded_at\) return false/);
  assert.match(code, /occurred !== recorded/);
  assert.match(code, /if \(!value\) return "unbekannt"/);
});

test("eine Kandidatenwahl ist explizit; Beibehalten gibt es nur bei aktiver bestätigter Angabe", () => {
  const code = source();
  assert.match(code, /Diese Angabe bestätigen/);
  assert.match(code, /function canKeepCurrent\(question: MemoryQuestion\)/);
  assert.match(code, /question\.active_claims\.length > 0/);
  assert.match(code, /Bestätigte Angabe beibehalten/);
  assert.match(code, /proposal_id: proposalId/);
});

test("veraltete Fehlerstände werden nicht als leere Fragenliste gezeigt und Doppelklicks sind gesperrt", () => {
  const code = source();
  assert.match(code, /const pending = useRef\(false\)/);
  assert.match(code, /if \(!activeRef\.current \|\| pending\.current\) return/);
  assert.match(code, /Die Klärung wurde nicht bestätigt/);
  assert.match(code, /setQuestions\(null\)/);
  assert.match(code, /setRevision\(value => value \+ 1\)/);
  assert.match(code, /lifecycle\.current === epoch/);
});
