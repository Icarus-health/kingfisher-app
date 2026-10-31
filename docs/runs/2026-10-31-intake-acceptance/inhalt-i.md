# Unabhängiges semantisches Review – vollständiger synthetischer Lauf I

**Urteil: technische Durchführung vollständig, Qualitätsfreigabe für die gesamte Aufnahme-/Aufgabenkette nicht erteilt.** Ein neuer wichtiger Fehler verliert die eindeutige eigene Zusage m11. Der Abruf aller 16 Fragen bewahrt dagegen die relevanten Personen, Originalbelege, Fristen und Negationen; insbesondere bleiben die Reparaturen für q08 und q09 wirksam. Keine neue kritische Falschbehauptung in den gerenderten Antworten gefunden.

Geprüft: `/private/tmp/kf-mail-intake-quality-live-20261031-i/{report.json,catalog.json}` und die benachbarte `.source-state.json`; sämtliche 24 Aufnahme-/Aufgabenentscheidungen, sieben resultierende Vorschläge, 16 vollständige Antworten und 87 rohe Modellantworten einschließlich verworfener Sätze. Vergleich mit G und H; H war ausschließlich ein Abruflauf mit wiederverwendeter G-Aufnahme, I ist wieder eine vollständige frische Aufnahme. Keine Modelle, Netzaufrufe, privaten Mailbestände oder Änderungen an Produkt, Katalog oder Orakel.

## Wichtiger Befund: m11 geht in der zusätzlichen Aufgabenprüfung verloren

**Schwere: wichtig / Blocker für die behauptete vollständige Aufgabenqualität.** Fundstelle: I `report.json`, `model_calls[23]`, `[38]`, `[39]` (nullbasiert), `task_checks[id=m11]` und fehlender Eintrag in `task_rows`.

Original m11 von Lea an Nora: „Ich werde dir die Kalkulation für Projekt Ceder bis zum 3. November 2026 um 15:30 Uhr senden.“ Die Arbeitsspeicherklassifikation `[23]` liefert korrekt `commitment`. Der getrennte TaskDetector-Aufruf `[38]` extrahiert korrekt `Kalkulation für Projekt Ceder senden` samt exaktem Originalzitat; der Adressrahmen kennzeichnet Lea als `ich=true` und Nora als `ich=false`. Erst die zusätzliche Aufgabenprüfung `[39]` verwirft den Kandidaten mit `kind=information, title_supported=false`, obwohl ihr Eingabepayload ausdrücklich `own_source=true`, den eindeutigen Zukunftssatz und den belegten Titel enthält.

Das ist ein falscher Negativbefund des Aufgabenprüfers, **keine belegte Fehlklassifikation des Arbeitsspeichers**. m12 ist nicht Bestandteil dieses Prüfprompts; eine kausale Erledigungsunterdrückung lässt sich deshalb nicht behaupten. Außerdem erklärt m12 ausdrücklich „noch nicht fertig“, „bisher nicht gesendet“ und den Fortbestand der Frist. Korrekte spätere Antworten q08/q09 ersetzen den verlorenen Aufgabenvorschlag nicht.

Minimales erforderliches Verhalten: Eine widersprüchliche zusätzliche Modellprüfung darf diesen quellenbelegten Kandidaten nicht still verlieren; mindestens muss er als ungeklärter Vorschlag mit Originalbeleg erhalten bleiben. Keine pauschale Übernahme aller Zusagen allein aufgrund des Klassifikationstyps. Verifikation: den exakten Extraktions-/Prüfoutput reproduzierbar abspielen und zusätzlich Fremdzusage m10, Anna/Lea m08, bedingte m09 sowie historische/weitergeleitete m16 als negative Kontrollen behalten. Ein neuer echter Modellnachweis wäre separat auszuweisen; dieses Review führt keinen durch.

## Aufnahme und Aufgaben: alle 24 Quellen

Alle Originaltexte und das fehlende Quelldatum von m22 bleiben erhalten. Vorschläge sind keine automatisch bestätigten Aufgaben: `tasks_created_without_confirmation=0`. Alle sieben gespeicherten Vorschläge haben exakte Originalzitate.

| Quelle | Einordnung in I | Semantische Prüfung der Aufgabenentscheidung |
|---|---|---|
| m01 | request | Atlas-Bitte vorhanden. Alter Titel nennt 2.11., aber `followup`, `review_required=true`, Fristfeld leer, Verweis auf m02 und ausdrückliches „alten Vorschlag nicht übernehmen“. Keine Freigabe der alten Frist. |
| m02 | change | Änderung auf 4.11.2026, 18 Uhr erhalten; keine zusätzliche eigene Aufgabe. |
| m03 | fact | Privater roter Ordner; keine Aufgabe und keine Verwechslung mit geschäftlichem Alex. |
| m04 | request | Boreal, Alex Sommer, 12.11.2026, 16 Uhr korrekt; importierter Vorschlag mit Offenheitsvorbehalt. |
| m05 | fact | Grüner Umschlag an separater Adresse; keine Identitätszusammenführung oder Aufgabe. |
| m06 | fact | Dr. Nora Berger korrekt; Signaturblock diesmal irrelevant statt zusätzlichem fact wie G. Keine Aufgabe. |
| m07 | fact | Automatischer Servicehinweis ohne eigene Aufgabe. |
| m08 | fact | Annas Arbeit, Lea muss nichts erledigen; extrahierter Rohkandidat korrekt verworfen. |
| m09 | conditional | Bedingtes Angebot, keine unbedingte Aufgabe. |
| m10 | commitment | Noras eigene eingehende Zusage; Rohkandidat korrekt als keine eigene Nutzeraufgabe verworfen. |
| m11 | commitment | **Eigene eindeutige Zusage fälschlich durch zusätzliche Aufgabenprüfung verloren**, siehe oben. |
| m12 | status | Nicht fertig/nicht gesendet/Frist gilt; keine neue separate Aufgabe. |
| m13 | fact + request | Besprechung 4.11., 18 Uhr getrennt von Agenda-Abgabe 2.11., 17 Uhr; Agenda-Vorschlag korrekt. |
| m14 | request | Kein Kandidat. Bekannter offener Sollwertkonflikt: Katalog verlangt historischen Vorschlag; m15 sagt erledigt. Der isolierte Extraktionsaufruf `[48]` enthält m15 nicht und liefert leer. **Keine kausale Anerkennung als erfolgreiche Erledigungserkennung.** |
| m15 | status | Erledigte Offerte aus 2020, kein neuer Auftrag; keine neue Aufgabe. |
| m16 | fact + historical | Weitergeleitete alte Bitte von Pia wird keine eigene neue Zusage. |
| m17 | leer / irrelevant | Werbung ohne Aufgabe; diesmal bereits leere Extraktion. |
| m18 | fact | Kleinere Typabweichung: ausdrücklicher unbestätigter Buchungsstatus passt besser zu status. Negation vollständig erhalten, keine Buchung oder Aufgabe erfunden. |
| m19 | request | Rechnung 86,40 EUR, 12.11.2026; Tagesfrist 23:59 als normalisierter Vorschlag, keine Person aus Serviceadresse erfunden. |
| m20 | fact | Allgemeine Fachbriefinformation, keine persönliche Aufgabe. Trusted-Opt-in nicht ausgeübt; Quellenbehauptung ist keine Freigabe. |
| m21 | leer / irrelevant | Manipulativer unbekannter Absender erzeugt weder Aufgabe noch befohlene Zusammenführung/Freigabe. |
| m22 | request | Vega-Prüfung vorhanden, Datum und relative Freitagsfrist bleiben ungeklärt; received_at und Frist leer, temporal unknown. |
| m23 | request | Lumen, Paul, Freitag aus Quelldatum 29.10. als 30.10.2026, 23:59 aufgelöst; importierter Prüfvorbehalt. |
| m24 | request | Sirius-Bitte vorhanden. Anders als G uncertain ist request für die eindeutige Bitte vertretbar; unklare Uhrzeit 18 oder 19 Uhr wird ausdrücklich bewahrt, kein erfundener Fälligkeitswert. |

Die Personenprojektion enthält zehn belegte Menschen. Drei Alex-Winter-Adressen und Alex Sommer bleiben getrennt, q01 fragt nach. Die fünf Serviceadressen (Versand/Rechnung, Shop-Angebote, Buchung, Praxisbedarf-Rechnung, Fachbrief) und der unbekannte Absender sind im Graph mit `quality_category=review` erfasst und aus der bestätigten Personenprojektion ausgeschlossen. Der interne Graph-Knotentyp heißt weiterhin `person`; das ist keine Behauptung, diese sechs Einträge seien bestätigte Menschen. Die Legacy-Liste enthält weiterhin den unbekannten Absender; ihre grünen Checks allein beweisen dessen korrekte Behandlung nicht. Maßgeblich ist die explizit geprüfte Projektion samt Review-Kategorie.

## Antworten: alle 16 Fragen

| Frage | Beleg und Urteil |
|---|---|
| q01 | Vier getrennte Alex-Adressrahmen zur Auswahl, keine erfundene eindeutige Frist. |
| q02 | m05: grüner Umschlag, korrekte separate Adresse; begrenzte Auswahl ausdrücklich sichtbar. |
| q03 | m02: neue Atlas-Frist 4.11.2026, 18 Uhr; Originalkorrektur statt irreführendem rohem „gilt ab“. |
| q04 | m03: roter Ordner, Privatadresse korrekt. |
| q05 | m04: vollständige Empfängerbitte, 12.11., 16 Uhr; roher falscher Akteur Alex als Leistender gelangt nicht in die Antwort. |
| q06 | m06: Dr. Nora Berger einschließlich korrekter Originalsignatur. |
| q07 | m08: Anna arbeitet; Lea muss nichts erledigen. |
| q08 | **Nur m11**: eigene Kalkulationszusage, 3.11., 15:30. Fremde Unterlagenzusage m10 nicht sichtbar und nicht als Beleg gebunden. |
| q09 | **Vollständiger m12-Originaltext** mit nicht fertig, nicht gesendet und fortbestehender Frist. Keine erneute Negationsverkürzung wie G. |
| q10 | m13: Besprechung 4.11., 18 Uhr, nicht Agenda-Abgabefrist. |
| q11 | m15: alte Offerte geprüft/versendet, erledigt, kein neuer Auftrag. |
| q12 | m18: Reise nicht bestätigt, Angebot nur bedingt, keine Buchung. Label „Angabe“ statt H „Statusmeldung“; Fakten unverändert korrekt. |
| q13 | m19: 86,40 EUR und 12.11.; richtige Rechnung. |
| q14 | m22: fragt nach fehlendem Quelldatum statt Freitag aus Erfassungszeit zu erfinden. |
| q15 | Keine Belege, begrenztes Nichtwissen. `unknown` statt Katalog `working_unknown` bleibt offen dokumentiert; inhaltlich zulässiger beleggebundener Vertrag, kein neuer Qualitätsblocker. |
| q16 | m20: allgemeine Angebotslisteninformation, ausdrücklich keine persönliche Beauftragung. Keine Bestätigung eines vertrauenswürdig gesetzten Newsletter-Opt-ins. |

Direkter JSON-Vergleich der vollständigen `observed`-Objekte mit H: nur q12 unterscheidet sich, ausschließlich durch „Angabe“ statt „Statusmeldung“. Alle anderen 15 sichtbaren Antworten einschließlich Quellen, Status und Auswahlmöglichkeiten sind identisch. Die längeren Originalantworten sind teils umständlich, aber sachlich richtig; sie werden nicht als Halluzination eingestuft. Auswahlgrenzen bei q02–q04 und fehlende Belegabschnitte bei q05/q12/q16 sind sichtbar, keine falsche globale Vollständigkeitsbehauptung.

Rohqualität bleibt begrenzt: q02/q07/q12 liefern teils unbegründet leere Ergebnisse, q03 eine falsche Zeitrelation und q05 den falschen Handelnden. q08 wählt zunächst weiterhin S2/S3, erhält vor der Formulierung aber den eingeschränkten eigenen Kontext; zusätzliche rohe Status-/Stichtagssätze werden nicht übernommen. q09 hat rohe vollständige Negationen; die Ausgabe bewahrt sie nun durch Originalfallback. Diese Schutzwirkung ist Produktverhalten, kein Beweis, dass jeder rohe Modellsatz richtig war. Kein freier Modellaufruf für q01/q15.

## Tatsächlicher Pfad, Ressourcen und Grenzen

Commit `bbb6497145b69c07a7124ecafd0d2169fbc6f86c`, laut Abschlusszustand sauber und während des Laufs unverändert. Alle 343 aufgezeichneten Wrapper-/Quellcodehashes wurden zusätzlich gegen die aktuell vorliegenden Dateien gelesen und stimmen überein. Kataloghash erneut berechnet: `ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda`.

87 echte protokollierte Produktaufrufe: 24 Aufnahme, 34 Aufgaben, 29 Abruf. Jeder hat `profile_selected_at_call=true`, `product_provider=true`, tatsächlichen Requestpayload und Antwort; überall Modell `kingfisher-qwen3.5:9b-8k`, `num_ctx=8192`, `stream=false`, `think=false`, `truncate=false`, `shift=false`, Abschluss `done_reason=stop`. Aufgezeichnete komplette Requestgrößen 2.943–15.749 Bytes, unter 16.000. Anders als F ist der Native-Pfad damit unmittelbar belegt. Das beweist keine beliebige 8K-Grenzfalltauglichkeit über diese Requests hinaus.

BGE-M3: drei abgeschlossene Indexbatches zu acht Quellen, separate Abruf-Embeddingaufrufe; Coverage 24 indexiert, keine fehlgeschlagenen oder ausstehenden Quellen vor/nach Abruf. Keine aufgezeichneten technischen Fehler, Worker normal beendet. Der äußere Exitcode 1 und die roten Mechanikchecks werden nicht als grüner Gesamterfolg umetikettiert. Offen bleiben `task:m11:candidate_present`, `task:m14:candidate_present`, `question:q15:status`; keine Genauigkeitsquote. Der Checknenner ist zudem vom Vorhandensein der Kandidaten abhängig.

572,59 Sekunden summierte Modellzeit, 585 Ressourcensamples bis 591,9 Sekunden; Minimum frei 25 %, höchster pressure-Wert 2. Kein protokollierter Watchdogabbruch. Gegen G (599,344 Sekunden/88 Aufrufe) ist dies eine Beobachtung unterschiedlicher Läufe, **kein kontrollierter Geschwindigkeitsbenchmark**. H enthielt nur Abruf und ist als Gesamtlaufzeit nicht vergleichbar.

Nicht beurteilt/freigegeben: Realdatenqualität oder Großimport (nur synthetischer Entwicklungskatalog); statistische Verlässlichkeit über diese Fälle hinaus; tatsächliche Newsletterfilterung/Trusted-Opt-in (Fixture übt sie nicht aus); native UI-Nutzung oder Installation; automatische Aufgabenübernahme (nicht ausgeführt); allgemeine Langkontext-, Abbruch- und Grenzlastrobustheit (dieser Lauf löst solche Grenzfälle nicht aus); Behebung von m14 durch Threadverständnis (nicht kausal belegt); Produktionsrelease/Vollsuite (nicht Gegenstand dieses Reviews). Keine Produktqualitätsfreigabe, solange der neue m11-Verlust offen ist.
