# Kingfisher Screen Reference Index v1

> **Hinweis (Oktober 2026):** Die hier genannten KI-Entwürfe (PNG) zeigten persönliche Beispieldaten und wurden
> vor der Veröffentlichung des Repositorys entfernt. Maßgeblich für die Gestaltung sind seither
> `docs/16-gestaltung.md`, die Boards unter `04_UI_Foundation` und `05_Components` und die laufende Oberfläche.

Dies ist keine Design-Vision. Es ist die verbindliche Zuordnung für die Implementierung. Für jede Ansicht gilt die entsprechende Original-PNG als visuelle Wahrheit.

| Bereich | Kanonische Datei | Regel für die Implementierung |
|---|---|---|
| Morgenbriefing am See | `morning-briefing-canonical-source-v1.png` | Helle Morgenlandschaft, dunkle Seitennavigation, persönliche Begrüßung und Kartenreihenfolge exakt bewahren. |
| Morgenbriefing / Dashboard | `morning-briefing-dashboard-canonical-source-v1.png` | Informationsdichte, Moduswechsel hell/dunkel und räumliche Ordnung aus dem Original übernehmen. |
| Gesamtübersicht | `system-overview-canonical-source-v1.png` | Alle darin sichtbaren Bildschirmtypen sind Vorbilder; nicht zu einer neuen Designsprache verdichten. |
| Dunkler Fokusmodus | `dark-dashboard-canonical-source-v1.png` | Dunkle Karten, sparsame Türkis-/Orangekontraste und Eisvogel-Motiv genau in diesem Verhältnis halten. |
| Visuelle Grundlagen | `visual-foundation-canonical-source-v1.png` | Für Markenbilder, Symbolsprache, Farbstimmung und Muster maßgeblich. |

## Unverhandelbare Regel

Ein Coding-Agent baut anhand der passenden Referenzdatei nach. Er kombiniert keine Screens frei, entfernt keine markante Bildwelt und erzeugt keine neue UI-Ästhetik. Fehlt eine Ansicht, erstellt er nur einen strukturell reduzierten Ableger der nächstliegenden Referenz und meldet `SCREEN-DEVIATION-REQUEST`.

Beispiel: Eine Aufgabenansicht darf das gleiche Sidebar-, Karten- und Hintergrundprinzip der Dashboard-Referenz übernehmen, aber nicht zu einem fremden, generischen Aufgaben-Tool werden.
