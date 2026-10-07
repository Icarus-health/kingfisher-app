import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const contract = (text, pattern) => pattern.test(text);

test("briefing API encodes the UID and retries with an explicit refresh while forwarding cancellation", () => {
  const api = quelle("api.ts");
  assert.equal(contract(api, /type MailBriefing\s*=\s*\{[\s\S]*?status:\s*"ready"\s*\|\s*"empty"\s*\|\s*"unavailable"\s*\|\s*"incomplete"[\s\S]*?source_digest:\s*string\s*\|\s*null[\s\S]*?quotes:\s*string\[\][\s\S]*?tasks:\s*Array<\{\s*title:\s*string;\s*quote:\s*string\s*\}>[\s\S]*?truncated:\s*boolean/), true);
  const declaration = api.match(/^\s*mailBriefing:[^\n]+$/m)?.[0];
  assert.ok(declaration, "API exposes mailBriefing");
  assert.equal(contract(declaration, /refresh\s*=\s*false/), true);
  const runtimeDeclaration = declaration
    .replace("(uid: string, signal?: AbortSignal, refresh = false)", "(uid, signal, refresh = false)")
    .replace("request<MailBriefing>", "request");
  const calls = [];
  const method = new Function("request", `return ({${runtimeDeclaration}}).mailBriefing`)((path, init) => {
    calls.push({ path, init });
    return Promise.resolve({ uid: "mail/7" });
  });
  const controller = new AbortController();
  return method("mail/7", controller.signal).then(() => method("mail/7", controller.signal, true)).then(() => {
    assert.equal(calls.length, 2);
    assert.equal(calls[0].path, "/api/v1/messages/mail%2F7/briefing");
    assert.equal(calls[0].init.method, "POST");
    assert.deepEqual(JSON.parse(calls[0].init.body), { refresh: false });
    assert.equal(calls[0].init.signal, controller.signal);
    assert.deepEqual(JSON.parse(calls[1].init.body), { refresh: true });
  });
});

test("mail overview keeps original mail immediately expandable and shows sender and date", () => {
  const reader = quelle("MailReader.tsx");
  assert.equal(contract(reader, /<MailBriefing\b/), true);
  assert.equal(contract(reader, /key=\{`briefing:\$\{uid\}:\$\{detail\.source_digest/), true);
  assert.equal(contract(reader, /expectedSourceDigest=\{detail\.source_digest\}/), true);
  assert.equal(contract(reader, /<details[^>]*className="mail-reader-original"/), true);
  assert.equal(contract(reader, /<summary>Aus der Originalnachricht<\/summary>/), true);
  assert.equal(contract(reader, /<dt>Von<\/dt>/), true);
  assert.equal(contract(reader, /<dt>Datum<\/dt>/), true);
  assert.equal(contract(reader, /onNeedsOriginal=\{openOriginalMessage\}/), true);
  assert.equal(contract(reader, /ref=\{originalMessageRef\}/), true);
  assert.equal(contract(reader, /originalMessageRef\.current\.open = true/), true);
});

test("briefing discards results for a different UID or changed source and aborts on cancel or unmount", () => {
  const briefing = quelle("MailBriefing.tsx");
  assert.equal(contract(briefing, /value\.uid !== uid/), true);
  assert.equal(contract(briefing, /value\.source_digest !== expectedSourceDigest/), true);
  assert.equal(contract(briefing, /controller\.current\?\.abort\(\)/), true);
  assert.equal(contract(briefing, /requestVersion\.current\+\+/), true);
  assert.equal(contract(briefing, /Die Nachricht hat sich geändert\. Bitte neu öffnen oder aktualisieren\./), true);
});

test("briefing has explicit progress, cancellation, retry and non-verified source wording", () => {
  const briefing = quelle("MailBriefing.tsx");
  for (const pattern of [/role="status"/, /Abbrechen/, /Wiederholen/, /Auf einen Blick/, /Auszüge aus der Originalnachricht/, /Als Aufgabe vorbereiten/, /source_digest/, /unvollständig[\s\S]*?Originalauszüge/, /result\.status === "ready" \|\| result\.status === "incomplete"/, /result\?\.status === "ready" && result\.available/]) {
    assert.equal(contract(briefing, pattern), true, pattern.toString());
  }
  assert.equal(contract(briefing, /onClick=\{\(\) => load\(true\)\}/), true);
});

test("choosing a suggested task opens the existing form with only title and source evidence prefilled", () => {
  const form = quelle("MailTaskForm.tsx");
  assert.equal(contract(form, /initialSuggestion\?:\s*\{\s*title:\s*string;\s*quote:\s*string;\s*source_digest:\s*string\s*\}/), true);
  assert.equal(contract(form, /onTaskFormProtected\?:\s*\(protectedState:\s*boolean\)\s*=>\s*void/), true);
  assert.equal(contract(form, /userChanged\.current\s*\|\|\s*saved/), true);
  assert.equal(contract(form, /onTaskFormProtected\?\.\(true\)/), true);
  assert.equal(contract(form, /setOpen\(true\)/), true);
  assert.equal(contract(form, /sourceQuote/), true);
  assert.equal(contract(form, /sourceDigest/), true);
  assert.equal(contract(form, /<form onSubmit=\{submit\}>/), true);
  assert.equal(contract(form, /setDue\(initialSuggestion/), false);
  assert.equal(contract(form, /setWaitingFor\(initialSuggestion/), false);
  const briefing = quelle("MailBriefing.tsx");
  assert.equal(contract(briefing, /taskSelectionDisabled\?:\s*boolean/), true);
  assert.equal(contract(briefing, /disabled=\{taskSelectionDisabled \|\| accepted\.has\(taskKey\)\}/), true);
  assert.equal(contract(briefing, /onPrepareTask\(\{ \.\.\.task, source_digest: result\.source_digest! \}\)/), true);
  assert.equal(contract(quelle("MailReader.tsx"), /taskSelectionDisabled=\{taskSuggestionProtected\}/), true);
});
