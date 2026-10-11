# Speicherreserve vor Aufnahme und Verarbeitung

11. Oktober 2026. Laufzeitcode `3690733`; in dieser Code-/UI-Prüfung noch nicht persönlich installiert. Anschließend als [gepaartes Update](../2026-10-11-intake-capacity-package/README.md) `1.0.6-preview.3690733` auf dem Mac installiert, große Aufnahme weiterhin pausiert. Kein persönlicher Modellstart, keine private Quellensichtung oder Cloudkosten in dieser Prüfung.

## Problem und Verhalten

Nach dem [tatsächlich vollen Docker-Dateisystem](../2026-10-11-docker-storage-reserve/README.md) konnte der alte Dienst nicht starten. Die bisherige Updater-Kapazitätsprüfung allein schützt laufende Aufnahme nicht. Jetzt prüft eine kleine lesende Sperre vor Hintergrundarbeit und frisch an Abruf-/Speichergrenzen `/` und den tatsächlichen Datenpfad: jeweils mindestens 512 MiB verfügbare Bytes und 1.024 verfügbare Inodes. Nicht messbare/ungültige Werte sperren ebenfalls. Keine Dateninspektion, automatische Bereinigung oder neue Konfiguration.

Mail-Intake öffnet bei Sperre nicht einmal eine neue Sitzung. Inventur und Nachricht werden vor dem Abruf sowie nach Rückkehr vor Persistenz erneut geprüft. Bei zwischenzeitlichem Speicherverlust bleiben UID-Cursor/Quelle/Versuchszähler unverändert; kein fehlgeschlagener Modell- oder Mailversuch daraus erfunden. Nach Erholung kann derselbe Eintrag wiederholt werden. Eigene Pause bleibt unverändert.

Start/Fortsetzen liefern bei Sperre HTTP 507 vor Discovery bzw. Planänderung und erneut nach Discovery. Gemeinsamer Mailstand zeigt „wartet“ und behält Zahlen; abgeschlossene/fehlgeschlagene Mailstände und eigene Pausen werden nicht übermalt. Intake-Ansicht zeigt den Grund, blockiert Start/Fortsetzen/Retry, lässt Pausieren und Ordner-Vorschau verfügbar. Nach einem frischen erfolgreichen Poll werden passende Aktionen wieder verfügbar. Neue Felder sind optional, alte Dienste bleiben darstellbar.

Hintergrund-Einbau verknüpft die Sperre mit dem Energie-Gate; manuelle Pause behält Vorrang. Die Modellampel unterbricht absichtlich bei Ressourcenverlust und gibt ihre Sperren frei. Keine Fertigschätzung bei unbekannter/knapper Kapazität. Direkte Fragen bleiben verfügbar; diese Änderung ist kein allgemeiner Schutz aller API-Schreibwege.

Unabhängiger Reviewer fand einen realen manuellen Full-Run-Bypass und eine Kaltstartlücke. Beide zuerst mit fehlschlagenden Gegenfällen reproduziert. `Scheduler` prüft nun auch manuelle Gesamtdurchläufe vor jeder Phase und vor der Fertigmarkierung. Ein abgebrochener Bericht bleibt sichtbar, ohne den vollständigen Laufzeitpunkt zu aktualisieren. `_wire_scheduler` installiert den Gate schon vor dem ersten Workerstart; Worker prüft ihn auch vor Anschluss der übrigen Steuerung. Finaler statischer Review ohne konkreten Restblocker, keine vom Reviewer ausgeführten Live-Tests.

## Nachweise

- 18 neue Fälle mit künstlichen Dateisystemmessungen und Mails: knappe Bytes/Inodes, unbekannte Messung, getrennte Root-/Datenbereiche, Verlust während Inventur/Nachricht, unveränderte Cursor/Retry, geschlossene Start-/Resume-/Full-Run-/Kaltstartwege, eigene Pause erhalten.
- 111 betroffene Backendtests bestanden, ein vorhandener Plattformfall ausgelassen. Gesamte Backend-Suite nicht erneut ausgeführt; der frühere Gesamtlauf qualifiziert diesen neuen Diff nicht zusätzlich.
- 551 vorhandene UI-Tests, Typprüfung, Produktionsbuild und Assetvertrag bestanden. Vorhandene Starlette/httpx-, Node-/MockTimers- und Chunk-Warnungen.
- Tatsächlich gerenderte React-Komponente über echte Produkt-ASGI-API mit künstlichen Quellen und isolierten Dateisystemmessungen: Desktop/390px, Low/Unknown/Healthy, sichtbare Meldung, gesperrter Start/Resume, verfügbare Pause, nur zwei erwartete Mail-Pause-Schreibaufrufe. Keine Konsolen-/Seitenfehler. Der erste Harnessaufruf fehlte `active=true` und zeigte deshalb nur Laden; Harness korrigiert, finaler Lauf mit frischem Produktcode bestanden. Keine native WKWebView-/persönliche Alltagsabnahme daraus abgeleitet.

`verification.json` bindet Code und Dateiprüfsummen. `ui-evidence.json`/Harness dokumentieren den künstlichen Lauf. Browserbilder liegen lokal unter `/private/tmp/kingfisher-intake-capacity-ui-20261011/`; Testserver nach Abschluss beendet. Keine privaten Daten oder Schlüssel im Nachweis.

## Grenzen

Dies ist eine Reserveprüfung, keine reservierte Kapazität oder harte Schreibquote. Ein bereits laufender einzelner Job/Anhang, SQLite-Journal oder anderer Prozess kann zwischen Messungen wachsen. Vollständige Backup-/Bulkimport-Kapazität und die 122.399 persönlichen Mails bleiben gesondert zu qualifizieren; kein großer Import freigegeben. Automatischer Neustart bei messbarer Reserve gilt nur innerhalb bereits autorisierter Verarbeitung und ohne eigene Pause. Keine automatische Löschung, Modellnachladung oder Speicherkonfiguration.
