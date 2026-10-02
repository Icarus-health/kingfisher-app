# Entscheidungen und Grundlagen — 2026-09-07

## Ablauf

Die Aufgabenansicht enthält Entscheidungen, wahlweise für ein ausgewähltes Projekt. Eine Entscheidung wird ausdrücklich mit Text und optional ausgewählten Grundlagen gespeichert. Verwendbar sind aktuelle Aussagen des Selbstmodells und bestätigtes Entitätswissen. Offene Vorschläge sind keine auswählbaren Grundlagen.

Entscheidungen verweisen auf Originalkennungen: bestehendes `derived_from` für Aussagen und `structured.claim_ids` für Claims. Texte werden nicht als zusätzliche Wissensaussagen ins Selbstmodell kopiert. Eine reine Leseprojektion wertet Claimzustand, Abhängigkeiten und Änderungszeiten des vorhandenen Wissensjournals aus. Verknüpfungen zu Grundlagen und Projekt sind auch im Graphen vorhanden.

Nach einer Korrektur bleibt die Entscheidung historisch erhalten und wird zur Prüfung angezeigt. Der Tagesüberblick verlinkt zur Entscheidungsansicht. Erst die ausdrückliche zweistufige Rücknahme ändert den Entscheidungsstatus. Bereits entfernte oder ersetzte Entscheidungen lassen sich nicht über diesen Weg reaktivieren.

## Nachweise

- Vollständige Backendtestsuite: **790 passed**, 123,37 Sekunden; eine bestehende Starlette/httpx-Abkündigungswarnung.
- Ergänzende Persistenzprüfung mit neu geöffneten SQLite-Verbindungen: identische Entscheidung inklusive widerrufener Claimgrundlage; gezielter Test erneut grün.
- Nachweis: ungeprüfter Vorschlag nicht auswählbar; bestätigter Claim auswählbar; keine Kopie im Selbstmodell; Widerruf erschüttert Entscheidung; Journalzeit begrenzt Morgenhinweis auf 30 Tage; historische Ansicht bleibt erhalten; veraltete/fehlende Grundlage wird beim Speichern abgewiesen.
- TypeScript/Vite im Dockerbuild erfolgreich. Assetmanifest unverändert gültig: 14 Dateien, 17 Icons.
- Vollständiger Browserablauf gegen isoliertes fertiges Docker-Image: Entscheidung mit Grundlage speichern, neu laden, Grundlage widerrufen, Hinweis unter Heute öffnen, Prüfzustand sehen, Rücknahme bestätigen, erhaltene Historie nach Neuladen prüfen. Keine JavaScript-Seitenfehler.
- Browser plugin not available; reguläres Playwright. Screenshot im lokalen Aufgabenordner: outputs/decision-changed-desktop.png. Nur synthetische Daten im temporären Testcontainer; keine echten Nutzeraussagen erzeugt oder zurückgenommen.
- Zusätzliche unabhängige Codeprüfung der Entscheidungskarten und Backend-Verknüpfung ohne weitere materielle Befunde.

## Grenzen der Abnahme

Die Inline-Ansicht verwendet vorhandene Aufgaben-/Formulargestaltung, ohne neue Sidebar oder Assets. Es existiert keine separate kanonisch freigegebene Entscheidungsansicht; vollständige visuelle Abnahme bleibt offen. Der große gemeinsame CoS-Prüfpunkt umfasst zusätzlich Zusagen, Terminvorbereitung und weitere Bedienabläufe und ist dadurch nicht vollständig geschlossen.
