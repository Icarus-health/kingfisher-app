# Ein vorhandenes lokales Modell für den quellengebundenen Frageweg

Produktstand `e30103e893da925511dca974ca52fc9a6d06bce9`. Auf dem Mac fehlt weiterhin das gewählte Gemma12B-Antwortmodell; Ollama war vor der Probe nicht erreichbar. Das wiederhergestellte `kingfisher-qwen3.5:9b-32k` wurde deshalb als **Kandidat** für Frageverständnis und Quellenauswahl zusammen geprüft. Keine persönlichen Modellrollen geändert, kein produktiver Modellserver gestartet, große Aufnahme bleibt pausiert. Die Kalenderfreigabe nach Nutzerbestätigung erneut lesend bestätigt: aktiviert, `granted`, Helfer online, kein Fehler, drei ausgewählte Kalender, `memory_allowed:false`. Der Mac-Fenstertest bleibt wegen erneut gesperrtem Mac offen.

## Tatsächlich ausgeführter Weg

18 erfundene Originalquellen: der bereits eingefrorene CoS-Katalog mit 14 Quellen/23 Fragen plus vier frühere Anchor-Kontrollen. Produkt-Dokumentupload und Gesprächsrouten über ASGI `TestClient`; **kein TCP-/Uvicorn-Server und kein nativer Fensternachweis**. Persistente temporäre Stores vor Fragen neu geöffnet, für jede Frage ein neuer Agent und ein neues Gespräch. Derselbe positiv auf lokale Gewichte geprüfte Anbieter für Frageverständnis und Quellenauswahl; freie Satzgenerierung aus, Originalstellen angezeigt. Die Arbeitsinterpretation ist bewusst deterministisch als vollständiger Originalabschnitt indiziert: **keine neue Modellaufnahme, Personen-/Themen-Einordnung oder semantische Suchqualifikation**.

Ollama aus der vorhandenen offiziellen App auf eigenem Port11439 mit eigenständigen APFS-Dateiklonen, unterschiedlichen Inodes und geprüften SHA256. Keine Hardlinks/Symlinks auf Modellgewichte, kein Download/Fallback, Cloud aus, Pruning aus, ein geladenes Modell, ein paralleler Aufruf. Nur PATH/LANG/TMPDIR/LC_ALL und das unveränderte, für Ollama erforderliche HOME geerbt; keine API-Schlüsselvariablen. Das ist kein Nachweis darüber, welche allgemeinen lokalen Ollama-Konfigurationsdateien der Hersteller intern liest. Persönliche Kingfisher-Einstellungen/-Datenverzeichnisse werden vom Test nicht geladen.

## Ergebnisse und Grenzen

| Nachweis | Ergebnis |
|---|---|
| Angezeigte Quellen und Antwortstatus | 23/23 entsprechen den eingefrorenen Sollwerten |
| Unabhängige manuelle Inhaltsprüfung | Alle 23 Antworten durch Originale gedeckt; keine unbelegte Sachbehauptung gefunden |
| Frageverständnis aus gültiger Modellausgabe | 18/23; fünf deterministische Rückfälle |
| Quellen-/Statuswertung ohne Transportfehler | 22/23; RQ01 hat einen Modellfehler trotz anschließend richtiger Antwort |
| Rückfälle | RQ01 Modellfehler; RQ04/RQ05/RQ12/RQ15 ungültige Ausgabe |
| Originale nach Fragen | Alle erhalten |
| Ein Quellenentzug nach erneutem Neustart | `working_unavailable`, keine Links, null Modellaufrufe, Originaltexte erhalten |
| Testprozesse/Modellcache | Beide eigenen Prozessgruppen anschließend leer; native Gewichte/Manifeste bytegleich |

Die Inhaltswertung gilt ausschließlich für diesen kleinen künstlichen Katalog und die angezeigten Quellenberichte. Der Lauf enthält weder eine neue Zufallsstichprobe noch persönliche Daten; Ergebnisse sind keine statistische Genauigkeitsquote oder Abnahme für den großen Mailbestand. Es wurden keine Tasks/Kalenderentscheidungen aus dem Modell angenommen. Der geprüfte Rückfall bleibt notwendig; die vier ungültigen Ausgaben werden nicht durch lockere Validierung nachträglich als Modell-Erfolge gewertet.

Letzte Laufmessung186,42 Sekunden, maximale stichprobenweise Summe des RSS der eigenen Prozesse8,353GiB. Watchdog480 Sekunden/11GiB RSS; **kein harter GPU-/Unified-Memory-Deckel und kein Akku- oder Tagesbetriebsnachweis**. Vor/nach Klonen jeweils mehr als10GiB SSD frei. Modelle nach dem Lauf nicht resident; Klone, Testdaten und Logs bleiben als temporäre Belege erhalten. SIGTERM führt jetzt durch den Cleanup; SIGKILL ist nicht abfangbar, deshalb PIDs zusätzlich gespeichert. Kein neuer allgemeiner Backend-/UI-Testlauf.

Zwei fehlgeschlagene Aufbauten bleiben in `setup-failures.json`: fehlendes FastAPI vor jeder Modellanfrage, danach fehlendes HOME vor jeder Modellanfrage. In beiden Fällen Prozesse beendet und Originalgewichte unverändert. Die benötigten öffentlichen Python-Testpakete wurden anschließend in eine eigene temporäre Umgebung aus dem offiziellen PyPI-Register geladen; keine Kingfisher-Inhalte übertragen. Exakte Testabhängigkeiten stehen in `test-dependencies.txt`; das ist nicht die Dependency-Liste des installierten Docker-Pakets. Die Starlette/httpx-Abkündigung im Log ist kein fehlgeschlagener Produktcheck.

## Konsequenz für den Alltag

Qwen9B ist ein plausibler lokaler Kandidat für beleggebundene Fragen, wenn Originale korrekt aufgenommen und suchbar sind. Dieser Nachweis allein rechtfertigt keinen großen automatischen Import und keine freie Antwortqualifikation. Als nächstes müssen der normale lokale Start und die aktive Antwortrolle zusammenpassen; danach ein kleiner gesicherter persönlicher Aufnahme→Frage→Aufgabe-Ablauf. Keine zweite Gedächtnisablage, keine neue Modellnachladung bei knapper SSD und keine automatische Cloudfreigabe.

`question_flow.py` und `run_native.py` sind konkrete damalige Run-Treiber mit festgelegten temporären Pfaden; nicht blind erneut ausführen. Antworten, Eingabeprüfsummen, Runtime, Aufbaufailures und unabhängiger Inhaltsbericht sind dauerhaft gespeichert. Modellgewichte, private Einstellungen und private Originalquellen sind nicht Bestandteil des Repositorys.
