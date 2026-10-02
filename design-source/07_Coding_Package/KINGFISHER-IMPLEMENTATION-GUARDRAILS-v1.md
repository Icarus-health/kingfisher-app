# Kingfisher Implementation Guardrails v1

## Ziel

Der Coding-Agent implementiert die vorhandene Kingfisher-Gestaltung. Er ist kein Art Director und darf sie nicht neu interpretieren.

## Reihenfolge der Wahrheit

1. **Kanonische Screen-PNGs in `06_Screens/Approved`** — höchste Priorität.
2. **Freigegebene Brand-, Icon- und Medien-Dateien** — nur die konkreten Dateien verwenden.
3. **UI Tokens und Komponentenvertrag** — für technische Konsistenz innerhalb der Vorlage.
4. Bei Widerspruch gewinnt immer die kanonische Screen-PNG.

## Verboten

- Keine neuen Logos, Icons, Illustrationen, Fotos, Hintergründe oder Farbwelten.
- Keine Neuanordnung, Verdichtung oder Vereinfachung eines kanonischen Screens.
- Keine generischen SaaS-Komponenten, Emoji, Stockbilder, Platzhalter-Avatare oder selbst generierten Gradients.
- Keine freie Mischung aus hellem und dunklem Screenshotmodus.

## Erlaubt

- Echte Daten an den vorgesehenen Stellen einsetzen.
- Responsives Verhalten hinzufügen, ohne visuelle Reihenfolge und Hierarchie zu verändern.
- Freigegebene Tokens für Abstände, Fokuszustände und Barrierefreiheit verwenden.

## Pflichtablauf pro Screen

1. Passende Referenz-PNG auswählen und als sichtbare Referenz neben dem Code verwenden.
2. Desktop zuerst mit identischer Bildhierarchie umsetzen.
3. Eigenen Render gegen die PNG prüfen: Header, Sidebar, Bildfläche, Kartenanordnung, Typohierarchie und Kontrast.
4. Bei einer nicht direkt abgebildeten Entscheidung anhalten und `SCREEN-DEVIATION-REQUEST` senden.

## Anfrageformat

```text
SCREEN-DEVIATION-REQUEST
Screen: …
Reference: …
Missing decision: …
Why no reference covers it: …
Smallest safe option: …
```

Beispiel: Für eine mobile Darstellung darf die linke Navigation zu einer Navigation am unteren Rand werden. Die Landschaft, Begrüßung und Priorisierung des Morning Briefings dürfen dadurch jedoch nicht verschwinden oder neu erfunden werden.
