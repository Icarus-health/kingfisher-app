# Eingefrorene synthetische Gedächtnisprüfungen

Diese Dateien enthalten ausschließlich erfundene Daten. Originale und Erwartungen
wurden vor der jeweiligen Ausführung getrennt festgelegt. Die Referenzen wurden
von einem unabhängigen KI-Agenten erstellt und vor dem Modelllauf geprüft; sie
sind keine menschlich erstellte Goldreferenz und kein Qualitätsnachweis.

| Satz | Umfang | Verwendung |
|---|---|---|
| `pilot-v1` | Zehn Mails, fünf Fragen | Unveränderter Vorgänger vor dem Referenzreview |
| `pilot-v2` | Dieselben zehn Mails, korrigierte Referenz | Lokaler Versuch am Speicherdruck abgebrochen; Mistral nur offline vorbereitet |
| `heldout-v1` | 100 Mails, zehn native Originale, getrennte Fragen und Zustandsphasen | Unveränderter Vorgänger vor dem Referenzreview; nicht ausgeführt |
| `heldout-v2` | Gleiche Originale, korrigierte Belege und getrennte Bewertungsdimensionen | Maßgeblicher größerer Prüfungssatz; nicht ausgeführt |

Jeder Ordner bleibt unverändert, einschließlich seiner historischen Pfadangaben.
Der in `heldout-v2` genannte ursprüngliche Nachbar `../heldout` liegt hier als
`../heldout-v1`. Absolute temporäre Pfade dokumentieren die ursprüngliche
Erstellung; sie sind keine Installationsanweisung. Der ebenfalls archivierte
Validator und sein Prüfbericht stehen im
[Laufverzeichnis](../../runs/2026-11-04-independent-memory-pilot/README.md).

Vor einer Ausführung sind die Prüfsummen aus `freeze.json` zu prüfen. Nur
`sources.json` und die dort genannten Originaldateien dürfen als Quellen an das
Modell gelangen. Erwartungen, Fragenreferenzen und Bewertungsdimensionen bleiben
außerhalb der Modellanfragen. Ergebnisse werden außerhalb der eingefrorenen
Ordner abgelegt. Die Quellenaufnahme muss für Anlagen den tatsächlichen
Dateiweg benutzen; bereitgestellte Texttranskripte prüfen keine Spracherkennung.

Der bisherige Mailgrader kann nicht alle Aufgaben und Zustandsphasen dieses
Satzes bewerten. Ein neuer Ausführungsadapter und eine semantische Auswertung
sind vor der großen Prüfung noch erforderlich. Die Existenz dieser Dateien
schaltet weder Cloudverarbeitung noch Großimport frei.
