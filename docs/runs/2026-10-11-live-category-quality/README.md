# Tatsächliche lokale Einordnungsprobe, 11. Oktober 2026

**Ergebnis: Qwen 3.5 4B erfüllt fünf von acht künstlichen Sollfällen. Die eingestellten 9B-/12B-Modelle sind nicht qualifiziert, weil ihre lokalen Gewichtedateien fehlen.** Keine Umstellung der persönlichen Modellwahl, kein Importstart, keine Cloudanfrage oder Modellnachladung.

## Ausgangslage und abgegrenzter Dienststart

Die erste [ausführbare Probe](../2026-10-11-category-quality-probe/README.md) konnte Ollama nicht erreichen. Eine anschließende lesende Hostprüfung bestätigte: kein Ollama-Prozess, vorhandener signaturgeprüfter offizieller CLI-Client 0.35.1, Mac mit 32 GiB am Strom, Akku geladen. Die Computersteuerung meldet weiterhin einen gesperrten Mac; keine neue Fensterabnahme.

Für die Probe wurde ausschließlich der vorhandene CLI-Dienst vorübergehend gestartet: `127.0.0.1:11434`, Cloudfunktionen aus (`OLLAMA_NO_CLOUD=1`), kein Pruning, höchstens ein geladenes Modell und eine parallele Anfrage, kurze Aufbewahrung von 15 Sekunden. Kein Autostart oder persistenter Konfigurationswechsel. Der große Kingfisher-Import bleibt unabhängig davon pausiert.

## Fehlender Modellbestand

Die API meldete nur zwei vollständig vorhandene Modelle: `qwen3.5:4b` und `bge-m3:latest`. Im üblichen lokalen Modellordner liegen außerdem Manifeste der eingestellten Kingfisher-Modelle vor, ihre referenzierten Dateien fehlen jedoch:

| Konfiguriertes Modell | Manifest vorhanden | Nicht vorhandene referenzierte Dateien |
|---|---|---:|
| `kingfisher-qwen3.5:9b-32k` | ja | 6 |
| `kingfisher-gemma4:12b-32k` | ja | 7 |

Der ursprüngliche 9B-Basistag verweist ebenfalls auf fehlende Dateien. Für die großen Gewichte und eine kleine Konfigurationsdatei wurde zusätzlich die tatsächliche Verzeichnisexistenz geprüft: keine verdeckt ausgelagerten/broken Symlinks an diesen Stellen. Große Gewichtedateien wurden nicht gelesen oder verändert. Die Ursache des Verlusts ist nicht ermittelt; niemandem eine Löschung zugeschrieben.

Der Dienststart behebt diesen fehlenden Bestand nicht. Der Läufer für das eingestellte 9B-Modell endet korrekt mit Exit 2, `model_not_proven_local`, null Inferenzversuchen: [configured-qwen9b-not-run.json](configured-qwen9b-not-run.json). Während Ollama erreichbar war, zeigte auch die installierte App ihr eingestelltes Antwortmodell als `fehlt`. Das ist keine unbemerkte Umschaltung auf das kleinere Modell.

Die SSD-Prüfung meldete rund 20 GiB freien Platz und 98 % belegte Kapazität. Beide größeren Modelle blind neu herunterzuladen würde zusätzlichen Platz beanspruchen; kein solcher Download oder Löschen vorhandener Dateien erfolgte. Nächster Modellschritt: fehlenden lokalen Bestand gezielt wiederherstellen, zunächst das bereits ausgewählte Einordnungsmodell, Kapazität berücksichtigen und dann mit dessen eigener Kennung messen. Kein neues Modell aufgrund des Namens allein qualifizieren.

## Echte 4B-Messung

Der [Prüfläufer](../../../scripts/probe_category_quality.py) aus `a0e09b4` hat alle acht Fälle über die unveränderten Produktionsfunktionen ausgeführt. Die Kategorienimplementierung ist gegenüber dem installierten Laufzeitcode `6979131` unverändert. Separate temporäre SQLite-Stores, ausschließlich künstliche Texte, kein persönlicher Quellenzugriff durch den Modellprozess.

```sh
PYTHONPATH=sidecar:scripts python scripts/probe_category_quality.py \
  --model qwen3.5:4b --output /tmp/kingfisher-quality-qwen4b-new.json
```

Tatsächlicher Bericht: [qwen4b-results.json](qwen4b-results.json). Exit 1, acht Inferenzversuche, acht auswertbare Fälle, **fünf genaue Sollmengen erfüllt**, rund 22 Sekunden für den gesamten Lauf. Alle acht Originaldatensätze unverändert; keine Belegvalidierungsfehler. Modelleigener Name/Metadaten sowie Katalog- und Produktkategorien-Prüfsummen sind getrennte Nachweise, keine Garantie statistischer Genauigkeit.

| Fall | Beobachtung |
|---|---|
| Werbung, automatische Statusmeldung | Information, keine erfundene Person: Soll erfüllt |
| Konkreter Projektauftrag | Arbeit erkannt, genannte Person fehlt |
| Newsletter mit persönlichem Auftrag | Beide Themen und genannte Person erkannt: Soll erfüllt |
| Rechnung | Finanzen: Soll erfüllt |
| Buchungsbestätigung | Termine/Buchungen: Soll erfüllt |
| Bedingter Projektbericht | Arbeit erkannt, genannte Person fehlt |
| Historischer abgesagter Projektauftrag | „Unklar“ statt des vorgegebenen historischen Arbeitsthemas |

Personenerkennung ist damit für diesen kleinen Vergleich nicht zuverlässig genug. Die historische Kategorie ist ein manueller Sollwert; die Probe sagt nichts darüber aus, ob daraus eine falsche aktuelle Aufgabe erzeugt würde. Bedingungen, Fristen, Identitätsauflösung und spätere Antworten gehören nicht zu dieser Messung. Kein Prozentwert für den persönlichen Mailbestand abgeleitet; kein Qwen-4B-Ergebnis für das fehlende Qwen-9B- oder Gemma-Modell behauptet. Kein Prompt auf diese acht Fälle angepasst und kein schwächeres Modell als Ersatz freigegeben.

API-Modellmetadaten für 4B: Manifest-Digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`, GGUF/Q4_K_M, nominell 4.7B, Paketgröße 3.389.983.735 Bytes. Nach dem Lauf meldete `/api/ps` ein geladenes Modell mit Kontext 32.768 und 4.346.882.292 Bytes Größe/VRAM. Das ist ein einzelner beobachteter Modellwert, kein RSS-/Spitzenwert oder kompletter Akkulasttest. `memory_pressure -Q` meldete 54 % vor, 32 % nach dem Lauf; keine Umrechnung in zugesicherte freie RAM-Bytes.

## Abschluss und Erhaltungsprüfung

Das ausschließlich für diese Probe geladene 4B-Modell wurde ausdrücklich entladen; anschließend null Modelle in `/api/ps`. Der eindeutig identifizierte eigene Testdaemon wurde beendet. Terminalhandle abgeschlossen, kein passender Prozess mehr, Loopback-Endpunkt wieder nicht erreichbar. Danach 57 % in der lesenden Speicherdruckabfrage. Kein dauerhafter Dienststart behauptet.

Die sieben persönlichen Kerntabellen wurden anschließend vollständig lesend über sortierte Zeilenprüfsummen mit dem nach der nativen Bedienprobe festgehaltenen Bestand verglichen: **alle identisch**. 344 Originalepisoden, 333 Quellenverweise, drei Gespräche/14 Nachrichten, keine Aufgaben/Projekte/Notizen. Keine privaten Prüfsummen, Originale, Zugangsdaten oder Dienstlogs im Repository. Die vorherige Sicherung bleibt erhalten. App-Paket und Modellwahl unverändert.

[Bereinigte Nachprüfung](host-postrun-checks.json): fehlende Modellreferenzen und freier Speicher frisch gelesen; eigener Daemon nicht vorhanden, Loopback-Endpunkt nicht erreichbar. Vergleich der separat privat gespeicherten Vor-/Nach-Zeilenprüfsummen als Gleichheitswert und Zeilenzahlen dokumentiert. Die Nachprüfung enthält keine privaten Prüfsummen oder Texte. Unabhängiger Reportreview bestätigte Fallzahlen, Sollabweichungen, Katalog-/Produktprüfsummen und Bereichsgrenzen; er hat die persönlichen Tabellen und Hostzustände nicht selbst gelesen.

Dieser Schritt liefert erstmals für diesen Acht-Fälle-Katalog einen echten Modellbefund. Er ersetzt weder die offenen anderen Modellprüfungen noch Datei-/Sprach-/Kalender-Vollständigkeitsabnahme oder einen persönlichen Arbeitstag. Kein neuer Code-Testlauf nötig: keine Produkt- oder Läuferänderung; zuletzt 123 betroffene Tests im vorherigen Schritt. Kein CI-Neustart, kein Merge nach main.
