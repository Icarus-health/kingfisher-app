# VISUAL-CHECK — Gedächtnis-Graph v1

- Status: `approved-empty-state; populated-graph-check-pending`
- Reference: section 05 of
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Browser: Codex In-app Browser
- Date: 2026-09-03

## Live verification

- The local Docker page at `/memory` loads from the existing read-only
  `/api/v1/memory/graph` projection.
- The five available categories switch correctly: Menschen, Projekte, Themen,
  Entscheidungen and Dokumente.
- Browser console: 0 errors, 0 warnings.
- The checked local SQLite database did not contain graph nodes. No fixture or
  demonstration data was inserted into the user's persistent volume.

## Approved difference

The canonical reference has no desktop empty state. The actual empty state is
approved in `docs/screen-deviations/SDR-004-approved-memory-empty-state.md`.

## Remaining gate

Once the user has imported a local source, compare the populated graph at the
canonical desktop viewport with section 05. The check is deliberately not
marked `pass` before that real-data comparison is possible.

## Nachprüfung 7. September 2026

Referenz: Abschnitt 05 derselben Originalübersicht. Viewport: 1521 × 1034.
Die aktuelle Ansicht wurde lesend gegen die lokale geschützte API geprüft.
Vorher waren Namen innerhalb der Kreise auf 11 px eingeengt und mitten im
Wort umgebrochen. Die Beschriftung steht jetzt unter den Knoten mit 14 px;
die Kreise verwenden vorhandene Manifest-Symbole für den jeweiligen Typ.
Es werden keine erfundenen Personenbilder verwendet.

Build und Assetprüfung bestanden. Playwright prüft die gerenderte Position
der Beschriftung, geladene Symbole, Tastaturöffnung der Registry-Akte und
Neuladen ohne JavaScript-/Konsolenfehler. Browser plugin nicht verfügbar.
Nachweis im Aufgabenordner: outputs/memory-labels-after.png. Nach dem
Ausrollen wurde die aktuelle Containerdarstellung unter outputs/audit-memory.png
erneut erfasst; Einstellungen, Gedächtnis, Aufgaben und Heute laden fehlerfrei.

Gesamtergebnis weiterhin offen: Ein dicht belegter Graph mit allen Knotentypen,
langen Namen und Verbindungen ist separat visuell zu prüfen. Die aktuelle
Prüfung schließt weder den gesamten Screen noch Roadmap-Punkt 16 ab.

## Größere Bestände

Die bisherige feste Begrenzung auf zehn Knoten ließ weitere geladene Personen
und Projekte unerreichbar. Der Graph bietet nun Zurück/Weiter für die jeweils
gewählte Kategorie und zeigt den sichtbaren Bereich mit Gesamtzahl. Beim
Kategoriewechsel beginnt die Auswahl wieder auf der ersten Seite. Die
Graphprojektion selbst und gespeicherte Daten bleiben unverändert.

Chromium bei 1521 × 1034 mit gebauter UI und synthetischer Graphantwort:
23 Personen über drei Seiten, Randzustände der Schaltflächen, Zurückblättern,
Kategoriewechsel und leere Projekte bestanden. Keine Daten geschrieben.
Screenshot: outputs/memory-pagination.png im Aufgabenordner. Build und
Assetmanifest bestanden. Diese Prüfung belegt die Erreichbarkeit der geladenen
Knoten, nicht eine vollständige Prüfung aller serverseitigen Größenlimits.
Die neue Seitenauswahl ist eine funktionale Ergänzung der Referenz; die
vollständige visuelle Abnahme bleibt offen.

Dichteprüfung bei 1440 × 900: Zehn Knoten mit dreizeiligen langen Namen
reproduzierten eine Überdeckung der Seitenauswahl durch die unterste
Beschriftung. Der untere Knoten steht nun höher. Derselbe geometrische
Browsercheck sowie der vollständige Seitenwechseltest bestehen danach.
Screenshot: outputs/memory-dense-long-labels.png im Aufgabenordner.
