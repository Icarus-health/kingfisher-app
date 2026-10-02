# VISUAL-CHECK — Gespräch und Kontext v1

- Status: `pass-with-approved-deviations`
- Reference: Screen 04 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: Playwright Chromium fallback
- Date: 2026-09-01

## Vergleich

- Dunkle Navigation, helle Kontextspalte und ruhige Gesprächsfläche folgen der
  kanonischen Dreiteilung.
- Nutzertext, Assistant-Karte und feste untere Command Bar verwenden die
  freigegebenen Komponentenformen und Tokens.
- Der Kontext wird aus dem lokalen Icarus-Gedächtnis gelesen; es werden keine
  Personendaten oder Demo-Projekte erfunden.
- Direkter Reload auf `/conversations/:id` stellt denselben Verlauf aus SQLite
  wieder her.
- Browser-Konsole: 0 Fehler, 0 Warnungen.

## Unterschiede

Nur die genehmigten Punkte aus
`docs/screen-deviations/SDR-001-approved-first-slice.md`: keine Avatarflächen
und keine nicht manifestierten Header-Aktionsicons.
