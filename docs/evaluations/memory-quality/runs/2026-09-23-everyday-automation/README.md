# Alltagssuche und bedienbare lokale Einordnung

Dieses Paket verbessert Quellenabruf und Bedienung auf dem bestehenden Gedächtnis. Es ist **keine Abnahme einer fertigen CoS-V1**. Alle hier verwendeten Testquellen sind erfunden. Keine privaten Quellen, neuen Modelle, Cloudanfragen oder Mailzustellungen wurden für die Modellprüfung verwendet.

## Verhalten

- Deutsche Komposita wie „Prüftermin“ können beim Abruf nach „Termin“ zusätzliche Kandidaten liefern. Der begrenzte, abgeleitete Index bevorzugt wörtliche Treffer. Das ist weder allgemeine Bedeutungsähnlichkeit noch eine Personenauflösung; keine neue Faktenablage.
- Die Auswahl sieht beim Schutz vor gleichnamigen Absendern auch übergangene Kandidaten. Namen im Nachrichtentext allein beweisen keine Identität. Für verschiedene Projektkontexte gibt es eine eigene Rückfrage.
- Konkrete Terminfragen innerhalb einer Vorbereitung bleiben quellengebunden. Eindeutige Uhrzeitfenster sind im Auswahlauftrag von offenen relativen Daten unterschieden; das garantiert noch keine richtige Modellentscheidung.
- Das alte direkte `merken`-Werkzeug wird Gesprächsmodellen nicht mehr angeboten und ein dennoch erfundener Aufruf wird abgelehnt. Gewöhnliche Äußerungen bleiben unveränderte Gesprächsquellen. Explizite Merkbitten behalten den separaten Vorschlagspfad. Der bestehende direkte Werkzeugaufruf außerhalb einer Gesprächsrunde ist nicht geändert.
- „Verarbeitung & Verlauf“ bietet lokale Aktivierung und Pause mit sichtbarem Umfang. Aktivierung verändert keine Quellen-/Kontofreigaben. Vorhandene Quellen werden in kleinen Portionen weiter eingeordnet, ohne bei jeder Portion Mailabruf oder Sicherung erneut auszuführen. Neue Uploads behalten Vorrang.
- Der lokale Automatikweg prüft vor jeder Inhaltsanfrage tatsächliche installierte Ollama-Gewichte, statt `localhost` allein zu vertrauen. Cloudweiterleitung, unbekannte Modelle, geänderte Gewichte, Proxy/Redirect und geänderte Zustimmung werden zurückgewiesen. Antworten laufender Anfragen werden nach Pause verworfen. Das setzt einen vertrauenswürdigen lokalen Ollama-Dienst voraus; es ist keine Attestierung gegen einen manipulierten lokalen Server.
- Unterstützt ist der bestehende direkte Ollama-Anbieter. Andere lokale Server und Router werden in diesem Aktivierungsweg nicht ungeprüft freigegeben. Bereits separat aktivierte Mailfilter bleiben separat freigegeben, sind bei gewähltem Lokalmodus ebenfalls lokal geschützt.

## Unabhängige synthetische Modellprüfung

Die unveränderten Quellen und Fragen stehen in `synthetic-cases.json` (SHA256 `f89c894605b068adb6abb47c7d6b8c10283dbc4b8543ed66cbc8e2c2edad8f68`). Die JSON-Dateien enthalten kompakte Originalergebnisse; vollständige HTTP-/Modellspuren bleiben als lokale Prüfartefakte erhalten, ihre Hashes sind enthalten. Ergebnisse werden nicht überschrieben.

Auf sauberem `ed19d91` wurden sieben Fälle mit dem vorhandenen `qwen3.5:4b` geprüft. Korrigierter Termin, unbekannter relativer Freitag, Quellenentzug und der gemeinsame Ablauf aus Tagesübersicht/Terminvorbereitung/Antwortentwurf bestanden ihre Kriterien. Bei der Anrufpräferenz wurde die richtige Quelle gefunden, aber unnötig nach ihrem Datum gefragt. Bei zwei Bedingungen wurde eine relevante Quelle übergangen. Beim gleichen Namen wurden beide Projektquellen gezeigt, aber die erwartete Klärung nicht richtig gewählt.

Ein einziger Vergleich von fünf dieser Fälle mit dem bereits installierten `qwen2.5:14b` auf demselben Quellstand fand beide Bedingungen. Die unnötige Zeitrückfrage und die nicht geklärte Projektzuordnung blieben bestehen. Das ist ein begrenzter Befund, keine allgemeine Modellrangliste und kein Anlass für einen automatischen Modellwechsel.

Ein gezielter Nachlauf von Anrufpräferenz und relativer Datums-Gegenprobe auf sauberem `7ec5b85` zeigte: Die zusätzliche Uhrzeit-Anweisung beseitigt die unnötige Rückfrage beim 4b-Modell nicht. Der unklare Freitag bleibt sicher als unklar ausgewiesen. Kein Nachoptimieren der eingefrorenen Bewertung und keine Wiederholungen bis zu einem günstigen Ergebnis.

**Grenzen der Testauslegung:** Der Vergleichsharness begrenzte Chat auf eine Werkzeugrunde (`max_rounds=1`). „Ich komme hier nicht weiter“ beweist dort keine wiederholte Produktionsschleife. Die erste C1-Spur belegt allerdings einen erfolgreichen direkten `merken`-Schreibaufruf; dagegen bestehen jetzt strukturelle Regressionstests. Der Variantenlauf mit Projektquellen verknüpfte Aufgaben mit Projekten, die Episoden selbst hatten weiterhin `project_id=null`. Das wird nicht als erfolgreiche strukturierte Personen-/Projektauflösung gezählt. Alte Fehlerläufe des Harness bleiben erhalten und zählen nicht als bestandene Prüfungen. Ein Neustarttest mit neu erzeugten Objekten ersetzt keinen Betriebssystem-/Prozessneustart.

Ein separater einmaliger C1-Lauf mit vier Modellrunden auf `7ec5b85` erfasste auch Werkzeugaufrufe. Dort gab es keinen Werkzeugaufruf und keinen Runden-Fallback; das Modell fragte jedoch unnötig, ob die Aussage gespeichert werden solle. Der spätere Abruf zeigte wieder die unnötige Datumsrückfrage. Diese beiden Bedienprobleme sind nicht als behoben ausgewiesen.

## Verifikation

- Vorstufe `ed19d91`: 2375 Tests und 4 Untertests bestanden.
- Nachfolgende Korrekturen an Gesprächswerkzeugen, Routing und Uhrzeit-Anweisung `7ec5b85`: 122 betroffene Tests bestanden.
- Lokaler Modell-Guard: positive Prüfung beider bereits installierten Textmodelle anhand ihrer Metadaten; keine Quelle im Prüfschritt. Gezielte Gegenproben gegen Cloudalias, fehlende Metadaten, Redirect, Proxyübernahme, Modellwechsel und Pause.
- Browser: Aktivieren, Verarbeitung zweier synthetischer Quellen, erhaltener Zustand nach Neuladen, Pausieren, abgelehnte Aktivierung nach synthetischem Cloudwechsel und Weiterleitung zur bestehenden Modelleinrichtung geprüft. Kein echter Cloudaufruf.
- Zusammengeführter Code `5929067`: 2421 reguläre Prüfungen bestanden. Vier Kalender-Untertests scheiterten ausschließlich am noch nicht gebauten Mac-Helfer im neuen Worktree; nach dessen unverändertem Build bestand der isolierte Nachlauf (1 Test, 4 Untertests). Keine Codeänderung und keine unnötige Wiederholung der gesamten Suite. Zwei bestehende Abhängigkeitswarnungen.
- UI-Build, Typprüfung und Assetvertrag (14 Dateien, 17 Icons) bestanden. Finaler synthetischer Browsernachlauf bestätigte fehlendes Modell sowie Aktivierung und Pause auf `5929067`.
- Auslieferung erfolgt erst nach Review und Übernahme. Private Modellverarbeitung bleibt ohne die noch ausstehende Freigabe ausgeschaltet.

## Offen

Allgemeine semantische Paraphrasensuche ohne Wortüberschneidung, belastbare freie Personen-/Projektauflösung, hilfreiche statt unnötige Rückfragen und die breitere unabhängige Alltagsabnahme bleiben offen. Diese Entwicklungsszenarien sind keine repräsentative Erfolgsquote. Die bisherigen UI-Abläufe werden gezielt verbessert; eine vollständige gemeinsame UI/UX-Überarbeitung ist damit nicht behauptet.
