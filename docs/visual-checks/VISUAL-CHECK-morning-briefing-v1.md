# VISUAL-CHECK — Morning Briefing v1

- Status: `pass-with-approved-deviations`
- Reference: `design-source/06_Screens/Approved/morning-briefing-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Native viewport: `1521 × 1034`
- Additional viewport: `1440 × 1034`
- Browser: Playwright Chromium fallback
- Date: 2026-09-01

## Vergleich

- Seitenkante und Sidebar: 220 px wie in der Referenz.
- Hero-/Card-Übergang: Card-Oberkante bei 377 px.
- Drei Karten, Reihenfolge, Inhalte, Zeilen und Informationsdichte entsprechen
  der Referenz.
- Tageslinie und Command Bar bleiben in derselben Hierarchie; die Command Bar
  beginnt im nativen Viewport bei 929 px.
- Approved Fonts, Farben, Medien und SVGs werden direkt aus `design-source/`
  geladen.
- Browser-Konsole: 0 Fehler, 0 Warnungen.

Ein Null-Pixel-Diff ist wegen der ausdrücklich genehmigten Abweichungen nicht
erwartbar. Im menschlichen Overlay-Vergleich wurden keine weiteren
Screen-Abweichungen festgestellt.

## Unterschiede

Nur die in `docs/screen-deviations/SDR-001-approved-first-slice.md`
dokumentierten und genehmigten Unterschiede:

- keine Avatare oder Ersatzkreise;
- manifestierter transparenter Flugvogel statt Sitzvogel und Ast;
- Sidebar-App-Icon plus Code-Text statt eines nicht vorhandenen breiten Logos;
- genehmigte Zuordnung vorhandener Icons für nicht manifestierte Symbole;
- Open-Meteo-Attribution nur im aktivierten Wetterbetrieb.
