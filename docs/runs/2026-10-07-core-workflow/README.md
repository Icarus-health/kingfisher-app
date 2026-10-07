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
