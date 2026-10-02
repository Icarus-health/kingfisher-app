# M2c: vollständige Aussagen und getrennte Quellenzeiten

19. September 2026. Fortsetzung auf `fix/knowledge-semantic-time-context`, Basis
`ebb2e63bc61f7bfcc867ffd3e03c28b5db3614c3` aus dem noch offenen M1d-PR #48.
Die private App auf 8890 und die vorhandene Review-Instanz auf 8891 wurden nicht geändert.

## Verhalten

Der lokale Anbieter erhält mit `knowledge-context-v3` die vollständige bestätigte
Aussage einschließlich Prädikat/Wert, stabiler Referenzen, Annahmezeit und
Gültigkeitsintervall. Der erste gespeicherte Originalbeleg enthält seine Identität,
seinen Digest, Quellenart/-referenz und getrennte Ereignis- und Importzeit.
Eine unbekannte Ereigniszeit bleibt ausdrücklich `null`. Alle Zeiten sind UTC;
verschiedene Offsets desselben Zeitpunkts verändern die Bedeutung nicht.

Die JSON-Projektion stammt aus demselben eingefrorenen Bestand, dessen vollständige
Belegkette geprüft wurde. Darstellung und Signatur verwenden dieselbe Projektion.
Die neue Verlaufsversion bindet den tatsächlich gelieferten Inhalt und die
Entzugsgenerationen aller beteiligten Originale. Ändert sich eine Grundlage,
werden alte Modellableitungen ausgeschlossen und aktuelle Kontextkarten entfernt;
der historische Gesprächstext bleibt erhalten. Dies ist eine Prüfung vor und nach
dem Modellaufruf, keine Transaktion mit einem Sprachmodell.

Ein Aufbau prüft höchstens 128 verschiedene Aussagen und separat 128 Originale.
Geliefert werden höchstens fünf vollständige JSON-Zeilen mit je höchstens 8 KiB;
alle präfixierten Datenzeilen zusammen belegen höchstens 32 KiB. Zu große Zeilen werden
als ganze Zeilen ausgelassen, statt Aussagen oder Quellenfelder abzuschneiden.

Der Diagnoserunner friert seine unabhängig aufgebauten Erwartungen vor dem Aufruf
ein. Er weist die Nutzlastversion aus und weist verfälschte Zeit-/Aussagefelder,
fremde Schlüssel und nicht erklärte Zeilen zurück. Die bestehenden Referenzmodi
und gespeicherten alten Modellversuche bleiben erhalten.

## Unabhängiger Laufzeitnachweis

Nur synthetische ORION-/NEBEL-Daten, frische getrennte SQLite-Stores und ein
deterministischer RecordingProvider. Kein echter Modellaufruf und keine privaten
Quellen. Der vorab eingefrorene Sollwert verwendet wörtliche fachliche Werte und
Zeitpunkte; kein Produktionsserializer berechnet die erwartete Projektion.

Der Ausgangsfehler ist im erhaltenen `baseline-result.json` direkt am tatsächlichen
Agentenaufruf belegt: v2 ließ Prädikat, Wert, Annahmezeit, Intervall und vollständige
Primärquellenmetadaten weg. Der native HTTP-Lauf prüft dieselben Angaben über
Provider-Eingabe und API sowie Prozessneustart, Zeitmutation, äquivalente Offsets,
Entzug/Wiederzulassung eines zweiten Belegs, externe Anbieter und fehlende Ereigniszeit.

Ein separater gebauter Container prüft den tatsächlichen HTTP-/SQLite-/Agentenpfad
mit eigenem Volume und Prozessneustart. Die Probe verwendet absichtlich den
aufzeichnenden Anbieter; sie behauptet keine Interpretation durch ein Sprachmodell.

## Offene Produktgrenzen

- Antwortqualität und die Unterscheidung etwa zwischen angedacht, beschlossen und
  erledigt brauchen weiterhin eine unabhängige Prüfung mit echten Modellen (M3).
- Eine isolierte Gegenprobe mit `snapshot_all`/`restore_all` bestätigt die offene
  Restore-Grenze: Nach einer Quellenrücknahme von Generation 0 auf 1 bringt eine
  ältere Sicherung Generation 0 und den früheren aktiven Zustand zurück. Geprüft
  wurde die niedrige Sicherungs-/Quellenschicht, keine gesamte Freigabe oder UI.
  M2c verändert diesen Wiederherstellungsweg nicht.
- Keine neue Timeline, keine ClaimStore-Schemamigration und keine allgemeine
  Gedächtnis-/Produktfreigabe. Die frühere Funktionsquote wird dadurch nicht erhöht.
- Die private laufende App enthält diese Änderungen erst nach einer gesonderten
  Integration und Aktualisierung.

## Prüfstand nach der Freigabekorrektur

- Codecommits `5bc9227`, `f52b910` und `ccb47b1`; Ausgangsbasis `ebb2e63`.
- Vollständiger finaler kombinierter Lauf: **1.757 bestanden** (**1.589 Backend +
  168 Diagnose**), 116,95 Sekunden, zwei bestehende Starlette/anyio-Deprecation-Warnungen.
- Unabhängiger Python-3.10.21-Lauf vor dem letzten engen Freigabestatusfix:
  **224 bestanden**, 15,23 Sekunden, zwei bestehende Warnungen. Neue Wissenstests,
  Identität, Mailfreigaben und alle drei Diagnosesuiten enthalten. Der abschließende
  veröffentlichte Stand wird zusätzlich in der Python-3.10/3.12-CI geprüft.
- TypeScript/Vite-Build, Asset-Vertrag (14 Dateien, 17 Icons), JSON-Schema/Beispiel und Diffprüfung bestanden;
  die nachfolgenden engen Backend-/Recorderkorrekturen verändern keine Frontendtypen.
- [17 native HTTP-/Providerkontrollen](native-result.json) und
  [6 Kontrollen im gebauten Docker-Container](docker-result.json) erneut nach dem
  letzten Produktionsfix bestanden. Image
  `sha256:1d75ffb0a4ef18df0e5e3a9be7f7b9f024dfcb4c7dc06f2d147a5ca2c0a4e845`.
- [Implementierungsbericht](implementation-report.md), ursprüngliche rote Läufe
  und [finale Quellprüfsummen](reviewed-source-sha256.json) erhalten.

Das breite [Integrationsreview](integration-review-before-fix.md) fand einen Fehler
im gespeicherten Freigabestatus: Eine vor der Ausführung wegen veralteter Grundlagen
abgewiesene Anfrage konnte als freigegeben erscheinen. `Turn.approval_outcome`
überträgt nun die tatsächliche Policy-Entscheidung unabhängig vom späteren
Antwortkontext. Ein nachgelagerter Antwortabbruch macht eine bereits ausgeführte
Aktion nicht rückwirkend zu einer Ablehnung. Die beiden echten HTTP-/GET-/SQLite-
Regressionen zeigen vor dem Fix einen Fehler und eine positive Kontrolle; nach dem
Fix bestehen beide sowie 149 relevante Tests und die gesamte Suite.

Der erste vollständige Lauf fand zwei Mailfreigabe-Regressionen. Beim Erstellen des
Mailentwurfs fehlte die explizit leere Wissensgrundlage in den Gesprächsmetadaten.
Sie wird nun dort gespeichert; beim Einlösen erfolgt keine nachträgliche Zertifizierung.
Der erste Python-3.10-Lauf hatte zusätzlich 26 Umgebungsfehler durch fehlendes Git;
mit korrigierter Umgebung blieb genau der doppelte UTC-Suffix als echter Recorderfehler.
Die enge Korrektur weist doppelte und falsch platzierte `Z` zurück. Diese Parseränderung
betrifft ausschließlich das Diagnosewerkzeug. Die spätere Freigabestatuskorrektur
wurde anschließend erneut mit der vollständigen Suite und im Container geprüft. Alle ursprünglichen Fehlschläge bleiben sichtbar.

Die [unabhängige Taskprüfung](independent-task-review.md) bestätigt Planerfüllung und Codequalität. Der Befund des breiten Integrationsreviews ist nach der [gezielten Nachprüfung](integration-review-final.md) geschlossen; keine blockierenden Reviewbefunde bleiben. GitHub-CI ist getrennt am veröffentlichten Head zu prüfen und im Pull Request verlinkt.

## Nachträgliche unabhängige Regression

Das Review konnte die ursprüngliche TDD-Werkzeugchronologie des Implementierers
nicht selbst einsehen. Deshalb wurde ergänzend der unveränderte Ausgangscode
`ebb2e63` (`git archive`, nur sidecar/scripts) in einen getrennten Scratchordner
gelegt und ausschließlich die neue Testdatei darübergelegt. Zwölf ausgewählte
RecordingProvider-Fälle scheitern dort fachlich: vollständige Felder, drei
Metadatenmutationen in drei Aufruffenstern, unbekannte Ereigniszeit und UTF-8-Grenze.
Dieselben zwölf Fälle bestehen auf `f52b910`. Die beiden Originalausgaben liegen
bei. Dies ist ausdrücklich eine spätere unabhängige Regression, kein nachträglich
rekonstruiertes Protokoll der ersten TDD-Sitzung.

Die unveränderten vollständigen Prüfausgaben sind mit Dateiname und SHA-256 in
[verification-logs.json](verification-logs.json) erhalten. Pfade im ursprünglichen
Implementierungsbericht bezeichnen den damaligen Prüfarbeitsbereich; dessen
Logdateien sind in diesem JSON ohne Inhaltsänderung enthalten.
