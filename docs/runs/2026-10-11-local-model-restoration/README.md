# Gewähltes Einordnungsmodell wiederhergestellt, 11. Oktober 2026

Das bereits gewählte `kingfisher-qwen3.5:9b-32k` ist wieder vollständig lokal vorhanden. Der Acht-Fälle-Katalog ergibt **4/8 genaue Sollmengen**, nicht eine Freigabe für die große persönliche Erstaufbereitung. Keine Cloudinferenz, persönlichen Quellen oder Rollenänderung; große Mailaufnahme weiterhin global pausiert.

## Wiederherstellung

Vorheriger Befund: [fehlende Gewichte und 4B-Vergleich](../2026-10-11-live-category-quality/README.md). Vor Start 21.995.520.000 Bytes frei, Stromversorgung aktiv. Vorhandener Ollama-CLI-Dienst 0.35.1 temporär, Cloud aus, kein Pruning, ein Modell/eine Anfrage, 15 Sekunden Verweildauer.

Nur die Basis `qwen3.5:9b` nachgeladen: [Pull-Ergebnis](pull-result.json), 6.550.825.550 Bytes gemeldete Dateien, Erfolg nach etwa 346 Sekunden. Freier Platz wurde während der Streamereignisse geprüft; Abbruchschwelle 10 GiB, keine harte Speicherquote. Nach Wiederherstellung 15.457.169.408 Bytes frei. Keine vorhandenen Images, Volumes, Originale oder anderen Modelle gelöscht. Docker hat keinen Buildcache zum Freigeben; unbenutzte Images/Volumes sind kein hier freigegebener Löschauftrag.

[Profilnachweis](profile-restoration.json): sechs alte Basisreferenzen frisch vollständig nach Größe und SHA-256 geprüft; vom Registry-Pull gelieferte Referenzen entsprechen dem alten Manifest. Fehlender 81-Byte-Profilparameter ist Basisparameter plus `num_ctx=32768`, mit exakt altem SHA-256. Erster Vorab-Abgleich ohne JSON-Zeilenabschluss stoppte vor jeder Profilmutation; vorhandene Basisdatei belegte den Zeilenabschluss, danach exakter Digesttreffer.

Der Parameterbaustein wurde über [Ollamas lokale Create-API](https://docs.ollama.com/api/create) unter einem einmaligen temporären Namen erstellt. Der bestehende ausgewählte Name wurde nicht überschrieben; seine Manifestdatei blieb bytegenau unverändert. Temporärer Name anschließend über die lokale API entfernt. Der ursprüngliche Name referenziert nun wieder alle vorhandenen Dateien. `/api/show` bestätigte GGUF und genau `num_ctx 32768`. Der ausgeführte Prüfer kontrollierte sowohl `remote_model` als auch `remote_host`; im JSON ist nur `remote_model_present` ausdrücklich gespeichert. Das belegt die gespeicherte Einstellung, nicht die Qualität bei ausgeschöpftem Kontext. Unabhängiger Review hatte vor der Ausführung ein konkurrierendes Profilüberschreiben und unvollständige Rollbackpfade des ersten Ansatzes erkannt; die temporäre Neuanlage vermeidet die Mutation des ausgewählten Profils vollständig.

Das gewählte Gemma-12B-Antwortmodell fehlt weiterhin. Kein weiteres Modell bei diesem freien SSD-Platz blind nachgeladen. App-Paket, Einwilligungen und gespeicherte Rollenwahl wurden nicht verändert.

## Echte Kategorienprobe und Ursachenabgrenzung

[Unveränderter Produktionsläufer](../../../scripts/probe_category_quality.py): acht tatsächliche Modellaufrufe, acht ausgewertete Fälle in 37,795 Sekunden, Exit 1: [qwen9b-quality.json](qwen9b-quality.json). Derselbe Katalog und Kategoriencode wie beim 4B-Lauf, keine Sollwerte oder Prompts geändert.

| Fall | Tatsächliches Ergebnis |
|---|---|
| Werbung | Keine Kategorie statt Information |
| Automatische Statusmeldung | Keine Kategorie statt Information |
| Projektauftrag | Arbeit und genaue Person: Soll erfüllt |
| Newsletter mit persönlichem Auftrag | Information und Arbeit, genaue Person: Soll erfüllt |
| Rechnung | Keine Kategorie statt Finanzen |
| Buchungsbestätigung | Termine/Buchungen: Soll erfüllt |
| Bedingter Projektbericht | Arbeit und genaue Person, zusätzlich Termine |
| Historische Absage | Arbeit: Soll erfüllt |

Alle ausdrücklich erwarteten Personen erkannt; alle acht Originale erhalten, kein Belegvalidierungsfehler. Einzelner kleiner Lauf, kein verlässlicher allgemeiner Modellvergleich und keine persönliche Fehlerquote. Aufgaben, Bedingungen, Fristen, Identitätsauflösung und Antworten sind weiterhin außerhalb dieser Messung. Auch ein weiteres Thema ist zunächst ein Vorschlag und beweist keine erfundene Aufgabe oder Buchung.

Vier abweichende Fälle zur Ursachenabgrenzung separat wiederholt: [deviation-trace.json](deviation-trace.json). Ausschließlich künstliche Modellantworten. Die leeren Kategorien kommen bereits als `categories: []` vom Modell; die Produktionsvalidierung entfernt keine vorhandenen Themen. Der bedingte Bericht enthält schon in der Antwort beide Kategorien. Nachträglich ergänzte Herkunftsmetadaten markieren ausdrücklich ihre Erfassung nach dem Lauf: Modellkennung aus dem ausgeführten Treiber, Treiber-/Katalog-/Produktcode-Hash, keine neue Inferenz oder nachträglich behauptete In-run-Erfassung. Identische beobachtete Abweichungen in dieser Wiederholung; kein Promptwechsel oder stiller Auswahlwechsel zwischen Durchläufen. Nächster Schritt ist eine kontrollierte Verbesserung der Themenzuordnung, mit neuen unabhängigen Gegenfällen und erhaltener Personenerkennung, bevor große Aufnahme weiterläuft.

## Abschluss

Der temporäre Testdaemon ist mit Exit 0 beendet; zuvor `/api/ps` ohne geladene Modelle. Keine dauerhaft laufende KI durch diesen Schritt eingerichtet. Die Modelldateien bleiben auf dem Mac; für spätere Benutzung muss Ollama laufen. Sieben persönliche Kerntabellen frisch vollständig gegenüber dem vorherigen Prüfstand lesend verglichen, alle unverändert. Diese Host-/Tabellenbelege stammen aus den Terminalabschlüssen und separat privat gespeicherten Vor-/Nachsnapshots, nicht aus den vier Modellberichten. Keine privaten Zeilen oder Prüfsummen veröffentlicht. Der unabhängige Review prüfte Zahlen, künstliche Antworten und Bereichsgrenzen, nicht die persönlichen Hostdaten. Keine Produkt-/Läuferänderung und deshalb kein wiederholter Testbestand als neue Evidenz ausgegeben. Kein App-Update oder Release, kein CI-Neustart, kein Merge nach main.
