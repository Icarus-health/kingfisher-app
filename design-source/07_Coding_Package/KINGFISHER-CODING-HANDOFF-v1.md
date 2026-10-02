# Kingfisher — Coding Handoff v1

## Auftrag

Implementiere Kingfisher so, dass die kanonischen Screen-PNGs wiedererkennbar nachgebaut werden. Verwende ausschließlich den Asset Manifest und die freigegebenen Dateien.

## Startreihenfolge

1. Dateien aus `07_Coding_Package`, `06_Screens/Approved`, `01_Brand/Approved`, `02_Icons/Approved`, `03_Media/Approved` und `04_UI_Foundation/Approved` in das Projekt übernehmen.
2. Morning Briefing desktop anhand von `morning-briefing-canonical-source-v1.png` (vor der Veröffentlichung entfernt) nachbauen.
3. Eine Screenshot-Prüfung gegen die Vorlage machen.
4. Erst danach die übrigen Ansichten umsetzen – immer mit der jeweils zugeordneten PNG geöffnet.

## Visual-Fidelity-Check pro Screen

- linke Navigation: Größe, Farbe, Position und aktive Zeile
- Header: Begrüßung, Zeit/Status, Bildfläche und Eisvogel
- Karten: Reihenfolge, Anzahl, Proportion, Ecken und Kontrast
- Typografie: gleiche Rangfolge; keine neue Display-Stilrichtung
- Medien: nur an den in der Vorlage sichtbaren Stellen
- Dark mode: nur aus der Dark-Dashboard-Referenz ableiten

## Stop-Regel

Wenn eine Entscheidung nicht eindeutig von einer Referenz ablesbar ist, nicht raten. `SCREEN-DEVIATION-REQUEST` senden.

Beispiel: Für eine neue Kalenderleiste kann dieselbe Navigation und Kartensprache verwendet werden. Ein zusätzlicher Verlauf, eine neue Illustration oder eine generische Kalender-Komponente sind nicht zulässig, bis sie freigegeben wurden.
