# Quellenstatus aus Zeitplan und tatsächlicher Warteschlange

Code **a214f99cde2c8910d1ba5e762b2e89f485380471**, Paket **1.0.6-preview.a214f99**, Basis `31c42ad` der gemeinsamen offenen Draft-Vorschau #46. Ergänzung [#51](https://github.com/Icarus-health/kingfisher-app/pull/51) in die weiterhin offene [Draft-Vorschau #46](https://github.com/Icarus-health/kingfisher-app/pull/46) übernommen (`7c17427`); Laufzeit-, UI-, native, Design-, Deployment-, Script- und Versionsquellen bytegleich zum geprüften Code. Nicht in Main übernommen oder installiert.

## Konkreter Fehler und Änderung

Die Anzeige beurteilte Einordnung anhand des Gesprächsproviders (`agent.provider`). Der Scheduler verwendet jedoch eine eigene Hintergrundrolle. Bei einem entfernten oder fehlenden Gesprächsmodell erschienen selbst wirklich vorgemerkte/laufende Quellen als pausiert. Auch die gespeicherte Fehlermarkierung eines früheren Versuchs verdeckte eine neue wartende/aktive Wiederholung.

Der lesende Status verwendet nun allein die expliziten Zeitplanflags und vorhandene Scheduler-Beobachtungen. pending/failed plus beobachtetes processing zeigt laufende Arbeit; selbst nach einer inzwischen ausgeschalteten Freigabe kann der bereits laufende Job erst am nächsten Worker-Prüfpunkt abbrechen. Wartende Arbeit bei ausgeschaltetem Zeitplan bleibt paused/failed_paused. Bei eingeschaltetem Zeitplan zeigt eine beobachtete Schlange queued; ohne Beobachtung bleiben pending/failed neutral. Der Fehlertext verspricht keinen bereits laufenden erneuten Versuch. complete/empty/deferred/dismissed/excluded aus dem aktuellen Speicher haben weiterhin Vorrang.

Keine Providerauflösung, Modellprobe, Cloudwahl oder Aufnahme wird durch die Anzeige ausgelöst. Keine Schemaänderung, zusätzliche Oberfläche oder automatisch bestätigte Aussage. Dies ändert keine Worker-Freigabe.

## Nachweise

- 16 neue tatsächliche HTTP-Fälle mit echten Episode-/WorkingMemory-Stores und Scheduler; kein gestarteter Modellfaden. Fehlender/entfernter Gesprächsprovider, pending/queued/processing, Retry nach Fehler, beide Ausschaltflags, Original-/Fehlererhalt und complete/excluded gegen veraltete Scheduler-Einträge geprüft. Verbotene Providerauflösung/Modellprobe würde die Tests abbrechen.
- Der erste Testanlauf verwendete die lokale Umgebung ohne pytest; erste Fixture-Fassungen versuchten außerdem einen nur lesenden Provider zu setzen bzw. setzten einen nicht gestarteten Scheduler voraus. Dies sind keine Fehlerbelege. Der korrigierte RED-Lauf zeigt 9 sachliche Statusfehler und 3 bestandene Kontrollen. Zwei nachträglich ergänzte Retry-Fälle scheiterten vor ihrer Korrektur genau am persistierten failed statt queued/processing.
- **60 betroffene Tests** auf dem sauberen Gitarchiv bestanden: Quellenstatus, vorhandener Einordnungsstatus, zeitnahe Upload-Prüfung, Modellrollen, lokaler Hintergrund und echte Originalquellen-HTTP-Antworten. Eine bestehende Starlette/httpx-Warnung bleibt sichtbar. Kein neuer Backend-Gesamtlauf behauptet; frühere breite Prüfungen beziehen sich ausdrücklich auf frühere Laufzeitstände.
- Isolierte Mutation: nur das alte Quellenstatus-Modul in einer getrennten Kopie eingesetzt. **12 erwartete Fehler, 4 bestandene Kontrollen**. Produktiver/aktueller Arbeitscode nicht für die Mutation geändert. Ein erster Archivversuch mit einer älteren System-Python-Version unterstützte den sicheren tar-Filter nicht; er führte keine Tests aus, der korrigierte Versuch nutzt Python 3.12.
- Enges unabhängiges Review ohne Blocker; ID-statt-Generation-Grenze unten ausdrücklich erhalten.
- Fertiges Abbild aus vorhandener geprüfter Basis ohne Pull/Netzwerk, Basis-Schichten erhalten; **269 Python- und 112 UI-Dateien** gegen Manifest geprüft. Acht isolierte künstliche Paket-Protokolle bestanden, darunter tatsächliche Quellenstatus-API, Lernannahme/-entzug, neue Mailaufgaben-Wiedervorlage, sichere Wiederholung, Kontakt-/Quellenänderung sowie synthetische v20→v21-Sicherung und Wiederherstellung. Keine produktiven Mounts/Secrets/Modelle.
- Gepaarte ARM64-App/DMG frisch erstellt; strenge tiefe Ad-hoc-Signatur und DMG-Integrität bestanden. Nur lesend eingehängte App ebenfalls signiert und in allen sechs Dateien gleich. Danach ausgehängt. Nicht notarisiert; Intel, echte Fenster/Sprach-/Kalenderbedienung nicht geprüft. UI-, native und Designquellen gegenüber vorherigem Paket unverändert.

## Grenzen und nächste Abnahme

processing ist eine Beobachtung des Scheduler-Jobs zu einer Episoden-ID, kein Beleg dafür, dass bereits die jüngste Quellgeneration verarbeitet wird. Ordentliche Hintergrund-Batches ohne diese Upload-Markierung können weiter als ausstehend erscheinen. Eingeschalteter Zeitplan ist kein Modellbereitschaftsbeleg; Batterie-/Last-/Rücknahme-/Anbieterprüfungen bleiben im Worker. Die Anzeige verändert nie ein gespeichertes Verarbeitungsergebnis.

**Nicht installiert, Fenstertest später.** Keine persönlichen Quellen gelesen, keine EventKit-/Mikrofonfreigabe oder Modellkosten ausgelöst, kein Import fortgesetzt. Persönliche Qualität und Alltagstauglichkeit weiterhin offen. Vor Installation ist ein geprüftes vollständiges Backup des persönlichen v20-Bestands erforderlich; die Vorschau erbt v21, die ältere App braucht zur Rückkehr die Sicherung vor Umstellung.

Dauerhafte Ablage: `/Users/sorenkube/Documents/Codex/Kingfisher-Pruefpakete/2026-10-09-source-status-a214f99/`.
Lokales Abbild `sha256:552a7d2f6ccc6433357000c2385dfe0b034f597a8c7126ea87fca3009580937a`, lokaler Tag `ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.a214f99`. Nicht hochgeladen. Ältere Prüfpakete/Protokolle bleiben erhalten.

Die Freeze-, Eingabe-, Prüf- und Artefaktmanifeste sowie komprimierte Logs binden die Aussagen. Isolierte Wiederprüfung nur mit vorhandenem lokalem Abbild:

```sh
docker run --rm --network none --read-only \
  --tmpfs /data:rw,uid=1000,gid=1000 --tmpfs /tmp:rw,uid=1000,gid=1000 \
  -e ICARUS_DATA_DIR=/data --entrypoint python -i \
  ghcr.io/icarus-health/kingfisher-app:1.0.6-preview.a214f99 - < probe.py
```
