# Nativer Mac-Kalender: begrenzter App-Lebenszyklus

Code-/Paketstand `9cbf9310d7fdec729bdfdb7d80e5ea17d4a9ffde`, lokale Version `1.0.6-local.9cbf931`. Basis `e7033f5`, vorherige Installation `af8e791`.

Die fertige App startete bisher keinen Kalenderhelfer. Der neue Swift-Helfer läuft im App-Prozess am selben authentifizierten lokalen Dienst. Keine zusätzliche Python-Laufzeit, keine Kalenderänderung, keine Cloud-/Modellverarbeitung. Er stoppt bei App-Ende und Update.

Eine Berechtigung wird nur aus einer ausdrücklichen Aktion im aktuellen Hauptfenster angefragt. Vor dem tatsächlichen Systemdialog werden Auswahlgeneration und Verbindungszustand erneut geprüft. Ohne Auswahl werden keine Termine gelesen. Live-Anzeige und historische Gedächtnisaufnahme sind getrennt; Pause, Akkusperre und geänderte Freigabe sperren die Aufnahme. Transport-/Lesefehler täuschen keinen macOS-Berechtigungsentzug vor. Unvollständige Gedächtnisabschnitte werden erneut versucht.

## Prüfung

- 99 betroffene Backendtests; 433 Frontendtests, Typprüfung und Produktionsbuild bestanden.
- 27 native App-Prüfungen bestanden, eine Nicht-Mac-Prüfung erwartungsgemäß übersprungen. Zwei zusätzliche echte Swift-/HTTP-Verhaltensprüfungen bestanden: injizierter Koordinator und begrenzter URLSession-Client mit synthetischem lokalen Server.
- Vier synthetische Austauschprüfungen: geändertes Kandidatenpaket, fehlende Backendfreigabe, Signaturfehler nach Austausch mit Wrapper-Wiederherstellung und erfolgreicher Austausch.
- Unabhängiges Review: verspätete Freigabe, verschluckte Brückenfehler und falsche Transport-/Berechtigungseinordnung korrigiert. Abschließendes Code-, Architektur- und Installationsreview ohne konkrete Blocker.
- Paketmanifest prüft alle 266 Python- und 112 UI-Dateien. Gegenüber dem installierten Elternabbild ändern sich nur `mac_calendar.py`, UI-JS und Index. Statische Assets bleiben unverändert.

## Mac-Lieferung

Das signierte ARM-App-Paket und neue Backend sind installiert. Der bisherige App-Wrapper und eine bytegeprüfte Rohdatenkopie einschließlich SQLite-Journals bleiben lokal gesichert. Schema 20, unverändertes Datenvolume, Originalquellen, Einstellungen und Pause wurden vor und nach dem Backendtausch geprüft. Keine Datenmigration, kein Modellstart.

Die echte App öffnet Einstellungen am richtigen lokalen Dienst, bestehende Zugänge bleiben sichtbar. Beim Start erscheint kein macOS-Kalenderdialog. Die echte Kalenderfreigabe und bewusste Auswahl stehen noch aus; dieser Nachweis wird nicht durch synthetische Tests ersetzt.

## Grenzen

Der lokale Intel-Paketbau scheitert an fehlenden Intel-Kompatibilitätsbibliotheken des Apple-Werkzeugs; derselbe Fehler wurde an der bisherigen Basis reproduziert. Der öffentliche Standard bleibt Universal, für diesen Mac ist ausdrücklich ARM paketiert und signaturgeprüft. Kein bestandener Universal-Release-Build wird behauptet.

Leere historische Abschnitte gelten weiterhin nicht automatisch als Löschbeweis. Der Kalenderhelfer ist eine Teil-Lieferung; ein vollständig verlässliches CoS-Gedächtnis oder ein fertiges Gesamtprodukt ist damit nicht nachgewiesen. GitHub-CI wurde nicht neu gestartet.
