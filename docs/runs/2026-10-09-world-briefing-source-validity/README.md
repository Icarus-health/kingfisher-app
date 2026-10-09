# Weltmeldung nur aus aktuellen Quellen und eigenen Belegen

Code **e2bd4c14e98a0aed7ca8a873286dbf46e53c52ad**, Paket **1.0.6-preview.e2bd4c1**, Basis `f782636` der offenen gemeinsamen Draft-Vorschau #46. Ergänzung [#52](https://github.com/Icarus-health/kingfisher-app/pull/52) in die weiterhin offene [Draft-Vorschau #46](https://github.com/Icarus-health/kingfisher-app/pull/46) übernommen (`30dde28`); Laufzeit-, UI-, native, Design-, Deployment-, Script- und Versionsquellen bytegleich zum geprüften Code. Nicht in Main übernommen und nicht installiert.

## Fehler und Korrektur

Der gespeicherte Tagestitel blieb sichtbar, wenn eine öffentliche Quelle direkt abgeschaltet, ignoriert oder durch eine neue Fassung ersetzt wurde. Die erste Auswahl las außerdem ignorierte/veraltete Originale. Auch der private Begründungstext konnte nach Rücknahme seiner eigenen Belege weiter erscheinen. Der Link zeigte die registrierte Adresse statt der tatsächlichen Originaladresse nach Weiterleitung.

Öffentliche Ausschnitte werden nun an die aktuelle Head-Episode und ihren Fingerabdruck gebunden. Aufnahme und Tagesspeicher werden vor Auswahl, Speicherung und Rückgabe erneut geprüft: aktiv/ausgewählt, erfolgreiche Aufnahme ohne Fehler, gültige Zeitzone, nicht zukünftig und höchstens 24 Stunden alt, nicht ignorierter aktueller WEB-Head der richtigen Quelle. Der Link stammt aus der Originalprovenienz. Die private Begründung wird ausschließlich für die bereits gewählte Sache aus noch verfügbaren eigenen Quellen erneut berechnet; stimmt sie nicht mehr, verschwindet die Anzeige. Es wird keine Ersatzmeldung am selben Tag gewählt. Gespeicherte Historie und Original bleiben erhalten.

Alte öffentliche Tagesspeicher ohne Fassungsbindung werden ausgeblendet. RSS wird weiterhin als Fremdbericht behandelt; keine Änderung seiner Erfassung oder des Feed-Eintragstyps. Gemeinsame Rückhalt-/Begründungshilfen vermeiden neue Kandidatenauswahl beim Lesen. Keine Modellaktivierung, neue Datenfreigabe, Schemaänderung, automatisch bestätigte Aussage oder neue Oberfläche.

## Nachweise

- 16 neue Regressionfälle: Entzug vor und nach Auswahl, direkter Disable/Ignore/neuer Head, fehlende/ungültige/naive/veraltete/zukünftige Aufnahme, unveränderte Wiederholung und tatsächlicher Link, alter Cache ohne Bindung, eigener Quellenentzug, Disable zwischen Auswahl/Speicherung, erneute Fehler-/Altersprüfung beim Lesen.
- Korrigierter erster RED-Lauf mit 12 Fällen: 11 scheiterten, eine Kontrolle bestand. Zusätzlich reproduzierte der später ergänzte eigene Quellenentzug seinen Fehler.
- Frisch auf dem eingefrorenen Gitarchiv: **105 betroffene Tests bestanden**, eine bestehende Starlette/httpx-Warnung. Isolierte Mutation nur des Produktionsmoduls auf die Baseline: **15 erwartete Fehler, eine bestandene Kontrolle**. Kein neuer vollständiger Backendlauf behauptet.
- Vorhandener positiver öffentlicher Quellen-Test verwendet jetzt den echten EpisodeStore und tatsächlichen Source-Head statt einer Fixture ohne Versionsbeleg; Erwartungen unverändert.
- Unabhängiges enges Diffreview ohne konkreten Blocker; Grenzen ausdrücklich unten.
- Lokales Abbild ohne Pull/Netzwerk aus geprüfter Basis gebaut, Basis-Schichten erhalten. **269 Python- und 112 UI-Dateien** im echten Container gegen Manifest geprüft. Neun JSON-Protokolle bestanden (acht Abläufe plus abschließende Paket-Metadaten); neue Weltprüfung verwendet tatsächliche HTTP-Registrierung/Abruf/Abschaltung und Originalspeicher, kontrollierte eigene Bezüge und feste synthetische Inhalte. URL-DNS-Prüfung hierfür gezielt ersetzt, also kein Sicherheitsnachweis der URL-Grenze. Kein echter Anbieter oder produktiver Mount.
- ARM64-App/DMG frisch gebaut; strenge tiefe Ad-hoc-Signatur und DMG-Integrität bestanden. Nur lesend eingehängte App ebenfalls signiert und alle sechs Dateien gleich; dauerhafte Kopie erneut geprüft und DMG ausgehängt. Nicht notarisiert, kein Intel-/Fenstertest. UI/native/Design gegenüber vorherigem Paket unverändert.

## Grenzen und nächste Abnahme

Frischer Abruf beweist nicht Veröffentlichungstag oder Wahrheit. Öffentliche Ausschnitte behalten keinen behaupteten Veröffentlichungstermin. Eigener Quellenabgleich bleibt auf die ersten 40 Belege begrenzt. Live-Prüfung über getrennte Stores ist keine atomare Gesamtsicht. Ein ausgeblendeter alter Tagesspeicher wird erst am nächsten regulären Tag neu gewählt; keine stille Ersatzmeldung. Persönliche Auswahl öffentlicher Quellen und Relevanz-/Inhaltsqualität sind nicht getestet.

**Nicht installiert, Fenstertest später.** Persönliche Daten, Modelle, Kalender-/Mikrofonfreigaben, Import und produktive App unverändert. Vor Installation bleibt die geprüfte vollständige persönliche Sicherung vor v21 erforderlich; Rückkehr zur älteren App erfordert die Sicherung vor Umstellung.

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-world-validity-e2bd4c1/`.
Lokales Abbild `sha256:fc2b486e0644fe17ad2dc4baf9d3098051ff8a6a5ded9e5db90b5d56b78ecf5f`, Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.e2bd4c1`. Nicht hochgeladen. Ältere Pakete bleiben erhalten.

Freeze-, Eingabe-, Prüf- und Artefaktmanifeste sowie komprimierte Logs binden diese Nachweise. Wiederprüfung nur mit vorhandenem lokalem Abbild:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.e2bd4c1 - < probe.py
```
