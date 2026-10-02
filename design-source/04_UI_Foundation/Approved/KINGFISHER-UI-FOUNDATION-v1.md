# Kingfisher UI Foundation v1 — Review

Diese Datei ist die verbindliche visuelle Grundlage für die Implementierung. Der Coding-Agent darf weder Farben, Größen, Schriften, Icons, Bilder noch Effekte ergänzen oder ersetzen. Fehlt etwas, meldet er `ASSET-REQUEST` mit Zweck, Zielplattform und benötigter Größe.

## 1. Typografie

- **Cormorant Garamond** ausschließlich für große, ruhige Orientierung: Seitenbegrüßung, Tagesüberschrift, große leere Zustände. Keine Card-Titel, Buttons, Navigation oder Tabellen.
- **Inter** für die gesamte Bedienoberfläche. 400 für Fließtext, 500 für Metadaten, 600 für Titel/Aktionen, 700 ausschließlich für kleine Labels.
- Großschreibung nur für das bestehende Brand-Wordmark und sehr sparsame Statuslabels. Keine neue Display-Schrift und keine künstlich verbreiterten Buchstaben.

Beispiel: `Guten Morgen, Lena.` ist `display-lg`; `3 Prioritäten für heute` ist `body`; `HEUTE` ist `label`.

## 2. Feste Größen

- **Desktop-Referenz:** 1440 px breit, linke Navigation 248 px, Arbeitsfläche max. 1120 px, Seitenabstand 40 px.
- **Tablet:** ab 768 px, 8-Spalten-Raster, 28 px Seitenabstand. Die Navigation wird zur schmalen Icon-Leiste bzw. zum Sheet.
- **Mobil:** 390 px Referenzbreite, 4-Spalten-Raster, 20 px Seitenabstand, 72 px Bottom Navigation. Keine Desktop-Ansicht zusammenschieben.
- **Abstände:** ausschließlich 4, 8, 12, 16, 20, 24, 32, 40, 48 oder 64 px.
- **Ecken:** 8 px für kleine Controls, 12 px Inputs/Buttons, 16 px Cards, 24 px große Medienflächen. Keine gemischten Zwischenwerte.
- **Icons:** nur 16/20/24/32 px, Strichstärke 1.8 px. Nur Dateien aus `02_Icons/Approved`.

## 3. Farbe und Bildwelt

- **Heller Arbeitsmodus:** `canvas #F7F5EF`, Cards `surface #FFFEFA`, Text `ink #062B3A`. Die Wärme kommt aus dem Canvas, nicht aus gelben UI-Elementen.
- **Dunkler Fokusmodus:** `navy-deep #032D40` als Grundfläche, Text `on-dark #F4FAF9`, Linien und sekundäre Informationen gedämpft.
- Türkis ist eine aktive, informative Farbe; Orange nur für dringende Priorität oder gezielte Akzente. Es ist kein zweiter Primärbutton.
- Freigegebene Kingfisher- und Wasser-Medien bleiben selten und großzügig eingesetzt: Hero, leerer Zustand, eine fokussierte Karte. Nie als Dekoration in jeder Karte.

## 4. Zustände

- Standard: ruhige Fläche, feine `line`-Kontur.
- Hover: Hintergrund `surface-muted`, kein Farbwechsel des gesamten Controls, 120 ms.
- Fokus: 2 px Ring `focus` mit 2 px Abstand; immer sichtbar für Tastatur.
- Ausgewählt: `navy` Fläche oder 8 % Türkis-Tönung, nie ausschließlich über Farbe kommunizieren.
- Fehler: `danger` plus Klartext; Erfolg: `success` plus Klartext; Warnung: `warning` plus Klartext.

## 5. Harte Implementierungsregel

```text
USE: tokens + approved assets + approved components.
NEVER: stock photos, emoji, Lucide replacement, generated icon/logo/image,
random gradients, ad-hoc shadow, ad-hoc radius, arbitrary pixel values.
IF MISSING: ASSET-REQUEST.
```

## 6. Nächste verbindliche Referenzen

1. Komponentenblatt: Navigation, Buttons, Inputs, Cards, Task Row, Timeline, Chat, Calendar, Status.
2. Finale Screens: Morning Briefing, Aufgaben & Projekte, Gespräche, Wissen, Kalender, Einstellungen.
3. Code-Paket: Tokens, Komponentenvertrag und Asset-Manifest.
