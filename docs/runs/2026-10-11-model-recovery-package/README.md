# Gemeinsames Paket für die einfachere lokale Modelleinrichtung

11. Oktober 2026. **Gebaut und isoliert geprüft, noch nicht persönlich installiert.** Version `1.0.6-preview.d092006`, Code `d092006699bdfe89b390916ede8505bc7b3cac9f`, bestehender Draft #54. Installierter persönlicher Stand frisch weiterhin `1.0.6-preview.45cb1c8`, Dienst gesund und Import pausiert. Kein Main-Merge, Registry-Publish oder CI-Neustart.

## Inhalt und feste Bindung

Das Paket enthält die beiden geprüften UI-Korrekturen: [Einrichtung bei fehlender Antwort-KI direkt öffnen](../2026-10-11-visible-model-recovery/README.md) und [eigene Modellwahl beim erneuten Suchen erhalten](../2026-10-11-preserve-model-selection/README.md). Die dortigen gerenderten Prüfungen und 551 UI-Tests sind die vorherigen Code-Nachweise; dieser Paketbau ist keine erneute Browser- oder Modellqualitätsabnahme.

UI aus dem frisch geprüften Produktionsbuild, 112 Dateien vollständig gehasht. Versionierte UI-Quellen entsprechen dem archivierten Code; Backend-/Native-Quellen sind gegenüber `45cb1c8` unverändert. Alle 270 Backend-Dateihashes identisch zum vorher installierten Paket. Neuer Docker-Layer auf genau dessen vorhandenem Image `sha256:d65a5a4b205496e222ffab16b1137b9734718e46837a0b848c12819bc2a4de3f`; ersetzt UI vollständig statt alte Bundle-Dateien mitzunehmen und bindet VERSION/ENV/Revision. Kein Abhängigkeiten- oder Gewichte-Download.

ARM64-Native-Bundle frisch mit Versionsmetadaten gebaut; sechs Dateien im schreibgeschützt eingebundenen DMG exakt entsprechend dem Manifest, strenge tiefe Signaturprüfung bestanden. Ad-hoc signiert, **nicht notarisiert**. Bekannter Hinweis zur veralteten hdiutil-Aufrufform bleibt.

- Backend-Image: `sha256:87e78d1d80179d7bba3008e3868f3f5f9d8a34e2cd001c1bb4bd8647d0876442`.
- DMG-SHA256: `4379a8050b21e5a7deedeba3b61c3c0eb6bf74c4cc9e92ba45f3e6fc76764c6f`.
- Kanonische byteweise geprüfte Kopie außerhalb Git: `Kingfisher-Pruefpakete/2026-10-11-model-recovery-d092006/Kingfisher.dmg` unter Sörens Codex-Dokumenten; Freeze/Manifest/Image-ID daneben. DMG und privater Bestand nicht im Repository.

## Tatsächlich ausgeführte Paketprobe

Ein separater Container ohne Netzwerk, Host-Port oder persönliches Volume, ausschließlich neues 256-MiB-`/data`-tmpfs. Host-Freeze unabhängig in das Skript eingesetzt; Laufzeitvergleich aller 270 Backend- und 112 UI-Dateien sowie Version/ENV bestanden. Bestehende künstliche Paketabläufe ausgeführt, einschließlich Quellenentzug und Neustart, Aufgabenbindung, Health, Kalenderkopien, Priorisierung, Wiederprüfung, Weltmeldungen, Bedingungen, Kategorien-/Projekt-/Transkript-Ablauf, lokale Rollenverbindung mit künstlichem Inventar, Speichergates und neu/alt gespeicherte Pronomenhinweise. Sämtliche Probe-Protokolle bestanden. Keine reale Inferenz, Personenauflösung oder persönlichen Daten. Das Skript meldet ausdrücklich `browser_rendered:false`.

Der erste Aufruf überschrieb den geerbten `icarus-sidecar`-Einstiegspunkt nicht und startete deshalb nur einen getrennten Dienst. Regulär beendet und als **nicht ausgeführter Test** dokumentiert. Der korrigierte Aufruf mit `--entrypoint python` führte das tatsächliche Prüfskript aus und endete mit Exit-Code 0. Beide Logs bleiben getrennt erhalten; kein persönlicher Dienst wurde gestoppt. Testcontainer anschließend nicht mehr vorhanden, DMG-Testmount geschlossen.

Unabhängiges enges statisches Artefaktreview bestätigt konsistente Version, Basisimage, Commit und Quellarchiv sowie Archivprüfsumme und Freeze-Bindung. Kein konkreter Bindungsfehler. Reviewer führte weder Docker, Probe noch Installation selbst aus; keine unabhängige Wiederholung des Builds behauptet.

## Persönlicher Stand und offene Abnahme

Frische authentifizierte Abfrage nach dem Bau: App-Backend weiterhin `45cb1c8`, ursprüngliches Image gesund, Kalenderfreigabe `granted`, drei ausgewählt, Helfer online, kein Fehler, Kalender-Gedächtnisübernahme aus. Hintergrund/Import bleibt pausiert. Das neue Paket hat weder persönliche Konfiguration noch Datenvolume eingebunden oder geändert. Etwa 1,37 GiB Docker-Reserve nach dem Bau sind keine Abnahme des großen Bestands.

Gepaarter tatsächlicher Wechsel mit frischer Sicherung und Datenprüfung, nativer Neustart, Dateiimport und persönlicher Frage-/Tagesablauf bleiben offen. Zur vorhandenen lokalen Qwen9B-Antwortwahl statt fehlendem Gemma12B läuft eine konkrete Nutzerfrage; keine entsprechende Umstellung ohne Antwort. Keine pauschale Qualitätsgarantie, keine erneute Behauptung perfekter Personen-/Faktenzuordnung.

`verification.json`, Paket-Freeze, Native-/DMG-Manifeste, Prüfskript und komprimierte Logs dokumentieren die tatsächlichen Grenzen. Neue Kosten und Datenfreigaben wurden nicht aktiviert.
