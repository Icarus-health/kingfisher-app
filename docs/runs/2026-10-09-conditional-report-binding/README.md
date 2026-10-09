# Bedingte Berichte bleiben bedingt

Laufzeitcode **e326f8113eae2e6e8123c7a39417fddf1e9fbebc**, Paket **1.0.6-preview.e326f81**, Basis `5f58e6f` der offenen Draft-Vorschau #46. Ergänzung [#53](https://github.com/Icarus-health/kingfisher-app/pull/53) in die weiterhin offene [Draft-Vorschau #46](https://github.com/Icarus-health/kingfisher-app/pull/46) übernommen (`883deb4`); Laufzeit-, UI-, native, Design-, Deployment-, Script- und Versionsquellen bytegleich zum geprüften Code. Nicht in Main übernommen, nicht installiert.

## Konkreter Fehler

Original: „Die Lieferung Orion erfolgt am 14. Oktober, sofern die Freigabe vorliegt.“ Die bisherige Satzprüfung und `working_memory_answers.prepare/render` ließen „Die Lieferung Orion erfolgt am 14. Oktober.“ als Sätzeantwort durch. Auch eine alte gespeicherte verkürzte Antwort konnte so wieder erscheinen. Das ist ein echter Verlust einer Bedingung, keine bloße Formulierungsabweichung.

Der gemeinsame Originalstellen-Vertrag erkennt jetzt auch explizit bedingte beschreibende Berichte: wenn/sofern/falls/sobald, nominale Vor-/Nach-/Während-Bezüge sowie vorausgesetzt/vorbehaltlich/unter Voraussetzung/Bedingung. Das Modell wählt vollständige ausgegebene Originaleinheiten; das Programm kopiert sie und prüft dieselben Quellen-/Satz-/Absatzgrenzen erneut. Verkürzter freier Text, auch in alten Speichern, fällt auf den Originalbericht zurück. Keine Erfüllung einer Bedingung oder Wahrheit wird daraus abgeleitet.

Funktionswörter sind keine nominalen Ereignisköpfe; „vor Ort“ ist ein Ortsausdruck. „erst/nur nach 10 Uhr“ bleibt unter der bisherigen Uhrzeitprüfung und ist nicht pauschal originalpflichtig. Keine geänderten alten Testerwartungen, zusätzliche UI, Datenfreigabe, Modellaktivierung oder Schemaänderung.

## Frische Nachweise

- Vor der Änderung: erster Testlauf 12 sachliche Fehler/6 Kontrollen; weitere vier Markerformen reproduzierten 12 zusätzliche Fehler. Die erste zu breite Kopplung der Zeitbedingungsregex erzeugte zwei echte Regressionen in bestehenden Uhrzeit-Tests; korrigiert, deren Erwartungen unverändert. Reviewer-Gegenbeispiele „vor Ort“ und „vor allem“ jeweils vor Korrektur reproduziert. Eine Scratch-Ausgabe versuchte irrtümlich `Versuch.to_dict()`; kein Fehlerbeleg.
- **45 neue Fälle**: Satzprüfung, tatsächliche frische und gespeicherte prepare/render-Antworten, vollständige Originale, serverseitige Originalstellen-Auswahl, Entzug und vorhandene Datumsumformulierung sowie Orts-/Funktionswortkontrollen. Keine echte Modellqualität behauptet.
- Auf dem eingefrorenen sauberen Gitarchiv **437 betroffene Tests bestanden**, eine bestehende Starlette/httpx-Warnung. Isolierte Mutation nur des Satzprüfungsmoduls auf die Baseline: **32 erwartete Fehler, 13 Kontrollen bestanden**. Vorheriger aktueller Kern-Audit zusätzlich 54 Claim-/Konflikt-/Zeit-/Pilotfälle bestanden; kein neuer Backend-Gesamtlauf.
- Unabhängiges enges Review; dessen konkrete Gegenbeispiele bearbeitet, finale Grenzen ausdrücklich erhalten.
- Lokales fertiges Abbild aus vorhandener Basis ohne Pull/Netzwerk, Basis-Schichten erhalten. **269 Python-/112 UI-Dateien** geprüft. **Zehn JSON-Protokolle** bestanden (neun Abläufe plus Metadaten), neu tatsächlicher Originalstore und frische/alte bedingte Antworten nach erneutem Öffnen der SQLite-Stores, Originalstellenwahl, Entzug und Originalerhalt. Fester lokaler Testanbieter, keine echte Inferenz, persönlichen Mounts oder Netzwerke. Der erste Paketversuch fing ein irrtümlich übernommenes altes Prüfsummenmanifest; nach korrekter Hash-Neuberechnung derselbe gebaute Container bestanden.
- ARM64-App/DMG frisch gebaut. Strenge tiefe Ad-hoc-Signatur und DMG-Integrität bestanden; nur lesend eingehängte App in allen sechs Dateien gleich, anschließend ausgehängt. Dauerhafte Kopie hatte neu hinzugefügte Finder-Metadaten, die die Signaturprüfung ablehnte; ausschließlich diese Metadaten entfernt, gleiche Datei-Hashes und Signatur anschließend bestätigt. Eine abschließende Prüfung zeigte erneut hinzugefügte Finder-Metadaten an der losen Kopie. Sie ist daher keine gültige startbare Lieferung und bleibt als `Kingfisher.app-Kopie-nicht-starten` diagnostisch erhalten. **Maßgebliches Installationspaket ist ausschließlich `Kingfisher.dmg`**: dessen tatsächliche dauerhafte Datei wurde frisch geprüft, nur lesend eingehängt, ihre App strikt signaturgeprüft und alle sechs Dateien gegen das Artefaktmanifest bestätigt, danach ausgehängt. Nicht notarisiert, kein Intel-/Fenstertest. UI/native/Designquellen unverändert.

## Grenzen

Die gemeinsame Originalprüfung ist konservativ: Eine echte Bedingung kann benachbarten Text desselben Absatzes mit erhalten, auch Boilerplate. Nominale Vor-/Nach-Bezüge sind kein allgemeiner Grammatikparser; weitere Ortsausdrücke oder ungewöhnliche Formen können konservativ Originaltext benötigen. Implizite Bedingungen, andere Sprachen, semantische Folgerungen und vom Modell ausgelassene relevante Quellen sind damit nicht allgemein gelöst. Der vollständige Gedächtnis-/CoS-Qualitätsmaßstab bleibt offen; er wird nicht auf Markerfälle reduziert.

**Nicht installiert; Fenstertest später.** Keine persönlichen Quellen, Kalender-/Mikrofonfreigaben, Kosten oder Importfortsetzung. Vor v21-Installation bleibt eine geprüfte vollständige persönliche Sicherung erforderlich; die ältere App kann v21 nicht direkt lesen.

Dauerhaft: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-conditional-report-e326f81/`. Lokales Abbild `sha256:f9caa5537b33403f0d7beff828a20fecd4ee3458d9ac41068e40d1cf1b436a6e`; Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.e326f81`. Kein Upload. Ältere Pakete unverändert erhalten. Manifeste, komprimierte Logs und isoliertes `probe.py` binden diese Aussagen.

```sh
docker run --rm --network none --read-only \
 --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
 -e ICARUS_DATA_DIR=/data --entrypoint python -i \
 ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.e326f81 - < probe.py
```
