# Gesicherte Arbeitsweisen und Korrekturen historisch lesen

P5-Anschlussprüfung an die gemeinsame Prüffassung `c8da753`. Nur künstliche Quellen und Schlüssel, keine Cloud-, lokalen Modell- oder persönlichen App-Aufrufe.

## Reproduzierter Befund und Korrektur

Die vollständige Sicherung enthielt `procedures.sqlite3` und `rueckmeldungen.sqlite3` samt Lernprüfergebnissen bereits. Die historische Wiederherstellungsansicht erlaubte den Zugriff darauf jedoch nicht: beide Leseaufrufe lieferten 404, und beide Bereiche fehlten in der Auswahl. Ein unabhängiger Review reproduzierte den Zustand mit einem getrennten Snapshot-Roundtrip.

Die bestehende feste Lese-Allowlist enthält jetzt diese beiden Tabellen. Authentifizierung, reine SQLite-Leseverbindungen, Paging und die Sperre aller regulären Schreib-/Modell-/Aktionsrouten bleiben unverändert. Ein historisch als aktiv gespeicherter Skill ist damit einsehbar, erhält aber keine aktuelle Ausführungsfreigabe.

## Nachweis

Der neue Regressionstest erzeugt durch drei ausdrückliche künstliche Arbeitskorrekturen einen Skill, bestätigt ihn im Ausgangsbestand, erstellt ein verschlüsseltes Wiederherstellungspaket und startet das normale Backend aus der getrennten Wiederherstellung. Vor der Korrektur scheiterte der Test an den fehlenden Datenbereichen. Danach prüft er:

- Herkunft, historischer Aktivstatus, drei Korrekturen sowie gespeicherte positive/negative Lernprüfergebnisse bleiben erhalten.
- Skills und Korrekturen sind über die historische Leseroute erreichbar; ohne Token bleibt der Zugriff gesperrt (401).
- Skillannahme, Lernstart und Zeitplanausführung bleiben gesperrt (423); Zugriff auf Schlüsseldateien bleibt ausgeschlossen (404).
- Der wiederhergestellte App-Start lädt weder Agent noch Schlüsselkonfiguration und führt keinen weiteren Modellaufruf aus.

57 betroffene Backup-/Recovery-/Restore-Tests bestanden in 10,18 Sekunden. Der unabhängige Abschlussreview führte den neuen Test zusätzlich aus und fand keine weiteren Befunde. Die bekannte Starlette/httpx-Warnung bleibt. Keine breite unveränderte Backend-Suite wiederholt.

## Grenzen

Die Cloud-Steuerdatei und das laufende Mistral-Budget bleiben bewusst außerhalb des historischen Pakets. Fachliche Ergebnisse, Herkunft und Lernprüfergebnisse werden bereits in den gesicherten Fach-Stores gehalten; flüchtige Vorschauen werden nicht wiederhergestellt. Historische Kosten dürfen den aktuellen Kostenstand und eine neue Ausgabenfreigabe nicht ersetzen. Die separate Cloud-Jobhistorie wird dabei nicht exportiert.

Das ist **historische Einsicht, keine vollständige Rückkehr in den Arbeitsbetrieb**. Der P5-Plan benennt diese noch fehlende Lieferung jetzt ausdrücklich. Eine pauschale Entfernung der Restore-Schutzmarkierung wäre kein zulässiger Ersatz. Eine erneute native Bedienprüfung steht aus; der vorhandene persönliche Bestand und der pausierte Großimport wurden nicht verändert.
