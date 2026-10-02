# Profilbedienung: Abnahme zu Punkt 07

13. September 2026. Ergänzung zu den bestehenden Graph-, Profilverwaltungs- und
CoS-Nachweisen. Gezählt wird die Bedienbarkeit belegter Personen-/Projektakten,
keine vollständige Qualifikation der Gedächtnisintelligenz.

## Prüfungen

- Echte freigegebene Maildaten aus einer lokalen Sicherung wurden in eine
  getrennte Instanz kopiert, ohne Kontoeinstellungen, Schlüssel oder laufende
  Synchronisierung. 86 Personen- und eine Projektakte antworteten über ihre
  passenden APIs ohne Fehler. Die vorhandene Projektakte ist ein früherer
  Integrationstest und wird ausdrücklich nicht als echtes Kundenprojekt gewertet.
- Eine echte Personenakte wurde über Namenssuche geöffnet; Gesprächsreiter und
  Originalinhalt einer gespeicherten E-Mail wurden geöffnet. Private Aufnahmen
  bleiben außerhalb des Repositories. Kein künstlicher Kundenbezug wurde ergänzt.
- Ein separater synthetischer Bestand prüft zwei gleichnamige explizite Personen,
  eine Person mit zwei aktiven Projektbeziehungen und die Gegenseite im Projekt.
  Originalbeleg und Verbindungslink öffnen; die andere gleichnamige Person
  bekommt keine fremden Aussagen. Diese Daten gelangen nicht in die Nutzerinstanz.
- Suche mit mehreren Begriffen, kein Treffer/Zurücksetzen, 25er-Seiten, Öffnen
  per Tastatur sowie API-Ausfall/Wiederholen im Chromium-Browser geprüft.
  Der simulierte Netzfehler erzeugt den erwarteten Konsolenfehler.
- Desktopvergleich 1521 × 1034 gegen Screens 05–07; Verzeichnis zusätzlich bei
  800 × 900 ohne horizontales Überlaufen geprüft. Vollständiger Mobilumfang
  wird nicht behauptet. Begrenzte Freigabe: SDR-013.
- Bestehende Prüfungen für Projektaufgaben, Entscheidungen, Dokumente,
  zeitliche Beziehungen und Historie gelten weiter; siehe ACCEPTANCE-COS.md,
  VISUAL-CHECK-profile-management-v1.md und Graph-/Kontexttests.
- Vollständige lokale Suite: 1.340 Tests bestanden, zwei bekannte
  Starlette/httpx/anyio-Abkündigungswarnungen. TypeScript/Vite und Assetvertrag
  (14 Dateien, 17 Icons) bestanden. Keine Änderung am Datenbankschema.

## Visuelle Belege mit ausschließlich synthetischen Daten

[Verzeichnis](../visual-checks/profiles-v2/list.png),
[Person mit zwei Beziehungen](../visual-checks/profiles-v2/person.png),
[Projekt](../visual-checks/profiles-v2/project.png),
[kleineres Fenster](../visual-checks/profiles-v2/small.png).

## Auslieferungsprüfung

- Getrennter Docker-Container auf 8896 mit eigenem synthetischen Volume:
  Verzeichnis → getrennte gleichnamige Akten → Originalbeleg → Projekt → Person
  vor und nach echtem Containerneustart geprüft. Beide aktiven Beziehungen
  bleiben erhalten; die zweite Person erhält weiterhin keine fremden Aussagen.
- Nutzerinstanz auf 8891 mit Image `kingfisher:profiles-fabd446` aktualisiert.
  Vorheriger Container bleibt gestoppt; bestehendes Datenvolume erhalten.
  Sicherung `kingfisher-20260913T153953Z`: zehn SQLite-Snapshots geprüft;
  nach Update alle elf vorhandenen Live-Datenbanken mit `integrity_check=ok`.
  Health gesund, Namenssuche → echte Personenakte → Originalmail im Browser
  erneut geprüft. Keine neue synthetische Information im Nutzerbestand.
- Der reguläre lokale Docker-Build scheiterte am Download-Timeout bei PyPI.
  Lokales Image deshalb aus der vorhandenen Laufzeit `main-aca8c47` mit
  unveränderten Abhängigkeiten, aktuellem Python-Code und neu gebautem UI erstellt.
  GitHub hat zusätzlich den vollständigen Docker-Build erfolgreich ausgeführt.
  Ein erster Test mit Mac-Temp-Bindmount scheiterte an Dateirechten; der erneute
  Lauf mit eigenem Docker-Volume bestand. Kein Eingriff in fremde Container.

**Punkt 07 ist damit erfüllt: 16 von 20 = 80 % der bestehenden Abnahmeliste.**
Die Kriterien wurden nicht um neue Fähigkeiten ergänzt; die begrenzten visuellen
Abweichungen sind ausdrücklich in SDR-013 dokumentiert.

## Grenzen

Diese Abnahme bestätigt weder automatische korrekte Verdichtung noch perfekte
Identitätsklärung oder vollständige semantische Suche. Die Kontakte zeigen
vorhandene Quellen und behalten ungeklärte Fälle. Keine persönlichen Daten in
Repository oder Screenshotbelegen. Der neue Kalender-Retrieval-Versuch bleibt
nach einer fehlgeschlagenen Prompt-Injection-Gegenprobe deaktiviert:
[Versuch](../evaluations/model-selection/calendar-recall-experiment/README.md).
Kontrollierte Selbstverbesserung ist [geplant](CONTROLLED-IMPROVEMENT.md), kein
bereits automatisch arbeitender Dienst.
