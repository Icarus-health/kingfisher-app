# Kingfisher 1.0.3 ausgeliefert · 7. Oktober 2026

## Veröffentlichung

- PR #3 gemergt: https://github.com/Icarus-health/kingfisher-app/pull/3
- Release-Commit/Tag: `e533913332a4207530dddc61a396432ea0579838`, `v1.0.3`.
- Einmaliger Release-Workflow vollständig erfolgreich: https://github.com/Icarus-health/kingfisher-app/actions/runs/37592603576
- Öffentliches Docker-Bild enthält `linux/arm64` und `linux/amd64`; Mac-Download ist universell (`arm64`, `x86_64`).
- Release: https://github.com/Icarus-health/kingfisher-app/releases/tag/v1.0.3
- Öffentlicher Updatekanal liefert `fassung: 1.0.3` und das passende Bild/DMG.
- DMG SHA-256: `06cbb1311074c41cb5848ffae6b5f50bba102d54e8f94ead0349c1e997a2f676`; heruntergeladene Datei stimmt überein, DMG-Integrität und ad hoc Codesign-Prüfung erfolgreich. Nicht notarisiert, entsprechend dem bestehenden Releaseverfahren.

## Prüfungen und tatsächliche Installation

- Zusätzliche Release-/Manifest-/Compose-/Updater-/Mac-Prüfungen: **112 bestanden, 1 übersprungen**. Der erste Sandbox-Lauf scheiterte an gesperrten lokalen Testsockets und Swift-Zugriff; derselbe Satz bestand mit dem benötigten lokalen Zugriff. Keine Produktänderung zur Umgehung der Tests.
- Vorheriger Funktionsnachweis: 76 betroffene Backendtests; 284 UI-Tests plus Typecheck/Build; unabhängige Gegenprüfung. Kein erneuter kompletter Backendlauf nur für Versionsnummer/Release-Notizen.
- Vor dem Wechsel konsistenter Kingfisher-Snapshot angelegt und zusätzlich auf den Mac kopiert; bestehende ältere Sicherungen und lokale Starterkonfiguration separat erhalten. Alle 14 Snapshot-Datenbanken mit `quick_check: ok`.
- Im realen nativen Fenster: „Jetzt nachsehen“ fand 1.0.3; „Jetzt aktualisieren“ sicherte/lud/startete neu; anschließend sichtbar „Kingfisher ist jetzt auf Fassung 1.0.3.“ Laufendes Bild `ghcr.io/icarus-health/kingfisher-app:1.0.3`, gleicher Datenvolume-Name `kingfisher_kingfisher-data`.
- Vergleich der Zeilenprüfsummen: alle 258 vorhandenen Original-Episoden und beide Gespräche/sechs Nachrichten unverändert erhalten. Vorhandene Assertions, Claims, Aufgaben, Projekte und Notizen waren in dieser Installation leer und blieben bei der Prüfung leer; daraus folgt kein Nachweis einer gelungenen fachlichen Erkennung.
- Zugangseinstellungen identisch, nur `KINGFISHER_IMAGE` auf 1.0.3 geändert. Kein Reset und keine neue Cloud-Freigabe.
- Live-Datenbanken nach Migration: 15 mal `quick_check: ok`; Episodenschema auf Version 18. Neue `recovery-status.sqlite3` erklärt die zusätzliche Datei.
- Zusätzlich nativen Starter von 1.0.1 auf 1.0.3 am bisherigen Installationsort ersetzt; alte App als Rückfallkopie erhalten, Codesign geprüft, tatsächlicher Neustart zur Heute-Seite erfolgreich. Keine Änderung der separat gespeicherten Daten/Zugänge.
- Vorhandener Posteingang lädt; lokaler Originalauszug-Überblick an einer echten Nachricht im nativen Fenster sichtbar. Keine Aufgabe gespeichert, keine Mail gesendet. Testbeispiele und private Rohdaten/Backups nicht im Repository.

## Speicher und offene Qualitätsgrenzen

Die Fehlermeldung beim früheren „Jetzt nachsehen“ kam von `ENOSPC` beim Speichern des Prüfstatus. Dockers 59-GiB-Datenplatte war voll, während der Mac ausreichend freie Kapazität hatte. Ausschließlich nachweislich unbenutzte Kingfisher-Testimages/Zwischenbuilds auf dem Mac archiviert und geprüft, dann ohne Zwang aus Docker entfernt; keine Container/Datenvolumes pauschal bereinigt. Vor dem Download rund 2,7 GiB Docker-Reserve. Nach der ersten Bereinigung funktionierte der Updateknopf bereits wieder. Alte lokale Buildstufen sollten künftig nach Prüfung entfernt werden, statt dauerhaft anzuwachsen.

Bei einer echten Newsletter-Mail lieferte das lokale Modell zwar wörtliche Originalauszüge, aber zu großzügige Aufgabentitel ohne klare Bitte/Zusage. Das bleibt ein **offener fachlicher Qualitätsbefund**: Quellengleichheit ist keine Bestätigung, dass ein Vorschlag sinnvoll oder vollständig belegt ist. Keine automatische Speicherung/Ausführung; nächste Verbesserung muss solche Negativfälle samt Prüfung nicht genannter Zusätze abdecken. Dieses Release ist kein Fehlerfreiheitsnachweis.

Die Heute-Seite meldet weiterhin „Kalender ist nicht verbunden.“ Der allgemeine Quellenhinweis war schon vor dem Update sichtbar; die Installation richtet keine neuen Kalenderzugänge ein. Mistral/OpenRouter sind nur dokumentiert vorbereitet und bleiben ausgeschaltet.
