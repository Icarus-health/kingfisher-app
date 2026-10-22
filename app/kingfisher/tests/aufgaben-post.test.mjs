// Aufgaben folgen der Post (Paket B6): Die Zeile mit Grund und „Rückgängig“ in der Aufgabenliste und in der Akte,
// die Vorschläge „Erledigt?“ mit einem Klick. Synthetische Daten.
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {angenommenText, annehmenText, postGrund, postSatz} from "../src/aufgabenPost.ts";

const grund = (art, satz) => ({art, satz, episode_id: "e-1", mail_titel: "AW: Druckdaten", wer: "Anna Berg", datum: null,
  am: "2026-10-21T09:00:00+00:00", verlauf: true, woerter: ["Druckdaten"]});

test("Die Zeile zeigt den Satz des Sidecars nur, solange die Änderung gilt", () => {
  const erledigt = grund("erledigt", "Erledigt, weil du Anna Berg am 21. Oktober „Druckdaten“ geschickt hast.");
  assert.equal(postSatz({status: "done", erledigt_grund: erledigt, geaendert_grund: null}), erledigt.satz);
  // Wieder von Hand geöffnet oder zurückgenommen: kein Satz mehr.
  assert.equal(postSatz({status: "open", erledigt_grund: erledigt, geaendert_grund: null}), null);
  assert.equal(postSatz({status: "done", erledigt_grund: null, geaendert_grund: null}), null);
  const zurueck = grund("zurueck", "Wieder bei dir, weil Anna Berg am 21. Oktober geantwortet hat.");
  assert.equal(postSatz({status: "open", erledigt_grund: null, geaendert_grund: zurueck}), zurueck.satz);
  assert.equal(postGrund({status: "done", erledigt_grund: null, geaendert_grund: zurueck}), null);
  // Älterer Sidecar ohne die Felder: nichts.
  assert.equal(postSatz({status: "done"}), null);
});

test("Die Knöpfe des Vorschlags sagen, was passiert, und die Antwort nennt Rückgängig", () => {
  assert.equal(annehmenText({art: "erledigt"}), "Ja, erledigt");
  assert.equal(annehmenText({art: "zurueck"}), "Ja, wieder bei mir");
  assert.match(angenommenText({art: "erledigt"}), /Rückgängig/);
  assert.match(angenommenText({art: "zurueck"}), /wieder bei dir/);
});

test("TaskRow zeigt die Zeile mit Rückgängig; die Aufgabenseite und die Aufgabe hängen den Aufruf an", () => {
  const zeile = readFileSync(new URL("../src/TaskRow.tsx", import.meta.url), "utf8");
  assert.match(zeile, /postSatz\(task\)/);
  assert.match(zeile, /className="task-post" role="status"/);
  assert.match(zeile, /onClick=\{onRueckgaengig\}>Rückgängig<\/button>/);
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.match(app, /api\.taskRueckgaengig\(taskId\)/);
  assert.match(app, /onRueckgaengig=\{\(\)=>void rueckgaengig\(task\.id\)\}/);
  assert.match(app, /<AufgabenPostVorschlaege onChanged=/);
  const detail = readFileSync(new URL("../src/TaskDetail.tsx", import.meta.url), "utf8");
  assert.match(detail, /onRueckgaengig=\{\(\) => \{void change\(\(\) => api\.taskRueckgaengig\(task\.id\)\);\}\}/);
});

test("Die Vorschläge: ein Klick nimmt an, einer verwirft, die Mail ist einsehbar", () => {
  const quelle = readFileSync(new URL("../src/AufgabenPostVorschlaege.tsx", import.meta.url), "utf8");
  assert.match(quelle, /api\.aufgabenPostAnnehmen\(v\.id\)/);
  assert.match(quelle, /api\.aufgabenPostVerwerfen\(v\.id\)/);
  assert.match(quelle, /\{annehmenText\(v\)\}<\/button>/);
  assert.match(quelle, />Nein<\/button>/);
  assert.match(quelle, /<ProfileSource kind="episode" id=\{v\.mail\.episode_id\}/);
  assert.doesNotMatch(quelle, /„[^“\n]*"/, "ein mit „ geöffnetes Zitat endet mit dem typografischen Zeichen, nie mit ASCII");
  const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");
  assert.match(api, /taskRueckgaengig: \(id: string\)/);
  assert.match(api, /aufgaben-post\/vorschlaege/);
  assert.match(api, /erledigt_grund\?: AufgabenPostGrund \| null/);
});

test("Die Akte zeigt die Änderung unter Braucht dich mit Rückgängig; die Tageslage öffnet die Aufgabe", () => {
  const akte = readFileSync(new URL("../src/AkteAbschnitte.tsx", import.meta.url), "utf8");
  assert.match(akte, /p\.art === "aufgabe_post" && p\.aufgabe \? <button[^>]*onClick=\{\(\) => aufgabeZurueck\(p\.ziel, p\.aufgabe!\.id\)\}>Rückgängig<\/button>/);
  assert.match(akte, /await api\.taskRueckgaengig\(aufgabeId\)/);
  const lage = readFileSync(new URL("../src/TagesLage.tsx", import.meta.url), "utf8");
  assert.match(lage, /aufgaben_post: "Post"/);
  assert.match(lage, /a\.art === "aufgabe" && a\.ref/);
  assert.match(lage, /\/vorhaben\?view=done&task=/);
});
