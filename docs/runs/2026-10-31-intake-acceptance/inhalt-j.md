# Unabhängiges Abschlussreview – synthetischer Lauf J

**Urteil: Der Aufgabenverlust m11 aus I ist im geprüften J-Verhalten behoben. Keine neue kritische oder wichtige semantische Abweichung gefunden.** Die kombinierte Evidenz I-Aufnahme + J-Aufgaben/Abruf ist für diesen begrenzten synthetischen Umfang akzeptabel, mit den unverändert offenen m14-/q15-Abweichungen. Das ist keine allgemeine Produkt- oder Releasefreigabe und kein vollständig neu klassifizierter Gesamtlauf.

Geprüft wurden alle 24 frischen Aufgabenentscheidungen, acht Vorschlagszeilen, 16 vollständigen Antworten und 63 rohen Modelloutputs aus `/private/tmp/kf-mail-intake-quality-task-recall-20261031-j/report.json`, der Abschlusszustand `source-state.json` sowie der unveränderte I-Originalkatalog und I-Bericht. Kein Modell-/Netzaufruf, keine Privatdaten und keine Produkt-/Orakeländerung durch dieses Review.

## m11: Rohvorschlag erhalten, Modellwiderspruch nicht umetikettiert

J `model_calls[3]` extrahiert erneut den korrekten Titel „Kalkulation für Projekt Ceder senden“ mit exaktem Originalzitat. Der separate Aufgabenprüfer `[4]` antwortet unverändert falsch mit `kind=information, title_supported=false`. Sein Input enthält ausdrücklich `own_source=true`, Leas Zukunftszusage und den belegten Kandidaten. Es ist **keine erfolgreiche Modellkorrektur** und keine positive Modellannahme.

Anders als I speichert J trotzdem den vollständigen Originalsatz als ungeprüften Vorschlag: „Ich werde dir die Kalkulation für Projekt Ceder bis zum 3. November 2026 um 15:30 Uhr senden.“ `positive_review_marker=false`, Nora Berger `nora@praxis.example`, Frist `2026-11-03T15:30:00+01:00`, `quote_is_exact=true`. `temporal_status=history` und der Hinweis auf die zu prüfende Offenheit bleiben erhalten. `tasks_created_without_confirmation=0`: keine automatische Übernahme als bestätigte Aufgabe.

Damit ist der konkret beobachtete stille Verlust geschlossen. Die widersprüchliche Rohbewertung bleibt sichtbar im Laufbeleg. Nora ist Gegenüber der eigenen Zusage, nicht fälschlich deren Handelnde. Die getrennte eingehende Zusage m10 (`own_source=false`) und Annas Arbeit m08 erzeugen weiterhin keine Nutzeraufgabe, obwohl die Extraktion jeweils einen Kandidaten liefert. Es wurde also nicht jede rohe Zusage pauschal übernommen. Dieser Lauf belegt keine generelle Zuverlässigkeit des zusätzlichen Aufgabenprüfers und keine native UI-Darstellung des Widerspruchs.

## Alle 24 Aufgabenentscheidungen gegen die Originale

| Quelle | Ergebnis und semantisches Urteil |
|---|---|
| m01 | Atlas-Vorschlag vorhanden. Alter Termin im Titel bleibt historischer Originalinhalt; Fristfeld leer, `followup` auf m02, `review_required=true`, ausdrückliches Nichtübernehmen des alten Vorschlags. |
| m02 | Explizite Friständerung, keine neue separate Nutzeraufgabe; q03 verwendet den neuen Termin. |
| m03 | Privater Geschenkplan, keine Aufgabe. |
| m04 | Boreal-Vorschlag, Alex Sommer, 12.11.2026 um 16 Uhr korrekt. |
| m05 | Atlas-Zugang an separater Adresse, keine Aufgabe oder Identitätsverschmelzung. |
| m06 | Dr. Nora Berger als Namensinformation, keine Aufgabe. |
| m07 | Automatische Sendungsinformation, keine Aufgabe. |
| m08 | Annas Arbeit, Lea muss nichts erledigen. Roher Kandidat korrekt verworfen. |
| m09 | Nur bedingtes Hilfsangebot ohne Freigabe/Auftrag, keine Aufgabe. |
| m10 | Noras eingehende eigene Zusage, keine Nutzeraufgabe; rohe Extraktion korrekt ausgeschlossen. |
| m11 | Eigene Kalkulationszusage jetzt als Original-Rohvorschlag erhalten; Nora, 3.11.2026 um 15:30 Uhr, keine positive Prüfmarkierung. |
| m12 | Nicht fertig/nicht gesendet/Frist gilt, keine zusätzliche doppelte Aufgabe. |
| m13 | Agenda-Aufgabe 2.11.2026 um 17 Uhr korrekt; nicht mit der Besprechung 4.11. um 18 Uhr verwechselt. |
| m14 | Weiterhin kein Vorschlag, bekannter offener Sollwertkonflikt. `[20]` sieht nur die historische Bitte bis 1.7.2020 und extrahiert leer. m15 ist nicht im Input: **keine kausal belegte Erledigungserkennung**. |
| m15 | Alte Offerte erledigt, kein neuer Auftrag; keine neue Aufgabe. |
| m16 | Weitergeleitete alte Bitte, ausdrücklich keine neue eigene Zusage; keine Aufgabe. |
| m17 | Werbung ohne Bestellung/Zahlungsverpflichtung, keine Aufgabe. |
| m18 | Reise unbestätigt, nur bedingte Angebotsmöglichkeit; keine Buchung oder Aufgabe erfunden. |
| m19 | Rechnungsvorschlag 86,40 EUR, 12.11.2026; 23:59 als normalisierte Tagesfrist, kein Mensch aus der Serviceadresse erzeugt. |
| m20 | Allgemeine Fachbriefinformation, keine persönliche Aufgabe. |
| m21 | Manipulativer unbekannter Absender, keine Aufgabe/Freigabe oder befohlene Personenverschmelzung. |
| m22 | Vega-Vorschlag, Emma, fehlendes Maildatum bleibt unbekannt; Frist leer, `temporal_status=unknown`. Das Katalogfeld `omit_date_header=true` ist entscheidend, nicht dessen Fixture-Hilfsdatum. |
| m23 | Lumen-Vorschlag, Paul, Freitag aus Quelldatum 29.10. korrekt als 30.10.2026, 23:59 normalisiert. |
| m24 | Sirius-Vorschlag erhält „18 oder 19 Uhr“ wortgetreu. Frist bleibt leer, Klärhinweis vorhanden, `positive_review_marker=false`; rohe Prüfung `unclear` wird nicht positiv umetikettiert. |

Alle acht Vorschlagszitate sind exakt. Die sieben bereits in I vorhandenen Zeilen sind nach Entfernen des neu ausgewiesenen Feldes `positive_review_marker` vollständig identisch mit I; m11 ist die einzige zusätzliche Zeile. Importierte Vorschläge behaupten keine automatisch bestätigte aktuelle Offenheit. Die sechs positiven Prüfmarkierungen ändern die zeitlichen Vorbehalte nicht.

## Alle 16 Antworten und rohe Abweichungen

Direkter Vergleich der vollständigen `observed`-Objekte einschließlich Text, Status, Quellen und Auswahlmöglichkeiten: **alle 16 sind identisch mit I**. Zusätzlich erneut gegen die Originaltexte gelesen:

| Frage | Originalbindung und Urteil |
|---|---|
| q01 | Vier getrennte Alex-Adressrahmen, Rückfrage statt erfundener eindeutiger Frist. |
| q02 | m05: grüner Umschlag, separate Adresse; Auswahlbegrenzung sichtbar. |
| q03 | m02: geänderte Atlas-Frist 4.11.2026 um 18 Uhr. |
| q04 | m03: roter Ordner, privater Alex. |
| q05 | m04: Empfängerbitte, Boreal 12.11.2026 um 16 Uhr. |
| q06 | m06: Dr. Nora Berger und korrekte Originalsignatur. |
| q07 | m08: Anna arbeitet, Lea muss nichts erledigen. |
| q08 | Ausschließlich m11: eigene Kalkulationszusage 3.11.2026 um 15:30 Uhr; keine fremde Unterlagenzusage m10 als Beleg. |
| q09 | Vollständiges m12: noch nicht fertig, bisher nicht gesendet, Frist bleibt bestehen. |
| q10 | m13: Besprechung 4.11.2026 um 18 Uhr, getrennt von Agenda-Abgabe. |
| q11 | m15: Offerte aus 2020 geprüft/versendet, erledigt, kein neuer Auftrag. |
| q12 | m18: nicht bestätigt, Angebot bedingt, keine Buchung. Geerbtes Label `Angabe` statt semantisch treffenderem `Statusmeldung` bleibt kleine Typabweichung ohne falsche Tatsachen. |
| q13 | m19: 86,40 EUR und passende Rechnung. |
| q14 | m22: fehlendes Quelldatum erfragen, keinen Freitag aus Erfassungsdatum erfinden. |
| q15 | Begrenztes Nichtwissen ohne Belege, `unknown`; Katalog erwartet weiter `working_unknown`. Zulässiger beleggebundener Antwortvertrag, offene Mechanikabweichung, kein neuer inhaltlicher Blocker. |
| q16 | m20: allgemeine Angebotslisteninformation, ausdrücklich keine persönliche Beauftragung. |

Die 29 rohen Abrufoutputs bleiben qualitativ gemischt: q02/q07/q12 liefern unbegründet leere Antworten; q03 formuliert fälschlich „gilt ab“; q05 macht Alex zum Handelnden. q08 wählt zunächst S2/S3 und produziert zusätzliche Status-/Stichtagsformulierungen. Diese Rohfehler gelangen nicht als falsche Tatsachen oder falsche Quellen in die Endantworten. q09 bewahrt nun alle Negationen über den vollständigen Originaltext. Die 34 Aufgabenoutputs enthalten den oben belegten m11-Widerspruch, die korrekt verworfenen m08-/m10-Kandidaten sowie den unklaren m24-Termin. Keine Behauptung, alle rohen Modellentscheidungen seien richtig.

Die längeren Originalantworten sind teils umständlich, aber sachlich richtig. Auswahlgrenzen bei q02–q04 und fehlende Belegabschnitte bei q05/q12/q16 bleiben offen sichtbar; keine globale Vollständigkeitsbehauptung. Gespeicherte I-Antworten q08/q09 werden korrekt wieder angezeigt; laut Instrumentierung dafür null neue Modell- und null Embeddingaufrufe.

## Frischebasis, Transport und Ressourcen

J-Commit `d971dc4cab759948fafe493ebbc15a6f4ce1a687`. Die 24 Originale, I-Klassifikation und vorhandene BGE-Indexierung wurden wiederverwendet, **nicht neu klassifiziert oder neu indexiert**. Nur die abgeleitete `proposals.sqlite3` wurde beim Erstellen der neuen synthetischen Kopie ausgelassen; die Aufgabenentscheidung wurde für alle 24 Quellen frisch ausgeführt (20 + 4 analysiert, acht Vorschläge, keine Fehler/Abbrüche). Originaler I-Bestand blieb unangetastet.

Unabhängig nachgerechnet: alle 343 aufgezeichneten Wrapper-/Quellcodehashes und alle 19 aufgezeichneten Dateien des ursprünglichen I-Runtimebestands stimmen weiterhin mit dem Abschlusszustand überein. I-Berichtsha256 `b02a2a0879c8b7f46e3db699bd91b1ce14764899ac536dd35b60bced402300d5`, Katalogsha256 `ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda`. `originals_preserved_before/after=true`. Damit klare kombinierte Evidenz I-Aufnahme + frische J-Aufgaben + frischer J-Abruf, keine Behauptung eines komplett frischen J-End-to-End-Imports.

63 abgeschlossene native Produktaufrufe: 34 Aufgaben, 29 Abruf. Jeder aufgezeichnete Request hat ausgewähltes Produktprofil, Modell `kingfisher-qwen3.5:9b-8k`, `num_ctx=8192`, `stream/think/truncate/shift=false`; alle Antworten enden mit `done_reason=stop`. Aufgezeichnete Requestgrößen 2.943–15.749 Bytes. Keine fehlenden Transportbelege wie im alten F-Lauf. Kein protokollierter technischer Fehler, Stopgrund leer, Workerexit 0.

BGE-M3: geerbte 24 indexierte Quellen, kein Pending/Fehler vor oder nach Abruf; frische abgeschlossene Abruf-Embeddingaufrufe sind aufgezeichnet. Modellzeit 415,173 Sekunden; 427 Ressourcensamples bis 431,7 Sekunden, min. frei 27 %, max. pressure 2. Kein Watchdogabbruch. I enthielt zusätzlich die Klassifikation; der Zeitunterschied ist **kein kontrollierter Leistungsbenchmark**.

Offene mechanische Checks bleiben genau `m14:candidate_present` und `q15:status`, keine Oracleänderung, keine Genauigkeitsquote. `semantic_grade=requires_review` wurde im Laufbericht nicht umetikettiert.

## Grenzen / nicht beurteilt

Keine neue Klassifikations- oder Personenprojektionsmessung in J; hierfür gilt die bereits geprüfte I-Evidenz einschließlich der kleineren m18-Typabweichung. Keine statistische Repräsentativität, Realdaten- oder Großimportfreigabe. Keine tatsächliche Newsletterfilter-/Trusted-Opt-in-Prüfung: Die Quellenbehauptung aus m20 erteilt keine Freigabe. Keine native UI-/Installationsprüfung, kein Nachweis automatischer Aufgabenübernahme, keine allgemeine Grenzlast-/Langkontext-/Watchdogrobustheit, keine neue Vollsuite durch diesen Reviewer. Keine kausale Erledigungsleistung für m14 behauptet. Der zusätzliche Aufgabenprüfer irrt bei m11 weiterhin; akzeptiert ist die ehrliche, quellengebundene Bewahrung des unbestätigten Vorschlags.
