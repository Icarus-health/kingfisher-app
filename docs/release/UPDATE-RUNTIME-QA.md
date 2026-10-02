# Docker-Update und Rückweg mit befülltem Bestand

Prüfung vom 8. September 2026, getrennte lokale Docker-Instanz auf dem Mac.
Keine Testdaten wurden in das Alltagsvolume geschrieben.

## Versionswechsel

- Ausgangsversion: `sha256:1bd8e31fcece0c0d76ca64cc99168a804511c6a09bae4eecf3f208e7378a9c36`
- Zielversion: `sha256:27c27049c9778dcd11d04fd183bbfbd59284c8001416e89a6235d7fb70803be8`
- Tatsächlich durchlaufen: Ausgangsversion → Zielversion → Ausgangsversion → Zielversion.
- Derselbe eigene Datencontainer-Mount und dieselbe private Konfiguration über alle vier Stufen.
- In jeder Stufe: alle zehn SQLite-Datenbanken lesbar, `integrity_check` erfolgreich, Schema-Versionen erhalten und sämtliche ursprünglichen Datenzeilen wiedergefunden.

## Datenumfang

Echte fachliche Testeinträge in Selbstmodell, Audit, Aufgaben, Arbeitsbereichen,
Episoden, Vorschlägen, Gesprächen, Wissensgraph, Regeln und Mac-Kalender.
Ein bestätigter Claim verweist auf eine Person, ein Projekt und seine Quelle.
Eine Aufgabe ist demselben Projekt zugeordnet. Einstellungen und verschlüsselte
Test-Zugangsdaten gehören zum Bestand.

Der ergänzende Pakettest vergleicht vollständige SQL-Dumps aller Stores,
entschlüsselt den erhaltenen Testzugang und prüft, dass neue Arbeit im
Ausgangsbestand nach einer separaten Wiederherstellung erhalten bleibt.
Der Migrationstest führt den echten Wechsel des alten Aufgabenschemas aus
und stellt dessen gesicherten Vorgänger separat wieder her.

## Browserprüfung

Der abschließende Browserlauf prüft Aufgabe, Registry-Claim und geöffnete
Originalquelle, ursprüngliche Gesprächsnachrichten sowie eine neue echte
Ollama-Antwort mit anschließendem Neuladen. Dabei wurde eine reale Abweichung
gefunden: Mac-Nachrichten (+02:00) und Container-Nachrichten (UTC) wurden als
ISO-Text statt nach Zeitpunkten sortiert. Die Antwort war gespeichert, stand
aber vor älteren Nachrichten. Ein Regressionstest reproduzierte dies.

Die Korrektur sortiert Nachrichten, Gesprächsvorschauen und das zuletzt
verwendete Gespräch nach dem tatsächlichen Zeitpunkt, ohne gespeicherte Texte
oder Zeitstempel umzuschreiben. Mikrosekunden bleiben berücksichtigt.
16 gezielte Gesprächstests bestanden; zusätzlich bestand ein gezielter Test
mit nur 100 Mikrosekunden Abstand. Derselbe Docker-/Browserlauf mit demselben
Bestand bestand anschließend vollständig einschließlich neuer Antwort und
Neuladen. Die Korrektur wurde lokal ausgerollt. Ältere Images enthalten sie
nicht; dieser Befund begrenzt deren visuelle Gesprächsabnahme.
Screenshot im Aufgabenordner: outputs/all-store-update-source.png.

## Reichweite

Diese Prüfung gilt für die oben benannten Versionen und den dokumentierten
Schema-Rückweg. Sie ist keine Zusage, dass beliebige zukünftige Datenformate
mit beliebigen älteren Images kompatibel sind. Bei inkompatiblen Schemata ist
der dokumentierte Weg die separate Wiederherstellung des vor dem Update
gesicherten Bestands mit seiner gespeicherten App-Version. Die neuere Instanz
wird dabei nicht überschrieben.
