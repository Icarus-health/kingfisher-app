# VISUAL-CHECK — Gespräch und Kontext v2

- Status: `pass-with-approved-deviations`
- Reference: Screen 04 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: Codex In-app Browser
- Date: 2026-09-02

## Nachweis

- Eine Frage aus dem Dashboard erzeugt eine Unterhaltung und navigiert auf
  `/conversations/:id`.
- Nutzertext und Kingfisher-Antwort werden in der vorgesehenen Dreiteilung aus
  Navigation, Kontext und Gespräch dargestellt.
- Ohne konfiguriertes Modell erscheint eine ehrliche lokale Systemantwort;
  keine Modellantwort wird simuliert.
- Browser-Reload und vollständiger Container-Neustart stellen denselben Verlauf
  aus dem persistenten SQLite-Volume wieder her.
- Browser-Konsole: 0 Fehler, 0 Warnungen.

## Unterschiede

Nur die bereits genehmigten Punkte aus
`docs/screen-deviations/SDR-001-approved-first-slice.md`: keine Avatarflächen
und keine nicht manifestierten Header-Aktionsicons.
