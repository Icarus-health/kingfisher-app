# Zeitangaben vor der Modellausgabe begrenzen

Der native Mac-Vorherlauf des unveränderten Codes zeigt: qwen3.5:4b ergänzt in vielen zeitlich unbeschränkten Fragen `heute`. Der Validator lehnt dies korrekt ab, verwirft dabei jedoch auch sinnvolle Suchumschreibungen. 35 von 36 Fragen fallen auf die regelbasierte Anfrage zurück; es sind keine Transportfehler.

Der lokale strukturierte Aufruf erhält deshalb eine eigene Kopie des Schemas: `zeitraum` erlaubt nur `keiner` und gegebenenfalls den bereits von der vorhandenen Erkennung bestimmten Zeitraum. Das ist genau die bisher akzeptierte Menge. Keine Lockerung des Validators, keine nachträgliche Reparatur einer Modellausgabe, keine Änderung an Suchschwelle, Quellenindex oder Auswahlprompt. `keiner` bleibt auch bei einer erkannten Zeitangabe möglich; Mehrdeutigkeiten und Grenzen der vorhandenen Zeiterkennung werden damit nicht neu gelöst.

## Reale Modellmessung

Ausschließlich künstliche Kataloge und vorhandene lokale Gewichte. Eigener nativer Ollama-0.35.1-Dienst auf 127.0.0.1:11439, Mac am Netzteil, Apple M2 Max/Metal im Laufzeitlog bestätigt, Kontext 4096, höchstens zwei geladene Modelle, Parallelität 1. qwen3.5:4b für Fragenverständnis und Quellenauswahl; bge-m3:latest für den echten dauerhaften SemanticService. Modellrollen, persönlicher Import und produktiver Ollama-Dienst bleiben unverändert/pausiert. Keine Cloudinferenz, kein Modell-Download. Dies ist **keine Netzisolierung** des nativen Prozesses und **keine harte GPU-/Speichergrenze**: Ein Watchdog beendet nur die eigenen Prozessgruppen bei gesampeltem RSS über10 GiB oder600 s. GPU-Allokationen sind damit nicht vollständig erfasst.

Die Einordnung der künstlichen Quellen ist deterministisch. Gemessen werden Abruf, Auswahl und Originalzitate; keine Aufnahmequalität, keine freie Antwortgenerierung und kein großer persönlicher Bestand. Jede Frage erhält einen unabhängigen Agenten. Der Quellenentzug wird mit einer zuvor angezeigten Antwort erneut geprüft.

Ein erster Versuch endete vor jeder Einbettung, weil in der nativen Testumgebung sqlite-vec fehlte. Eine bereits vorhandene Mac-arm64-Wheel 0.1.9 wurde lokal installiert; erst die abgeschlossenen folgenden Läufe zählen. Die gescheiterte Umgebung wurde beendet, nicht als Antwortfehler ausgewertet.

| Originalkatalog,36 Fragen | Vorher | Nachher |
|---|---:|---:|
| Formal übernommenes Modell-JSON | 1 | 32 |
| Direkte Quellen-/Statuspunkte | 15/16 | 15/16 |
| Umschreibungs-Quellen-/Statuspunkte | 9/16 | 11/16 |
| Korrekte Nichtantworten | 4/4 | 4/4 |
| Median gesamte Antwortzeit | 3,297s | 3,641s |

Q6 findet neu den Aufbewahrungsort der Zugangskarte. Q2 zeigt neu das Wartungszitat; eine Unerreichbarkeit ist dadurch **nicht belegt**. Der Score misst passende Quellen/Status, nicht beantwortete Bedeutung jeder Frage. Q13 liefert eine sinnvolle Zeitbezugsrückfrage und zählt im strikten Gold trotzdem als Misserfolg. Die unabhängige Inhaltsprüfung findet keine verlorene Einschränkung oder erfundene Aussage in den sichtbaren Zitaten. Vier Fragen fallen nachher weiterhin auf Regeln zurück. Formal übernommenes JSON ist keine bewiesene Interpretation: beispielsweise ist `wartet_auf` bei Q26 fachlich fragwürdig. Kein allgemeiner Beschleunigungs- oder Fehlerfreiheitsnachweis.

Der Katalog blieb unverändert. Beide Originalkatalog-Treiber enthalten im Textfeld `tested_code` eine statische, für den Nachherlauf unzutreffende Bezeichnung „unchanged f5af412“. Die tatsächliche Vorher-/Nachherzuordnung ist durch `code_version`, ausgeführte Treiber, den Produktdiff und den begleitenden Manifestnachweis festgehalten. Die Rohberichte werden inhaltlich nicht nachträglich umgeschrieben; ihre SHA-256 bezieht sich auf die dekomprimierten Originalbytes.

## Unabhängige Kontrollmenge

Die vorab eingefrorenen 23 Fragen aus `retrieval-controls/catalog-20261008.json` wurden vor und nach der Änderung vollständig gemessen. Der Baseline-Code liegt dafür in einer eigenen Kopie mit unveränderter `frage.py` aus f5af412; die Nachhermessung lädt den Kandidaten. Beide finden dieselben Quellen mit denselben Statuswerten:22/23 Quellen-/Statuspunkte, keine neue Fehlzuordnung. Der verbleibende Fall liefert die richtige Sichtprüfungsquelle zu KL-42 mit unnötiger Personenrückfrage. Formal übernommenes Modell-JSON steigt 1→18/23, Median 4,160→4,105s. Das beweist keine allgemeine Beschleunigung. Beide Mehrthemenquellen bleiben erhalten, vier unbeantwortbare Fragen ohne Antwort. Alle vier Läufe bestehen Quellenentzug, ohne Providerfehler oder ausgefallene Bedeutungssuche.

Die Rohberichte liegen bytegetreu in `.json.gz` komprimiert bei, `summary.json` zeigt die wesentlichen Ergebnisfelder lesbar; `manifest.json` verknüpft Hashes, tatsächliche Quellenstände, Laufzeiten, Gewichte, Metal-Nachweis und gesampelten eigenen Speicher. Spitzen-RSS über alle abgeschlossenen Läufe rund 5,79GiB, kein Speichercap-Beweis. Ausgeführte Treiber mit an diesen Mac gebundenen Pfaden liegen bei; für andere Rechner müssen Repo-/Ausgabepfade und installierte lokale Modelle ausdrücklich angepasst werden. Keine produktiven Einstellungen übernehmen.

## Regressionen

Vier neue Fälle scheitern vor der Änderung; der zusätzliche Fall für ein Modell, das das Schema missachtet, besteht bereits vorher. Danach85 Frage-/Transportprüfungen bestanden, einschließlich echtem langsamem Loopback-Server. Erweiterter betroffener Lauf:191 Prüfungen bestanden, eine bestehende Starlette/httpx-Warnung. Gemeinsames Schema bleibt unverändert, verschiedene Anfragen verlieren keine Zeitbereiche, ungültige Zeitangaben werden weiterhin verworfen. Unabhängiges Code- und Inhaltsreview fand keine wichtige Regression im begrenzten Diff.

## Noch offene Abnahme

Fünf Umschreibungen bleiben ohne passenden Quellen-/Statuspunkt. Teilweise wird die richtige Quelle gefunden, danach verworfen. Die Katalogfragen enthalten zudem weitergehende Annahmen (Wartung/Ausfall, Überweisung/Erledigung, Messegesamtbudget/Standbudget, Urlaub/allgemeine Stellvertretung), die nur eingeschränkte Quellenberichte tragen. Originalzitate erhalten ihre Bedingungen; sie beweisen keine aktuelle Anwendbarkeit oder Zuordnung zum Nutzer.

Native Fensterprüfung erneut blockiert: Mac gesperrt. Die reale Quellenabdeckung, Einordnungsqualität, persönliche Alltagsbedienung und Akkulaufzeit sind weiterhin nicht abgenommen. Kein neuer vollständiger Backend-/UI-Lauf und keine CI-Wiederholung.

## Lieferung

Produktcode `064a4d9ae3f24112bef92045bc975d9e675d24e7`, lokal **1.0.6-local.064a4d9**. Das netzlos gebaute Image `sha256:46149ea3f8e2edb9d90cde83ef2c4fc6664edd8e3a5e50f84bd6c9ec11cd4065` enthält die byteweise geprüften264Paketdateien und112UI-Dateien; die unveränderte Oberfläche wurde nicht erneut gebaut. Ein netzloser Paket-Smoke prüft Zeitgrammatik, erhaltene Umschreibungen, weiterhin verworfene falsche Zeitangabe und unverändertes gemeinsames Schema.

Kalte Sicherung unter `Kingfisher-Rueckweg/2026-10-08-vor-064a4d9`.344Original-IDs/Digests und17SQLite-Dateien erhalten/geprüft; Konten-, Kalender-, Anbieter-, Modellrollen- und Zeitplaneinstellungen erhalten. Gleicher Datenvolume, natives Programm unverändert, Backend gesund und Mailpause weiterhin sichtbar. Persönlicher Import pausiert, produktives Ollama aus, Bedeutungssuche deshalb `unavailable`. Native Fensterprüfung wegen gesperrtem Mac offen. Kein öffentlicher Release/Registry-Upload und keine CI-Wiederholung.
