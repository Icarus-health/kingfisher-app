# VISUAL-CHECK — Dashboard und Morning Briefing v2

- Status: `pass-with-approved-deviations`
- Reference: vom Product Owner freigegebene V3-Ansicht und
  `design-source/06_Screens/Approved/morning-briefing-dashboard-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: Codex In-app Browser
- Date: 2026-09-02

## Nachweis

- Der deterministische Fixture-Zustand zeigt drei Prioritäten, drei laufende
  Aktivitäten und vier spätere Termine.
- Logo, Sitzvogel, Tageslinie, Flugvogel, Command Bar und Karten verwenden nur
  Dateien aus Asset Manifest 1.1.
- Das Morning Briefing öffnet als breiter Drawer von rechts und lässt sich über
  „Dashboard“ wieder schließen.
- Audio startet und pausiert; das Tempo schaltet über `1×`, `1,25×`, `1,5×`
  und zurück auf `1×`.
- Die Meeting-Vorbereitung verwendet im Fixture den als Termin markierten
  Eintrag „Dr. Kranz / Strategiegespräch“.
- Im Live-Zustand bleiben nicht verbundene Kalender-, Mail-, Wetter-, Routen-
  und Nachrichtenquellen ehrlich leer; Fixture-Inhalte werden nicht angezeigt.
- Browser-Konsole: 0 Fehler, 0 Warnungen.

Die Geometrie entspricht der freigegebenen V3-Ansicht. Uhrzeit, Datum,
Audio-Länge und Live-Inhalte sind echte Laufzeitdaten und deshalb keine
Pixel-Diff-Konstanten.

## Unterschiede

Nur die ausdrücklich genehmigten Punkte aus
`docs/screen-deviations/SDR-001-approved-first-slice.md` und
`docs/screen-deviations/SDR-002-approved-v3-controls-and-media.md`.
