# Nativer Mac-Kalender: begrenzter App-Lebenszyklus

Aktueller Code-/Paketstand `3403623073b5714834961995b9e2c428fb30abc0`, lokale Version `1.0.6-local.3403623`. Basis `e7033f5`, erste Helferinstallation `9cbf931`, vorherige Installation `af8e791`.

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

Die echte App öffnet Einstellungen am richtigen lokalen Dienst, bestehende Zugänge bleiben sichtbar. Beim Start erscheint kein macOS-Kalenderdialog. Die macOS-Lesefreigabe wurde im echten App-Fenster geprüft. Die vom Nutzer ausdrücklich genannten drei Hauptkalender sind gespeichert; der erste vollständige Live-Schnappschuss enthält 490 Termine. Historische Gedächtnisaufnahme bleibt pausiert.

## Grenzen

Der lokale Intel-Paketbau scheitert an fehlenden Intel-Kompatibilitätsbibliotheken des Apple-Werkzeugs; derselbe Fehler wurde an der bisherigen Basis reproduziert. Der öffentliche Standard bleibt Universal, für diesen Mac ist ausdrücklich ARM paketiert und signaturgeprüft. Kein bestandener Universal-Release-Build wird behauptet.

Leere historische Abschnitte gelten weiterhin nicht automatisch als Löschbeweis. Der Kalenderhelfer ist eine Teil-Lieferung; ein vollständig verlässliches CoS-Gedächtnis oder ein fertiges Gesamtprodukt ist damit nicht nachgewiesen. GitHub-CI wurde nicht neu gestartet.

## Kalenderkopien: Korrektur nach dem Fenstertest

Die zusätzliche Mac-Verbindung zeigte einen Termin auch über das bestehende Kalenderabo. Die Anzeige fasst nun nur Kopien mit derselben externen Anbieterkennung, demselben konkreten Beginn/Ende und übereinstimmenden sichtbaren Details zusammen. Gleiche Titel/Uhrzeiten, unbekannte Kennungen, abweichende Kopien und Vorkommen einer Serie bleiben getrennt. Alle ursprünglichen Quellenkennungen bleiben erhalten; es ist eine Leseprojektion ohne Quellenlöschung oder Schemawechsel. ICS-Titel/Orte werden korrekt entwertet.

Bestehende Projektwahl, Nachbereitung und Mitschriften werden über die aktuell verfügbaren Kopien gelesen. Widersprüchliche Projektentscheidungen erzeugen eine sichtbare Klärung; eine ausdrückliche Wahl setzt die aktuellen Kopien atomar. Kalenderänderungen behalten die genaue schreibbare Google-Quelle als Ziel. Ein entzogener Quellenalias ist danach nicht mehr auflösbar.

Unabhängiges Review fand verlorene Aliasentscheidungen und verdeckte Bearbeitungsaktionen; beide wurden mit Regressionstests korrigiert. Ein weiterer Reviewfall zur expliziten Projektwahl im Nachbereitungsformular wurde rot/grün bestätigt und korrigiert. 250 betroffene Backendtests bestanden vor dieser letzten idempotenten Bedingungskorrektur; die abschließenden 32 Tests für Kopien/Nachbereitung bestanden danach. 435 UI-Tests, Typprüfung und Produktionsbuild bestanden. Aus einem sauberen Quellschnappschuss bestanden 29 native Prüfungen mit einer erwarteten Nicht-Mac-Ausnahme; lokale Synchronisationsduplikate bleiben unangetastet.

Die Anbieterkennung ist ausdrücklich vorgesehen: [Apple EventKit: calendarItemExternalIdentifier](https://developer.apple.com/documentation/eventkit/ekcalendaritem/calendaritemexternalidentifier?language=objc). Sie allein reicht nicht zum Zusammenfassen wiederkehrender Termine. Der neue Wert wird intern separat gespeichert, sodass das bisherige Cacheformat und der Rückweg erhalten bleiben. Die korrigierte Version `1.0.6-local.3403623` ist als Backend und signierter ARM-Wrapper installiert. Erneute bytegeprüfte Sicherung, unverändertes Schema/Volume und erhaltene Originale/Einstellungen/Pause sind nachgewiesen. Alle 266 Python- und 112 UI-Dateien wurden isoliert gegen das Paketmanifest geprüft; der eingefrorene Quellstand bestand 29 native Prüfungen und eine erwartete Plattformausnahme.

**Offenes Bediengate:** macOS verlangt nach dem Austausch des ad-hoc signierten Wrappers die Lesefreigabe erneut. Die Auswahl der drei Kalender ist gespeichert, die Live-Anzeige auf diesem neuen Stand wartet aber auf die Systemfreigabe. Der Mac sperrte sich; der Nutzer verschob den Fenstertest ausdrücklich. Die abschließende zusammengefasste Anzeige ist daher noch nicht live bestätigt. PR bleibt Entwurf. Historische Gedächtnisaufnahme und Mailverarbeitung bleiben pausiert; keine Cloud-/Modellverarbeitung.
