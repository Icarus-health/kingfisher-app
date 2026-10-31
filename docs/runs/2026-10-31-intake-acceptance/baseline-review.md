# Lokale Aufnahme-/Abrufprobe – 31.10.2026

## Ergebnis

Die Ressourcen erlauben den begrenzten Lauf; keine Qualitätsfreigabe und kein Großimport.
Getesteter Quellstand entspricht der installierten Fassung 1.0.35, Commit
`68767ac6d62e7dc117c62aa39e3f784e8aa8af1f`.

- 24 künstliche Mails, 16 Fragen. Eingefrorener Katalog unverändert:
  `ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda`.
- Ausschließlich vorhandenes lokales Qwen9B und BGE-M3. Diagnosetransport mit 8K Kontext,
  maximal 1.200 Ausgabetoken, 140 Aufrufen/900 Sekunden. Keine Cloud-API.
- 284,5 Sekunden, 282 Ressourcenmesspunkte; Reserve mindestens 31 %, Speicherdruck höchstens 2.
  Start dreimal Stufe 1 / 67 %; danach Stufe 1 / 62 %, keine Modelle mehr geladen.
- Native Kingfisher-Navigation Heute → Gedächtnis → Heute unter Last erfolgreich;
  gemessener Klick/AX-Zustandswechsel ungefähr 1,2 s. Kein Gesamtbenchmark anderer Mac-Programme.
- Alle 24 Originaltexte und fehlende Quelldaten erhalten, keine Aufgabe ohne Bestätigung angelegt.
- Persönlicher Bestand getrennt: Fassung 1.0.35, beide Konten erhalten, globale Importpause weiterhin true.

## Bestätigte fachliche Probleme

1. **q05/m04: Zuständigkeit vertauscht.** Die Antwort sagt, Alex Sommer müsse Druckdaten senden.
   Die Originalmail von Alex bittet dagegen die Empfängerin Lea, diese zu senden. Datum und Beleg stimmen;
   dadurch wird die falsche Zuständigkeit nicht richtig. Der automatische Wort-/Quellenvertrag übersieht dies.
2. **m19: Rechnungsaufgabe fehlt.** Eine ausdrückliche Zahlung von 86,40 EUR bis 12.11.2026
   wird nicht als Kandidat erhalten. Der Modell-Titel enthält die nur im Betreff vorhandene Nummer 184;
   der exakte Körperbeleg enthält sie nicht. `memory_analysis.interpret` verwirft den Kandidaten über
   `hard_details_supported`. Den Belegschutz erhalten; einen gültigen Vorgang nicht still verlieren.
3. **m24: Handlung verschwindet mit unklarer Uhrzeit.** Antrag einreichen ist klar; offen sind 18 oder 19 Uhr.
   Die zweite Prüfung verwirft die ganze Aufgabe. Benötigt wird ein prüfbarer Vorgang mit Rückfrage zur Uhrzeit,
   keine erfundene Uhrzeit und kein Weglassen der Verpflichtung.

## Was noch nicht fachlich geprüft wurde

- q02–q04: Eingaben von 16.802 / 16.455 / 16.545 Byte überschreiten den unveränderten 16.000-Byte-Schutz
  der 8K-Diagnose. Kein Modellaufruf für diese Auswahl. Drei geschützte Ablehnungen, kein Beweis für ein
  Scheitern des 32K-Produkttransports. Keine Grenze gelockert und nichts still gekürzt.
- q15–q16: Der Diagnoseadapter lehnt den normalen Agentenaufruf mit Werkzeugdefinitionen ab.
  Der Text „Modell nicht erreichbar“ ist hier kein Nachweis eines Ollama-Ausfalls.
- BGE-M3 indiziert die 23 vorhandenen Belegabschnitte vollständig. Nach zwei regulären Agentenrückfällen
  zeigt die Abdeckung zwei neu ausstehende Quellen. Daher ist `pipeline_complete` auch technisch false.
- Die tatsächliche Personen-UI wurde in dieser synthetischen Probe nicht abgenommen. Der alte
  `personen.alle`-Kontaktbestand enthält Angebots-/Buchungs-/Redaktionsabsender; der Prüfvertrag misst
  keine `quality_category`. Graph/UI-Zuordnung separat verifizieren, keine pauschale Personenfreigabe.
- m20 ist als leer/irrelevant eingeordnet. Der Originaltext bleibt gespeichert. Die Quelle bezeichnet
  sich selbst als ausgewählten Fachbrief; die Fixture setzt keine gesonderte vertrauenswürdige
  Newsletterfreigabe. Daraus nicht ableiten, dass Quellen solche Freigaben selbst erteilen dürfen.
  Newsletterauswahl und Abrufabbildung müssen separat geprüft werden; q16 bleibt ungeprüft.
- m14 erwartet laut festem Prüfvertrag einen historischen Prüfkandidaten. m15 bezeichnet die alte Sache
  ausdrücklich als erledigt. Keine offene aktuelle Aufgabe ist fachlich vertretbar; der Einzelaufruf zu m14
  belegt aber keine intelligente Zusammenführung mit m15. Sollwertkonflikt offen dokumentiert.

## Einzelprüfung der Antworten

| Fälle | Bewertung |
|---|---|
| q01 | passende Rückfrage, vier Alex-Postfächer unterscheidbar |
| q02–q04 | technisch nicht geprüft, Budgetschutz greift |
| q05 | falsch: verantwortliche Person vertauscht |
| q06 | Signaturname korrekt |
| q07 | Originalquelle weist Anna die Arbeit zu, Lea hat nichts zu tun |
| q08 | eigene gesendete Zusage, korrekte Frist 3.11. / 15:30 |
| q09 | nicht fertig, nicht gesendet, keine erfundene Erledigung |
| q10 | Besprechung 4.11. / 18 Uhr korrekt von Agenda-Frist getrennt |
| q11 | alte Sache erledigt, kein neuer Auftrag |
| q12 | Reise nicht bestätigt, keine Buchung behauptet |
| q13 | Rechnungsbetrag korrekt wiedergefunden; Aufgabenlücke bleibt |
| q14 | fehlendes Quelldatum erkannt, keine Freitags-Datierung erfunden |
| q15–q16 | technisch nicht geprüft, Adapter verweigert Werkzeugdefinitionen |

Damit 10 akzeptable Endantworten, eine fachlich falsche, fünf technisch nicht geprüfte.
Das ist keine Genauigkeitsschätzung für reale Mails. Mehrere akzeptable Antworten sind gerahmte
Originalquellen statt einer neu formulierten Modellantwort.
Die automatische Wertung 135/152 bzw. 11/16 beantwortet die fachliche Freigabefrage nicht.

Unabhängige Gegenprüfung durch `review_live_intake_quality` bestätigt die Zuständigkeitsverwechslung
und beide nützlichen Aufgabenlücken; m20/Personen-/m14-Grenzen wurden anschließend gesondert eingeordnet.
Keine Wiederholung ausgewählter guter Fälle, kein veränderter Katalog, keine abgesenkten Schutzschwellen.

Nächste abgegrenzte Reparatur: Zuständigkeit in belegten Antworten sichern, gültige Kandidaten bei
Beleg-/Uhrzeit-Unklarheit prüfbar erhalten; Diagnosepfade an den tatsächlichen Abruf anbinden. Danach denselben
vollständigen Katalog erneut prüfen, erst anschließend echte Mail-Stichprobe. Großimport bleibt pausiert.
