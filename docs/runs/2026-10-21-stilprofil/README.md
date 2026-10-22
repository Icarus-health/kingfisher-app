# Paket B5: Stilprofil aus eigenen gesendeten Mails (Ton je Person und Kreis)

Stand 22.10.2026, Branch `feat/stilprofil-20261021` auf `feat/gesendet-ordner-20261020` (PR #86, weil eigene gesendete
Mails gebraucht werden). Ausschließlich synthetische Daten (Lena Probe, Anna Berg, Lea Muster, Max Beispiel); kein echtes
Postfach, kein Modellaufruf nach außen. VERSION unverändert.

## Was gebaut wurde

| Bereich | Datei | Kern |
|---|---|---|
| Belege | `sidecar/icarus_memory/episodes.py` (`gesendete_an`, `geltende_mit_marke`, `ueberholte_fassungen`) | Eigene gesendete Mails an genau eine Adresse (Absender `ich`, einziger Empfänger, Konto), höchstens 20 jüngste, nur geltende Fassungen; Datenbank filtert vor, kein Durchlauf im Programm. Schreibbelege gezielt über die Marke ohne überholte Fassungen (Befund 1) |
| Regeln | `sidecar/icarus_memory/mail_style.py` (`regeln_aus`, `eigener_text`, `_proposal`, `_kreis_proposal`, `effective_style`, `tone_hint`) | Neue Regeln `gruss` (wörtlich, nur ganze Grußzeilen), `anrede_form`, `sprache`; zitierter Verlauf abgeschnitten (`kreis._ZITAT`); nur Einstimmigkeit; Scope `kreis:<kreis>` nur für bestätigte Kreise; Schichtung allgemein → Kreis → Kontakt; Regel fällt bei ausgeschlossenem oder überholtem Beleg |
| Routen | `mail_style.py` (`GET/PUT /api/v1/messages/{uid}/style`, `POST …/style/ablehnen`, `GET /api/v1/stil/kreise`, `PUT`/`DELETE /api/v1/stil/kreis/{kreis}`, `POST …/ablehnen`) | Vorschlag mit `evidence_ids`, `gesendet`, `belege`; Bestätigung über den bestehenden PUT (409 bei veraltetem Vorschlag); „Nicht übernehmen“ im Selbstmodell gemerkt (`mail_style_abgelehnt`), bis neue Belege dazukommen; übernommener Vorschlag wird nicht erneut vorgelegt |
| Entwurf | `sidecar/icarus_memory/mail_reply_suggestions.py` | Systemhinweis um `gruss`, `anrede_form`, `sprache` ergänzt; bei `sprache=en` englischer Entwurf; Antwort trägt `stil` (bestätigt, Zahl gesendeter Mails) |
| Oberfläche | `app/kingfisher/src/stilprofil.ts`, `MailStyle.tsx`, `MailReplySuggestion.tsx`, `MailReader.tsx`, `StilKreis.tsx`, `Einstellungen/Ich.tsx`, `api.ts` | Zeile „Dein Ton an anna@…: Du, kurz, … (aus 4 gesendeten Mails).“ mit Übernehmen, Nicht übernehmen, Belege zum Aufklappen (Mail öffnen); Hinweis beim Entwurf mit „Schreibstil ansehen“; Ton je Kreis unter Kingfisher und du |
| Doku | `docs/release/MAIL-STYLE-QA.md`, `docs/37-pruefbefunde.md` (Befund 1), `docs/49-kreis-und-privat.md` (Ton je Kreis), `docs/DEVELOPER-START.md` (Codekarte), Modulkommentar `mail_style.py` | |

## Tests

Erst rot, dann grün (gezielt `test_mail_style.py`, `test_mail_reply_suggestions.py`, neu `test_stilprofil.py`):

| Lauf | Ergebnis |
|---|---|
| Vorher (Bestand, 2 Dateien) | 16 bestanden |
| Neue Tests vor der Änderung (3 Dateien) | 18 rot, 14 grün |
| Nach der Änderung (3 Dateien) | 32 bestanden (14 neu in `test_stilprofil.py`, 2 neu in `test_mail_reply_suggestions.py`; 3 bestehende um die neuen Felder `gruss`, `anrede_form`, `sprache` und die Schicht `kreis` ergänzt) |
| Volle Suite `pytest sidecar/tests -q -n auto` (18:09 min) | 7.776 bestanden, 0 fehlgeschlagen, 3 übersprungen, 26 Untertests bestanden |
| Oberfläche `npm test` | 773 bestanden (6 neu in `stilprofil.test.mjs`) |
| `npx tsc --noEmit` | ohne Befund |
| `npm run build` | gebaut |
| `scripts/pruefe_anfuehrungszeichen.py` über alle geänderten Dateien | ohne Befund |

Laufzeit: 10.003 Episoden (10.000 synthetische Mails, je zur Hälfte eigene und fremde, an 200 Adressen; dazu drei an
Lea), Vorschlag über die Route `GET …/style`: **66 ms** (Grenze im Test 1 s, `test_vorschlag_bei_zehntausend_episoden_unter_einer_sekunde`).

Neu geprüft: Vorschlag aus drei gesendeten Mails mit Belegen, Bestätigung über PUT mit `evidence_ids`, danach kein
erneuter Vorschlag bis zu einer neuen Mail; zwei Mails reichen nicht, ein Lernbeleg ergänzt; gemischt Du/Sie ergibt keine
Anrede, Gruß und Länge bleiben; Mehrfachempfänger, fremdes Konto und ein nicht als „ich“ bekannter Absender zählen nicht,
die eigene Adresse im Cc schadet nicht; zitierter Verlauf wird abgeschnitten (auch in den gezeigten Belegen); Gruß
wörtlich, Englisch, Nachname mit Titel; verschiedene Grüße ergeben keinen Gruß; Widerruf bei ausgeschlossener und bei
überholter Mail; veralteter Vorschlag 409; „Nicht übernehmen“ gemerkt bis neue Belege; Kreisregel nur für bestätigte
Kreise, Schichtung allgemein → Kreis → Kontakt, Kreiswechsel; Kreisvorschlag einstimmig über drei Personen (zwei Du, eine
Sie: keine Anrede), unbestätigte Person zählt nicht, Ablehnung je Kreis; `_examples` ohne überholte Fassung (direkt und
über die Route); Systemhinweis mit Grußformel, Anredeform, Sprache und englischem Entwurf; `stil` in der Antwort.

## Sabotageproben

Jede Zusicherung absichtlich gebrochen (im Arbeitsbaum, danach `git checkout` der Datei), die drei gezielten Dateien
(32 Tests) beziehungsweise `stilprofil.test.mjs` (6 Tests) laufen gelassen. Zahlen aus den Läufen.

| Nr. | Sabotage | Test rot |
|---|---|---|
| 1 | Mehrfachempfänger zählen als Beleg (`gesendete_an`: Adresse muss nur vorkommen) | 1 failed, 31 passed (`test_mehrfachempfaenger_und_fremde_konten_zaehlen_nicht`) |
| 2 | Zitierter Verlauf nicht abgeschnitten (`eigener_text`) | 1 failed, 31 passed (`test_zitierter_verlauf_wird_abgeschnitten`) |
| 3 | Mehrheit statt Einstimmigkeit bei der Anrede (`regeln_aus`) | 3 failed, 29 passed (gemischt Du/Sie, Kreisvorschlag, bestehender `test_mixed_form_of_address_does_not_infer_du`) |
| 3b | Mehrheit statt Einstimmigkeit über die Kontakte des Kreises (`_kreis_proposal`) | erst 0 rot (Test zu schwach: zwei Personen), nach drittem Kollegen per Sie 1 failed, 31 passed (`test_kreisvorschlag_einstimmig_ueber_die_kontakte_des_kreises`) |
| 4 | Unbestätigter Kreis wirkt (`_kreis_von` gibt „kollegen“ statt nichts) | 1 failed, 31 passed (`test_kreisregel_nur_fuer_bestaetigten_kreis_…`) |
| 5 | Regel ohne Bestätigung wirksam (Vorschlag fließt in `effective_style`) | 5 failed, 27 passed |
| 6 | Überholte Fassung gelesen (`geltende_mit_marke` ohne Zeiger-Bedingung) | 1 failed, 31 passed (`test_examples_lesen_keine_ueberholte_fassung`) |
| 6b | Überholte Fassung trägt die Regel weiter (`_belege_gelten` ohne `ueberholte_fassungen`) | 1 failed, 31 passed (`test_widerruf_…`) |
| 7 | Ausgeschlossene Mail trägt die Regel weiter | 1 failed, 31 passed (`test_widerruf_…`) |
| 8 | „Nicht übernehmen“ wird nicht gemerkt | 2 failed, 30 passed (Person und Kreis) |
| 9 | Anderes Konto zählt als Beleg | 1 failed, 31 passed |
| UI-1 | Zeile ohne Herkunft („aus 4 gesendeten Mails“ fehlt) | 2 fail, 4 pass |
| UI-2 | Hinweis beim Entwurf trotz bestätigtem Kontaktstil | 1 fail, 5 pass |

## Browserprobe

`scripts/probe_stilprofil_ui.py` (Chromium `/opt/pw-browsers/chromium-1194`, echter Sidecar, IMAP-Attrappe mit fünf
Mails im Posteingang und fünf eigenen in „Gesendet“: vier an Anna allein, eine an Anna und Jonas; Skriptmodell, das den
Entwurf aus dem Systemhinweis baut, kein Sprachmodell). Ergebnis `ok: true`, Konsole leer; 1280 und 390 px ohne
seitliches Scrollen (390/390 an beiden Stellen).

| Bild | Was zu sehen ist |
|---|---|
| `stilprofil-1-vorschlag.png`, `-390.png` | Nachrichten → Mail von Anna → Antwort schreiben → Schreibstil: „Dein Ton an anna.berg@example.org: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 4 gesendeten Mails).“, Knöpfe Übernehmen, Nicht übernehmen, Für alle Kontakte übernehmen; „4 gesendete Mails ansehen“; Kreiszeile „Kreis „Kollegen“: ohne eigene Regel.“ |
| `stilprofil-2-belege.png` | Die vier Belege mit Betreff, Zeit, eigenem Text (ohne den zitierten Verlauf aus „Re: Angebot“) und „Mail öffnen“; die Mail an zwei Empfänger fehlt |
| `stilprofil-3-hinweis.png` | Entwurf vor dem Übernehmen per Sie („Sehr geehrte Frau Berg, … Mit freundlichen Grüßen“); darunter „Ton aus 4 gesendeten Mails vorgeschlagen, noch nicht übernommen. Schreibstil ansehen“; der Klick klappt den Schreibstil auf |
| `stilprofil-4-uebernommen.png` | „Übernommen. Dieser Ton gilt jetzt für Entwürfe an diesen Kontakt.“; die Vorschlagszeile ist weg, Anrede steht auf Du |
| `stilprofil-5-entwurf-mit-ton.png` | Neuer Entwurf: „Hallo Anna, ja, das passt. Ich schicke dir das Angebot bis Freitag. Viele Grüße Lena“; kein Hinweis mehr |
| `stilprofil-6-kreis-vorschlag.png`, `-390.png` | Einstellungen → Kingfisher und du → „Dein Ton je Kreis“: Innerer Kreis und Kontakte „Noch niemand bestätigt zugeordnet“, Kollegen „Dein Ton an Kollegen: … (aus 4 gesendeten Mails).“ mit Übernehmen |
| `stilprofil-7-kreis-bestaetigt.png` | „Kollegen: Bestätigt: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch.“ mit „Regel zurücknehmen“; im Selbstmodell genau zwei Regeln (Kontakt, `kreis:kollegen`) |

Die Bilder liegen außerhalb des Repositories (Scratchpad der Sitzung).

## Abweichungen vom Bauplan und Grenzen

* **Belege kommen über eine gezielte SQL-Abfrage, nicht über den Bezüge-Index.** `gesendete_an` filtert in der Datenbank
  (Adresse im Dokument, Absender „ich“, geltende Fassung) und prüft jede Zeile in Python genau; der Index `sach_bezuege`
  hängt am Hintergrundabgleich und stünde im Stilgedächtnis nicht immer bereit.
* **Überholt heißt: Der Versionszeiger zeigt woandershin.** Schreibbelege tragen einen Quellenschlüssel, hatten aber nie
  einen Zeiger; `sql_aktuelle_fassung` hätte sie alle entzogen. `geltende_mit_marke` gilt deshalb für Belege ohne
  Zeiger weiter; `add_example` setzt den Zeiger jetzt, damit derselbe Beleg mit anderem Leerraum die Fassung ersetzt.
* **`sprache`** erkennt nur Deutsch und Englisch über Stoppwörter; Dialekt nicht. Für alles Deutsche entsteht die
  Regel „Deutsch“, sichtbar in der Zeile; sie ändert am Entwurf nichts. Nur `en` wechselt die Sprache des Entwurfs.
* **Grußformel** nur, wenn eine ganze Schlusszeile einer bekannten Formel entspricht (höchstens 40 Zeichen); freier Text
  einer Mail gelangt so nicht in den Systemhinweis. Ein ungewöhnlicher Gruß wird nicht erkannt.
* **Form der Anrede** liest nur die erste Zeile; „Hallo Anna“ ist Vorname, „Hallo Frau Dr. Berg“ Nachname, „Hallo“ allein
  nur Hallo.
* **Kreis einer Person** über `person:a:<adresse>`; eine zusammengeführte Person mit anderer Kennung bekommt keinen
  Kreis-Ton (fail closed).
* **Kreisvorschlag** zählt gesendete Mails aus allen Konten (der Kreis ist kontounabhängig); der Kontaktvorschlag nur
  das Konto der Mail.
* **Übernommener Vorschlag** wird nicht erneut vorgelegt (gleiche Belege, gleiche Regeln, für den Kontakt oder allgemein);
  das war im Bauplan nicht genannt, fiel aber in der Browserprobe auf (Zeile blieb nach „Übernehmen“ stehen).
* **Kreisabfrage je Person.** `GET /api/v1/stil/kreise` fragt die gesendeten Mails je bestätigter Person einzeln ab
  (eine Datenbankabfrage je Person); bei sehr vielen bestätigten Kollegen wird die Karte spürbar langsamer. Gemessen
  ist nur der Kontaktfall (66 ms bei 10.003 Episoden).
* **Wie ein echtes lokales Modell** `gruss`, `anrede_form` und `sprache` umsetzt, ist hier nur mit dem Skriptmodell
  geprüft; ein Lauf mit Ollama steht aus.
* Nicht am Mac geprüft; die Route `PUT /api/v1/kreis` in der Probe setzt den Kreis, wie es der Klick in der Akte täte.
