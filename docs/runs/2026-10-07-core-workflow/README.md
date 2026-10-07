# Kernablauf: geprüfter Entwicklungsstand für 1.0.6

7. Oktober 2026. Ausgangspunkt `96e8f64` (1.0.5); Branch `feat/core-workflow-20261007`. Umfang und Grenzen: [Kernablauf](../../59-kernablauf-gedaechtnis-cos.md).

## Endstand geprüft

- 155 gezielte Backendtests bestanden: Cloud-Vorbereitung/Regionalrouting/Schlüsselspeicher, Rollen, beide Zeitachsen, Quellenentzug, Zeitklassifikation, Aufgabenprüfung/Paginierung und gemeinsamer Pilotablauf einschließlich Neustart.
- 309 UI-Tests bestanden. TypeScript und Produktionsbuild bestanden. Der vorhandene Hinweis auf ein JavaScript-Bündel über 500 kB bleibt; kein Buildfehler.
- Releasevertrag `pruefen --tag v1.0.6` bestanden; noch kein Tag oder Release veröffentlicht.
- Getrennte Docker-Testinstanz `kingfisher-workflow-final-qa-20261006` mit künstlichen Daten aktualisiert. Lokale HTTP-Prüfung: Originalquelle von 2015 in der 2015-Achse, zwei disjunkte Aufgabenseiten samt Bestandskennung, künstlichen Mistral-Schlüssel verschlüsselt speichern und entfernen, keine Inferenzaufrufe. Keine echten Konten, Schlüssel oder Quellen verwendet.
- Metadaten-Belastungsprobe mit 20.001 künstlichen Quellen: drei Coverage-Abrufe mit 109,0 / 129,1 / 81,4 ms. 2.000 Quellen in der ausdrücklich begrenzten Aufschlüsselung; 2.858 undatierte Quellen korrekt gezählt. Keine Aussage über LLM-Einordnung oder echte Volltextsuche bei dieser Größenordnung.

## Breiterer Lauf und Grenzen seiner Aussage

Der vollständige Backendlauf eines früheren Zwischenstands ergab 4.762 bestanden, 1 übersprungen, 17 fehlgeschlagen und 86 Einrichtungsfehler. Die meisten Fehler entstanden beim Start lokaler Testserver in der Sandbox. Der anschließende Lauf mit erforderlichen Rechten ergab 101 bestanden, 1 fehlgeschlagen und 1 abgewählt (Swift-Prüfung).

Der verbliebene Pilotfehler lag an einer fest auf September datierten Nachricht, die inzwischen außerhalb des Siebentagefensters lag. Die bewusst zeitnahe Testnachricht verwendet jetzt eine relative Zeit; feste historische Negativfälle bleiben erhalten. Eine neue Morning-Testvorgabe fehlte um das vorhandene Pflichtfeld `kinds`; sie wurde vervollständigt. Beide Fälle bestehen im gezielten Endlauf. Dieser Endlauf ersetzt keine Behauptung, der gesamte Backendbestand sei nach jeder letzten Änderung erneut vollständig durchgelaufen.

Die native Swift-Prüfung konnte in der lokalen Werkzeug-/SDK-Umgebung nicht abgeschlossen werden. In dieser Lieferung wurden keine Swift-Dateien geändert. Eine erfolgreiche frühere Mac-Build-Pipeline ist kein neuer Buildnachweis dieser Fassung.

## Unabhängige Gegenprüfung

Read-only Review fand und bestätigte Korrekturen für falsche Quellendatums-Fallbacks, bedienbare alte Aufgabenseiten, übersprungene Einträge bei veränderter Warteschlange, veraltete Schlüsselzustände in bereits besuchten Einstellungsbereichen, ignorierte Schlüssellöschfehler und Windows-Schlüsselinterpolation. Cloud-Freigaben sind nach Schlüssel-/Modellwechsel persistent lokal gesperrt; weder ein anderer Cloud-Standard noch ein unbekanntes Ollama-Modell darf übernehmen. Ein fehlgeschlagener Agent-Neuaufbau lässt keine zuvor erfasste Anbieterreferenz aktiv. Regressionen wurden vor der jeweiligen Korrektur fehlschlagend geprüft; die abschließende unabhängige Cloud-Prüfung bestand mit 55 Tests.

## Offen vor Installation

Der Mac war beim Bedienversuch gesperrt; die Bitte um Entsperren ist offen. Deshalb keine native Bedienprüfung, kein Screenshotnachweis, keine Änderung des persönlichen Piloten, kein Produktionsbackup/-update und keine Behauptung eines installierten Updates. Die getrennte Testinstanz ist bereit für diese Prüfung. Kalenderanbindung, kompletter gewünschter Mailumfang und unabhängiger echter Nutzwerttest bleiben eigenständige Abschlusskriterien.

Keine GitHub-CI-Neustarts, keine Abonnements und keine Check-ins angelegt. Ein GitHub-Push verwendet `[skip ci]`, um das leere Minutenkontingent nicht zusätzlich zu belasten; die lokale Prüfung ist oben ausdrücklich begrenzt beschrieben.

## Nachprüfung der Zeitraumfragen vor dem Mac-Test

Die vorhandenen 74 gezielt ausgewählten Prüfungen für den Pilotablauf, Personen, Quellenentzug, zeitliche Aufgabenprüfung und Antwortzustände bestanden. Eine anschließende Codeprüfung fand trotzdem eine konkrete Lücke: Kandidatenpriorisierung, Personen-Zeitraumfilter und Kontextkennzeichnung verwendeten `reference_time()`, das bei fehlendem Quelldatum auf den Import zurückfällt. Ein undatiertes Dokument konnte deshalb zugleich „Quellenzeit: unbekannt“ und „Außerhalb des gefragten Zeitraums: Quelle vom 26.09.2026“ anzeigen; das angebliche Quelldatum war der Import.

Die Korrektur verwendet an diesen Stellen ausschließlich `occurred_at`. Undatierte Personenquellen bleiben als Kontext erhalten, hinter datierten Treffern im gefragten Zeitraum. Es gibt keine Änderung gespeicherter Originalquellen, keine Migration und keine globale Änderung von `Episode.reference_time()` oder Rangfusion. Die allgemeine technische Rangfolge und begrenzte Kandidatenzahl sind weiterhin kein Vollständigkeitsnachweis.

Sechs neue Testfälle decken Priorisierung, Filter, zwei Importzeitpunkte, tatsächliche Antwortdarstellung und den Erhalt undatierten Personenkontexts ab. Die fünf Fehlerfälle wurden vor ihrer jeweiligen Korrektur fehlschlagend beobachtet; der sechste ist eine zusätzliche Kontrolle. Der gezielte Endlauf bestand mit **105 Tests**, einschließlich datierter Mail-/Terminlogik, Personenfragen, Quellenentzug und gespeicherter Antworten. Eine rein lesende Gegenprüfung bestätigte die begrenzte Korrektur; sie startete keine weiteren Tests oder Scans.

Die [Alltagsabnahme](../../60-alltagsabnahme.md) definiert zwölf Situationen und trennt technische Schutzregeln von noch offenen Tests mit echtem Modell und tatsächlichem Quellenbestand. Kein bezahlter Modellaufruf, kein echtes Postfach, kein Produktionsupdate und keine native Bedienprüfung wurden in dieser Nachprüfung ausgeführt.

Der zusätzliche vollständige Backendlauf mit den erforderlichen lokalen Testserverrechten bestand mit **4.886 Tests, 1 übersprungen**, in 728,67 Sekunden. Hinweise: bestehende Starlette/httpx-Abkündigung sowie eine ungültige Escape-Sequenz im Anführungszeichen-Test. Der Lauf startete nach der ersten Zeitraumkorrektur und vor der letzten Ergänzung zum undatierten Personenkontext; diese letzte Ergänzung ist im oben genannten 105-Test-Endlauf geprüft. Die frühere SDK-/Sandbox-Begrenzung gilt für den früheren Lauf, nicht als Fehler dieses neuen erfolgreichen Laufs. Eine native Bedienprüfung ist dadurch weiterhin nicht ersetzt.

## Direkte Alltagsabläufe nach der Funktionsinventur

Ausgangspunkt `1f3fde4`; begrenzter Ausbau nach dem freigegebenen [Plan](../../plans/2026-10-07-direkte-alltagsablaeufe.md). Aufgaben direkt auf Heute bedienen, genaue Aufgabenlinks statt Listenverweise, einheitliche Fälligkeitstage und ein rein quellengestützter Mailverlauf. Keine Datenmigration, keine neue Kontofreigabe und kein zusätzliches Modell.

- **120 gezielte Backendtests bestanden** (31,16 Sekunden): Aufgaben, Einzelabruf, Bearbeitung, Verlauf, Projekte, Vorschlagsprüfung, Mailaufnahme, zeitliche Regeln, Kurzüberblick, neuer Mailverlauf und Microsoft-Connector. Der Einzelabruf wurde anschließend mit 200 vorgelagerten Aufgaben verschärft und nochmals bestanden: die Zielaufgabe fehlt in der begrenzten Liste und wird trotzdem über ihre Kennung geladen.
- **314 UI-Tests bestanden**; TypeScript und Produktionsbuild bestanden. Der bestehende Hinweis auf das große JavaScript-Bündel bleibt. Die Tests ersetzen keine native Bedienprüfung.
- Neue Prüffälle: exakte Aufgabenkennung über Wartestatus/Erledigung, kontogebundene Headerbeziehungen, Originalzeit statt Importreihenfolge, Quellenentzug und neue Fassung, unbekannte Datierung, abgeschnittene Texte/Nachrichtenzahl, Arbeitsbudget und dessen Freigabe, Mailzugangswechsel, Outlook-Antwortheader, Sommer-/Winterzeit, eindeutige absolute Datumsangebote und Erhalt genauer Fristzeitpunkte.
- Vorher fehlschlagend beobachtet: fehlender Einzelabruf/Verlaufsendpunkt, fehlende Outlook-Antwortheader und der Zeitzonenfall. Letzterer verschob eine unveränderte Frist von `2026-10-12T23:30:00Z` auf das Ende des Folgetags. Eingabefeld und Vergleich verwenden jetzt denselben lokalen Kalendertag; der ursprüngliche Zeitpunkt bleibt unverändert.
- Zwei unabhängige, begrenzte Read-only-Reviews. Die gefundenen Outlook- und Abfragebudgetlücken sowie der Zeitzonenrandfall wurden korrigiert. Keine weiteren konkreten Blocker im geprüften Umfang; keine Behauptung eines umfassenden Audits.
- Die SQL-Arbeit des Mailverlaufs wird über alle Erweiterungsschritte zusammen begrenzt. Der Fortschrittshandler ist nur unter der Episodensperre aktiv und wird im `finally` entfernt. Ein eigener Test erzwingt Abbruch und führt danach wieder eine größere Abfrage auf derselben Verbindung aus. Ergebnislimit, Textlimit und maximale Beziehungstiefe sind zusätzlich wirksam. Ein gesonderter Headerindex ist damit nicht ersetzt; bei großen Beständen kann der Ausschnitt unvollständig bleiben.
- Getrennte Docker-Testinstanz mit künstlichen Daten aktualisiert. HTTP-Abnahme über die reguläre lokale Sitzung: ursprüngliche Bitte samt späterer Absage im Originalverlauf; Aufgabe in Heute an ihrer Kennung auffindbar; Bearbeiten, Warten, Zurückholen, Erledigen und Wiederöffnen; konkrete Aufgaben-URL liefert die App. Der erste Versuch ohne Sitzung wurde korrekt mit 401 abgewiesen. Keine echten Konten, Schlüssel, Anbieteraufrufe oder versendeten Nachrichten.
- Releasevertrag für `v1.0.6` erneut bestanden; kein Release veröffentlicht und persönlicher Pilot unverändert.

**Verbleibende Grenzen:** Mailverlauf ist keine semantische Zusammenfassung. Fehlende Aufnahmen/Antwortheader, nicht sichtbare Bedingungen und abgeschnittene Zusammenhänge bleiben möglich und werden benannt. Es gibt keine automatische Projektwahl oder Erledigung aus einer Absage. Google-OAuth-Schreiben, terminierte Wiedervorlagen, Serienaufgaben und die Zusammenführung aller wichtigen Gedächtnisfragen sind noch offen. Kein erneuter vollständiger 4.886-Test-Lauf für diesen Ausbau; der gezielte Umfang steht oben. Native Bedienung, Tastatur/Fokus, schmale Fenster, tatsächlicher Klickaufwand und echter Alltagsnutzen bleiben am Mac zu prüfen.
