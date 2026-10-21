// Stilprofil (Paket B5): die Zeile „Dein Ton an …“ aus dem Vorschlag, die Herkunft in Klammern, der Satz je Kreis und der
// Hinweis beim Entwurf; dazu die Verdrahtung in MailStyle, MailReplySuggestion, MailReader und StilKreis. Synthetische Daten.
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {bestaetigtSatz, belegeTitel, herkunft, kreisTonSatz, regelTeile, stilHinweis, tonSatz} from "../src/stilprofil.ts";

const regeln = (mehr = {}) => ({address: "du", length: "short", emoji: "no", gruss: "Viele Grüße", anrede_form: "vorname", sprache: "de", ...mehr});
const vorschlag = (mehr = {}) => ({rules: regeln(), evidence_ids: ["e1", "e2", "e3"], gesendet: 7, belege: 0, ...mehr});
const quelle = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

test("Die Zeile nennt nur gesetzte Regeln, den Gruß wörtlich und die Herkunft", () => {
  assert.equal(tonSatz("anna@example.org", vorschlag()),
    "Dein Ton an anna@example.org: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 7 gesendeten Mails).");
  assert.equal(herkunft(vorschlag({gesendet: 5, belege: 2})), "(aus 5 gesendeten Mails und 2 Lernbelegen)");
  assert.equal(herkunft(vorschlag({gesendet: 0, belege: 3})), "(aus 3 Lernbelegen)");
  assert.equal(herkunft(vorschlag({gesendet: 1, belege: 1})), "(aus einer gesendeten Mail und einem Lernbeleg)");
  assert.equal(herkunft(vorschlag({gesendet: 5, personen: 2})), "(aus 5 gesendeten Mails an 2 Personen)");
  // Gemischt Du/Sie: keine Anrede im Satz, der Rest bleibt.
  assert.deepEqual(regelTeile(regeln({address: "default", gruss: "", sprache: "en", anrede_form: "nachname"})),
    ["Anrede mit Nachnamen", "kurz", "ohne Emoji", "auf Englisch"]);
  assert.equal(bestaetigtSatz({address: "sie", length: "detailed"}), "Bestätigt: Sie, ausführlich.");
  assert.equal(bestaetigtSatz({}), "Bestätigt, ohne eigene Regel.");
  assert.equal(belegeTitel(1), "Die gesendete Mail ansehen");
  assert.equal(belegeTitel(7), "7 gesendete Mails ansehen");
});

test("Der Satz je Kreis: bestätigt, vorgeschlagen, niemand zugeordnet, abgelehnt, uneinheitlich", () => {
  const stand = (mehr = {}) => ({kreis: "kollegen", kreis_text: "Kollegen", personen: 2, profile: null, proposal: null, abgelehnt: false, gesendete: [], ...mehr});
  assert.equal(kreisTonSatz(stand({profile: {id: "p", rules: regeln({gruss: ""})}})), "Kollegen: Bestätigt: Du, Anrede mit Vornamen, kurz, ohne Emoji, auf Deutsch.");
  assert.equal(kreisTonSatz(stand({proposal: vorschlag({gesendet: 5, personen: 2})})),
    "Dein Ton an Kollegen: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 5 gesendeten Mails an 2 Personen).");
  assert.equal(kreisTonSatz(stand({kreis: "innerer_kreis", kreis_text: "Innerer Kreis", proposal: vorschlag({gesendet: 3, personen: 1})})),
    "Dein Ton an den Innerer Kreis: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 3 gesendeten Mails).");
  assert.equal(kreisTonSatz(stand({personen: 0})), "Kollegen: Noch niemand bestätigt zugeordnet; Kreise legst du in der Akte einer Person fest.");
  assert.equal(kreisTonSatz(stand({abgelehnt: true})), "Kollegen: Vorschlag nicht übernommen. Kommt eine neue gesendete Mail dazu, fragt Kingfisher wieder.");
  assert.equal(kreisTonSatz(stand({personen: 1})), "Kollegen: Noch kein einheitlicher Ton in den gesendeten Mails an die Person dieses Kreises.");
  assert.equal(kreisTonSatz(stand()), "Kollegen: Noch kein einheitlicher Ton in den gesendeten Mails an die 2 Personen dieses Kreises.");
});

test("Der Hinweis beim Entwurf steht nur, solange ein Vorschlag unbestätigt ist", () => {
  assert.equal(stilHinweis({bestaetigt: false, gesendet: 7}), "Ton aus 7 gesendeten Mails vorgeschlagen, noch nicht übernommen.");
  assert.equal(stilHinweis({bestaetigt: false, gesendet: 1}), "Ton aus einer gesendeten Mail vorgeschlagen, noch nicht übernommen.");
  assert.equal(stilHinweis({bestaetigt: true, gesendet: 7}), null);
  assert.equal(stilHinweis({bestaetigt: false, gesendet: 0}), null);
  assert.equal(stilHinweis(undefined), null, "älterer Sidecar ohne das Feld: kein Hinweis");
});

test("MailStyle zeigt die Zeile mit Übernehmen und Nicht übernehmen, die Belege und die neuen Regeln", () => {
  const stil = quelle("MailStyle.tsx");
  assert.match(stil, /tonSatz\(data\.contact/);
  assert.match(stil, />\s*Übernehmen\s*</);
  assert.match(stil, />\s*Nicht übernehmen\s*</);
  assert.match(stil, /style\/ablehnen/);
  assert.match(stil, /belegeTitel\(data\.gesendete\.length\)/);
  assert.match(stil, /<ProfileSource kind="episode" id=\{beleg\.id\}[^>]*readOnly/);
  assert.match(stil, /evidence_ids: evidenceIds/, "die Bestätigung geht über den bestehenden PUT mit den Belegen");
  for (const feld of ["anrede_form", "sprache", "gruss"]) assert.match(stil, new RegExp(feld));
  assert.doesNotMatch(stil, /gesendete Mails werden nicht automatisch eingelesen/);
  assert.doesNotMatch(stil, /„[^“\n]*"/, "ein mit „ geöffnetes Zitat endet mit dem typografischen Zeichen, nie mit ASCII");
});

test("Beim Entwurf steht der Hinweis mit Weg zum Schreibstil; der Leser klappt ihn auf", () => {
  const vorschlagQuelle = quelle("MailReplySuggestion.tsx");
  assert.match(vorschlagQuelle, /stilHinweis\(suggestion\.stil\)/);
  assert.match(vorschlagQuelle, /Schreibstil ansehen/);
  assert.match(vorschlagQuelle, /onClick=\{onOpenStyle\}/);
  const leser = quelle("MailReader.tsx");
  assert.match(leser, /onOpenStyle=\{openStyle\}/);
  assert.match(leser, /ref=\{stylePanelRef\}/);
  assert.doesNotMatch(vorschlagQuelle, /„[^“\n]*"/);
});

test("Unter „Kingfisher und du“ steht der Ton je Kreis mit Übernehmen, Nicht übernehmen und Belegen", () => {
  const karte = quelle("StilKreis.tsx");
  assert.match(karte, /kreisTonSatz\(stand\)/);
  assert.match(karte, /api\.stilKreisUebernehmen\(stand\.kreis, stand\.proposal!\.rules, stand\.proposal!\.evidence_ids\)/);
  assert.match(karte, /api\.stilKreisAblehnen\(/);
  assert.match(karte, /api\.stilKreisZurueck\(/);
  assert.match(karte, /<ProfileSource kind="episode" id=\{beleg\.id\}[^>]*readOnly/);
  assert.match(quelle("Einstellungen/Ich.tsx"), /<KreisTon \/>/);
  const api = quelle("api.ts");
  assert.match(api, /\/api\/v1\/stil\/kreise/);
  assert.match(api, /\/api\/v1\/stil\/kreis\/\$\{kreis\}\/ablehnen/);
  for (const name of ["stilprofil.ts", "StilKreis.tsx", "Einstellungen/gliederung.ts"]) {
    assert.doesNotMatch(quelle(name), /„[^“\n]*"/, `${name}: typografische Anführungszeichen`);
  }
});
