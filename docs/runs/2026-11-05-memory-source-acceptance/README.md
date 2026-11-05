# Gedächtnisaufnahme: synthetischer Abnahmesatz

Stand 5. November 2026. Diese Prüfung bereitet die unabhängige Qualitätsprobe vor. **Keine Bewertung von Personen-, Aufgaben-, Frist- oder Antwortqualität; kein Großimport und kein Modellaufruf.**

## Beobachteter Basislauf

Der eingefrorene Satz `../../fixtures/memory-acceptance-20261104/heldout-v2` enthält 100 Maildatensätze und zehn native Dateien. Über die wirklichen Mail-, MIME-, PDF-, Text-/Transkript-, DOCX- und Kalenderleser entstanden 109 Episoden. 105 Aufnahmebelege sind vollständig, vier teilweise und die spätere Kalenderabsage N06 ist zurückgehalten. Die beiden PDFs sind ausschließlich Kinder der zugehörigen Mails. Wiederholte Aufnahme erzeugte keine weiteren Episoden.

Bei N07 bis N10 wird die externe Quellenzeit im Prüfbeleg ausgewiesen, aber nicht als strukturierte Ereigniszeit gespeichert. `occurred_at` bleibt leer; die Aufnahmezeit ersetzt diese fehlende Angabe nicht. Das ist eine sichtbare Teilabdeckung.

Der ursprüngliche JSON-Beleg ist [baseline-before-calendar-fix.json](baseline-before-calendar-fix.json), SHA-256 `d78da82d6e6126f644e0a590db5113883b0f65c51ec7d3d048eac91bb4076b0a`. Er wurde mit dem Kalendercode aus `ff2f07513a64dab09735d3dc7831f25000cc9af7` erzeugt, bevor die gesonderte Kalenderkorrektur begann. Spätere Prüfungen ersetzen diesen Nachweis nicht.

## Noch getrennt zu prüfen

Der [Zustandsvertrag am Basisstand](state-contract-at-ff2f075.md) ordnet alle neun Zweige und elf Fragen tatsächlichen Produktwegen zu. Er enthält ausdrücklich offene Grenzen, beispielsweise bestätigte Aufgabeninhaber, Erledigungswissen im freien Abruf und unvollständige Mailaufnahme. Der ursprüngliche ICS-Parser verwirft die einzige Absage; ein leerer Kalenderabschnitt entzieht deshalb den alten Termin nicht. Der Vertrag beschreibt den Befund vor der laufenden Korrektur.

Modellqualität benötigt anschließend einen freigegebenen Modelllauf und unabhängige Bewertung über die festgelegten Nenner. Ein vorbereiteter Eingang, ein gespeicherter Datensatz oder grüne Tests sind dafür kein Ersatz. Native Mac-Bedienung und Alltagslast sind eigene Abnahmen. Die laufende Fassung auf dem Mac wurde durch diesen Prüfaufbau nicht geändert.

## Reproduktion

Aus dem Repository mit eingerichteter Python-Umgebung:

```sh
PYTHONPATH=sidecar:scripts:. python scripts/memory_acceptance_intake.py
PYTHONPATH=sidecar:scripts:. python -m pytest -q scripts/test_memory_acceptance_intake.py
```

Der Quellenadapter ist ausschließlich für den fest eingefrorenen künstlichen Bestand bestimmt. Er prüft alle Artefaktprüfsummen, parst nur Eingabedaten und enthält keinen Live-Modus. Die Aufnahmeprüfung hat das unabhängige [Review der ersten Korrekturrunde](intake-fix01-review.md) bestanden: alle vier wichtigen Befunde geschlossen, keine neuen Befunde. 18 gezielte Tests bestanden auf dem finalen Skriptstand. Der frühere breitere Nachweis mit 224 Tests sowie die separat ausgewiesenen Sandbox- und Laufzeitbefunde stehen im Autorenbericht; diese Zahlen werden nicht zu einer neuen Gesamtprüfung addiert.

## Herkunftsbelege nach Reviewkorrektur

Der zweite Offline-Lauf enthält zusätzlich die persistenten Mail-Transportidentitäten und tatsächlichen Produktschlüssel: [baseline-with-transport-identities.json](baseline-with-transport-identities.json), SHA-256 `a899e4c3a95846008989609fe921bfc88d2f8ec760b2c28cac629d6f21b9a25c`. 102 Mail-Transporttupel und 108 Produktschlüssel wurden gelesen; der allgemeine DOCX-Upload N10 ist ausdrücklich unversioniert. Die Quellenzahlen bleiben gleich. Der [Autorenbericht](intake-author-report.md) hält die beiden genauen Codezustände, Befehle und Befunde auseinander. Das [erste Review](intake-review.md) dokumentiert die vier gefundenen Schutzlücken.

Die Replay-Probe belegt den erneuten Aufruf mit stabilem Intake-Cursor. Sie ist kein Nachweis der späteren S08-Prüfung mit erneut vorgelegten identischen MIME-Bytes. Die ergänzende Reply-Probe prüft Header und Cc am Connector; eine gespeicherte Reply-Verknüpfung ist damit noch nicht abgenommen.

## Gesonderte Kalenderkorrektur

Der [Kalenderbericht](calendar-author-report.md) beschreibt die Korrektur des reproduzierten Absagefehlers: explizite ICS-Absagen gehen über den wirklichen Abo-/CalDAV-Leser und den Kalenderjob als versionierte Absagebelege ins Gedächtnis. Die Live-Kalenderliste zeigt sie weiterhin nicht als aktive Termine. Einträge mit gleicher Überschrift werden nicht miteinander gleichgesetzt. Unvollständige Antworten und Änderungsnachrichten berechtigen nicht zum Entzug ungenannter Nachbartermine.

Der Quellenreplay mit den unveränderten N05-/N06-Dateien ergab zuerst eine Aufnahme, dann einen Versionswechsel und bei Wiederholung einen unveränderten Beleg. Der alte Termintext blieb historisch erhalten und verlor die aktuelle Belegberechtigung. Dies prüft den Quellenweg, nicht die semantische Antwort SQ11. Die vollständige Antwort muss zusätzlich die unabhängig gültige PDF-Frist berücksichtigen; der Kalender-Gegentest selbst verwendet nur eine getrennte Dokumentquelle.

Mehrdeutige alte Serienkennungen bleiben ausdrücklich ungeklärt. Sparsame Serienabsagen gelten nur für bereits gespeicherte Vorkommen mit verifizierter Roh-UID und passender Versionsordnung; unbekannte Vorkommen werden nicht erfunden. Ein lückenhafter Absagestand berechtigt auch bei fehlender eindeutiger Zuordnung nicht zum Entzug anderer Einträge. Diese Grenzen, fehlende Live-Provider-/Mac-Prüfung und die nicht durchgeführte Modellbewertung verhindern eine pauschale Abnahme des gesamten Gedächtnisses.

## Reviewabschluss und Zeitzone

Die Kalenderänderung hat nach drei gezielten Korrekturrunden das unabhängige [Spezifikations- und Qualitätsreview](calendar-fix03-review.md) bestanden. Die anfänglichen sechs wichtigen Befunde und die in den Korrekturen entdeckten Restfälle sind dokumentiert und geschlossen. Unveränderte Altbelege behalten ihre IDs und Evidenzfingerabdrücke, technische Kalenderrevisionen werden im vorhandenen Episodendokument gehalten, und ein fehlgeschlagener Kopfwechsel kann wiederholt werden. Bei getrennten Claim-Transaktionen können betroffene Behauptungen bis zur Wiederholung bereits vorsorglich gesperrt sein. Ein kleiner Befund zur gemeinsamen Begrenzung datierter/undatierter Kalenderzeilen bleibt für das abschließende Gesamtbranch-Review vermerkt.

Die vorherige CI am Commit `ff2f075` bestand die vollständigen Backendtests mit jeweils 10.198 bestandenen Fällen unter Python 3.10 und 3.12. Beide Jobs scheiterten anschließend an genau einem Test im neuen Mistral-Prüfwerkzeug: Er verglich 09:00 UTC und 10:00 Berlin als ungleiche Zeichenfolgen. Die [Testkorrektur](pilot-timezone-report.md) vergleicht jetzt den gleichen Zeitpunkt mit Zeitzone; UTC und Europe/Berlin bestehen separat. Das [unabhängige Review](pilot-timezone-review.md) bestätigt, dass falsche oder zeitzonenlose Zeitpunkte weiterhin abgewiesen werden. Produktionsdaten und Timestamp-Normalisierung wurden hierfür nicht geändert. Diese CI-Ergebnisse gehören zum vorherigen Commit und sind keine vollständige Backendprüfung der späteren Kalenderänderung.

Am finalen Codecommit `fab9a03da6271f45228684282b26d2774c239b8e` bestehen unter UTC gemeinsam 131 Tests für Mistral-Prüfwerkzeuge, Eingangsadapter und Kalenderabsagen (17,12 s, eine bestehende Starlette-TestClient-Warnung). Die drei gesonderten CalDAV-Tests mit künstlichem lokalem TLS-Server bestehen ebenfalls (1,83 s; [Protokoll](calendar-tls-final.txt)). Ihr vorheriger Terminalausgang war nach dem Kontextwechsel nicht mehr verfügbar; ausschließlich diese offenen Nachweise wurden wiederholt.

Der tatsächliche [finale Offline-Basislauf](baseline-final.json), SHA-256 `c80811a0ff0b2b08f3a70fb7adc5b8f0c94c5447267139c9cafc4ca96f8c8682`, bestätigt auf diesem Code weiterhin 109 Episoden, 108 persistente Produktschlüssel und die Abdeckung 105 vollständig / 4 teilweise / 1 zurückgehalten. Alle eingefrorenen, versionierten Prüfdateien stimmen byteweise mit dem vorherigen Git-Stand überein. Die genauen Dateihashes und Prüfgrenzen stehen in [validation.json](validation.json). Der ältere Nachweis [validation-before-calendar-review.json](validation-before-calendar-review.json) bleibt ausdrücklich dem früheren Code zugeordnet.

Dies sind Aufnahme- und Verhaltensprüfungen ohne Modellbewertung. Personen-, Aufgaben-, Frist- und Antwortqualität sind noch nicht abgenommen. Der Großimport bleibt pausiert; die persönliche Mac-App wurde nicht geändert.
