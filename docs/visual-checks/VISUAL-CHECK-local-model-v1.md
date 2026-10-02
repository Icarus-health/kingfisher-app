# VISUAL-CHECK — lokale Modelleinrichtung

Screen: Lokale KI innerhalb der Einstellungen.
Reference: Screen 14, system-overview-canonical-source-v1.png (vor der Veröffentlichung entfernt).
Viewport: 1521 × 1034; Gesprächsablauf zusätzlich 1440 × 1000.
Result: pass im ausdrücklich begrenzten Umfang von SDR-010.
Approved deviation: ../screen-deviations/SDR-010-reviewed-local-model-setup.md.

## Visuelle Prüfung

Die ursprüngliche zweispaltige Einstellungsstruktur und dunkle Seitennavigation
bleiben erhalten. Der geöffnete Bereich verwendet dieselben Karten, Schriften,
Abstände und Schaltflächen. Namen, Fehlertexte und Aktionen bleiben im Bereich
lesbar; kein Overlay und keine überlagernden Elemente. Eingerichtet ist die
Ansicht wieder auf eine kompakte Zeile reduzierbar. Die zusätzliche lokale
Modelleinrichtung ist durch SDR-010 ausdrücklich eingegrenzt.

Screenshots im Aufgabenordner unter outputs/: model-loading-full.png,
model-empty-full.png, model-failed-full.png, model-success-full.png und
model-compact-full.png. Laden und leere Einrichtung wurden für die visuelle
Zustandsprüfung über kontrollierte GET-Antworten erzeugt; kein Zurücksetzen des
Datenbestands. Fehlgeschlagenes und erfolgreiches Verbinden liefen tatsächlich
gegen Docker und das lokale Ollama. Browser plugin nicht verfügbar; vorhandenes
Playwright verwendet.

## Funktionsprüfung

- Nicht erreichbare Einrichtung als Fehler anzeigen und erfolgreich wiederholen.
- Nicht installiertes Modell speichern und Verbindungsfehler sichtbar machen.
- Vorhandenes qwen3.5:4b auswählen, verbinden und tatsächliche Antwort prüfen.
- „Zum Gespräch“ verwenden, neues Gespräch mit realer Antwort 42 führen, neu laden.
- Container wirklich neu starten; gespeicherte Modellwahl und neue Antwort bleiben erhalten.
- Laden: Speichern deaktiviert, laufende Suche nicht als Fehler darstellen.

Die erneute Zustandsprüfung nach Korrektur des irreführenden Ladehinweises
ist bestanden. Build und Assetmanifest bestanden; lokal ausgerollt. Vollständige UI-Abnahme anderer Bereiche
und die Docker-Desktop-Neuinstallation gehören nicht zu diesem Einrichtungsnachweis.
