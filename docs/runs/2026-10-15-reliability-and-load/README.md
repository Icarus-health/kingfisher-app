# Zuordnung und Hintergrundlast – 15. Oktober 2026

## Umfang

Qwen9B und BGE-M3 bleiben erhalten. Automatische Vorschläge bekommen zusätzliche lokale Belegprüfungen; die ursprünglichen Quellen und ausdrücklich bestätigten Aufgaben werden nicht umgeschrieben. Kein Cloudzugang, kein Wiederanlauf des pausierten Großimports und kein Modellwechsel.

- Aufgaben: Daten, Zahlen/Beträge, Mailadressen, relative Tagesangaben und mehrteilige Namensfolgen im Titel müssen zur eigenen Originalstelle passen. Die Bedeutungs- und Zuständigkeitsprüfung des Modells bleibt notwendig. Die Regel gilt auch bei der Extraktion aus anderen Quellen. Alte positive Modellprüfungen umgehen die neuen Regeln beim Anzeigen nicht; fragliche Vorschläge bleiben sichtbar und prüfpflichtig.
- Menschen: Firmen mit den bereits bekannten Rechtsformen und allgemeine Servicebezeichnungen sind keine automatisch belegten Personen. Die Prüfung greift auch in der lesenden Kategorienansicht. Es werden keine Personenidentitäten vereinigt.
- Zahlungsfristen: Ein Rechnungs- oder Leistungsdatum reicht nicht als Fälligkeit. Klare Zahlungsformulierungen bleiben unterstützt; Alternativen und Bedingungen bleiben zur Prüfung im Original. Historische Zeitbezüge und der bestehende Bestätigungsschritt bleiben erhalten.
- Hintergrund: Der authentifizierte native Bericht enthält Speicherdruck aus macOS. Warnung, kritisch und unbekannt sperren automatische Modellarbeit, ebenso fehlende/veraltete erforderliche Berichte. Ein Abschnittsversuch pro automatischem Klassifikationspaket, einschließlich fehlerhafter Antworten; anschließend ein Arbeit/Pause-Ziel von 20/80. Verdiente Pause bleibt nach Wecksignalen, Unterbrechung und Neustart desselben Schedulers erhalten. Fertige Abschnitte bleiben bei einer Pause im vorhandenen begrenzten Zwischenspeicher.

Native App und Dienst müssen gemeinsam aktualisiert werden. Ein alter reiner Energiebericht bleibt gültiges Eingabeformat, autorisiert aber keine automatische Mac-Modellarbeit. Nicht-Mac-Installationen ohne erforderlichen Hostbericht bleiben unverändert.

## Nachweise und Grenzen

Die ersten neuen Belegfälle reproduzierten vor der Korrektur 21 Fehler bei 28 Tests. Weitere Reviewfälle zeigten zu strenge gültige Titel, Datumszuordnungen sowie Pausen- und Fehlerbudgetlücken; alle wurden vor der Auslieferung mit eigenen Gegenbeispielen korrigiert. Das unabhängige abschließende Review meldete keine offenen Befunde.

Gezielte fachliche Regression: 325 bestanden. Finale Ressourcenregression: 105 bestanden, ein Linux-spezifischer Test auf macOS übersprungen. Oberfläche: 741 bestanden, Produktionsbuild und Asset-Vertrag bestanden. Die umfassende Backendprüfung und die Installation werden separat abgeschlossen und dokumentiert.

[Die echte lokale Qwen-Probe](live-qwen.json) nutzte `OpenAICompatible` und die bestehende 32K-Modellkonfiguration ohne Transportänderung, nur künstliche Daten. Der erste ausdrückliche Auftrag wurde korrekt erhalten (8,7 Sekunden). Anschließend brach die Probe **vor dem zweiten Aufruf** wegen erhöhten Speicherdrucks ab und entlud nur ihr eigenes Modell. Sechs Ressourcenmesspunkte enthielten normale, Warn- und kritische Stufen. Das ist **keine abgeschlossene Modell-Qualitätsabnahme** und kein Nachweis dauerhaft flüssiger Bedienung. Weitere Inferenz wurde nicht erzwungen.

Die Hintergrundregeln begrenzen Start und Takt, nicht den RAM-Spitzenbedarf eines einzelnen laufenden Modellaufrufs. Ein bereits laufender Aufruf darf fertig werden. Der native Bericht wird alle 30 Sekunden erneuert und nach 90 Sekunden ungültig. Die 20 Prozent sind ein Taktziel für automatische Pakete, kein Betriebssystem-CPU-Limit und keine Messung der Batterielaufzeit.

Die Zusatzprüfung kann keine fehlerfreie sprachliche Extraktion garantieren: einzelne Namen und Bedeutung/Zuständigkeit brauchen weiterhin Modellprüfung und Nutzerbestätigung. Keine Sprachregel ersetzt den Originalbeleg.
