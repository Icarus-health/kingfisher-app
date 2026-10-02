# Kingfisher Components v1 — Review

Alle Komponenten verwenden ausschließlich die UI Tokens und Approved Assets. Varianten dürfen nur über den beschriebenen Inhalt oder Zustand entstehen, niemals durch neue Formensprache.

## Bestandteile

- **Sidebar:** 248 px auf Desktop; ein klarer aktiver Punkt; profilbezogene Aktionen im Footer.
- **Command Bar:** primärer Einstieg für Suche und Agent; 58 px hoch, immer zugänglich über `⌘K`.
- **Priority Card:** eine einzige dominierende Tagespriorität. Große Überschrift, Kontext, Dauer, klare Folgeaktion.
- **Task Row:** Checkbox, Aufgabe, Kontext, ein Status oder Termin. Keine mehrzeilige Kontrollwand.
- **Momentum Timeline:** eine lesbare Tageslinie; maximal vier hervorgehobene Zeitpunkte.
- **Calendar Moment:** zeigt den einen nächsten Termin und dessen Vorbereitungsaktion.
- **Assistant Message:** erscheint als nüchterne, hilfsbereite Karte, niemals als Chatblasen-Flut.
- **Status / Feedback:** Status mit Text und Farbe; Toasts oben rechts auf Desktop, oben auf Mobil.

## Button-Vertrag

- Primary: Navy, nur eine Hauptaktion pro Kontext.
- Secondary: helle Fläche, feine Kontur.
- Tertiary: Textaktion in Türkis, nur neben klarer Primäraktion.
- Destructive: erst in einem Bestätigungskontext, niemals neben einer normalen Aktion als gleichwertiger Button.

## Accessibility

- Jeder Zustand muss neben Farbe über Text, Icon oder Form lesbar sein.
- Mindestzielgröße: 40 × 40 px, in Mobile 44 × 44 px.
- Keyboard-Fokus immer sichtbar mit `focus` Token.
