# Kingfisher Visual Acceptance v1

## Pflicht vor einem Merge

1. Referenz-PNG und gebauten Screen bei derselben Desktop- oder Mobilbreite öffnen.
2. Erst räumlich prüfen: Sidebar/Bottom Navigation, Header, Bildfläche, Kartenreihenfolge und dominante Bereiche.
3. Danach Stil prüfen: helle/dunkle Stimmung, Typohierarchie, Icon-Familie, Kontrast und Bildplatzierung.
4. Dann Zustände prüfen: Laden, Leer, Fehler, Erfolg und Deaktiviert verwenden nur die definierte vorhandene Struktur.
5. Sichtbare Abweichung ohne freigegebene `SCREEN-DEVIATION-REQUEST` = nicht abnahmefähig.

## Ergebnisformat

```text
VISUAL-CHECK
Screen: …
Reference: …
Viewport: …
Result: pass | blocked
Differences: none | …
Approved deviation: link or none
```

Beispiel: Wenn die Karten im gebauten Morning Briefing untereinander statt wie in der Vorlage verteilt liegen, lautet das Ergebnis `blocked` – auch wenn alle Inhalte technisch funktionieren.
