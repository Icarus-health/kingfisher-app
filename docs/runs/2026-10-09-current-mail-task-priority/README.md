# Neue Mailaufgaben vor dem historischen Bestand prüfen

Code **1913e265744344de91b123ab1dc6e58dbd4b9ca3**, Version **1.0.6-preview.1913e26**. Ergänzung zur gemeinsamen Vorschau #46 auf `integration/cos-preview-reviewed-20261009`; keine Installation oder Veröffentlichung.

## Problem und Verhalten

Während eines großen Erstimports war neue Post beim Abruf bereits priorisiert, ihre Aufgabenprüfung wartete jedoch auf den regulären Zeitplanlauf und konnte hinter dessen Scan-Zeiger liegen. Nun wird eine neu erfasste Live-Mail im selben Speichervorgang in die vorhandene textfreie Wiedervorlage gestellt. Der bestehende Scheduler prüft zwischen vollständigen Durchgängen höchstens zwei Quellen und höchstens 20 Queue-Zeilen. Er durchsucht dabei weder historische Quellen noch alle offenen Aufgabenvorschläge. Es gibt keinen zusätzlichen Worker und keine automatische Aufgabenübernahme.

Modellfreigabe, manuelle Pause, Aktivitäts-/Last-/Stromgrenzen, Parallelitätssperre und Wiederherstellungssperre gelten weiter. Briefing, Anzeige und Annahme prüfen Quellen und Beteiligtenkontext frisch. Fehlende Modellfreigabe aktiviert kein Modell. Bestehende historische Mails werden durch diese Änderung nicht als neue Post behandelt; der normale Scan bleibt erhalten. Eine Wiederherstellungssperre blockiert die Arbeit, beendet aber nicht mehr den Scheduler-Thread.

Die bestehenden vier Health-ISO-Leser verwenden nun den zentralen Leser mit identischer Parse-Semantik. Diese kleine Korrektur wurde durch die Datums-Konventionsprüfung im breiten Testlauf gefunden; Gesundheitswerte und Datenformat ändern sich nicht.

## Nachweise

- Definitive Baseline: korrigierte Live-Mail-Fixture auf `0d1c868` reproduziert beide ursprünglichen Fehler. Die erste Fixture hatte durch Lane-Wechsel fälschlich eine historische Mail gewählt; ihre Resultate sind kein Baseline-Nachweis. Gesichert ist der korrigierte RED-Lauf.
- Zusätzliche RED-Prüfungen für ungewollten globalen Scan und Scheduler-Abbruch bei `RestorePending`. Finale betroffene Mail-/Aufgaben-/Scheduler-/Pause-/Lastprüfungen: **139 bestanden** auf `b472108`. Die anschließende Health-Helferkorrektur wurde mit allen Datums-/Health-Fällen geprüft: **42 bestanden**.
- Zwei unabhängige Mutationen in getrennten Kopien: Live-Wiedervorlage entfernt beziehungsweise historischer Scan im kurzen Lauf wieder zugelassen. Jeweils der passende Regressionstest schlägt fehl. Produktiver Code wurde nicht für die Mutationen verändert.
- Der erste breite Lauf auf `b472108` wurde ausdrücklich beendet, nachdem künstliche Loopback-Testserver an eingeschränkten Testrechten scheiterten. Er war **nicht grün und nicht vollständig**: 13 fehlgeschlagen, 2713 bestanden, 36 Setupfehler, 1 Skip und 26 Unterfälle. Die vollständigen Fehlernamen stehen in `interrupted-test-diagnosis.json`. Ein Fehler betraf tatsächlich die Health-Datumskonvention und wurde behoben. Die umgebungsabhängigen vollständigen Testdateien bestehen mit geeigneten Rechten: **168 bestanden**. Kein Zugriff auf echte Mail-/Kalenderkonten dabei.
- Ein frischer vollständiger Backendlauf auf dem sauberen finalen Gitarchiv `1913e26` ist gestartet. Ergebnis wird getrennt festgehalten; diese Notiz behauptet noch keinen erfolgreichen Gesamtlauf.
- [Unabhängiges enges Review](independent-review.md), ohne eigenen Testlauf. Die gefundenen Grenzen wurden korrigiert und regressionsgeprüft.
- Frische ARM64-App und DMG gebaut, strenge tiefe Ad-hoc-Signatur und DMG-Prüfsumme bestanden. Nicht notarisiert, Intel nicht geprüft. Erste frühere Buildprobe scheiterte bei der Icon-Konvertierung; erneuter Build in getrennter Quelle mit passenden OS-Rechten bestand. Kein gleichzeitiger Test-/Build-Ausgabeordner mehr.
- Fertiges lokales Abbild ohne Pull oder Netzwerk aus vorhandener Basis gebaut. Alle **269 Python-/112 UI-Dateien** gegen Manifest geprüft; UI unverändert gegenüber dem bisherigen Paket. Sechs künstliche Paketabläufe bestanden, einschließlich Live-Mail → Wiedervorlage → kurzer Schedulerlauf → prüfbarer Aufgabenvorschlag, ohne historischen Scan oder automatische Annahme. Gesundheits-/Quellen-/Kontakt-/Wiederholungs- und synthetische v20→v21-Sicherungs-/Restore-Prüfungen bestanden ebenfalls.

## Grenzen und Ablage

**Nicht installiert. Fenstertest später**, wie ausdrücklich gewünscht. Keine persönliche Mail, kein Kalenderinhalt, kein Mikrofon oder EventKit, kein Cloudaufruf, kein echtes Modell, kein Download und keine Import-Fortsetzung. Die Paketurteile sind künstliche Testantworten, kein Nachweis inhaltlicher Modellqualität. Persönliche Abruf-/Einordnungsqualität, echte Kalenderdarstellung, RAM/Akku und Alltagstauglichkeit bleiben offen. Ein fehlerfreies Gedächtnis wird nicht behauptet.

Dauerhafte separate Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-current-mail-1913e26/`. Vorherige Pakete bleiben erhalten. Lokales Abbild `sha256:6b03de639866319d310581f003345c458b13e824d53bb4e76a5381c14f5c9430`; nur lokaler Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.1913e26`.

Vor späterer Installation ist eine geprüfte vollständige Sicherung des tatsächlichen Bestands nötig. Die ältere App kann v21 nicht direkt öffnen; eine Rückkehr benötigt die Sicherung von vor der Umstellung. Die künstliche Restore-Probe ersetzt keine persönliche Sicherung.

`freeze.json`, `package-inputs.json`, `package-verification.json` und `artifact-sha256.json` binden Code und Artefakte. Rohlogs verlustfrei komprimiert. Lokale Reproduktion des Paketablaufs mit bereits vorhandenem Abbild:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.1913e26 - < probe.py
```
