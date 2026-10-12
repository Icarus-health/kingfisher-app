# Exakte Mailverläufe im großen Bestand

Code `f858681bb5afa0d7fe0482f87ce208c10793c38f`, 11.10.2026. Neue Version noch nicht auf dem persönlichen Mac installiert. Dort läuft weiterhin `1.0.6-preview.a5787c8`; Mailaufnahme bleibt pausiert.

## Problem und Änderung

Der bisherige Aufgaben-Prüfhinweis suchte Headerkennungen durch alle JSON-Dokumente. Ab 50.000 fremden Mails erschöpfte der künstliche Test das gemeinsame SQLite-Arbeitsbudget: Eine vorhandene Antwort blieb ungeprüft. Der bestehende Hinweis behauptete dabei keine vollständige Prüfung.

Migration v22 ergänzt einen abgeleiteten Index für exakte `mail:message:`- und `mail:reply:`-Kennungen. Er enthält keine Mailtexte und keine neue semantische Einordnung. Backfill und Trigger laufen atomar mit der bestehenden Datenbankmigration bzw. den Original-Schreibtransaktionen. Die Kontextsuche prüft weiterhin aktuelle, nicht ausgeschlossene Mailquellen, kontogebundene vollständige Kennungen und dieselben Suchbudgets. Aufgaben, Fristen und bestätigtes Wissen werden nicht automatisch verändert.

## Nachweise

- Regression auf dem unveränderten Stand erwartungsgemäß rot; neuer 50.000-Mails-Fall danach grün.
- Betroffene Suite: 200 Tests bestanden. Separater Lauf mit zusätzlichem Migrations-Abbruchfall, Quellenberechtigungen und Mailzeitlinien: 111 bestanden. Originalspeicherung/Persistenz: 24 bestanden. Die Suiten überschneiden sich; ihre Zahlen sind keine Summe unterschiedlicher Tests. Ein vorhandener Starlette-Testclient-Deprecation-Hinweis bleibt.
- Ein anfänglicher Lauf hatte zwei Fehler durch alte Migrationstest-Fixtures, die fälschlich eine spätere Tabelle enthielten. Die Legacy-Fixtures bilden nun ihre tatsächliche alte Version ab. Das Rohprotokoll bleibt erhalten.
- Derselbe künstliche Bestand mit 125.002 Originalzeilen: v21 → v22 einschließlich Öffnen rund 1,16 Sekunden; exakte Antwort in drei Abfragen rund 0,45–1,06 ms gefunden. Vorher/Nachher-SHA-256 aller Originalzeilen identisch. Das misst nur Header-Metadaten, keine allgemeine Gedächtnisqualität, Mailaufnahme, Modellleistung oder UI-Latenz.
- Fehlende Trigger werden abgewiesen; unterbrochene Migration rollt Schema, Version und Originale zurück, danach erfolgreicher Wiederholungsversuch. Update/DELETE/Rollback der Projektion geprüft.
- Enger unabhängiger statischer Review ohne konkreten Blocker; finale Produktionsdateien entsprechen den Review-Hashes. Anführungszeichenprüfung und `git diff --check` bestanden.

Der Verifier prüft Schema/Trigger, nicht bei jedem Start die gesamte Datenparität. Backfill und zusätzlicher Speicher sind einmalige Migrationskosten. Diese Änderung ist kein Nachweis perfekter inhaltlicher Erinnerung.

## Persönlicher Kalenderstatus

Nach Bestätigung des macOS-Dialogs aktuell per lokalem Backend geprüft: Lesefreigabe erteilt, drei Kalender ausgewählt, Verbindung online, keine Fehler oder Warnungen in der nächsten Siebentagesabfrage; sechs Einträge im angefragten Zeitraum. Kalender-Gedächtnisfreigabe bleibt aus. Das enthält keine persönlichen Termintexte. Der native Fenstertest ist offen, da die Computersteuerung den Mac als gesperrt meldet. Keine Kalenderänderung.

## Wiederholung und Installation

Die Testdateien unter `sidecar/tests/` laufen mit pytest. Die beiden Scale-Treiber verwenden damalige absolute temporäre Pfade; für eine Wiederholung eigene temporäre Pfade und einen frischen v21-Bestand wählen. `scale_after.py` erwartet den unveränderten v21-Bestand des Vorher-Laufs. Keine persönlichen Datenbanken verwenden. Die gespeicherten Ergebnisse sind Nachweise der ausgeführten Läufe.

Vor einer persönlichen Installation: Paket aus dem festgehaltenen Quellstand bauen und prüfen, kalte Datensicherung anlegen, v22 auf einer geschützten lokalen Kopie prüfen, Original-/Kernbestände vergleichen und ausschließlich die erwartete Schemaerweiterung zulassen. Der bisherige Installer setzt unveränderte Schemas voraus und darf für dieses Update nicht ungeprüft wiederverwendet werden. Kein alter v21-Dienst wird auf einer v22-Datenbank gestartet; keine automatische Wiederherstellung überschreibt neuere Nutzerdaten. Noch kein Merge oder öffentlicher Update-Release.
