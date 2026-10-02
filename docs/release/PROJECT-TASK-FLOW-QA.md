# Projekte, Aufgaben und Tagesüberblick — 2026-09-07

## Nutzbarer Ablauf

Unter Aufgaben können Projekte angelegt, ausgewählt, pausiert, abgeschlossen und wieder aktiviert werden. Neue Aufgaben übernehmen die ausgewählte Projektzuordnung; bestehende Aufgaben lassen sich zuordnen oder wieder lösen. Die drei Aufgabenansichten filtern serverseitig nach Projekt und behalten ihren echten Offen-/Warte-/Erledigt-Status. Projektabschluss löscht keine Aufgaben und erledigt sie nicht automatisch.

Der Tagesüberblick ergänzt bei Aufgabenmeldungen den vorhandenen Projektnamen und führt zur passenden Aufgabenansicht. Die kanonische bestehende Aufgabenroute ist `/vorhaben`; `/tasks` bleibt die ältere JSON-API. Die browserfähigen Projekt-APIs verwenden `/api/v1/projects` und damit die vorhandene HttpOnly-Sitzung.

## Nachweise

- 65 gezielte Backendtests erfolgreich: project_task_flow, workspace, kingfisher, container und conversation_actions.
- Neue Prüfung deckt Zuordnung, Entfernen, ungültige Kennung, Wartestatus, Projektabschluss, echte neue SQLite-Verbindungen und Projektkontext im Morgen ab.
- TypeScript/Vite-Build und Assetmanifest (14 Dateien, 17 Icons) erfolgreich.
- Isolierter echter Chromium-Browser: Projekt und Aufgabe anlegen, ausgewählte Zuordnung übernehmen, Projekt schließen ohne Aufgabenverlust, Aufgabe erledigen/wieder öffnen, Zuordnung entfernen/wieder setzen, vom Tagesüberblick zurück zur Aufgabenansicht. Keine JavaScript-Seitenfehler.
- Derselbe vollständige Browserablauf zusätzlich gegen das fertige Docker-Image mit temporärem Datenvolume erfolgreich. Danach lokale App auf 8891 aktualisiert und Projektkontrollen sowie Kalender geprüft.
- Testdaten ausschließlich im temporären Teststore, keine Nutzerdaten verändert. Browser plugin not available; reguläres Playwright.
- Screenshots im lokalen Aufgabenordner: outputs/project-tasks-desktop.png und project-tasks-mobile.png. Desktop visuell geprüft. Die bestehende feste Desktopbreite schneidet bei 390 px ab; mobile Abnahme bleibt offen und ist keine erreichte Eigenschaft.
- Zusätzliche Codeprüfung fand eine veraltete Projektabfrage, die neuere Ergebnisse überschreiben konnte; Antwortversionierung ergänzt.

## Referenz und verbleibender Umfang

Projektbezug war in Screen 08 vorgesehen und in SDR-008 mangels nutzbarer Zuordnung ausgespart. Die Zuordnung ist jetzt real. Die zusätzlichen Inline-Projektkontrollen verwenden die bestehenden Formen und Materialien; eine separate pixelgenaue Referenz für Projektverwaltung liegt nicht vor. Kein neuer Navigationspunkt und keine neuen Assets.

Entscheidungen mit Annahmen, projektbezogene Notizbedienung, Prioritäten und eine vollständige gemeinsame CoS-Abnahme bleiben offen. Der kombinierte Roadmap-Prüfpunkt 12 ist nicht abgeschlossen.

## Projektakte: Entscheidungen und Aufgabenquellen

Am 7. September 2026 wurde die falsche Zuordnung im Projektprofil behoben: Der Entscheidungsreiter verwendet nun gespeicherte Entscheidungen des konkreten Projekts statt Wissensaussagen. Der vorhandene Entscheidungsablauf bietet Erfassung, Grundlagen und Rücknahme. Die Übersicht bezeichnet Claims korrekt als bestätigten Wissensstand. Aufgaben führen zur passenden Projekt-/Statusliste und öffnen vorhandene gespeicherte Episodenquellen direkt.

Isolierter Playwright-Lauf mit zwei synthetischen Projekten bestanden: nur eigene Entscheidungen angezeigt; neue Entscheidung im richtigen Projekt gespeichert und nach Reload sichtbar; Aufgabenquelle geöffnet; Navigation zur passenden Aufgabenliste. Keine Browserfehler. Screenshot visuell geprüft, TypeScript/Vite-Build und Assetmanifest bestanden. Keine Änderungen an Nutzerdaten im Test.

Profilquellen: Personeninteraktionen sowie Projektnotizen und ausdrücklich zugeordnete Projektepisoden lassen sich im Profil öffnen. Gemeinsamer Klartextleser mit Herkunft, Ignoriert-Hinweis, Lade-/Fehlerzustand und begrenzter Anzeige (20.000 Zeichen). Isolierter Browserlauf für eine explizite Projektquelle: Öffnen/Schließen und inertes HTML im Quelltext bestanden; Screenshot geprüft. TypeScript/Vite- und Docker-Build bestanden. Aufgabenquellen bleiben unabhängig über die Aufgabe erreichbar.
